#!/usr/bin/env python1.5

"""  A module for reading and writing Flexible Image Transport System
  (FITS) files.  This file format was endorsed by the International
  Astronomical Union in 1999 and mandated by NASA as the standard format
  for storing high energy astrophysics data.  For details of the FITS
  standard, see the NASA/Science Office of Standards and Technology
  publication, NOST 100-2.0."""

import re, string, struct, types
import UserList
import Numeric, record

version = '0.3.1'

#   Utility Functions

#def littleEndian():
#    import struct
#    return struct.unpack('b', struct.pack('i', 1)[-1])[0]

def padLength(stringLen):
    return (FITS.blockLen - stringLen%FITS.blockLen)%FITS.blockLen

def tableSize(axes):
    if len(axes) > 0:
        size = 1
        for j in range(len(axes)):
            size = size*axes[j]
    else:
        size = 0
    return size

__octalRegex = re.compile(r'([+-]?)0+([1-9][0-9]*)')

def _eval(number):
    "Converts a numeric string value (integer or floating point)"
    "to a Python integer or float converting integers greater than"
    "32-bits to Python long-integers and octal strings to integers"
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

class Boolean:
    "Boolean type class"
    
    def __init__(self, bool):
        self.__bool = bool
    
    def __cmp__(self, other):
        return cmp(str(self), str(other))
    
    def __str__(self):
        return self.__bool


class Card:
    "FITS card class: Corresponds to an 80 character string used"
    "in each line of the header."
    
    length = 80
    
    __comment_RE  = re.compile(r'[ -~]{72}')
    __keywd_RE = re.compile(r'[A-Z0-9_-]* *')
    __numr = r'[+-]?(?:\.\d+|\d+(?:\.\d*)?)(?:[deDE][+-]?\d+)?'
    __value_RE = re.compile(
        r'(?P<valu_field> *'
        r'(?P<valu>'
        r'(?P<strg>\'[ -~]*\')[ /\z]?|'
        r'(?P<bool>[FT])|'
        r'(?P<numr>'+__numr+')|'
        r'(?P<cplx>\( *(?P<real>'+__numr+') *, *(?P<imag>'+__numr+') *\))'
        r') *)'
        r'(?P<comm_field>'
        r'(?P<sepr>/ *)(?P<comm>[ -~]*)?)?')
    __format = r'%[-+0 #]*\d*(?:\.\d*)?[csdiufEG]'
    __format_RE= re.compile(
        r'(?P<valfmt> *'+__format+r' *)'\
        r'(?:(?P<sepfmt>/[ -$&-~]*)'\
        r'(?P<comfmt>'+__format+r'[ -~]*)?)?$')

    __comment_keys = ['', 'COMMENT', 'HISTORY', 'END']
    
    def __init__(self, key, value=None, comment=None, format=None):
        "Create an 80 character record from the key, value, and comment"
        
        #  check keyword for type, length, and invalid characters
        if type(key) != types.StringType:
            raise ValueError, "keyword is not StringType '%s'"%key
        if len(key) > 8:
            raise ValueError, "keyword length is > 8 characters '%s'"%key
        if not Card.__keywd_RE.search(key):
            raise ValueError, "keyword has unsupported character '%s'"%key
        
        #  check for card type and value, and begin creating card
        if key in Card.__comment_keys:
            if comment:
                raise ValueError, "card contains comment '%s'"%key
            if key == 'END' or type(value) == types.NoneType:
                value = ''
            if type(value) != types.StringType:
                raise ValueError, "card comment is not StringType '%s'"%key
            card = '%-8s%-72s' % (key, '%-72s' % value[:72])
        elif format:
            fmt = Card.__format_RE.match(format)
            if not fmt:
                raise ValueError, "card has invalid format string '%s'"%key
            card = ('%-8s= '+ fmt.group('valfmt')) % (key, value)
            if fmt.group('sepfmt'):
                card = card + fmt.group('sepfmt')
            if fmt.group('comfmt') and comment:
                card = card + fmt.group('comfmt') % comment
        else:
            card = '%-8s= %20s' % (key, self.__asString(value))
            comLen = Card.length - (len(card) + 3)
            if comment and comLen > 15:
                card = card + ' / %-*s' % (comLen, comment[:comLen])
        card = card + (Card.length - len(card))*' '
        if len(card) != Card.length:
            raise ValueError, "Card length is %d characters"%len(card)
        self.__dict__['_Card__card'] = card
    
    def __getattr__(self, attr):
	"Get a card attribute"
        key = string.rstrip(self.__card[:8])
	if   attr == 'key':
            return key
	elif attr == 'value':
            if key in Card.__comment_keys:
                value = self.__card[8:]
            else:
                valu = Card.__value_RE.match(self.__card[10:])
                if   valu.group('bool'):
                    value = Boolean(valu.group('bool'))
                elif valu.group('strg'):
                    value = string.rstrip(re.sub("''", "'", \
                                                 valu.group('strg')[1:-1]))
                elif valu.group('numr'):
                    value = _eval(valu.group('numr'))
                elif valu.group('cplx'):
                    value = _eval(valu.group('real')) + \
                            _eval(valu.group('imag'))*1j
                else:
                    value = None
            return value
	elif attr == 'comment':
            valu = Card.__value_RE.search(self.__card[10:])
            if valu.group('comm'):
                value = valu.group('comm')
            else:
                value = None
            return value
        else:
            raise AttributeError, attr
    
    def __setattr__(self, attr, value):
        "Set a Card attribute"
        
        key = string.rstrip(self.__card[:8])
        if   attr == 'key':
            # check card and value keywords for compatibility
            if not ((key in Card.__comment_keys and \
                     value in ['', 'COMMENT', 'HISTORY']) or \
                    (self.__card[8:10] == '= ' and \
                     not value in Card.__comment_keys)):
                raise ValueError, 'Card and value keywords are not compatible'
            card = "%-8s" % value + self.__card[8:]
        elif attr == 'value':
            if key in Card.__comment_keys:
                card = '%-8s%-72s' % (key, '%-72s' % value[:72])
            else:
                card = '%-8s= ' % key
                valu = Card.__value_RE.match(self.__card[10:])
                # check card for fixed or free format
                if (valu.group('strg') and valu.start('strg') == 0) or \
                   valu.end('valu') == 20:
                    # if fixed format, then write it as fixed format
                    if type(value) == types.StringType:
                        card = card + '%-20s' % self.__asString(value)
                    else:
                        card = card + '%20s' % self.__asString(value)
                else:
                    # if free format, then write it as free format
                    card = card + '%*s' % ((10+valu.end('valu')-len(card)),\
                                           self.__asString(value))
                # check for comment field
                if valu.group('comm_field'):
                    card = card + (10+valu.start('sepr')-len(card))*' '
                    card = card + \
                           valu.group('comm_field')[:Card.length-len(card)]
        elif attr == 'comment':
            # check for comment attribute
            if key in Card.__comment_keys:
                raise ValueError, 'Comment keywords have no comment attribute'
            valu = Card.__value_RE.search(self.__card[10:])
            card = self.__card[:10+valu.end('valu_field')]
            if valu.group('comm_field'):
                card = card + valu.group('sepr')
                card = card + value[:Card.length-len(card)]
        else:
            raise AttributeError, attr
        card = card + (Card.length - len(card))*' '
        if len(card) != Card.length:
            raise ValueError, "Card length is %d characters"%len(card)
        self.__dict__['_Card__card'] = card
    
    def __str__(self):
        return self.__card
    
    def fromstring(self, card):
        "Parse a card (an 80 char string) for the keyword, value,"
        "comment, and format (fixed or free)"
        
        if len(card) != Card.length:
            raise ValueError, "card length != 80: %d"%len(card)
        if   card[:3] == 'END':
            if card[3:] != 77*' ':
                raise ValueError, "invalid END card\n'%s'"%card
        elif card[:8] in ['        ', 'COMMENT ', 'HISTORY ']:
            if not Card.__comment_RE.match(card[8:]):
                raise ValueError, "invalid comment card\n'%s'"%card
        elif card[8:10] == '= ':
            if not Card.__keywd_RE.match(card[:8]):
                raise ValueError, "invalid keyword:'%s'"%card[:8]
            if not Card.__value_RE.match(card[10:]):
                raise ValueError, "invalid value type:'%s'"%card[10:]
        else:
            raise ValueError, "invalid card syntax\n'%s'"%card
	self.__dict__['_Card__card'] = card
        return self
    
    def __asString(self, value):
        if   isinstance(value, Boolean):
            res = "%s" % value
        elif type(value) == types.StringType:
            res = "%-20s" % ("'%-8s'" % re.sub("'", "''", value))
        elif type(value) == types.IntType:
            res = "%d" % value
        elif type(value) == types.LongType:
            res = ("%s" % value)[:-1]
        elif type(value) == types.FloatType:
            res = "%#G" % value
        elif type(value) == types.ComplexType:
            res = "(%#8G, %#8G)" % (value.real, value.imag)
        else:
            raise TypeError, value
        return res


class Header(UserList.UserList):
    "A FITS card list"
    
    def __init__(self, cards=None):
        "Initialize the card list in the Header."
        UserList.UserList.__init__(self, cards)
    
    def __getitem__(self, key):
        "Get a card from the Header.\n"\
        "Note: a keyword returns a value, and an index a card."
        if type(key) == types.StringType:
            return self.data[self.index_of(key)].value
        else:
            return self.data[key]
    
    def __setitem__(self, key, value):
        "Set a card in the Header.\n"\
        "Note: a keyword sets a value, and an index a card."
        if type(key) == types.StringType:
            self.data[self.index_of(key)].value = value
        else:
            self.data[key] = value
    
    def __delitem__(self, key):
        "Delete a card from the Header."
        if type(key) == types.StringType:
            key = self.index_of(key)
        del self.data[key]
    
    def keys(self):
        "Return a list of all keywords from the Header."
        keys = []
        for card in self.data:
            keys.append(card.key)
        return keys
    
    def items(self):
        "Return a list of all keyword-value pairs from the Header."
        cards = []
        for card in self.data:
            cards.append((card.key, card.value))
        return cards
    
    def has_key(self, key):
        "Test for a keyword in the Header."
        for card in self.data:
            if card.key == key:
                return 1
        else:
            return 0
    
    def get(self, key, default=None):
        "Get a keyword value from the Header.\n"\
        "If no keyword is found, return the default value."
        for card in self.data:
            if card.key == key:
                return card.value
        else:
            return default
    
    def update(self, key, value, comment=None, before=None, after=None):
        if self.has_key(key):
            j = self.index_of[key]
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
        "Get the index of a keyword in the Header."
        for j in range(len(self.data)):
            if self.data[j].key == key:
                return j
        else:
            raise KeyError, key
    
    def copy(self):
        return Header(self.data[:])
    
    def __repr__(self):
        "Format a list of cards into a string"
        block = ''
        for card in self:
            block = block + str(card)
            if len(block) % Card.length != 0:
                raise CardLen, card
        return block


class Array:
    "FITS data class"

    #  Attributes:
    #   header:  type of array
    #   data:  shape of array
    #
    #  Class data:
    #   _file:  file associated with array          (None)
    #   _data:  starting byte of data block in file (None)
    
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
            self.header['BITPIX'] = Array.ImgCode[data.typecode()]
            axes = list(data.shape)
            axes.reverse()
            self.header['NAXIS']  = len(axes)
            for j in range(len(axes)):
                self.header['NAXIS'+str(j+1)] = axes[j]
            self.data = data
        elif type(data) == types.NoneType:
            pass
        else:
            raise ValueError, "incorrect array type"
        self.name = name
	self.autoscale = 1
    
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
                code = Array.NumCode[self.header['BITPIX']]
                zero = Numeric.array(self.header.get('BZERO', 0), code)
                scale = Numeric.array(self.header.get('BSCALE', 1), code)
                self.data = Numeric.fromstring(blok, code)
                if Numeric.LittleEndian:
                    self.data.byteswapped()
                if self.autoscale:
                    self.data = scale*self.data + zero
                self.data.shape = self.shape()
        return self.__dict__[attr]
    
    def shape(self):
        naxis = self.header['NAXIS']
        axes = naxis*[0]
        for j in range(naxis):
            axes[j] = self.header['NAXIS'+str(j+1)]
        axes.reverse()
        return tuple(axes)
    
    def size(self):
        size, naxis = 0, self.header['NAXIS']
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size = size*self.header['NAXIS'+str(j+1)]
            size = (abs(self.header['BITPIX'])/8)* \
                   self.header.get('GCOUNT', 1)* \
                   (self.header.get('PCOUNT', 0) + size)
        return size
    
    def summary(self):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data:
            shape, format = self.data.shape, self.data.typecode()
        else:
            shape, format = (), ''
        return "%-10s  %-11s  %5d  %-12s  %s"%\
               (self.name, type, len(self.header), shape, format)
    
    def verify(self):
        req_kw = [
            ('SIMPLE',   "val == FITS.TRUE or val == FITS.FALSE"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0")]
        for j in range(self.header['NAXIS']):
            req_kw.append(('NAXIS'+str(j+1), "val >= 0"))
        for j in range(len(req_kw)):
            key, val = self.header[j].key, self.header[j].value
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'"%self.header[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'"%self.header[j]


class PrimaryHDU(Array):
    "FITS Primary Array Header-Data Unit"
    
    def __init__(self, data=None, cards=None):
        Array.__init__(self, data, cards, 'PRIMARY')
    
    def copy(self):
        if self.data:
            data = self.data.copy()
        else:
            data = None
        return PrimaryHDU(data, self.header.copy())


class ImageHDU(Array):
    "FITS Image Extension Header-Data Unit"
    
    def __init__(self, data=None, cards=None, name=None):
        Array.__init__(self, data, cards, name)
        #  set extension name
        if not name and self.header.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name
    
    def __setattr__(self, attr, value):
        "Set an Array HDU attribute"
        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.has_key('EXTNAME'):
                self.header['EXTNAME'] = value
            else:
                self.header.append(Card('EXTNAME', value, 'extension name'))
        self.__dict__[attr] = value
    
    def copy(self):
        if self.data:
            data = self.data.copy()
        else:
            data = None
        return ImageHDU(data, self.header.copy())
    
    def verify(self):
        req_kw = [
            ('XTENSION', "val == 'IMAGE'"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0")]
        for j in range(self.header['NAXIS']):
            req_kw.append(('NAXIS'+str(j+1), "val >= 0"))
        req_kw = req_kw + [
            ('PCOUNT',   "val == 0"),
            ('GCOUNT',   "val == 1")]
        for j in range(len(req_kw)):
            key, val = self.header[j].key, self.header[j].value
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'"%self.header[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'"%self.header[j]


class GroupsHDU(Array):
    "FITS Random Groups Header-Data Unit"
    
    def __init__(self, data=None, cards=None, groups=None, name=None):
        Array.__init__(self, data, cards, 'PRIMARY')
    
    def size(self):
        size, naxis = 0, self.header['NAXIS']
        if naxis > 0:
            size = self.header['NAXIS1']
            for j in range(1, naxis):
                size = size*self.header['NAXIS'+str(j+1)]
            size = (abs(self.header['BITPIX'])/8)*self.header['GCOUNT']* \
                   (self.header['PCOUNT'] + size)
        return size
    
    def copy(self):
        if self.data:
            data = self.data.copy()
        else:
            data = None
        return GroupsHDU(data, self.header.copy())
    
    def verify(self):
        hdr = self.header
        req_kw = [
            ('SIMPLE',   "val == FITS.TRUE or val == FITS.FALSE"),
            ('BITPIX',   "val in [8, 16, 32, -32, -64]"),
            ('NAXIS',    "val >= 0"),
            ('NAXIS1',   "val == 0")]
        for j in range(1, hdr['NAXIS']+1):
            req_kw.append(('NAXIS'+str(j+1), "val >= 0"))
        for j in range(len(req_kw)):
            key, val = hdr[j].key, hdr[j].value
            if not key == req_kw[j][0]:
                raise "Required keyword not found:\n'%s'"%hdr[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'"%hdr[j]
        nec_kw = [
            ('GROUPS',   "val == FITS.TRUE"),
            ('PCOUNT',   "val >= 0"),
            ('GCOUNT',   "val >= 0")]
        for kw in nec_kw:
            if not hdr.has_key[kw[0]]:
                raise "Required keyword not found:\n'%s'"%\
                      hdr[hdr.index_of[kw[0]]]
            val = hdr[kw[0]]
            if not eval(kw[1]):
                raise "Invalid keyword type or value:\n'%s'"%\
                      hdr[hdr.index_of[kw[0]]]


class Field:
    "FITS field class: Defines fields used in data tables"
    
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
        if data:
            self.code = string.split(data.format[1:], ',')[col]
    
    def __repr__(self):
        "Create a list of field cards for display"
        cards = Header()
        n = str(self.column+1)
        if self.name:         cards.append(Card('TTYPE'+n, self.name,
                                                'label of field'))
        cards.append(Card('TFORM'+n, Field.binCode[self.code], \
                          'data type of field: %s' % \
                          Field.codestr[self.code]))
        if self.unit:         cards.append(Card('TUNIT'+n, self.unit,
                                                'physical unit of field'))
        if self.scale != 1.0: cards.append(Card('TSCAL'+n, self.scale, ''))
        if self.zero != 0.0:  cards.append(Card('TZERO'+n, self.zero, ''))
        if self.null: 	      cards.append(Card('TNULL'+n, self.null, ''))
        return cards


class ASCIIField:
    
    # Maps FITS types to recarray types, and vice versa
    recdCode = {'A':'s', 'I':'i16', 'F':'f32', 'E':'f32', 'D':'f64'}
    fitsCode = {'s':'A', 'i16':'I', 'f32':'F', 'f32':'E', 'f64':'D'}
    
    def __init__(self, col, data=None, cards=None, name=None):
        "Creates a ASCII Field type"
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
        if data:
            self.__code = string.split(data.format[1:], ',')[col]
    
    def __repr__(self):
        "Create a list of field cards for display"
        cards = Header()
        n = str(self.__column+1)
	cards.append(Card('TBCOL'+n, self.__start, ''))
        cards.append(Card('TFORM'+n, ASCIIField.code[self.__code], \
                          'data type of field: %s' % \
                          ASCIIField.codestr[self.__code]))
        if self.__name:         cards.append(Card('TTYPE'+n, self.__name, ''))
        if self.__unit:         cards.append(Card('TUNIT'+n, self.__unit, ''))
        if self.__scale != 1.0: cards.append(Card('TSCAL'+n, self.__scale, ''))
        if self.__zero != 0.0:  cards.append(Card('TZERO'+n, self.__zero, ''))
        if self.__null: 	cards.append(Card('TNULL'+n, self.__null, ''))
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
        "Creates a Field type"
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
            key = 'TFORM'+str(j+1)
            if not hdr.has_key[kw]:
                raise "Required keyword not found:\n'%s'"%\
                      hdr[hdr.index_of[key]]
            val = hdr[key]
            if not type(val) == types.StringType:
                raise "Invalid keyword type or value:\n'%s'"%\
                      hdr[hdr.index_of[key]]
            for kw in res_kw:
                key = kw[0]+str(j+1)
                if hdr.has_key(key):
                    val = hdr[key]
                    if not eval(kw[1]):
                        raise "Invalid keyword type or value:\n'%s'"%\
                              hdr[hdr.index_of[key]]
        
        
    #def __repr__(self):
    #    "Create a list of field cards for display"
    #    cards = Header()
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
    "FITS data table class"

    #  Attributes:
    #   header:  type of table
    #   data:  shape of table
    #
    #  Class data:
    #  _file:  file associated with table          (None)
    #  _data:  starting byte of data block in file (None)
    
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
            #self.header['NAXIS1'] = data.formatsize
            self.header['NAXIS1'] = len(data[0].tostring())
            self.header['NAXIS2'] = data.shape[0]
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
        return self.__dict__[attr]
    
    def __setattr__(self, attr, value):
        "Set an Array HDU attribute"
        if attr == 'name' and value:
            if type(value) != types.StringType:
                raise TypeError, 'bad value type'
            if self.header.has_key('EXTNAME'):
                self.header['EXTNAME'] = value
            else:
                self.header.append(Card('EXTNAME', value, 'extension name'))
        self.__dict__[attr] = value
    
    def shape(self):
        return (self.header['NAXIS2'], self.header['NAXIS1'])
    
    def size(self):
        size, naxis = 0, self.header['NAXIS']
        if naxis > 0:
            size = 1
            for j in range(naxis):
                size = size*self.header['NAXIS'+str(j+1)]
            size = (abs(self.header['BITPIX'])/8)* \
                   self.header.get('GCOUNT', 1)* \
                   (self.header.get('PCOUNT', 0) + size)
        return size
    
    def summary(self):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data:
            shape, format = self.data.shape, self.data.format
        else:
            shape, format = (), ''
        return "%-10s  %-11s  %5d  %-12s  %s"%\
               (self.name, type, len(self.header), shape, format)


class TableHDU(Table):
    
    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')
    
    def __init__(self, data=None, cards=None, name=None):
        Table.__init__(self, data, cards, name)
        if self.header[0].value != 'TABLE':
            self.header[0].value   = 'TABLE'
            self.header[0].comment = 'ASCII table extension'
        self.recdCode = ASCIIField.recdCode
        self.fitsCode = ASCIIField.fitsCode
    
    def format(self):
        strfmt, strlen = '', 0
        for j in range(self.header['TFIELDS']):
            bcol = self.header['TBCOL'+str(j+1)]
            valu = self.header['TFORM'+str(j+1)]
            fmt  = self.__format_RE.match(valu)
            if fmt:
                code, width, prec = fmt.group('code', 'width', 'prec')
            else:
                raise ValueError, valu
            size = bcol-strlen-1+eval(width)
            strfmt = strfmt + 's'+str(size) + ','
            strlen = strlen + size
        else:
            strfmt = '>' + strfmt[:-1]
        return strfmt
    
    def copy(self):
        if self.data:
            data = self.data.copy()
        else:
            data = None
        return TableHDU(data, self.header.copy())
    
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
            key, val = self.header[j].key, self.header[j].value
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'"%self.header[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'"%self.header[j]


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
        if hdr[0].value != 'BINTABLE':
            hdr[0].value   = 'BINTABLE'
            hdr[0].comment = 'binary table extension'
        self.recdCode = BinaryField.recdCode
        self.fitsCode = BinaryField.fitsCode
        if data:
            format = string.split(data.format[1:], ',')
            hdr['TFIELDS'] = len(format)
            for j in range(hdr['TFIELDS']):
                val, com = self.fitsType(format[j])
                hdr.update('TFORM'+str(j+1), val, com, after='TFORM'+str(j))
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
        if type(key) == types.StringType:
            for j in range(hdr['TFIELDS']):
                if hdr.has_key('TTYPE'+str(j+1)):
                    key = j
                    break
            else:
                raise KeyError, key
        return self.data[:,key]
    
    def format(self):
        format = ''
        for j in range(self.header['TFIELDS']):
            valu = self.header['TFORM'+str(j+1)]
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
            data = self.data.copy()
        else:
            data = None
        return BinTableHDU(data, self.header.copy())
    
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
            key, val = self.header[j].key, self.header[j].value
            if not key == req_kw[j][0]:
                raise "Invalid keyword ordering:\n'%s'"%self.header[j]
            if not eval(req_kw[j][1]):
                raise "Invalid keyword type or value:\n'%s'"%self.header[j]
        # BinaryField.verify()


class FITS(UserList.UserList):
    "FITS class"
    
    blockLen = 2880 # set the FITS block size
    
    TRUE  = Boolean('T')
    FALSE = Boolean('F')
    
    def __init__(self, name, mode='r'):
        UserList.UserList.__init__(self)
        self.__file = open(name, mode+'b')
        if   'r' in self.__file.mode:
            while 1:
                try:
                    self.data.append(self.__read())
                except EOFError:
                    break
        elif 'w' in self.__file.mode:
            self.data.append(PrimaryHDU())
    
    def __del__(self):
        if   'w' in self.__file.mode:
            for hdu in self.data:
                self.__write(hdu)
        self.__file.close()
    
    def __getitem__(self, key):
        "Get an HDU from the FITS object."
        if type(key) == types.StringType:
            key = self.index_of(key)
        return self.data[key]
    
    def __setitem__(self, key, hdu):
        "Set an HDU FITS item."
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        if type(key) == types.StringType:
            key = self.index_of(key)
        self.data[key] = hdu
    
    def __delitem__(self, key):
        "Delete an HDU from the FITS object."
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        if type(key) == types.StringType:
            key = self.index_of(key)
        del self.data[key]
    
    def __getslice__(self, i, j):
        "Get a FITS slice"
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        return self.data[i:j]
        
    def __setslice__(self, i, j, hdus):
        "Set an HDUs"
        if 'r' in self.__file.mode:
            raise TypeError, "FITS object is read-only"
        if type(hdus) == types.ListType:
            self.data[i:j] = hdus
    
    def __delslice__(self, i, j, hdus):
        "Delete a slice of HDUs"
        if 'r' in self.__.file.mode:
            raise TypeError, "FITS object is read-only"
        del self.data[i:j]
    
    def index_of(self, key):
        "Get the index of an HDU from the FITS object."
        for j in range(len(self.data)):
            if self.data[j].name == key:
                return j
        else:
            raise KeyError, key
    
    def __blockio(self):
        block = self.__file.read(FITS.blockLen)
        if len(block) == 0:
            raise EOFError
        elif len(block) != FITS.blockLen:
            raise IOError, 'Block length is not %d: %d'%(FITS.blockLen, 
                                                         len(block))
        cards = []
        for i in range(0, FITS.blockLen, Card.length):
            cards.append(Card('').fromstring(block[i:i+Card.length]))
            if cards[-1].key == 'END':
                break
        return cards
    
    def __read(self):
        "Read a FITS HDU"
        
        header = cards = Header(self.__blockio())
        while not 'END' in cards.keys():
            cards  = Header(self.__blockio())
            header = header + cards
        else:
            del header[-1]
        if   header[0].key == 'SIMPLE':
            if   'GROUPS' in header.keys() and header['GROUPS'] == FITS.TRUE:
                hdu = GroupsHDU(cards=header)
            elif header[0].value == FITS.TRUE:
                hdu = PrimaryHDU(cards=header)
            else:
                raise IOError, "non-standard primary header"
        elif header[0].key == 'XTENSION':
            if   header[0].value == 'TABLE':
                hdu = TableHDU(cards=header)
            elif header[0].value == 'IMAGE':
                hdu = ImageHDU(cards=header)
            elif header[0].value == 'BINTABLE':
                hdu = BinTableHDU(cards=header)
            else:
                raise IOError, "non-standard extension"
        else:
            raise IOError, "non-standard HDU, expecting 'SIMPLE'"\
                  " or 'XTENSION' keyword"
        hdu._file = self.__file
        hdu._data = self.__file.tell()
        self.__file.seek(hdu.size()+padLength(hdu.size()), 1)
        hdu.verify()
        return hdu
    
    def __write(self, hdu):
        "Write FITS HDUs"
        block = str(hdu.header) + str(Card('END'))
        block = block + padLength(len(block))*' '
        if len(block)%FITS.blockLen != 0:
            raise IOError
        self.__file.write(block)
        if hdu.data:
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

    import os

    for file in os.listdir('.'):
        if file[-4:] == 'fits':
            try:
                fits = FITS(file)
                print fits.info()
            except:
                print file
                continue
            #fits.close()

# Local Variables:
# py-indent-offset: 4
# End:
