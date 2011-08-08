import os
import warnings

from collections import defaultdict

from pyfits.card import Card, CardList, RecordValuedKeywordCard, \
                        _ContinueCard, _HierarchCard, create_card, \
                        create_card_from_string, upper_key
from pyfits.util import BLOCK_SIZE, deprecated, isiterable


class Header(object):
    # TODO: Fix up this docstring and all other docstrings in the class
    """
    FITS header class.

    The purpose of this class is to present the header like a
    dictionary as opposed to a list of cards.

    The header class uses the card's keyword as the dictionary key and
    the cards value is the dictionary value.

    The header may be indexed by keyword value and like a dictionary, the
    associated value will be returned.  When the header contains cards
    with duplicate keywords, only the value of the first card with the
    given keyword will be returned.  It is also possible to use a 2-tuple as
    the index in the form (keyword, n)--this returns the n-th value with that
    keyword, in the case where there are duplicate keywords.

    The header may also be indexed by card list index number.  In that
    case, the value of the card at the given index in the card list
    will be returned.
    """

    # TODO: Allow the header to take a few other types of inputs, for example
    # a list of (key, value) tuples, (key, value, comment) tuples, or a dict
    # of either key: value or key: (value, comment) mappings.  This could all
    # be handled by the underlying CardList I suppose.
    def __init__(self, cards=[], txtfile=None):
        """
        Construct a `Header` from an iterable and/or text file.

        Parameters
        ----------
        cards : A list of `Card` objects, optional
            The cards to initialize the header with.

        txtfile : file path, file object or file-like object, optional
            Input ASCII header parameters file.
        """

        self._cards = []
        self._modified = False
        self._keyword_indices = defaultdict(list)

        if txtfile:
            warnings.warn(
                'The txtfile argument is deprecated.  Use Header.fromfile to '
                'create a new Header object from a text file.',
                DeprecationWarning)
            # get the cards from the input ASCII file
            self.update(self.fromfile(txtfile))
            return

        if isinstance(cards, Header):
            cards = cards.cards

        self.update(cards)

    def __len__(self):
        return len(self._cards)

    def __iter__(self):
        for card in self._cards:
            yield card.keyword

    def __contains__(self, keyword):
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

        #key = upper_key(key)
        #if key[:8] == 'HIERARCH':
        #    key = key[8:].strip()
        return keyword.upper() in self._keyword_indices
    has_key = deprecated(name='has_key',
                         alternative='`key in header` syntax')(__contains__)

    def __getitem__ (self, key):
        """
        Get a header keyword value.
        """

