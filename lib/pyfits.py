#!/usr/bin/env python2.0
"""
Copyright (C) 2001 Association of Universities for Research in Astronomy (AURA)

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.

    3. The name of AURA and its representatives may not be used to
      endorse or promote products derived from this software without
      specific prior written permission.

THIS SOFTWARE IS PROVIDED BY AURA ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL AURA BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGE.
"""

"""A module for reading and writing FITS files.

                But men at whiles are sober
                  And think by fits and starts.
                And if they think, they fasten
                  Their hands upon their hearts.

                                                Last Poems X, Housman

A module for reading and writing Flexible Image Transport System
(FITS) files.  This file format was endorsed by the International
Astronomical Union in 1999 and mandated by NASA as the standard format
for storing high energy astrophysics data.  For details of the FITS
standard, see the NASA/Science Office of Standards and Technology
publication, NOST 100-2.0.

"""

import re, string, types, os, tempfile, exceptions, copy
import __builtin__, UserList
import numarray as num
import chararray
import recarray as rec

version = '0.6.2 (Feb 12, 2002)'

# Public variables
blockLen = 2880         # the FITS block size
python_mode = {'readonly':'rb', 'update':'rb+', 'append':'ab+'}

# Functions

def padLength(stringLen):
    return (blockLen - stringLen%blockLen) % blockLen

__octalRegex = re.compile(r'([+-]?)0+([1-9][0-9]*)')

def tmpName(input):
    """Create a temporary file name which should not already exist.  Use the
       directory of the input file and the base name of the mktemp() output."""

    dirName = os.path.dirname(input)
    if dirName != '':
        dirName += '/'
    _name = dirName + os.path.basename(tempfile.mktemp())
    if not os.path.exists(_name):
        return _name
    else:
        raise _name, "exists"

def _eval(number):

    """Trap octal and long integers

    Convert a numeric string value (integer or floating point)
    to a Python integer or float converting integers greater than
    32-bits to Python long-integers and octal strings to integers

    """

    try:
        value = eval(number)
    except OverflowError:
        value = eval(number+'L')
    except SyntaxError:
        octal = __octalRegex.match(number)
        if octal:
            value = _eval(string.join(octal.group(1,2),''))
        else:
            raise ValueError, number
    return value

def cardStr(key, value):
    """Returns the specified mandatory keyword card as a string."""

    _comment = {'SIMPLE':'conforms to FITS standard',
                'BITPIX':'array data type',
                'NAXIS':'number of array dimensions',
                'PCOUNT':'number of group parameters',
                'GCOUNT':'number of groups',
                'TFIELDS':'number of table fields'}

    _key = key.upper()
    try:
        comm = _comment[_key]
    except:
        comm = ''

    return str(Card(key, value, comm))


#   A base class for FITS specific exceptions of which there are
#   three: Warning, Severe, and Critical/Fatal.  Warning messages are
#   always caught and their messages printed.  Execution resumes.
#   Severe errors are those which can be fixed-up in many cases, so
#   that execution can continue, whereas Critical Errors are so severe
#   execution can not continue under any situation.


class FITS_FatalError(exceptions.Exception):

    """This level of exception raises an unrecoverable error."""


class FITS_SevereError(FITS_FatalError):

    """This level of exception raises a recoverable error which is likely
    to be fixed, so that processing can continue.

    """


class FITS_Warning(FITS_SevereError):

    """This level of exception raises a warning and allows processing to
    continue.

    """


class Boolean:

    """Boolean type class"""

    def __init__(self, bool):
        self.__bool = bool

    def __cmp__(self, other):
        return cmp(str(self), str(other))

    def __str__(self):
        return self.__bool


TRUE  = Boolean('T')
FALSE = Boolean('F')

class Card:

    """The Card class provides access to individual header cards.

    A FITS Card is an 80 character string containing a key, a value
    (optional) and a comment (optional).  Cards are divided into two
    groups: value and commentary cards.  A value card has '= ' in
    columns 9-10 and does not begin with a commentary key (namely
    'COMMENT ', 'HISTORY ', or '        '), otherwise it is considered
    a commentary card.

    Cards that are read from files are stored in their original format
    as 80 character strings as are any new cards that are created.
    The default format of new cards is fixed format.  Free format
    cards can be created using the 'format=' option.  The key, value,
    and comment parts of the card are accessed and modified by the
    .key, .value, and .comment attributes.  Commentary cards have no
    .comment attribute.

    """

    #  String length of a card
    length = 80
    keyLen = 8
    valLen = 70
    comLen = 72

    #  This regex checks for a valid keyword.  The length of the
    #  keyword string is assumed to be 8.
    __keywd_RE = re.compile(r'[A-Z0-9_-]* *$')

    #  This regex checks for a number sub-string, either an integer
    #  or a float in fixed or scientific notation.
    __numr = r'[+-]?(\.\d+|\d+(\.\d*)?)([DE][+-]?\d+)?'

    #  This regex checks for a valid value/comment string.  The
    #  valu_field group will always return a match for a valid value
    #  field, including a null or empty value.  Therefore, __value_RE
    #  will return a match object for a valid value/comment string.
    #  The valu group will return a match if a FITS string, boolean,
    #  number, or complex value is found, otherwise it will return
    #  None, meaning the keyword is undefined.  The comment field will
    #  return a match if the comment separator is found, though the
    #  comment maybe an empty string.

    __value_RE = re.compile(
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
                r'(?P<numr>'+__numr+')|'
                r'(?P<cplx>\( *'
                    r'(?P<real>'+__numr+') *, *(?P<imag>'+__numr+') *\))'
            r')? *)'
        r'(?P<comm_field>'
            r'(?P<sepr>/ *)'
            r'(?P<comm>[!-~][ -~]*)?'
        r')?$')

    #  This regex checks for a valid commentary card string which must
    #  contain _printable_ ASCII characters.

    __comment_RE = re.compile(r'[ -~]*$')

    #  This regex helps delete leading zeros from numbers, otherwise
    #  Python might evaluate them as octal values.

    __number_RE = re.compile(
        r'(?P<sign>[+-])?0*(?P<digt>(\.\d+|\d+(\.\d*)?)([DE][+-]?\d+)?)')

    #  This regex checks for a valid printf-style formatting sub-string.
    __format = r'%[-+0 #]*\d*(?:\.\d*)?[csdiufEG]'

    #  This regex checks for a valid value/comment format string, the
    #  form of which is expected to be simple, e.g. "%d / %s".  The
    #  use of the '%' character should be used with caution, since it
    #  is used as the escape character as in a printf statement.

    __format_RE= re.compile(
        r'(?:(?P<valfmt> *'+__format+r' *)|'
        r'(?P<cpxfmt> *\('+__format+r' *, *'+__format+r' *\) *))'
        r'(?:(?P<sepfmt>/[ -~]*?)'
        r'(?P<comfmt>'+__format+r'[ -~]*)?)?$')

    #  A list of commentary keywords.  Note that their length is 8.

    __comment_keys = ['        ', 'COMMENT ', 'HISTORY ']

    #  A list of mandatory keywords, whose syntax must be in fixed-
    #  format.

    __mandatory_keys = ['SIMPLE  ', 'EXTEND  ', 'BITPIX  ',
                        'PCOUNT  ', 'GCOUNT  ']

    def __init__(self, key, value=None, comment=None, format=None):
        """Create a new card from key, value, and comment arguments.

        Cards are an 80 character string composed of a key, a value
        indicator (optional unless a value is present), a value
        (optional) and a comment (optional); and come in two flavors:
        value and commentary.

        By default cards are created in fixed-format, but by using the
        'format=' option they can be created in free-format, e.g.
        Card('KEY', value, comment, format='%d / %s').

        Lower-case keys are converted to upper-case.

        """
        cardLen = Card.length
        keyLen  = Card.keyLen
        valLen  = Card.valLen
        comLen  = Card.comLen

        #  Prepare keyword for regex match
        if not isinstance(key, types.StringType):
            raise FITS_SevereError, 'key is not StringType'
        key = string.strip(key)
        if len(key) > keyLen:
            raise FITS_SevereError, 'key length is >%d' % keyLen
        key = "%-*s" % (keyLen, string.upper(key))
        if not Card.__keywd_RE.match(key):
            raise FITS_SevereError, 'key has invalid syntax'

        if isinstance(value, types.StringType) and \
           not self.__comment_RE.match(value):
            raise FITS_SevereError, 'value has unprintable characters'

        if comment:
            if not isinstance(comment, types.StringType):
                raise FITS_SevereError, 'comment is not StringType'
            if not self.__comment_RE.match(comment):
                raise FITS_SevereError, 'comment has unprintable characters'

        #  Create the following card types: comment cards, and free- and
        #  fixed-format value cards.

        #  Create a commentary card
        if key in Card.__comment_keys+['END     ']:
            if comment != None:
                raise FITS_SevereError, 'commentary card has no comment '\
                      'attribute'
            if key == 'END     ' and not isinstance(value, types.NoneType):
                raise FITS_SevereError, 'END card has no value attribute'
            if isinstance(value, types.NoneType):
                card = '%-*s' % (cardLen, key)
            elif isinstance(value, types.StringType):
                if len(value) > comLen:
                    raise FITS_SevereError, 'comment length is >%d' % comLen
                card = '%-*s%-*s' % (keyLen, key, comLen, value)
            else:
                raise FITS_SevereError, 'comment is not StringType'

        #  Create a free-format value card
        elif format:
            if "%-8s"%key in Card.__mandatory_keys+["XTENSION"] or \
               key[:5] == 'NAXIS':
                raise FITS_SevereError, 'mandatory keys are fixed-format only'
            fmt = Card.__format_RE.match(format)
            if not fmt:
                raise FITS_SevereError, 'format has invalid syntax'
            if fmt.group('valfmt'):
                card = ('%-8s= '+ fmt.group('valfmt')) % (key, value)
            elif fmt.group('cpxfmt'):
                card = ('%-8s= '+ fmt.group('cpxfmt')) % (key, value.real,
                                                          value.imag)
            if fmt.group('sepfmt'):
                card += fmt.group('sepfmt')
            if fmt.group('comfmt') and comment:
                card += fmt.group('comfmt') % comment

        #  Create a fixed-format value card
        else:
            if isinstance(value, types.StringType):
                card = '%-8s= %-20s' % (key, self.__formatter(value))
            else:
                card = '%-8s= %20s' % (key, self.__formatter(value))
            if comment:
                card = '%s / %-s' % (card, comment)
        self.__dict__['_Card__card'] = '%-*s' % (cardLen, card[:cardLen])

    def __getattr__(self, attr):
        """Get a card attribute: .key, .value, or .comment.

        Commentary cards ('COMMENT ', 'HISTORY ', '        ') have no
        .comment attribute and attributes of invalid cards may not be
        accessible.

        """

        keyLen = Card.keyLen

        kard = self.__card
        if attr == 'key':
            return string.rstrip(kard[:8])
        elif attr == 'value':
            if kard[:keyLen] not in Card.__comment_keys and \
               kard[keyLen:10] == '= ' :
                #  Value card
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise FITS_SevereError, 'value of old card has '\
                          'invalid syntax'
                elif valu.group('bool') != None:
                    value = Boolean(valu.group('bool'))
                elif valu.group('strg') != None:
                    value = re.sub("''", "'", valu.group('strg'))
                elif valu.group('numr') != None:
                    #  Check for numbers with leading 0s.
                    numr  = Card.__number_RE.match(valu.group('numr'))
                    if numr.group('sign') == None:
                        value = _eval(numr.group('digt'))
                    else:
                        value = _eval(numr.group('sign')+numr.group('digt'))
                elif valu.group('cplx') != None:
                    #  Check for numbers with leading 0s.
                    #  When integers and long integers (literal 'L') are
                    #  unified in Python v2.2, _eval() can be removed and
                    #  replace by eval().
                    real  = Card.__number_RE.match(valu.group('real'))
                    if real.group('sign') == None:
                        value = _eval(real.group('digt'))
                    else:
                        value = _eval(real.group('sign')+real.group('digt'))
                    imag  = Card.__number_RE.match(valu.group('imag'))
                    if imag.group('sign') == None:
                        value += _eval(imag.group('digt'))*1j
                    else:
                        value += _eval(imag.group('sign')+\
                                       imag.group('digt'))*1j
                else:
                    value = None
            else:
                #  Commentary card
                value = kard[keyLen:]
            return value
        elif attr == 'comment':
            #  for value card
            if kard[0:8] not in Card.__comment_keys and kard[8:10] == '= ' :
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise FITS_SevereError, 'comment of old card has '\
                          'invalid syntax'
                comment = valu.group('comm')
            else:
                # !!! Could also raise a exception. !!!
                comment = None
            return comment
        else:
            raise AttributeError, attr

    def __setattr__(self, attr, val):
        """Set a card attribute: .key, .value, or .comment.

        Commentary cards ('COMMENT ', 'HISTORY ', '        ') have no
        .comment attribute and attributes of invalid cards may not be
        accessible.

        """
        keyLen = Card.keyLen
        valLen = Card.valLen

        kard = self.__card
        if kard[:keyLen] == 'END     ':
            raise FITS_SevereError, 'cannot modify END card'
        if attr == 'key':
            #  Check keyword for type, length, and invalid characters
            if not isinstance(val, types.StringType):
                raise FITS_SevereError, 'key is not StringType'
            key = string.strip(val)
            if len(val) > 8:
                raise FITS_SevereError, 'key length is >8'
            val = "%-8s" % string.upper(val)
            if not Card.__keywd_RE.match(val):
                raise FITS_SevereError, 'key has invalid syntax'
            #  Check card and value keywords for compatibility
            if val == 'END     ':
                raise FITS_SevereError, 'cannot set key to END'
            elif not ((kard[:8] in Card.__comment_keys and \
                     val in Card.__comment_keys) or (kard[8:10] == '= ' and \
                     val not in Card.__comment_keys)):
                raise FITS_SevereError, 'old and new card types do not match'
            card = val + kard[8:]
        elif attr == 'value':
            if isinstance(val, types.StringType) and \
               not self.__comment_RE.match(val):
                raise FITS_SevereError, 'value has unprintable characters'
            if kard[0:8] not in Card.__comment_keys and kard[8:10] == '= ' :
                #  This is a value card
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise FITS_SevereError, 'value of old card has '\
                          'invalid syntax'

                #  Check card for fixed- or free-format
                if (valu.group('strg') and valu.start('strg') == 1) \
                    or (not valu.group('strg') and valu.end('valu') == 20):
                    #  This is fixed-format card.
                    if isinstance(val, types.StringType):
                        card = '%-8s= %-20s'%(kard[:8], self.__formatter(val))
                    else:
                        card = '%-8s= %20s'% (kard[:8], self.__formatter(val))

                else:
                    #  This is a free-format card
                    card = '%-8s= %*s' % (kard[:8], valu.end('valu'),
                           self.__formatter(val))

                if valu.group('comm_field'):
                    card = '%-*s%s' % (10+valu.start('sepr'), card,
                                       valu.group('comm_field'))
            else:
                #  Commentary card
                if isinstance(val, types.StringType):
                    if len(val) > valLen:
                        raise FITS_SevereError, 'comment length is >%d'%valLen
                    card = '%-*s%-*s' % (keyLen, kard[:8], valLen, val)
                else:
                    raise FITS_SevereError, 'comment is not StringType'
        elif attr == 'comment':
            if not isinstance(val, types.StringType):
                raise FITS_SevereError, 'comment is not StringType'
            if kard[0:8] not in Card.__comment_keys and kard[8:10] == '= ' :
                #  Then this is value card
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise FITS_SevereError, 'value of old card has '\
                          'invalid syntax'
                if valu.group('comm_field'):
                    card = kard[:10+valu.end('sepr')] + val
                elif valu.end('valu') > 0:
                    card = '%s / %s' % (kard[:10+valu.end('valu')], val)
                else:
                    card = '%s / %s' % (kard[:10], val)
            else:
                #  This is commentary card
                raise AttributeError, 'commentary card has no comment '\
                      'attribute'
        else:
            raise AttributeError, attr
        self.__dict__['_Card__card'] = '%-80s' % card[:80]

    def __str__(self):
        """Return a card as a printable 80 character string."""
        return self.__card

    def fromstring(self, card):
        """Create a card from an 80 character string.

        Verify an 80 character string for valid card syntax in either
        fixed- or free-format.  Create a new card if the syntax is
        valid, otherwise raise an exception.

        """

        if len(card) != 80:
            raise FITS_SevereError, 'card length != 80'
        if not Card.__keywd_RE.match(card[:8]):
            raise FITS_SevereError, 'key has invalid syntax'

        if card[0:8] == 'END     ':
            if not card[8:] == 72*' ':
                raise FITS_SevereError, 'END card has invalid syntax'
        elif card[0:8] not in Card.__comment_keys and card[8:10] == '= ' :
            #  Check for fixed-format of mandatory keywords
            valu = Card.__value_RE.match(card[10:])
            if valu == None:
                raise FITS_SevereError, 'value has invalid syntax'
            elif ((card[:8] in Card.__mandatory_keys or card[:5] == 'NAXIS') \
                 and valu.end('valu') != 20) or \
                 (card[:8] == 'XTENSION' and valu.start('valu') != 0):
                raise FITS_SevereError, 'mandatory keywords are not '\
                      'fixed format'
        else:
            if not Card.__comment_RE.match(card[8:]):
                raise FITS_SevereError, 'commentary card has unprintable '\
                      'characters'

        self.__dict__['_Card__card'] = card
        return self

    def __formatter(self, value):
        """Format a value based on its type

        Strings are delimited by single quotes, contain at least 8
        characters and are left justified, unless it is a null string
        which is just two single quotes.  Single quotes embedded in a
        string are expanded to two single quotes.

        Complex numbers are a pair of real and imaginary values
        delimited by paratheses and separated by a comma.  The
        precision and type of real numbers should be preserved.

        """

        if isinstance(value, Boolean):
            res = "%s" % value
        elif isinstance(value, types.StringType):
            if len(value) > 0:
                res = ("'%-8s'" % re.sub("'", "''", value))
            else:
                res = "''"
        elif isinstance(value, types.IntType) or \
             isinstance(value, types.LongType):
            res = "%d" % value
        elif isinstance(value, types.FloatType):
            res = "%.16G" % value
            if "." not in res and "E" not in res:
                res += ".0"
        elif isinstance(value, types.ComplexType):
            real, imag = "%.16G" % value.real, "%.16G" % value.imag
            if "." not in real and "E" not in real:
                real += ".0"
            if "." not in imag and "E" not in imag:
                imag += ".0"
            res = "(%8s, %8s)" % (real, imag)
        elif value == None:
            res = ""
        else:
            raise TypeError, value
        if len(res) > 70:
            raise FITS_SevereError, 'value length > 70'
        return res


