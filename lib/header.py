from UserDict import DictMixin

from pyfits.card import Card, CardList, RecordValuedKeywordCard, \
                        _HierarchCard, create_card, upper_key
from pyfits.hdu.base import _NonstandardHDU, _CorruptedHDU, _ValidHDU
from pyfits.hdu.compressed import COMPRESSION_SUPPORTED, CompImageHDU
from pyfits.hdu.groups import GroupsHDU
from pyfits.hdu.image import _ImageBaseHDU, PrimaryHDU, ImageHDU
from pyfits.hdu.table import TableHDU, BinTableHDU, _TableBaseHDU


# TODO: The UserDict documentation recommends using the
# collections.MutableMapping ABC in Python >= 2.6, but we're not requiring 2.6
# yet
class Header(DictMixin):
    """
    FITS header class.

    The purpose of this class is to present the header like a
    dictionary as opposed to a list of cards.

    The attribute `ascard` supplies the header like a list of cards.

    The header class uses the card's keyword as the dictionary key and
    the cards value is the dictionary value.

    The `has_key`, `get`, and `keys` methods are implemented to
    provide the corresponding dictionary functionality.  The header
    may be indexed by keyword value and like a dictionary, the
    associated value will be returned.  When the header contains cards
    with duplicate keywords, only the value of the first card with the
    given keyword will be returned.

    The header may also be indexed by card list index number.  In that
    case, the value of the card at the given index in the card list
    will be returned.

    A delete method has been implemented to allow deletion from the
    header.  When `del` is called, all cards with the given keyword
    are deleted from the header.

    The `Header` class has an associated iterator class `_Header_iter`
    which will allow iteration over the unique keywords in the header
    dictionary.
    """

    def __init__(self, cards=[], txtfile=None):
        """
        Construct a `Header` from a `CardList` and/or text file.

        Parameters
        ----------
        cards : A list of `Card` objects, optional
            The cards to initialize the header with.

        txtfile : file path, file object or file-like object, optional
            Input ASCII header parameters file.
        """

        # populate the cardlist
        self.ascard = CardList(cards)

        if txtfile:
            # get the cards from the input ASCII file
            self.fromTxtFile(txtfile, not len(self.ascard))
            self._mod = 0
        else:
            # decide which kind of header it belongs to
            self._updateHDUtype()

    def __contains__(self, key):
        """
        Check for existence of a keyword.

        Parameters
        ----------
        key : str or int
           Keyword name.  If given an index, always returns 0.

        Returns
        -------
        has_key : bool
            Returns `True` if found, otherwise, `False`.
        """

        key = upper_key(key)
        if key[:8] == 'HIERARCH':
            key = key[8:].strip()
        return key in self.ascard

    def __getitem__ (self, key):
        """
        Get a header keyword value.
        """

        card = self.ascard[key]

        if isinstance(card, RecordValuedKeywordCard) and \
           (not isinstance(key, basestring) or '.' not in key):
            return card.strvalue()
        elif isinstance(card, CardList):
            return card
        else:
            return card.value

    def __setitem__ (self, key, value):
        """
        Set a header keyword value.
        """

        self.ascard[key].value = value
        self._mod = 1

    def __delitem__(self, key):
        """
        Delete card(s) with the name `key`.
        """

        # delete ALL cards with the same keyword name
        if isinstance(key, basestring):
            while True:
                try:
                    del self.ascard[key]
                    self._mod = 1
                except:
                    return

        # for integer key only delete once
        else:
            del self.ascard[key]
            self._mod = 1

    def __str__(self):
        return str(self.ascard)

    def keys(self):
        """
        Return a list of keys with duplicates removed.
        """

        retval = []

        for key in self.ascard.keys():
            if not key in retval:
                retval.append(key)

        return retval

    def update(self, key, value, comment=None, before=None, after=None,
               savecomment=False):
        """
        Update one header card.

        If the keyword already exists, it's value and/or comment will
        be updated.  If it does not exist, a new card will be created
        and it will be placed before or after the specified location.
        If no `before` or `after` is specified, it will be appended at
        the end.

        Parameters
        ----------
        key : str
            keyword

        value : str
            value to be used for updating

        comment : str, optional
            to be used for updating, default=None.

        before : str or int, optional
            name of the keyword, or index of the `Card` before which
            the new card will be placed.  The argument `before` takes
            precedence over `after` if both specified.

        after : str or int, optional
            name of the keyword, or index of the `Card` after which
            the new card will be placed.

        savecomment : bool, optional
            When `True`, preserve the current comment for an existing
            keyword.  The argument `savecomment` takes precedence over
            `comment` if both specified.  If `comment` is not
            specified then the current comment will automatically be
            preserved.
        """

        keylist = RecordValuedKeywordCard.validKeyValue(key, value)

        if keylist:
            keyword = keylist[0] + '.' + keylist[1]
        else:
            keyword = key

        if self.has_key(keyword):
            j = self.ascard.index_of(keyword)
            if not savecomment and comment is not None:
                _comment = comment
            else:
                _comment = self.ascard[j].comment
            self.ascard[j] = create_card(key, value, _comment)
        elif before != None or after != None:
            _card = create_card(key, value, comment)
            self.ascard._pos_insert(_card, before=before, after=after)
        else:
            self.ascard.append(create_card(key, value, comment))

        self._mod = 1

        # If this header is associated with a compImageHDU then update
        # the objects underlying header (_table_header) unless the update was
        # made to a card that describes the data.

        # TODO: Consider creating a separate class for CompImageHDU headers

        if hasattr(self, '_table_header') and \
           key not in ('XTENSION', 'BITPIX', 'PCOUNT', 'GCOUNT', 'TFIELDS',
                       'ZIMAGE', 'ZBITPIX', 'ZCMPTYPE') and \
           key[:4] not in ('ZVAL') and \
           key[:5] not in ('NAXIS', 'TTYPE', 'TFORM', 'ZTILE', 'ZNAME') and \
           key[:6] not in ('ZNAXIS'):
            self._table_header.update(key, value, comment, before, after)

    def copy(self):
        """
        Make a copy of the `Header`.
        """

        tmp = Header(self.ascard.copy())

        # also copy the class
        tmp._hdutype = self._hdutype
        return tmp

    def ascardlist(self):
        """
        Returns a `CardList` object.
        """

        return self.ascard

    def rename_key(self, oldkey, newkey, force=False):
        """
        Rename a card's keyword in the header.

        Parameters
        ----------
        oldkey : str or int
            old keyword

        newkey : str
            new keyword

        force : bool
            When `True`, if new key name already exists, force to have
            duplicate name.
        """

        oldkey = upper_key(oldkey)
        newkey = upper_key(newkey)

        if newkey == 'CONTINUE':
            raise ValueError('Can not rename to CONTINUE')
        if newkey in Card._commentary_keys or oldkey in Card._commentary_keys:
            if not (newkey in Card._commentary_keys and 
                    oldkey in Card._commentary_keys):
                raise ValueError('Regular and commentary keys can not be '
                                 'renamed to each other.')
        elif (force == 0) and self.has_key(newkey):
            raise ValueError('Intended keyword %s already exists in header.'
                             % newkey)
        _index = self.ascard.index_of(oldkey)
        _comment = self.ascard[_index].comment
        _value = self.ascard[_index].value
        self.ascard[_index] = create_card(newkey, _value, _comment)


