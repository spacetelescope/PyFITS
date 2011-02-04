import gzip
import operator
import os
import signal
import threading
import types
import warnings

import numpy as np
from numpy import memmap as Memmap

import pyfits
from pyfits.card import Card
from pyfits.column import _FormatP
from pyfits.hdu.base import _AllHDU, _ValidHDU, _TempHDU, _NonstandardHDU
from pyfits.hdu.compressed import CompImageHDU
from pyfits.hdu.extension import _ExtensionHDU
from pyfits.hdu.groups import GroupsHDU
from pyfits.hdu.image import PrimaryHDU, ImageHDU, _ImageBaseHDU
from pyfits.hdu.table import _TableBaseHDU
from pyfits.util import _tmpName
from pyfits.verify import _Verify, _ErrList


def fitsopen(name, mode="copyonwrite", memmap=False, classExtensions={},
             **parms):
    """
    Factory function to open a FITS file and return an `HDUList` object.

    Parameters
    ----------
    name : file path, file object or file-like object
        File to be opened.

    mode : str
        Open mode, 'copyonwrite' (default), 'readonly', 'update',
        'append', or 'ostream'.

        If `name` is a file object that is already opened, `mode` must
        match the mode the file was opened with, copyonwrite (rb),
        readonly (rb), update (rb+), append (ab+), ostream (w)).

    memmap : bool
        Is memory mapping to be used?

    classExtensions : dict
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    parms : dict
        optional keyword arguments, possible values are:

        - **uint** : bool

            Interpret signed integer data where ``BZERO`` is the
            central value and ``BSCALE == 1`` as unsigned integer
            data.  For example, `int16` data with ``BZERO = 32768``
            and ``BSCALE = 1`` would be treated as `uint16` data.

            Note, for backward compatibility, the kwarg **uint16** may
            be used instead.  The kwarg was renamed when support was
            added for integers of any size.

        - **ignore_missing_end** : bool

            Do not issue an exception when opening a file that is
            missing an ``END`` card in the last header.

        - **checksum** : bool

            If `True`, verifies that both ``DATASUM`` and
            ``CHECKSUM`` card values (when present in the HDU header)
            match the header and data of all HDU's in the file.

        - **disable_image_compression** : bool

            If `True`, treates compressed image HDU's like normal
            binary table HDU's.

        - **do_not_scale_image_data** : bool

            If `True`, image data is not scaled using BSCALE/BZERO values
            when read.

    Returns
    -------
        hdulist : an HDUList object
            `HDUList` containing all of the header data units in the
            file.
    """
    # instantiate a FITS file object (ffo)

    import pyfits.core
    from pyfits.file import _File
    from pyfits.hdu import compressed

    if classExtensions.has_key(_File):
        ffo = classExtensions[_File](name, mode=mode, memmap=memmap, **parms)
    else:
        ffo = _File(name, mode=mode, memmap=memmap, **parms)

    if classExtensions.has_key(HDUList):
        hduList = classExtensions[HDUList](file=ffo)
    else:
        hduList = HDUList(file=ffo)

    savedCompressionSupported = compressed.COMPRESSION_SUPPORTED

    try:
        if 'disable_image_compression' in parms and \
           parms['disable_image_compression']:
            compressionSupported = -1

        if 'do_not_scale_image_data' in parms:
            do_not_scale_image_data = parms['do_not_scale_image_data']
        else:
            do_not_scale_image_data = False

        if mode != 'ostream':
            # read all HDU's
            while 1:
                try:
                    thdu = ffo._readHDU()
                    thdu._do_not_scale_image_data = do_not_scale_image_data
                    hduList.append(thdu, classExtensions=classExtensions)
                except EOFError:
                    break
                # check in the case there is extra space after the last HDU or
                # corrupted HDU
                except ValueError, e:
                    warnings.warn('Warning:  Required keywords missing when trying to read HDU #%d.\n          %s\n          There may be extra bytes after the last HDU or the file is corrupted.' % (len(hduList),e))
                    break
                except IOError, e:
                    if isinstance(ffo.getfile(), gzip.GzipFile) and \
                       string.find(str(e),'on write-only GzipFile object'):
                        break
                    else:
                        raise e

            # If we're trying to read only and no header units were found,
            # raise and exception
            if mode == 'readonly' and len(hduList) == 0:
                raise IOError("Empty FITS file")

            # For each HDU, verify the checksum/datasum value if the cards
            # exist in the header and we are opening with checksum=True.
            # Always remove the checksum/datasum cards from the header.

            # NOTE:  private data members _checksum and _datasum are
            # used by the utility script "fitscheck" to detect missing
            # checksums.
            for i in range(len(hduList)):
                hdu = hduList.__getitem__(i, classExtensions)

                if hdu._header.has_key('CHECKSUM'):
                     hdu._checksum = hdu._header['CHECKSUM']
                     hdu._checksum_comment = \
                                hdu._header.ascardlist()['CHECKSUM'].comment

                     if 'checksum' in parms and parms['checksum'] and \
                     not hdu.verify_checksum(parms['checksum']):
                         warnings.warn('Warning:  Checksum verification failed '
                                   'for HDU #%d.\n' % i)

                     del hdu.header['CHECKSUM']
                else:
                     hdu._checksum = None
                     hdu._checksum_comment = None

                if hdu._header.has_key('DATASUM'):
                     hdu._datasum = hdu.header['DATASUM']
                     hdu._datasum_comment = \
                                   hdu.header.ascardlist()['DATASUM'].comment

                     if 'checksum' in parms and parms['checksum'] and \
                     not hdu.verify_datasum(parms['checksum']):
                         warnings.warn('Warning:  Datasum verification failed '
                                       'for HDU #%d.\n' % (len(hduList)))

                     del hdu.header['DATASUM']
                else:
                     hdu._checksum = None
                     hdu._checksum_comment = None
                     hdu._datasum = None
                     hdu._datasum_comment = None

        # initialize/reset attributes to be used in "update/append" mode
        # CardList needs its own _mod attribute since it has methods to change
        # the content of header without being able to pass it to the header
        # object
        hduList._resize = 0
        hduList._truncate = 0

    finally:
        compressed.COMPRESSION_SUPPORTED = savedCompressionSupported

    return hduList


class HDUList(list, _Verify):
    """
    HDU list class.  This is the top-level FITS object.  When a FITS
    file is opened, a `HDUList` object is returned.
    """

    def __init__(self, hdus=[], file=None):
        """
        Construct a `HDUList` object.

        Parameters
        ----------
        hdus : sequence of HDU objects or single HDU, optional
            The HDU object(s) to comprise the `HDUList`.  Should be
            instances of `_AllHDU`.

        file : file object, optional
            The opened physical file associated with the `HDUList`.
        """
        self.__file = file
        if hdus is None:
            hdus = []

        # can take one HDU, as well as a list of HDU's as input
        if isinstance(hdus, _ValidHDU):
            hdus = [hdus]
        elif not isinstance(hdus, (HDUList, list)):
            raise TypeError, "Invalid input for HDUList."

        for hdu in hdus:
            if not isinstance(hdu, _AllHDU):
                raise TypeError(
                      "Element %d in the HDUList input is not an HDU."
                      % hdus.index(hdu))
        list.__init__(self, hdus)

    def __iter__(self):
        return [self[i] for i in range(len(self))].__iter__()

    def __getitem__(self, key, classExtensions={}):
        """
        Get an HDU from the `HDUList`, indexed by number or name.
        """
        key = self.index_of(key)
        _item = super(HDUList, self).__getitem__(key)
        if isinstance(_item, _TempHDU):
            super(HDUList, self).__setitem__(key,
                                             _item.setupHDU(classExtensions))

        return super(HDUList, self).__getitem__(key)

    def __getslice__(self, start, end):
        _hdus = super(HDUList, self).__getslice__(start,end)
        result = HDUList(_hdus)
        return result

    def __setitem__(self, key, hdu):
        """
        Set an HDU to the `HDUList`, indexed by number or name.
        """
        _key = self.index_of(key)
        if isinstance(hdu, (slice, list)):
            if isinstance(_key, (int,np.integer)):
                raise ValueError, "An element in the HDUList must be an HDU."
            for item in hdu:
                if not isinstance(item, _AllHDU):
                    raise ValueError, "%s is not an HDU." % item
        else:
            if not isinstance(hdu, _AllHDU):
                raise ValueError, "%s is not an HDU." % hdu

        try:
            super(HDUList, self).__setitem__(_key, hdu)
        except IndexError:
            raise IndexError, 'Extension %s is out of bound or not found.' % key
        self._resize = 1
        self._truncate = 0

    def __delitem__(self, key):
        """
        Delete an HDU from the `HDUList`, indexed by number or name.
        """
        key = self.index_of(key)

        endIndex = len(self)-1
        super(HDUList, self).__delitem__(key)

        if ( key == endIndex or key == -1 and not self._resize):
            self._truncate = 1
        else:
            self._truncate = 0
            self._resize = 1

    def __delslice__(self, i, j):
        """
        Delete a slice of HDUs from the `HDUList`, indexed by number only.
        """
        endIndex = len(self)
        super(HDUList, self).__delslice__(i, j)

        if ( j == endIndex or j == sys.maxint and not self._resize):
            self._truncate = 1
        else:
            self._truncate = 0
            self._resize = 1


    def _verify (self, option='warn'):
        _text = ''
        _err = _ErrList([], unit='HDU')

        # the first (0th) element must be a primary HDU
        if len(self) > 0 and (not isinstance(self[0], PrimaryHDU)) and \
                             (not isinstance(self[0], _NonstandardHDU)):
            err_text = "HDUList's 0th element is not a primary HDU."
            fix_text = 'Fixed by inserting one as 0th HDU.'
            fix = "from pyfits.hdu.image import PrimaryHDU; self.insert(0, PrimaryHDU())"
            _text = self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix)
            _err.append(_text)

        # each element calls their own verify
        for i in range(len(self)):
            if i > 0 and (not isinstance(self[i], _ExtensionHDU)):
                err_text = "HDUList's element %s is not an extension HDU." % `i`
                _text = self.run_option(option, err_text=err_text, fixable=0)
                _err.append(_text)

            else:
                _result = self[i]._verify(option)
                if _result:
                    _err.append(_result)
        return _err

    def _wasresized(self, verbose=False):
        """
        Determine if any changes to the HDUList will require a file resize
        when flushing the file.

        Side effect of setting the objects _resize attribute.
        """

        from pyfits.file import _pad_length

        if not self._resize:

            # determine if any of the HDU is resized
            for hdu in self:

                # Header:
                # Add 1 to .ascard to include the END card
                _nch80 = reduce(operator.add, map(Card._ncards,
                                                  hdu.header.ascard))
                _bytes = (_nch80+1) * Card.length
                _bytes = _bytes + _pad_length(_bytes)
                if _bytes != (hdu._datLoc-hdu._hdrLoc):
                    self._resize = 1
                    self._truncate = 0
                    if verbose:
                        print "One or more header is resized."
                    break

                # Data:
                if 'data' not in dir(hdu):
                    continue
                if hdu.data is None:
                    continue
                _bytes = hdu.data.nbytes
                _bytes = _bytes + _pad_length(_bytes)
                if _bytes != hdu._datSpan:
                    self._resize = 1
                    self._truncate = 0
                    if verbose:
                        print "One or more data area is resized."
                    break

            if self._truncate:
               try:
                   self.__file.getfile().truncate(hdu._datLoc+hdu._datSpan)
               except IOError:
                   self._resize = 1
               self._truncate = 0

        return self._resize

    def fileinfo(self, index):
        """
        Returns a dictionary detailing information about the locations
        of the indexed HDU within any associated file.  The values are
        only valid after a read or write of the associated file with
        no intervening changes to the `HDUList`.

        Parameters
        ----------
        index : int
            Index of HDU for which info is to be returned.

        Returns
        -------
        dictionary or None

            The dictionary details information about the locations of
            the indexed HDU within an associated file.  Returns `None`
            when the HDU is not associated with a file.

            Dictionary contents:

            ========== =========================================================
            Key        Value
            ========== =========================================================
            file       File object associated with the HDU
            filename   Name of associated file object
            filemode   Mode in which the file was opened (readonly, copyonwrite,
                       update, append, ostream)
            resized    Flag that when `True` indicates that the data has been
                       resized since the last read/write so the returned values
                       may not be valid.
            hdrLoc     Starting byte location of header in file
            datLoc     Starting byte location of data block in file
            datSpan    Data size including padding
            ========== =========================================================

        """

        if self.__file is not None:
            output = self[index].fileinfo()

            if not output:
                # OK, the HDU associated with this index is not yet
                # tied to the file associated with the HDUList.  The only way
                # to get the file object is to check each of the HDU's in the
                # list until we find the one associated with the file.
                f = None

                for hdu in self:
                   info = hdu.fileinfo()

                   if info:
                      f = info['file']
                      fm = info['filemode']
                      break

                output = {'file':f, 'filemode':fm, 'hdrLoc':None,
                          'datLoc':None, 'datSpan':None}

            output['filename'] = self.__file.name
            output['resized'] = self._wasresized()
        else:
            output = None

        return output

    def insert(self, index, hdu, classExtensions={}):
        """
        Insert an HDU into the `HDUList` at the given `index`.

        Parameters
        ----------
        index : int
            Index before which to insert the new HDU.

        hdu : _AllHDU instance
            The HDU object to insert

        classExtensions : dict
            A dictionary that maps pyfits classes to extensions of those
            classes.  When present in the dictionary, the extension class
            will be constructed in place of the pyfits class.
        """
        if isinstance(hdu, _AllHDU):
            num_hdus = len(self)

            if index == 0 or num_hdus == 0:
                if num_hdus != 0:
                    # We are inserting a new Primary HDU so we need to
                    # make the current Primary HDU into an extension HDU.
                    if isinstance(self[0], GroupsHDU):
                       raise ValueError, \
                             "The current Primary HDU is a GroupsHDU.  " + \
                             "It can't be made into an extension HDU," + \
                             " so you can't insert another HDU in front of it."

                    if classExtensions.has_key(ImageHDU):
                        hdu1 = classExtensions[ImageHDU](self[0].data,
                                                         self[0].header)
                    else:
                        hdu1= ImageHDU(self[0].data, self[0].header)

                    # Insert it into position 1, then delete HDU at position 0.
                    super(HDUList, self).insert(1,hdu1)
                    super(HDUList, self).__delitem__(0)

                if not isinstance(hdu, PrimaryHDU):
                    # You passed in an Extension HDU but we need a Primary HDU.
                    # If you provided an ImageHDU then we can convert it to
                    # a primary HDU and use that.
                    if isinstance(hdu, ImageHDU):
                        if classExtensions.has_key(PrimaryHDU):
                            hdu = classExtensions[PrimaryHDU](hdu.data,
                                                              hdu.header)
                        else:
                            hdu = PrimaryHDU(hdu.data, hdu.header)
                    else:
                        # You didn't provide an ImageHDU so we create a
                        # simple Primary HDU and append that first before
                        # we append the new Extension HDU.
                        if classExtensions.has_key(PrimaryHDU):
                            phdu = classExtensions[PrimaryHDU]()
                        else:
                            phdu = PrimaryHDU()

                        super(HDUList, self).insert(0,phdu)
                        index = 1
            else:
                if isinstance(hdu, GroupsHDU):
                   raise ValueError, \
                         "A GroupsHDU must be inserted as a Primary HDU"

                if isinstance(hdu, PrimaryHDU):
                    # You passed a Primary HDU but we need an Extension HDU
                    # so create an Extension HDU from the input Primary HDU.
                    if classExtensions.has_key(ImageHDU):
                        hdu = classExtensions[ImageHDU](hdu.data,hdu.header)
                    else:
                        hdu = ImageHDU(hdu.data, hdu.header)

            super(HDUList, self).insert(index,hdu)
            self._resize = 1
            self._truncate = 0
        else:
            raise ValueError, "%s is not an HDU." % hdu

        # make sure the EXTEND keyword is in primary HDU if there is extension
        if len(self) > 1:
            self.update_extend()

    def append(self, hdu, classExtensions={}):
        """
        Append a new HDU to the `HDUList`.

        Parameters
        ----------
        hdu : instance of _AllHDU
            HDU to add to the `HDUList`.

        classExtensions : dict
            A dictionary that maps pyfits classes to extensions of those
            classes.  When present in the dictionary, the extension class
            will be constructed in place of the pyfits class.
        """
        if isinstance(hdu, _AllHDU):
            if not isinstance(hdu, _TempHDU):
                if len(self) > 0:
                    if isinstance(hdu, GroupsHDU):
                       raise ValueError, \
                             "Can't append a GroupsHDU to a non-empty HDUList"

                    if isinstance(hdu, PrimaryHDU):
                        # You passed a Primary HDU but we need an Extension HDU
                        # so create an Extension HDU from the input Primary HDU.
                        if classExtensions.has_key(ImageHDU):
                            hdu = classExtensions[ImageHDU](hdu.data,hdu.header)
                        else:
                            hdu = ImageHDU(hdu.data, hdu.header)
                else:
                    if not isinstance(hdu, PrimaryHDU):
                        # You passed in an Extension HDU but we need a Primary
                        # HDU.
                        # If you provided an ImageHDU then we can convert it to
                        # a primary HDU and use that.
                        if isinstance(hdu, ImageHDU):
                            if classExtensions.has_key(PrimaryHDU):
                                hdu = classExtensions[PrimaryHDU](hdu.data,
                                                                  hdu.header)
                            else:
                                hdu = PrimaryHDU(hdu.data, hdu.header)
                        else:
                            # You didn't provide an ImageHDU so we create a
                            # simple Primary HDU and append that first before
                            # we append the new Extension HDU.
                            if classExtensions.has_key(PrimaryHDU):
                                phdu = classExtensions[PrimaryHDU]()
                            else:
                                phdu = PrimaryHDU()

                            super(HDUList, self).append(phdu)

            super(HDUList, self).append(hdu)
            hdu._new = 1
            self._resize = 1
            self._truncate = 0
        else:
            raise ValueError, "HDUList can only append an HDU"

        # make sure the EXTEND keyword is in primary HDU if there is extension
        if len(self) > 1:
            self.update_extend()

    def index_of(self, key):
        """
        Get the index of an HDU from the `HDUList`.

        Parameters
        ----------
        key : int, str or tuple of (string, int)
           The key identifying the HDU.  If `key` is a tuple, it is of
           the form (`key`, `ver`) where `ver` is an ``EXTVER`` value
           that must match the HDU being searched for.

        Returns
        -------
        index : int
           The index of the HDU in the `HDUList`.
        """

        if isinstance(key, (int, np.integer,slice)):
            return key
        elif isinstance(key, tuple):
            _key = key[0]
            _ver = key[1]
        else:
            _key = key
            _ver = None

        if not isinstance(_key, str):
            raise KeyError, key
        _key = (_key.strip()).upper()

        nfound = 0
        for j in range(len(self)):
            _name = self[j].name
            if isinstance(_name, str):
                _name = _name.strip().upper()
            if _name == _key:

                # if only specify extname, can only have one extension with
                # that name
                if _ver == None:
                    found = j
                    nfound += 1
                else:

                    # if the keyword EXTVER does not exist, default it to 1
                    _extver = self[j]._extver
                    if _ver == _extver:
                        found = j
                        nfound += 1

        if (nfound == 0):
            raise KeyError, 'extension %s not found' % `key`
        elif (nfound > 1):
            raise KeyError, 'there are %d extensions of %s' % (nfound, `key`)
        else:
            return found

    def readall(self):
        """
        Read data of all HDUs into memory.
        """
        for i in range(len(self)):
            if self[i].data is not None:
                continue

    def update_tbhdu(self):
        """
        Update all table HDU's for scaled fields.
        """

        for hdu in self:
            if 'data' in dir(hdu) and not isinstance(hdu, CompImageHDU):
                if isinstance(hdu, (GroupsHDU, _TableBaseHDU)) and hdu.data is not None:
                    hdu.data._scale_back()
                if isinstance(hdu, _TableBaseHDU) and hdu.data is not None:

                    # check TFIELDS and NAXIS2
                    hdu.header['TFIELDS'] = hdu.data._nfields
                    hdu.header['NAXIS2'] = hdu.data.shape[0]

                    # calculate PCOUNT, for variable length tables
                    _tbsize = hdu.header['NAXIS1']*hdu.header['NAXIS2']
                    _heapstart = hdu.header.get('THEAP', _tbsize)
                    hdu.data._gap = _heapstart - _tbsize
                    _pcount = hdu.data._heapsize + hdu.data._gap
                    if _pcount > 0:
                        hdu.header['PCOUNT'] = _pcount

                    # update TFORM for variable length columns
                    for i in range(hdu.data._nfields):
                        if isinstance(hdu.data._coldefs.formats[i], _FormatP):
                            key = hdu.header['TFORM'+`i+1`]
                            hdu.header['TFORM'+`i+1`] = key[:key.find('(')+1] + `hdu.data.field(i)._max` + ')'


    def flush(self, output_verify='exception', verbose=False, classExtensions={}):
        """
        Force a write of the `HDUList` back to the file (for append and
        update modes only).

        Parameters
        ----------
        output_verify : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.

        verbose : bool
            When `True`, print verbose messages

        classExtensions : dict
            A dictionary that maps pyfits classes to extensions of
            those classes.  When present in the dictionary, the
            extension class will be constructed in place of the pyfits
            class.
        """

        from pyfits.file import _File

        # Get the name of the current thread and determine if this is a single treaded application
        threadName = threading.currentThread()
        singleThread = (threading.activeCount() == 1) and (threadName.getName() == 'MainThread')

        # Define new signal interput handler
        if singleThread:
            keyboardInterruptSent = False
            def New_SIGINT(*args):
                warnings.warn("KeyboardInterrupt ignored until flush is complete!")
                keyboardInterruptSent = True

            # Install new handler
            old_handler = signal.signal(signal.SIGINT,New_SIGINT)

        if self.__file.mode not in ('append', 'update', 'ostream'):
            warnings.warn("flush for '%s' mode is not supported." % self.__file.mode)
            return

        self.update_tbhdu()
        self.verify(option=output_verify)

        if self.__file.mode in ('append', 'ostream'):
            for hdu in self:
                if (verbose):
                    try: _extver = `hdu.header['extver']`
                    except: _extver = ''

                # only append HDU's which are "new"
                if not hasattr(hdu, '_new') or hdu._new:
                    # only output the checksum if flagged to do so
                    if hasattr(hdu, '_output_checksum'):
                        checksum = hdu._output_checksum
                    else:
                        checksum = False

                    self.__file.writeHDU(hdu, checksum=checksum)
                    if (verbose):
                        print "append HDU", hdu.name, _extver
                    hdu._new = 0

        elif self.__file.mode == 'update':
            self._wasresized(verbose)

            # if the HDUList is resized, need to write out the entire contents
            # of the hdulist to the file.
            if self._resize or isinstance(self.__file.getfile(), gzip.GzipFile):
                oldName = self.__file.name
                oldMemmap = self.__file.memmap
                _name = _tmpName(oldName)

                if isinstance(self.__file.getfile(), file) or \
                   isinstance(self.__file.getfile(), gzip.GzipFile):
                    #
                    # The underlying file is an acutal file object.
                    # The HDUList is resized, so we need to write it to a tmp
                    # file, delete the original file, and rename the tmp
                    # file to the original file.
                    #
                    if isinstance(self.__file.getfile(), gzip.GzipFile):
                        newFile = gzip.GzipFile(_name, mode='ab+')
                    else:
                        newFile = _name

                    _hduList = fitsopen(newFile, mode="append",
                                        classExtensions=classExtensions)
                    if (verbose): print "open a temp file", _name

                    for hdu in self:
                        # only output the checksum if flagged to do so
                        if hasattr(hdu, '_output_checksum'):
                            checksum = hdu._output_checksum
                        else:
                            checksum = False

                        (hdu._hdrLoc, hdu._datLoc, hdu._datSpan) = \
                               _hduList.__file.writeHDU(hdu, checksum=checksum)
                    _hduList.__file.close()
                    self.__file.close()
                    os.remove(self.__file.name)
                    if (verbose): print "delete the original file", oldName

                    # reopen the renamed new file with "update" mode
                    os.rename(_name, oldName)

                    if isinstance(newFile, gzip.GzipFile):
                        oldFile = gzip.GzipFile(oldName, mode='rb+')
                    else:
                        oldFile = oldName

                    if classExtensions.has_key(_File):
                        ffo = classExtensions[_File](oldFile, mode="update",
                                                       memmap=oldMemmap)
                    else:
                        ffo = _File(oldFile, mode="update", memmap=oldMemmap)

                    self.__file = ffo
                    if (verbose): print "reopen the newly renamed file", oldName
                else:
                    #
                    # The underlying file is not a file object, it is a file
                    # like object.  We can't write out to a file, we must
                    # update the file like object in place.  To do this,
                    # we write out to a temporary file, then delete the
                    # contents in our file like object, then write the
                    # contents of the temporary file to the now empty file
                    # like object.
                    #
                    self.writeto(_name)
                    _hduList = fitsopen(_name)
                    ffo = self.__file

                    try:
                        ffo.getfile().truncate(0)
                    except AttributeError:
                        pass

                    for hdu in _hduList:
                        # only output the checksum if flagged to do so
                        if hasattr(hdu, '_output_checksum'):
                            checksum = hdu._output_checksum
                        else:
                            checksum = False

                        (hdu._hdrLoc, hdu._datLoc, hdu._datSpan) = \
                                            ffo.writeHDU(hdu, checksum=checksum)

                    # Close the temporary file and delete it.

                    _hduList.close()
                    os.remove(_hduList.__file.name)

                # reset the resize attributes after updating
                self._resize = 0
                self._truncate = 0
                for hdu in self:
                    hdu.header._mod = 0
                    hdu.header.ascard._mod = 0
                    hdu._new = 0
                    hdu._file = ffo.getfile()

            # if not resized, update in place
            else:
                for hdu in self:
                    if (verbose):
                        try: _extver = `hdu.header['extver']`
                        except: _extver = ''

                    if 'data' in dir(hdu) and isinstance(hdu, _ImageBaseHDU):
                        # If the data has changed update the image header to
                        # match the data
                        hdu.update_header()

                    if hdu.header._mod or hdu.header.ascard._mod:
                        # only output the checksum if flagged to do so
                        if hasattr(hdu, '_output_checksum'):
                            checksum = hdu._output_checksum
                        else:
                            checksum = False

                        hdu._file.seek(hdu._hdrLoc)
                        self.__file.writeHDUheader(hdu,checksum=checksum)
                        if (verbose):
                            print "update header in place: Name =", hdu.name, _extver
                    if 'data' in dir(hdu):
                        if hdu.data is not None:
                            if isinstance(hdu.data,Memmap):
                                hdu.data.sync()
                            else:
                                hdu._file.seek(hdu._datLoc)
                                self.__file.writeHDUdata(hdu)
                            if (verbose):
                                print "update data in place: Name =", hdu.name, _extver

                # reset the modification attributes after updating
                for hdu in self:
                    hdu.header._mod = 0
                    hdu.header.ascard._mod = 0
        if singleThread:
            if keyboardInterruptSent:
                raise KeyboardInterrupt

            if old_handler != None:
                signal.signal(signal.SIGINT,old_handler)
            else:
                signal.signal(signal.SIGINT, signal.SIG_DFL)

    def update_extend(self):
        """
        Make sure that if the primary header needs the keyword
        ``EXTEND`` that it has it and it is correct.
        """
        hdr = self[0].header
        if hdr.has_key('extend'):
            if (hdr['extend'] == False):
                hdr['extend'] = True
        else:
            if hdr['naxis'] == 0:
                hdr.update('extend', True, after='naxis')
            else:
                n = hdr['naxis']
                hdr.update('extend', True, after='naxis'+`n`)

    def writeto(self, name, output_verify='exception', clobber=False,
                classExtensions={}, checksum=False):
        """
        Write the `HDUList` to a new file.

        Parameters
        ----------
        name : file path, file object or file-like object
            File to write to.  If a file object, must be opened for
            append (ab+).

        output_verify : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.

        clobber : bool
            When `True`, overwrite the output file if exists.

        classExtensions : dict
            A dictionary that maps pyfits classes to extensions of
            those classes.  When present in the dictionary, the
            extension class will be constructed in place of the pyfits
            class.

        checksum : bool
            When `True` adds both ``DATASUM`` and ``CHECKSUM`` cards
            to the headers of all HDU's written to the file.
        """

        from pyfits.file import PYTHON_MODES

        if (len(self) == 0):
            warnings.warn("There is nothing to write.")
            return

        self.update_tbhdu()


        if output_verify == 'warn':
            output_verify = 'exception'
        self.verify(option=output_verify)

        # check if the file object is closed
        closed = True
        fileMode = 'ab+'

        if isinstance(name, file):
            closed = name.closed
            filename = name.name

            if not closed:
                fileMode = name.mode

        elif isinstance(name, gzip.GzipFile):
            if name.fileobj != None:
                closed = name.fileobj.closed
            filename = name.filename

            if not closed:
                fileMode = name.fileobj.mode

        elif isinstance(name, types.StringType) or \
             isinstance(name, types.UnicodeType):
            filename = name
        else:
            if hasattr(name, 'closed'):
                closed = name.closed

            if hasattr(name, 'mode'):
                fileMode = name.mode

            if hasattr(name, 'name'):
                filename = name.name
            elif hasattr(name, 'filename'):
                filename = name.filename
            elif hasattr(name, '__class__'):
                filename = str(name.__class__)
            else:
                filename = str(type(name))

        # check if the output file already exists
        if (isinstance(name,types.StringType) or
            isinstance(name,types.UnicodeType) or isinstance(name,file) or
            isinstance(name,gzip.GzipFile)):
            if (os.path.exists(filename) and os.path.getsize(filename) != 0):
                if clobber:
                    warnings.warn( "Overwrite existing file '%s'." % filename)
                    if (isinstance(name,file) and not name.closed) or \
                       (isinstance(name,gzip.GzipFile) and name.fileobj != None
                        and not name.fileobj.closed):
                       name.close()
                    os.remove(filename)
                else:
                    raise IOError, "File '%s' already exist." % filename
        elif (hasattr(name,'len') and name.len > 0):
            if clobber:
                warnings.warn( "Overwrite existing file '%s'." % filename)
                name.truncate(0)
            else:
                raise IOError, "File '%s' already exist." % filename

        # make sure the EXTEND keyword is there if there is extension
        if len(self) > 1:
            self.update_extend()

        for key in PYTHON_MODES.keys():
            if PYTHON_MODES[key] == fileMode:
                mode = key
                break

        hduList = fitsopen(name, mode=mode, classExtensions=classExtensions)

        for hdu in self:
            hduList.__file.writeHDU(hdu, checksum)
        hduList.close(output_verify=output_verify,closed=closed)


    def close(self, output_verify='exception', verbose=False, closed=True):
        """
        Close the associated FITS file and memmap object, if any.

        Parameters
        ----------
        output_verify : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.

        verbose : bool
            When `True`, print out verbose messages.

        closed : bool
            When `True`, close the underlying file object.
        """

        if self.__file != None:
            if self.__file.mode in ['append', 'update']:
                self.flush(output_verify=output_verify, verbose=verbose)

            if closed and hasattr(self.__file, 'close'):
                self.__file.close()

        # close the memmap object, it is designed to use an independent
        # attribute of mmobject so if the HDUList object is created from files
        # other than FITS, the close() call can also close the mm object.
#        try:
#            self.mmobject.close()
#        except:
#            pass

    def info(self):
        """
        Summarize the info of the HDUs in this `HDUList`.

        Note that this function prints its results to the console---it
        does not return a value.
        """
        if self.__file is None:
            _name = '(No file associated with this HDUList)'
        else:
            _name = self.__file.name
        results = "Filename: %s\nNo.    Name         Type"\
                  "      Cards   Dimensions   Format\n" % _name

        for j in range(len(self)):
            results = results + "%-3d  %s\n"%(j, self[j]._summary())
        results = results[:-1]
        print results

    def filename(self):
        """
        Return the file name associated with the HDUList object if one exists.
        Otherwise returns None.

        Returns
        -------
        filename : a string containing the file name associated with the
                   HDUList object if an association exists.  Otherwise returns
                   None.
        """
        if self.__file is not None:
           if hasattr(self.__file, 'name'):
              return self.__file.name
        return None

    # Support the 'with' statement
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

