#!/usr/bin/env python2.1

"""A module for reading and writing FITS files.

A module for reading and writing Flexible Image Transport System
(FITS) files.  This file format was endorsed by the International
Astronomical Union in 1999 and mandated by NASA as the standard format
for storing high energy astrophysics data.  For details of the FITS
standard, see the NASA/Science Office of Standards and Technology
publication, NOST 100-2.0.

"""

version = '0.5.0 (Jul 20, 2001)'

from __future__ import nested_scopes

import os, mmap, re, string, types, sys
import __builtin__, UserList, array
#import exceptions,

import warnings
def fitswarn(message, category, filename, lineno, file=None):
    """A function to print warning messages about FITS files.

    This replaces the standard print function in the warnings module.
    """

    if file is None:
        file = sys.stderr
    file.write("%s: %s\n" % (str(category)[11:], message))

warnings.showwarning = fitswarn

try:
    import Numeric
except ImportError:
    print """Numeric module is not installed.  Image data is not accessible"""

try:
    import record
except ImportError:
    print """record module is not installed.  Table data is not accessible"""

#   Utility Functions

def _eval(number):

    """Trap octal and long integers

    Convert a numeric string value (integer or floating point)
    to a Python integer or float, converting integers greater than
    32-bits to Python long-integers and octal strings to integers.

    """

    __octalRegex = re.compile(r'([+-]?)0+([1-9][0-9]*)')

    try:
        value = eval(number)
    except OverflowError:
        value = eval(number+'L')
    except SyntaxError:
        octal = __octalRegex.match(number)
        if octal:
            value = _eval(''.join(octal.group(1,2)))
        else:
            raise ValueError, number
    return value

def File_blockPadLen(stringLen):

    """A function to calculate the number of padding characters needed
    for the last block (of 2880 bytes) in the Header.
    """

    return (File.blockLen - stringLen%File.blockLen)%File.blockLen


#   FITS Classes

#   A base class for FITS specific exceptions of which there are
#   three: Warning, Severe, and Critical/Fatal.  Warning messages are
#   always caught and their messages printed.  Execution resumes.
#   Severe errors are those which can be fixed-up in many cases, so
#   that execution can continue, whereas Critical Errors are so severe
#   execution can not continue under any situation.
#
#
#class FatalError(exceptions.Exception):
#    """This level of exception raises an unrecoverable error."""
#    pass
#
#
#class SevereError(FatalError):
#    """This level of exception raises a recoverable error which is likely
#    to be fixed, so that processing can continue."""
#    pass
#
#
#class Warning(SevereError):
#    """This level of exception raises a warning and allows processing to
#    continue."""
#    pass


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


