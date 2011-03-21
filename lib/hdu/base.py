import datetime
import inspect
import operator
import warnings

import numpy as np

from pyfits.card import Card, CardList, _ContinueCard, \
                        create_card_from_string, _pad
from pyfits.column import DELAYED
from pyfits.util import lazyproperty, _fromfile, _is_int, _with_extensions, \
                        _pad_length, BLOCK_SIZE
from pyfits.verify import _Verify, _ErrList


class _AllHDU(object):
    """
    Base class for all HDU (header data unit) classes.
    """

    def __init__(self, data=None, header=None):
        self._header = header
        self._file = None
        self._offset = None
        self._datLoc = None
        self._data_loaded = False
        self.name = None

        if data is not None and data is not DELAYED:
            self._data_loaded = True

    def _getheader(self):
        return self._header

    def _setheader(self, value):
        self._header = value
    header = property(_getheader, _setheader)

    @_with_extensions
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

        hdulist = HDUList([self])
        hdulist.writeto(name, output_verify, clobber=clobber,
                        checksum=checksum)


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

    def size(self):
        """
        Returns the size (in bytes) of the HDU's data part.
        """

        return self._file.size - self._datLoc

    def _summary(self):
        return '%-10s  %-11s' % (self.name, 'CorruptedHDU')

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

    def size(self):
        """
        Returns the size (in bytes) of the HDU's data part.
        """

        return self._file.size - self._datLoc

    def _summary(self):
        return '%-7s  %-11s  %5d' % (self.name, 'NonstandardHDU',
                                     len(self._header.ascard))

    @lazyproperty
    def data(self):
        """
        Return the file data.
        """

        self._file.seek(self._datLoc)
        self._data_loaded = True
        return self._file.read()

    def _verify(self, option='warn'):
        errs = _ErrList([], unit='Card')

        # verify each card
        for card in self._header.ascard:
            errs.append(card._verify(option))

        return errs


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
            for idx in range(naxis):
                size = size * self._header['NAXIS' + str(idx + 1)]
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

        from pyfits.file import FITSFile

        f = FITSFile()
        return f.writeHDUheader(self)[1] + f.writeHDUdata(self)[1]

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

        if hasattr(self, '_file') and self._file:
           return {'file': self._file, 'filemode': self._file.mode,
                   'hdrLoc': self._hdrLoc, 'datLoc': self._datLoc,
                   'datSpan': self._datSpan}
        else:
            return None

    def copy(self):
        """
        Make a copy of the HDU, both header and data are copied.
        """

        if self.data is not None:
            data = self.data.copy()
        else:
            data = None
        return self.__class__(data=data, header=self._header.copy())


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
        from pyfits.hdu.extension import _ExtensionHDU

        errs= _ErrList([], unit='Card')

        is_valid = lambda v: v in [8, 16, 32, 64, -32, -64]

        # Verify location and value of mandatory keywords.
        # Do the first card here, instead of in the respective HDU classes,
        # so the checking is in order, in case of required cards in wrong order.
        if isinstance(self, _ExtensionHDU):
            firstkey = 'XTENSION'
            firstval = self._extension
        else:
            firstkey = 'SIMPLE'
            firstval = True

        self.req_cards(firstkey, 0, None, firstval, option, errs)
        self.req_cards('BITPIX', 1, lambda v: (_is_int(v) and is_valid(v)), 8,
                       option, errs)
        self.req_cards('NAXIS', 2,
                       lambda v: (_is_int(v) and v >= 0 and v <= 999), 0,
                       option, errs)

        naxis = self._header.get('NAXIS', 0)
        if naxis < 1000:
            for ax in range(3, naxis + 3):
                self.req_cards('NAXIS' + str(ax - 2), ax,
                               lambda v: (_is_int(v) and v >= 0), 1, option,
                               errs)

            # Remove NAXISj cards where j is not in range 1, naxis inclusive.
            for card in self._header.ascard:
                if card.key.startswith('NAXIS') and len(card.key) > 5:
                    try:
                        number = int(card.key[5:])
                        if number <= 0 or number > naxis:
                            raise ValueError
                    except ValueError:
                        err_text = "NAXISj keyword out of range ('%s' when " \
                                   "NAXIS == %d)" % (card.key, naxis)
 
                        def fix(self=self, card=card):
                            del self._header[card.key]

                        errs.append(
                            self.run_option(option=option, err_text=err_text,
                                            fix=fix, fix_text="Deleted."))

        # verify each card
        for card in self._header.ascard:
            errs.append(card._verify(option))

        return errs

    def req_cards(self, keywd, pos, test, fix_value, option, errlist):
        """
        Check the existence, location, and value of a required `Card`.

        TODO: Write about parameters

        If `pos` = `None`, it can be anywhere.  If the card does not exist,
        the new card will have the `fix_value` as its value when created.
        Also check the card's value by using the `test` argument.
        """

        errs = errlist
        fix = None
        cards = self._header.ascard

        try:
            _index = cards.index_of(keywd)
        except:
            _index = None

        fixable = fix_value is not None

        insert_pos = len(cards) + 1

        # If pos is an int, insert at the given position (and convert it to a
        # lambda)
        if _is_int(pos):
            insert_pos = pos
            pos = lambda x: x == insert_pos

        # if the card does not exist
        if _index is None:
            err_text = "'%s' card does not exist." % keywd
            fix_text = "Fixed by inserting a new '%s' card." % keywd
            if fixable:
                # use repr to accomodate both string and non-string types
                # Boolean is also OK in this constructor
                card = "Card('%s', %s)" % (keywd, repr(fix_value))

                def fix(self=self, insert_pos=insert_pos, card=card):
                    self._header.ascard.insert(insert_pos, card)

            errs.append(self.run_option(option, err_text=err_text,
                        fix_text=fix_text, fix=fix, fixable=fixable))
        else:
            # if the supposed location is specified
            if pos is not None:
                if not pos(_index):
                    err_text = "'%s' card at the wrong place (card %d)." \
                               % (keywd, _index)
                    fix_text = "Fixed by moving it to the right place " \
                               "(card %d)." % insert_pos

                    def fix(self=self, index=_index, insert_pos=insert_pos):
                        cards = self._header.ascard
                        dummy = cards[index]
                        del cards[index]
                        cards.insert(insert_pos, dummy)

                    errs.append(self.run_option(option, err_text=err_text,
                                fix_text=fix_text, fix=fix))

            # if value checking is specified
            if test:
                val = self._header[keywd]
                if not test(val):
                    err_text = "'%s' card has invalid value '%s'." \
                               % (keywd, val)
                    fix_text = "Fixed by setting a new value '%s'." % fix_value

                    if fixable:
                        def fix(self=self, keyword=keyword, val=fix_value):
                            self._header[keyword] = repr(fix_value)

                    errs.append(self.run_option(option, err_text=err_text,
                                fix_text=fix_text, fix=fix, fixable=fixable))

        return errs

    def add_datasum(self, when=None, blocking='standard'):
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
           when = 'data unit checksum updated %s' % self._get_timestamp()

        self.header.update('DATASUM', str(cs), when);
        return cs

    def add_checksum(self, when=None, override_datasum=False,
                     blocking='standard'):
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
            when = 'HDU checksum updated %s' % self._get_timestamp()

        # Add the CHECKSUM card to the header with a value of all zeros.
        if 'DATASUM' in self.header:
            self.header.update('CHECKSUM', '0'*16, when, before='DATASUM')
        else:
            self.header.update('CHECKSUM', '0'*16, when)

        s = self._calculate_checksum(data_cs, blocking)

        # Update the header card.
        self.header.update('CHECKSUM', s, when);

    def verify_datasum(self, blocking='standard'):
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

        if 'DATASUM' in self.header:
            datasum = self._calculate_datasum(blocking)
            if datasum == int(self.header['DATASUM']):
                return 1
            elif blocking == 'either': # i.e. standard failed,  try nonstandard
                return self.verify_datasum(blocking='nonstandard')
            else: # Failed with all permitted blocking kinds
                return 0
        else:
            return 2

    def verify_checksum(self, blocking='standard'):
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

        if 'CHECKSUM' in self._header:
            if 'DATASUM' in self._header:
                datasum = self._calculate_datasum(blocking)
            else:
                datasum = 0
            checksum = self._calculate_checksum(datasum, blocking)
            if checksum == self.header['CHECKSUM']:
                return 1
            elif blocking == 'either': # i.e. standard failed,  try nonstandard
                return self.verify_checksum(blocking='nonstandard')
            else: # Failed with all permitted blocking kinds
                return 0
        else:
            return 2

    def _get_timestamp(self):
        """
        Return the current timestamp in ISO 8601 format, with microseconds
        stripped off.

        Ex.: 2007-05-30T19:05:11
        """

        return datetime.datetime.now().isoformat()[:19]

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        if self._data_loaded:
            # This is the case where the data has not been read from the file
            # yet.  We find the data in the file, read it, and calculate the
            # datasum.
            if self.size() > 0:
                raw_data = self._file.readarray(size=self._datSpan,
                                                offset=self._datLoc,
                                                dtype='ubyte')
                return self._compute_checksum(raw_data, blocking=blocking)
            else:
                return 0
        elif self.data is not None:
            return self._compute_checksum(
                np.fromstring(self.data, dtype='ubyte'), blocking=blocking)
        else:
            return 0

    def _calculate_checksum(self, datasum, blocking):
        """
        Calculate the value of the ``CHECKSUM`` card in the HDU.
        """

        oldChecksum = self.header['CHECKSUM']
        self.header.update('CHECKSUM', '0'*16);

        # Convert the header to a string.
        s = repr(self._header.ascard) + _pad('END')
        s = s + _pad_length(len(s))*' '

        # Calculate the checksum of the Header and data.
        cs = self._compute_checksum(np.fromstring(s, dtype='ubyte'), datasum,
                                    blocking=blocking)

        # Encode the checksum into a string.
        s = self._char_encode(~cs)

        # Return the header card value.
        self.header.update("CHECKSUM", oldChecksum);

        return s

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

        blocklen = {'standard': 2880,
                    'nonstandard': len(bytes),
                    'either':2880,  # do standard first
                    True: 2880}[blocking]

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