#        self.ascard[_index].__dict__['key']=newkey
#        self.ascard[_index].ascardimage()
#        self.ascard._keylist[_index] = newkey

    def add_history(self, value, before=None, after=None):
        """
        Add a ``HISTORY`` card.

        Parameters
        ----------
        value : str
            history text to be added.

        before : str or int, optional
            same as in `Header.update`

        after : str or int, optional
            same as in `Header.update`
        """

        self._add_commentary('history', value, before=before, after=after)

        # If this header is associated with a compImageHDU then update
        # the objects underlying header (_table_header).

        if hasattr('_table_header'):
            self._table_header.add_history(value, before, after)

    def add_comment(self, value, before=None, after=None):
        """
        Add a ``COMMENT`` card.

        Parameters
        ----------
        value : str
            text to be added.

        before : str or int, optional
            same as in `Header.update`

        after : str or int, optional
            same as in `Header.update`
        """

        self._add_commentary('comment', value, before=before, after=after)

        # If this header is associated with a compImageHDU then update
        # the objects underlying header (_table_header).
        if hasattr('_table_header'):
            self._table_header.add_comment(value, before, after)

    def add_blank(self, value='', before=None, after=None):
        """
        Add a blank card.

        Parameters
        ----------
        value : str, optional
            text to be added.

        before : str or int, optional
            same as in `Header.update`

        after : str or int, optional
            same as in `Header.update`
        """

        self._add_commentary(' ', value, before=before, after=after)

        # If this header is associated with a compImageHDU then update
        # the objects underlying header (_table_header).

        if hasattr('_table_header'):
            self._table_header.add_blank(value,before,after)

    def get_history(self):
        """
        Get all history cards as a list of string texts.
        """

        return [c for c in self.ascardlist() if c.key == 'HISTORY']

    def get_comment(self):
        """
        Get all comment cards as a list of string texts.
        """

        return [c for c in self.ascardlist() if c.key == 'COMMENT']

    def toTxtFile(self, outFile, clobber=False):
        """
        Output the header parameters to a file in ASCII format.

        Parameters
        ----------
        outFile : file path, file object or file-like object
            Output header parameters file.

        clobber : bool
            When `True`, overwrite the output file if it exists.
        """

        closeFile = False

        # check if the output file already exists
        if isinstance(outFile, basestring):
            if (os.path.exists(outFile) and os.path.getsize(outFile) != 0):
                if clobber:
                    warnings.warn("Overwriting existing file '%s'." % outFile)
                    os.remove(outFile)
                else:
                    raise IOError("File '%s' already exist." % outFile)

            outFile = open(outFile, 'w')
            closeFile = True

        lines = []   # lines to go out to the header parameters file

        # Add the card image for each card in the header to the lines list

        for j in range(len(self.ascardlist())):
            lines.append(str(self.ascardlist()[j]) + '\n')

        # Write the header parameter lines out to the ASCII header
        # parameter file
        outFile.writelines(lines)

        if closeFile:
            outFile.close()

    def fromTxtFile(self, inFile, replace=False):
        """
        Input the header parameters from an ASCII file.

        The input header cards will be used to update the current
        header.  Therefore, when an input card key matches a card key
        that already exists in the header, that card will be updated
        in place.  Any input cards that do not already exist in the
        header will be added.  Cards will not be deleted from the
        header.

        Parameters
        ----------
        inFile : file path, file object or file-like object
            Input header parameters file.

        replace : bool, optional
            When `True`, indicates that the entire header should be
            replaced with the contents of the ASCII file instead of
            just updating the current header.
        """

        closeFile = False

        if isinstance(inFile, basestring):
            inFile = open(inFile, 'r')
            closeFile = True

        lines = inFile.readlines()

        if closeFile:
            inFile.close()

        if len(self.ascardlist()) > 0 and not replace:
            prevKey = 0
        else:
            if replace:
                self.ascard = CardList([])
            prevKey = 0

        for line in lines:
            card = Card().fromstring(line[:min(80, len(line)-1)])
            card.verify('silentfix')

            if card.key == 'SIMPLE':
                if self.get('EXTENSION'):
                    del self.ascardlist()['EXTENSION']

                self.update(card.key, card.value, card.comment, before=0)
                prevKey = 0
            elif card.key == 'EXTENSION':
                if self.get('SIMPLE'):
                    del self.ascardlist()['SIMPLE']

                self.update(card.key, card.value, card.comment, before=0)
                prevKey = 0
            elif card.key == 'HISTORY':
                if not replace:
                    items = self.items()
                    idx = 0

                    for item in items:
                        if item[0] == card.key and item[1] == card.value:
                            break
                        idx += 1

                    if idx == len(self.ascardlist()):
                        self.add_history(card.value, after=prevKey)
                        prevKey += 1
                else:
                    self.add_history(card.value, after=prevKey)
                    prevKey += 1
            elif card.key == 'COMMENT':
                if not replace:
                    items = self.items()
                    idx = 0

                    for item in items:
                        if item[0] == card.key and item[1] == card.value:
                            break
                        idx += 1

                    if idx == len(self.ascardlist()):
                        self.add_comment(card.value, after=prevKey)
                        prevKey += 1
                else:
                    self.add_comment(card.value, after=prevKey)
                    prevKey += 1
            elif card.key == '        ':
                if not replace:
                    items = self.items()
                    idx = 0

                    for item in items:
                        if item[0] == card.key and item[1] == card.value:
                            break
                        idx += 1

                    if idx == len(self.ascardlist()):
                        self.add_blank(card.value, after=prevKey)
                        prevKey += 1
                else:
                    self.add_blank(card.value, after=prevKey)
                    prevKey += 1
            else:
                if isinstance(card, _HierarchCard):
                    prefix = 'hierarch '
                else:
                    prefix = ''

                self.update(prefix + card.key,
                                     card.value,
                                     card.comment,
                                     after=prevKey)
                prevKey += 1

        # update the hdu type of the header to match the parameters read in
        self._updateHDUtype()

    def _add_commentary(self, key, value, before=None, after=None):
        """
        Add a commentary card.

        If `before` and `after` are `None`, add to the last occurrence
        of cards of the same name (except blank card).  If there is no
        card (or blank card), append at the end.
        """

        new_card = Card(key, value)
        if before != None or after != None:
            self.ascard._pos_insert(new_card, before=before, after=after)
        else:
            if key[0] == ' ':
                useblanks = new_card._cardimage != ' '*80
                self.ascard.append(new_card, useblanks=useblanks, bottom=1)
            else:
                try:
                    _last = self.ascard.index_of(key, backward=1)
                    self.ascard.insert(_last+1, new_card)
                except:
                    self.ascard.append(new_card, bottom=1)

        self._mod = 1

    def _updateHDUtype(self):
        cards = self.ascard

        try:
            if cards[0].key == 'SIMPLE':
                if 'GROUPS' in cards._keys and cards['GROUPS'].value == True:
                    self._hdutype = GroupsHDU
                elif cards[0].value == True:
                    self._hdutype = PrimaryHDU
                elif cards[0].value == False:
                    self._hdutype = _NonstandardHDU
                else:
                    self._hdutype = _CorruptedHDU
            elif cards[0].key == 'XTENSION':
                xtension = cards[0].value.rstrip()
                if xtension == 'TABLE':
                    self._hdutype = TableHDU
                elif xtension == 'IMAGE':
                    self._hdutype = ImageHDU
                elif xtension in ('BINTABLE', 'A3DTABLE'):
                    try:
                        if cards['ZIMAGE'].value == True:
                            if COMPRESSION_SUPPORTED:
                                self._hdutype = CompImageHDU
                            else:
                                warnings.warn(
                                    'Failure creating a header for a '
                                    'compressed image HDU.')
                                warnings.warn(
                                    'The pyfitsComp module is not available.')
                                warnings.warn(
                                    'The HDU will be treated as a Binary '
                                    'Table HDU.')
                                raise KeyError
                    except KeyError:
                        self._hdutype = BinTableHDU
                else:
                    self._hdutype = _NonstandardExtHDU
            else:
                self._hdutype = _ValidHDU
        except:
            self._hdutype = _CorruptedHDU

    def _strip(self):
        """
        Strip cards specific to a certain kind of header.

        Strip cards like ``SIMPLE``, ``BITPIX``, etc. so the rest of
        the header can be used to reconstruct another kind of header.
        """

        try:

            # have both SIMPLE and XTENSION to accomodate Extension
            # and Corrupted cases
            del self['SIMPLE']
            del self['XTENSION']
            del self['BITPIX']

            if self.has_key('NAXIS'):
                _naxis = self['NAXIS']
            else:
                _naxis = 0

            if issubclass(self._hdutype, _TableBaseHDU):
                if self.has_key('TFIELDS'):
                    _tfields = self['TFIELDS']
                else:
                    _tfields = 0

            del self['NAXIS']
            for idx in range(_naxis):
                del self['NAXIS'+ str(idx + 1)]

            if issubclass(self._hdutype, PrimaryHDU):
                del self['EXTEND']
            del self['PCOUNT']
            del self['GCOUNT']

            if issubclass(self._hdutype, PrimaryHDU):
                del self['GROUPS']

            if issubclass(self._hdutype, _ImageBaseHDU):
                del self['BSCALE']
                del self['BZERO']

            if issubclass(self._hdutype, _TableBaseHDU):
                del self['TFIELDS']
                for name in ['TFORM', 'TSCAL', 'TZERO', 'TNULL', 'TTYPE',
                             'TUNIT']:
                    for idx in range(_tfields):
                        del self[name + str(idx + 1)]

            if issubclass(self._hdutype, BinTableHDU):
                for name in ['TDISP', 'TDIM', 'THEAP']:
                    for idx in range(_tfields):
                        del self[name + str(idx + 1)]

            if issubclass(self._hdutype, TableHDU):
                for idx in range(_tfields):
                    del self['TBCOL' + str(idx + 1)]

        except KeyError:
            pass