class Buffer:

    """A mutable character array.

    This class provides a simple array interface to character data
    residing in a file or memory.  If the data resides in a file, then
    memory-mapped file I/O is used by default with standard file I/O
    as a failsafe.  This class is used in conjunction with the
    CardList class to provide list-like behavior for files.  The file
    partition can be of any size or have any offset into the file.
    The size and offset default to 0.
    """

    def __init__(self, size=0, offset=0, file=None, cards=None, map=1):
        """Initialize the buffer partition.

        The arguments for this class are size, offset (in bytes),
        file, and a list of cards.  If the buffer is mapped to a file,
        then the partition offset plus size must be less than the file
        size.
        """

        if size < 0:
            raise ValueError, "partition size is less than zero"
        if offset < 0:
            raise ValueError, "offset is less than zero"
        if file == None:
            self.__data = array.array('c', size*' ')
            if cards != None:
                data = ''.join([str(c) for c in cards])
                self.__data[:len(data)] = array.array('c', data)
        else:
            file.seek(0, 2)
            filelen = file.tell()
            if size > filelen:
                raise ValueError, "partition size is greater than file size"
            self.__data = None
            if map == 1:
                # At least for Linux, mmap returns an invalid mmap object
                # for files of size 0, so we cheap and create a file of
                # size 1, which we test for later.
                if filelen == 0:
                    file.truncate(1)
                    filelen = 1
                try:
                    self.__data = mmap.mmap(file.fileno(), filelen)
                except ImportError:
                    pass
        self.__file   = file
        self.__offset = offset
        self.__size   = size

    def __len__(self):
        """Return the size of the array."""

        return self.__size

    def __getitem__(self, index):
        """Get a character from the array."""

        if index < 0:
            index += self.__size
        if not (0 <= index < self.__size):
            raise IndexError, "list index out of range"
        if self.__data == None:
            self.__file.seek(self.__offset+index)
            return self.__file.read(1)
        else:
            return self.__data[self.__offset+index]

    def __setitem__(self, index, value):
        """Assign a character to the array."""

        if not (isinstance(value, types.StringType) or \
           isinstance(value, Buffer)):
            raise ValueError, "assigned value must be string or Buffer"
        if index < 0:
            index += self.__size
        if not (0 <= index < self.__size):
            raise IndexError, "list index out of range"
        if len(value) != 1:
            raise ValueError, "length of assigned value != 1"
        if self.__data == None:
            self.__file.seek(self.__offset+index)
            self.__file.write(value)
        else:
            self.__data[self.__offset+index] = value

    def __getslice__(self, start, stop):
        """Get a substring from the array.

        Get a substring beginning at the index start and upto the
        index stop.  The start and stop values default to the
        beginning and end of the array.  The return value is a Python
        string.
        """

        start, stop = self.__setrange(start, stop)
        oset = self.__offset
        if self.__data == None:
            self.__file.seek(oset+start)
            return self.__file.read(stop-start)
        elif self.__file == None:
            return str(self.__data[oset+start: oset+stop])[12:-2]
        else:
            return self.__data[oset+start: oset+stop]

    def __setslice__(self, start, stop, value):
        """Assign a substring to the array.

        Replace a substring beginning at the index start and upto the
        index stop.  The start and stop values default to the
        beginning and end of the list.  The array size cannot change.
        """

        if not (isinstance(value, types.StringType) or \
           isinstance(value, Buffer)):
            raise ValueError, "assigned value must be string or Buffer"
        start, stop = self.__setrange(start, stop)
        oset = self.__offset
        if len(value) != stop-start:
            raise ValueError, "length of assigned value != length of slice"
        if self.__data == None:
            self.__file.seek(oset+start)
            self.__file.write(value)
        elif self.__file == None:
            self.__data[oset+start: oset+stop] = array.array('c', value)
        else:
            self.__data[oset+start: oset+stop] = value

    def __repr__(self):
        """Return a representation of the array."""

        oset = self.__offset
        if self.__data == None:
            self.__file.seek(oset)
            return self.__file.read(self.__size)
        elif self.__file == None:
            return str(self.__data[oset: oset+self.__size])[12:-2]
        else:
            return self.__data[oset: oset+self.__size]

    def view(self, offset, size):
        """Return a view into a Buffer object.

        The view can have a different offset and size from that of the
        base object.
        """

        buff = Buffer()
        buff.__data = self.__data
        buff.__file = self.__file
        buff.__offset = self.__offset+offset
        buff.__size = size
        return buff

    def base(self):
        """Return base (file) object"""

        return self.__file

    def offset(self):
        """Return the offset of the array in the file."""

        return self.__offset

    # The File_blockPadLen function should be moved out.

    def resize(self, newsize):
        """Resize the Buffer object.

        This method will expand or contract the size of the Buffer in
        increments of the block size.  Data following the Buffer will
        be moved to account for the expansion or contraction.
        Different techniques are used to accomplish this depending on
        where the data resides.
        """

        file, data = self.__file, self.__data
        oset, size = self.__offset, self.__size
        newsize += File_blockPadLen(newsize)
        if newsize <= size - File.blockLen:
            if file == None:
                self.__data = array.array('c', str(data[:newsize])[12:-2])
            elif data == None:
                tempfile = os.tmpfile()
                file.seek(oset+size)
                tempfile.write(file.read())
                count = tempfile.tell()
                tempfile.seek(0)
                file.seek(oset+newsize)
                file.write(tempfile.read())
                file.truncate(oset+newsize+count)
                tempfile.close()
            else:
                data.seek(0, 2)
                datalen = data.tell()
                if datalen == 1:
                    datalen = 0
                count = datalen - (oset + size)
                data.move(oset+newsize, oset+size, count)
                data.resize(oset+newsize+count)
                file.truncate(oset+newsize+count)
        elif newsize > size:
            if file == None:
                self.__data = array.array('c', str(data)[12: -2] + \
                                          (newsize - size)*' ')
            elif data == None:
                tempfile = os.tmpfile()
                file.seek(oset+size)
                tempfile.write(file.read())
                tempfile.seek(0)
                file.seek(oset+newsize)
                file.write(tempfile.read())
                file.seek(oset+size)
                file.write((newsize-size)*' ')
                tempfile.close()
            else:
                data.seek(0, 2)
                datalen = data.tell()
                if datalen == 1:
                    datalen = 0
                count = datalen - (oset+size)
                file.truncate(oset+newsize+count)
                data.resize(oset+newsize+count)
                data.move(oset+newsize, oset+size, count)
                data[oset+size: oset+newsize] = (newsize - size)*' '
        self.__size = newsize
        return self.__size

    def __setrange(self, start, stop):
        """A helper method for setting valid start and stop indices of
        a simple slice.
        """

        if start < -self.__size:
            start = 0
        elif start < 0:
            start += self.__size
        elif start > self.__size:
            start = self.__size
        if stop < -self.__size:
            stop = 0
        elif stop < 0:
            stop += self.__size
        elif stop > self.__size:
            stop = self.__size
        return start, stop


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

    def __init__(self, key='', value=None, comment=None, format=None):
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
            raise TypeError, 'key is not StringType'
        key = string.strip(key)
        if len(key) > keyLen:
            raise ValueError, 'key length is >%d' % keyLen
        key = "%-*s" % (keyLen, string.upper(key))
        if not Card.__keywd_RE.match(key):
            raise ValueError, 'key has invalid syntax'

        if isinstance(value, types.StringType) and \
           not self.__comment_RE.match(value):
            raise ValueError, 'value has unprintable characters'

        if comment:
            if not isinstance(comment, types.StringType):
                raise TypeError, 'comment is not StringType'
            if not self.__comment_RE.match(comment):
                raise ValueError, 'comment has unprintable characters'

        #  Create the following card types: comment cards, and free- and
        #  fixed-format value cards.

        #  Create a commentary card
        if key in Card.__comment_keys+['END     ']:
            if comment != None:
                raise AttributeError, 'commentary card has no comment ' \
                      'attribute'
            if key == 'END     ' and not isinstance(value, types.NoneType):
                raise AttributeError, 'END card has no value attribute'
            if isinstance(value, types.NoneType):
                card = '%-*s' % (cardLen, key)
            elif isinstance(value, types.StringType):
                if len(value) > comLen:
                    raise ValueError, 'comment length is >%d' % comLen
                card = '%-*s%-*s' % (keyLen, key, comLen, value)
            else:
                raise TypeError, 'comment is not StringType'

        #  Create a free-format value card
        elif format:
            if "%-8s"%key in Card.__mandatory_keys+["XTENSION"] or \
               key[:5] == 'NAXIS':
                raise ValueError, 'mandatory keys are fixed-format only'
            fmt = Card.__format_RE.match(format)
            if not fmt:
                raise ValueError, 'format has invalid syntax'
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
                    raise ValueError, 'value of old card has invalid syntax'
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
                    raise ValueError, 'comment of old card has invalid syntax'
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
        cardLen = Card.length
        keyLen  = Card.keyLen
        valLen  = Card.valLen

        kard = self.__card
        if kard[:keyLen] == 'END     ':
            raise ValueError, 'cannot modify END card'
        if attr == 'key':
            #  Check keyword for type, length, and invalid characters
            if not isinstance(val, types.StringType):
                raise TypeError, 'key is not StringType'
            key = string.strip(val)
            if len(val) > 8:
                raise ValueError, 'key length is >8'
            val = "%-8s" % string.upper(val)
            if not Card.__keywd_RE.match(val):
                raise ValueError, 'key has invalid syntax'
            #  Check card and value keywords for compatibility
            if val == 'END     ':
                raise ValueError, 'cannot set key to END'
            elif not ((kard[:8] in Card.__comment_keys and \
                     val in Card.__comment_keys) or (kard[8:10] == '= ' and \
                     val not in Card.__comment_keys)):
                raise ValueError, 'old and new card types do not match'
            card = val + kard[8:]
        elif attr == 'value':
            if isinstance(val, types.StringType) and \
               not self.__comment_RE.match(val):
                raise ValueError, 'value has unprintable characters'
            if kard[0:8] not in Card.__comment_keys and kard[8:10] == '= ' :
                #  This is a value card
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise ValueError, 'value of old card has invalid syntax'
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
                        raise ValueError, 'comment length is >%d'%valLen
                    card = '%-*s%-*s' % (keyLen, kard[:8], valLen, val)
                else:
                    raise TypeError, 'comment is not StringType'
        elif attr == 'comment':
            if not isinstance(val, types.StringType):
                raise TypeError, 'comment is not StringType'
            if kard[0:8] not in Card.__comment_keys and kard[8:10] == '= ' :
                #  Then this is value card
                valu = Card.__value_RE.match(kard[10:])
                if valu == None:
                    raise ValueError, 'value of old card has invalid syntax'
                if valu.group('comm_field'):
                    card = kard[:10+valu.end('sepr')] + val
                elif valu.end('valu') > 0:
                    card = '%s / %s' % (kard[:10+valu.end('valu')], val)
                else:
                    card = '%s / %s' % (kard[:10], val)
            else:
                #  This is commentary card
                raise AttributeError, 'commentary card has no comment ' \
                      'attribute'
        else:
            raise AttributeError, attr

        card = '%-*s' % (cardLen, card[:cardLen])
        if isinstance(kard, Buffer):
            kard[:] = card
        else:
            self.__dict__['_Card__card'] = card

    def __repr__(self):
        """Return a card as a printable 80 character string."""
        return "'%s'"%self.__card

    def __str__(self):
        """Return a card as a printable 80 character string."""
        return str(self.__card)

    def fromstring(self, card):
        """Create a card from an 80 character string.

        Verify an 80 character string for valid card syntax in either
        fixed- or free-format.  Create a new card if the syntax is
        valid, otherwise raise an exception.

        """

        cardLen, keyLen, comLen = Card.length, Card.keyLen, Card.comLen

        key = card[:keyLen]
        if len(card) != cardLen:
            raise ValueError, "'%-8s' card has invalid length (!= 80)" % key
        if not Card.__keywd_RE.match(key):
            raise ValueError, "'%-8s' card has invalid syntax (keyword)" % key

        if key == 'END     ':
            if not card[keyLen:] == comLen*' ':
                raise ValueError, "'END     ' card has invalid syntax"
        elif key not in Card.__comment_keys and card[8:10] == '= ' :
            #  Check for fixed-format of mandatory keywords
            valu = Card.__value_RE.match(card[10:])
            if valu == None:
                raise ValueError, "'%-8s' card has invalid syntax (value)" % \
                      key
            elif ((key in Card.__mandatory_keys or card[:5] == 'NAXIS') \
                 and valu.end('valu') != 20) or \
                 (key == 'XTENSION' and valu.start('valu') != 0):
                raise ValueError, "'%-8s' (mandatory keyword) card is not " \
                      "in fixed format" % key
        else:
            if not Card.__comment_RE.match(card[8:]):
                raise ValueError, "'%-8s' (commentary) card has unprintable " \
                      "characters" % key

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
            raise ValueError, 'value length > 70'
        return res


