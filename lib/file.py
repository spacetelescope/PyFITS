import gzip
import os
import re
import sys
import tempfile
import urllib
import warnings
import zipfile

import numpy as np
from numpy import char as chararray
from numpy import memmap as Memmap

from pyfits import rec
from pyfits.card import Card, _pad
from pyfits.column import _FormatP, _VLF
from pyfits.hdu import TableHDU, BinTableHDU, CompImageHDU
from pyfits.hdu.base import _NonstandardHDU, _TempHDU
from pyfits.hdu.extension import _NonstandardExtHDU
from pyfits.hdu.groups import GroupData
from pyfits.hdu.image import _ImageBaseHDU
from pyfits.util import Extendable, _tofile, _chunk_array, _unsigned_zero, \
                        _is_pseudo_unsigned


BLOCK_SIZE = 2880 # the FITS block size
PYTHON_MODES = {'readonly': 'rb', 'copyonwrite': 'rb', 'update': 'rb+',
                'append': 'ab+', 'ostream': 'w'}  # open modes
MEMMAP_MODES = {'readonly': 'r', 'copyonwrite': 'c', 'update': 'r+'}


class _File(object):
    """
    A file I/O class.
    """

    __metaclass__ = Extendable

    def __init__(self, name=None, mode='copyonwrite', memmap=False, **kwargs):
        if name is None:
            self._simulateonly = True
            return
        else:
            self._simulateonly = False

        if mode not in PYTHON_MODES.keys():
            raise ValueError("Mode '%s' not recognized" % mode)


        # Determine what the _File object's name should be
        if isinstance(name, file):
            self.name = name.name
        elif isinstance(name, basestring):
            if mode != 'append' and not os.path.exists(name) and \
               not os.path.splitdrive(name)[0]:
                #
                # Not writing file and file does not exist on local machine and
                # name does not begin with a drive letter (Windows), try to
                # get it over the web.
                #
                self.name, fileheader = urllib.urlretrieve(name)
            else:
                self.name = name
        else:
            if hasattr(name, 'name'):
                self.name = name.name
            elif hasattr(name, 'filename'):
                self.name = name.filename
            elif hasattr(name, '__class__'):
                self.name = str(name.__class__)
            else:
                self.name = str(type(name))

        self.mode = mode
        self.memmap = memmap
        self.code = None
        self.dims = None
        self.offset = 0

        if 'ignore_missing_end' in kwargs:
            self.ignore_missing_end = kwargs['ignore_missing_end']
        else:
            self.ignore_missing_end = False

        self.uint = kwargs.get('uint16', False) or kwargs.get('uint', False)

        if memmap and mode not in ['readonly', 'copyonwrite', 'update']:
            raise NotImplementedError(
                   "Memory mapping is not implemented for mode `%s`." % mode)
        else:
            # Initialize the internal self.__file object
            if isinstance(name, file) or isinstance(name, gzip.GzipFile):
                if hasattr(name, 'closed'):
                    closed = name.closed
                    foMode = name.mode
                else:
                    if name.fileobj is not None:
                        closed = name.fileobj.closed
                        foMode = name.fileobj.mode
                    else:
                        closed = True
                        foMode = PYTHON_MODES[mode]

                if not closed:
                    if PYTHON_MODES[mode] != foMode:
                        raise ValueError(
                            "Input mode '%s' (%s) does not match mode of the "
                            "input file (%s)." % (mode, PYTHON_MODES[mode],
                                                  name.mode))
                    self.__file = name
                elif isinstance(name, file):
                    self.__file = open(self.name, PYTHON_MODES[mode])
                else:
                    self.__file = gzip.open(self.name, PYTHON_MODES[mode])
            elif isinstance(name, basestring):
                if os.path.splitext(self.name)[1] == '.gz':
                    # Handle gzip files
                    if mode in ['update', 'append']:
                        raise NotImplementedError(
                              "Writing to gzipped fits files is not supported")
                    zfile = gzip.GzipFile(self.name)
                    self.tfile = tempfile.NamedTemporaryFile('rb+',-1,'.fits')
                    self.name = self.tfile.name
                    self.__file = self.tfile.file
                    self.__file.write(zfile.read())
                    zfile.close()
                elif os.path.splitext(self.name)[1] == '.zip':
                    # Handle zip files
                    if mode in ['update', 'append']:
                        raise NotImplementedError(
                              "Writing to zipped fits files is not supported")
                    zfile = zipfile.ZipFile(self.name)
                    namelist = zfile.namelist()
                    if len(namelist) != 1:
                        raise NotImplementedError(
                          "Zip files with multiple members are not supported.")
                    self.tfile = tempfile.NamedTemporaryFile('rb+',-1,'.fits')
                    self.name = self.tfile.name
                    self.__file = self.tfile.file
                    self.__file.write(zfile.read(namelist[0]))
                    zfile.close()
                else:
                    self.__file=open(self.name, PYTHON_MODES[mode])
            else:
                # We are dealing with a file like object.
                # Assume it is open.
                self.__file = name

                # If there is not seek or tell methods then set the mode to
                # output streaming.
                if not hasattr(self.__file, 'seek') or \
                   not hasattr(self.__file, 'tell'):
                    self.mode = mode = 'ostream'

                if (self.mode in ('copyonwrite', 'update', 'append') and
                    not hasattr(self.__file, 'write')):
                    raise IOError("File-like object does not have a 'write' "
                                  "method, required for mode '%s'."
                                  % self.mode)

                if self.mode == 'readonly' and \
                   not hasattr(self.__file, 'read'):
                    raise IOError("File-like object does not have a 'read' "
                                  "method, required for mode 'readonly'."
                                  % self.mode)

            # For 'ab+' mode, the pointer is at the end after the open in
            # Linux, but is at the beginning in Solaris.

            if mode == 'ostream':
                # For output stream start with a truncated file.
                self._size = 0
            elif isinstance(self.__file, gzip.GzipFile):
                self.__file.fileobj.seek(0, 2)
                self._size = self.__file.fileobj.tell()
                self.__file.fileobj.seek(0)
                self.__file.seek(0)
            elif hasattr(self.__file, 'seek'):
                self.__file.seek(0, 2)
                self._size = self.__file.tell()
                self.__file.seek(0)
            else:
                self._size = 0

    @property
    def _mm(self):
        return Memmap(self.name, offset=self.offset,
                      mode=MEMMAP_MODES[self.mode], dtype=self.code,
                      shape=self.dims)

    def getfile(self):
        return self.__file

    def _readheader(self, cardlist, keylist, blocks):
        """
        Read blocks of header, and put each card into a list of cards.
        Will deal with CONTINUE cards in a later stage as CONTINUE cards
        may span across blocks.
        """

        if len(block) != BLOCK_SIZE:
            raise IOError('Block length is not %d: %d.'
                          % (BLOCK_SIZE, len(block)))
        elif (blocks[:8] not in ['SIMPLE  ', 'XTENSION']):
            raise IOError('Block does not begin with SIMPLE or XTENSION.')

        for i in range(0, len(BLOCK_SIZE), Card.length):
            card = Card('').fromstring(block[i:i + Card.length])
            key = card.key

            cardlist.append(card)
            keylist.append(key)
            if key == 'END':
                break

    def _readHDU(self):
        """
        Read the skeleton structure of the HDU.
        """

        if not hasattr(self.__file, 'tell') or \
           not hasattr(self.__file, 'read'):
            raise EOFError

        end_RE = re.compile('END' + ' '*77)
        _hdrLoc = self.__file.tell()

        # Read the first header block.
        block = self.__file.read(BLOCK_SIZE)
        if block == '':
            raise EOFError

        hdu = _TempHDU()
        hdu._raw = ''
        blocks = []

        # continue reading header blocks until END card is reached
        while True:

            # find the END card
            mo = end_RE.search(block)
            if mo is None:
                blocks.append(block)
                block = self.__file.read(BLOCK_SIZE)
                if block == '':
                    break
            else:
                break
        blocks.append(block)

        if not end_RE.search(block) and not self.ignore_missing_end:
            raise IOError('Header missing END card.')

        hdu._raw = ''.join(blocks)

        _size, hdu.name = hdu._getsize(hdu._raw)

        # get extname and extver
        if hdu.name == '':
            hdu.name, hdu._extver = hdu._getname()
        elif hdu.name == 'PRIMARY':
            hdu._extver = 1

        hdu._file = self.__file
        hdu._hdrLoc = _hdrLoc                # beginning of the header area
        hdu._datLoc = self.__file.tell()     # beginning of the data area

        # data area size, including padding
        hdu._datSpan = _size + _pad_length(_size)
        hdu._new = 0
        hdu._ffile = self
        if isinstance(hdu._file, gzip.GzipFile):
            pos = self.__file.tell()
            self.__file.seek(pos + hdu._datSpan)
        else:
            self.__file.seek(hdu._datSpan, 1)

            if self.__file.tell() > self._size:
                warnings.warn('Warning: File may have been truncated: actual '
                              'file length (%i) is smaller than the expected '
                              'size (%i)'  % (self._size, self.__file.tell()))

        return hdu

    def writeHDU(self, hdu, checksum=False):
        """
        Write *one* FITS HDU.  Must seek to the correct location
        before calling this method.
        """

        #TODO: Maybe move some of the logic for this to the appropriate HDU classes

        if isinstance(hdu, _ImageBaseHDU):
            hdu.update_header()
        elif isinstance(hdu, CompImageHDU):
            hdu.updateCompressedData()
        return (self.writeHDUheader(hdu,checksum)[0],) + self.writeHDUdata(hdu)

    def writeHDUheader(self, hdu, checksum=False):
        """
        Write FITS HDU header part.
        """

        #TODO: Maybe some of the logic for this to the appropriate HDU classes

        # If the data is unsigned int 16, 32, or 64 add BSCALE/BZERO
        # cards to header

        if hdu._data_loaded and hdu.data is not None and \
           not isinstance(hdu, _NonstandardHDU) and \
           not isinstance(hdu, _NonstandardExtHDU) and \
           _is_pseudo_unsigned(hdu.data.dtype):
            hdu._header.update('BSCALE', 1,
                               after='NAXIS' + repr(hdu.header.get('NAXIS')))
            hdu._header.update('BZERO', _unsigned_zero(hdu.data.dtype),
                               after='BSCALE')

        # Handle checksum
        if 'CHECKSUM' in hdu._header:
            del hdu.header['CHECKSUM']

        if 'DATASUM' in hdu._header:
            del hdu.header['DATASUM']

        if checksum == 'datasum':
            hdu.add_datasum()
        elif checksum == 'nonstandard_datasum':
            hdu.add_datasum(blocking='nonstandard')
        elif checksum == 'test':
            hdu.add_datasum(hdu._datasum_comment)
            hdu.add_checksum(hdu._checksum_comment, True)
        elif checksum == 'nonstandard':
            hdu.add_checksum(blocking='nonstandard')
        elif checksum:
            hdu.add_checksum(blocking='standard')

        blocks = repr(hdu._header.ascard) + _pad('END')
        blocks = blocks + _pad_length(len(blocks)) * ' '

        loc = 0
        size = len(blocks)

        if size % BLOCK_SIZE != 0:
            raise IOError('Header size (%d) is not a multiple of block size '
                          '(%d).' % (size, BLOCK_SIZE))

        if not self._simulateonly:
            if hasattr(self.__file, 'flush'):
                self.__file.flush()

            try:
               if self.__file.mode == 'ab+':
                   self.__file.seek(0,2)
            except AttributeError:
               pass

            try:
                loc = self.__file.tell()
            except (AttributeError, IOError):
                loc = 0

            self.__file.write(blocks)

            # flush, to make sure the content is written
            if hasattr(self.__file, 'flush'):
                self.__file.flush()

        # If data is unsigned integer 16, 32 or 64, remove the
        # BSCALE/BZERO cards
        if hdu._data_loaded and hdu.data is not None and \
           not isinstance(hdu, _NonstandardHDU) and \
           not isinstance(hdu, _NonstandardExtHDU) and \
           _is_pseudo_unsigned(hdu.data.dtype):
            del hdu._header['BSCALE']
            del hdu._header['BZERO']

        return loc, size

    def writeHDUdata(self, hdu):
        """
        Write FITS HDU data part.
        """

        #TODO: Maybe move some of the logic for this to the appropriate HDU classes

        loc = 0
        _size = 0

        if not self._simulateonly:
            if hasattr(self.__file, 'flush'):
                self.__file.flush()

            try:
                loc = self.__file.tell()
            except (AttributeError, IOError):
                loc = 0

        if isinstance(hdu, _NonstandardHDU) and hdu.data is not None:
            if not self._simulateonly:
                self.__file.write(hdu.data)

                # flush, to make sure the content is written
                self.__file.flush()

            # return both the location and the size of the data area
            return loc, len(hdu.data)

        elif isinstance(hdu, _NonstandardExtHDU) and hdu.data is not None:
            if not self._simulateonly:
                self.__file.write(hdu.data)
            _size = len(hdu.data)

            if not self._simulateonly:
                # pad the fits data block
                self.__file.write(_pad_length(_size) * '\0')

                # flush, to make sure the content is written
                self.__file.flush()

            # return both the location and the size of the data area
            return loc, _size + _pad_length(_size)

        elif hdu.data is not None:
            # Based on the system type, determine the byteorders that
            # would need to be swapped to get to big-endian output
            if sys.byteorder == 'little':
                swap_types = ('<', '=')
            else:
                swap_types = ('<',)

            # if image, need to deal with byte order
            if isinstance(hdu, _ImageBaseHDU):
                # deal with unsigned integer 16, 32 and 64 data
                if _is_pseudo_unsigned(hdu.data.dtype):
                    # Convert the unsigned array to signed
                    output = np.array(
                        hdu.data - _unsigned_zero(hdu.data.dtype),
                        dtype='>i%d' % hdu.data.dtype.itemsize)
                    should_swap = False
                else:
                    output = hdu.data

                    if isinstance(hdu.data, GroupData):
                        fname = hdu.data.dtype.names[0]
                        byteorder = output.dtype.fields[fname][0].str[0]
                    else:
                        byteorder = output.dtype.str[0]
                    should_swap = (byteorder in swap_types)

                if not self._simulateonly:
                    if should_swap:
                        # If we need to do byteswapping, do it in chunks
                        # so the original array is not touched
                        # output_dtype = output.dtype.newbyteorder('>')
                        # for chunk in _chunk_array(output):
                        #     chunk = np.array(chunk, dtype=output_dtype,
                        #                      copy=True)
                        #     _tofile(output, self.__file)

                        output.byteswap(True)
                        try:
                            _tofile(output, self.__file)
                        finally:
                            output.byteswap(True)
                    else:
                        _tofile(output, self.__file)

            # Binary table byteswap
            elif isinstance(hdu, BinTableHDU):
                if isinstance(hdu, CompImageHDU):
                    output = hdu.compData
                else:
                    output = hdu.data

                # And this is why it might make sense to move out some of the
                # logic...
                _size += self._binary_table_byte_swap(output)

            else:
                output = hdu.data

                if not self._simulateonly:
                    _tofile(output, self.__file)

            _size = _size + output.size * output.itemsize

            # pad the FITS data block
            if _size > 0 and not self._simulateonly:
                if isinstance(hdu, TableHDU):
                    self.__file.write(_pad_length(_size)*' ')
                else:
                    self.__file.write(_pad_length(_size)*'\0')

        # flush, to make sure the content is written
        if not self._simulateonly and hasattr(self.__file, 'flush'):
            self.__file.flush()

        # return both the location and the size of the data area
        return loc, _size+_pad_length(_size)

    def close(self):
        """
        Close the 'physical' FITS file.
        """
        if hasattr(self.__file, 'close'):
            self.__file.close()

        if hasattr(self, 'tfile'):
            del self.tfile

    def _binary_table_byte_swap(self, output):
        swapped = []
        nbytes = 0
        if sys.byteorder == 'little':
            swap_types = ('<', '=')
        else:
            swap_types = ('<',)
        try:
            if not self._simulateonly:
                for idx in range(output._nfields):
                    coldata = output.field(idx)
                    if isinstance(coldata, chararray.chararray):
                        continue
                    # only swap unswapped
                    # deal with var length table
                    if isinstance(coldata, _VLF):
                        for jdx, c in enumerate(coldata):
                            if (not isinstance(c, chararray.chararray) and
                                c.itemsize > 1 and
                                c.dtype.str[0] in swap_types):
                                swapped.append(c)
                            field = rec.recarray.field(output, idx)
                            if (field[jdx:jdx+1].dtype.str[0] in swap_types):
                                swapped.append(field[jdx:jdx+1])
                    else:
                        if (coldata.itemsize > 1 and
                            output.dtype.descr[idx][1][0] in swap_types):
                            swapped.append(rec.recarray.field(output, idx))

                for obj in swapped:
                    obj.byteswap(True)

                _tofile(output, self.__file)

                # write out the heap of variable length array
                # columns this has to be done after the
                # "regular" data is written (above)
                self.__file.write(output._gap * '\0')

            nbytes = output._gap

            for idx in range(output._nfields):
                if isinstance(output._coldefs._recformats[idx], _FormatP):
                    for jdx in range(len(output.field(idx))):
                        coldata = output.field(idx)[jdx]
                        if len(coldata) > 0:
                            nbytes = nbytes + coldata.nbytes
                            if not self._simulateonly:
                                coldata.tofile(self.__file)

            output._heapsize = nbytes - output._gap
        finally:
            for obj in swapped:
                obj.byteswap(True)

        return nbytes


    # Support the 'with' statement
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


def _pad_length(stringlen):
    """Bytes needed to pad the input stringLen to the next FITS block."""

    return (BLOCK_SIZE - (stringlen % BLOCK_SIZE)) % BLOCK_SIZE

