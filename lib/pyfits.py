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

A module for reading and writing Flexible Image Transport System
(FITS) files.  This file format was endorsed by the International
Astronomical Union in 1999 and mandated by NASA as the standard format
for storing high energy astrophysics data.  For details of the FITS
standard, see the NASA/Science Office of Standards and Technology
publication, NOST 100-2.0.

                But men at whiles are sober
                  And think by fits and starts.
                And if they think, they fasten
                  Their hands upon their hearts.

                                                Last Poems X, Housman

"""

import re, string, types, os, tempfile, exceptions, copy
import __builtin__, sys, UserList
import numarray as num
import chararray
import recarray as rec

__version__ = '0.7.2 (June 19, 2002)'

# Module variables
blockLen = 2880         # the FITS block size
python_mode = {'readonly':'rb', 'update':'rb+', 'append':'ab+'}  # open modes

TAB = "   "
DELAYED = "delayed"     # used for lazy instanciation of data
isInt = "isinstance(val, types.IntType)"

__octalRegex = re.compile(r'([+-]?)0+([1-9][0-9]*)')

# Functions

def padLength(stringLen):
    return (blockLen - stringLen%blockLen) % blockLen

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


class VerifyError(exceptions.Exception):
    """Verify exception class."""
    pass


class ErrList(UserList.UserList):
    """Verification error list."""

    def __init__(self, val, unit="Element"):
        UserList.UserList.__init__(self, val)
        self.unit = unit

    def __str__(self, tab=0):
        """Print out nested structure with corresponding indentations.

           A tricky use of __str__, since normally __str__ has only one
           argument
        """
        result = ""
        element = 0

        # go through the list twice, first time print out all top level messages
        for item in self.data:
            if not isinstance(item, ErrList):
                result += TAB*tab+"%s\n" % item

        # second time go through the next level items, each of the next level
        # must present, even it has nothing.
        for item in self.data:
            if isinstance(item, ErrList):
                _dummy = item.__str__(tab=tab+1)

                # print out a message only if there is something
                if _dummy.strip():
                    if self.unit:
                        result += TAB*tab+"%s %s:\n" % (self.unit, element)
                    result += _dummy
                element += 1

        return result


class _Verify:
    """Shared methods for verification."""

    def run_option(self, option="warn", err_text="", fix_text="Fixed.", fix = "pass", fixable=1):
        """Execute the verification with selected option."""

        _text = err_text
        if not fixable:
            option = 'unfixable'
        if option in ['warn', 'exception']:
            #raise VerifyError, _text
        #elif option == 'warn':
            pass

        # fix the value
        elif option == 'unfixable':
            _text = "Unfixable error: %s" % _text
        else:
            exec(fix)
            #if option != 'silentfix':
            _text += '  ' + fix_text
        return _text

    def verify (self, option='warn'):
        """Wrapper for _verify."""

        _option = option.lower()
        if _option not in ['fix', 'silentfix', 'ignore', 'warn', 'exception']:
            raise ValueError, 'Option %s not recognized.' % option

        if (_option == "ignore"):
            return

        x = str(self._verify(_option)).rstrip()
        self._verifytext = x
        if _option in ['fix', 'silentfix'] and string.find(x, 'Unfixable') != -1:
            raise VerifyError, '\n'+x
        if (_option != "silentfix") and x:
            print 'Output verification result:'
            print x
        if _option == 'exception' and x:
            raise VerifyError


class Boolean:
    """Boolean type class"""

    def __init__(self, bool):
        self.__bool = bool

    def __cmp__(self, other):
        return cmp(str(self), str(other))

    def __str__(self):
        return self.__bool

    def __repr__(self):
        repr_dict = {'T':'TRUE', 'F':'FALSE'}
        return repr_dict[self.__bool]

# Must be after the class is defined
TRUE  = Boolean('T')
FALSE = Boolean('F')


class Card(_Verify):

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
        comLen  = 72

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
            return string.rstrip(kard[:keyLen])
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
            if kard[:keyLen] not in Card.__comment_keys and kard[keyLen:10] == '= ' :
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise FITS_SevereError, 'comment of old card has '\
                          'invalid syntax'
                comment = valu.group('comm').rstrip()
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
        valLen = 70

        kard = self.__card
        if kard[:keyLen] == 'END     ':
            raise FITS_SevereError, 'cannot modify END card'
        if attr == 'key':

            #  Check keyword for type, length, and invalid characters
            if not isinstance(val, types.StringType):
                raise FITS_SevereError, 'key is not StringType'
            key = string.strip(val)
            if len(val) > keyLen:
                raise FITS_SevereError, 'key length > %d' % keyLen
            val = "%-8s" % string.upper(val)

            #  Check card and value keywords for compatibility
            if val == 'END     ':
                raise FITS_SevereError, 'cannot set key to END'
            elif not ((kard[:keyLen] in Card.__comment_keys and \
                   val in Card.__comment_keys) or (kard[keyLen:10] == '= ' and \
                   val not in Card.__comment_keys)):
                raise FITS_SevereError, 'old and new card types do not match'
            card = val + kard[keyLen:]
        elif attr == 'value':
            if isinstance(val, types.StringType) and \
               not self.__comment_RE.match(val):
                raise FITS_SevereError, 'value has unprintable characters'
            if kard[:keyLen] not in Card.__comment_keys and kard[keyLen:10] == '= ' :
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
                        raise FITS_SevereError, 'comment length > %d' % valLen
                    card = '%-*s%-*s' % (keyLen, kard[:keyLen], valLen, val)
                else:
                    raise FITS_SevereError, 'comment is not StringType'
        elif attr == 'comment':
            if not isinstance(val, types.StringType):
                raise FITS_SevereError, 'comment is not StringType'
            if kard[:keyLen] not in Card.__comment_keys and kard[keyLen:10] == '= ' :

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
            raise FITS_SevereError, 'key has invalid syntax, card is:\n%s' % card

        if card[0:8] == 'END     ':
            if not card[8:] == 72*' ':
                raise FITS_SevereError, 'END card has invalid syntax'
        elif card[0:8] not in Card.__comment_keys and card[8:10] == '= ' :
            #  Check for fixed-format of mandatory keywords
            valu = Card.__value_RE.match(card[10:])
            if valu == None:
                raise FITS_SevereError, 'value has invalid syntax, card is:\n%s' % card
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

    def _verify(self, option='warn'):
        """Card class verification method."""
        _err = ErrList([])
        if self.key:

            # this is just for testing
            if not Card.__keywd_RE.match(self.key):
                err_text = "Illegal keyword '%s'" % self.key
                _err.append(self.run_option(option, err_text=err_text, fixable=0))
        return _err

class Header(_Verify):
    """A FITS header wrapper"""

    def __init__(self, cards=None):

        # decide which kind of header it belongs to
        try:
            if cards[0].key == 'SIMPLE':
                if 'GROUPS' in cards.keys() and cards['GROUPS'].value == TRUE:
                    self._hdutype = GroupsHDU
                elif cards[0].value == TRUE:
                    self._hdutype = PrimaryHDU
                else:
                    self._hdutype = ValidHDU
            elif cards[0].key == 'XTENSION':
                xtension = string.rstrip(cards[0].value)
                if xtension == 'TABLE':
                    self._hdutype = TableHDU
                elif xtension == 'IMAGE':
                    self._hdutype = ImageHDU
                elif xtension == 'BINTABLE':
                    self._hdutype = BinTableHDU
                else:
                    self._hdutype = ExtensionHDU
            else:
                self._hdutype = ValidHDU
        except:
            self._hdutype = CorruptedHDU

        # populate the cardlist
        self.ascard = CardList(cards)

    def __getitem__ (self, key):
        """Get a header keyword value."""

        return self.ascard[key].value

    def __setitem__ (self, key, value):
        """Set a header keyword value."""

        self.ascard[key].value = value
        self._mod = 1

    def __delitem__(self, key):
        """Delete card(s) with the name 'key'."""

        # delete ALL cards with the same keyword name
        if isinstance(key, types.StringType):
            while 1:
                try:
                    del self.ascard[key]
                    self._mod = 1
                except:
                    return

        # for integer key only delete once
        else:
            del self.ascard[key]
            self._mod = 1

    def ascardlist(self):
        """ Returns a cardlist """

        return self.ascard

    def items(self):
        """Return a list of all keyword-value pairs from the CardList."""

        pairs = []
        for card in self.ascard:
            pairs.append((card.key, card.value))
        return pairs

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

    def add_history(self, value, before=None, after=None):
        """Add history card."""
        self._add_commentary('history', value, before=before, after=after)

    def add_comment(self, value, before=None, after=None):
        """Add comment card."""
        self._add_commentary('comment', value, before=before, after=after)

    def add_blank(self, value, before=None, after=None):
        """Add blank card."""
        self._add_commentary(' ', value, before=before, after=after)

    def _add_commentary(self, key, value, before=None, after=None):
        """Add commentary card.

           If before and after are None, add to the last occurrence of
           cards of the same name (except blank card).  If there is no card
           (or blank card), append at the end.
        """

        new_card = Card(key, value)
        if before and self.has_key(before):
            self.ascard.insert(self.ascard.index_of(before), new_card)
        elif after and self.has_key(after):
            self.ascard.insert(self.ascard.index_of(after)+1, new_card)
        else:
            _last = None
            if key[0] != ' ':
                _last = self.ascard.index_of(key, backward=1)
            if _last is not None:
                self.ascard.insert(_last+1, new_card)
            else:
                self.ascard.append(new_card)

        self._mod = 1

    def copy(self):
        """Make a copy of the header."""
        tmp = Header(self.ascard.copy())

        # also copy the class
        tmp._hdutype = self._hdutype
        return tmp

    def _strip(self):
        """Strip cards specific to a certain kind of header.

           Strip cards like SIMPLE, BITPIX, etc. so the rest of the header
           can be used to reconstruct another kind of header.
        """
        try:

            # have both SIMPLE and XTENSION to accomodate Extension
            # and Corrupted cases
            del self['SIMPLE']
            del self['XTENSION']
            del self['BITPIX']

            _naxis = self['NAXIS']
            if self._hdutype in [TableHDU, BinTableHDU]:
                _naxis1 = self['NAXIS1']

            del self['NAXIS']
            for i in range(_naxis):
                del self['NAXIS'+`i+1`]

            if self._hdutype == PrimaryHDU:
                del self['EXTEND']
            else:
                del self['PCOUNT']
                del self['GCOUNT']

            if self._hdutype in [PrimaryHDU, GroupsHDU]:
                del self['GROUPS']

            if self._hdutype in [TableHDU, BinTableHDU]:
                del self['TFIELDS']
                for name in ['TFORM', 'TSCAL', 'TZERO', 'TNULL', 'TTYPE', 'TUNIT']:
                    for i in range(_naxis1):
                        del self[name+`i+1`]

            if self._hdutype == BinTableHDU:
                for name in ['TDISP', 'TDIM', 'THEAP']:
                    for i in range(_naxis1):
                        del self[name+`i+1`]

            if self._hdutype == TableHDU:
                for i in range(_naxis1):
                    del self['TBCOL'+`i+1`]

        except:
            pass


class CardList(UserList.UserList):
    """A FITS card list"""

    def __init__(self, cards=None):
        "Initialize the card list of the header."

        UserList.UserList.__init__(self, cards)

        # find out how many blank cards are *directly* before the END card
        self.count_blanks()

    def __getitem__(self, key):
        """Get a card from the CardList."""

        _key = self.index_of(key)
        return self.data[_key]

    def __setitem__(self, key, value):
        """Set a card in the CardList."""

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
           When useblanks == 0, the card will be appended at the end, even
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

    def index_of(self, key, backward=0):
        """Get the index of a keyword in the CardList.

           The key can be either a string or an integer.
           If backward = 1, search from the end.
        """

        if type(key) in (types.IntType, types.LongType):
            return key
        elif type(key) == types.StringType:
            _key = key.strip().upper()
            _search = range(len(self.data))
            if backward:
                _search.reverse()
            for j in _search:
                if self.data[j].key == _key:
                    return j
            raise KeyError, 'Keyword %s not found.' % `key`
        else:
            raise KeyError, 'Illegal key data type %s' % type(key)

    def copy(self):
        """Make a copy of the CardList."""

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


# ----------------------------- HDU classes ------------------------------------

class AllHDU:
    pass

class CorruptedHDU(AllHDU):
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

    def _summary(self):
        return "%-10s  %-11s" % (self.name, "CorruptedHDU")

    def verify(self):
        pass


class ValidHDU(AllHDU, _Verify):
    """Base class for all HDUs which are not corrupted."""

    # 0.6.5.5
    def size(self):
        """Size of the data part."""
        size = 0
        naxis = self.header.get('NAXIS', 0)
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size = size * self.header['NAXIS'+`j+1`]
            bitpix = self.header['BITPIX']
            gcount = self.header.get('GCOUNT', 1)
            pcount = self.header.get('PCOUNT', 0)
            size = abs(bitpix) * gcount * (pcount + size) / 8
        return size

    def copy(self):
        """Make a copy of the HDU, both header and data are copied."""
        if self.data is not None:
            _data = self.data.copy()
        else:
            _data = None
        return self.__class__(data=_data, header=self.header.copy())

    def _verify(self, option='warn'):
        _err = ErrList([], unit='Card')

        isValid = "val in [8, 16, 32, -32, -64]"

        # Verify location and value of mandatory keywords.
        # Do the first card here, instead of in the respective HDU classes,
        # so the checking is in order, in case of required cards in wrong order.
        if isinstance(self, ExtensionHDU):
            firstkey = 'XTENSION'
            firstval = self._xtn
        else:
            firstkey = 'SIMPLE'
            firstval = TRUE
        self.req_cards(firstkey, '== 0', '', firstval, option, _err)
        self.req_cards('BITPIX', '== 1', isInt+" and "+isValid, 8, option, _err)
        self.req_cards('NAXIS', '== 2', isInt+" and val >= 0 and val <= 999", 0, option, _err)

        naxis = self.header.get('NAXIS', 0)
        if naxis < 1000:
            for j in range(3, naxis+3):
                self.req_cards('NAXIS'+`j-2`, '== '+`j`, isInt+" and val>= 0", 1, option, _err)
        # verify each card
        for _card in self.header.ascard:
            _err.append(_card._verify(option))

        return _err

    def req_cards(self, keywd, pos, test, fix_value, option, errlist):
        """Check the existence, location, and value of a required card.

           If pos = None, it can be anywhere.  If the card does not exist,
           the new card will have the fix_value as its value when created.
           Also check the card's value by using the "test" argument.
        """

        _err = errlist
        fix = ''
        cards = self.header.ascard
        try:
            _index = cards.index_of(keywd)
        except:
            _index = None
        fixable = fix_value is not None

        # if pos is a string, it must be of the syntax of "> n",
        # where n is an int
        if isinstance(pos, types.StringType):
            _parse = pos.split()
            if _parse[0] in ['>=', '==']:
                insert_pos = eval(_parse[1])

        # if the card does not exist
        if _index is None:
            err_text = "'%s' card does not exist." % keywd
            fix_text = "Fixed by inserting a new '%s' card." % keywd
            if fixable:

                # use repr to accomodate both string and non-string types
                # Boolean is also OK (with its __repr__ method)
                _card = "Card('%s', %s)" % (keywd, `fix_value`)
                fix = "self.header.ascard.insert(%d, %s)" % (insert_pos, _card)
            _err.append(self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix, fixable=fixable))
        else:

            # if the supposed location is specified
            if pos is not None:
                test_pos = '_index '+ pos
                if not eval(test_pos):
                    err_text = "'%s' card at the wrong place (card %d)." % (keywd, _index)
                    fix_text = "Fixed by moving it to the right place (card %d)." % insert_pos
                    fix = "_cards=self.header.ascard; dummy=_cards[%d]; del _cards[%d];_cards.insert(%d, dummy)" % (_index, _index, insert_pos)
                    _err.append(self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix))

            # if value checking is specified
            if test:
                val = self.header[keywd]
                if not eval(test):
                    err_text = "'%s' card has invalid value '%s'." % (keywd, val)
                    fix_text = "Fixed by setting a new value '%s'." % fix_value
                    if fixable:
                        fix = "self.header['%s'] = %s" % (keywd, `fix_value`)
                    _err.append(self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix, fixable=fixable))

        return _err


class ExtensionHDU(ValidHDU):
    """An extension HDU class.

    This class is the base class for the TableHDU, ImageHDU, and
    BinTableHDU classes.
    """

    def __init__(self, data=None, header=None):
        self._file, self._offset, self._datLoc = None, None, None
        self.header = header
        self.data = data
        self._xtn = ' '

    def __setattr__(self, attr, value):
        """Set an HDU attribute."""

        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.has_key('EXTNAME'):
                self.header['EXTNAME'] = value
            else:
                self.header.ascard.append(Card('EXTNAME', value, 'extension name'))

        self.__dict__[attr] = value

    def _verify(self, option='warn'):
        _err = ValidHDU._verify(self, option=option)

        # Verify location and value of mandatory keywords.
        naxis = self.header.get('NAXIS', 0)
        self.req_cards('PCOUNT', '== '+`naxis+3`, isInt+" and val >= 0", 0, option, _err)
        self.req_cards('GCOUNT', '== '+`naxis+4`, isInt+" and val == 1", 1, option, _err)
        return _err


class ImageBaseHDU(ValidHDU):
    """FITS image data

      Attributes:
       header:  image header
       data:  image data
       _file:  file associated with array          (None)
       _datLoc:  starting byte location of data block in file (None)

    """

    # mappings between FITS and numarray typecodes
    NumCode = {8:'UInt8', 16:'Int16', 32:'Int32', -32:'Float32', -64:'Float64'}
    ImgCode = {'UInt8':8, 'Int16':16, 'Int32':32, 'Float32':-32, 'Float64':-64}

    def __init__(self, data=None, header=None):
        self._file, self._datLoc = None, None
        if header is not None:

            # Make a "copy" (not just a view) of the input header, since it
            # may get modified.  The data is still a "view" (for now)
            if data is not DELAYED:
                self.header = header.copy()

            # if the file is read the first time, no need to copy
            else:
                self.header = header
        else:
            self.header = Header(CardList(
                [Card('SIMPLE', TRUE, 'conforms to FITS standard'),
                 Card('BITPIX',         8, 'array data type'),
                 Card('NAXIS',          0, 'number of array dimensions')]))

        self.zero = self.header.get('BZERO', 0)
        self.scale = self.header.get('BSCALE', 1)
        self.autoscale = (self.zero != 0) or (self.scale != 1)

        if (data is DELAYED): return

        self.data = data

        # update the header
        self.update_header()

    def update_header(self):
        """Update the header keywords to agree with the data.

           Does not work for GroupHDU.  Need a separate method.
        """

        old_naxis = self.header['NAXIS']

        if isinstance(self.data, num.NumArray):
            self.header['BITPIX'] = ImageBaseHDU.ImgCode[self.data.type()]
            axes = list(self.data.getshape())
            axes.reverse()

        elif self.data is None:
            axes = []
        else:
            raise ValueError, "incorrect array type"

        self.header['NAXIS'] = len(axes)

        # add NAXISi if it does not exist
        for j in range(len(axes)):
            try:
                self.header['NAXIS'+`j+1`] = axes[j]
            except:
                if (j == 0):
                    _after = 'naxis'
                else :
                    _after = 'naxis'+`j`
                self.header.update('naxis'+`j+1`, axes[j], after = _after)

        # delete extra NAXISi's
        for j in range(len(axes)+1, old_naxis+1):
            try:
                del self.header.ascard['NAXIS'+`j`]
            except KeyError:
                pass

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
                self.data._byteorder = 'big'
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

    def _summary(self):
        """Summarize the HDU: name, dimensions, and formats."""
        class_name  = str(self.__class__)
        type  = class_name[class_name.rfind('.')+1:]

        # if data is touched, use data info.
        if 'data' in dir(self):
            if self.data is None:
                _shape, _format = (), ''
            else:

                # the shape will be in the order of NAXIS's which is the
                # reverse of the numarray shape
                _shape = list(self.data.getshape())
                _shape.reverse()
                _shape = tuple(_shape)
                _format = `self.data.type()`
                _format = _format[_format.rfind('.')+1:]

        # if data is not touched yet, use header info.
        else:
            _shape = ()
            for j in range(self.header['NAXIS']):
                _shape += (self.header['NAXIS'+`j+1`],)
            _format = self.NumCode[self.header['BITPIX']]

        return "%-10s  %-11s  %5d  %-12s  %s" % \
               (self.name, type, len(self.header.ascard), _shape, _format)


class PrimaryHDU(ImageBaseHDU):
    """FITS Primary Array Header-Data Unit."""

    def __init__(self, data=None, header=None):
        ImageBaseHDU.__init__(self, data=data, header=header)
        self.name = 'PRIMARY'

        # insert the keywords EXTEND
        if header is None:
            dim = `self.header['NAXIS']`
            if dim == '0':
                dim = ''
            self.header.update('EXTEND', TRUE, after='NAXIS'+dim)


class ImageHDU(ExtensionHDU, ImageBaseHDU):
    """FITS Image Extension Header-Data Unit."""

    def __init__(self, data=None, header=None, name=None):

        # no need to run ExtensionHDU.__init__ since it is not doing anything.
        ImageBaseHDU.__init__(self, data=data, header=header)
        self._xtn = 'IMAGE'

        # change the first card from SIMPLE to XTENSION
        if self.header.ascard[0].key == 'SIMPLE':
            self.header.ascard[0] = Card('XTENSION', self._xtn, 'Image extension')
        self.header._hdutype = ImageHDU

        # insert the require keywords PCOUNT and GCOUNT
        dim = `self.header['NAXIS']`
        if dim == '0':
            dim = ''

        # only update if they don't exist, if they exist but have incorrect
        # values, keep as is
        if not self.header.has_key('PCOUNT'):
            self.header.update('PCOUNT', 0, after='NAXIS'+dim)
        if not self.header.has_key('GCOUNT'):
            self.header.update('GCOUNT', 1, after='PCOUNT')

        #  set extension name
        if not name and self.header.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name

    def _verify(self, option='warn'):
        """ImageHDU verify method."""
        _err = ExtensionHDU._verify(self, option=option)
        self.req_cards('PCOUNT', None, isInt+" and val == 0", 0, option, _err)
        return _err


class GroupsHDU(PrimaryHDU):
    """FITS Random Groups Header-Data Unit."""

    def __init__(self, data=None, header=None, groups=None, name=None):
        PrimaryHDU.__init__(self, data=data, header=header)
        self.header._hdutype = GroupsHDU
        self.name = name

        # insert the require keywords GROUPS, PCOUNT, and GCOUNT
        if self.header['NAXIS'] <= 0:
            self.header['NAXIS'] = 1
        self.header.update('NAXIS1', 0, after='NAXIS')

        dim = `self.header['NAXIS']`
        self.header.update('GROUPS', TRUE, after='NAXIS'+dim)
        self.header.update('PCOUNT', 0, after='GROUPS')
        self.header.update('GCOUNT', 1, after='PCOUNT')

    # 0.6.5.5
    def size(self):
        """Size of the data part."""
        size = 0
        naxis = self.header.get('NAXIS', 0)

        # for random group image, NAXIS1 should be 0, so we skip NAXIS1.
        if naxis > 1:
            size = 1
            for j in range(1, naxis):
                size = size * self.header['NAXIS'+`j+1`]
            bitpix = self.header['BITPIX']
            gcount = self.header.get('GCOUNT', 1)
            pcount = self.header.get('PCOUNT', 0)
            size = abs(bitpix) * gcount * (pcount + size) / 8
        return size

    def _verify(self, option='warn'):
        _err = PrimaryHDU._verify(self, option=option)

        # Verify location and value of mandatory keywords.
        self.req_cards('NAXIS', None, isInt+" and val >= 1", 1, option, _err)
        self.req_cards('NAXIS1', None, isInt+" and val == 0", 0, option, _err)
        _after = self.header['NAXIS'] + 3

        # if the card EXTEND exists, must be after it.
        try:
            _dum = self.header['EXTEND']
            _after += 1
        except:
            pass
        _pos = '>= '+`_after`
        self.req_cards('GCOUNT', _pos, isInt, 1, option, _err)
        self.req_cards('PCOUNT', _pos, isInt, 0, option, _err)
        self.req_cards('GROUPS', _pos, 'val == TRUE', TRUE, option, _err)
        return _err


# --------------------------Table related code----------------------------------

# lists of column/field definition common names and keyword names, make
# sure to preserve the one-to-one correspondence when updating the list(s).
# Use lists, instead of dictionaries so the names can be displayed in a
# preferred order.
commonNames = ['name', 'format', 'unit', 'null', 'bscale', 'bzero', 'disp', 'start', 'dim']
keyNames = ['TTYPE', 'TFORM', 'TUNIT', 'TNULL', 'TSCAL', 'TZERO', 'TDISP', 'TBCOL', 'TDIM']

# mapping from TFORM data type to numarray data type (code)

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

    def __init__(self, input, tbtype='BinTableHDU'):

        self._tbtype = tbtype

        # if the input is a list of Columns
        if isinstance(input, types.ListType):
            self._nfields = len(input)
            self._setup()

            # populate the attributes
            for i in range(self._nfields):
                if not isinstance(input[i], Column):
                    raise TypeError, "input to ColDefs must be a list of Columns"
                for cname in commonNames:
                    attr = getattr(self, cname+'s')
                    val = getattr(input[i], cname)
                    if val != None:
                        attr[i] = getattr(input[i], cname)

                if tbtype == 'BinTableHDU':
                    self.formats[i] = convert_format(self.formats[i])
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
                        attr = getattr(self, cname+'s')
                        attr[col-1] = _card.value


            # for ASCII table, the formats needs to be converted to positions
            # following TBCOL's
            if tbtype == 'TableHDU':
                self._Formats = self.formats
                dummy = map(lambda x, y: x-y, self.starts[1:], self.starts[:-1])
                dummy.append(input['NAXIS1']-self.starts[-1]+1)
                self.formats = map(lambda y: `y`+'a', dummy)

            # only convert format for binary tables, since ASCII table's
            # "raw data" are string (taken care of above)
            else:
                for i in range(self._nfields):
                    fmt = self.formats[i]
                    if fmt != '':
                        (repeat, dtype, option) = parse_tformat(fmt)
                        if dtype in fits2rec.keys():
                            self.formats[i] = `repeat`+fits2rec[dtype]
                        else:
                            raise ValueError, "Illegal format %s" % dtype

        elif isinstance(input, BinTableHDU):   # extract the column definitions
            tmp = input.data            # touch the data
            self.__dict__ = input.columns.__dict__
        else:
            raise TypeError, "input to ColDefs must be BinTableHDU or a list of Columns"

    def _setup(self):
        """ Initialize all attributes to be a list of null strings."""
        for cname in commonNames:
            setattr(self, cname+'s', ['']*self._nfields)
        setattr(self, '_arrays', [None]*self._nfields)

    def add_col(self, column):
        """ append one column"""

        self._nfields += 1

        # append the column attributes to the attribute lists
        for cname in commonNames:
            attr = getattr(self, cname+'s')
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

        indx = rec.index_of(self.names, col_name)

        for cname in commonNames:
            attr = getattr(self, cname+'s')
            del attr[indx]

        del self._arrays[indx]
        self._nfields -= 1

    def change_attrib(self, col_name, attrib, new_value):
        """ change an attribute (in the commonName list) of a column """

        indx = rec.index_of(self.names, col_name)
        getattr(self, attrib+'s')[indx] = new_value

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
            print '    ', getattr(self, att+'s')

    #def change_format(self, col_name, new_format):
        #new_format = convert_format(new_format)
        #self.change_attrib(col_name, 'format', new_format)

def get_tbdata(data_source, col_def=None):
    """ Get the table data from data_source, using column definitions in
        col_def.
    """
    #if col_def == None:
        #(xxx)_data = rec.array(data_source)

    # if the column definition is from a Table (header)
    if isinstance(col_def, ColDefs):
        tmp = col_def
        _data = rec.array(data_source, formats=tmp.formats, names=tmp.names, shape=tmp._shape)
        if isinstance(data_source, types.FileType):
            _data._byteorder = 'big'

        # pass the attributes
        for attr in ['formats', 'names']:
            setattr(_data, attr, getattr(tmp, attr))
        for i in range(tmp._nfields):
            tmp._arrays[i] = _data.field(i)

    return FITS_rec(_data)

def new_table (input, header=None, nrows=0, fill=0, tbtype='BinTableHDU'):
    """ Create a new table from the input column definitions.

        input: a list of Columns or a ColDefs object.
        header: header to be used to populate the non-required keywords
        nrows: number of rows in the new table
        fill: if = 1, will fill all cells with zeros or blanks
              if = 0, copy the data from input, undefined cells will still
                      be filled with zeros/blanks.
        tbtype: table type to be created (BinTableHDU or TableHDU)
    """

    # construct a table HDU
    hdu = eval(tbtype)(header=header)

    if isinstance(input, ColDefs):
        tmp = hdu.columns = input
    else:                 # input is a list of Columns
        tmp = hdu.columns = ColDefs(input, tbtype)

    # use the largest column shape as the shape of the record
    if nrows == 0:
        for arr in tmp._arrays:
            if arr is not None:
                dim = arr._shape[0]
            else:
                dim = 0
            if dim > nrows:
                nrows = dim

    hdu.data = FITS_rec(rec.array(None, formats=tmp.formats, names=tmp.names, shape=nrows))
    hdu.data._coldefs = hdu.columns

    # populate data to the new table
    for i in range(tmp._nfields):
        if tmp._arrays[i] is None:
            size = 0
        else:
            size = len(tmp._arrays[i])

        n = min(size, nrows)
        if fill:
            n = 0
        if n > 0:
            hdu.data._parent.field(i)[:n] = tmp._arrays[i][:n]
        if n < nrows:
            if isinstance(hdu.data._parent.field(i), num.NumArray):
                hdu.data._parent.field(i)[n:] = 0
            else:
                hdu.data._parent.field(i)[n:] = ''

        #hdu.data._convert[i] = hdu.data._parent.field(i)

    hdu.update()
    return hdu


class FITS_rec(rec.RecArray):
    """A layer over the record array, so we can deal with scaled columns."""

    def __init__(self, input):

        # input should be a record array
        self.__dict__ = input.__dict__
        self._parent = input
        self._convert = [None]*self._nfields

    def field(self, key):
        indx = rec.index_of(self._names, key)

        if (self._convert[indx] is None):
            if self._coldefs._tbtype == 'BinTableHDU':
                _str = self._coldefs.formats[indx][-1] == 'a'
                _bool = self._coldefs.formats[indx][-1] == 'b'
            else:
                _str = self._coldefs._Formats[indx][0] == 'A'
                _bool = 0             # there is no boolean in ASCII table
            _number = not(_bool or _str)
            bscale = self._coldefs.bscales[indx]
            bzero = self._coldefs.bzeros[indx]
            _scale = bscale not in ['', None, 1]
            _zero = bzero not in ['', None, 0]

            if _str:
                return self._parent.field(key)

            # ASCII table, convert strings to numbers
            if self._coldefs._tbtype == 'TableHDU':
                _dict = {'I':num.Int32, 'F':num.Float32, 'E':num.Float32, 'D':num.Float64}
                _type = _dict[self._coldefs._Formats[indx][0]]

                # if the string = TNULL, return 0
                nullval = self._coldefs.nulls[indx].strip()
                dummy = num.zeros(len(self._parent), type=_type)
                self._convert[indx] = dummy
                for i in range(len(self._parent)):
                    if self._parent.field(indx)[i].strip() != nullval:
                        dummy[i] = eval(self._parent.field(indx)[i])
            else:
                dummy = self._parent.field(key)

            # further conversion for both ASCII and binary tables
            if _number and (_scale or _zero):

                # only do the scaling the first time and store it in _convert
                self._convert[indx] = dummy*bscale+bzero
            elif _bool:
                self._convert[indx] = num.equal(dummy, ord('T'))
            else:
                return dummy

        return self._convert[indx]


class TableBaseHDU(ExtensionHDU):
    """Table base HDU"""

    def __init__(self, data=None, header=None, name=None):
        if header != None:

            # Make a "copy" (not just a view) of the input header, since it
            # may get modified.
            # the data is still a "view" (for now)
            if data is not DELAYED:
                self.header = header.copy()

            # if the file is read the first time, no need to copy
            else:
                self.header = header
        else:
            self.header = Header(CardList(
                [Card('XTENSION', '     ', 'FITS table extension'),
                 Card('BITPIX',         8, 'array data type'),
                 Card('NAXIS',          2, 'number of array dimensions'),
                 Card('NAXIS1',         0, 'length of dimension 1'),
                 Card('NAXIS2',         0, 'length of dimension 2'),
                 Card('PCOUNT',         0, 'number of group parameters'),
                 Card('GCOUNT',         1, 'number of groups'),
                 Card('TFIELDS',        0, 'number of table fields')]))

        if (data is not DELAYED):
            if isinstance(data, rec.RecArray):
                self.header['NAXIS1'] = data._itemsize
                self.header['NAXIS2'] = data._shape[0]
                self.data = data
            elif type(data) == types.NoneType:
                pass
            else:
                raise TypeError, "table data has incorrect type"

        #  set extension name
        if not name and self.header.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name
        #self.autoscale = 1

    def __getattr__(self, attr):
        if attr == 'data':
            size = self.size()
            if size:
                self._file.seek(self._datLoc)
                data = get_tbdata(self._file, self.columns)
                data._coldefs = self.columns
            else:
                data = None
            self.__dict__[attr] = data

        elif attr == 'columns':
            class_name = str(self.__class__)
            class_name = class_name[class_name.rfind('.')+1:]
            self.__dict__[attr] = ColDefs(self.header, tbtype=class_name)

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)


    def _summary(self):
        """Summarize the HDU: name, dimensions, and formats."""
        class_name  = str(self.__class__)
        type  = class_name[class_name.rfind('.')+1:]

        # if data is touched, use data info.
        if 'data' in dir(self):
            if self.data is None:
                _shape, _format = (), ''
            else:
                _nrows = len(self.data)
                _ncols = len(self.data._coldefs.formats)
                _format = self.data._coldefs.formats

        # if data is not touched yet, use header info.
        else:
            _shape = ()
            _nrows = self.header['NAXIS2']
            _ncols = self.header['TFIELDS']
            _format = '['
            for j in range(_ncols):
                _format += self.header['TFORM'+`j+1`] + ', '
            _format = _format[:-2] + ']'
        _dims = "%dR x %dC" % (_nrows, _ncols)

        return "%-10s  %-11s  %5d  %-12s  %s" % \
            (self.name, type, len(self.header.ascard), _dims, _format)

    # 0.6.2
    def get_coldefs(self):
        return self.columns

    def update(self):
        """ Update header keywords to reflect recent changes of columns"""
        _update = self.header.update
        _append = self.header.ascard.append
        _cols = self.columns
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
                val = getattr(_cols, cname+'s')[i]
                if val != '':
                    keyword = keyNames[commonNames.index(cname)]+`i+1`
                    if cname == 'format':
                        val = convert_format(val, reverse=1)
                    #_update(keyword, val)
                    _append(Card(keyword, val))

    def copy(self):
        """Make a copy of the table HDU, both header and data are copied."""
        # touch the data, so it's defined (in the case of reading from a
        # FITS file)
        self.data
        return new_table(self.columns, header=self.header, tbtype=self.columns._tbtype)

    def _verify(self, option='warn'):
        """TableBaseHDU verify method."""
        _err = ExtensionHDU._verify(self, option=option)
        self.req_cards('NAXIS', None, 'val == 2', 2, option, _err)
        self.req_cards('TFIELDS', '== 7', isInt+" and val >= 0 and val <= 999", 0, option, _err)
        tfields = self.header['TFIELDS']
        for i in range(tfields):
            self.req_cards('TFORM'+`i+1`, None, None, None, option, _err)
        return _err


class TableHDU(TableBaseHDU):

    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')

    def __init__(self, data=None, header=None, name=None):
        TableBaseHDU.__init__(self, data=data, header=header, name=name)
        self._xtn = 'TABLE'
        if self.header[0].rstrip() != self._xtn:
            self.header[0] = self._xtn
            self.header.ascard[0].comment = 'ASCII table extension'
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


    def _verify(self, option='warn'):
        """TableHDU verify method."""
        _err = TableBaseHDU._verify(self, option=option)
        self.req_cards('PCOUNT', None, 'val == 0', 0, option, _err)
        tfields = self.header['TFIELDS']
        for i in range(tfields):
            self.req_cards('TBCOL'+`i+1`, None, isInt, None, option, _err)
        return _err


class BinTableHDU(TableBaseHDU):
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

    def __init__(self, data=None, header=None, name=None):
        TableBaseHDU.__init__(self, data=data, header=header, name=name)
        self._xtn = 'BINTABLE'
        hdr = self.header
        if hdr[0] != self._xtn:
            hdr[0] = self._xtn
            hdr.ascard[0].comment = 'binary table extension'

    '''

    def fitsType(self, type, count=1):
        if self.fitsCode.has_key(type):
            value = str(count)+BinTableHDU.fitsCode[type]
        elif 's' in type:
            value, type = type[1:]+'A', 's'
        else:
            raise TypeError, type
        return value, self.fitsComment[type]

    ''' # 0.4.4


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

            # For 'ab+' mode, the pointer is at the end after the open in
            # Linux, but is at the beginning in Solaris.
            self.__file.seek(0)

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
            header=Header(kards)
            hdu = header._hdutype(data=DELAYED, header=header)

            hdu._file = self.__file
            hdu._hdrLoc = _hdrLoc                # beginning of the header area
            hdu._datLoc = self.__file.tell()     # beginning of the data area
            hdu._new = 0
            self.__file.seek(hdu.size()+padLength(hdu.size()), 1)

        except:
            pass

        return hdu

    def writeHDU(self, hdu):
        """Write *one* FITS HDU.  Must seek to the correct location before
           calling this method."""

        if isinstance(hdu, ImageBaseHDU):
            hdu.update_header()
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

            # if image, need to deal with bzero/bscale and byteorder
            if isinstance(hdu, ImageBaseHDU):
                hdu.zero = hdu.header.get('BZERO', 0)
                hdu.scale = hdu.header.get('BSCALE', 1)
                hdu.autoscale = (hdu.zero != 0) or (hdu.scale != 1)
                if hdu.autoscale:
                    code = ImageBaseHDU.NumCode[hdu.header['BITPIX']]
                    zero = num.array([hdu.zero], type=code)
                    scale = num.array([hdu.scale], type=code)
                    hdu.data = (hdu.data - zero) / scale

                if hdu.data._byteorder != 'big':
                    hdu.data.byteswap()
                    hdu.data._byteorder = 'big'

            # Binary table byteswap
            elif isinstance(hdu, BinTableHDU):
                for i in range(hdu.data._nfields):
                    coldata = hdu.data.field(i)
                    if not isinstance(coldata, chararray.CharArray):
                        if coldata._type.bytes > 1:

                            # only swap unswapped
                            if coldata._byteorder != 'big':
                                coldata.byteswap()
                                coldata._byteorder = 'big'

                # In case the FITS_rec was created in a LittleEndian machine
                hdu.data._byteorder = 'big'

            hdu.data.tofile(self.__file)
            _size = hdu.data.nelements() * hdu.data._itemsize

            # pad the FITS data block
            if _size > 0:
                self.__file.write(padLength(_size)*'\0')

        # flush, to make sure the content is written
        self.__file.flush()
        return loc

    def close(self):
        """ close the 'physical' FITS file"""

        if self.__file.closed:
            print "The associated file is already closed."

        self.__file.close()

class HDUList(UserList.UserList, _Verify):
    """HDU list class"""

    def __init__(self, hdus=None, file=None, output_verify="exception"):
        UserList.UserList.__init__(self)
        self.__file = file
        self.output_verify = output_verify
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
        """Set an HDU to the list, indexed by number or name."""
        key = self.index_of(key)
        self.data[key] = hdu
        self._resize = 1

    def __delitem__(self, key):
        """Delete an HDU from the list, indexed by number or name."""
        key = self.index_of(key)
        del self.data[key]
        self._resize = 1

    def __delslice__(self, i, j):
        """Delete a slice of HDUs from the list, indexed by number only."""
        del self.data[i:j]
        self._resize = 1

    def __getattr__(self, attr):
        if attr == 'closed':
            return self.__file._File__file.closed
        raise AttributeError(attr)

    def _verify (self, option='warn'):
        _text = ''
        _err = ErrList([], unit='HDU')

        # the first (0th) element must be a primary HDU
        if not isinstance(self.data[0], PrimaryHDU):
            err_text = "HDUList's 0th element is not a primary HDU."
            fix_text = 'Fixed by inserting one as 0th HDU.'
            fix = "self.data.insert(0, PrimaryHDU())"
            _text = self.run_option(option, err_text=err_text, fix_text=fix_text, fix=fix)
            _err.append(_text)

        # each element calls their own verify
        for i in range(len(self.data)):
            if not isinstance(self.data[i], AllHDU):
                err_text = "HDUList's element %s is not an HDU." % `i`
                _text = self.run_option(option, err_text=err_text, fixable=0)
                _err.append(_text)

            else:
                _result = self.data[i]._verify(option)
                if _result:
                    _err.append(_result)
        return _err

    def append(self, hdu):
        """Append a new HDU to the HDUList."""
        if isinstance(hdu, AllHDU):
            self.data.append(hdu)
            hdu._new = 1
            self._resize = 1
        else:
            raise "HDUList can only append an HDU"

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

    def writeto(self, name, output_verify=None):
        """Write the HDUList to a new file."""

        if (len(self) == 0):
            print "There is nothing to write."
            return

        if output_verify is None:
            if 'output_verify' not in dir(self):
                _option = 'exception'  # default value
            else:
                _option = self.output_verify
        else:
            _option = output_verify

        if _option == 'warn':
            _option == 'exception'
        self.verify(option=_option)

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
                  "      Cards   Dimensions   Format\n" % _name

        for j in range(len(self)):
            results = results + "%-3d  %s\n"%(j, self.data[j]._summary())
        results = results[:-1]
        print results


def open(name, mode="readonly", memmap=0, output_verify="exception"):
    """Factory function to open a FITS file and return an HDUList instance"""

    # instanciate a FITS file object (ffo)
    ffo = _File(name, mode=mode, memmap=memmap)
    hduList = HDUList(file=ffo, output_verify=output_verify)

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
