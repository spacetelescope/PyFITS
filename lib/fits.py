#!/usr/bin/env python2.0

"""A module for reading and writing FITS files.

A module for reading and writing Flexible Image Transport System
(FITS) files.  This file format was endorsed by the International
Astronomical Union in 1999 and mandated by NASA as the standard format
for storing high energy astrophysics data.  For details of the FITS
standard, see the NASA/Science Office of Standards and Technology
publication, NOST 100-2.0.

"""

import re, string, types, sys, exceptions
import UserList, Numeric
import record

version = '0.4 (Feb 28, 2001)'

#   Utility Functions

def padLength(stringLen):
    return (FITS.blockLen - stringLen%FITS.blockLen)%FITS.blockLen

__octalRegex = re.compile(r'([+-]?)0+([1-9][0-9]*)')

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


#   FITS Classes

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
                if (valu.group('strg') and valu.start('strg') == 0) or \
                   valu.end('valu') == 20:
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


class CardList(UserList.UserList):

    """A FITS card list"""
    
    def __init__(self, cards=None):
        "Initialize the card list of the header."

        UserList.UserList.__init__(self, cards)
    
    def __getitem__(self, key):
        """Get a card from the CardList."""

        if type(key) == types.StringType:
            key = self.index_of(key)
        return self.data[key]
    
    def __setitem__(self, key, value):
        "Set a card in the CardList."

        if isinstance (value, Card):
            if type(key) == types.StringType:
                key = string.upper(string.strip(key))
                self.data[self.index_of(key)] = value
            else:
                self.data[key] = value
        else:
            raise SyntaxError, "%s is not a Card" % str(value)
    
    def __delitem__(self, key):
        """Delete a card from the CardList."""

        if type(key) == types.StringType:
            key = string.upper(string.strip(key))
            key = self.index_of(key)
        del self.data[key]
    
    def keys(self):
        """Return a list of all keywords from the CardList."""

        keys = []
        for card in self.data:
            keys.append(card.key)
        return keys
    
    def items(self):
        """Return a list of all keyword-value pairs from the CardList."""

        cards = []
        for card in self.data:
            cards.append((card.key, card.value))
        return cards
    
    def has_key(self, key):
        """Test for a keyword in the CardList."""

        key = string.upper(key)
        for card in self.data:
            if card.key == key:
                return 1
        else:
            return 0
    
    def get(self, key, default=None):
        """Get a keyword value from the CardList.
        If no keyword is found, return the default value.

        """

        key = string.upper(key)
        for card in self.data:
            if card.key == key:
                return card.value
        else:
            return default
    
    def update(self, key, value, comment=None, before=None, after=None):
        if self.has_key(key):
            j = self.index_of(key)
            self[j].value = value
            if comment:
                self[j].comment = comment
        elif before and self.has_key(before):
            self.insert(self.index_of(before), Card(key, value, comment))
        elif after and self.has_key(after):
            self.insert(self.index_of(after)+1, Card(key, value, comment))
        else:
            self.append(Card(key, value, comment))
    
    def index_of(self, key):
        """Get the index of a keyword in the CardList."""

        key = string.upper(string.strip(key))
        for j in range(len(self.data)):
            if self.data[j].key == key:
                return j
        else:
            raise KeyError, key
    
    def copy(self):
        return CardList(self.data[:])
    
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
       header:  type of array
       data:  shape of array
    
      Class data:
       _file:  file associated with array          (None)
       _data:  starting byte of data block in file (None)

    """
    
    # mappings between FITS and Numeric typecodes
    NumCode = {8:'b', 16:'s', 32:'l', -32:'f', -64:'d'}
    ImgCode = {'b':8, 's':16, 'l':32, 'f':-32, 'd':-64}

    def __init__(self, data=None, cards=None, name=None):
        self._file, self._data = None, None
        if cards:
            self.header = Header(cards)
        else:
            self.header = Header(
                [Card('SIMPLE', FITS.TRUE, 'conforms to FITS standard'),
                 Card('BITPIX',         8, 'array data type'),
                 Card('NAXIS',          0, 'number of array dimensions')])
        
        if type(data) == Numeric.arraytype:
            self.header['BITPIX'] = ImageBaseHDU.ImgCode[data.typecode()]
            axes = list(data.shape)
            axes.reverse()
            self.header['NAXIS'] = len(axes)
            for j in range(len(axes)):
                self.header['NAXIS'+`j+1`] = axes[j]
            self.data = data
        elif type(data) == types.NoneType:
            pass
        else:
            raise ValueError, "incorrect array type"
        self.name = name
        self.zero = self.header.ascard.get('BZERO', 0)
        self.scale = self.header.ascard.get('BSCALE', 1)
	self.autoscale = (self.zero != 0) or (self.scale != 1)
    
    def __getattr__(self, attr):
        if attr == 'data':
            self.__dict__[attr] = None
            if self.header['NAXIS'] > 0:
                self._file.seek(self._data)
                size = self.size()
                blok = self._file.read(size)
                if len(blok) == 0:
                    raise EOFError
                elif len(blok) != size:
                    raise IOError

                #  To preserve the type of self.data during autoscaling,
                #  make zero and scale 0-dim Numeric arrays.
                code = ImageBaseHDU.NumCode[self.header['BITPIX']]
                self.data = Numeric.fromstring(blok, code)
                if Numeric.LittleEndian:
                    self.data = self.data.byteswapped()
                if self.autoscale:
                    zero = Numeric.array(self.zero, code)
                    scale = Numeric.array(self.scale, code)
                    self.data = scale*self.data + zero
                self.data.shape = self.shape()
        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def shape(self):
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
                   self.header.ascard.get('GCOUNT', 1)* \
                   (self.header.ascard.get('PCOUNT', 0) + size)
        return size
    
    def summary(self):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data != None:
            shape, format = self.data.shape, self.data.typecode()
        else:
            shape, format = (), ''
        print shape
        return "%-10s  %-11s  %5d  %-12s  %s"%\
               (self.name, type, len(self.header.ascard), shape, format)
    
    def verify(self):
        req_kw = [
            ('SIMPLE',   "val == FITS.TRUE or val == FITS.FALSE"),
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


class PrimaryHDU(ImageBaseHDU):
    """FITS Primary Array Header-Data Unit"""
    
    def __init__(self, data=None, cards=None):
        ImageBaseHDU.__init__(self, data, cards, 'PRIMARY')
    
    def copy(self):
        if self.data:
            Data = self.data.copy()
        else:
            Data = None
        return PrimaryHDU(Data, self.header.ascard.copy())


class ImageHDU(ImageBaseHDU):
    """FITS Image Extension Header-Data Unit"""
    
    def __init__(self, data=None, cards=None, name=None):
        ImageBaseHDU.__init__(self, data, cards, name)

        #  set extension name
        if not name and self.header.ascard.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name
    
    def __setattr__(self, attr, value):
        """Set an Array HDU attribute"""

        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.ascard.has_key('EXTNAME'):
                self.header['EXTNAME'] = value
            else:
                self.header.ascard.append(Card('EXTNAME', value, 'extension name'))
        self.__dict__[attr] = value
    
    def copy(self):
        if self.data != None:
            Data = self.data.copy()
        else:
            Data = None
        return ImageHDU(Data, self.header.ascard.copy())
    
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
    
    def __init__(self, data=None, cards=None, groups=None, name=None):
        ImageBaseHDU.__init__(self, data, cards, 'PRIMARY')
    
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
            Data = self.data.copy()
        else:
            Data = None
        return GroupsHDU(Data, self.header.ascard.copy())
    
    def verify(self):
        hdr = self.header
        req_kw = [
            ('SIMPLE',   "val == FITS.TRUE or val == FITS.FALSE"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0"),
            ('NAXIS1',   "val == 0")]
        for j in range(1, hdr['NAXIS']+1):
            req_kw.append(('NAXIS'+`j+1`, "val >= 0"))
        req_kw = req_kw + [
            ('GROUPS',   "val == FITS.TRUE"),
            ('PCOUNT',   "val >= 0"),
            ('GCOUNT',   "val >= 0")]

        for j in range(len(req_kw)):
            key, val = hdr.ascard[j].key, hdr[j]
            if not key == req_kw[j][0]:
                raise "Required keyword not found:\n'%s'" % hdr.ascard[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'" % hdr.ascard[j]


class Field:

    """FITS field class: Defines fields used in data tables"""
    
    reqkey = [
        ('TFIELDS' ,          0, 'number of fields in each row'),
        ('TFORM'   ,       'I1', '')]
    
    reskey = [
        ('TTYPE'   ,         '', 'name of field'),
        ('TUNIT'   ,         '', 'physical unit of field'),
        ('TNULL'   ,        ' ', 'null value of field'),
        ('TSCAL'   ,        1.0, 'scale factor of field'),
        ('TZERO'   ,        0.0, 'zero point of field')]
    
    def __init__(self, col, data=None, cards=None, name=None):
        "Creates a Field type"

        self.column, n = col, str(col+1)     # = column number
        self.name, self.code, self.unit = name, 'B', None
        self.scale,self.zero, self.null = 1.0, 0.0, None
        if cards:
            if cards.has_key('TTYPE'+n): self.name = cards['TTYPE'+n]
            if cards.has_key('TUNIT'+n): self.unit = cards['TUNIT'+n]
            if cards.has_key('TNULL'+n): self.null = cards['TNULL'+n]
            if cards.has_key('TSCAL'+n): self.scale= cards['TSCAL'+n]
            if cards.has_key('TZERO'+n): self.zero = cards['TZERO'+n]
        if data == None:
            self.code = string.split(data.format[1:], ',')[col]
    
    def __repr__(self):
        """Create a list of field cards for display"""

        cards = CardList()
        n = str(self.column+1)
        if self.name:         
            cards.append(Card('TTYPE'+n, self.name, 'label of field'))
        cards.append(Card('TFORM'+n, Field.binCode[self.code], \
                          'data type of field: %s' % \
                          Field.codestr[self.code]))
        if self.unit:         
            cards.append(Card('TUNIT'+n, self.unit, 'physical unit of field'))
        if self.scale != 1.0: 
            cards.append(Card('TSCAL'+n, self.scale, ''))
        if self.zero != 0.0:  
            cards.append(Card('TZERO'+n, self.zero, ''))
        if self.null: 	      
            cards.append(Card('TNULL'+n, self.null, ''))
        return cards


class ASCIIField:
    
    # Maps FITS types to recarray types, and vice versa
    recdCode = {'A':'s', 'I':'i16', 'F':'f32', 'E':'f32', 'D':'f64'}
    fitsCode = {'s':'A', 'i16':'I', 'f32':'F', 'f32':'E', 'f64':'D'}
    
    def __init__(self, col, data=None, cards=None, name=None):
        """Creates a ASCII Field type"""

        self.__column, n = col, str(col+1)     # = column number
	self.__name,  self.__code = name, ''
	self.__start, self.__unit = 1, ''
        self.__scale, self.__zero, self.__null = 1.0, 0.0, None
	
        if cards:
	    if cards.has_key('TBCOL'+n): self.__start = cards['TBCOL'+n]
	    if cards.has_key('TFORM'+n): self.__code = \
	       ASCIIField.format[cards['TFORM'+n][-1]]
	    
            if cards.has_key('TTYPE'+n): self.__name = cards['TTYPE'+n]
            if cards.has_key('TUNIT'+n): self.__unit = cards['TUNIT'+n]
            if cards.has_key('TSCAL'+n): self.__scale= cards['TSCAL'+n]
            if cards.has_key('TZERO'+n): self.__zero = cards['TZERO'+n]
            if cards.has_key('TNULL'+n): self.__null = cards['TNULL'+n]
        if data == None:
            self.__code = string.split(data.format[1:], ',')[col]
    
    def __repr__(self):
        """Create a list of field cards for display"""

        cards = CardList()
        n = str(self.__column+1)
	cards.append(Card('TBCOL'+n, self.__start, ''))
        cards.append(Card('TFORM'+n, ASCIIField.code[self.__code], \
                          'data type of field: %s' % \
                          ASCIIField.codestr[self.__code]))
        if self.__name:         
            cards.append(Card('TTYPE'+n, self.__name, ''))
        if self.__unit:         
            cards.append(Card('TUNIT'+n, self.__unit, ''))
        if self.__scale != 1.0: 
            cards.append(Card('TSCAL'+n, self.__scale, ''))
        if self.__zero != 0.0:  
            cards.append(Card('TZERO'+n, self.__zero, ''))
        if self.__null: 	
            cards.append(Card('TNULL'+n, self.__null, ''))
        return cards


class BinaryField:
    
    binaryResKey = [
        ('TDISP'   ,         '', 'suggested display format of field'),
        ('THEAP'   ,          0, 'start of supplemental data'),
        ('TDIM'    ,         '', 'shape of array of field')]
    
    # Maps FITS types to record types, and vice versa
    recdCode = {'L':'I8', 'X':'c', 'A':'s', 'B':'I8', 'I':'i16', 'J':'i32', \
                'E':'f32', 'D':'f64', 'C':'F32', 'M':'F64', 'P':'s8'}
    fitsCode = {'s':'A', 'I8':'B', 'i16':'I', 'i32':'J', \
                'f32':'E', 'f64':'D', 'F32':'C', 'F64':'M', 's8':'P'}
    
    # Description of FITS types for comment field
    recdComm = {
        's'  :'CHARACTER array',
        'I8' :'1-byte unsigned CHARACTER',
        'i16':'2-byte signed INTEGER',
        'i32':'4-byte signed INTEGER',
        'f32':'REAL',
        'f64':'DOUBLE PRECISION'}
    
    def __init__(self, field, type, name=None, unit=None, null=None,
                 scale=1., zero=0., disp=None, heap=None, dimn=None):
        """Creates a Field type"""

        self.field, self.type = field, type
        self.name, self.unit  = name,  unit
        self.null, self.scale, self.zero = null, scale, zero
        self.disp, self.heap,  self.dim  = disp, heap, dimn
    
    def verify(self, cards):
        res_kw = [
            ('TTYPE', "type(val) == types.StringType"),
            ('TUNIT', "type(val) == types.StringType"),
            ('TNULL', "type(val) == types.IntType"),
            ('TSCAL', "type(val) == types.FloatType"),
            ('TZERO', "type(val) == types.FloatType"),
            ('TDISP', "type(val) == types.StringType"),
            ('THEAP', "val > 0"),
            ('TDIM',  "type(val) == types.StringType")]

        for j in hdr['TFIELDS']:
            key = 'TFORM'+`j+1`
            if not hdr.has_key[kw]:
                raise "Required keyword not found:\n'%s'"%\
                      hdr[hdr.index_of(key)]
            val = hdr[key]
            if not type(val) == types.StringType:
                raise "Invalid keyword type or value:\n'%s'"%\
                      hdr[hdr.index_of(key)]

            for kw in res_kw:
                key = kw[0]+`j+1`
                if hdr.has_key(key):
                    val = hdr[key]
                    if not eval(kw[1]):
                        raise "Invalid keyword type or value:\n'%s'"%\
                              hdr[hdr.index_of(key)]
        
        
    #def __repr__(self):
    #    "Create a list of field cards for display"
    #    cards = CardList()
    #    n = str(self.__column+1)
    #    cards.append(Card('TFORM'+n, BinaryField.code[self.__code], \
    #                      'data type of field: %s' % \
    #                      BinaryField.codestr[self.__code]))
    #    if self.__name:         cards.append(Card('TTYPE'+n, self.__name, ''))
    #    if self.__unit:         cards.append(Card('TUNIT'+n, self.__unit, ''))
    #    if self.__scale != 1.0: cards.append(Card('TSCAL'+n, self.__scale,''))
    #    if self.__zero != 0.0:  cards.append(Card('TZERO'+n, self.__zero, ''))
    #    if self.__null:         cards.append(Card('TNULL'+n, self.__null, ''))
    #    if self.__disp:         cards.append(Card('TDISP'+n, self.__disp, ''))
    #    if self.__heap:         cards.append(Card('THEAP'+n, self.__heap, ''))
    #    if self.__dimn:         cards.append(Card('TDIM' +n, self.__dimn, ''))
    #    return cards


class Table:
    """FITS data table class

      Attributes:
       header:  the header part
       data:  the data part
    
      Class data:
      _file:  file associated with table          (None)
      _data:  starting byte of data block in file (None)

    """
    
    def __init__(self, data=None, cards=None, name=None):
        self._file, self._data = None, None
        if cards:
            self.header = Header(cards)
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

        if type(data) == type(record.record((1,))):
            self.header['NAXIS1'] = len(data[0].tostring())
            self.header['NAXIS2'] = data.shape[0]
            self.data = data
        elif type(data) == types.NoneType:
            pass
        else:
            raise TypeError, "incorrect data attribute type"

        #  set extension name
        if not name and self.header.ascard.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name
	self.autoscale = 1
    
    def __getattr__(self, attr):
        if attr == 'data':
            size = self.size()
            if size:
                self._file.seek(self._data)
                blok = self._file.read(size)
                if len(blok) == 0:
                    raise EOFError
                elif len(blok) != size:
                    raise IOError
                rows = self.header['NAXIS2']
                data = record.fromstring(blok, rows, self.format()) 
            else:
                data = None
            self.__dict__[attr] = data
        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)
    
    def __setattr__(self, attr, value):
        """Set an Array HDU attribute"""

        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.ascard.has_key('EXTNAME'):
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
                   self.header.ascard.get('GCOUNT', 1) * \
                   (self.header.ascard.get('PCOUNT', 0) + size)
        return size
    
    def summary(self):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data:
            shape, format = self.data.shape, self.data.format
        else:
            shape, format = (), ''
        return "%-10s  %-11s  %5d  %-12s  %s"%\
               (self.name, type, len(self.header.ascard), shape, format)


class TableHDU(Table):
    
    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')
    
    def __init__(self, data=None, cards=None, name=None):
        Table.__init__(self, data, cards, name)
        if string.rstrip(self.header[0]) != 'TABLE':
            self.header[0] = 'TABLE   '
            self.header.ascard[0].comment = 'ASCII table extension'
        self.recdCode = ASCIIField.recdCode
        self.fitsCode = ASCIIField.fitsCode
    
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
    
    def copy(self):
        if self.data:
            Data = self.data.copy()
        else:
            Data = None
        return TableHDU(Data, self.header.ascard.copy())
    
    def verify(self):
        req_kw = [
            ('XTENSION', "val == 'TABLE   '"),
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
    
    fitsCode = {
        'I8':'B', 'i16':'I', 'i32':'J', \
        'f32':'E', 'f64':'D','F32':'C', 'F64':'M'}
    
    fitsComment = {
        's'  :'character array',
        'I8' :'1-byte integer (unsigned)',
        'i16':'2-byte integer (signed)',
        'i32':'4-byte integer (signed)',
        'f32':'real',
        'f64':'double precision'}
    
    def __init__(self, data=None, cards=None, fields=None, name=None):
        Table.__init__(self, data, cards, name)
        hdr = self.header
        if hdr[0] != 'BINTABLE':
            hdr[0] = 'BINTABLE'
            hdr.ascard[0].comment = 'binary table extension'
        self.recdCode = BinaryField.recdCode
        self.fitsCode = BinaryField.fitsCode

        if data:
            format = string.split(data.format[1:], ',')
            hdr['TFIELDS'] = len(format)
            for j in range(hdr['TFIELDS']):
                val, com = self.fitsType(format[j])
                hdr.update('TFORM'+`j+1`, val, com, after='TFORM'+`j`)

        if fields:
            for field in fields:
                n = str(field.index+1)
                if field.name:
                    hdr.update('TTYPE'+n, field.name, 'name of field',
                               before='TFORM'+str(field.index+2))
                if field.unit:
                    hdr.update('TUNIT'+n, field.unit, 'physical unit of field',
                               before='TFORM'+str(field.index+2))
        #    if self.scale != 1.0: cards.append(Card('TSCAL'+n, self.scale,''))
        #    if self.zero != 0.0:  cards.append(Card('TZERO'+n, self.zero, ''))
        #    if self.null:         cards.append(Card('TNULL'+n, self.null, ''))
        #    if self.disp:         cards.append(Card('TDISP'+n, self.disp, ''))
        #    if self.heap:         cards.append(Card('THEAP'+n, self.heap, ''))
        #    if self.dimn:         cards.append(Card('TDIM' +n, self.dimn, ''))
        #
        #  cache column names, if any.
        #self.__field = {}
        #for j in range(hdr['TFIELDS']):
        #    n = str(j+1)
        #    if hdr.has_key('TTYPE'+n):
        #        self.__field[hdr['TTYPE'+n]] = j
    
    def __getitem__(self, key):
        """ return a field (column) as a (record) array """

        if type(key) == types.StringType:
            for j in range(self.header['TFIELDS']):
                if self.header.ascard.has_key('TTYPE'+`j+1`):
                    key = j
                    break
            else:
                raise KeyError, key
        return self.data[:,key]
    
    def format(self):
        format = ''
        for j in range(self.header['TFIELDS']):
            valu = string.rstrip(self.header['TFORM'+`j+1`])
            code, size = self.recdCode[valu[-1:]], 1
            if valu[:-1]:
                size = eval(valu[:-1])
            if code == 's':
                code, size = code+str(size), 1
            format = format + size*(code+',')
        else:
            format = '>' + format[:-1]
        return format
    
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
        return BinTableHDU(Data, self.header.ascard.copy())
    
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


class FITS(UserList.UserList):

    """FITS class"""
    
    blockLen = 2880 # set the FITS block size
    
    TRUE  = Boolean('T')
    FALSE = Boolean('F')
    
    def __init__(self, name, mode='r'):
        UserList.UserList.__init__(self)
        self.__file = open(name, mode+'b')
        if 'r' in self.__file.mode:
            while 1:
                try:
                    self.data.append(self.__read())
                except EOFError:
                    break
        elif 'w' in self.__file.mode:
            self.data.append(PrimaryHDU())
    
    def __del__(self):
        if 'w' in self.__file.mode:
            for hdu in self.data:
                self.__write(hdu)
        self.__file.close()
    
    def __getitem__(self, key):
        """Get an HDU from the FITS object."""
        if type(key) == types.StringType:
            key = self.index_of(key)
        return self.data[key]
    
    def __setitem__(self, key, hdu):
        """Set an HDU FITS item."""
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        if type(key) == types.StringType:
            key = self.index_of(key)
        self.data[key] = hdu
    
    def __delitem__(self, key):
        """Delete an HDU from the FITS object."""
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        if type(key) == types.StringType:
            key = self.index_of(key)
        del self.data[key]
    
    def __getslice__(self, i, j):
        """Get a FITS slice"""
        return self.data[i:j]
        
    def __setslice__(self, i, j, hdus):
        """Set an HDUs"""
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        if type(hdus) == types.ListType:
            self.data[i:j] = hdus
    
    def __delslice__(self, i, j, hdus):
        """Delete a slice of HDUs"""
        if 'r' in self.__.file.mode:
            raise TypeError, "FITS object is read-only"
        del self.data[i:j]
    
    def index_of(self, key):
        """Get the index of an HDU from the FITS object."""
        for j in range(len(self.data)):
            if self.data[j].name == key:
                return j
        else:
            raise KeyError, key
    
    def __readblock(self):
        block = self.__file.read(FITS.blockLen)
        if len(block) == 0:
            raise EOFError
        elif len(block) != FITS.blockLen:
            raise IOError, 'Block length is not %d: %d' % (FITS.blockLen, 
                                                         len(block))
        cards = []
        for i in range(0, FITS.blockLen, Card.length):
            try:
                cards.append(Card('').fromstring(block[i:i+Card.length]))
            except ValueError:
                if Card._Card__keywd_RE.match(string.upper(block[i:i+8])):
                    print "Warning: fixing-up invalid keyword: '%s'"%card[:8]
                    block[i:i+8] = string.upper(block[i:i+8])
                    cards.append(Card('').fromstring(block[i:i+Card.length]))
            if cards[-1].key == 'END':
                break
        return cards
    

    def __read(self):
        """ Read one FITS HDU, data portions are not actually read here, but the
		beginning locations are computed """

        kards = CardList(self.__readblock())
        while not 'END' in kards.keys():
            kards = kards + CardList(self.__readblock())
        else:
            del kards[-1]
        if kards[0].key == 'SIMPLE':
            if 'GROUPS' in kards.keys() and kards['GROUPS'].value == FITS.TRUE:
                hdu = GroupsHDU(cards=kards)
            elif kards[0].value == FITS.TRUE:
                hdu = PrimaryHDU(cards=kards)
            else:
                raise IOError, "non-standard primary header"
        elif kards[0].key == 'XTENSION':
            xtension = string.rstrip(kards[0].value)
            if xtension == 'TABLE':
                hdu = TableHDU(cards=kards)
            elif xtension == 'IMAGE':
                hdu = ImageHDU(cards=kards)
            elif xtension == 'BINTABLE':
                hdu = BinTableHDU(cards=kards)
            else:
                raise IOError, "non-standard extension: %s" % xtension
        else:
            raise IOError, "non-standard HDU, expecting 'SIMPLE'"\
                  " or 'XTENSION' keyword"

        hdu._file = self.__file
        hdu._data = self.__file.tell()	# locate the beginning of the data area
        self.__file.seek(hdu.size()+padLength(hdu.size()), 1)
        hdu.verify()
        return hdu
    
    def __write(self, hdu):
        """Write FITS HDUs"""
        block = str(hdu.header.ascard) + str(Card('END'))
        block = block + padLength(len(block))*' '

        if len(block)%FITS.blockLen != 0:
            raise IOError
        self.__file.write(block)

        if hdu.data != None:
            block = hdu.data.tostring()
            if len(block) > 0:
                block = block + padLength(len(block))*'\0'
                if len(block)%FITS.blockLen != 0:
                    raise IOError
                self.__file.write(block)
    
    def info(self):
        results = "Filename: %s\nNo.    Name         Type"\
                  "      Cards   Shape        Format\n"%self.__file.name
        for j in range(len(self.data)):
            results = results + "%-3d  %s\n"%(j, self.data[j].summary())
        return results


if __name__ == '__main__':

    print "\n---start a little internal testing..."
    print "\n---open '%s' read-only..." % sys.argv[1]
    fd = FITS(sys.argv[1])

    print "\n---print the file's information..."
    print fd.info()

    print "\n---print out the second card of the primary header..."
    print fd[0].header.ascard[1]
    
    print "\n---print out the value of NAXIS of the 1st extension header..."
    print fd[1].header['naxis']
    
    print "\n---close the file..."
    del fd

# Local Variables:
# py-indent-offset: 4
# End:
