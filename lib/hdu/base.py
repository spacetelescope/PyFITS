import datetime
import operator
import re

import numpy as np

from pyfits.card import Card, CardList, _Card_with_continue, \
                        createCardFromString
from pyfits.verify import _Verify


_isInt = "isinstance(val, (int, long, np.integer))"


class _AllHDU(object):
    """
    Base class for all HDU (header data unit) classes.
    """
    def __init__(self, data=None, header=None):
        from pyfits.core import DELAYED

        self._header = header

        if (data is DELAYED):
            return
        else:
            self.data = data

    def __getattr__(self, attr):
        if attr == 'header':
            return self.__dict__['_header']

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def __setattr__(self, attr, value):
        """
        Set an HDU attribute.
        """
        if attr == 'header':
            self._header = value
        else:
            object.__setattr__(self,attr,value)


class _CorruptedHDU(_AllHDU):
    """
    A Corrupted HDU class.

    This class is used when one or more mandatory `Card`s are
    corrupted (unparsable), such as the ``BITPIX``, ``NAXIS``, or
    ``END`` cards.  A corrupted HDU usually means that the data size
    cannot be calculated or the ``END`` card is not found.  In the case
    of a missing ``END`` card, the `Header` may also contain the binary
    data

    .. note::
       In future, it may be possible to decipher where the last block
       of the `Header` ends, but this task may be difficult when the
       extension is a `TableHDU` containing ASCII data.
    """
    def __init__(self, data=None, header=None):
        super(_CorruptedHDU, self).__init__(data, header)
        self._file, self._offset, self._datLoc = None, None, None
        self.name = None

    def size(self):
        """
        Returns the size (in bytes) of the HDU's data part.
        """
        self._file.seek(0, 2)
        return self._file.tell() - self._datLoc

    def _summary(self):
        return "%-10s  %-11s" % (self.name, "CorruptedHDU")

    def verify(self):
        pass


class _NonstandardHDU(_AllHDU, _Verify):
    """
    A Non-standard HDU class.

    This class is used for a Primary HDU when the ``SIMPLE`` Card has
    a value of `False`.  A non-standard HDU comes from a file that
    resembles a FITS file but departs from the standards in some
    significant way.  One example would be files where the numbers are
    in the DEC VAX internal storage format rather than the standard
    FITS most significant byte first.  The header for this HDU should
    be valid.  The data for this HDU is read from the file as a byte
    stream that begins at the first byte after the header ``END`` card
    and continues until the end of the file.
    """
    def __init__(self, data=None, header=None):
        super(_NonstandardHDU, self).__init__(data, header)
        self._file, self._offset, self._datLoc = None, None, None
        self.name = None

    def size(self):
        """
        Returns the size (in bytes) of the HDU's data part.
        """
        self._file.seek(0, 2)
        return self._file.tell() - self._datLoc

    def _summary(self):
        return "%-7s  %-11s  %5d" % (self.name, "NonstandardHDU",
                                     len(self._header.ascard))

    def __getattr__(self, attr):
        """
        Get the data attribute.
        """
        if attr == 'data':
            self.__dict__[attr] = None
            self._file.seek(self._datLoc)
            self.data = self._file.read()
        else:
            return _AllHDU.__getattr__(self, attr)

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def _verify(self, option='warn'):
        from pyfits.core import _ErrList

        _err = _ErrList([], unit='Card')

        # verify each card
        for _card in self._header.ascard:
            _err.append(_card._verify(option))

        return _err

    def writeto(self, name, output_verify='exception', clobber=False,
                classExtensions={}, checksum=False):
        """
        Write the HDU to a new file.  This is a convenience method to
        provide a user easier output interface if only one HDU needs
        to be written to a file.

        Parameters
        ----------
        name : file path, file object or file-like object
            Output FITS file.  If opened, must be opened for append
            ("ab+")).

        output_verify : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.

        clobber : bool
            Overwrite the output file if exists.

        classExtensions : dict
            A dictionary that maps pyfits classes to extensions of
            those classes.  When present in the dictionary, the
            extension class will be constructed in place of the pyfits
            class.

        checksum : bool
            When `True` adds both ``DATASUM`` and ``CHECKSUM`` cards
            to the header of the HDU when written to the file.
        """

        from pyfits.hdu.hdulist import HDUList

        if classExtensions.has_key(HDUList):
            hdulist = classExtensions[HDUList]([self])
        else:
            hdulist = HDUList([self])

        hdulist.writeto(name, output_verify, clobber=clobber,
                        checksum=checksum, classExtensions=classExtensions)


class _ValidHDU(_AllHDU, _Verify):
    """
    Base class for all HDUs which are not corrupted.
    """

    # 0.6.5.5
    def size(self):
        """
        Size (in bytes) of the data portion of the HDU.
        """
        size = 0
        naxis = self._header.get('NAXIS', 0)
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size = size * self._header['NAXIS'+`j+1`]
            bitpix = self._header['BITPIX']
            gcount = self._header.get('GCOUNT', 1)
            pcount = self._header.get('PCOUNT', 0)
            size = abs(bitpix) * gcount * (pcount + size) // 8
        return size

    def filebytes(self):
        """
        Calculates and returns the number of bytes that this HDU will write to
        a file.

        Parameters
        ----------
        None

        Returns
        -------
        Number of bytes
        """

        from pyfits.file import _File

        file = _File()
        return file.writeHDUheader(self)[1] + file.writeHDUdata(self)[1]

    def fileinfo(self):
        """
        Returns a dictionary detailing information about the locations
        of this HDU within any associated file.  The values are only
        valid after a read or write of the associated file with no
        intervening changes to the `HDUList`.

        Parameters
        ----------
        None

        Returns
        -------
        dictionary or None

           The dictionary details information about the locations of
           this HDU within an associated file.  Returns `None` when
           the HDU is not associated with a file.

           Dictionary contents:

           ========== ================================================
           Key        Value
           ========== ================================================
           file       File object associated with the HDU
           filemode   Mode in which the file was opened (readonly, copyonwrite,
                      update, append, ostream)
           hdrLoc     Starting byte location of header in file
           datLoc     Starting byte location of data block in file
           datSpan    Data size including padding
           ========== ================================================
        """

        if hasattr(self,'_file') and self._file:
           return {'file':self._file, 'filemode':self._ffile.mode,
                   'hdrLoc':self._hdrLoc,
                   'datLoc':self._datLoc, 'datSpan':self._datSpan}
        else:
            return None

    def copy(self):
        """
        Make a copy of the HDU, both header and data are copied.
        """
        if self.data is not None:
            _data = self.data.copy()
        else:
            _data = None
        return self.__class__(data=_data, header=self._header.copy())

    def writeto(self, name, output_verify='exception', clobber=False,
                classExtensions={}, checksum=False):
        """
        Write the HDU to a new file.  This is a convenience method to
        provide a user easier output interface if only one HDU needs
        to be written to a file.

        Parameters
        ----------
        name : file path, file object or file-like object
            Output FITS file.  If opened, must be opened for append
            ("ab+")).

        output_verify : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.

        clobber : bool
            Overwrite the output file if exists, default = False.

        classExtensions : dict
           A dictionary that maps pyfits classes to extensions of
           those classes.  When present in the dictionary, the
           extension class will be constructed in place of the pyfits
           class.

        checksum : bool
            When `True`, adds both ``DATASUM`` and ``CHECKSUM`` cards
            to the header of the HDU when written to the file.
        """

        from pyfits.hdu.extension import _ExtensionHDU
        from pyfits.hdu.hdulist import HDUList
        from pyfits.hdu.image import PrimaryHDU

        if isinstance(self, _ExtensionHDU):
            if classExtensions.has_key(HDUList):
                hdulist = classExtensions[HDUList]([PrimaryHDU(),self])
            else:
                hdulist = HDUList([PrimaryHDU(), self])
        elif isinstance(self, PrimaryHDU):
            if classExtensions.has_key(HDUList):
                hdulist = classExtensions[HDUList]([self])
            else:
                hdulist = HDUList([self])
        hdulist.writeto(name, output_verify, clobber=clobber,
                        checksum=checksum, classExtensions=classExtensions)

    def update_ext_name(self, value, comment=None, before=None,
                        after=None, savecomment=False):
        """
        Update the extension name associated with the HDU.

        If the keyword already exists in the Header, it's value and/or comment
        will be updated.  If it does not exist, a new card will be created
        and it will be placed before or after the specified location.
        If no `before` or `after` is specified, it will be appended at
        the end.

        Parameters
        ----------
        value : str
            value to be used for the new extension name

        comment : str, optional
            to be used for updating, default=None.

        before : str or int, optional
            name of the keyword, or index of the `Card` before which
            the new card will be placed in the Header.  The argument
            `before` takes precedence over `after` if both specified.

        after : str or int, optional
            name of the keyword, or index of the `Card` after which
            the new card will be placed in the Header.

        savecomment : bool, optional
            When `True`, preserve the current comment for an existing
            keyword.  The argument `savecomment` takes precedence over
            `comment` if both specified.  If `comment` is not
            specified then the current comment will automatically be
            preserved.
        """
        self._header.update('extname', value, comment, before, after,
                            savecomment)
        self.name = value


    def update_ext_version(self, value, comment=None, before=None,
                           after=None, savecomment=False):
        """
        Update the extension version associated with the HDU.

        If the keyword already exists in the Header, it's value and/or comment
        will be updated.  If it does not exist, a new card will be created
        and it will be placed before or after the specified location.
        If no `before` or `after` is specified, it will be appended at
        the end.

        Parameters
        ----------
        value : str
            value to be used for the new extension version

        comment : str, optional
            to be used for updating, default=None.

        before : str or int, optional
            name of the keyword, or index of the `Card` before which
            the new card will be placed in the Header.  The argument
            `before` takes precedence over `after` if both specified.

        after : str or int, optional
            name of the keyword, or index of the `Card` after which
            the new card will be placed in the Header.

        savecomment : bool, optional
            When `True`, preserve the current comment for an existing
            keyword.  The argument `savecomment` takes precedence over
            `comment` if both specified.  If `comment` is not
            specified then the current comment will automatically be
            preserved.
        """
        self._header.update('extver', value, comment, before, after,
                            savecomment)
        self._extver = value


    def _verify(self, option='warn'):
        from pyfits.core import _ErrList
        from pyfits.hdu.extension import _ExtensionHDU

        _err = _ErrList([], unit='Card')

        isValid = "val in [8, 16, 32, 64, -32, -64]"

        # Verify location and value of mandatory keywords.
        # Do the first card here, instead of in the respective HDU classes,
        # so the checking is in order, in case of required cards in wrong order.
        if isinstance(self, _ExtensionHDU):
            firstkey = 'XTENSION'
            firstval = self._xtn
        else:
            firstkey = 'SIMPLE'
            firstval = True
        self.req_cards(firstkey, '== 0', '', firstval, option, _err)
        self.req_cards('BITPIX', '== 1', _isInt+" and "+isValid, 8, option, _err)
        self.req_cards('NAXIS', '== 2', _isInt+" and val >= 0 and val <= 999", 0, option, _err)

        naxis = self._header.get('NAXIS', 0)
        if naxis < 1000:
            for j in range(3, naxis+3):
                self.req_cards('NAXIS'+`j-2`, '== '+`j`, _isInt+" and val>= 0", 1, option, _err)
            # Remove NAXISj cards where j is not in range 1, naxis inclusive.
            for _card in self._header.ascard:
                if _card.key.startswith("NAXIS") and len(_card.key) > 5:
                    try:
                        number = int(_card.key[5:])
                        if number <= 0 or number > naxis:
                            raise ValueError
                    except ValueError:
                        _err.append(self.run_option(
                                option=option,
                                err_text=("NAXISj keyword out of range ('%s' when NAXIS == %d)" %
                                          (_card.key, naxis)),
                                fix="del self._header['%s']" % _card.key,
                                fix_text="Deleted."))

        # verify each card
        for _card in self._header.ascard:
            _err.append(_card._verify(option))

        return _err

    def req_cards(self, keywd, pos, test, fix_value, option, errlist):
        """
        Check the existence, location, and value of a required `Card`.

        TODO: Write about parameters

        If `pos` = `None`, it can be anywhere.  If the card does not exist,
        the new card will have the `fix_value` as its value when created.
        Also check the card's value by using the `test` argument.
        """
        _err = errlist
        fix = ''
        cards = self._header.ascard
        try:
            _index = cards.index_of(keywd)
        except:
            _index = None
        fixable = fix_value is not None

        insert_pos = len(cards)+1

        # if pos is a string, it must be of the syntax of "> n",
        # where n is an int
        if isinstance(pos, str):
            _parse = pos.split()
            if _parse[0] in ['>=', '==']:
                insert_pos = eval(_parse[1])

        # if the card does not exist
        if _index is None:
            err_text = "'%s' card does not exist." % keywd
            fix_text = "Fixed by inserting a new '%s' card." % keywd
            if fixable:

                # use repr to accomodate both string and non-string types
                # Boolean is also OK in this constructor
                _card = "Card('%s', %s)" % (keywd, `fix_value`)
                fix = "self._header.ascard.insert(%d, %s)" % (insert_pos, _card)
            _err.append(self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix, fixable=fixable))
        else:

            # if the supposed location is specified
            if pos is not None:
                test_pos = '_index '+ pos
                if not eval(test_pos):
                    err_text = "'%s' card at the wrong place (card %d)." % (keywd, _index)
                    fix_text = "Fixed by moving it to the right place (card %d)." % insert_pos
                    fix = "_cards=self._header.ascard; dummy=_cards[%d]; del _cards[%d];_cards.insert(%d, dummy)" % (_index, _index, insert_pos)
                    _err.append(self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix))

            # if value checking is specified
            if test:
                val = self._header[keywd]
                if not eval(test):
                    err_text = "'%s' card has invalid value '%s'." % (keywd, val)
                    fix_text = "Fixed by setting a new value '%s'." % fix_value
                    if fixable:
                        fix = "self._header['%s'] = %s" % (keywd, `fix_value`)
                    _err.append(self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix, fixable=fixable))

        return _err

    def _compute_checksum(self, bytes, sum32=0, blocking="standard"):
        """
        Compute the ones-complement checksum of a sequence of bytes.

        Parameters
        ----------
        bytes
            a memory region to checksum

        sum32
            incremental checksum value from another region

        blocking
            "standard", "nonstandard", or "either"
            selects the block size on which to perform checksumming,  originally
            the blocksize was chosen incorrectly.  "nonstandard" selects the
            original approach,  "standard" selects the interoperable
            blocking size of 2880 bytes.  In the context of _compute_checksum,
            "either" is synonymous with "standard".

        Returns
        -------
        ones complement checksum
        """
        blocklen = {"standard" : 2880,
                    "nonstandard" : len(bytes),
                    "either":2880,  # do standard first
                    True: 2880,
                    }[blocking]
        sum32 = np.array(sum32, dtype='uint32')
        for i in range(0, len(bytes), blocklen):
            length = min(blocklen, len(bytes)-i)   # ????
            sum32 = self._compute_hdu_checksum(bytes[i:i+length], sum32)
        return sum32

    def _compute_hdu_checksum(self, bytes, sum32=0):
        # Translated from FITS Checksum Proposal by Seaman, Pence, and Rots.
        # Use uint32 literals as a hedge against type promotion to int64.

        # This code should only be called with blocks of 2880 bytes
        # Longer blocks result in non-standard checksums with carry overflow
        # Historically,  this code *was* called with larger blocks and for that
        # reason still needs to be for backward compatibility.

        u8 = np.array(8, dtype='uint32')
        u16 = np.array(16, dtype='uint32')
        uFFFF = np.array(0xFFFF, dtype='uint32')

        b0 = bytes[0::4].astype('uint32') << u8
        b1 = bytes[1::4].astype('uint32')
        b2 = bytes[2::4].astype('uint32') << u8
        b3 = bytes[3::4].astype('uint32')

        hi = np.array(sum32, dtype='uint32') >> u16
        lo = np.array(sum32, dtype='uint32') & uFFFF

        hi += np.add.reduce((b0 + b1)).astype('uint32')
        lo += np.add.reduce((b2 + b3)).astype('uint32')

        hicarry = hi >> u16
        locarry = lo >> u16

        while int(hicarry) or int(locarry):
            hi = (hi & uFFFF) + locarry
            lo = (lo & uFFFF) + hicarry
            hicarry = hi >> u16
            locarry = lo >> u16

        return (hi << u16) + lo


    # _MASK and _EXCLUDE used for encoding the checksum value into a character
    # string.
    _MASK = [ 0xFF000000,
              0x00FF0000,
              0x0000FF00,
              0x000000FF ]

    _EXCLUDE = [ 0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f, 0x40,
                 0x5b, 0x5c, 0x5d, 0x5e, 0x5f, 0x60 ]

    def _encode_byte(self, byte):
        """
        Encode a single byte.
        """
        quotient = byte // 4 + ord('0')
        remainder = byte % 4

        ch = np.array(
            [(quotient + remainder), quotient, quotient, quotient],
            dtype='int32')

        check = True
        while check:
            check = False
            for x in self._EXCLUDE:
                for j in [0, 2]:
                    if ch[j] == x or ch[j+1] == x:
                        ch[j]   += 1
                        ch[j+1] -= 1
                        check = True
        return ch

    def _char_encode(self, value):
        """
        Encodes the checksum `value` using the algorithm described
        in SPR section A.7.2 and returns it as a 16 character string.

        Parameters
        ----------
        value
            a checksum

        Returns
        -------
        ascii encoded checksum
        """
        value = np.array(value, dtype='uint32')

        asc = np.zeros((16,), dtype='byte')
        ascii = np.zeros((16,), dtype='byte')

        for i in range(4):
            byte = (value & self._MASK[i]) >> ((3 - i) * 8)
            ch = self._encode_byte(byte)
            for j in range(4):
                asc[4*j+i] = ch[j]

        for i in range(16):
            ascii[i] = asc[(i+15) % 16]

        return ascii.tostring()

    def _datetime_str(self):
        """
        Time of now formatted like: 2007-05-30T19:05:11
        """
        now = str(datetime.datetime.now()).split()
        return now[0] + "T" + now[1].split(".")[0]

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        from pyfits.core import _fromfile

        if (not self.__dict__.has_key('data')):
            # This is the case where the data has not been read from the file
            # yet.  We find the data in the file, read it, and calculate the
            # datasum.
            if self.size() > 0:
                self._file.seek(self._datLoc)
                raw_data = _fromfile(self._file, dtype='ubyte',
                                     count=self._datSpan, sep="")
                return self._compute_checksum(raw_data, blocking=blocking)
            else:
                return 0
        elif (self.data != None):
            return self._compute_checksum(
                                 np.fromstring(self.data, dtype='ubyte'), blocking=blocking)
        else:
            return 0

    def _calculate_checksum(self, datasum, blocking):
        """
        Calculate the value of the ``CHECKSUM`` card in the HDU.
        """

        from pyfits.core import _padLength, _pad

        oldChecksum = self.header['CHECKSUM']
        self.header.update('CHECKSUM', '0'*16);

        # Convert the header to a string.
        s = repr(self._header.ascard) + _pad('END')
        s = s + _padLength(len(s))*' '

        # Calculate the checksum of the Header and data.
        cs = self._compute_checksum(np.fromstring(s, dtype='ubyte'), datasum, blocking=blocking)

        # Encode the checksum into a string.
        s = self._char_encode(~cs)

        # Return the header card value.
        self.header.update("CHECKSUM", oldChecksum);

        return s

    def add_datasum(self, when=None, blocking="standard"):
        """
        Add the ``DATASUM`` card to this HDU with the value set to the
        checksum calculated for the data.

        Parameters
        ----------
        when : str, optional
            Comment string for the card that by default represents the
            time when the checksum was calculated

        blocking: str, optional
            "standard" or "nonstandard", compute sum 2880 bytes at a time, or not

        Returns
        -------
        checksum : int
            The calculated datasum

        Notes
        -----
        For testing purposes, provide a `when` argument to enable the
        comment value in the card to remain consistent.  This will
        enable the generation of a ``CHECKSUM`` card with a consistent
        value.
        """
        cs = self._calculate_datasum(blocking)

        if when is None:
           when = "data unit checksum updated " + self._datetime_str()

        self.header.update("DATASUM", str(cs), when);
        return cs

    def add_checksum(self, when=None, override_datasum=False, blocking="standard"):
        """
        Add the ``CHECKSUM`` and ``DATASUM`` cards to this HDU with
        the values set to the checksum calculated for the HDU and the
        data respectively.  The addition of the ``DATASUM`` card may
        be overridden.

        Parameters
        ----------
        when : str, optional
           comment string for the cards; by default the comments
           will represent the time when the checksum was calculated

        override_datasum : bool, optional
           add the ``CHECKSUM`` card only

        blocking: str, optional
            "standard" or "nonstandard", compute sum 2880 bytes at a time, or not

        Notes
        -----
        For testing purposes, first call `add_datasum` with a `when`
        argument, then call `add_checksum` with a `when` argument and
        `override_datasum` set to `True`.  This will provide
        consistent comments for both cards and enable the generation
        of a ``CHECKSUM`` card with a consistent value.
        """

        if not override_datasum:
           # Calculate and add the data checksum to the header.
           data_cs = self.add_datasum(when, blocking)
        else:
           # Just calculate the data checksum
           data_cs = self._calculate_datasum(blocking)

        if when is None:
            when = "HDU checksum updated " + self._datetime_str()

        # Add the CHECKSUM card to the header with a value of all zeros.
        if self.header.has_key("DATASUM"):
            self.header.update("CHECKSUM", "0"*16, when, before='DATASUM');
        else:
            self.header.update("CHECKSUM", "0"*16, when);

        s = self._calculate_checksum(data_cs, blocking)

        # Update the header card.
        self.header.update("CHECKSUM", s, when);

    def verify_datasum(self, blocking="standard"):
        """
        Verify that the value in the ``DATASUM`` keyword matches the value
        calculated for the ``DATASUM`` of the current HDU data.

        blocking: str, optional
            "standard" or "nonstandard", compute sum 2880 bytes at a time, or not

        Returns
        -------
        valid : int
           - 0 - failure
           - 1 - success
           - 2 - no ``DATASUM`` keyword present
        """
        if self.header.has_key('DATASUM'):
            if self._calculate_datasum(blocking) == int(self.header['DATASUM']):
                return 1
            elif blocking == "either": # i.e. standard failed,  try nonstandard
                return self.verify_datasum(blocking="nonstandard")
            else: # Failed with all permitted blocking kinds
                return 0
        else:
            return 2

    def verify_checksum(self, blocking="standard"):
        """
        Verify that the value in the ``CHECKSUM`` keyword matches the
        value calculated for the current HDU CHECKSUM.

        blocking: str, optional
            "standard" or "nonstandard", compute sum 2880 bytes at a time, or not

        Returns
        -------
        valid : int
           - 0 - failure
           - 1 - success
           - 2 - no ``CHECKSUM`` keyword present
        """
        if self._header.has_key('CHECKSUM'):
            if self._header.has_key('DATASUM'):
                datasum = self._calculate_datasum(blocking)
            else:
                datasum = 0
            if self._calculate_checksum(datasum, blocking) == self.header['CHECKSUM']:
                return 1
            elif blocking == "either": # i.e. standard failed,  try nonstandard
                return self.verify_checksum(blocking="nonstandard")
            else: # Failed with all permitted blocking kinds
                return 0
        else:
            return 2


