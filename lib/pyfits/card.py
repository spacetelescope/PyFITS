import copy
import re
import string
import sys
import warnings

import numpy as np

from pyfits.util import (_str_to_num, _is_int, deprecated, maketrans,
                         translate, _words_group)
from pyfits.verify import _Verify, _ErrList


__all__ = ['Card', 'CardList', 'RecordValuedKeywordCard', 'create_card',
           'create_card_from_string', 'upper_key', 'createCard',
           'createCardFromString', 'upperKey', 'Undefined']


FIX_FP_TABLE = maketrans('de', 'DE')
FIX_FP_TABLE2 = maketrans('dD', 'eE')


class Undefined:
    """Undefined value."""

    def __init__(self):
        # This __init__ is required to be here for Sphinx documentation
        pass
UNDEFINED = Undefined()


class CardList(list):
    # TODO: Add some kind of docstring for this class
    def __init__(self, cards=[], keylist=None):
        """
        Construct the `CardList` object from a list of `Card` objects.

        `CardList` is now merely a thin wrapper around `Header` to provide
        backwards compatibility for the old API.

        Parameters
        ----------
        cards
            A list of `Card` objects.
        """

        warnings.warn(
                'The CardList class has been deprecated; all its former '
                'functionality has been subsumed by the Header class, so '
                'CardList objects should not be directly created.  See the '
                'PyFITS 3.1.0 CHANGELOG for more details.',
                DeprecationWarning)

        # TODO: Rearrange the header and card modules so that this import
        # doesn't have to be here
        from pyfits.header import Header

        # I'm not sure if they keylist argument here was ever really useful;
        # I'm going to just say don't use it.
        if keylist is not None:
            raise ValueError(
                'The keylist argument to CardList() is no longer supported.')

        if isinstance(cards, Header):
            self._header = cards
        else:
            self._header = Header(cards)

        super(CardList, self).__init__(self._header.cards)

    def __contains__(self, key):
        return key in self._header

    def __getitem__(self, key):
        """Get a `Card` by indexing or by the keyword name."""

        idx = self._header._cardindex(key)
        return self._header.cards[idx]

    def __setitem__(self, key, value):
        """Set a `Card` by indexing or by the keyword name."""

        if isinstance(value, tuple) and (1 < len(value) <= 3):
            value = Card(*value)

        if isinstance(value, Card):
            idx = self._header._cardindex(key)
            card = self._header.cards[idx]
            if str(card) != str(value):
                # Replace the existing card at this index by delete/insert
                del self._header[idx]
                self._header.insert(idx, value)
        else:
            raise ValueError('%s is not a Card' % str(value))

    def __delitem__(self, key):
        """Delete a `Card` from the `CardList`."""

        # TODO: This original CardList implementation would raise an exception
        # when a card is not found, which differs from Header; eventually the
        # new Header class should have the behavior of the old CardList class
        if key not in self._header._keyword_indices:
            raise KeyError("Keyword '%s' not found." % key)
        del self._header[key]

    def __getslice__(self, start, end):
        return CardList(self[slice(start, end)])

    def __repr__(self):
        """Format a list of cards into a string."""

        return str(self._header)

    def __str__(self):
        """Format a list of cards into a printable string."""

        return '\n'.join(str(card) for card in self)

    @deprecated(alternative='Header.copy()', pending=False)
    def copy(self):
        """Make a (deep)copy of the `CardList`."""

        return CardList(self._header.copy())

    @deprecated(alternative='Header.keys()', pending=False)
    def keys(self):
        """
        Return a list of all keywords from the `CardList`.
        """

        return self._header.keys()

    @deprecated(alternative='Header.append()', pending=False)
    def append(self, card, useblanks=True, bottom=False):
        """
        Append a `Card` to the `CardList`.

        Parameters
        ----------
        card : `Card` object
            The `Card` to be appended.

        useblanks : bool, optional
            Use any *extra* blank cards?

            If `useblanks` is `True`, and if there are blank cards
            directly before ``END``, it will use this space first,
            instead of appending after these blank cards, so the total
            space will not increase.  When `useblanks` is `False`, the
            card will be appended at the end, even if there are blank
            cards in front of ``END``.

        bottom : bool, optional
           If `False` the card will be appended after the last
           non-commentary card.  If `True` the card will be appended
           after the last non-blank card.
        """

        self._header.append(card, useblanks=useblanks, bottom=bottom)

    @deprecated(alternative='Header.insert()', pending=False)
    def insert(self, idx, card, useblanks=True):
        """
        Insert a `Card` to the `CardList`.

        Parameters
        ----------
        pos : int
            The position (index, keyword name will not be allowed) to
            insert. The new card will be inserted before it.

        card : `Card` object
            The card to be inserted.

        useblanks : bool, optional
            If `useblanks` is `True`, and if there are blank cards
            directly before ``END``, it will use this space first,
            instead of appending after these blank cards, so the total
            space will not increase.  When `useblanks` is `False`, the
            card will be appended at the end, even if there are blank
            cards in front of ``END``.
        """

        self._header.insert(idx, card, useblanks=useblanks)

    @deprecated(alternative='Header.values()', pending=False)
    def values(self):
        """
        Return a list of the values of all cards in the `CardList`.

        For `RecordValuedKeywordCard` objects, the value returned is
        the floating point value, exclusive of the
        ``field_specifier``.
        """

        return self._header.values()

    @deprecated(alternative='Header.index()', pending=False)
    def index_of(self, key, backward=False):
        """
        Get the index of a keyword in the `CardList`.

        Parameters
        ----------
        key : str or int
            The keyword name (a string) or the index (an integer).

        backward : bool, optional
            When `True`, search the index from the ``END``, i.e.,
            backward.

        Returns
        -------
        index : int
            The index of the `Card` with the given keyword.
        """

        # Backward is just ignored now, since the search is not linear anyways

        if _is_int(key) or isinstance(key, basestring):
            return self._header._cardindex(key)
        else:
            raise KeyError('Illegal key data type %s' % type(key))

    def filter_list(self, key):
        """
        Construct a `CardList` that contains references to all of the cards in
        this `CardList` that match the input key value including any special
        filter keys (``*``, ``?``, and ``...``).

        Parameters
        ----------
        key : str
            key value to filter the list with

        Returns
        -------
        cardlist :
            A `CardList` object containing references to all the
            requested cards.
        """

        return CardList(self._header[key])

    # For API backwards-compatibility
    @deprecated(alternative='filter_list', pending=False)
    def filterList(self, key):
        return self.filter_list(key)

    @deprecated(pending=False)
    def count_blanks(self):
        """
        Returns how many blank cards are *directly* before the ``END``
        card.
        """

        return self._header._countblanks()