# TODO: Possibly move this into a separate module, and possibly even not make
# it a _ValidHDU subclass (after all, and this point we don't necessarily know
# if the HDU is valid)
class _RawHDU(_ValidHDU):
    """
    Temporary HDU, used when the file is first opened. This is to
    speed up the open.  Any header will not be initialized till the
    HDU is accessed.
    """

    def __init__(self, data='', fileobj=None, offset=0, checksum=False,
                 **kwargs):
        """
        TODO: Document me better.
        """

        from pyfits.header import Header

        super(_RawHDU, self).__init__()
        self._raw = data
        self._check_checksum = checksum
        self._kwargs = kwargs

        if (len(data) % BLOCK_SIZE) != 0:
            raise IOError('Header size is not multiple of %d: %d'
                          % (BLOCK_SIZE, len(data)))
        elif data[:8] not in ['SIMPLE  ', 'XTENSION']:
            raise IOError('Block does not begin with SIMPLE or XTENSION')

        cards = []
        keys = []

        for idx in range(0, len(data), Card.length):
            card = create_card_from_string(data[idx:idx + Card.length])
            key = card.key

            if key == 'END':
                break
            else:
                cards.append(card)
                keys.append(key)

        self._header = Header(CardList(cards, keylist=keys))

        size = self.size()

        if 'SIMPLE' in self._header and self._header['SIMPLE']:
            self.name = 'PRIMARY'
            self._extver = 1
        else:
            # If name was not PRIMARY get extname and extver
            if 'EXTNAME' in self._header:
                self.name = self._header['EXTNAME']
            else:
                self.name = ''
            if 'EXTVER' in self._header:
                self._extver = self._header['EXTVER']
            else:
                self._extver = 1

        self._file = fileobj
        self._hdrLoc = offset                 # beginning of the header area
        self._datLoc = fileobj.tell()         # beginning of the data area

        # data area size, including padding
        self._datSpan = size + _pad_length(size)
        self._new = False

    def size(self):
        if not 'BITPIX' in self._header:
            raise ValueError('BITPIX not found where expected')
        if not 'NAXIS' in self._header:
            raise ValueError('NAXIS not found where expected')
        return super(_RawHDU, self).size()

    @_with_extensions
    def setupHDU(self, classExtensions={}):
        """
        Read one FITS HDU; data portions are not actually read here,
        but the beginning locations are computed.
        """

        from pyfits.header import Header

        # Deal with CONTINUE cards
        # if a long string has CONTINUE cards, the "Card" is considered
        # to be more than one 80-char "physical" cards.
        cards = self._header.ascard

        idx = len(cards)
        continueimg = []
        for card in reversed(cards):
            idx -= 1
            if idx != 0 and card.key == 'CONTINUE':
                continueimg.append(card._cardimage)
                del cards[idx]
            elif continueimg:
                continueimg.append(card._cardimage)
                continueimg = ''.join(reversed(continueimg))
                cards[idx] = _ContinueCard.fromstring(continueimg)
                continueimg = []

        # construct the new Header object with combined CONTINUE cards
        header = Header(CardList(cards))

        # Determine the appropriate arguments to pass to the constructor from
        # self._kwargs.  self._kwargs contains any number of optional arguments
        # that may or may not be valid depending on the HDU type
        cls = header._hdutype
        args, varargs, varkwargs, defaults = inspect.getargspec(cls.__init__)
        if not varkwargs:
            # If __init__ accepts arbitrary keyword arguments, then we can go
            # ahead and pass all keyword argumnets; otherwise we need to delete
            # any that are invalid
            for key in self._kwargs.keys():
                if key not in args:
                    del self._kwargs[key]

        hdu = cls(data=DELAYED, header=header, **self._kwargs)

        # pass on these attributes
        hdu._file = self._file
        hdu._hdrLoc = self._hdrLoc
        hdu._datLoc = self._datLoc
        hdu._datSpan = self._datSpan
        hdu.name = self.name
        hdu._extver = self._extver
        hdu._new = False
        hdu.header._mod = False
        hdu.header.ascard._mod = False

        if self._check_checksum:
            self._verify_checksum_datasum(hdu)

        return hdu

    def is_primary(self):
        # TODO: This doesn't seem to be used anyhwere, but I'm hesitant to
        # remove it until I'm sure no one uses it.
        blocks = self._raw

        if (blocks[:8] == 'SIMPLE  '):
           return True
        else:
           return False
    isPrimary = is_primary

    def _verify_checksum_datasum(self, hdu):
        """
        Verify the checksum/datasum values if the cards exist in the header.
        """

        # NOTE:  private data members _checksum and _datasum are
        # used by the utility script "fitscheck" to detect missing
        # checksums.

        if 'CHECKSUM' in hdu.header:
            hdu._checksum = hdu._header['CHECKSUM']
            hdu._checksum_comment = hdu._header.ascard['CHECKSUM'].comment
            if not hdu.verify_checksum():
                 warnings.warn('Warning:  Checksum verification failed for '
                               'HDU %s.\n' % ((hdu.name, hdu._extver),))
            del hdu._header['CHECKSUM']
        else:
            hdu._checksum = None
            hdu._checksum_comment = None

        if 'DATASUM' in hdu.header:
             hdu._datasum = hdu._header['DATASUM']
             hdu._datasum_comment = hdu._header.ascard['DATASUM'].comment

             if not hdu.verify_datasum():
                 warnings.warn('Warning:  Datasum verification failed for '
                               'HDU %s.\n' % ((hdu.name, hdu._extver),))
             del hdu.header['DATASUM']
        else:
             hdu._checksum = None
             hdu._checksum_comment = None
             hdu._datasum = None
             hdu._datasum_comment = None
