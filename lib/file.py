import gzip
import os
import re
import sys
import tempfile
import types
import urllib
import warnings
import zipfile

import numpy as np
from numpy import char as chararray
from numpy import memmap as Memmap

from pyfits import rec


PYTHON_MODES = {'readonly': 'rb', 'copyonwrite': 'rb', 'update': 'rb+',
                'append': 'ab+', 'ostream': 'w'}  # open modes


class _File:
    """
    A file I/O class.
    """
    def __init__(self, name=None, mode='copyonwrite', memmap=0, **parms):
        if name == None:
            self._simulateonly = True
            return
        else:
            self._simulateonly = False

        if mode not in PYTHON_MODES.keys():
            raise ValueError, "Mode '%s' not recognized" % mode


        if isinstance(name, file):
            self.name = name.name
        elif isinstance(name, types.StringType) or \
             isinstance(name, types.UnicodeType):
            if mode != 'append' and not os.path.exists(name) and \
            not os.path.splitdrive(name)[0]:
                #
                # Not writing file and file does not exist on local machine and
                # name does not begin with a drive letter (Windows), try to
                # get it over the web.
                #
                try:
                    self.name, fileheader = urllib.urlretrieve(name)
                except IOError, e:
                    raise e
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

        if parms.has_key('ignore_missing_end'):
            self.ignore_missing_end = parms['ignore_missing_end']
        else:
            self.ignore_missing_end = 0

        self.uint = parms.get('uint16', False) or parms.get('uint', False)

        if memmap and mode not in ['readonly', 'copyonwrite', 'update']:
            raise NotImplementedError(
                   "Memory mapping is not implemented for mode `%s`." % mode)
        else:
            if isinstance(name, file) or isinstance(name, gzip.GzipFile):
                if hasattr(name, 'closed'):
                    closed = name.closed
                    foMode = name.mode
                else:
                    if name.fileobj != None:
                        closed = name.fileobj.closed
                        foMode = name.fileobj.mode
                    else:
                        closed = True
                        foMode = PYTHON_MODES[mode]

                if not closed:
                    if PYTHON_MODES[mode] != foMode:
                        raise ValueError, "Input mode '%s' (%s) " \
                              % (mode, PYTHON_MODES[mode]) + \
                              "does not match mode of the input file (%s)." \
                              % name.mode
                    self.__file = name
                elif isinstance(name, file):
                    self.__file=open(self.name, PYTHON_MODES[mode])
                else:
                    self.__file=gzip.open(self.name, PYTHON_MODES[mode])
            elif isinstance(name, types.StringType) or \
                 isinstance(name, types.UnicodeType):
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
                    raise IOError("File-like object does not have a 'write' method, required for mode '%s'" % self.mode)

                if self.mode == 'readonly' and not hasattr(self.__file, 'read'):
                    raise IOError("File-like object does not have a 'read' method, required for mode 'readonly'" % self.mode)

            # For 'ab+' mode, the pointer is at the end after the open in
            # Linux, but is at the beginning in Solaris.

            if mode == 'ostream':
                # For output stream start with a truncated file.
                self._size = 0
            elif isinstance(self.__file,gzip.GzipFile):
                self.__file.fileobj.seek(0,2)
                self._size = self.__file.fileobj.tell()
                self.__file.fileobj.seek(0)
                self.__file.seek(0)
            elif hasattr(self.__file, 'seek'):
                self.__file.seek(0, 2)
                self._size = self.__file.tell()
                self.__file.seek(0)
            else:
                self._size = 0

    def __getattr__(self, attr):
        """
        Get the `_mm` attribute.
        """
        if attr == '_mm':
            return Memmap(self.name,offset=self.offset,mode=_memmap_mode[self.mode],dtype=self.code,shape=self.dims)
        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def getfile(self):
        return self.__file

    def _readheader(self, cardList, keyList, blocks):
        """Read blocks of header, and put each card into a list of cards.
           Will deal with CONTINUE cards in a later stage as CONTINUE cards
           may span across blocks.
        """

        from pyfits.core import Card, _blockLen

        if len(block) != _blockLen:
            raise IOError, 'Block length is not %d: %d' % (_blockLen, len(block))
        elif (blocks[:8] not in ['SIMPLE  ', 'XTENSION']):
            raise IOError, 'Block does not begin with SIMPLE or XTENSION'

        for i in range(0, len(_blockLen), Card.length):
            _card = Card('').fromstring(block[i:i+Card.length])
            _key = _card.key

            cardList.append(_card)
            keyList.append(_key)
            if _key == 'END':
                break

    def _readHDU(self):
        """
        Read the skeleton structure of the HDU.
        """

        from pyfits.core import _TempHDU, _padLength, _blockLen

        if not hasattr(self.__file, 'tell') or not hasattr(self.__file, 'read'):
            raise EOFError

        end_RE = re.compile('END'+' '*77)
        _hdrLoc = self.__file.tell()

        # Read the first header block.
        block = self.__file.read(_blockLen)
        if block == '':
            raise EOFError

        hdu = _TempHDU()
        hdu._raw = ''

        # continue reading header blocks until END card is reached
        while 1:

            # find the END card
            mo = end_RE.search(block)
            if mo is None:
                hdu._raw += block
                block = self.__file.read(_blockLen)
                if block == '':
                    break
            else:
                break
        hdu._raw += block

        if not end_RE.search(block) and not self.ignore_missing_end:
            raise IOError, "Header missing END card."

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
        hdu._datSpan = _size + _padLength(_size)
        hdu._new = 0
        hdu._ffile = self
        if isinstance(hdu._file, gzip.GzipFile):
            pos = self.__file.tell()
            self.__file.seek(pos+hdu._datSpan)
        else:
            self.__file.seek(hdu._datSpan, 1)

            if self.__file.tell() > self._size:
                warnings.warn('Warning: File may have been truncated: actual file length (%i) is smaller than the expected size (%i)'  % (self._size, self.__file.tell()))

        return hdu

    def writeHDU(self, hdu, checksum=False):
        """
        Write *one* FITS HDU.  Must seek to the correct location
        before calling this method.
        """

        from pyfits.core import _ImageBaseHDU, CompImageHDU

        if isinstance(hdu, _ImageBaseHDU):
            hdu.update_header()
        elif isinstance(hdu, CompImageHDU):
            hdu.updateCompressedData()
        return (self.writeHDUheader(hdu,checksum)[0],) + self.writeHDUdata(hdu)

    def writeHDUheader(self, hdu, checksum=False):
        """
        Write FITS HDU header part.
        """

        from pyfits.core import _NonstandardHDU, _NonstandardExtHDU, \
                                _unsigned_zero, _is_pseudo_unsigned, \
                                _padLength, _pad, _blockLen

        # If the data is unsigned int 16, 32, or 64 add BSCALE/BZERO
        # cards to header

        if 'data' in dir(hdu) and hdu.data is not None \
        and not isinstance(hdu, _NonstandardHDU) \
        and not isinstance(hdu, _NonstandardExtHDU) \
        and _is_pseudo_unsigned(hdu.data.dtype):
            hdu._header.update(
                'BSCALE', 1,
                after='NAXIS'+`hdu.header.get('NAXIS')`)
            hdu._header.update(
                'BZERO', _unsigned_zero(hdu.data.dtype),
                after='BSCALE')

        # Handle checksum
        if hdu._header.has_key('CHECKSUM'):
            del hdu.header['CHECKSUM']

        if hdu._header.has_key('DATASUM'):
            del hdu.header['DATASUM']

        if checksum == 'datasum':
            hdu.add_datasum()
        elif checksum == 'nonstandard_datasum':
            hdu.add_datasum(blocking="nonstandard")
        elif checksum == 'test':
            hdu.add_datasum(hdu._datasum_comment)
            hdu.add_checksum(hdu._checksum_comment,True)
        elif checksum == "nonstandard":
            hdu.add_checksum(blocking="nonstandard")
        elif checksum:
            hdu.add_checksum(blocking="standard")

        blocks = repr(hdu._header.ascard) + _pad('END')
        blocks = blocks + _padLength(len(blocks))*' '

        if len(blocks)%_blockLen != 0:
            raise IOError

        loc = 0
        size = len(blocks)

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
        if 'data' in dir(hdu) and hdu.data is not None \
        and not isinstance(hdu, _NonstandardHDU) \
        and not isinstance(hdu, _NonstandardExtHDU) \
        and _is_pseudo_unsigned(hdu.data.dtype):
            del hdu._header['BSCALE']
            del hdu._header['BZERO']

        return loc, size

    def writeHDUdata(self, hdu):
        """
        Write FITS HDU data part.
        """

        from pyfits.core import TableHDU, BinTableHDU, CompImageHDU, \
                                GroupData, _NonstandardHDU, \
                                _NonstandardExtHDU, _ImageBaseHDU, \
                                _is_pseudo_unsigned, _unsigned_zero, \
                                _padLength, _tofile, _FormatP, _VLF

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
                self.__file.write(_padLength(_size)*'\0')

                # flush, to make sure the content is written
                self.__file.flush()

            # return both the location and the size of the data area
            return loc, _size+_padLength(_size)
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
                        byteorder = \
                            output.dtype.fields[hdu.data.dtype.names[0]][0].str[0]
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

                swapped = []
                try:
                    if not self._simulateonly:
                        for i in range(output._nfields):
                            coldata = output.field(i)
                            if not isinstance(coldata, chararray.chararray):
                                # only swap unswapped
                                # deal with var length table
                                if isinstance(coldata, _VLF):
                                    k = 0
                                    for j in coldata:
                                        if (not isinstance(j, chararray.chararray) and
                                            j.itemsize > 1 and
                                            j.dtype.str[0] in swap_types):
                                            swapped.append(j)
                                        if (rec.recarray.field(output,i)[k:k+1].dtype.str[0] in
                                            swap_types):
                                            swapped.append(rec.recarray.field(output,i)[k:k+1])
                                        k = k + 1
                                else:
                                    if (coldata.itemsize > 1 and
                                        output.dtype.descr[i][1][0] in swap_types):
                                        swapped.append(rec.recarray.field(output, i))

                        for obj in swapped:
                            obj.byteswap(True)

                        _tofile(output, self.__file)

                        # write out the heap of variable length array
                        # columns this has to be done after the
                        # "regular" data is written (above)
                        self.__file.write(output._gap*'\0')

                    nbytes = output._gap

                    for i in range(output._nfields):
                        if isinstance(output._coldefs._recformats[i], _FormatP):
                            for j in range(len(output.field(i))):
                                coldata = output.field(i)[j]
                                if len(coldata) > 0:
                                    nbytes= nbytes + coldata.nbytes
                                    if not self._simulateonly:
                                        coldata.tofile(self.__file)

                    output._heapsize = nbytes - output._gap
                    _size = _size + nbytes
                finally:
                    for obj in swapped:
                        obj.byteswap(True)
            else:
                output = hdu.data

                if not self._simulateonly:
                    _tofile(output, self.__file)

            _size = _size + output.size * output.itemsize

            # pad the FITS data block
            if _size > 0 and not self._simulateonly:
                if isinstance(hdu, TableHDU):
                    self.__file.write(_padLength(_size)*' ')
                else:
                    self.__file.write(_padLength(_size)*'\0')

        # flush, to make sure the content is written
        if not self._simulateonly and hasattr(self.__file, 'flush'):
            self.__file.flush()

        # return both the location and the size of the data area
        return loc, _size+_padLength(_size)

    def close(self):
        """
        Close the 'physical' FITS file.
        """
        if hasattr(self.__file, 'close'):
            self.__file.close()

        if hasattr(self, 'tfile'):
            del self.tfile

    # Support the 'with' statement
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()