class _TempHDU(_ValidHDU):
    """
    Temporary HDU, used when the file is first opened. This is to
    speed up the open.  Any header will not be initialized till the
    HDU is accessed.
    """

    def _getname(self):
        """
        Get the ``EXTNAME`` and ``EXTVER`` from the header.
        """
        re_extname = re.compile(r"EXTNAME\s*=\s*'([ -&(-~]*)'")
        re_extver = re.compile(r"EXTVER\s*=\s*(\d+)")

        mo = re_extname.search(self._raw)
        if mo:
            name = mo.group(1).rstrip()
        else:
            name = ''

        mo = re_extver.search(self._raw)
        if mo:
            extver = int(mo.group(1))
        else:
            extver = 1

        return name, extver

    def _getsize(self, block):
        """
        Get the size from the first block of the HDU.
        """
        re_simple = re.compile(r'SIMPLE  =\s*')
        re_bitpix = re.compile(r'BITPIX  =\s*(-?\d+)')
        re_naxis = re.compile(r'NAXIS   =\s*(\d+)')
        re_naxisn = re.compile(r'NAXIS(\d)  =\s*(\d+)')
        re_gcount = re.compile(r'GCOUNT  =\s*(-?\d+)')
        re_pcount = re.compile(r'PCOUNT  =\s*(-?\d+)')
        re_groups = re.compile(r'GROUPS  =\s*(T)')

        simple = re_simple.search(block[:80])
        mo = re_bitpix.search(block)
        if mo is not None:
            bitpix = int(mo.group(1))
        else:
            raise ValueError("BITPIX not found where expected")

        mo = re_gcount.search(block)
        if mo is not None:
            gcount = int(mo.group(1))
        else:
            gcount = 1

        mo = re_pcount.search(block)
        if mo is not None:
            pcount = int(mo.group(1))
        else:
            pcount = 0

        mo = re_groups.search(block)
        if mo and simple:
            groups = 1
        else:
            groups = 0

        mo = re_naxis.search(block)
        if mo is not None:
            naxis = int(mo.group(1))
            pos = mo.end(0)
        else:
            raise ValueError("NAXIS not found where expected")

        if naxis == 0:
            datasize = 0
        else:
            dims = [0]*naxis
            for i in range(naxis):
                mo = re_naxisn.search(block, pos)
                pos = mo.end(0)
                dims[int(mo.group(1))-1] = int(mo.group(2))
            datasize = reduce(operator.mul, dims[groups:])
        size = abs(bitpix) * gcount * (pcount + datasize) // 8

        if simple and not groups:
            name = 'PRIMARY'
        else:
            name = ''

        return size, name

    def setupHDU(self, classExtensions={}):
        """
        Read one FITS HDU, data portions are not actually read here,
        but the beginning locations are computed.
        """

        from pyfits.core import Header, DELAYED, _blockLen

        _cardList = []
        _keyList = []

        blocks = self._raw
        if (len(blocks) % _blockLen) != 0:
            raise IOError, 'Header size is not multiple of %d: %d' % (_blockLen, len(blocks))
        elif (blocks[:8] not in ['SIMPLE  ', 'XTENSION']):
            raise IOError, 'Block does not begin with SIMPLE or XTENSION'

        for i in range(0, len(blocks), Card.length):
            _card = createCardFromString(blocks[i:i+Card.length])
            _key = _card.key

            if _key == 'END':
                break
            else:
                _cardList.append(_card)
                _keyList.append(_key)

        # Deal with CONTINUE cards
        # if a long string has CONTINUE cards, the "Card" is considered
        # to be more than one 80-char "physical" cards.
        _max = _keyList.count('CONTINUE')
        _start = 0
        for i in range(_max):
            _where = _keyList[_start:].index('CONTINUE') + _start
            for nc in range(1, _max+1):
                if _where+nc >= len(_keyList):
                    break
                if _cardList[_where+nc]._cardimage[:10].upper() != 'CONTINUE  ':
                    break

            # combine contiguous CONTINUE cards with its parent card
            if nc > 0:
                _longstring = _cardList[_where-1]._cardimage
                for c in _cardList[_where:_where+nc]:
                    _longstring += c._cardimage
                _cardList[_where-1] = _Card_with_continue().fromstring(_longstring)
                del _cardList[_where:_where+nc]
                del _keyList[_where:_where+nc]
                _start = _where

            # if not the real CONTINUE card, skip to the next card to search
            # to avoid starting at the same CONTINUE card
            else:
                _start = _where + 1
            if _keyList[_start:].count('CONTINUE') == 0:
                break

        # construct the Header object, using the cards.
        header = Header(CardList(_cardList, keylist=_keyList))

        if classExtensions.has_key(header._hdutype):
            header._hdutype = classExtensions[header._hdutype]

        from pyfits.hdu.image import PrimaryHDU, ImageHDU
        if ((header._hdutype == PrimaryHDU or header._hdutype == ImageHDU)
            and (hasattr(self, '_do_not_scale_image_data'))):
            hdu = header._hdutype(data=DELAYED, header=header,
                                  do_not_scale_image_data=self._do_not_scale_image_data)
        else:
            hdu = header._hdutype(data=DELAYED, header=header)

        try:
            # pass these attributes
            hdu._file = self._file
            hdu._hdrLoc = self._hdrLoc
            hdu._datLoc = self._datLoc
            hdu._datSpan = self._datSpan
            hdu._ffile = self._ffile
            hdu.name = self.name
            hdu._extver = self._extver
            hdu._new = 0
            hdu.header._mod = 0
            hdu.header.ascard._mod = 0
        except:
            pass

        return hdu

    def isPrimary(self):
        blocks = self._raw

        if (blocks[:8] == 'SIMPLE  '):
           return True
        else:
           return False