class Header:

    """A FITS header wrapper"""

    def __init__(self, cards=None):
        self.ascard = CardList(cards)

    def __getitem__ (self, key):
        """Get a header keyword value."""

        return self.ascard[key].value

    def __setitem__ (self, key, value):
        """Set a header keyword value."""

        self.ascard[key].value = value
        self._mod = 1

    def ascardlist(self):
        """ Returns a cardlist """

        return self.ascard

    def items(self):
        """Return a list of all keyword-value pairs from the CardList."""

        cards = []
        for card in self.ascard:
            cards.append((card.key, card.value))
        return cards

    def has_key(self, key):
        """Test for a keyword in the CardList."""

        try:
            key = string.upper(string.strip(key))
        except:
            return 0
        for card in self.ascard:
            if card.key == key:
                return 1
        else:
            return 0

    def get(self, key, default=None):
        """Get a keyword value from the CardList.
        If no keyword is found, return the default value.

        """

        key = string.upper(string.strip(key))
        for card in self.ascard:
            if card.key == key:
                return card.value
        else:
            return default

    def update(self, key, value, comment=None, before=None, after=None):
        if self.has_key(key):
            j = self.ascard.index_of(key)
            self[j] = value
            if comment:
                self.ascard[j].comment = comment
        elif before and self.has_key(before):
            self.ascard.insert(self.ascard.index_of(before),
                                Card(key, value, comment))
        elif after and self.has_key(after):
            self.ascard.insert(self.ascard.index_of(after)+1,
                                Card(key, value, comment))
        else:
            self.ascard.append(Card(key, value, comment))

        self._mod = 1


class CardList(UserList.UserList):

    """A FITS card list"""

    def __init__(self, cards=None):
        "Initialize the card list of the header."

        UserList.UserList.__init__(self, cards)

        # find out how many blank cards are *directly* before the END card
        self.count_blanks()

    def __getitem__(self, key):
        """Get a card from the CardList."""

        if type(key) == types.StringType:
            key = self.index_of(key)
        return self.data[key]

    def __setitem__(self, key, value):
        "Set a card in the CardList."

        if isinstance (value, Card):
            _key = self.index_of(key)

            # only set if the value is different from the old one
            if str(self.data[_key]) != str(value):
                self.data[_key] = value
                self.count_blanks()
                self._mod = 1
        else:
            raise SyntaxError, "%s is not a Card" % str(value)

    def __delitem__(self, key):
        """Delete a card from the CardList."""

        _key = self.index_of(key)
        del self.data[_key]
        self.count_blanks()
        self._mod = 1

    def count_blanks(self):
        """Find out how many blank cards are *directly* before the END card."""

        for i in range(1, len(self)):
            if str(self[-i]) != ' '*80:
                self._blanks = i - 1
                break

    def append(self, card, useblanks=1):
        """Append a card to the CardList.

           When useblanks != 0, and if there are blank cards directly before
           END, it will use this space first, instead of appending after these
           blank cards, such that the total space will not increase (default).
           When useblanks == 0, the card will be appended to the end, even
           if there are blank cards in front of END.
        """

        if isinstance (card, Card):
            if (self._blanks > 0) and useblanks:
                _pos = len(self) - self._blanks
                self[_pos] = card   # no need to call count_blanks and set _mod,
                                    # since __setitem__ does it already.
            else:
                self.data.append(card)
                self.count_blanks()
                self._mod = 1
        else:
            raise SyntaxError, "%s is not a Card" % str(card)

    def insert(self, pos, card, useblanks=1):
        """Insert a card to the CardList.

           When useblanks != 0, and if there are blank cards directly before
           END, one blank card will be deleted at the bottom the CardList,
           such that the total space will not increase (default).
           When useblanks == 0, no blank card at the bottom will be deleted.
        """

        if isinstance (card, Card):
            if (self._blanks > 0) and useblanks and pos < len(self):
                self.data.insert(pos,card)
                del self.data[-1]
            else:
                self.data.insert(pos,card)

            self.count_blanks()
            self._mod = 1
        else:
            raise SyntaxError, "%s is not a Card" % str(card)

    def keys(self):
        """Return a list of all keywords from the CardList."""

        keys = []
        for card in self.data:
            keys.append(card.key)
        return keys

    def index_of(self, key):
        """Get the index of a keyword in the CardList.

           The key can be either a string or an integer.
        """

        if type(key) == types.IntType:
            return key
        elif type(key) == types.StringType:
            key = string.upper(string.strip(key))
            for j in range(len(self.data)):
                if self.data[j].key == key:
                    return j
        else:
            raise KeyError, key

    def copy(self):

        # Make a copy of the CardList
        cards = [None]*len(self)
        for i in range(len(self)):
            cards[i]=Card('').fromstring(str(self[i]))

        return CardList(cards)

    def __repr__(self):
        """Format a list of cards into a string"""

        block = ''
        for card in self:
            block = block + str(card)
            if len(block) % Card.length != 0:
                raise CardLen, card
        return block