class Card(_Verify):
    # TODO: This class might still be useful for the Header class
    # internally; consider moving this to pyfits.header and leaving an
    # alias in pyfits.card for backwards-compat

    length = 80

    # String for a FITS standard compliant (FSC) keyword.
    _keywd_FSC_RE = re.compile(r'^[A-Z0-9_-]{0,8}$')

    # A number sub-string, either an integer or a float in fixed or
    # scientific notation.  One for FSC and one for non-FSC (NFSC) format:
    # NFSC allows lower case of DE for exponent, allows space between sign,
    # digits, exponent sign, and exponents
    _digits_FSC = r'(\.\d+|\d+(\.\d*)?)([DE][+-]?\d+)?'
    _digits_NFSC = r'(\.\d+|\d+(\.\d*)?) *([deDE] *[+-]? *\d+)?'
    _numr_FSC = r'[+-]?' + _digits_FSC
    _numr_NFSC = r'[+-]? *' + _digits_NFSC

    # This regex helps delete leading zeros from numbers, otherwise
    # Python might evaluate them as octal values.
    _number_FSC_RE = re.compile(r'(?P<sign>[+-])?0*(?P<digt>%s)'
                                % _digits_FSC)
    _number_NFSC_RE = re.compile(r'(?P<sign>[+-])? *0*(?P<digt>%s)'
                                 % _digits_NFSC)

    # FSC commentary card string which must contain printable ASCII characters.
    _ascii_text = r'[ -~]*$'
    _comment_FSC_RE = re.compile(_ascii_text)

    # Checks for a valid value/comment string.  It returns a match object
    # for a valid value/comment string.
    # The valu group will return a match if a FITS string, boolean,
    # number, or complex value is found, otherwise it will return
    # None, meaning the keyword is undefined.  The comment field will
    # return a match if the comment separator is found, though the
    # comment maybe an empty string.
    _value_FSC_RE = re.compile(
        r'(?P<valu_field> *'
            r'(?P<valu>'

                #  The <strg> regex is not correct for all cases, but
                #  it comes pretty darn close.  It appears to find the
                #  end of a string rather well, but will accept
                #  strings with an odd number of single quotes,
                #  instead of issuing an error.  The FITS standard
                #  appears vague on this issue and only states that a
                #  string should not end with two single quotes,
                #  whereas it should not end with an even number of
                #  quotes to be precise.
                #
                #  Note that a non-greedy match is done for a string,
                #  since a greedy match will find a single-quote after
                #  the comment separator resulting in an incorrect
                #  match.
                r'\'(?P<strg>([ -~]+?|\'\'|)) *?\'(?=$|/| )|'
                r'(?P<bool>[FT])|'
                r'(?P<numr>' + _numr_FSC + r')|'
                r'(?P<cplx>\( *'
                    r'(?P<real>' + _numr_FSC + r') *, *'
                    r'(?P<imag>' + _numr_FSC + r') *\))'
            r')? *)'
        r'(?P<comm_field>'
            r'(?P<sepr>/ *)'
            r'(?P<comm>[!-~][ -~]*)?'
        r')?$')

    _value_NFSC_RE = re.compile(
        r'(?P<valu_field> *'
            r'(?P<valu>'
                r'\'(?P<strg>([ -~]+?|\'\'|)) *?\'(?=$|/| )|'
                r'(?P<bool>[FT])|'
                r'(?P<numr>' + _numr_NFSC + r')|'
                r'(?P<cplx>\( *'
                    r'(?P<real>' + _numr_NFSC + r') *, *'
                    r'(?P<imag>' + _numr_NFSC + r') *\))'
            r')? *)'
        r'(?P<comm_field>'
            r'(?P<sepr>/ *)'
            r'(?P<comm>(.|\n)*)'
        r')?$')

    _commentary_keywords = ['', 'COMMENT', 'HISTORY', 'END']

    def __init__(self, keyword=None, value=None, comment=None):
        # TODO: A Card with a value and comment but no keyword should not be
        # allowed
        self._keyword = None
        self._value = None
        self._comment = None
        self._image = None
        # This attribute is set to False when reading the card image from a
        # to ensure that the contents of the image get verified at some point
        self._parsed = True

        if keyword is not None:
            self.keyword = keyword
        if value is not None:
            self.value = value
        if comment is not None:
            self.comment = comment

        self._modified = False
        self._valuestring = None
        self._valuemodified = False

    def __repr__(self):
        # TODO: Have some useful string representation
        return repr((self.keyword, self.value, self.comment))

    def __str__(self):
        return self.image

    def __len__(self):
        return 3

    def __getitem__(self, index):
        return (self.keyword, self.value, self.comment)[index]

    @property
    def keyword(self):
        """Returns the keyword name parsed from the card image."""
        if self._keyword is not None:
            return self._keyword
        elif self._image:
            self._keyword = self._parsekeyword()
            return self._keyword
        else:
            self.keyword = ''
            return ''

    @keyword.setter
    def keyword(self, keyword):
        """Set the key attribute; once set it cannot be modified."""
        if self._keyword is not None:
            raise AttributeError(
                'Once set, the Card keyword may not be modified')
        elif isinstance(keyword, basestring):
            if len(keyword) <= 8:
                # For keywords with length > 8 they will be HIERARCH cards,
                # and can have arbitrary case keywords
                keyword = keyword.upper()
                if not self._keywd_FSC_RE.match(keyword):
                    raise ValueError('Illegal keyword name: %r.' % keyword)
            else:
                # In prior versions of PyFITS HIERARCH cards would only be
                # created if the user-supplied keyword explicitly started with
                # 'HIERARCH '.  Now we will create them automtically for long
                # keywords, but we still want to support the old behavior too:
                if keyword[:9].upper() == 'HIERARCH ':
                    # The user explicitly asked for a HIERARCH card, so don't
                    # bug them about it...
                    keyword = keyword[9:]
                else:
                    # We'll gladly create a HIERARCH card, but a warning is
                    # also displayed
                    warnings.warn(
                        'Keyword name %r is greater than 8 characters; a '
                        'HIERARCH card will be created.' % keyword)
            self._keyword = keyword
            self._modified = True
        else:
            raise ValueError('Keyword name %r is not a string.' % keyword)
    # For API backwards-compatibility; key should raise a deprecation warning
    # TODO: key should be made to raise a deprecation warning; yeah, keyword is
    # more typing, but it's also more semantically correct here than just 'key'
    key = keyword

    @property
    def value(self):
        if self._value is not None:
            return self._value
        elif self._valuestring is not None:
            self.value = self._valuestring
            return self._valuestring
        elif self._image:
            self._value = self._parsevalue()
            return self._value
        else:
            self.value = ''
            return ''

    @value.setter
    def value(self, value):
        if value is None:
            value = ''
        oldvalue = self._value
        if oldvalue is None:
            oldvalue = ''
        if isinstance(value, (basestring, int, long, float, complex, bool,
                              Undefined, np.floating, np.integer,
                              np.complexfloating)):
            if value != oldvalue:
                self._value = value
                self._modified = True
                self._valuestring = None
                self._valuemodified = True
        else:
            raise ValueError('Illegal value: %r.' % value)

    @value.deleter
    def value(self):
        self.value = ''

    @property
    def comment(self):
        """Get the comment attribute from the card image if not already set."""
        if self._comment is not None:
            return self._comment
        elif self._image:
            self._comment = self._parsecomment()
            return self._comment
        else:
            self.comment = ''
            return ''

    @comment.setter
    def comment(self, comment):
        if comment is None:
            comment = ''
        oldcomment = self._comment
        if oldcomment is None:
            oldcomment = ''
        if comment != oldcomment:
            self._comment = comment
            self._modified = True

    @comment.deleter
    def comment(self):
        self.comment = ''

    @property
    def image(self):
        if self._image and not self._parsed:
            self.verify('silentfix')
        if self._image is None or self._modified:
            self._image = self._formatimage()
        return self._image

    @property
    @deprecated(alternative='the .image attribute')
    def cardimage(self):
        return self.image

    @deprecated(alternative='the .image attribute')
    def ascardimage(self, option='silentfix'):
        if not self._parsed:
            self.verify(option)
        return self.image

    @classmethod
    def fromstring(cls, image):
        """
        Construct a `Card` object from a (raw) string. It will pad the
        string if it is not the length of a card image (80 columns).
        If the card image is longer than 80 columns, assume it
        contains ``CONTINUE`` card(s).
        """

        card = cls()
        card._image = _pad(image)
        card._parsed = False
        return card

    def _parsekeyword(self):
        if self._value is not None and self._comment is not None:
            self._parsed = False
        keyword = self._image[:8].strip()
        keyword_upper = keyword.upper()
        if keyword_upper in self._commentary_keywords:
            if keyword_upper != keyword:
                self._modified = True
            return keyword_upper
        if '=' in self._image:
            keyword = self._image.split('=', 1)[0].strip()
        if len(keyword) > 8:
            if keyword[:8].upper() == 'HIERARCH':
                return keyword[9:].strip()
            else:
                raise ValueError(
                    'Invalid keyword value in card image: %r; cards with '
                    'keywords longer than 8 characters must use the HIERARCH '
                    'keyword.' % self._image)
        else:
            keyword_upper = keyword.upper()
            if keyword_upper != keyword:
                self._modified = True
            return keyword_upper

    def _parsevalue(self):
        """Extract the keyword value from the card image."""

        if self._keyword is not None and self._comment is not None:
            self._parsed = False

        # for commentary cards, no need to parse further
        if self.keyword.upper() in self._commentary_keywords:
            return self._image[8:].rstrip()

        if len(self._image) > self.length:
            values = []
            for card in self._itersubcards():
                value = card.value.rstrip().replace("''", "'")
                if value and value[-1] == '&':
                    value = value[:-1]
                values.append(value)

            value = ''.join(values).rstrip()
            self._valuestring = value
            return value

        m = self._value_NFSC_RE.match(self._split()[1])

        if m is None:
            raise ValueError("Unparsable card (%s), fix it first with "
                             ".verify('fix')." % self.key)

        if m.group('bool') is not None:
            value = m.group('bool') == 'T'
        elif m.group('strg') is not None:
            value = re.sub("''", "'", m.group('strg'))
        elif m.group('numr') is not None:
            #  Check for numbers with leading 0s.
            numr = self._number_NFSC_RE.match(m.group('numr'))
            digt = translate(numr.group('digt'), FIX_FP_TABLE2, ' ')
            if numr.group('sign') is None:
                sign = ''
            else:
                sign = numr.group('sign')
            value = _str_to_num(sign + digt)

        elif m.group('cplx') is not None:
            #  Check for numbers with leading 0s.
            real = self._number_NFSC_RE.match(m.group('real'))
            rdigt = translate(real.group('digt'), FIX_FP_TABLE2, ' ')
            if real.group('sign') is None:
                rsign = ''
            else:
                rsign = real.group('sign')
            value = _str_to_num(rsign + rdigt)
            imag = self._number_NFSC_RE.match(m.group('imag'))
            idigt = translate(imag.group('digt'), FIX_FP_TABLE2, ' ')
            if imag.group('sign') is None:
                isign = ''
            else:
                isign = imag.group('sign')
            value += _str_to_num(isign + idigt) * 1j
        else:
            value = UNDEFINED

        self._valuestring = m.group('valu')
        return value

    def _parsecomment(self):
        """Extract the keyword value from the card image."""

        if self._keyword is not None and self._value is not None:
            self._parsed = False

        # for commentary cards, no need to parse further
        if self.keyword in Card._commentary_keywords:
            return ''

        if len(self._image) > self.length:
            comments = []
            for card in self._itersubcards():
                if card.comment:
                    comments.append(card.comment)
            comment = '/ ' + ' '.join(comments).rstrip()
            m = self._value_NFSC_RE.match(comment)
        else:
            m = self._value_NFSC_RE.match(self._split()[1])

        if m is not None:
            comment = m.group('comm')
            if comment:
                return comment.rstrip()
        return ''

    def _split(self):
        """
        Split the card image between the keyword and the rest of the card.
        """

        if self._image is not None:
            # If we already have a card image, don't try to rebuild a new card
            # image, which self.image would do
            image = self._image
        else:
            image = self.image

        if self.keyword in self._commentary_keywords + ['CONTINUE']:
            keyword, valuecomment = image.split(' ', 1)
        else:
            try:
                delim_index = image.index('=')
            except ValueError:
                delim_index = None

            # The equal sign may not be any higher than column 10; anything
            # past that must be considered part of the card value
            if delim_index is None:
                keyword = image[:8]
                valuecomment = image[8:]
            elif delim_index > 10 and image[:9] != 'HIERARCH ':
                keyword = image[:8]
                valuecomment = image[10:]
            else:
                keyword, valuecomment = image.split('=', 1)
        return keyword.strip(), valuecomment.strip()

    def _fixkeyword(self):
        self._keyword = self._keyword.upper()
        self._modified = True

    def _fixvalue(self):
        """Fix the card image for fixable non-standard compliance."""

        value = None
        keyword, valuecomment = self._split()
        m = self._value_NFSC_RE.match(valuecomment)

        # for the unparsable case
        if m is None:
            try:
                value, comment = valuecomment.split('/', 1)
                self.value = value.strip()
                self.comment = comment.strip()
            except (ValueError, IndexError):
                self.value = valuecomment
            self._valuestring = self._value
            self._valuemodified = False
            return
        # TODO: How much of this is redundant with _parsevalue?
        elif m.group('numr') is not None:
            numr = self._number_NFSC_RE.match(m.group('numr'))
            value = translate(numr.group('digt'), FIX_FP_TABLE, ' ')
            if numr.group('sign') is not None:
                value = numr.group('sign') + value

        elif m.group('cplx') is not None:
            real = self._number_NFSC_RE.match(m.group('real'))
            rdigt = translate(real.group('digt'), FIX_FP_TABLE, ' ')
            if real.group('sign') is not None:
                rdigt = real.group('sign') + rdigt

            imag = self._number_NFSC_RE.match(m.group('imag'))
            idigt = translate(imag.group('digt'), FIX_FP_TABLE, ' ')
            if imag.group('sign') is not None:
                idigt = imag.group('sign') + idigt
            value = '(%s, %s)' % (rdigt, idigt)
        self._valuestring = value
        self._valuemodified = False

    def _formatkeyword(self):
        if self.keyword:
            if len(self.keyword) <= 8:
                return '%-8s' % self.keyword
            else:
                return 'HIERARCH %s ' % self.keyword
        else:
            return ' ' * 8

    def _formatvalue(self):
        # value string
        float_types = (float, np.floating, complex, np.complexfloating)
        value = self.value # Force the value to be parsed out first
        if not self.keyword:
            # Blank cards must have blank values
            value = ''
        elif self.keyword in self._commentary_keywords:
            # The value of a commentary card must be just a raw unprocessed
            # string
            value = str(value)
        elif (self._valuestring and not self._valuemodified and
                isinstance(self.value, float_types)):
            # Keep the existing formatting for float/complex numbers
            value = '%20s' % self._valuestring
        else:
            value = _format_value(value)

        # For HIERARCH cards the value should be shortened to conserve space
        if len(self.keyword) > 8:
            value = value.strip()

        return value

    def _formatcomment(self):
        if not self.comment:
            return ''
        else:
            return ' / %s' % self._comment

    def _formatimage(self):
        keyword = self._formatkeyword()

        value = self._formatvalue()
        is_commentary = keyword.strip() in self._commentary_keywords
        if is_commentary:
            comment = ''
        else:
            comment = self._formatcomment()

        # equal sign string
        delimiter = '= '
        if is_commentary:
            delimiter = ''

        # put all parts together
        output = ''.join([keyword, delimiter, value, comment])

        # For HIERARCH cards we can save a bit of space if necessary by
        # removing the space between the keyword and the equals sign; I'm
        # guessing this is part of the HIEARCH card specification
        keywordvalue_length = len(keyword) + len(delimiter) + len(value)
        if (keywordvalue_length > self.length and
                keyword.startswith('HIERARCH')):
            if (keywordvalue_length == self.length + 1 and keyword[-1] == ' '):
                output = ''.join([keyword[:-1], delimiter, value, comment])
            else:
                # I guess the HIERARCH card spec is incompatible with CONTINUE
                # cards
                raise ValueError('The keyword %s with its value is too long' %
                                 self.keyword)

        if len(output) <= self.length:
            output = '%-80s' % output
        else:
            # longstring case (CONTINUE card)
            # try not to use CONTINUE if the string value can fit in one line.
            # Instead, just truncate the comment
            if (isinstance(self.value, str) and
                len(value) > (self.length - 10)):
                output = self._formatlongimage()
            else:
                warnings.warn('Card is too long, comment is truncated.')
                output = output[:Card.length]
        return output

    def _formatlongimage(self):
        """
        Break up long string value/comment into ``CONTINUE`` cards.
        This is a primitive implementation: it will put the value
        string in one block and the comment string in another.  Also,
        it does not break at the blank space between words.  So it may
        not look pretty.
        """

        value_length = 67
        comment_length = 64
        output = []

        # do the value string
        value_format = "'%-s&'"
        value = self.value.replace("'", "''")
        words = _words_group(value, value_length)
        for idx, word in enumerate(words):
            if idx == 0:
                headstr = '%-8s= ' % self.keyword
            else:
                headstr = 'CONTINUE  '
            value = value_format % word
            output.append('%-80s' % (headstr + value))

        # do the comment string
        comment_format = "%-s"
        if self.comment:
            words = _words_group(self.comment, comment_length)
            for word in words:
                comment = "CONTINUE  '&' / " + comment_format % word
                output.append('%-80s' % comment)

        return ''.join(output)


    def _verify(self, option='warn'):
        errs = _ErrList([])
        fix_text = 'Fixed card to meet the FITS standard: %s' % self.keyword
        # verify the equal sign position
        if (self.keyword not in self._commentary_keywords and
            (self._image and self._image[:8].upper() != 'HIERARCH' and
             self._image.find('=') != 8)):
            errs.append(self.run_option(
                option,
                err_text='Card image is not FITS standard (equal sign not '
                         'at column 8).',
                fix_text=fix_text,
                fix=self._fixvalue))

        # verify the key, it is never fixable
        # always fix silently the case where "=" is before column 9,
        # since there is no way to communicate back to the _keys.
        # TODO: I think this will break for hierarch cards...
        if self._image and self._image[:8].upper() == 'HIERARCH':
            pass
        elif self.keyword != self.keyword.upper():
            # Keyword should be uppercase unless it's a HIERARCH card
            errs.append(self.run_option(
                option,
                err_text='Card keyword is not upper case.',
                fix_text=fix_text,
                fix=self._fixkeyword))
        elif not self._keywd_FSC_RE.match(self.keyword):
            errs.append(self.run_option(
                option,
                err_text='Illegal keyword name %s' % repr(self.keyword),
                fixable=False))

        # verify the value, it may be fixable
        keyword, valuecomment = self._split()
        m = self._value_FSC_RE.match(valuecomment)
        if not (m or self.keyword in self._commentary_keywords):
            errs.append(self.run_option(
                option,
                err_text='Card image is not FITS standard (unparsable value '
                         'string: %s).' % valuecomment,
                fix_text=fix_text,
                fix=self._fixvalue))

        # verify the comment (string), it is never fixable
        m = self._value_NFSC_RE.match(valuecomment)
        if m is not None:
            comment = m.group('comm')
            if comment is not None:
                if not self._comment_FSC_RE.match(comment):
                    errs.append(self.run_option(
                        option,
                        err_text='Unprintable string %r' % comment,
                        fixable=False))

        return errs

    def _itersubcards(self):
        """
        If the card image is greater than 80 characters, it should consist of a
        normal card followed by one or more CONTINUE card.  This method returns
        the subcards that make up this logical card.
        """

        ncards = len(self._image) // Card.length

        for idx in xrange(0, Card.length * ncards, Card.length):
            card = Card.fromstring(self._image[idx:idx + Card.length])
            if idx > 0 and card.keyword.upper() != 'CONTINUE':
                raise ValueError(
                        'Long card images must have CONTINUE cards after '
                        'the first card.')

            if not isinstance(card.value, str):
                raise ValueError('CONTINUE cards must have string values.')

            yield card