class CardList:

    """The CardList class provides access to the list of Header Cards.

    This class provides a list-like interface to a group of header
    blocks which are mapped as an array of characters.  As the list
    grows and shrinks, the underlying array will be resized in
    multiples of the block size (2880 characters) as necessary.  The
    length of each item is fixed at one Card length (80 characters).

    This class expects the underlying data to provide a view of the
    data as a simple sequence or one-dimensional array of characters,
    like that of a memory-mapped file.  The underyling data can reside
    in memory as a character array, or on disk using memory-mapped or
    standard file I/O.
    """

    def __init__(self, data, ncards=0):
        """Initialize the Card list.

        The arguments of this method are data and ncards.  Only the
        data object must be supplied.  The initial number of Cards in
        the list can be given by ncards, otherwise it defaults to 0.
        """

        itemlen = 80

        if len(data)%File.blockLen:
            raise ValueError, "size is not a multiple of block length (2880)"
        if data.offset()%File.blockLen:
            raise ValueError, "offset is not a multiple of block length (2880)"
        if ncards < 0:
            raise ValueError, "numbers of cards < 0"
        if ncards*itemlen > len(data):
            raise ValueError, "list length > partition length"
        self.__data = data
        self.__itemlen = itemlen
        self.__listlen = ncards

    def size(self):
        """Returns the size of the data buffer."""
        return len(self.__data)

    def __len__(self):
        """Returns the length of the list."""
        return self.__listlen

    def __getitem__(self, index):
        """Get a Card from the list.

        The index can be an integer or a string.  If a string, the
        list will be searched for a keyword matching that name and its
        index will be used.
        """

        if isinstance(index, types.StringType):
            index = self.index_of(index)
        if index < 0:
            index += self.__listlen
        if not (0 <= index < self.__listlen):
            raise IndexError, "list index out of range"
        data, ilen = self.__data, self.__itemlen
        return Card().fromstring(data.view(ilen*index, ilen))

    def __setitem__(self, index, value):
        """Replace a Card in the List.

        The index can be an integer or a string.  If a string, the
        list will be searched for a keyword matching that name and its
        index will be used.
        """

        if not isinstance(value, Card):
            raise ValueError, "%s is not a Card" % str(value)
        if isinstance(index, types.StringType):
            index = self.index_of(index)
        if index < 0:
            index += self.__listlen
        if not (0 <= index < self.__listlen):
            raise IndexError, "list index out of range"
        ilen = self.__itemlen
        self.__data[ilen*index: ilen*(index+1)] = str(value)

    def __delitem__(self, index):
        """Delete a Card from the List.

        The index can be an integer or a string.  If a string, the
        list will be searched for a keyword matching that name and its
        index will be used.  The buffer will contract if the last
        block becomes empty.
        """

        if isinstance(index, types.StringType):
            index = self.index_of(index)
        if index < 0:
            index += self.__listlen
        if not (0 <= index < self.__listlen):
            raise IndexError, "list index out of range"
        ilen = self.__itemlen
        i1, i2 = ilen*index, ilen*self.__listlen
        self.__data[i1: i2] = self.__data[i1+ilen: i2] + ilen*' '
        self.__listlen -= 1
        newsize = self.__listlen*ilen
        self.__data.resize(newsize)

    def __getslice__(self, start, stop):
        """Get several Cards from the list.

        Get Cards beginning at the index start and upto the index
        stop.  The start and stop values default to the beginning and
        end of the list.
        """

        start, stop = self.__setrange(start, stop)
        data, ilen = self.__data, self.__itemlen
        return [Card().fromstring(data.view(j, ilen)) \
                for j in range(ilen*start, ilen*stop, ilen)]

    def __setslice__(self, start, stop, value):
        """Replace several Cards from the list with those from another
        list.

        Replace Cards beginning at the index start and upto the index
        stop.  The start and stop values default to the beginning and
        end of the list.  The list can shrink or expand depending on
        the size of the list being assigned.
        """

        if not isinstance(value, types.ListType):
            raise ValueError, "assigned value is not a List"
        start, stop = self.__setrange(start, stop)
        slen, vlen = stop-start, len(value)
        strval = ''.join([str(val) for val in value])
        ilen = self.__itemlen
        i1, i2, i3 = ilen*start, ilen*stop, ilen*self.__listlen
        if vlen < slen:
            self.__data[i1: i3] = strval + self.__data[i2: i3] + \
                                  (slen-vlen)*ilen*' '
            self.__listlen -= slen-vlen
            newsize = self.__listlen*ilen
            self.__data.resize(newsize)
        elif vlen > slen:
            newsize = (self.__listlen+vlen-slen)*ilen
            self.__data.resize(newsize)
            self.__data[i1: i3+ilen*(vlen-slen)] = strval + self.__data[i2: i3]
            self.__listlen += vlen-slen
        else:
            self.__data[i1: i2] = strval

    def __delslice__(self, start, stop):
        """Delete several Cards from the List.

        Delete Cards beginning at the index start and upto the index
        stop.  The start and stop values default to the beginning and
        end of the list.  The buffer will contract if the last block
        becomes empty.
        """

        start, stop = self.__setrange(start, stop)
        ilen = self.__itemlen
        i1, i2, i3 = ilen*start, ilen*stop, ilen*self.__listlen
        self.__data[i1: i3] = self.__data[i2: i3] + (stop-start)*ilen*' '
        self.__listlen -= stop-start
        newsize = self.__listlen*ilen
        self.__data.resize(newsize)

    def __str__(self):
        """Return a printable version of the list.

        The returned string contains no newline characters.
        """

        ilen = self.__itemlen
        return ''.join([self.__data[j: j+ilen]
                        for j in range(0, ilen*self.__listlen, ilen)])

    def __repr__(self):
        """Return a representation of the list.

        The returned string contains a representation of the Cards in
        the list.
        """

        ilen = self.__itemlen
        strs = [Card().fromstring(self.__data[j: j+ilen])
                for j in range(0, ilen*self.__listlen, ilen)]
        return repr(strs)

    def insert(self, index, value):
        """Insert a Card into the list.

        The buffer will expand if the last block becomes full.
        """

        if not isinstance(value, Card):
            raise ValueError, "%s is not a Card" % str(value)
        if index < 0:
            index += self.__listlen
        if not (0 <= index < self.__listlen):
            raise IndexError, "list index out of range"
        ilen = self.__itemlen
        newsize = (self.__listlen+1)*ilen
        self.__data.resize(newsize)
        i1, i2 = ilen*index, ilen*self.__listlen
        self.__data[i1: i2+ilen] = str(value) + self.__data[i1: i2]
        self.__listlen += 1

    def append(self, value, replace=0):
        """Append a Card to the list

        Insert a new Card in the list before the END Card or replace
        the first blank Card before the END Card, if one exists.  The
        END Card is appended to the list if there is no END Card,
        otherwise an exception is raised.  The buffer will expand if
        the last block becomes full.
        """

        if not isinstance(value, Card):
            raise ValueError, "%s is not a Card" % str(value)
        if self.__listlen == 0 or self[-1].key != 'END':
            j = 0
            while j > -self.__listlen:
                if str(self[j-1]) != str(Card()):
                    break
                j -= 1
            if replace == 1 and j < 0 and value.key != 'END':
                # Do a replace of the 1st blank card at the end of list
                self[j] = value
            else:
                # Do a true append for list-length == 0 or no END card
                ilen = self.__itemlen
                newsize = (self.__listlen+1)*ilen
                self.__data.resize(newsize)
                i1 = ilen*self.__listlen
                self.__data[i1: i1+ilen] = str(value)
                self.__listlen += 1
        elif value.key != 'END':
            j = -1
            while j > -self.__listlen:
                if str(self[j-1]) != str(Card()):
                    break
                j -= 1
            if replace == 1 and j < -1:
                # Do a replace of the 1st blank card at the end of list
                self[j] = value
            else:
                # Do an insert before END card
                self.insert(-1, value)
        else:
            raise ValueError, "can't append card to list"

    def keys(self):
        """Return a list of all keywords from the list."""

        data, ilen = self.__data, self.__itemlen
        return [Card().fromstring(data.view(j, ilen)).key \
                for j in range(0, ilen*self.__listlen, ilen)]

    def index_of(self, index):
        """Get the index of a keyword in the list."""

        index = string.upper(string.strip(index))
        data, ilen, k = self.__data, self.__itemlen, 0
        for j in range(0, ilen*self.__listlen, ilen):
            try:
                if Card().fromstring(data.view(j, ilen)).key == index:
                    return k
                k += 1
            except ValueError:
                pass
        else:
            raise KeyError, index

    def getfill(self):
        """Return the fill characters that pad the last block"""

        data = self.__data
        return data[self.__itemlen*self.__listlen: len(data)]

    def __setrange(self, start, stop):
        """A helper method for setting valid start and stop indices of
        a simple slice.
        """

        if start < -self.__listlen:
            start = 0
        elif start < 0:
            start += self.__listlen
        elif start > self.__listlen:
            start = self.__listlen
        if stop < -self.__listlen:
            stop = 0
        elif stop < 0:
            stop += self.__listlen
        elif stop > self.__listlen:
            stop = self.__listlen
        return start, stop

    #def copy(self):
    #    return CardList(self.__data[:])