class ImageBaseHDU:

    """FITS image data

      Attributes:
       header:  image header
       data:  image data

      Class data:
       _file:  file associated with array          (None)
       _data:  starting byte of data block in file (None)

    """

    # mappings between FITS and numarray typecodes
    NumCode = {8:'UInt8', 16:'Int16', 32:'Int32', -32:'Float32', -64:'Float64'}
    ImgCode = {'UInt8':8, 'Int16':16, 'Int32':32, 'Float32':-32, 'Float64':-64}

    def __init__(self, data="delayed", header=None):
        self._file, self._datLoc = None, None
        if header != None:

            # Make a "copy" (not just a view) of the input header, since it
            # may get modified.
            # the data is still a "view" (for now)
            if data != "delayed":
                self.header = Header(header.ascard.copy())

            # if the file is read the first time, no need to copy
            else:
                self.header = header
        else:
            self.header = Header(
                [Card('SIMPLE', TRUE, 'conforms to FITS standard'),
                 Card('BITPIX',         8, 'array data type'),
                 Card('NAXIS',          0, 'number of array dimensions')])

        self.zero = self.header.get('BZERO', 0)
        self.scale = self.header.get('BSCALE', 1)
        self.autoscale = (self.zero != 0) or (self.scale != 1)

        if (data == "delayed"): return

        old_naxis = self.header['NAXIS']

        if isinstance(data, num.NumArray):
            self.header['BITPIX'] = ImageBaseHDU.ImgCode[data.type()]
            axes = list(data.getshape())
            axes.reverse()

        elif type(data) == types.NoneType:
            axes = []
        else:
            raise ValueError, "incorrect array type"

        self.header['NAXIS'] = len(axes)

        # add NAXISi if it does not exist
        for j in range(len(axes)):
            try:
                self.header['NAXIS'+`j+1`] = axes[j]
            except:
                if (j == 0): after = 'naxis'
                else : after = 'naxis'+`j`
                self.header.update('naxis'+`j+1`, axes[j], after = after)

        # delete extra NAXISi's
        for j in range(len(axes)+1, old_naxis+1):
            try:
                del self.header.ascard['NAXIS'+`j`]
            except KeyError:
                pass
        self.data = data

    def __getattr__(self, attr):
        if attr == 'data':
            self.__dict__[attr] = None
            if self.header['NAXIS'] > 0:
                self._file.seek(self._datLoc)
                dims = self.dimShape()

                #  To preserve the type of self.data during autoscaling,
                #  make zero and scale 0-dim numarray arrays.
                code = ImageBaseHDU.NumCode[self.header['BITPIX']]
                self.data = num.fromfile(self._file, type=code, shape=dims)
                if not num.isBigEndian:
                    self.data._byteswap = not(self.data._byteswap)
                if self.autoscale:
                    zero = num.array([self.zero], type=code)
                    scale = num.array([self.scale], type=code)
                    self.data = scale*self.data + zero
        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def dimShape(self):
        naxis = self.header['NAXIS']
        axes = naxis*[0]
        for j in range(naxis):
            axes[j] = self.header['NAXIS'+`j+1`]
        axes.reverse()
        return tuple(axes)

    def size(self):
        size, naxis = 0, self.header['NAXIS']
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size = size*self.header['NAXIS'+`j+1`]
            size = (abs(self.header['BITPIX'])/8)* \
                   self.header.get('GCOUNT', 1)* \
                   (self.header.get('PCOUNT', 0) + size)
        return size

    def summary(self):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]

        # if data is not read yet, use header info
        if 'data' in dir(self):
            if self.data is None:
                shape, format = (), ''
            else:

                # the shape will be in the order of NAXIS's which is the
                # reverse of the numarray shape
                shape = list(self.data.getshape())
                shape.reverse()
                shape = tuple(shape)
                format = self.data.type()
        else:
            shape = ()
            for j in range(self.header['naxis']):
                shape += (self.header['naxis'+`j+1`],)
            format = self.NumCode[self.header['bitpix']]

        return "%-10s  %-11s  %5d  %-12s  %s" % \
               (self.name, type, len(self.header.ascard), shape, format)

    def verify(self):
        req_kw = [
            ('SIMPLE',   "val == TRUE or val == FALSE"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0")]
        for j in range(self.header['NAXIS']):
            req_kw.append(('NAXIS'+`j+1`, "val >= 0"))
        for j in range(len(req_kw)):
            key, val = self.header.ascard[j].key, self.header[j]
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'" % self.header.ascard[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'" % self.header.ascard[j]

class CorruptedHDU:

    """A Corrupted HDU class.

    This class is used when one or more mandatory Cards are corrupted
    (unparsable), such as the 'BITPIX', 'NAXIS', or 'END' card.  A
    corrupted HDU usually means that the size of the data attibute can
    not be calculated or the 'END' card is not found.  In the case of
    a missing 'END' card, the Header may also contain the binary
    data(*).

    (*) In future it may be possible to decipher where the last block
    of the Header ends, but this task may be difficult when the
    extension is a TableHDU containing ASCII data.
    """

    def __init__(self, data=None, header=None):
        self._file, self._offset, self._datLoc = None, None, None
        self.header = header
        self.data = data
        self.name = None

    def size(self):
        self._file.seek(0, 2)
        return self._file.tell() - self._datLoc

    def summary(self, format):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data is not None:
            shape, code = self.data.getshape(), self.data.typecode()
        else:
            shape, code = (), ''
        return format % (self.name, type, len(self.header.ascard), shape, code)

    def verify(self):
        pass


class NonConformingHDU:

    """A Non-Conforming HDU class.

    This class is used when the mandatory Cards are parseable, but
    their values do not conform to any current FITS standard, such as
    the first Card key of the header is neither 'SIMPLE' nor
    'XTENSION', or the value of the 'SIMPLE' Card is FALSE.  The size
    of the data attribute of a non-conforming extension can still be
    calculated, so the HDU still provides access to the data.
    """

    def __init__(self, data=None, header=None):

        self._file, self._offset, self._datLoc = None, None, None
        self.header = header
        self.data = data
        self.name = None

    def size(self):

        size, hdr = 0, self.header
        naxis = hdr['NAXIS']
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size *= hdr['NAXIS%d'%(j+1)]
        return abs(hdr['BITPIX'])/8 * hdr.get('GCOUNT', 1) * \
               (hdr.get('PCOUNT', 0) + size)

    def summary(self, format):

        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data is not None:
            shape, code = self.data.getshape(), self.data.typecode()
        else:
            shape, code = (), ''
        return format % (self.name, type, len(self.header.ascard), shape, code)

    def verify(self):

        isInt   = "isinstance(val, types.IntType)"
        isValid = "val in [8, 16, 32, -32, -64]"
        cards = self.header.ascard
        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards['BITPIX'], 'BITPIX', isInt+" and "+isValid)
        self._verifycard(cards['NAXIS'],  'NAXIS',  isInt+" and val >= 0")
        for j in range(1, self.header['NAXIS']+1):
            self._verifycard(cards['NAXIS%d'%j], 'NAXIS%d'%j,
                             isInt+" and val >= 0")
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                print msg
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            print "header fill contains non-space characters"

    def _verifycard(self, card, keywd, test):

        key, val = card.key, card.value
        if not key == keywd:
            raise IndexError, "'%-8s' card has invalid ordering" % key
        if not eval(test):
            raise ValueError, "'%-8s' card has invalid value" % key


class ConformingHDU:

    """A Conforming HDU class.

    This class is used when no standard (TableHDU, ImageHDU, or
    BinTableHDU) extension is found, but the HDU conforms to the FITS
    standard.  This means that the ConformingHDU class is the base
    class for the TableHDU, ImageHDU, and BinTableHDU classes.
    """

    def __init__(self, data=None, header=None):
        self._file, self._offset, self._datLoc = None, None, None
        self.header = header
        self.data = data
        self.name = header[0]

    def size(self):
        size, hdr = 0, self.header
        naxis = hdr[2]
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size *= hdr[j+3]
        return abs(hdr[1])/8 * hdr['GCOUNT'] * (hdr['PCOUNT'] + size)

    def summary(self, format):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data is not None:
            shape, code = self.data.getshape(), self.data.typecode()
        else:
            shape, code = (), ''
        return format % (self.name, type, len(self.header.ascard), shape, code)

    def verify(self):

        isInt = "isinstance(val, types.IntType)"
        isValid = "val in [8, 16, 32, -32, -64]"
        cards = self.header.ascard

        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards[0], 'XTENSION', "1")
        self._verifycard(cards[1], 'BITPIX',   isInt+" and "+isValid)
        self._verifycard(cards[2], 'NAXIS', isInt+" and val >= 0")
        naxis = self.header[2]
        for j in range(3, naxis+3):
            self._verifycard(cards[j], 'NAXIS%d'%(j-2), isInt+" and val >= 0")
        self._verifycard(cards['PCOUNT'], 'PCOUNT', isInt+" and val >= 0")
        self._verifycard(cards['GCOUNT'], 'GCOUNT', isInt+" and val >= 1")
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(naxis+3, len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                print msg
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            ##warnings.warn("header fill contains non-space characters",
                          ##SyntaxWarning)
            print "header fill contains non-space characters"

    def _verifycard(self, card, keywd, test):
        key, val = card.key, card.value
        if not key == keywd:
            raise IndexError, "'%-8s' card has invalid ordering" % key
        if not eval(test):
            raise ValueError, "'%-8s' card has invalid value" % key



class PrimaryHDU(ImageBaseHDU):

    """FITS Primary Array Header-Data Unit"""

    def __init__(self, data="delayed", header=None):
        ImageBaseHDU.__init__(self, data=data, header=header)
        self.name = 'PRIMARY'

        # insert the keywords EXTEND
        dim = `self.header['NAXIS']`
        if dim == '0': dim = ''
        self.header.update('EXTEND', TRUE, after='NAXIS'+dim)

    def copy(self):
        if self.data:
            Data = self.data[:]
        else:
            Data = None
        return PrimaryHDU(Data, Header(self.header.ascard.copy()))


class ImageHDU(ImageBaseHDU):

    """FITS Image Extension Header-Data Unit"""

    def __init__(self, data="delayed", header=None, name=None):
        ImageBaseHDU.__init__(self, data=data, header=header)

        # change the first card from SIMPLE to XTENSION
        if self.header.ascard[0].key == 'SIMPLE':
            self.header.ascard[0] = Card('XTENSION', 'IMAGE', 'Image extension')

        # insert the require keywords PCOUNT and GCOUNT
        dim = `self.header['NAXIS']`
        if dim == '0': dim = ''
        self.header.update('PCOUNT', 0, after='NAXIS'+dim)
        self.header.update('GCOUNT', 1, after='PCOUNT')

        #  set extension name
        if not name and self.header.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name

    def __setattr__(self, attr, value):
        """Set an Array HDU attribute"""

        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.has_key('EXTNAME'):
                self.header['EXTNAME'] = value
            else:
                self.header.ascard.append(Card('EXTNAME', value, 'extension name'))
        self.__dict__[attr] = value

    def copy(self):
        if self.data is not None:
            Data = self.data[:]
        else:
            Data = None
        return ImageHDU(Data, Header(self.header.ascard.copy()))

    def verify(self):
        req_kw = [
            ('XTENSION', "val[:5] == 'IMAGE'"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0")]
        for j in range(self.header['NAXIS']):
            req_kw.append(('NAXIS'+`j+1`, "val >= 0"))
        req_kw = req_kw + [
            ('PCOUNT',   "val == 0"),
            ('GCOUNT',   "val == 1")]
        for j in range(len(req_kw)):
            key, val = self.header.ascard[j].key, self.header[j]
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'" % self.header.ascard[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'" % self.header.ascard[j]


class GroupsHDU(ImageBaseHDU):

    """FITS Random Groups Header-Data Unit"""

    def __init__(self, data=None, header="delayed", groups=None, name=None):
        ImageBaseHDU.__init__(self, data=data, header=header)

    def size(self):
        size, naxis = 0, self.header['NAXIS']
        if naxis > 0:
            size = self.header['NAXIS1']

            # for random group image, NAXIS1 should be 0 , dimension in each
            # axix is in NAXIS(n-1)
            for j in range(1, naxis):
                size = size*self.header['NAXIS'+`j+1`]
            size = (abs(self.header['BITPIX'])/8) * self.header['GCOUNT'] * \
                   (self.header['PCOUNT'] + size)
        return size

    def copy(self):
        if self.data:
            Data = self.data[:]
        else:
            Data = None
        return GroupsHDU(Data, Header(self.header.ascard.copy()))

    def verify(self):
        hdr = self.header
        req_kw = [
            ('SIMPLE',   "val == TRUE or val == FALSE"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0"),
            ('NAXIS1',   "val == 0")]
        for j in range(1, hdr['NAXIS']+1):
            req_kw.append(('NAXIS'+`j+1`, "val >= 0"))
        req_kw = req_kw + [
            ('GROUPS',   "val == TRUE"),
            ('PCOUNT',   "val >= 0"),
            ('GCOUNT',   "val >= 0")]

        for j in range(len(req_kw)):
            key, val = hdr.ascard[j].key, hdr[j]
            if not key == req_kw[j][0]:
                raise "Required keyword not found:\n'%s'" % hdr.ascard[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'" % hdr.ascard[j]

# Table related code


# lists of column/field definition common names and keyword names, make
# sure to preserve the one-to-one correspondence when updating the list(s).
# Use lists, instead of dictionaries so the names can be displayed in a
# preferred order.
commonNames = ['name', 'format', 'unit', 'null', 'bscale', 'bzero', 'disp', 'start', 'dim']
keyNames = ['TTYPE', 'TFORM', 'TUNIT', 'TNULL', 'TSCAL', 'TZERO', 'TDISP', 'TBCOL', 'TDIM']

# mapping from TFORM data type to Numeric data type, and their sizes in bytes

fits2rec = {'L':'b', 'B':'u', 'I':'s', 'E':'r', 'D':'d', 'J':'i', 'A':'a'}
rec2fits = {'b':'L', 'u':'B', 's':'I', 'r':'E', 'd':'D', 'i':'J', 'a':'A'}

# move the following up once numarray supports complex data types (XXX)

# TFORM regular expression
tformat_re = re.compile(r'(?P<repeat>^[0-9]*)(?P<dtype>[A-Za-z])(?P<option>[!-~]*)')

# table definition keyword regular expression
tdef_re = re.compile(r'(?P<label>^T[A-Z]*)(?P<num>[1-9][0-9 ]*$)')

def parse_tformat(tform):
    """ parse the TFORM value into repeat, data type, and option """

    try:
        (repeat, dtype, option) = tformat_re.match(tform).groups()
    except:
        print 'Format "%s" is not recognized.' % tform

    if repeat == '': repeat = 1
    else: repeat = eval(repeat)

    return (repeat, dtype, option)

def convert_format(input_format, reverse=0):
    """ Convert FITS format spec to record format spec.  Do the opposite
        if reverse is true.
    """
    fmt = input_format
    if fmt != '':
        (repeat, dtype, option) = parse_tformat(fmt)
        if dtype in fits2rec.keys():                            # FITS format
            if reverse: output_format = fmt
            else:       output_format = `repeat`+fits2rec[dtype]
        elif dtype in rec2fits.keys():                          # record format
            if reverse: output_format = `repeat`+rec2fits[dtype]
            else:       output_format = fmt
        else:
            raise ValueError, "Illegal format %s" % fmt
    else:
        output_format = fmt

    return output_format


class Column:

    """ column class, which contains the defintion of the column, e.g.
        ttype, tform, etc. and the array.  Does not support theap yet.
    """

    def __init__(self, name=None, format=None, unit=None, null=None, \
                       bscale=None, bzero=None, disp=None, start=None, \
                       dim=None, array=None):

        # format can not be empty
        if format == None:
            raise ValueError, "Must specify format"

        # any of the input argument (except array) can be a Card or just
        # a number/string
        for cname in commonNames:
            value = eval(cname)           # get the argument's value

            keyword = keyNames[commonNames.index(cname)]
            if isinstance(value, Card):
                setattr(self, cname, value.value)
            else:
                setattr(self, cname, value)

        # column data should be a Numeric array
        if isinstance(array, num.NumArray) or isinstance(array, chararray.CharArray) or array == None:
            self.array = array
        else:
            raise TypeError, "array must be a NumArray or CharArray"


    def __repr__(self):
        text = ''
        for cname in commonNames:
            value = getattr(self, cname)
            if value != None:
                text += cname + ' = ' + `value` + '\n'
        return text[:-1]


class ColDefs:
    """ Defitions of columns.  It has attributes of columns, each attribute
        is a list of values from each column.
    """

    def __init__(self, input):

        # if the input is a list of Columns
        if isinstance(input, types.ListType):
            self._nfields = len(input)
            self._setup()

            # populate the attributes
            for i in range(self._nfields):
                if not isinstance(input[i], Column):
                    raise TypeError, "input to ColDefs must be a list of Columns"
                for cname in commonNames:
                    attr = getattr(self, '_'+cname+'s')
                    val = getattr(input[i], cname)
                    if val != None:
                        attr[i] = getattr(input[i], cname)

                self._formats[i] = convert_format(self._formats[i])
                self._arrays[i] = input[i].array

        # if the input is a table header
        elif isinstance(input, Header):
            self._nfields = input['TFIELDS']
            self._shape = input['NAXIS2']
            self._setup()

            # go through header keywords to pick up table definition keywords
            for _card in input.ascardlist():
                _key = tdef_re.match(_card.key)
                try: keyword = _key.group('label')
                except: continue               # skip if there is no match
                if (keyword in keyNames):
                    col = eval(_key.group('num'))
                    if col <= self._nfields:
                        cname = commonNames[keyNames.index(keyword)]
                        attr = getattr(self, '_'+cname+'s')
                        attr[col-1] = _card.value

            for i in range(self._nfields):
                fmt = self._formats[i]
                if fmt != '':
                    (repeat, dtype, option) = parse_tformat(fmt)
                    if dtype in fits2rec.keys():
                        self._formats[i] = `repeat`+fits2rec[dtype]
                    else:
                        raise ValueError, "Illegal format %s" % dtype

        elif isinstance(input, BinTableHDU):   # extract the column definitions
            tmp = input.data
            self.__dict__ = input._columns.__dict__
        else:
            raise TypeError, "input to ColDefs must be BinTableHDU or a list of Columns"

    def _setup(self):
        """ Initialize all attributes to be a list of null strings."""
        for cname in commonNames:
            setattr(self, '_'+cname+'s', ['']*self._nfields)
        setattr(self, '_arrays', [None]*self._nfields)

    def add_col(self, column):
        """ append one column"""

        self._nfields += 1

        # append the column attributes to the attribute lists
        for cname in commonNames:
            attr = getattr(self, '_'+cname+'s')
            val = getattr(column, cname)
            if cname == 'format':
                val = convert_format(val)
            if val != None:
                attr.append(val)
            else:
                attr.append('')
        self._arrays.append(column.array)

    def del_col(self, col_name):
        """ delete a column """

        indx = rec.index_of(self._names, col_name)

        for cname in commonNames:
            attr = getattr(self, '_'+cname+'s')
            del attr[indx]

        del self._arrays[indx]
        self._nfields -= 1

    def change_attrib(self, col_name, attrib, new_value):
        """ change an attribute (in the commonName list) of a column """

        indx = rec.index_of(self._names, col_name)
        getattr(self, '_'+attrib+'s')[indx] = new_value

    def change_name(self, col_name, new_name):
        self.change_attrib(col_name, 'name', new_name)

    def change_unit(self, col_name, new_unit):
        self.change_attrib(col_name, 'unit', new_unit)

    def info(self, attrib='all'):
        """Get attribute(s) of the column definition.

           the attrib can be one or more of the atrributes listed in
           commonNames.  The default is "all" which will print out
           all attributes.  It forgives plurals and blanks.  If there are
           two or more attribute names, they must be separated by comma(s).
        """

        if attrib.strip().lower() in ['all', '']:
            list = commonNames
        else:
            list = attrib.split(',')
            for i in range(len(list)):
                list[i]=list[i].strip().lower()
                if list[i][-1] == 's':
                    list[i]=list[i][:-1]

        for att in list:
            if att not in commonNames:
                print "'%s' is not an attribute of the column definitions."%att
                continue
            print "%s:" % att
            print '    ', getattr(self, '_'+att+'s')

    #def change_format(self, col_name, new_format):
        #new_format = convert_format(new_format)
        #self.change_attrib(col_name, 'format', new_format)

def get_data(data_source, col_def=None):
    """ Get the table data from data_source, using column definitions in
        col_def.
    """
    #if col_def == None:
        #_data = rec.array(data_source)
    #else:

    # if the column definition is from a Table (header)
    if isinstance(col_def, ColDefs):
        tmp = col_def
        _data = rec.array(data_source, formats=tmp._formats, names=tmp._names, shape=tmp._shape)
        if isinstance(data_source, types.FileType):
            _data._byteswap = not(num.isBigEndian)

        # pass the attributes
        for attr in ['_formats', '_names']:
            setattr(_data, attr, getattr(tmp, attr))
        for i in range(tmp._nfields):
            tmp._arrays[i] = _data.field(i)

    return _data

def new_table (input, header=None, nrows=0, fill=1,tbhdu=None):
    """ Create a new table from the input column definitions.

        Input can be a list of Columns or a ColDefs object.
    """

    hdu = BinTableHDU(header=header)
    if isinstance(input, ColDefs):
        tmp = hdu._columns = input
    else:                 # input is a list of Columns
        tmp = hdu._columns = ColDefs(input)

    # use the largest column shape as the shape of the record
    if nrows == 0:
        for arr in tmp._arrays:
            if arr is not None:
                dim = arr._shape[0]
            else:
                dim = 0
            if dim > nrows:
                nrows = dim

    hdu.data = rec.array(None, formats=tmp._formats, names=tmp._names, shape=nrows)

    # populate data to the new table
    for i in range(tmp._nfields):
        if tmp._arrays[i] is None: size = 0
        else: size = len(tmp._arrays[i])

        n = min(size, nrows)
        if n > 0:
            hdu.data.field(i)[:n] = tmp._arrays[i][:n]
        if fill and n < nrows:
            if isinstance(hdu.data.field(i), num.NumArray):
                hdu.data.field(i)[n:] = 0
            else:
                hdu.data.field(i)[n:] = ''

    hdu.update()
    return hdu

class Table:

    """FITS data table class

    Attributes:
      header:  the header part
      data:  the data part

    Class data:
      _file:  file associated with table          (None)
      _data:  starting byte of data block in file (None)

    """

    def __init__(self, data=None, header=None, name=None, fname=None, loc=None):
        self._file, self._datLoc = fname, loc
        if header != None:
            self.header = Header(header.ascard.copy())
        else:
            self.header = Header(
                [Card('XTENSION', '     ', 'FITS table extension'),
                 Card('BITPIX',         8, 'array data type'),
                 Card('NAXIS',          2, 'number of array dimensions'),
                 Card('NAXIS1',         0, 'length of dimension 1'),
                 Card('NAXIS2',         0, 'length of dimension 2'),
                 Card('PCOUNT',         0, 'number of group parameters'),
                 Card('GCOUNT',         1, 'number of groups'),
                 Card('TFIELDS',        0, 'number of table fields')])

        if isinstance(data, rec.RecArray):
            self.header['NAXIS1'] = data._itemsize
            self.header['NAXIS2'] = data._shape[0]
            self.data = data
        elif type(data) == types.NoneType:
            pass
        else:
            raise TypeError, "incorrect data attribute type"

        #  set extension name
        if not name and self.header.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name
        self.autoscale = 1

    def __getattr__(self, attr):
        if attr == 'data':
            size = self.size()
            if size:
                self._file.seek(self._datLoc)
                data = get_data(self._file, self._columns)
            else:
                data = None
            self.__dict__[attr] = data

        elif attr == '_columns':
            self.__dict__[attr] = ColDefs(self.header)

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def __setattr__(self, attr, value):
        """Set an Array HDU attribute"""

        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.has_key('EXTNAME'):
                self.header['EXTNAME'] = value
            else:
                self.header.ascard.append(Card('EXTNAME', value, 'extension name'))
        self.__dict__[attr] = value

    def shape(self):
        return (self.header['NAXIS2'], self.header['NAXIS1'])

    def size(self):
        size, naxis = 0, self.header['NAXIS']
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size = size*self.header['NAXIS'+`j+1`]
            size = (abs(self.header['BITPIX'])/8) * \
                   self.header.get('GCOUNT', 1) * \
                   (self.header.get('PCOUNT', 0) + size)
        return size

    def summary(self):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data:
            shape, format = self.data.getshape(), self.data._formats
        else:
            shape, format = (), ''
        return "%-10s  %-11s  %5d  %-12s  %s"%\
               (self.name, type, len(self.header.ascard), shape, format)

    # 0.6.2
    def get_coldefs(self):
        return self._columns

    def update(self):
        """ Update header keywords to reflect recent changes of columns"""
        _update = self.header.update
        _cols = self._columns
        _update('naxis1', self.data._itemsize, after='naxis')
        _update('naxis2', self.data._shape[0], after='naxis1')
        _update('tfields', _cols._nfields, after='gcount')

        # Wipe out the old table definition keywords.  Mark them first,
        # then delete from the end so as not to confuse the indexing.
        _list = []
        for i in range(len(self.header.ascard)-1,-1,-1):
            _card = self.header.ascard[i]
            _key = tdef_re.match(_card.key)
            try: keyword = _key.group('label')
            except: continue                # skip if there is no match
            if (keyword in keyNames):
                _list.append(i)
        for i in _list:
            del self.header.ascard[i]
        del _list

        # populate the new table definition keywords
        for i in range(_cols._nfields):
            for cname in commonNames:
                val = getattr(_cols, '_'+cname+'s')[i]
                if val != '':
                    keyword = keyNames[commonNames.index(cname)]+`i+1`
                    if cname == 'format':
                        val = convert_format(val, reverse=1)
                    _update(keyword, val)


class TableHDU(Table):

    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')

    def __init__(self, data=None, header=None, name=None):
        Table.__init__(self, data=data, header=header, name=name)
        if string.rstrip(self.header[0]) != 'TABLE':
            self.header[0] = 'TABLE   '
            self.header.ascard[0].comment = 'ASCII table extension'
        '''
        self.recdCode = ASCIIField.recdCode
        self.fitsCode = ASCIIField.fitsCode
        '''
    '''
    def format(self):
        strfmt, strlen = '', 0
        for j in range(self.header['TFIELDS']):
            bcol = self.header['TBCOL'+`j+1`]
            valu = self.header['TFORM'+`j+1`]
            fmt  = self.__format_RE.match(valu)
            if fmt:
                code, width, prec = fmt.group('code', 'width', 'prec')
            else:
                raise ValueError, valu
            size = eval(width)+1
            strfmt = strfmt + 's'+str(size) + ','
            strlen = strlen + size
        else:
            strfmt = '>' + strfmt[:-1]
        return strfmt
    '''
    def copy(self):
        if self.data:
            Data = self.data.copy()
        else:
            Data = None
        return TableHDU(Data, self.header)

    def verify(self):
        req_kw = [
            ('XTENSION', "string.rstrip(val) == 'TABLE'"),
            ('BITPIX',   "val == 8"),
            ('NAXIS',    "val == 2"),
            ('NAXIS1',   "val >= 0"),
            ('NAXIS2',   "val >= 0"),
            ('PCOUNT',   "val == 0"),
            ('GCOUNT',   "val == 1"),
            ('TFIELDS',  "0 <= val <= 999")]

        for j in range(len(req_kw)):
            key, val = self.header.ascard[j].key, self.header[j]
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'" % self.header.ascard[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'" % self.header[j]


class BinTableHDU(Table):
    '''
    fitsCode = {
        'I8':'B', 'i16':'I', 'i32':'J', \
        'f32':'E', 'f64':'D','F32':'C', 'F64':'M'}
    '''
    fitsComment = {
        's'  :'character array',
        'I8' :'1-byte integer (unsigned)',
        'i16':'2-byte integer (signed)',
        'i32':'4-byte integer (signed)',
        'f32':'real',
        'f64':'double precision'}

    def __init__(self, data=None, header=None, name=None, fname=None, loc=None):
        Table.__init__(self, data=data, header=header, name=name, fname=fname, loc=loc)
        hdr = self.header
        if hdr[0] != 'BINTABLE':
            hdr[0] = 'BINTABLE'
            hdr.ascard[0].comment = 'binary table extension'

        '''
        self.recdCode = BinaryField.recdCode
        self.fitsCode = BinaryField.fitsCode
        '''
    '''

    def fitsType(self, type, count=1):
        if self.fitsCode.has_key(type):
            value = str(count)+BinTableHDU.fitsCode[type]
        elif 's' in type:
            value, type = type[1:]+'A', 's'
        else:
            raise TypeError, type
        return value, self.fitsComment[type]

    def copy(self):
        if self.data:
            Data = self.data.copy()
        else:
            Data = None
        return BinTableHDU(Data, self.header)
    ''' # 0.4.4
    def verify(self):
        req_kw = [
            ('XTENSION', "val == 'BINTABLE'"),
            ('BITPIX',   "val == 8"),
            ('NAXIS',    "val == 2"),
            ('NAXIS1',   "val >= 0"),
            ('NAXIS2',   "val >= 0"),
            ('PCOUNT',   "val >= 0"),
            ('GCOUNT',   "val == 1"),
            ('TFIELDS',  "0 <= val <= 999")]

        for j in range(len(req_kw)):
            key, val = self.header.ascard[j].key, self.header[j]
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'"%self.header.ascard[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'"%self.header.ascard[j]
        # BinaryField.verify()
class _File:
    """A file I/O class"""

    def __init__(self, name, mode='readonly', memmap=0):
        if mode not in python_mode.keys():
            raise "Mode '%s' not recognized" % mode
        self.name = name
        self.mode = mode
        self.memmap = memmap
        if memmap:
            raise "Memory mapping is not implemented yet."
        else:
            self.__file = __builtin__.open(name, python_mode[mode])

    def getfile(self):
        return self.__file

    def __readblock(self):
        block = self.__file.read(blockLen)
        if len(block) == 0:
            raise EOFError
        elif len(block) != blockLen:
            raise IOError, 'Block length is not %d: %d' % (blockLen, len(block))
        cards = []
        for i in range(0, blockLen, Card.length):
            try:
                cards.append(Card('').fromstring(block[i:i+Card.length]))

            # catch bad cards
            except ValueError:
                if Card._Card__keywd_RE.match(string.upper(block[i:i+8])):
                    print "Warning: fixing-up invalid keyword: '%s'"%card[:8]
                    block[i:i+8] = string.upper(block[i:i+8])
                    cards.append(Card('').fromstring(block[i:i+Card.length]))
            if cards[-1].key == 'END':
                break
        return cards

    def readHDU(self):
        """ Read one FITS HDU, data portions are not actually read here, but
            the beginning locations are computed """

        _hdrLoc = self.__file.tell()
        kards = CardList(self.__readblock())
        while not 'END' in kards.keys():
            kards = kards + CardList(self.__readblock())
        else:
            del kards[-1]

        try:
            if kards[0].key == 'SIMPLE':
                if 'GROUPS' in kards.keys() and kards['GROUPS'].value == TRUE:
                    hdu = GroupsHDU(header=Header(kards))
                elif kards[0].value == TRUE:
                    hdu = PrimaryHDU(header=Header(kards))
                else:
                    hdu = NonConformingHDU(header=Header(kards))
            elif kards[0].key == 'XTENSION':
                xtension = string.rstrip(kards[0].value)
                if xtension == 'TABLE':
                    hdu = TableHDU(header=Header(kards))
                elif xtension == 'IMAGE':
                    hdu = ImageHDU(header=Header(kards))
                elif xtension == 'BINTABLE':
                    hdu = BinTableHDU(header=Header(kards), fname=self.__file, loc=self.__file.tell())
                else:
                    hdu = ConformingHDU(header=Header(kards))
            else:
                hdu = NonConformingHDU(header=Header(kards))

            hdu._file = self.__file
            hdu._hdrLoc = _hdrLoc                # beginning of the header area
            hdu._datLoc = self.__file.tell()     # beginning of the data area
            hdu._new = 0
            self.__file.seek(hdu.size()+padLength(hdu.size()), 1)
            hdu.verify()
        except:
            hdu = CorruptedHDU(header=Header(kards))

        return hdu

    def writeHDU(self, hdu):
        """Write *one* FITS HDU.  Must seek to the correct location before
           calling this method."""

        return self.writeHDUheader(hdu), self.writeHDUdata(hdu)

    def writeHDUheader(self, hdu):
        """Write FITS HDU header part."""

        blocks = str(hdu.header.ascard) + str(Card('END'))
        blocks = blocks + padLength(len(blocks))*' '

        if len(blocks)%blockLen != 0:
            raise IOError
        self.__file.flush()
        loc = self.__file.tell()
        self.__file.write(blocks)

        # flush, to make sure the content is written
        self.__file.flush()
        return loc

    def writeHDUdata(self, hdu):
        """Write FITS HDU data part."""

        self.__file.flush()
        loc = self.__file.tell()
        if hdu.data is not None:

            # if image, need to deal with bzero/bscale and byteswap
            if isinstance(hdu, ImageBaseHDU):
                hdu.zero = hdu.header.get('BZERO', 0)
                hdu.scale = hdu.header.get('BSCALE', 1)
                hdu.autoscale = (hdu.zero != 0) or (hdu.scale != 1)
                if hdu.autoscale:
                    code = ImageBaseHDU.NumCode[hdu.header['BITPIX']]
                    zero = num.array([hdu.zero], type=code)
                    scale = num.array([hdu.scale], type=code)
                    hdu.data = (hdu.data - zero) / scale

                if not num.isBigEndian:
                    if hdu.data._byteswap == 0:
                        hdu.data.byteswap()

            # Binary table byteswap
            elif isinstance(hdu, BinTableHDU):
                if not num.isBigEndian:
                    for i in range(hdu.data._nfields):
                        coldata = hdu.data.field(i)
                        if not isinstance(coldata, chararray.CharArray):
                            if coldata._type.bytes > 1:

                                # only swap unswapped
                                if hdu.data._byteswap == 0:
                                    coldata.byteswap()

            block = hdu.data.tostring()
            if len(block) > 0:
                block = block + padLength(len(block))*'\0'
                if len(block)%blockLen != 0:
                    raise IOError
                self.__file.write(block)

        # flush, to make sure the content is written
        self.__file.flush()
        return loc

    def close(self):
        """ close the 'physical' FITS file"""

        if self.__file.closed:
            print "The associated file is already closed."

        self.__file.close()

class HDUList(UserList.UserList):
    """HDU list class"""

    def __init__(self, hdus=None, file=None):
        UserList.UserList.__init__(self)
        self.__file = file
        if hdus == None:
            hdus = []

        # can take one HDU, as well as a list of HDU's as input
        elif not isinstance(hdus, types.ListType):
            hdus = [hdus]
        for hdu in hdus:
            self.data.append(hdu)

    def __getitem__(self, key):
        """Get an HDU from the list, indexed by number or name."""
        key = self.index_of(key)
        return self.data[key]

    def __setitem__(self, key, hdu):
        """Set an HDU to the list, indexed by number of name."""
        key = self.index_of(key)
        self.data[key] = hdu

    def __delitem__(self, key):
        """Delete an HDU from the list, indexed by number or name."""
        key = self.index_of(key)
        del self.data[key]
        self._resize = 1

    def __delslice__(self, i, j):
        """Delete a slice of HDUs from the list, indexed by number only."""
        del self.data[i:j]
        self._resize = 1

    def append(self, hdu):
        """Append a new HDU to the HDUList."""
        #if isinstance(hdu, ImageBaseHDU) or isinstance(hdu, Table):
            #self.data.append(hdu)
            #hdu._new = 1
            #self._resize = 1
        self.data.append(hdu)
        hdu._new = 1
        self._resize = 1
        #else:
            #raise "HDUList can only append an HDU"

    def index_of(self, key):
        """Get the index of an HDU from the FITS object.  The key can be an
           integer, a string, or a tuple of (string, integer) """

        if isinstance(key, types.IntType):
            return key
        elif isinstance(key, types.TupleType):
            _key = key[0]
            _ver = key[1]
        else:
            _key = key
            _ver = None

        if not isinstance(_key, types.StringType):
            raise KeyError, key
        _key = string.upper(string.strip(_key))

        nfound = 0
        for j in range(len(self.data)):
            _name = self.data[j].name
            if isinstance(_name, types.StringType):
                _name = string.upper(string.strip(self.data[j].name))
            if _name == _key:

                # if only specify extname, can only have one extension with
                # that name
                if _ver == None:
                    found = j
                    nfound += 1
                else:

                    # if the keyword EXTVER does not exist, default it to 1
                    _extver = self.data[j].header.get('EXTVER', 1)
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
        """Read all data into memory"""

        for hdu in self:
            if hdu.data is not None:
                continue

    def flush(self, verbose=0):
        """Force a write of the HDUList back to the file (for append and
           update modes only"""

        if self.__file.mode == 'append':
            for hdu in self:
                if (verbose):
                    try: _extver = `hdu.header['extver']`
                    except: _extver = ''

                # only append HDU's which are "new"
                if hdu._new:
                    self.__file.writeHDU(hdu)
                    if (verbose):
                        print "append HDU", hdu.name, _extver
                    hdu._new = 0

        elif self.__file.mode == 'update':
            if not self._resize:

                # determine if any of the HDU is resized
                # only do the header for now (XXX)
                cardsPerBlock = blockLen / Card.length
                for hdu in self:
                    blocks = len(hdu.header.ascard)/cardsPerBlock + 1
                    if (blocks*blockLen) != (hdu._datLoc-hdu._hdrLoc):
                        self._resize = 1
                        break

            # if the HDUList is resized, need to write it to a tmp file,
            # delete the original file, and rename the tmp to the original file
            if self._resize:
                oldName = self.__file.name
                oldMemmap = self.__file.memmap
                _name = tmpName(oldName)
                _hduList = open(_name, mode="append")
                if (verbose): print "open a temp file", _name

                for hdu in self:
                    (hdu._hdrLoc, hdu._datLoc) = _hduList.__file.writeHDU(hdu)
                _hduList.__file.close()
                self.__file.close()
                os.remove(self.__file.name)
                if (verbose): print "delete the original file", oldName

                # reopen the renamed new file with "update" mode
                os.rename(_name, oldName)
                ffo = _File(oldName, mode="update", memmap=oldMemmap)
                self.__file = ffo
                if (verbose): print "reopen the newly renamed file", oldName

                # reset the resize attributes after updating
                self._resize = 0
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
                    if hdu.header._mod or hdu.header.ascard._mod:
                        hdu._file.seek(hdu._hdrLoc)
                        self.__file.writeHDUheader(hdu)
                        if (verbose):
                            print "update header in place: Name =", hdu.name, _extver
                    if 'data' in dir(hdu):
                        if hdu.data is not None:
                            hdu._file.seek(hdu._datLoc)
                            self.__file.writeHDUdata(hdu)
                            if (verbose):
                                print "update data in place: Name =", hdu.name, _extver

                # reset the modification attributes after updating
                for hdu in self:
                    hdu.header._mod = 0
                    hdu.header.ascard._mod = 0

        else:
            print "flush for '%s' mode is not defined." % self.__file.mode

    def update_extend(self):
        """Make sure if the primary header needs the keyword EXTEND or it has
           the proper value"""

        hdr = self[0].header
        if hdr.has_key('extend'):
            if (hdr['extend'] == FALSE):
                hdr['extend'] = TRUE
        else:
            if hdr['naxis'] == 0:
                hdr.update('extend', TRUE, after='naxis')
            else:
                n = hdr['naxis']
                hdr.update('extend', TRUE, after='naxis'+`n`)

    def writeto(self, name):
        """Write the HDUList to a new file."""

        if (len(self) == 0):
            print "There is nothing to write."
            return

        # the output file must not already exist
        if os.path.exists(name):
            raise IOError, "File '%s' already exist." % name
        else:

            # make sure the EXTEND keyword is there if there is extension
            if len(self) > 1:
                self.update_extend()

            hduList = open(name, mode="append")
            for hdu in self:
                hduList.__file.writeHDU(hdu)
            hduList.close()

    def close(self, verbose=0):
        """ close the associated FITS file, this simply calls the close method
            of the _File class.  It has this two-tier calls because _File
            has ts own private attribute __file."""

        if self.__file == None:
            print "No file associated with this HDUList."
        else:
            if self.__file.mode in ['append', 'update']:
                self.flush(verbose)
            self.__file.close()

    def info(self):
        """Summarize the HDU info in the list"""

        if self.__file is None:
            _name = '(No file associated with this HDUList)'
        else:
            _name = self.__file.name
        results = "Filename: %s\nNo.    Name         Type"\
                  "      Cards   NAXIS        Format\n" % _name

        for j in range(len(self)):
            if 'data' in dir(self[j]):
                results = results + "%-3d  %s\n"%(j, self.data[j].summary())
            else:
                results = results + "%-3d  %s\n"%(j, self.data[j].summary())
        results = results[:-1]
        print results


def open(name, mode="readonly", memmap=0):
    """Factory function to open a FITS file and return an HDUList instance"""

    # instanciate a FITS file object (ffo)
    ffo = _File(name, mode=mode, memmap=memmap)
    hduList = HDUList(file=ffo)

    # read all HDU's
    while 1:
        try:
            hduList.append(ffo.readHDU())
        except EOFError:
            break

    # initialize/reset attributes to be used in "update/append" mode
    # CardList needs its own _mod attribute since it has methods to change
    # the content of header without being able to pass it to the header object
    hduList._resize = 0
    for hdu in hduList:
        hdu.header._mod = 0
        hdu.header.ascard._mod = 0
        hdu._new = 0

    return hduList