#         card = self.ascard[key]
# 
#         if isinstance(card, RecordValuedKeywordCard) and \
#            (not isinstance(key, basestring) or '.' not in key):
#             return card.strvalue()
#         elif isinstance(card, CardList):
#             return card
#         else:
#             return card.value
        # TODO: Implement the filterstring capability of CardList
        return self._cards[self._cardindex(key)].value

    def __setitem__ (self, key, value):
        """
        Set a header keyword value.
        """

        if isinstance(value, tuple):
            if not (0 < len(value) <= 2):
                raise ValueError(
                    'A Header item may be set with either a scalar value, '
                    'a 1-tuple containing a scalar value, or a 2-tuple '
                    'containing a scalar value and comment string.')
            if len(value) == 1:
                value, comment = value, None
                if value is None:
                    value = ''
            elif len(value) == 2:
                value, comment = value
                if value is None:
                    value = ''
                if comment is None:
                    comment = ''
        else:
            comment = None

        try:
            idx = self._cardindex(key)
            card = self._cards[idx]
            card.value = value
            if comment is not None:
                card.comment = comment
            if card._modified:
                self._modified = True
        except (KeyError, IndexError):
            self._update(key, value, comment)
            self._modified = True

    def __delitem__(self, key):
        """
        Delete card(s) with the name `key`.
        """

        # TODO: Handle slices both here and in __set/getitem__
        # delete ALL cards with the same keyword name
        if isinstance(key, basestring):
            key = key.upper()
            if key not in self._keyword_indices:
                # TODO: The old Header implementation allowed deletes of
                # nonexistent keywords to pass; this behavior should be warned
                # against and eventually changed to raise a KeyError
                #raise KeyError("Keyword '%s' not found." % key)
                return
            for idx in self._keyword_indices[key][:]:
                # Have to copy the indices list since it will be modified below
                del self[idx]
            return

        idx = self._cardindex(key)
        keyword = self._cards[idx].keyword.upper()
        del self._cards[idx]
        indices = self._keyword_indices[keyword]
        indices.remove(idx)
        if not indices:
            del self._keyword_indices[keyword]

        # We also need to update all other indices
        self._updateindices(idx, increment=False)
        self._modified = True

    def __str__(self):
        return ''.join(str(card) for card in self._cards)

    @property
    def cards(self):
        """
        The underlying physical cards that make up this Header; it can be
        looked at, but it should not be modified directly.
        """

        return tuple(self._cards)

    @property
    def ascard(self):
        """
        Returns a CardList object wrapping this Header; provided for
        backwards compatibility for the old API (where Headers had an
        underlying CardList).
        """

        return CardList(self)

    @classmethod
    def fromstring(cls, data):
        """
        Creates an HDU header from a byte string containing the entire header
        data.

        Parameters
        ----------
        data : str
           String containing the entire header.
        """

        if (len(data) % BLOCK_SIZE) != 0:
            raise ValueError('Header size is not multiple of %d: %d'
                             % (BLOCK_SIZE, len(data)))

        cards = []

        # Split the header into individual cards
        idx = 0

        def peeknext():
            if idx + Card.length < len(data):
                return data[idx + Card.length:idx + Card.length * 2]
            else:
                return None

        while idx < len(data):
            image = [data[idx:idx + Card.length]]
            next = peeknext()
            while next and next[:8] == 'CONTINUE':
                image.append(next)
                idx += Card.length
                next = peeknext()
            card = Card.fromstring(''.join(image))
            if card.key == 'END':
                break
            cards.append(card)
            idx += Card.length

        return cls(cards)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def keys(self):
        """
        Return a list of keys with duplicates removed.
        """

        seen = set()
        retval = []

        for card in self._cards:
            # Blank keywords are ignored
            keyword = card.keyword
            if keyword and keyword not in seen:
                seen.add(keyword)
                retval.append(keyword)

        return retval

    def update(self, key=None, value=None, comment=None, before=None,
               after=None, savecomment=False, **kwargs):

        # TODO: Update this docstring

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

        if key is None:
            # Key will be an empty dict to be filled by any keyword arguments
            key = {}

        if isinstance(key, basestring):
            # Old-style update
            # TODO: Issue a deprecation warning for this
            if key in self:
                if comment is None or savecomment:
                    updateval = value
                else:
                    updateval = (value, comment)
                if before is None and after is None:
                    self[key] = updateval
                else:
                    self[key] = updateval
                    idx = self._cardindex(key)
                    card = self._cards[idx]
                    del self[idx]
                    self._relativeinsert(card, before=before, after=after)
            elif before is not None or after is not None:
                self._relativeinsert((key, value, comment), before=before,
                                     after=after)
            else:
                self[key] = (value, comment)

        # The rest of this should work similarly to dict.update()
        elif hasattr(key, 'iteritems') and hasattr(key, 'update'):
            # If this is a dict, just update with tuples created by joining the
            # key and the value--the value may either be a single item
            # representing the value of the card, or it may be a 2-tuple if the
            # value and a comment If this is not an ordered dict, the order in
            # which new keywords are appended is of course unpredictable, so
            # this method should not be used for adding new cards

            # If both a dictionary and keyword arguments are provided, they
            # keyword arguments take precendence; also add the
            # value/comment/before/after/savecomment keywords in case someone
            # actually wants to use those as the names of cards
            kwargs.update([('value', value), ('comment', comment),
                           ('before', before), ('after', after),
                           ('savecomment', savecomment)])
            key.update(kwargs)

            for k, val in key.iteritems():
                if not isinstance(val, tuple):
                    val = (k, val)
                elif 0 < len(val) <= 2:
                    val = (k,) + val
                else:
                    raise ValueError(
                            'Header update value for key %r is invalid; the '
                            'value must be either a scalar, a 1-tuple '
                            'containing the scalar value, or a 2-tuple '
                            'containing the value and a comment string.' % k)
                self._update(*val)
        elif isiterable(key):
            for idx, val in enumerate(key):
                if isinstance(val, (tuple, Card)) and (1 < len(val) <= 3):
                    self._update(*val)
                else:
                    raise ValueError(
                            'Header update sequence item #%d is invalid; the '
                            'item must either be a 2-tuple containing a '
                            'keyword and value, or a 3-tuple containing a '
                            'keyword, value, and comment string.' % idx)

    def append(self, card):
        if isinstance(card, tuple):
            card = Card(*card)
            self._cards.append(card)
        else:
            self._cards.append(card)
        keyword = card.keyword.upper()
        # TODO: This is not thread-safe; do we care?
        self._keyword_indices[keyword].append(len(self._cards) - 1)
        self._modified = True

    def insert(self, idx, card):
        if idx >= len(self._cards):
            # This is just an append
            self.append(card)
            return

        if isinstance(card, tuple):
            card = Card(*card)
            self._cards.insert(idx, card)
        else:
            self._cards.insert(idx, card)

        keyword = card.keyword.upper()

        # If idx was < 0, determine the actual index according to the rules
        # used by list.insert()
        if idx < 0:
            idx += len(self._cards) - 1
            if idx < 0:
                idx = 0

        # All the keyword indices above the insertion point must be updated
        self._updateindices(idx)

        self._keyword_indices[keyword].append(idx)
        count = len(self._keyword_indices[keyword])
        if count > 1:
            # There were already keywords with this same name
            # TODO: Maybe issue a warning when this occurs (and the keyword is
            # non-commentary)
            self._keyword_indices[keyword].sort()
        self._modified = True

    def _update(self, keyword, value='', comment=''):
        """
        The real update code.  If keyword already exists, its value and/or
        comment will be updated.  Otherwise a new card will be appended.

        This will not create a duplicate keyword except in the case of
        commentary cards.  The only other way to force creation of a duplicate
        is to use the insert(), append(), or extend() methods.
        """

        # TODO: Handle RVKCs at some point; right now for simplicity's sake
        # we're ignoring them

        # TODO: Obviously commentary keywords aren't really properly supported
        # yet

        keyword = keyword.upper()

        if keyword in self._keyword_indices:
            # Easy; just update the value/comment
            # TODO: Once we start worrying about the string representation of
            # the entire header, we should probably touch something here to
            # ensure that it's updated
            idx = self._keyword_indices[keyword][0]
            card = self._cards[idx]
            card.value = value
            card.comment = comment
            if card._modified:
                self._modified = True
        else:
            # A new keyword! self.append() will handle updating _modified
            self.append((keyword, value, comment))

    def _cardindex(self, key):
        """Returns an index into the ._cards list given a valid lookup key."""

        if isinstance(key, (int, slice)):
            return key

        if isinstance(key, basestring):
            key = (key.upper(), 0)

        if isinstance(key, tuple):
            if (len(key) != 2 or not isinstance(key[0], basestring) or
                    not isinstance(key[1], int)):
                raise ValueError(
                        'Tuple indices must be 2-tuples consisting of a '
                        'keyword string and an integer index.')
            keyword, n = key
            keyword = keyword.upper()
            # Returns the index into _cards for the n-th card with the given
            # keyword (where n is 0-based)
            if keyword not in self._keyword_indices:
                raise KeyError("Keyword '%s' not found." % keyword)
            return self._keyword_indices[keyword][n]
        else:
            raise ValueError(
                    'Header indices must be either a string, a 2-tuple, or '
                    'an integer.')
        # TODO: Handle and reraise key/index errors as well.

    def _relativeinsert(self, card, before=None, after=None):
        if before is None:
            insertionkey = after
        else:
            insertionkey = before
        idx = self._cardindex(insertionkey)
        if before is not None:
            self.insert(idx, card)
        else:
            self.insert(idx + 1, card)

    def _updateindices(self, idx, increment=True):
        """
        For all cards with index above idx, increment or decrement its index
        value in the keyword_indices dict.
        """

        increment = 1 if increment else -1

        for indices in self._keyword_indices.itervalues():
            for jdx, keyword_index in enumerate(indices):
                if keyword_index >= idx:
                    indices[jdx] += increment


    def copy(self, strip=False):
        """
        Make a copy of the `Header`.

        Parameters
        ----------
        strip : bool, optional
           If True, strip any headers that are specific to one of the standard
           HDU types, so that this header can be used in a different HDU.
        """

        tmp = Header(self.ascard.copy())
        if strip:
            tmp._strip()
        return tmp

    @deprecated(alternative='the ascard attribute')
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
        elif (force == 0) and newkey in self:
            raise ValueError('Intended keyword %s already exists in header.'
                             % newkey)

        idx = self.ascard.index_of(oldkey)
        comment = self.ascard[idx].comment
        value = self.ascard[idx].value
        self.ascard[idx] = create_card(newkey, value, comment)

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

    def get_history(self):
        """
        Get all history cards as a list of string texts.
        """

        return [c for c in self.ascard if c.key == 'HISTORY']

    def get_comment(self):
        """
        Get all comment cards as a list of string texts.
        """

        return [c for c in self.ascard if c.key == 'COMMENT']

    def toTxtFile(self, fileobj, clobber=False):
        """
        Output the header parameters to a file in ASCII format.

        Parameters
        ----------
        fileobj : file path, file object or file-like object
            Output header parameters file.

        clobber : bool
            When `True`, overwrite the output file if it exists.
        """

        close_file = False

        # check if the output file already exists
        if isinstance(fileobj, basestring):
            if (os.path.exists(fileobj) and os.path.getsize(fileobj) != 0):
                if clobber:
                    warnings.warn("Overwriting existing file '%s'." % fileobj)
                    os.remove(fileobj)
                else:
                    raise IOError("File '%s' already exist." % fileobj)

            fileobj = open(fileobj, 'w')
            close_file = True

        lines = []   # lines to go out to the header parameters file

        # Add the card image for each card in the header to the lines list

        for j in range(len(self.ascard)):
            lines.append(str(self.ascard[j]) + '\n')

        # Write the header parameter lines out to the ASCII header
        # parameter file
        fileobj.writelines(lines)

        if close_file:
            fileobj.close()

    def fromTxtFile(self, fileobj, replace=False):
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
        fileobj : file path, file object or file-like object
            Input header parameters file.

        replace : bool, optional
            When `True`, indicates that the entire header should be
            replaced with the contents of the ASCII file instead of
            just updating the current header.
        """

        close_file = False

        if isinstance(fileobj, basestring):
            fileobj = open(fileobj, 'r')
            close_file = True

        lines = fileobj.readlines()

        if close_file:
            fileobj.close()

        if len(self.ascard) > 0 and not replace:
            prevKey = 0
        else:
            if replace:
                self.ascard = CardList([])
            prevKey = 0

        for line in lines:
            card = Card.fromstring(line[:min(80, len(line)-1)])
            card.verify('silentfix')

            if card.key == 'SIMPLE':
                if self.get('EXTENSION'):
                    del self.ascard['EXTENSION']

                self.update(card.key, card.value, card.comment, before=0)
                prevKey = 0
            elif card.key == 'EXTENSION':
                if self.get('SIMPLE'):
                    del self.ascard['SIMPLE']

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

                    if idx == len(self.ascard):
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

                    if idx == len(self.ascard):
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

                    if idx == len(self.ascard):
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

    def _add_commentary(self, key, value, before=None, after=None):
        """
        Add a commentary card.

        If `before` and `after` are `None`, add to the last occurrence
        of cards of the same name (except blank card).  If there is no
        card (or blank card), append at the end.
        """

        new_card = Card(key, value)
        if before is not None or after is not None:
            self.ascard._pos_insert(new_card, before=before, after=after)
        else:
            if key[0] == ' ':
                useblanks = new_card.cardimage != ' '*80
                self.ascard.append(new_card, useblanks=useblanks, bottom=1)
            else:
                try:
                    _last = self.ascard.index_of(key, backward=1)
                    self.ascard.insert(_last+1, new_card)
                except:
                    self.ascard.append(new_card, bottom=1)

        self._modified = True

    def _strip(self):
        """
        Strip cards specific to a certain kind of header.

        Strip cards like ``SIMPLE``, ``BITPIX``, etc. so the rest of
        the header can be used to reconstruct another kind of header.
        """

        # TODO: Previously this only deleted some cards specific to an HDU if
        # _hdutype matched that type.  But it seemed simple enough to just
        # delete all desired cards anyways, and just ignore the KeyErrors if
        # they don't exist.
        # However, it might be desirable to make this extendable somehow--have
        # a way for HDU classes to specify some headers that are specific only
        # to that type, and should be removed otherwise.

        try:
            if 'NAXIS' in self:
                naxis = self['NAXIS']
            else:
                naxis = 0

            if 'TFIELDS' in self:
                tfields = self['TFIELDS']
            else:
                tfields = 0

            for idx in range(naxis):
                del self['NAXIS' + str(idx + 1)]

            for name in ('TFORM', 'TSCAL', 'TZERO', 'TNULL', 'TTYPE',
                         'TUNIT', 'TDISP', 'TDIM', 'THEAP', 'TBCOL'):
                for idx in range(tfields):
                    del self[name + str(idx + 1)]

            for name in ('SIMPLE', 'XTENSION', 'BITPIX', 'NAXIS', 'EXTEND',
                         'PCOUNT', 'GCOUNT', 'GROUPS', 'BSCALE', 'TFIELDS'):
                del self[name]
        except KeyError:
            pass