class Header:

    """The Header class provides easy access to Card values.

    The Header class is a wrapper around the CardList class providing
    shorthand access to a Card's value, i.e. header[0] is equivalent
    to cardlist[0].value.  Access to Cards is via the ascardlist()
    method or the ascard attribute.
    """

    def __init__(self, cards=None):
        """Initialize the Header class with a list of cards.

        The cards argument (optional) takes a CardList as input.  If
        no CardList is given, the default is to create an empty
        CardList in memory.
        """

        if isinstance(cards, types.ListType):
            self.ascard = CardList(cards)
        else:
            self.ascard = cards

    def __getitem__ (self, key):
        """Get a header keyword value."""

        return self.ascard[key].value

    def __setitem__ (self, key, value):
        """Set a header keyword value."""

        self.ascard[key].value = value

    def ascardlist(self):
        """Returns a CardList."""

        return self.ascard

    def items(self):
        """Return a list of all Card keyword-value pairs from the
        CardList.
        """

        cards = []
        for card in self.ascard:
            cards.append((card.key, card.value))
        return cards

    def has_key(self, key):
        """Test for a Card keyword in the CardList."""

        if not isinstance(key, types.StringType):
            raise TypeError, 'key must be string object'
        key = string.upper(string.strip(key))
        for card in self.ascard:
            if card.key == key:
                return 1
        else:
            return 0

    def get(self, key, default=None):
        """Get a Card value from the CardList.

        If no keyword is found, return the default value (optional).
        """

        key = string.upper(string.strip(key))
        for j in range(len(self.ascard)):
            try:
                card = self.ascard[j]
                if card.key == key:
                    return card.value
            except ValueError:
                continue
        else:
            return default

    def update(self, key, value, comment=None, before=None, after=None):
        """Update a Card value in the CardList.

        The key argument takes either an index or a string value.  If
        a string, the CardList is search for a matching keyword.  If
        none is found, then a new Card is inserted into the CardList,
        if the before or after keyword (optional) arguments are used,
        or appended to the end of the CardList by default.  A Card
        comment (optional) can also be given and will replace the old
        Card comment.
        """

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
        self._file, self._offset, self._data = None, None, None
        self.header = header
        self.data = data
        self.name = None

    def size(self):
        self._file.seek(0, 2)
        return self._file.tell() - self._data

    def summary(self, format):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data != None:
            shape, code = self.data.shape, self.data.typecode()
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

        self._file, self._offset, self._data = None, None, None
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
        if self.data != None:
            shape, code = self.data.shape, self.data.typecode()
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
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)

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
        self._file, self._offset, self._data = None, None, None
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
        if self.data != None:
            shape, code = self.data.shape, self.data.typecode()
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
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)

    def _verifycard(self, card, keywd, test):
        key, val = card.key, card.value
        if not key == keywd:
            raise IndexError, "'%-8s' card has invalid ordering" % key
        if not eval(test):
            raise ValueError, "'%-8s' card has invalid value" % key