# TODO: This is completely broken under the current card implementation (and it
# never seemed quite complete to begin with).  Create some unit tests for RVKCs
# and update this class to work.
class RecordValuedKeywordCard(Card):
    """
    Class to manage record-valued keyword cards as described in the
    FITS WCS Paper IV proposal for representing a more general
    distortion model.

    Record-valued keyword cards are string-valued cards where the
    string is interpreted as a definition giving a record field name,
    and its floating point value.  In a FITS header they have the
    following syntax::

        keyword = 'field-specifier: float'

    where `keyword` is a standard eight-character FITS keyword name,
    `float` is the standard FITS ASCII representation of a floating
    point number, and these are separated by a colon followed by a
    single blank.  The grammar for field-specifier is::

        field-specifier:
            field
            field-specifier.field

        field:
            identifier
            identifier.index

    where `identifier` is a sequence of letters (upper or lower case),
    underscores, and digits of which the first character must not be a
    digit, and `index` is a sequence of digits.  No blank characters
    may occur in the field-specifier.  The `index` is provided
    primarily for defining array elements though it need not be used
    for that purpose.

    Multiple record-valued keywords of the same name but differing
    values may be present in a FITS header.  The field-specifier may
    be viewed as part of the keyword name.

    Some examples follow::

        DP1     = 'NAXIS: 2'
        DP1     = 'AXIS.1: 1'
        DP1     = 'AXIS.2: 2'
        DP1     = 'NAUX: 2'
        DP1     = 'AUX.1.COEFF.0: 0'
        DP1     = 'AUX.1.POWER.0: 1'
        DP1     = 'AUX.1.COEFF.1: 0.00048828125'
        DP1     = 'AUX.1.POWER.1: 1'
    """

    #
    # A group of class level regular expression definitions that allow the
    # extraction of the key, field-specifier, value, and comment from a
    # card string.
    #
    identifier = r'[a-zA-Z_]\w*'
    field = identifier + r'(\.\d+)?'
    field_specifier_s = r'%s(\.%s)*' % (field, field)
    field_specifier_val = r'(?P<keyword>%s): (?P<val>%s\s*)' \
                          % (field_specifier_s, Card._numr_FSC)
    field_specifier_NFSC_val = r'(?P<keyword>%s): (?P<val>%s\s*)' \
                               % (field_specifier_s, Card._numr_NFSC)
    keyword_val = r'\'%s\'' % field_specifier_val
    keyword_NFSC_val = r'\'%s\'' % field_specifier_NFSC_val
    keyword_val_comm = r' +%s *(/ *(?P<comm>[ -~]*))?$' % keyword_val
    keyword_NFSC_val_comm = r' +%s *(/ *(?P<comm>[ -~]*))?$' % keyword_NFSC_val
    #
    # regular expression to extract the field specifier and value from
    # a card image (ex. 'AXIS.1: 2'), the value may not be FITS Standard
    # Compliant
    #
    field_specifier_NFSC_image_RE = re.compile(field_specifier_NFSC_val)
    #
    # regular expression to extract the field specifier and value from
    # a card value; the value may not be FITS Standard Compliant
    # (ex. 'AXIS.1: 2.0e5')
    #
    field_specifier_NFSC_val_RE = re.compile(field_specifier_NFSC_val + r'$')
    #
    # regular expression to extract the key and the field specifier from a
    # string that is being used to index into a card list that contains
    # record value keyword cards (ex. 'DP1.AXIS.1')
    #
    keyword_name_RE = re.compile(r'(?P<key>%s)\.(?P<field_spec>%s)$'
                                 % (identifier, field_specifier_s))
    #
    # regular expression to extract the field specifier and value and comment
    # from the string value of a record value keyword card
    # (ex "'AXIS.1: 1' / a comment")
    #
    keyword_val_comm_RE = re.compile(keyword_val_comm)
    #
    # regular expression to extract the field specifier and value and comment
    # from the string value of a record value keyword card  that is not FITS
    # Standard Complient (ex "'AXIS.1: 1.0d12' / a comment")
    #
    keyword_NFSC_val_comm_RE = re.compile(keyword_NFSC_val_comm)

    def __init__(self, key='', value='', comment=''):
        """
        Parameters
        ----------
        key : str, optional
            The key, either the simple key or one that contains
            a field-specifier

        value : str, optional
            The value, either a simple value or one that contains a
            field-specifier

        comment : str, optional
            The comment
        """

        mo = self.keyword_name_RE.match(key)

        if mo:
            self._field_specifier = mo.group('field_spec')
            key = mo.group('key')
        else:
            if isinstance(value, str):
                if value:
                    mo = self.field_specifier_NFSC_val_RE.match(value)

                    if mo:
                        self._field_specifier = mo.group('keyword')
                        value = mo.group('val')
                        # The value should be a float, though we don't coerce
                        # ints into floats.  Anything else should be a value
                        # error
                        try:
                            value = int(value)
                        except ValueError:
                            try:
                                value = float(value)
                            except ValueError:
                                raise ValueError(
                                    "Record-valued keyword card value must be "
                                    "a floating point or integer value.")
                    else:
                        raise ValueError(
                            "Value %s must be in the form "
                            "field_specifier: value (ex. 'NAXIS: 2')" % value)
            else:
                raise ValueError('value %s is not a string' % value)

        super(RecordValuedKeywordCard, self).__init__(key, value, comment)

    @property
    def field_specifier(self):
       self._extract_value()
       return self._field_specifier

    @property
    def raw(self):
        """
        Return this card as a normal Card object not parsed as a record-valued
        keyword card.  Note that this returns a copy, so that modifications to
        it do not update the original record-valued keyword card.
        """

        key = super(RecordValuedKeywordCard, self).key
        return Card(key, self.strvalue(), self.comment)

    @property
    def key(self):
        key = super(RecordValuedKeywordCard, self).key
        if not hasattr(self, '_field_specifier'):
            return key
        return '%s.%s' % (key, self._field_specifier)

    @key.setter
    def key(self, value):
        Card.key.fset(self, value)

    @property
    def value(self):
        """The RVKC value should always be returned as a float."""

        return float(super(RecordValuedKeywordCard, self).value)

    @value.setter
    def value(self, val):
        if not isinstance(val, float):
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except:
                    raise ValueError('value %s is not a float' % val)
        Card.value.fset(self, val)

    #
    # class method definitins
    #

    @classmethod
    def coerce(cls, card):
        """
        Coerces an input `Card` object to a `RecordValuedKeywordCard`
        object if the value of the card meets the requirements of this
        type of card.

        Parameters
        ----------
        card : `Card` object
            A `Card` object to coerce

        Returns
        -------
        card
            - If the input card is coercible:

                a new `RecordValuedKeywordCard` constructed from the
                `key`, `value`, and `comment` of the input card.

            - If the input card is not coercible:

                the input card
        """

        mo = cls.field_specifier_NFSC_val_RE.match(card.value)
        if mo:
            return cls(card.key, card.value, card.comment)
        else:
            return card

    @classmethod
    def upper_key(cls, key):
        """
        `classmethod` to convert a keyword value that may contain a
        field-specifier to uppercase.  The effect is to raise the
        key to uppercase and leave the field specifier in its original
        case.

        Parameters
        ----------
        key : int or str
            A keyword value that could be an integer, a key, or a
            `key.field-specifier` value

        Returns
        -------
        Integer input
            the original integer key

        String input
            the converted string
        """

        if _is_int(key):
            return key

        mo = cls.keyword_name_RE.match(key)

        if mo:
            return mo.group('key').strip().upper() + '.' + \
                   mo.group('field_spec')
        else:
            return key.strip().upper()
    # For API backwards-compatibility
    upperKey = \
        deprecated(name='upperKey', alternative='upper_key()')(upper_key)

    @classmethod
    def valid_key_value(cls, key, value=0):
        """
        Determine if the input key and value can be used to form a
        valid `RecordValuedKeywordCard` object.  The `key` parameter
        may contain the key only or both the key and field-specifier.
        The `value` may be the value only or the field-specifier and
        the value together.  The `value` parameter is optional, in
        which case the `key` parameter must contain both the key and
        the field specifier.

        Parameters
        ----------
        key : str
            The key to parse

        value : str or float-like, optional
            The value to parse

        Returns
        -------
        valid input : A list containing the key, field-specifier, value

        invalid input : An empty list

        Examples
        --------

        >>> valid_key_value('DP1','AXIS.1: 2')
        >>> valid_key_value('DP1.AXIS.1', 2)
        >>> valid_key_value('DP1.AXIS.1')
        """

        rtnKey = rtnFieldSpec = rtnValue = ''
        myKey = cls.upper_key(key)

        if isinstance(myKey, basestring):
            validKey = cls.keyword_name_RE.match(myKey)

            if validKey:
               try:
                   rtnValue = float(value)
               except ValueError:
                   pass
               else:
                   rtnKey = validKey.group('key')
                   rtnFieldSpec = validKey.group('field_spec')
            else:
                if isinstance(value, str) and \
                Card._keywd_FSC_RE.match(myKey) and len(myKey) < 9:
                    validValue = cls.field_specifier_NFSC_val_RE.match(value)
                    if validValue:
                        rtnFieldSpec = validValue.group('keyword')
                        rtnValue = validValue.group('val')
                        rtnKey = myKey

        if rtnFieldSpec:
            return [rtnKey, rtnFieldSpec, rtnValue]
        else:
            return []
    # For API backwards-compatibility
    validKeyValue = \
        deprecated(name='validKeyValue',
                   alternative='valid_key_value()')(valid_key_value)

    @classmethod
    def create(cls, key='', value='', comment=''):
        """
        Create a card given the input `key`, `value`, and `comment`.
        If the input key and value qualify for a
        `RecordValuedKeywordCard` then that is the object created.
        Otherwise, a standard `Card` object is created.

        Parameters
        ----------
        key : str, optional
            The key

        value : str, optional
            The value

        comment : str, optional
            The comment

        Returns
        -------
        card
            Either a `RecordValuedKeywordCard` or a `Card` object.
        """

        if not cls.valid_key_value(key, value):
            # This should be just a normal card
            cls = Card

        return cls(key, value, comment)
    # For API backwards-compatibility
    createCard = deprecated(name='createCard', alternative='create()')(create)

    @classmethod
    def fromstring(cls, input):
        """
        Create a card given the `input` string.  If the `input` string
        can be parsed into a key and value that qualify for a
        `RecordValuedKeywordCard` then that is the object created.
        Otherwise, a standard `Card` object is created.

        Parameters
        ----------
        input : str
            The string representing the card

        Returns
        -------
        card
            either a `RecordValuedKeywordCard` or a `Card` object
        """

        idx1 = input.find("'") + 1
        idx2 = input.rfind("'")

        if idx2 > idx1 and idx1 >= 0 and \
           cls.valid_key_value('', value=input[idx1:idx2]):
            # This calls Card.fromstring, but with the RecordValuedKeywordClass
            # as the cls argument (causing an RVKC to be created)
            return super(RecordValuedKeywordCard, cls).fromstring(input)
        else:
            # This calls Card.fromstring directly, creating a plain Card
            # object.
            return Card.fromstring(input)

    # For API backwards-compatibility
    createCardFromString = deprecated(name='createCardFromString',
                                      alternative='fromstring()')(fromstring)

    def _update_cardimage(self):
        """
        Generate a (new) card image from the attributes: `key`, `value`,
        `field_specifier`, and `comment`.  Core code for `ascardimage`.
        """

        super(RecordValuedKeywordCard, self)._update_cardimage()
        eqloc = self._cardimage.index('=')
        slashloc = self._cardimage.find('/')

        if hasattr(self, '_value_modified') and self._value_modified:
            # Bypass the automatic coertion to float here, so that values like
            # '2' will still be rendered as '2' instead of '2.0'
            value = super(RecordValuedKeywordCard, self).value
            val_str = _value_to_string(value).strip()
        else:
            val_str = self._valuestring

        val_str = "'%s: %s'" % (self._field_specifier, val_str)
        val_str = '%-20s' % val_str

        output = self._cardimage[:eqloc+2] + val_str

        if slashloc > 0:
            output = output + self._cardimage[slashloc-1:]

        if len(output) <= Card.length:
            output = '%-80s' % output

        self._cardimage = output


    def _extract_value(self):
        """Extract the keyword value from the card image."""

        valu = self._check(option='parse')

        if valu is None:
            raise ValueError(
                "Unparsable card, fix it first with .verify('fix').")

        self._field_specifier = valu.group('keyword')

        if not hasattr(self, '_valuestring'):
            self._valuestring = valu.group('val')
        if not hasattr(self, '_value_modified'):
            self._value_modified = False

        return _str_to_num(translate(valu.group('val'), FIX_FP_TABLE2, ' '))

    def strvalue(self):
        """
        Method to extract the field specifier and value from the card
        image.  This is what is reported to the user when requesting
        the value of the `Card` using either an integer index or the
        card key without any field specifier.
        """

        mo = self.field_specifier_NFSC_image_RE.search(self.cardimage)
        return self.cardimage[mo.start():mo.end()]

    def _fix_value(self, input):
        """Fix the card image for fixable non-standard compliance."""

        _val_str = None

        if input is None:
            tmp = self._get_value_comment_string()

            try:
                slash_loc = tmp.index("/")
            except:
                slash_loc = len(tmp)

            self._err_text = 'Illegal value %s' % tmp[:slash_loc]
            self._fixable = False
            raise ValueError(self._err_text)
        else:
            self._valuestring = translate(input.group('val'), FIX_FP_TABLE,
                                          ' ')
            self._update_cardimage()

    def _format_key(self):
        if hasattr(self, '_key') or hasattr(self, '_cardimage'):
            return '%-8s' % super(RecordValuedKeywordCard, self).key
        else:
            return ' ' * 8

    def _check_key(self, key):
        """
        Verify the keyword to be FITS standard and that it matches the
        standard for record-valued keyword cards.
        """

        if '.' in key:
            keyword, field_specifier = key.split('.', 1)
        else:
            keyword, field_specifier = key, None

        super(RecordValuedKeywordCard, self)._check_key(keyword)

        if field_specifier:
            if not self.field_specifier_s.match(key):
                self._err_text = 'Illegal keyword name %s' % repr(key)
                # TODO: Maybe fix by treating as normal card and not RVKC?
                self._fixable = False
                raise ValueError(self._err_text)


    def _check(self, option='ignore'):
        """Verify the card image with the specified `option`."""

        self._err_text = ''
        self._fix_text = ''
        self._fixable = True

        if option == 'ignore':
            return
        elif option == 'parse':
            return self.keyword_NFSC_val_comm_RE.match(
                    self._get_value_comment_string())
        else:
            # verify the equal sign position
            if self.cardimage.find('=') != 8:
                if option in ['exception', 'warn']:
                    self._err_text = \
                        'Card image is not FITS standard (equal sign not at ' \
                        'column 8).'
                    raise ValueError(self._err_text + '\n%s' % self.cardimage)
                elif option in ['fix', 'silentfix']:
                    result = self._check('parse')
                    self._fix_value(result)

                    if option == 'fix':
                        self._fix_text = \
                           'Fixed card to be FITS standard. : %s' % self.key

            # verify the key
            self._check_key(self.key)

            # verify the value
            result = \
              self.keyword_val_comm_RE.match(self._get_value_comment_string())

            if result is not None:
                return result
            else:
                if option in ['fix', 'silentfix']:
                    result = self._check('parse')
                    self._fix_value(result)

                    if option == 'fix':
                        self._fix_text = \
                              'Fixed card to be FITS standard.: %s' % self.key
                else:
                    self._err_text = \
                        'Card image is not FITS standard (unparsable value ' \
                        'string).'
                    raise ValueError(self._err_text + '\n%s' % self.cardimage)

            # verify the comment (string), it is never fixable
            if result is not None:
                _str = result.group('comm')
                if _str is not None:
                    self._check_text(_str)