class ImageBaseHDU:
    """FITS image data"""

    # mappings between FITS and Numeric typecodes
    NumCode = {8:'b', 16:'s', 32:'l', -32:'f', -64:'d'}
    ImgCode = {'b':8, 's':16, 'l':32, 'f':-32, 'd':-64}

    def __init__(self, data=None, header=None):
        self._file, self._offset, self._data = None, None, None
        if header != None:
            self.header = header
        else:
            cards = [Card('SIMPLE', TRUE, 'conforms to FITS standard'),
                     Card('BITPIX',    8, 'array data type'),
                     Card('NAXIS',     0, 'number of array dimensions'),
                     Card('END')]
            self.header = Header(CardList(Buffer(File.blockLen, cards=cards),
                                          len(cards)))

        if isinstance(data, Numeric.arraytype):
            self.header['BITPIX'] = ImageBaseHDU.ImgCode[data.typecode()]
            axes = list(data.shape)
            axes.reverse()
            self.header['NAXIS'] = len(axes)
            for j in range(len(axes)):
                # add NAXISi if it does not exist
                try:
                    self.header['NAXIS%d'%(j+1)] = axes[j]
                except KeyError:
                    if (j == 0):
                        after = 'NAXIS'
                    else:
                        after = 'NAXIS%d'%j
                    self.header.update('NAXIS%d'%(j+1), axes[j], after=after)
            self._data = data
        elif isinstance(data, types.NoneType):
            self._data = None
        else:
            raise ValueError, "incorrect array type"

        self.zero = self.header.get('BZERO', 0)
        self.scale = self.header.get('BSCALE', 1)
        self.autoscale = (self.zero != 0) or (self.scale != 1)

    def __getattr__(self, attr):
        if attr == 'data':
            self.__dict__[attr] = None
            if self.header['NAXIS'] > 0:
                size = self.size()
                #  The seek should come just before the read to avoid
                #  the file pointer from being inadvertantly changed
                #  before being used.
                self._file.seek(self._data)
                blok = self._file.read(size)
                if len(blok) == 0:
                    raise EOFError
                elif len(blok) != size:
                    raise IOError

                #  To preserve the type of self.data during autoscaling,
                #  make zero and scale 0-dim Numeric arrays.
                code = ImageBaseHDU.NumCode[self.header['BITPIX']]
                self.data = Numeric.fromstring(blok, code)
                #self.data = Numeric.fromstring(self._data, code)
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

    def _writeHeader(self):
        return str(self.header.ascard)

    def _writeData(self):
        self.zero = self.header.get('BZERO', 0)
        self.scale = self.header.get('BSCALE', 1)
        self.autoscale = (self.zero != 0) or (self.scale != 1)
        if self.autoscale:
            code = ImageBaseHDU.NumCode[self.header['BITPIX']]
            zero = Numeric.array(self.zero, code)
            scale = Numeric.array(self.scale, code)
            self.data = (self.data - zero) / scale

        if Numeric.LittleEndian:
            self.data = self.data.byteswapped()

        return data

    def copy(self):
        data = None
        if self.data != None:
            data = self.data.copy()
        return apply(self.__class__, (data, Header(self.header.ascard.copy())))

    def shape(self):
        naxis = self.header['NAXIS']
        axes = naxis*[0]
        for j in range(naxis):
            axes[j] = self.header['NAXIS%d'%(j+1)]
        axes.reverse()
        return tuple(axes)

    def size(self):
        raise NotImplementedError, "virtual size method not implemented"

    def summary(self, format):
        clas  = str(self.__class__)
        type, shape, code = clas[string.rfind(clas, '.')+1:], (), ''
        if not isinstance(self.data, types.NoneType):
            shape, code = self.data.shape, self.data.typecode()
        return format % (self.name, type, len(self.header.ascard), shape, code)

    def _verifycard(self, card, keywd, test):
        key, val = card.key, card.value
        if not key == keywd:
            raise IndexError, "'%-8s' card has invalid ordering" % key
        if not eval(test):
            raise ValueError, "'%-8s' card has invalid value" % key

    def verify(self):
        raise NotImplementedError, "virtual verify method not implemented"


class PrimaryHDU(ImageBaseHDU):

    """FITS Primary Array Header-Data Unit"""

    def __init__(self, data=None, header=None):
        ImageBaseHDU.__init__(self, data=data, header=header)
        self.name = 'PRIMARY'

    def size(self):
        size, hdr = 0, self.header
        naxis = hdr[2]
        if naxis > 0:
            size = abs(hdr[1])/8
            for j in range(naxis):
                size *= hdr[j+3]
        return size

    def verify(self):

        isInt = "isinstance(val, types.IntType)"
        isValid = "val in [8, 16, 32, -32, -64]"
        cards = self.header.ascard

        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards[0], 'SIMPLE', "val == TRUE")
        self._verifycard(cards[1], 'BITPIX', isInt+" and "+isValid)
        self._verifycard(cards[2], 'NAXIS',  isInt+" and val >= 0")
        naxis = self.header[2]
        for j in range(3, naxis+3):
            self._verifycard(cards[j], 'NAXIS%d'%(j-2), isInt+" and val >= 0")
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(naxis+3, len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)


class GroupsHDU(ImageBaseHDU):

    """FITS Random Groups Header-Data Unit"""

    def __init__(self, data=None, header=None, groups=None, name=None):
        ImageBaseHDU.__init__(self, data=data, header=header)

    def size(self):
        size, hdr = 0, self.header
        naxis = hdr[2]
        # NAXIS1 == 0 and the shape of the array is given by NAXIS(n-1)
        if naxis > 1:
            size = 1
            for j in range(1, naxis):
                size *= hdr[j+3]
        return abs(hdr[1])/8 * hdr['GCOUNT'] * (hdr['PCOUNT'] + size)

    def verify(self):

        isInt = "isinstance(val, types.IntType)"
        isValid = "val in [8, 16, 32, -32, -64]"
        cards = self.header.ascard

        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards[0], 'SIMPLE', "val == TRUE")
        self._verifycard(cards[1], 'BITPIX', isInt+" and "+isValid)
        self._verifycard(cards[2], 'NAXIS',  isInt+" and val >= 1")
        self._verifycard(cards[3], 'NAXIS1', isInt+" and val == 0")
        naxis = self.header[2]
        for j in range(4, naxis+3):
            self._verifycard(cards[j], 'NAXIS%d'%(j-2), isInt+" and val >= 0")
        self._verifycard(cards['GROUPS'], 'GROUPS', "val == TRUE")
        self._verifycard(cards['PCOUNT'], 'PCOUNT', isInt+" and val >= 0")
        self._verifycard(cards['GCOUNT'], 'GCOUNT', isInt+" and val >= 0")
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(naxis+3, len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)