# TODO: Put these functions under pending deprecation; fully deprecate their
# camelCase aliases
def create_card(key='', value='', comment=''):
    return RecordValuedKeywordCard.create(key, value, comment)
create_card.__doc__ = RecordValuedKeywordCard.create.__doc__
# For API backwards-compatibility
createCard = deprecated(name='createCard',
                        alternative='create_card()')(create_card)


def create_card_from_string(input):
    return RecordValuedKeywordCard.fromstring(input)
create_card_from_string.__doc__ = RecordValuedKeywordCard.fromstring.__doc__
# For API backwards-compat
createCardFromString = \
        deprecated(name='createCardFromString',
                   alternative='fromstring()')(create_card_from_string)


def upper_key(key):
    return RecordValuedKeywordCard.upper_key(key)
upper_key.__doc__ = RecordValuedKeywordCard.upper_key.__doc__
# For API backwards-compat
upperKey = deprecated(name='upperKey', alternative='upper_key()')(upper_key)


def _format_value(value):
    """
    Converts a card value to its appropriate string representation as
    defined by the FITS format.
    """

    # string value should occupies at least 8 columns, unless it is
    # a null string
    if isinstance(value, str):
        if value == '':
            return "''"
        else:
            exp_val_str = value.replace("'", "''")
            val_str = "'%-8s'" % exp_val_str
            return '%-20s' % val_str

    # must be before int checking since bool is also int
    elif isinstance(value, (bool, np.bool_)):
        return '%20s' % repr(value)[0] # T or F

    elif _is_int(value):
        return '%20d' % value

    # XXX need to consider platform dependence of the format (e.g. E-009 vs. E-09)
    elif isinstance(value, (float, np.floating)):
        return '%20s' % _format_float(value)

    elif isinstance(value, (complex, np.complexfloating)):
        val_str = '(%s, %s)' % (_format_float(value.real),
                                _format_float(value.imag))
        return '%20s' % val_str

    elif isinstance(value, Undefined):
        return ''
    else:
        return ''


def _format_float(value):
    """Format a floating number to make sure it gets the decimal point."""

    value_str = '%.16G' % value
    if '.' not in value_str and 'E' not in value_str:
        value_str += '.0'

    # Limit the value string to at most 20 characters.
    str_len = len(value_str)

    if str_len > 20:
        idx = value_str.find('E')

        if idx < 0:
            value_str = value_str[:20]
        else:
            value_str = value_str[:20-(str_len-idx)] + value_str[idx:]

    return value_str


def _pad(input):
    """Pad blank space to the input string to be multiple of 80."""

    _len = len(input)
    if _len == Card.length:
        return input
    elif _len > Card.length:
        strlen = _len % Card.length
        if strlen == 0:
            return input
        else:
            return input + ' ' * (Card.length-strlen)

    # minimum length is 80
    else:
        strlen = _len % Card.length
        return input + ' ' * (Card.length-strlen)