class ImageHDU(ImageBaseHDU):

    """FITS Image Extension Header-Data Unit"""

    def __init__(self, data=None, header=None, name=None):
        ImageBaseHDU.__init__(self, data=data, header=header)

        # change the first card from SIMPLE to XTENSION
        #if self.header.ascard[0].key == 'SIMPLE':
        #    self.header.ascard[0] = Card('XTENSION','IMAGE','Image extension')

        # insert the require keywords PCOUNT and GCOUNT
        #dim = `self.header['NAXIS']`
        #if dim == '0':
        #    dim = ''
        #self.header.update('PCOUNT', 0, after='NAXIS'+dim)
        #self.header.update('GCOUNT', 1, after='PCOUNT')

        #  set extension name
        if not name and self.header.has_key('EXTNAME'):
            name = self.header['EXTNAME']
        self.name = name

    #def __setattr__(self, attr, value):
    #    """Set an Array HDU attribute"""
    #
    #    if attr == 'name' and value:
    #        if type(value) != types.StringType:
    #            raise TypeError, 'bad value type'
    #        if self.header.has_key('EXTNAME'):
    #            self.header['EXTNAME'] = value
    #        else:
    #            self.header.ascard.append(Card('EXTNAME', value,
    #            'extension name'))
    #    self.__dict__[attr] = value

    def size(self):
        hdr = self.header
        size, naxis = 0, hdr[2]
        if naxis > 0:
            size = abs(hdr[1])/8
            for j in range(naxis):
                size *= hdr[j+3]
        return size

    def verify(self):

        isInt = "isinstance(val, types.IntType)"
        isValid = "val in [8, 16, 32, -32, -64]"
        cards = self.header.ascard

        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards[0], 'XTENSION', "val == 'IMAGE'")
        self._verifycard(cards[1], 'BITPIX',   isInt+" and "+isValid)
        self._verifycard(cards[2], 'NAXIS', isInt+" and val >= 0")
        naxis = self.header[2]
        for j in range(3, naxis+3):
            self._verifycard(cards[j], 'NAXIS%d'%(j-2), isInt+" and val >= 0")
        self._verifycard(cards[naxis+3], 'PCOUNT', isInt+" and val == 0")
        self._verifycard(cards[naxis+4], 'GCOUNT', isInt+" and val == 1")
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(naxis+5, len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)


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

      _file:  file associated with table          (None)
      _data:  starting byte of data block in file (None)

    """

    def __init__(self, data=None, header=None, name=None):
        self._file, self._data = None, None
        if header != None:
            self.header = header
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
        elif isinstance(data, types.NoneType):
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
        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    #def __setattr__(self, attr, value):
    #    """Set an Array HDU attribute"""
    #
    #    if attr == 'name' and value:
    #        if type(value) != types.StringType:
    #            raise TypeError, 'bad value type'
    #        if self.header.has_key('EXTNAME'):
    #            self.header['EXTNAME'] = value
    #        else:
    #            self.header.ascard.append(Card('EXTNAME', value, \
    #                                           'extension name'))
    #    self.__dict__[attr] = value

    def copy(self):
        data = None
        if self.data != None:
            data = self.data.copy()
        return apply(self.__class__, (data, Header(self.header.ascard.copy())))

    def shape(self):
        return (self.header['NAXIS2'], self.header['NAXIS1'])

    def size(self):
        hdr = self.header
        return hdr[3]*hdr[4] + hdr[5]

    def summary(self, format):
        clas  = str(self.__class__)
        type  = clas[string.rfind(clas, '.')+1:]
        if self.data != None:
            shape, code = self.data.shape, self.data.format
        else:
            shape, code = (), ''
        return format % (self.name, type, len(self.header.ascard), shape, code)

    def verify(self):
        raise NotImplementedError

    def _verifycard(self, card, keywd, test):
        key, val = card.key, card.value
        if not key == keywd:
            raise IndexError, "'%-8s' card has invalid ordering" % key
        if not eval(test):
            raise ValueError, "'%-8s' card has invalid value" % key


class TableHDU(Table):

    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')

    def __init__(self, data=None, header=None, name=None):
        Table.__init__(self, data=data, header=header, name=name)
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

    def verify(self):
        tform = "re.match(r'[AI]\d+$|[FED]\d+(\.\d*)?$', val)"
        isInt = "isinstance(val, types.IntType)"
        cards = self.header.ascard

        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards[0], 'XTENSION', "val == 'TABLE'")
        self._verifycard(cards[1], 'BITPIX',   isInt+" and val == 8")
        self._verifycard(cards[2], 'NAXIS',    isInt+" and val == 2")
        self._verifycard(cards[3], 'NAXIS1',   isInt+" and val >= 0")
        self._verifycard(cards[4], 'NAXIS2',   isInt+" and val >= 0")
        self._verifycard(cards[5], 'PCOUNT',   isInt+" and val == 0")
        self._verifycard(cards[6], 'GCOUNT',   isInt+" and val == 1")
        self._verifycard(cards[7], 'TFIELDS',  isInt+" and 0 <= val <= 999")
        for j in range(1, self.header[7]+1):
            self._verifycard(cards['TBCOL%d'%j], 'TBCOL%d'%j,
                             isInt+" and val >= 1")
            self._verifycard(cards['TFORM%d'%j], 'TFORM%d'%j, tform)
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(8, len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)


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

    def __init__(self, data=None, header=None, fields=None, name=None):
        Table.__init__(self, data=data, header=header, name=name)
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
                if self.header.has_key('TTYPE'+`j+1`):
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

    def verify(self):
        tform = "re.match(r'\d*[LXBIJAEDCMP]\w*$', val)"
        isInt = "isinstance(val, types.IntType)"
        cards = self.header.ascard

        # Verify syntax and value of mandatory keywords.
        self._verifycard(cards[0], 'XTENSION', "val == 'BINTABLE'")
        self._verifycard(cards[1], 'BITPIX',   isInt+" and val == 8")
        self._verifycard(cards[2], 'NAXIS',    isInt+" and val == 2")
        self._verifycard(cards[3], 'NAXIS1',   isInt+" and val >= 0")
        self._verifycard(cards[4], 'NAXIS2',   isInt+" and val >= 0")
        self._verifycard(cards[5], 'PCOUNT',   isInt+" and val >= 0")
        self._verifycard(cards[6], 'GCOUNT',   isInt+" and val == 1")
        self._verifycard(cards[7], 'TFIELDS',  isInt+" and 0 <= val <= 999")
        for j in range(1, self.header[7]+1):
            self._verifycard(cards['TFORM%d'%j], 'TFORM%d'%j, tform)
        self._verifycard(cards[-1], 'END', "1")

        # Verify syntax of other keywords, issue warning if invalid.
        for j in range(8, len(cards)):
            try:
                cards[j]
            except ValueError, msg:
                warnings.warn(msg, SyntaxWarning)
        fill = cards.getfill()
        if len(fill)*' ' != fill:
            warnings.warn("header fill contains non-space characters",
                          SyntaxWarning)


class HDUList(UserList.UserList):
    """A HDUList class

    This class provides list behavior for FITS HDUs, making it easy to
    access and manipulate the FITS file.
    """

    def __init__(self, hdus=None, file=None):
        """Create a new HDUList"""

        UserList.UserList.__init__(self)
        self.__file = file
        if hdus == None:
            hdus = []
        elif not isinstance(hdus, types.ListType):
            hdus = [hdus]
        for hdu in hdus:
            self.data.append(hdu)

    def __getitem__(self, key):
        """Get an HDU from the HDUList object."""

        if isinstance(key, types.IntType):
            return self.data[key]
        else:
            return self.data[self.index_of(key)]

    def __setitem__(self, key, hdu):
        """Set an HDU HDUList item."""

        #if not isinstance(hud, BaseHDU):
        #    raise TypeError, "item is not an header-data unit"
        if isinstance(key, types.IntType):
            self.data[key] = hdu
        else:
            self.data[self.index_of(key)] = hdu

    def __delitem__(self, key):
        """Delete an HDU from the HDUList object."""

        if isinstance(key, types.IntType):
            del self.data[key]
        else:
            del self.data[self.index_of(key)]

    def append(self, hdu):
        """Append a new HDU to the HDUList"""

        #if not isinstance(hdu, BaseHDU):
        #    raise TypeError, "item is not an header-data unit"
        self.data.append(hdu)

    def index_of(self, key):
        """Get the index of an HDU from the HDUList object.  The key
        can be an integer, a string, or a tuple of (string, integer)."""

        if isinstance(key, types.TupleType):
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

    #def __write(self, hdu):
    #    """Write HDUList HDUs"""
    #    block = str(hdu.header.ascard) + str(Card('END'))
    #    block = block + File.__padBlock(len(block))*' '
    #
    #    if len(block)%File.blockLen != 0:
    #        raise IOError
    #    self._file.write(block)
    #
    #    if hdu.data != None:
    #        # if image, need to deal with bzero/bscale and byteswap
    #        if isinstance(hdu, ImageBaseHDU):
    #            hdu.zero = hdu.header.get('BZERO', 0)
    #            hdu.scale = hdu.header.get('BSCALE', 1)
    #            hdu.autoscale = (hdu.zero != 0) or (hdu.scale != 1)
    #            if hdu.autoscale:
    #                code = ImageBaseHDU.NumCode[hdu.header['BITPIX']]
    #                zero = Numeric.array(hdu.zero, code)
    #                scale = Numeric.array(hdu.scale, code)
    #                hdu.data = (hdu.data - zero) / scale
    #
    #            if Numeric.LittleEndian:
    #                hdu.data = hdu.data.byteswapped()
    #
    #        block = hdu.data.tostring()
    #        if len(block) > 0:
    #            block = block + File.__padBlock(len(block))*'\0'
    #            if len(block)%File.blockLen != 0:
    #                raise IOError
    #            self._file.write(block)

    def info(self):
        results = "No.    Name         Type      Cards   Shape        Format\n"
        for j in range(len(self.data)):
            results = results + "%-3d  %s\n" % \
                      (j, self.data[j].summary("%-10s  %-11s  %5d  %-12s  %s"))
        return results


class File:
    """A File I/O class.

    This class provides a standard file I/O interface to FITS files.
    """

    # set the FITS block size
    blockLen = 2880

    def __init__(self, name, mode='r'):

        if '+' not in mode:
            mode += '+'
        if 'b' not in mode:
            mode += 'b'
        file = __builtin__.open(name, mode)
        self.__file = file

        self.name = name
        self.mode = mode
        self.__offset = 0
        self.__file.seek(0)

    def __readHDU(self):
        """Read one FITS HDU from a file.  Delay reading of the data
        partition, instead save its byte offset in the file."""

        cardLen, blokLen = Card.length, File.blockLen
        bloksize, ncards, card = 0, 0, ''
        remainder = self.__size - self.__offset
        buffer = Buffer(bloksize, self.__offset, self.__file)

        # Read one header block at a time, stopping when an END card,
        # an end-of-file, or an IO error is encountered.
        while card != '%-80s'%'END':
            if ncards%36 == 0:
                if   remainder <= 0:
                    break
                elif remainder < blokLen:
                    raise IOError
                bloksize  += blokLen
                remainder -= blokLen
                buffer = Buffer(bloksize, self.__offset, self.__file)
            j = ncards*cardLen
            card = buffer[j:j+cardLen]
            ncards += 1

        header = Header(CardList(buffer, ncards))

        try:
            # The header is corrupted, if the first card can't be parsed.
            extens = header.ascard[0]
            if   self.__offset == 0 and extens.key == 'SIMPLE':
                if extens.value == TRUE:
                    if header.get('GROUPS', None) == TRUE:
                        hdu = GroupsHDU(header=header)
                    else:
                        hdu = PrimaryHDU(header=header)
                else:
                    hdu = NonConformingHDU(header=header)
            elif self.__offset > 0 and extens.key == 'XTENSION':
                if   extens.value == 'TABLE':
                    hdu = TableHDU(header=header)
                elif extens.value == 'IMAGE':
                    hdu = ImageHDU(header=header)
                elif extens.value == 'BINTABLE':
                    hdu = BinTableHDU(header=header)
                else:
                    hdu = ConformingHDU(header=header)
            else:
                hdu = NonConformingHDU(header=header)
            hdu.verify()
        except (ValueError, IndexError), msg:
            warnings.warn(msg, SyntaxWarning)
            hdu = CorruptedHDU(header=header)

        self.__offset += len(buffer)
        hdu._file = self.__file
        # Don't read the data from the file at this time, but provide
        # the HDU with the byte offset into the file of the data buffer
        # for later access.
        hdu._data = self.__offset

        # Set the byte offset to the start of the next HDU
        hduSize = hdu.size()
        self.__offset += hduSize+File_blockPadLen(hduSize)
        return hdu

    def read(self):
        """Read (scan) the FITS HDUs"""

        self.__file.seek(0, 2)
        self.__size = self.__file.tell()
        hdus = HDUList(file=self.__file)
        while self.__offset < self.__size:
            hdus.append(self.__readHDU())
        return hdus

    def __writeHDU(self, hdu):
        """Write one FITS HDU to a file"""

        hdu.verify()
        block = hdu._writeHeader()
        block += File_blockPadLen(len(block))*' '
        if len(block)%File.blockLen != 0:
            raise IOError, "Header size is not a multiple of block size"
        self.__file.write(block)

        if hdu.data != None:
            block = hdu._writeData()
            if len(block) > 0:
                block += File_blockPadLen(len(block))*'\0'
                if len(block)%File.blockLen != 0:
                    raise IOError, "Data size is not a multiple of block size"
                self.__file.write(block)

    def write(self, hdus):
        """Write FITS HDUs"""

        if not isinstance(hdus, HDUList):
            hdus = HDUList(hdus)
        for hdu in hdus:
            self.__writeHDU(hdu)

    def close(self):
        self.__file.close()


def open(name, mode='r'):
    """A module-level method for opening a FITS file.

    This method takes a filename and a mode (optional) as arguments.
    The file modes are the same as the built-in open() method, so a
    mode of 'w' (write) will create a new file and a mode of 'a'
    (append) will only append to the file.  To read and update an
    existing file, use a mode of 'r+'.  The default mode is read-only
    ('r').  All files are opened in binary mode.
    """

    return File(name, mode)


if __name__ == '__main__':

    print "\n---start a little internal testing..."
    print "\n---open '%s' read-only..." % sys.argv[1]
    ff = open(sys.argv[1])
    fd = ff.read()

    print "\n---print the file's information..."
    print fd.info()

    print "\n---print out the second card of the primary header..."
    print fd[0].header.ascardlist()[1]

    print "\n---print out the value of NAXIS of the 1st extension header..."
    print fd[1].header['naxis']

    print "\n---print out the value of NAXIS of the 1st sci extension header..."
    print fd['sci',1].header['naxis']

    print "\n---print out the first pixel value of the 1st extension ..."
    print fd[1].data[0,0]

    print "\n---close the file..."
    ff.close()

# Local Variables:
# py-indent-offset: 4
# End:
