#!/usr/bin/env python

# $Id$

"""
A module for reading and writing FITS files and manipulating their
contents.

A module for reading and writing Flexible Image Transport System
(FITS) files.  This file format was endorsed by the International
Astronomical Union in 1999 and mandated by NASA as the standard format
for storing high energy astrophysics data.  For details of the FITS
standard, see the NASA/Science Office of Standards and Technology
publication, NOST 100-2.0.

For detailed examples of usage, see the `PyFITS User's Manual
<http://stsdas.stsci.edu/download/wikidocs/The_PyFITS_Handbook.pdf>`_.

"""

from __future__ import division # confidence high

"""
        Do you mean: "Profits"?

                - Google Search, when asked for "PyFITS"
"""

import re, os, tempfile
import operator
import __builtin__
import urllib
import numpy as np
from numpy import char as chararray
import rec
from string import maketrans
import string
import types
import sys
import warnings
import weakref

# Refactored imports--will move around a lot for a while
from pyfits.file import _File
from pyfits.hdu.base import _CorruptedHDU, _NonstandardHDU, _ValidHDU
from pyfits.hdu.extension import _NonstandardExtHDU
from pyfits.hdu.image import _ImageBaseHDU
from pyfits.hdu.table import _TableBaseHDU
from pyfits.verify import _Verify

# API compatibility imports
from pyfits.convenience import * 
from pyfits.fitsrec import *
from pyfits.hdu import *
from pyfits.hdu.hdulist import fitsopen as open

# Module variables
_blockLen = 2880         # the FITS block size
_memmap_mode = {'readonly':'r', 'copyonwrite':'c', 'update':'r+'}

TRUE  = True    # deprecated
FALSE = False   # deprecated

_INDENT = "   "
DELAYED = "delayed"     # used for lazy instantiation of data
ASCIITNULL = 0          # value for ASCII table cell with value = TNULL
                        # this can be reset by user.

# The following variable and function are used to support case sensitive
# values for the value of a EXTNAME card in an extension header.  By default,
# pyfits converts the value of EXTNAME cards to upper case when reading from
# a file.  By calling setExtensionNameCaseSensitive() the user may circumvent
# this process so that the EXTNAME value remains in the same case as it is
# in the file.

EXTENSION_NAME_CASE_SENSITIVE = False

def setExtensionNameCaseSensitive(value=True):
    global EXTENSION_NAME_CASE_SENSITIVE
    EXTENSION_NAME_CASE_SENSITIVE = value

# Warnings routines

_showwarning = warnings.showwarning

def showwarning(message, category, filename, lineno, file=None, line=None):
    if file is None:
        file = sys.stdout
    _showwarning(message, category, filename, lineno, file)

def formatwarning(message, category, filename, lineno, line=None):
    return str(message)+'\n'

warnings.showwarning = showwarning
warnings.formatwarning = formatwarning
warnings.filterwarnings('always',category=UserWarning,append=True)

# Functions

def _padLength(stringLen):
    """
    Bytes needed to pad the input stringLen to the next FITS block.
    """
    return (_blockLen - stringLen%_blockLen) % _blockLen

def _tmpName(input):
    """
    Create a temporary file name which should not already exist.  Use
    the directory of the input file and the base name of the mktemp()
    output.
    """
    dirName = os.path.dirname(input)
    if dirName != '':
        dirName += '/'
    _name = dirName + os.path.basename(tempfile.mktemp())
    if not os.path.exists(_name):
        return _name
    else:
        raise RuntimeError("%s exists" % _name)

def _fromfile(infile, dtype, count, sep):
    if isinstance(infile, file):
        return np.fromfile(infile, dtype=dtype, count=count, sep=sep)
    else: # treat as file-like object with "read" method
        read_size=np.dtype(dtype).itemsize * count
        str=infile.read(read_size)
        return np.fromstring(str, dtype=dtype, count=count, sep=sep)

def _tofile(arr, outfile):
    if isinstance(outfile, file):
        arr.tofile(outfile)
    else: # treat as file-like object with "write" method
        str=arr.tostring()
        outfile.write(str)

def _chunk_array(arr, CHUNK_SIZE=2 ** 25):
    """
    Yields subviews of the given array.  The number of rows is
    selected so it is as close to CHUNK_SIZE (bytes) as possible.
    """
    if len(arr) == 0:
        return
    if isinstance(arr, FITS_rec):
        arr = np.asarray(arr)
    row_size = arr[0].size
    rows_per_chunk = max(min(CHUNK_SIZE // row_size, len(arr)), 1)
    for i in range(0, len(arr), rows_per_chunk):
        yield arr[i:i+rows_per_chunk,...]

def _unsigned_zero(dtype):
    """
    Given a numpy dtype, finds it's "zero" point, which is exactly in
    the middle of its range.
    """
    assert dtype.kind == 'u'
    return 1 << (dtype.itemsize * 8 - 1)

def _is_pseudo_unsigned(dtype):
    return dtype.kind == 'u' and dtype.itemsize >= 2

class _ErrList(list):
    """
    Verification errors list class.  It has a nested list structure
    constructed by error messages generated by verifications at
    different class levels.
    """

    def __init__(self, val, unit="Element"):
        list.__init__(self, val)
        self.unit = unit

    def __str__(self, tab=0):
        """
        Print out nested structure with corresponding indentations.

        A tricky use of `__str__`, since normally `__str__` has only
        one argument.
        """
        result = ""
        element = 0

        # go through the list twice, first time print out all top level messages
        for item in self:
            if not isinstance(item, _ErrList):
                result += _INDENT*tab+"%s\n" % item

        # second time go through the next level items, each of the next level
        # must present, even it has nothing.
        for item in self:
            if isinstance(item, _ErrList):
                _dummy = item.__str__(tab=tab+1)

                # print out a message only if there is something
                if _dummy.strip():
                    if self.unit:
                        result += _INDENT*tab+"%s %s:\n" % (self.unit, element)
                    result += _dummy
                element += 1

        return result

def _pad(input):
    """
    Pad blank space to the input string to be multiple of 80.
    """
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

def _floatFormat(value):
    """
    Format the floating number to make sure it gets the decimal point.
    """
    valueStr = "%.16G" % value
    if "." not in valueStr and "E" not in valueStr:
        valueStr += ".0"

    # Limit the value string to at most 20 characters.
    strLen = len(valueStr)

    if strLen > 20:
        idx = valueStr.find('E')

        if idx < 0:
            valueStr = valueStr[:20]
        else:
            valueStr = valueStr[:20-(strLen-idx)] + valueStr[idx:]

    return valueStr

class Undefined:
    """
    Undefined value.
    """
    def __init__(self):
        # This __init__ is required to be here for Sphinx documentation
        pass

class Delayed:
    """
    Delayed file-reading data.
    """
    def __init__(self, hdu=None, field=None):
        self.hdu = weakref.ref(hdu)
        self.field = field

    def __getitem__(self, key):
        # This forces the data for the HDU to be read, which will replace
        # the corresponding Delayed objects in the Tables Columns to be
        # transformed into ndarrays.  It will also return the value of the
        # requested data element.
        return self.hdu().data[key][self.field]

# translation table for floating value string
_fix_table = maketrans('de', 'DE')
_fix_table2 = maketrans('dD', 'eE')

class Card(_Verify):

    # string length of a card
    length = 80

    # String for a FITS standard compliant (FSC) keyword.
    _keywd_FSC = r'[A-Z0-9_-]* *$'
    _keywd_FSC_RE = re.compile(_keywd_FSC)

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
    _number_FSC_RE = re.compile(r'(?P<sign>[+-])?0*(?P<digt>' + _digits_FSC+')')
    _number_NFSC_RE = re.compile(r'(?P<sign>[+-])? *0*(?P<digt>' + _digits_NFSC + ')')

    # FSC commentary card string which must contain printable ASCII characters.
    _ASCII_text = r'[ -~]*$'
    _comment_FSC_RE = re.compile(_ASCII_text)

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
                r'(?P<numr>' + _numr_FSC + ')|'
                r'(?P<cplx>\( *'
                    r'(?P<real>' + _numr_FSC + ') *, *(?P<imag>' + _numr_FSC + ') *\))'
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
                r'(?P<numr>' + _numr_NFSC + ')|'
                r'(?P<cplx>\( *'
                    r'(?P<real>' + _numr_NFSC + ') *, *(?P<imag>' + _numr_NFSC + ') *\))'
            r')? *)'
        r'(?P<comm_field>'
            r'(?P<sepr>/ *)'
            r'(?P<comm>.*)'
        r')?$')

    # keys of commentary cards
    _commentaryKeys = ['', 'COMMENT', 'HISTORY']

    def __init__(self, key='', value='', comment=''):
        """
        Construct a card from `key`, `value`, and (optionally)
        `comment`.  Any specifed arguments, except defaults, must be
        compliant to FITS standard.

        Parameters
        ----------
        key : str, optional
            keyword name

        value : str, optional
            keyword value

        comment : str, optional
            comment
        """

        if key != '' or value != '' or comment != '':
            self._setkey(key)
            self._setvalue(value)
            self._setcomment(comment)

            # for commentary cards, value can only be strings and there
            # is no comment
            if self.key in Card._commentaryKeys:
                if not isinstance(self.value, str):
                    raise ValueError, 'Value in a commentary card must be a string'
        else:
            self.__dict__['_cardimage'] = ' '*80

    def __repr__(self):
        return self._cardimage

    def __getattr__(self, name):
        """
        Instantiate specified attribute object.
        """

        if name == '_cardimage':
            self.ascardimage()
        elif name == 'key':
            self._extractKey()
        elif name in ['value', 'comment']:
            self._extractValueComment(name)
        else:
            raise AttributeError, name

        return getattr(self, name)

    def _setkey(self, val):
        """
        Set the key attribute, surrogate for the `__setattr__` key case.
        """

        if isinstance(val, str):
            val = val.strip()
            if len(val) <= 8:
                val = val.upper()
                if val == 'END':
                    raise ValueError, "keyword 'END' not allowed"
                self._checkKey(val)
            else:
                if val[:8].upper() == 'HIERARCH':
                    val = val[8:].strip()
                    self.__class__ = _Hierarch
                else:
                    raise ValueError, 'keyword name %s is too long (> 8), use HIERARCH.' % val
        else:
            raise ValueError, 'keyword name %s is not a string' % val
        self.__dict__['key'] = val

    def _setvalue(self, val):
        """
        Set the value attribute.
        """

        if isinstance(val, (str, int, long, float, complex, bool, Undefined,
                            np.floating, np.integer, np.complexfloating)):
            if isinstance(val, str):
                self._checkText(val)
            self.__dict__['_valueModified'] = 1
        else:
            raise ValueError, 'Illegal value %s' % str(val)
        self.__dict__['value'] = val

    def _setcomment(self, val):
        """
        Set the comment attribute.
        """

        if isinstance(val,str):
            self._checkText(val)
        else:
            if val is not None:
                raise ValueError, 'comment %s is not a string' % val
        self.__dict__['comment'] = val

    def __setattr__(self, name, val):
        if name == 'key':
            raise SyntaxError, 'keyword name cannot be reset.'
        elif name == 'value':
            self._setvalue(val)
        elif name == 'comment':
            self._setcomment(val)
        elif name == '__class__':
            _Verify.__setattr__(self, name, val)
            return
        else:
            raise AttributeError, name

        # When an attribute (value or comment) is changed, will reconstructe
        # the card image.
        self._ascardimage()

    def ascardimage(self, option='silentfix'):
        """
        Generate a (new) card image from the attributes: `key`, `value`,
        and `comment`, or from raw string.

        Parameters
        ----------
        option : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.
        """

        # Only if the card image already exist (to avoid infinite loop),
        # fix it first.
        if self.__dict__.has_key('_cardimage'):
            self._check(option)
        self._ascardimage()
        return self.__dict__['_cardimage']

    def _ascardimage(self):
        """
        Generate a (new) card image from the attributes: `key`, `value`,
        and `comment`.  Core code for `ascardimage`.
        """

        # keyword string
        if self.__dict__.has_key('key') or self.__dict__.has_key('_cardimage'):
            if isinstance(self, _Hierarch):
                keyStr = 'HIERARCH %s ' % self.key
            else:
                keyStr = '%-8s' % self.key
        else:
            keyStr = ' '*8

        # value string

        # check if both value and _cardimage attributes are missing,
        # to avoid infinite loops
        if not (self.__dict__.has_key('value') or self.__dict__.has_key('_cardimage')):
            valStr = ''

        # string value should occupies at least 8 columns, unless it is
        # a null string
        elif isinstance(self.value, str):
            if self.value == '':
                valStr = "''"
            else:
                _expValStr = self.value.replace("'","''")
                valStr = "'%-8s'" % _expValStr
                valStr = '%-20s' % valStr
        # must be before int checking since bool is also int
        elif isinstance(self.value ,(bool,np.bool_)):
            valStr = '%20s' % `self.value`[0]
        elif isinstance(self.value , (int, long, np.integer)):
            valStr = '%20d' % self.value

        # XXX need to consider platform dependence of the format (e.g. E-009 vs. E-09)
        elif isinstance(self.value, (float, np.floating)):
            if self._valueModified:
                valStr = '%20s' % _floatFormat(self.value)
            else:
                valStr = '%20s' % self._valuestring
        elif isinstance(self.value, (complex,np.complexfloating)):
            if self._valueModified:
                _tmp = '(' + _floatFormat(self.value.real) + ', ' + _floatFormat(self.value.imag) + ')'
                valStr = '%20s' % _tmp
            else:
                valStr = '%20s' % self._valuestring
        elif isinstance(self.value, Undefined):
            valStr = ''

        # conserve space for HIERARCH cards
        if isinstance(self, _Hierarch):
            valStr = valStr.strip()

        # comment string
        if keyStr.strip() in Card._commentaryKeys:  # do NOT use self.key
            commentStr = ''
        elif self.__dict__.has_key('comment') or self.__dict__.has_key('_cardimage'):
            if self.comment in [None, '']:
                commentStr = ''
            else:
                commentStr = ' / ' + self.comment
        else:
            commentStr = ''

        # equal sign string
        eqStr = '= '
        if keyStr.strip() in Card._commentaryKeys:  # not using self.key
            eqStr = ''
            if self.__dict__.has_key('value'):
                valStr = str(self.value)

        # put all parts together
        output = keyStr + eqStr + valStr + commentStr

        # need this in case card-with-continue's value is shortened
        if not isinstance(self, _Hierarch) and \
           not isinstance(self, RecordValuedKeywordCard):
            self.__class__ = Card
        else:
            if len(keyStr + eqStr + valStr) > Card.length:
                if isinstance(self, _Hierarch) and \
                   len(keyStr + eqStr + valStr) == Card.length + 1 and \
                   keyStr[-1] == ' ':
                    output = keyStr[:-1] + eqStr + valStr + commentStr
                else:
                    raise ValueError, \
                         "The keyword %s with its value is too long." % self.key
        if len(output) <= Card.length:
            output = "%-80s" % output

        # longstring case (CONTINUE card)
        else:
            # try not to use CONTINUE if the string value can fit in one line.
            # Instead, just truncate the comment
            if isinstance(self.value, str) and len(valStr) > (Card.length-10):
                self.__class__ = _Card_with_continue
                output = self._breakup_strings()
            else:
                warnings.warn('card is too long, comment is truncated.')
                output = output[:Card.length]

        self.__dict__['_cardimage'] = output

    def _checkText(self, val):
        """
        Verify `val` to be printable ASCII text.
        """
        if Card._comment_FSC_RE.match(val) is None:
            self.__dict__['_err_text'] = 'Unprintable string %s' % repr(val)
            self.__dict__['_fixable'] = 0
            raise ValueError, self._err_text

    def _checkKey(self, val):
        """
        Verify the keyword `val` to be FITS standard.
        """
        # use repr (not str) in case of control character
        if Card._keywd_FSC_RE.match(val) is None:
            self.__dict__['_err_text'] = 'Illegal keyword name %s' % repr(val)
            self.__dict__['_fixable'] = 0
            raise ValueError, self._err_text

    def _extractKey(self):
        """
        Returns the keyword name parsed from the card image.
        """
        head = self._getKeyString()
        if isinstance(self, _Hierarch):
            self.__dict__['key'] = head.strip()
        else:
            self.__dict__['key'] = head.strip().upper()

    def _extractValueComment(self, name):
        """
        Extract the keyword value or comment from the card image.
        """
        # for commentary cards, no need to parse further
        if self.key in Card._commentaryKeys:
            self.__dict__['value'] = self._cardimage[8:].rstrip()
            self.__dict__['comment'] = ''
            return

        valu = self._check(option='parse')

        if name == 'value':
            if valu is None:
                raise ValueError, "Unparsable card (" + self.key + \
                                  "), fix it first with .verify('fix')."
            if valu.group('bool') != None:
                _val = valu.group('bool')=='T'
            elif valu.group('strg') != None:
                _val = re.sub("''", "'", valu.group('strg'))
            elif valu.group('numr') != None:

                #  Check for numbers with leading 0s.
                numr = Card._number_NFSC_RE.match(valu.group('numr'))
                _digt = numr.group('digt').translate(_fix_table2, ' ')
                if numr.group('sign') == None:
                    _val = eval(_digt)
                else:
                    _val = eval(numr.group('sign')+_digt)
            elif valu.group('cplx') != None:

                #  Check for numbers with leading 0s.
                real = Card._number_NFSC_RE.match(valu.group('real'))
                _rdigt = real.group('digt').translate(_fix_table2, ' ')
                if real.group('sign') == None:
                    _val = eval(_rdigt)
                else:
                    _val = eval(real.group('sign')+_rdigt)
                imag  = Card._number_NFSC_RE.match(valu.group('imag'))
                _idigt = imag.group('digt').translate(_fix_table2, ' ')
                if imag.group('sign') == None:
                    _val += eval(_idigt)*1j
                else:
                    _val += eval(imag.group('sign') + _idigt)*1j
            else:
                _val = UNDEFINED

            self.__dict__['value'] = _val
            if '_valuestring' not in self.__dict__:
                self.__dict__['_valuestring'] = valu.group('valu')
            if '_valueModified' not in self.__dict__:
                self.__dict__['_valueModified'] = 0

        elif name == 'comment':
            self.__dict__['comment'] = ''
            if valu is not None:
                _comm = valu.group('comm')
                if isinstance(_comm, str):
                    self.__dict__['comment'] = _comm.rstrip()

    def _fixValue(self, input):
        """
        Fix the card image for fixable non-standard compliance.
        """
        _valStr = None

        # for the unparsable case
        if input is None:
            _tmp = self._getValueCommentString()
            try:
                slashLoc = _tmp.index("/")
                self.__dict__['value'] = _tmp[:slashLoc].strip()
                self.__dict__['comment'] = _tmp[slashLoc+1:].strip()
            except:
                self.__dict__['value'] = _tmp.strip()

        elif input.group('numr') != None:
            numr = Card._number_NFSC_RE.match(input.group('numr'))
            _valStr = numr.group('digt').translate(_fix_table, ' ')
            if numr.group('sign') is not None:
                _valStr = numr.group('sign')+_valStr

        elif input.group('cplx') != None:
            real  = Card._number_NFSC_RE.match(input.group('real'))
            _realStr = real.group('digt').translate(_fix_table, ' ')
            if real.group('sign') is not None:
                _realStr = real.group('sign')+_realStr

            imag  = Card._number_NFSC_RE.match(input.group('imag'))
            _imagStr = imag.group('digt').translate(_fix_table, ' ')
            if imag.group('sign') is not None:
                _imagStr = imag.group('sign') + _imagStr
            _valStr = '(' + _realStr + ', ' + _imagStr + ')'

        self.__dict__['_valuestring'] = _valStr
        self._ascardimage()

    def _locateEq(self):
        """
        Locate the equal sign in the card image before column 10 and
        return its location.  It returns `None` if equal sign is not
        present, or it is a commentary card.
        """
        # no equal sign for commentary cards (i.e. part of the string value)
        _key = self._cardimage[:8].strip().upper()
        if _key in Card._commentaryKeys:
            eqLoc = None
        else:
            if _key == 'HIERARCH':
                _limit = Card.length
            else:
                _limit = 10
            try:
                eqLoc = self._cardimage[:_limit].index("=")
            except:
                eqLoc = None
        return eqLoc

    def _getKeyString(self):
        """
        Locate the equal sign in the card image and return the string
        before the equal sign.  If there is no equal sign, return the
        string before column 9.
        """
        eqLoc = self._locateEq()
        if eqLoc is None:
            eqLoc = 8
        _start = 0
        if self._cardimage[:8].upper() == 'HIERARCH':
            _start = 8
            self.__class__ = _Hierarch
        return self._cardimage[_start:eqLoc]

    def _getValueCommentString(self):
        """
        Locate the equal sign in the card image and return the string
        after the equal sign.  If there is no equal sign, return the
        string after column 8.
        """
        eqLoc = self._locateEq()
        if eqLoc is None:
            eqLoc = 7
        return self._cardimage[eqLoc+1:]

    def _check(self, option='ignore'):
        """
        Verify the card image with the specified option.
        """
        self.__dict__['_err_text'] = ''
        self.__dict__['_fix_text'] = ''
        self.__dict__['_fixable'] = 1

        if option == 'ignore':
            return
        elif option == 'parse':

            # check the value only, no need to check key and comment for 'parse'
            result = Card._value_NFSC_RE.match(self._getValueCommentString())

            # if not parsable (i.e. everything else) result = None
            return result
        else:

            # verify the equal sign position
            if self.key not in Card._commentaryKeys and self._cardimage.find('=') != 8:
                if option in ['exception', 'warn']:
                    self.__dict__['_err_text'] = 'Card image is not FITS standard (equal sign not at column 8).'
                    raise ValueError, self._err_text + '\n%s' % self._cardimage
                elif option in ['fix', 'silentfix']:
                    result = self._check('parse')
                    self._fixValue(result)
                    if option == 'fix':
                        self.__dict__['_fix_text'] = 'Fixed card to be FITS standard.: %s' % self.key

            # verify the key, it is never fixable
            # always fix silently the case where "=" is before column 9,
            # since there is no way to communicate back to the _keylist.
            self._checkKey(self.key)

            # verify the value, it may be fixable
            result = Card._value_FSC_RE.match(self._getValueCommentString())
            if result is not None or self.key in Card._commentaryKeys:
                return result
            else:
                if option in ['fix', 'silentfix']:
                    result = self._check('parse')
                    self._fixValue(result)
                    if option == 'fix':
                        self.__dict__['_fix_text'] = 'Fixed card to be FITS standard.: %s' % self.key
                else:
                    self.__dict__['_err_text'] = 'Card image is not FITS standard (unparsable value string).'
                    raise ValueError, self._err_text + '\n%s' % self._cardimage

            # verify the comment (string), it is never fixable
            if result is not None:
                _str = result.group('comm')
                if _str is not None:
                    self._checkText(_str)

    def fromstring(self, input):
        """
        Construct a `Card` object from a (raw) string. It will pad the
        string if it is not the length of a card image (80 columns).
        If the card image is longer than 80 columns, assume it
        contains ``CONTINUE`` card(s).
        """
        self.__dict__['_cardimage'] = _pad(input)

        if self._cardimage[:8].upper() == 'HIERARCH':
            self.__class__ = _Hierarch
        # for card image longer than 80, assume it contains CONTINUE card(s).
        elif len(self._cardimage) > Card.length:
            self.__class__ = _Card_with_continue

        # remove the key/value/comment attributes, some of them may not exist
        for name in ['key', 'value', 'comment', '_valueModified']:
            if self.__dict__.has_key(name):
                delattr(self, name)
        return self

    def _ncards(self):
        return len(self._cardimage) // Card.length

    def _verify(self, option='warn'):
        """
        Card class verification method.
        """
        _err = _ErrList([])
        try:
            self._check(option)
        except ValueError:
            # Trapping the ValueError raised by _check method.  Want execution to continue while printing
            # exception message.
            pass
        _err.append(self.run_option(option, err_text=self._err_text, fix_text=self._fix_text, fixable=self._fixable))

        return _err

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
    field_specifier_s = field + r'(\.' + field + r')*'
    field_specifier_val = r'(?P<keyword>' + field_specifier_s + r'): (?P<val>' \
                          + Card._numr_FSC + r'\s*)'
    field_specifier_NFSC_val = r'(?P<keyword>' + field_specifier_s + \
                               r'): (?P<val>' + Card._numr_NFSC + r'\s*)'
    keyword_val = r'\'' + field_specifier_val + r'\''
    keyword_NFSC_val = r'\'' + field_specifier_NFSC_val + r'\''
    keyword_val_comm = r' +' + keyword_val + r' *(/ *(?P<comm>[ -~]*))?$'
    keyword_NFSC_val_comm = r' +' + keyword_NFSC_val + \
                            r' *(/ *(?P<comm>[ -~]*))?$'
    #
    # regular expression to extract the field specifier and value from
    # a card image (ex. 'AXIS.1: 2'), the value may not be FITS Standard
    # Complient
    #
    field_specifier_NFSC_image_RE = re.compile(field_specifier_NFSC_val)
    #
    # regular expression to extract the field specifier and value from
    # a card value; the value may not be FITS Standard Complient
    # (ex. 'AXIS.1: 2.0e5')
    #
    field_specifier_NFSC_val_RE = re.compile(field_specifier_NFSC_val+'$')
    #
    # regular expression to extract the key and the field specifier from a
    # string that is being used to index into a card list that contains
    # record value keyword cards (ex. 'DP1.AXIS.1')
    #
    keyword_name_RE = re.compile(r'(?P<key>' + identifier + r')\.' + \
                                 r'(?P<field_spec>' + field_specifier_s + r')$')
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

    #
    # class method definitins
    #

    def coerce(cls,card):
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

    coerce = classmethod(coerce)

    def upperKey(cls, key):
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
        if isinstance(key, (int, long,np.integer)):
            return key

        mo = cls.keyword_name_RE.match(key)

        if mo:
            return mo.group('key').strip().upper() + '.' + \
                   mo.group('field_spec')
        else:
            return key.strip().upper()

    upperKey = classmethod(upperKey)

    def validKeyValue(cls, key, value=0):
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

        >>> validKeyValue('DP1','AXIS.1: 2')
        >>> validKeyValue('DP1.AXIS.1', 2)
        >>> validKeyValue('DP1.AXIS.1')
        """

        rtnKey = rtnFieldSpec = rtnValue = ''
        myKey = cls.upperKey(key)

        if isinstance(myKey, str):
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

    validKeyValue = classmethod(validKeyValue)

    def createCard(cls, key='', value='', comment=''):
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
        if cls.validKeyValue(key, value):
            objClass = cls
        else:
            objClass = Card

        return objClass(key, value, comment)

    createCard = classmethod(createCard)

    def createCardFromString(cls, input):
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
        idx1 = string.find(input, "'")+1
        idx2 = string.rfind(input, "'")

        if idx2 > idx1 and idx1 >= 0 and \
           cls.validKeyValue('',value=input[idx1:idx2]):
            objClass = cls
        else:
            objClass = Card

        return objClass().fromstring(input)

    createCardFromString = classmethod(createCardFromString)

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
            self.__dict__['field_specifier'] = mo.group('field_spec')
            key = mo.group('key')
        else:
            if isinstance(value, str):
                if value != '':
                    mo = self.field_specifier_NFSC_val_RE.match(value)

                    if mo:
                        self.__dict__['field_specifier'] = mo.group('keyword')
                        value = float(mo.group('val'))
                    else:
                        raise ValueError, \
                              "value %s must be in the form " % value + \
                              "field_specifier: value (ex. 'NAXIS: 2')"
            else:
                raise ValueError, 'value %s is not a string' % value

        Card.__init__(self, key, value, comment)

    def __getattr__(self, name):

        if name == 'field_specifier':
            self._extractValueComment('value')
        else:
            Card.__getattr__(self, name)

        return getattr(self, name)

    def __setattr__(self, name, val):
        if name == 'field_specifier':
            raise SyntaxError, 'field_specifier cannot be reset.'
        else:
            if not isinstance(val, float):
                try:
                    val = float(val)
                except ValueError:
                    raise ValueError, 'value %s is not a float' % val
            Card.__setattr__(self,name,val)

    def _ascardimage(self):
        """
        Generate a (new) card image from the attributes: `key`, `value`,
        `field_specifier`, and `comment`.  Core code for `ascardimage`.
        """
        Card._ascardimage(self)
        eqloc = self._cardimage.index("=")
        slashloc = self._cardimage.find("/")

        if '_valueModified' in self.__dict__ and self._valueModified:
            valStr = _floatFormat(self.value)
        else:
            valStr = self._valuestring

        valStr = "'" + self.field_specifier + ": " + valStr + "'"
        valStr = '%-20s' % valStr

        output = self._cardimage[:eqloc+2] + valStr

        if slashloc > 0:
            output = output + self._cardimage[slashloc-1:]

        if len(output) <= Card.length:
            output = "%-80s" % output

        self.__dict__['_cardimage'] = output


    def _extractValueComment(self, name):
        """
        Extract the keyword value or comment from the card image.
        """
        valu = self._check(option='parse')

        if name == 'value':
            if valu is None:
                raise ValueError, \
                         "Unparsable card, fix it first with .verify('fix')."

            self.__dict__['field_specifier'] = valu.group('keyword')
            self.__dict__['value'] = \
                           eval(valu.group('val').translate(_fix_table2, ' '))

            if '_valuestring' not in self.__dict__:
                self.__dict__['_valuestring'] = valu.group('val')
            if '_valueModified' not in self.__dict__:
                self.__dict__['_valueModified'] = 0

        elif name == 'comment':
            Card._extractValueComment(self, name)


    def strvalue(self):
        """
        Method to extract the field specifier and value from the card
        image.  This is what is reported to the user when requesting
        the value of the `Card` using either an integer index or the
        card key without any field specifier.
        """

        mo = self.field_specifier_NFSC_image_RE.search(self._cardimage)
        return self._cardimage[mo.start():mo.end()]

    def _fixValue(self, input):
        """
        Fix the card image for fixable non-standard compliance.
        """
        _valStr = None

        if input is None:
            tmp = self._getValueCommentString()

            try:
                slashLoc = tmp.index("/")
            except:
                slashLoc = len(tmp)

            self.__dict__['_err_text'] = 'Illegal value %s' % tmp[:slashLoc]
            self.__dict__['_fixable'] = 0
            raise ValueError, self._err_text
        else:
            self.__dict__['_valuestring'] = \
                                 input.group('val').translate(_fix_table, ' ')
            self._ascardimage()


    def _check(self, option='ignore'):
        """
        Verify the card image with the specified `option`.
        """
        self.__dict__['_err_text'] = ''
        self.__dict__['_fix_text'] = ''
        self.__dict__['_fixable'] = 1

        if option == 'ignore':
            return
        elif option == 'parse':
            return self.keyword_NFSC_val_comm_RE.match(self._getValueCommentString())
        else:
            # verify the equal sign position

            if self._cardimage.find('=') != 8:
                if option in ['exception', 'warn']:
                    self.__dict__['_err_text'] = 'Card image is not FITS ' + \
                                       'standard (equal sign not at column 8).'
                    raise ValueError, self._err_text + '\n%s' % self._cardimage
                elif option in ['fix', 'silentfix']:
                    result = self._check('parse')
                    self._fixValue(result)

                    if option == 'fix':
                        self.__dict__['_fix_text'] = \
                           'Fixed card to be FITS standard. : %s' % self.key

            # verify the key

            self._checkKey(self.key)

            # verify the value

            result = \
              self.keyword_val_comm_RE.match (self._getValueCommentString())

            if result is not None:
                return result
            else:
                if option in ['fix', 'silentfix']:
                    result = self._check('parse')
                    self._fixValue(result)

                    if option == 'fix':
                        self.__dict__['_fix_text'] = \
                              'Fixed card to be FITS standard.: %s' % self.key
                else:
                    self.__dict__['_err_text'] = \
                    'Card image is not FITS standard (unparsable value string).'
                    raise ValueError, self._err_text + '\n%s' % self._cardimage

            # verify the comment (string), it is never fixable
            if result is not None:
                _str = result.group('comm')
                if _str is not None:
                    self._checkText(_str)

def createCard(key='', value='', comment=''):
    return RecordValuedKeywordCard.createCard(key, value, comment)
createCard.__doc__ = RecordValuedKeywordCard.createCard.__doc__

def createCardFromString(input):
    return RecordValuedKeywordCard.createCardFromString(input)
createCardFromString.__doc__ = \
    RecordValuedKeywordCard.createCardFromString.__doc__

def upperKey(key):
    return RecordValuedKeywordCard.upperKey(key)
upperKey.__doc__ = RecordValuedKeywordCard.upperKey.__doc__

class _Hierarch(Card):
    """
    Cards begins with ``HIERARCH`` which allows keyword name longer
    than 8 characters.
    """
    def _verify(self, option='warn'):
        """No verification (for now)."""
        return _ErrList([])


class _Card_with_continue(Card):
    """
    Cards having more than one 80-char "physical" cards, the cards after
    the first one must start with ``CONTINUE`` and the whole card must have
    string value.
    """

    def __str__(self):
        """
        Format a list of cards into a printable string.
        """
        kard = self._cardimage
        output = ''
        for i in range(len(kard)//80):
            output += kard[i*80:(i+1)*80] + '\n'
        return output[:-1]

    def _extractValueComment(self, name):
        """
        Extract the keyword value or comment from the card image.
        """
        longstring = ''

        ncards = self._ncards()
        for i in range(ncards):
            # take each 80-char card as a regular card and use its methods.
            _card = Card().fromstring(self._cardimage[i*80:(i+1)*80])
            if i > 0 and _card.key != 'CONTINUE':
                raise ValueError, 'Long card image must have CONTINUE cards after the first card.'
            if not isinstance(_card.value, str):
                raise ValueError, 'Cards with CONTINUE must have string value.'



            if name == 'value':
                _val = re.sub("''", "'", _card.value).rstrip()

                # drop the ending "&"
                if len(_val) and _val[-1] == '&':
                    _val = _val[:-1]
                longstring = longstring + _val

            elif name == 'comment':
                _comm = _card.comment
                if isinstance(_comm, str) and _comm != '':
                    longstring = longstring + _comm.rstrip() + ' '

            self.__dict__[name] = longstring.rstrip()

    def _breakup_strings(self):
        """
        Break up long string value/comment into ``CONTINUE`` cards.
        This is a primitive implementation: it will put the value
        string in one block and the comment string in another.  Also,
        it does not break at the blank space between words.  So it may
        not look pretty.
        """
        val_len = 67
        comm_len = 64
        output = ''

        # do the value string
        valfmt = "'%-s&'"
        val = self.value.replace("'", "''")
        val_list = self._words_group(val, val_len)
        for i in range(len(val_list)):
            if i == 0:
                headstr = "%-8s= " % self.key
            else:
                headstr = "CONTINUE  "
            valstr = valfmt % val_list[i]
            output = output + '%-80s' % (headstr + valstr)

        # do the comment string
        if self.comment is None:
            comm = ''
        else:
            comm = self.comment
        commfmt = "%-s"
        if not comm == '':
            comm_list = self._words_group(comm, comm_len)
            for i in comm_list:
                commstr = "CONTINUE  '&' / " + commfmt % i
                output = output + '%-80s' % commstr

        return output

    def _words_group(self, input, strlen):
        """
        Split a long string into parts where each part is no longer
        than `strlen` and no word is cut into two pieces.  But if
        there is one single word which is longer than `strlen`, then
        it will be split in the middle of the word.
        """
        list = []
        _nblanks = input.count(' ')
        nmax = max(_nblanks, len(input)//strlen+1)
        arr = chararray.array(input+' ', itemsize=1)

        # locations of the blanks
        blank_loc = np.nonzero(arr == ' ')[0]
        offset = 0
        xoffset = 0
        for i in range(nmax):
            try:
                loc = np.nonzero(blank_loc >= strlen+offset)[0][0]
                offset = blank_loc[loc-1] + 1
                if loc == 0:
                    offset = -1
            except:
                offset = len(input)

            # check for one word longer than strlen, break in the middle
            if offset <= xoffset:
                offset = xoffset + strlen

            # collect the pieces in a list
            tmp = input[xoffset:offset]
            list.append(tmp)
            if len(input) == offset:
                break
            xoffset = offset

        return list

class _Header_iter:
    """
    Iterator class for a FITS header object.

    Returns the key values of the cards in the header.  Duplicate key
    values are not returned.
    """

    def __init__(self, header):
        self._lastIndex = -1  # last index into the card list
                              # accessed by the class iterator
        self.keys = header.keys()  # the unique keys from the header

    def __iter__(self):
        return self

    def next(self):
        self._lastIndex += 1

        if self._lastIndex >= len(self.keys):
            self._lastIndex = -1
            raise StopIteration()

        return self.keys[self._lastIndex]


class Header:
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

    def _updateHDUtype(self):
        cards = self.ascard

        try:
            if cards[0].key == 'SIMPLE':
                if 'GROUPS' in cards._keylist and cards['GROUPS'].value == True:
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
                        if self.ascard['ZIMAGE'].value == True:
                            from pyfits.hdu import compressed

                            if compressed.COMPRESSION_SUPPORTED:
                                self._hdutype = CompImageHDU
                            else:
                                warnings.warn("Failure creating a header for a " + \
                                              "compressed image HDU.")
                                warnings.warn( "The pyfitsComp module is not " + \
                                              "available.")
                                warnings.warn("The HDU will be treated as a " + \
                                              "Binary Table HDU.")

                                raise KeyError
                    except KeyError:
                        self._hdutype = BinTableHDU
                else:
                    self._hdutype = _NonstandardExtHDU
            else:
                self._hdutype = _ValidHDU
        except:
            self._hdutype = _CorruptedHDU

    def __contains__(self, item):
        return self.has_key(item)

    def __iter__(self):
        return _Header_iter(self)

    def __getitem__ (self, key):
        """
        Get a header keyword value.
        """
        card = self.ascard[key]

        if isinstance(card, RecordValuedKeywordCard) and \
           (not isinstance(key, types.StringType) or string.find(key,'.') < 0):
            returnVal = card.strvalue()
        elif isinstance(card, CardList):
            returnVal = card
        else:
            returnVal = card.value

        return returnVal

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
        if isinstance(key, str):
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

    def __str__(self):
        return self.ascard.__str__()

    def ascardlist(self):
        """
        Returns a `CardList` object.
        """
        return self.ascard

    def items(self):
        """
        Return a list of all keyword-value pairs from the `CardList`.
        """
        pairs = []
        for card in self.ascard:
            pairs.append((card.key, card.value))
        return pairs

    def has_key(self, key):
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
        try:
            key = upperKey(key)

            if key[:8] == 'HIERARCH':
                key = key[8:].strip()
            _index = self.ascard[key]
            return True
        except:
            return False

    def rename_key(self, oldkey, newkey, force=0):
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
        oldkey = upperKey(oldkey)
        newkey = upperKey(newkey)

        if newkey == 'CONTINUE':
            raise ValueError, 'Can not rename to CONTINUE'
        if newkey in Card._commentaryKeys or oldkey in Card._commentaryKeys:
            if not (newkey in Card._commentaryKeys and oldkey in Card._commentaryKeys):
                raise ValueError, 'Regular and commentary keys can not be renamed to each other.'
        elif (force == 0) and self.has_key(newkey):
            raise ValueError, 'Intended keyword %s already exists in header.' % newkey
        _index = self.ascard.index_of(oldkey)
        _comment = self.ascard[_index].comment
        _value = self.ascard[_index].value
        self.ascard[_index] = createCard(newkey, _value, _comment)


#        self.ascard[_index].__dict__['key']=newkey
#        self.ascard[_index].ascardimage()
#        self.ascard._keylist[_index] = newkey

    def keys(self):
        """
        Return a list of keys with duplicates removed.
        """
        rtnVal = []

        for key in self.ascard.keys():
            if not key in rtnVal:
                rtnVal.append(key)

        return rtnVal

    def get(self, key, default=None):
        """
        Get a keyword value from the `CardList`.  If no keyword is
        found, return the default value.

        Parameters
        ----------
        key : str or int
            keyword name or index

        default : object, optional
            if no keyword is found, the value to be returned.
        """

        try:
            return self[key]
        except KeyError:
            return default

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
        keylist = RecordValuedKeywordCard.validKeyValue(key,value)

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
            self.ascard[j] = createCard(key, value, _comment)
        elif before != None or after != None:
            _card = createCard(key, value, comment)
            self.ascard._pos_insert(_card, before=before, after=after)
        else:
            self.ascard.append(createCard(key, value, comment))

        self._mod = 1

        # If this header is associated with a compImageHDU then update
        # the objects underlying header (_tableHeader) unless the update was
        # made to a card that describes the data.

        if self.__dict__.has_key('_tableHeader') and \
           key not in ('XTENSION','BITPIX','PCOUNT','GCOUNT','TFIELDS',
                       'ZIMAGE','ZBITPIX','ZCMPTYPE') and \
           key[:4] not in ('ZVAL') and \
           key[:5] not in ('NAXIS','TTYPE','TFORM','ZTILE','ZNAME') and \
           key[:6] not in ('ZNAXIS'):
            self._tableHeader.update(key,value,comment,before,after)

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
        # the objects underlying header (_tableHeader).

        if self.__dict__.has_key('_tableHeader'):
            self._tableHeader.add_history(value,before,after)

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
        # the objects underlying header (_tableHeader).

        if self.__dict__.has_key('_tableHeader'):
            self._tableHeader.add_comment(value,before,after)

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
        # the objects underlying header (_tableHeader).

        if self.__dict__.has_key('_tableHeader'):
            self._tableHeader.add_blank(value,before,after)

    def get_history(self):
        """
        Get all history cards as a list of string texts.
        """
        output = []
        for _card in self.ascardlist():
            if _card.key == 'HISTORY':
                output.append(_card.value)
        return output

    def get_comment(self):
        """
        Get all comment cards as a list of string texts.
        """
        output = []
        for _card in self.ascardlist():
            if _card.key == 'COMMENT':
                output.append(_card.value)
        return output



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

    def copy(self):
        """
        Make a copy of the `Header`.
        """
        tmp = Header(self.ascard.copy())

        # also copy the class
        tmp._hdutype = self._hdutype
        return tmp

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
            for i in range(_naxis):
                del self['NAXIS'+`i+1`]

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
                for name in ['TFORM', 'TSCAL', 'TZERO', 'TNULL', 'TTYPE', 'TUNIT']:
                    for i in range(_tfields):
                        del self[name+`i+1`]

            if issubclass(self._hdutype, BinTableHDU):
                for name in ['TDISP', 'TDIM', 'THEAP']:
                    for i in range(_tfields):
                        del self[name+`i+1`]

            if issubclass(self._hdutype, TableHDU):
                for i in range(_tfields):
                    del self['TBCOL'+`i+1`]

        except KeyError:
            pass

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
        if (isinstance(outFile,types.StringType) or
            isinstance(outFile,types.UnicodeType)):
            if (os.path.exists(outFile) and os.path.getsize(outFile) != 0):
                if clobber:
                    warnings.warn( "Overwrite existing file '%s'." % outFile)
                    os.remove(outFile)
                else:
                    raise IOError, "File '%s' already exist." % outFile

            outFile = __builtin__.open(outFile,'w')
            closeFile = True

        lines = []   # lines to go out to the header parameters file

        # Add the card image for each card in the header to the lines list

        for j in range(len(self.ascardlist())):
            lines.append(self.ascardlist()[j].__str__()+'\n')

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

        if isinstance(inFile, types.StringType) or \
           isinstance(inFile, types.UnicodeType):
            inFile = __builtin__.open(inFile,'r')
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
            card = Card().fromstring(line[:min(80,len(line)-1)])
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
                if isinstance(card, _Hierarch):
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


class CardList(list):
    """
    FITS header card list class.
    """

    def __init__(self, cards=[], keylist=None):
        """
        Construct the `CardList` object from a list of `Card` objects.

        Parameters
        ----------
        cards
            A list of `Card` objects.
        """

        list.__init__(self, cards)
        self._cards = cards

        # if the key list is not supplied (as in reading in the FITS file),
        # it will be constructed from the card list.
        if keylist is None:
            self._keylist = [k.upper() for k in self._keys()]
        else:
            self._keylist = keylist

        # find out how many blank cards are *directly* before the END card
        self._blanks = 0
        self.count_blanks()

    def _hasFilterChar(self, key):
        """
        Return `True` if the input key contains one of the special filtering
        characters (``*``, ``?``, or ...).
        """
        if isinstance(key, types.StringType) and (key.endswith('...') or \
           key.find('*') > 0 or key.find('?') > 0):
            return True
        else:
            return False

    def filterList(self, key):
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
        outCl = CardList()

        mykey = upperKey(key)
        reStr = string.replace(mykey,'*','\w*')+'$'
        reStr = string.replace(reStr,'?','\w')
        reStr = string.replace(reStr,'...','\S*')
        match_RE = re.compile(reStr)

        for card in self:
            if isinstance(card, RecordValuedKeywordCard):
                matchStr = card.key + '.' + card.field_specifier
            else:
                matchStr = card.key

            if match_RE.match(matchStr):
                outCl.append(card)

        return outCl

    def __getitem__(self, key):
        """
        Get a `Card` by indexing or by the keyword name.
        """
        if self._hasFilterChar(key):
            return self.filterList(key)
        else:
            _key = self.index_of(key)
            return super(CardList, self).__getitem__(_key)

    def __getslice__(self, start, end):
        _cards = super(CardList, self).__getslice__(start,end)
        result = CardList(_cards, self._keylist[start:end])
        return result

    def __setitem__(self, key, value):
        """
        Set a `Card` by indexing or by the keyword name.
        """
        if isinstance (value, Card):
            _key = self.index_of(key)

            # only set if the value is different from the old one
            if str(self[_key]) != str(value):
                super(CardList, self).__setitem__(_key, value)
                self._keylist[_key] = value.key.upper()
                self.count_blanks()
                self._mod = 1
        else:
            raise SyntaxError, "%s is not a Card" % str(value)

    def __delitem__(self, key):
        """
        Delete a `Card` from the `CardList`.
        """
        if self._hasFilterChar(key):
            cardlist = self.filterList(key)

            if len(cardlist) == 0:
                raise KeyError, "Keyword '%s' not found/" % key

            for card in cardlist:
                if isinstance(card, RecordValuedKeywordCard):
                    mykey = card.key + '.' + card.field_specifier
                else:
                    mykey = card.key

                del self[mykey]
        else:
            _key = self.index_of(key)
            super(CardList, self).__delitem__(_key)
            del self._keylist[_key]  # update the keylist
            self.count_blanks()
            self._mod = 1

    def count_blanks(self):
        """
        Returns how many blank cards are *directly* before the ``END``
        card.
        """
        for i in range(1, len(self)):
            if str(self[-i]) != ' '*Card.length:
                self._blanks = i - 1
                break

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

        if isinstance (card, Card):
            nc = len(self) - self._blanks
            i = nc - 1
            if not bottom:
                for i in range(nc-1, -1, -1): # locate last non-commentary card
                    if self[i].key not in Card._commentaryKeys:
                        break

            super(CardList, self).insert(i+1, card)
            self._keylist.insert(i+1, card.key.upper())
            if useblanks:
                self._use_blanks(card._ncards())
            self.count_blanks()
            self._mod = 1
        else:
            raise SyntaxError, "%s is not a Card" % str(card)

    def _pos_insert(self, card, before, after, useblanks=1):
        """
        Insert a `Card` to the location specified by before or after.

        The argument `before` takes precedence over `after` if both
        specified.  They can be either a keyword name or index.
        """

        if before != None:
            loc = self.index_of(before)
            self.insert(loc, card, useblanks=useblanks)
        elif after != None:
            loc = self.index_of(after)
            self.insert(loc+1, card, useblanks=useblanks)

    def insert(self, pos, card, useblanks=True):
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

        if isinstance (card, Card):
            super(CardList, self).insert(pos, card)
            self._keylist.insert(pos, card.key)  # update the keylist
            self.count_blanks()
            if useblanks:
                self._use_blanks(card._ncards())

            self.count_blanks()
            self._mod = 1
        else:
            raise SyntaxError, "%s is not a Card" % str(card)

    def _use_blanks(self, how_many):
        if self._blanks > 0:
            for i in range(min(self._blanks, how_many)):
                del self[-1] # it also delete the keylist item

    def keys(self):
        """
        Return a list of all keywords from the `CardList`.

        Keywords include ``field_specifier`` for
        `RecordValuedKeywordCard` objects.
        """
        rtnVal = []

        for card in self:
            if isinstance(card, RecordValuedKeywordCard):
                key = card.key+'.'+card.field_specifier
            else:
                key = card.key

            rtnVal.append(key)

        return rtnVal

    def _keys(self):
        """
        Return a list of all keywords from the `CardList`.
        """
        return map(lambda x: getattr(x,'key'), self)

    def values(self):
        """
        Return a list of the values of all cards in the `CardList`.

        For `RecordValuedKeywordCard` objects, the value returned is
        the floating point value, exclusive of the
        ``field_specifier``.
        """
        return map(lambda x: getattr(x,'value'), self)

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
        if isinstance(key, (int, long,np.integer)):
            return key
        elif isinstance(key, str):
            _key = key.strip().upper()
            if _key[:8] == 'HIERARCH':
                _key = _key[8:].strip()
            _keylist = self._keylist
            if backward:
                _keylist = self._keylist[:]  # make a copy
                _keylist.reverse()
            try:
                _indx = _keylist.index(_key)
            except ValueError:
                requestedKey = RecordValuedKeywordCard.validKeyValue(key)
                _indx = 0

                while requestedKey:
                    try:
                        i = _keylist[_indx:].index(requestedKey[0].upper())
                        _indx = i + _indx

                        if isinstance(self[_indx], RecordValuedKeywordCard) \
                        and requestedKey[1] == self[_indx].field_specifier:
                            break
                    except ValueError:
                        raise KeyError, 'Keyword %s not found.' % `key`

                    _indx = _indx + 1
                else:
                    raise KeyError, 'Keyword %s not found.' % `key`

            if backward:
                _indx = len(_keylist) - _indx - 1
            return _indx
        else:
            raise KeyError, 'Illegal key data type %s' % type(key)

    def copy(self):
        """
        Make a (deep)copy of the `CardList`.
        """
        return CardList([createCardFromString(repr(c)) for c in self])

    def __repr__(self):
        """
        Format a list of cards into a string.
        """
        return ''.join(map(repr,self))

    def __str__(self):
        """
        Format a list of cards into a printable string.
        """
        return '\n'.join(map(str,self))


# 0.8.8
def _iswholeline(indx, naxis):
    if isinstance(indx, (int, long,np.integer)):
        if indx >= 0 and indx < naxis:
            if naxis > 1:
                return _SinglePoint(1, indx)
            elif naxis == 1:
                return _OnePointAxis(1, 0)
        else:
            raise IndexError, 'Index %s out of range.' % indx
    elif isinstance(indx, slice):
        indx = _normalize_slice(indx, naxis)
        if (indx.start == 0) and (indx.stop == naxis) and (indx.step == 1):
            return _WholeLine(naxis, 0)
        else:
            if indx.step == 1:
                return _LineSlice(indx.stop-indx.start, indx.start)
            else:
                return _SteppedSlice((indx.stop-indx.start)//indx.step, indx.start)
    else:
        raise IndexError, 'Illegal index %s' % indx


def _normalize_slice(input, naxis):
    """
    Set the slice's start/stop in the regular range.
    """

    def _normalize(indx, npts):
        if indx < -npts:
            indx = 0
        elif indx < 0:
            indx += npts
        elif indx > npts:
            indx = npts
        return indx

    _start = input.start
    if _start is None:
        _start = 0
    elif isinstance(_start, (int, long,np.integer)):
        _start = _normalize(_start, naxis)
    else:
        raise IndexError, 'Illegal slice %s, start must be integer.' % input

    _stop = input.stop
    if _stop is None:
        _stop = naxis
    elif isinstance(_stop, (int, long,np.integer)):
        _stop = _normalize(_stop, naxis)
    else:
        raise IndexError, 'Illegal slice %s, stop must be integer.' % input

    if _stop < _start:
        raise IndexError, 'Illegal slice %s, stop < start.' % input

    _step = input.step
    if _step is None:
        _step = 1
    elif isinstance(_step, (int, long, np.integer)):
        if _step <= 0:
            raise IndexError, 'Illegal slice %s, step must be positive.' % input
    else:
        raise IndexError, 'Illegal slice %s, step must be integer.' % input

    return slice(_start, _stop, _step)


class _KeyType:
    def __init__(self, npts, offset):
        self.npts = npts
        self.offset = offset


class _WholeLine(_KeyType):
    pass


class _SinglePoint(_KeyType):
    pass


class _OnePointAxis(_KeyType):
    pass


class _LineSlice(_KeyType):
    pass


class _SteppedSlice(_KeyType):
    pass


class Section:
    """
    Image section.

    TODO: elaborate
    """
    def __init__(self, hdu):
        self.hdu = hdu

    def _getdata(self, key):
        out = []
        naxis = self.hdu.header['NAXIS']

        # Determine the number of slices in the set of input keys.
        # If there is only one slice then the result is a one dimensional
        # array, otherwise the result will be a multidimensional array.
        numSlices = 0
        for i in range(len(key)):
            if isinstance(key[i], slice):
                numSlices = numSlices + 1

        for i in range(len(key)):
            if isinstance(key[i], slice):
                # OK, this element is a slice so see if we can get the data for
                # each element of the slice.
                _naxis = self.hdu.header['NAXIS'+`naxis-i`]
                ns = _normalize_slice(key[i], _naxis)

                for k in range(ns.start, ns.stop):
                    key1 = list(key)
                    key1[i] = k
                    key1 = tuple(key1)

                    if numSlices > 1:
                        # This is not the only slice in the list of keys so
                        # we simply get the data for this section and append
                        # it to the list that is output.  The out variable will
                        # be a list of arrays.  When we are done we will pack
                        # the list into a single multidimensional array.
                        out.append(self.__getitem__(key1))
                    else:
                        # This is the only slice in the list of keys so if this
                        # is the first element of the slice just set the output
                        # to the array that is the data for the first slice.
                        # If this is not the first element of the slice then
                        # append the output for this slice element to the array
                        # that is to be output.  The out variable is a single
                        # dimensional array.
                        if k == ns.start:
                            out = self.__getitem__(key1)
                        else:
                            out = np.append(out,self.__getitem__(key1))

                # We have the data so break out of the loop.
                break

        if isinstance(out, list):
            out = np.array(out)

        return out

    def __getitem__(self, key):
        dims = []
        if not isinstance(key, tuple):
            key = (key,)
        naxis = self.hdu.header['NAXIS']
        if naxis < len(key):
            raise IndexError, 'too many indices.'
        elif naxis > len(key):
            key = key + (slice(None),) * (naxis-len(key))

        offset = 0

        for i in range(naxis):
            _naxis = self.hdu.header['NAXIS'+`naxis-i`]
            indx = _iswholeline(key[i], _naxis)
            offset = offset * _naxis + indx.offset

            # all elements after the first WholeLine must be WholeLine or
            # OnePointAxis
            if isinstance(indx, (_WholeLine, _LineSlice)):
                dims.append(indx.npts)
                break
            elif isinstance(indx, _SteppedSlice):
                raise IndexError, 'Stepped Slice not supported'

        contiguousSubsection = True

        for j in range(i+1,naxis):
            _naxis = self.hdu.header['NAXIS'+`naxis-j`]
            indx = _iswholeline(key[j], _naxis)
            dims.append(indx.npts)
            if not isinstance(indx, _WholeLine):
                contiguousSubsection = False

            # the offset needs to multiply the length of all remaining axes
            else:
                offset *= _naxis

        if contiguousSubsection:
            if dims == []:
                dims = [1]
            npt = 1
            for n in dims:
                npt *= n

            # Now, get the data (does not include bscale/bzero for now XXX)
            _bitpix = self.hdu.header['BITPIX']
            code = _ImageBaseHDU.NumCode[_bitpix]
            self.hdu._file.seek(self.hdu._datLoc+offset*abs(_bitpix)//8)
            nelements = 1
            for dim in dims:
                nelements = nelements*dim
            raw_data = _fromfile(self.hdu._file, dtype=code, count=nelements,
                                 sep="")
            raw_data.shape = dims
            raw_data.dtype = raw_data.dtype.newbyteorder(">")
            return raw_data
        else:
            out = self._getdata(key)
            return out



# --------------------------Table related code----------------------------------

# lists of column/field definition common names and keyword names, make
# sure to preserve the one-to-one correspondence when updating the list(s).
# Use lists, instead of dictionaries so the names can be displayed in a
# preferred order.
_commonNames = ['name', 'format', 'unit', 'null', 'bscale', 'bzero', 'disp', 'start', 'dim']
_keyNames = ['TTYPE', 'TFORM', 'TUNIT', 'TNULL', 'TSCAL', 'TZERO', 'TDISP', 'TBCOL', 'TDIM']

# mapping from TFORM data type to numpy data type (code)

_booltype = 'i1'
_fits2rec = {'L':_booltype, 'B':'u1', 'I':'i2', 'E':'f4', 'D':'f8', 'J':'i4', 'A':'a', 'C':'c8', 'M':'c16', 'K':'i8'}

# the reverse dictionary of the above
_rec2fits = {}
for key in _fits2rec.keys():
    _rec2fits[_fits2rec[key]]=key


class _FormatX(str):
    """
    For X format in binary tables.
    """
    pass

class _FormatP(str):
    """
    For P format in variable length table.
    """
    pass

# TFORM regular expression
_tformat_re = re.compile(r'(?P<repeat>^[0-9]*)(?P<dtype>[A-Za-z])(?P<option>[!-~]*)')

# table definition keyword regular expression
_tdef_re = re.compile(r'(?P<label>^T[A-Z]*)(?P<num>[1-9][0-9 ]*$)')

def _parse_tformat(tform):
    """
    Parse the ``TFORM`` value into `repeat`, `dtype`, and `option`.
    """
    try:
        (repeat, dtype, option) = _tformat_re.match(tform.strip()).groups()
    except:
        warnings.warn('Format "%s" is not recognized.' % tform)


    if repeat == '': repeat = 1
    else: repeat = eval(repeat)

    return (repeat, dtype, option)

def _convert_format(input_format, reverse=0):
    """
    Convert FITS format spec to record format spec.  Do the opposite
    if reverse = 1.
    """
    if reverse and isinstance(input_format, np.dtype):
        shape = input_format.shape
        kind = input_format.base.kind
        option = str(input_format.base.itemsize)
        if kind == 'S':
            kind = 'a'
        dtype = kind

        ndims = len(shape)
        repeat = 1
        if ndims > 0:
            nel = np.array(shape, dtype='i8').prod()
            if nel > 1:
                repeat = nel
    else:
        fmt = input_format
        (repeat, dtype, option) = _parse_tformat(fmt)

    if reverse == 0:
        if dtype in _fits2rec.keys():                            # FITS format
            if dtype == 'A':
                output_format = _fits2rec[dtype]+`repeat`
                # to accomodate both the ASCII table and binary table column
                # format spec, i.e. A7 in ASCII table is the same as 7A in
                # binary table, so both will produce 'a7'.
                if fmt.lstrip()[0] == 'A' and option != '':
                    output_format = _fits2rec[dtype]+`int(option)` # make sure option is integer
            else:
                _repeat = ''
                if repeat != 1:
                    _repeat = `repeat`
                output_format = _repeat+_fits2rec[dtype]

        elif dtype == 'X':
            nbytes = ((repeat-1) // 8) + 1
            # use an array, even if it is only ONE u1 (i.e. use tuple always)
            output_format = _FormatX(`(nbytes,)`+'u1')
            output_format._nx = repeat

        elif dtype == 'P':
            output_format = _FormatP('2i4')
            output_format._dtype = _fits2rec[option[0]]
        elif dtype == 'F':
            output_format = 'f8'
        else:
            raise ValueError, "Illegal format %s" % fmt
    else:
        if dtype == 'a':
            # This is a kludge that will place string arrays into a
            # single field, so at least we won't lose data.  Need to
            # use a TDIM keyword to fix this, declaring as (slength,
            # dim1, dim2, ...)  as mwrfits does

            ntot = int(repeat)*int(option)

            output_format = str(ntot)+_rec2fits[dtype]
        elif isinstance(dtype, _FormatX):
            warnings.warn('X format')
        elif dtype+option in _rec2fits.keys():                    # record format
            _repeat = ''
            if repeat != 1:
                _repeat = `repeat`
            output_format = _repeat+_rec2fits[dtype+option]
        else:
            raise ValueError, "Illegal format %s" % fmt

    return output_format

def _convert_ASCII_format(input_format):
    """
    Convert ASCII table format spec to record format spec.
    """

    ascii2rec = {'A':'a', 'I':'i4', 'F':'f4', 'E':'f4', 'D':'f8'}
    _re = re.compile(r'(?P<dtype>[AIFED])(?P<width>[0-9]*)')

    # Parse the TFORM value into data type and width.
    try:
        (dtype, width) = _re.match(input_format.strip()).groups()
        dtype = ascii2rec[dtype]
        if width == '':
            width = None
        else:
            width = eval(width)
    except KeyError:
        raise ValueError, 'Illegal format `%s` for ASCII table.' % input_format

    return (dtype, width)

def _get_index(nameList, key):
    """
    Get the index of the `key` in the `nameList`.

    The `key` can be an integer or string.  If integer, it is the index
    in the list.  If string,

        a. Field (column) names are case sensitive: you can have two
           different columns called 'abc' and 'ABC' respectively.

        b. When you *refer* to a field (presumably with the field
           method), it will try to match the exact name first, so in
           the example in (a), field('abc') will get the first field,
           and field('ABC') will get the second field.

        If there is no exact name matched, it will try to match the
        name with case insensitivity.  So, in the last example,
        field('Abc') will cause an exception since there is no unique
        mapping.  If there is a field named "XYZ" and no other field
        name is a case variant of "XYZ", then field('xyz'),
        field('Xyz'), etc. will get this field.
    """

    if isinstance(key, (int, long,np.integer)):
        indx = int(key)
    elif isinstance(key, str):
        # try to find exact match first
        try:
            indx = nameList.index(key.rstrip())
        except ValueError:

            # try to match case-insentively,
            _key = key.lower().rstrip()
            _list = map(lambda x: x.lower().rstrip(), nameList)
            _count = operator.countOf(_list, _key) # occurrence of _key in _list
            if _count == 1:
                indx = _list.index(_key)
            elif _count == 0:
                raise KeyError, "Key '%s' does not exist." % key
            else:              # multiple match
                raise KeyError, "Ambiguous key name '%s'." % key
    else:
        raise KeyError, "Illegal key '%s'." % `key`

    return indx

def _unwrapx(input, output, nx):
    """
    Unwrap the X format column into a Boolean array.

    Parameters
    ----------
    input
        input ``Uint8`` array of shape (`s`, `nbytes`)

    output
        output Boolean array of shape (`s`, `nx`)

    nx
        number of bits
    """

    pow2 = [128, 64, 32, 16, 8, 4, 2, 1]
    nbytes = ((nx-1) // 8) + 1
    for i in range(nbytes):
        _min = i*8
        _max = min((i+1)*8, nx)
        for j in range(_min, _max):
            np.bitwise_and(input[...,i], pow2[j-i*8], output[...,j])

def _wrapx(input, output, nx):
    """
    Wrap the X format column Boolean array into an ``UInt8`` array.

    Parameters
    ----------
    input
        input Boolean array of shape (`s`, `nx`)

    output
        output ``Uint8`` array of shape (`s`, `nbytes`)

    nx
        number of bits
    """

    output[...] = 0 # reset the output
    nbytes = ((nx-1) // 8) + 1
    unused = nbytes*8 - nx
    for i in range(nbytes):
        _min = i*8
        _max = min((i+1)*8, nx)
        for j in range(_min, _max):
            if j != _min:
                np.left_shift(output[...,i], 1, output[...,i])
            np.add(output[...,i], input[...,j], output[...,i])

    # shift the unused bits
    np.left_shift(output[...,i], unused, output[...,i])

def _makep(input, desp_output, dtype):
    """
    Construct the P format column array, both the data descriptors and
    the data.  It returns the output "data" array of data type `dtype`.

    The descriptor location will have a zero offset for all columns
    after this call.  The final offset will be calculated when the file
    is written.

    Parameters
    ----------
    input
        input object array

    desp_output
        output "descriptor" array of data type ``Int32``

    dtype
        data type of the variable array
    """
    _offset = 0
    data_output = _VLF([None]*len(input))
    data_output._dtype = dtype

    if dtype == 'a':
        _nbytes = 1
    else:
        _nbytes = np.array([],dtype=np.typeDict[dtype]).itemsize

    for i in range(len(input)):
        if dtype == 'a':
            data_output[i] = chararray.array(input[i], itemsize=1)
        else:
            data_output[i] = np.array(input[i], dtype=dtype)

        desp_output[i,0] = len(data_output[i])
        desp_output[i,1] = _offset
        _offset += len(data_output[i]) * _nbytes

    return data_output

class _VLF(np.ndarray):
    """
    Variable length field object.
    """

    def __new__(subtype, input):
        """
        Parameters
        ----------
        input
            a sequence of variable-sized elements.
        """
        a = np.array(input,dtype=np.object)
        self = np.ndarray.__new__(subtype, shape=(len(input)), buffer=a,
                                  dtype=np.object)
        self._max = 0
        return self

    def __array_finalize__(self,obj):
        if obj is None:
            return
        self._max = obj._max

    def __setitem__(self, key, value):
        """
        To make sure the new item has consistent data type to avoid
        misalignment.
        """
        if isinstance(value, np.ndarray) and value.dtype == self.dtype:
            pass
        elif isinstance(value, chararray.chararray) and value.itemsize == 1:
            pass
        elif self._dtype == 'a':
            value = chararray.array(value, itemsize=1)
        else:
            value = np.array(value, dtype=self._dtype)
        np.ndarray.__setitem__(self, key, value)
        self._max = max(self._max, len(value))


class Column:
    """
    Class which contains the definition of one column, e.g.  `ttype`,
    `tform`, etc. and the array containing values for the column.
    Does not support `theap` yet.
    """
    def __init__(self, name=None, format=None, unit=None, null=None, \
                       bscale=None, bzero=None, disp=None, start=None, \
                       dim=None, array=None):
        """
        Construct a `Column` by specifying attributes.  All attributes
        except `format` can be optional.

        Parameters
        ----------
        name : str, optional
            column name, corresponding to ``TTYPE`` keyword

        format : str, optional
            column format, corresponding to ``TFORM`` keyword

        unit : str, optional
            column unit, corresponding to ``TUNIT`` keyword

        null : str, optional
            null value, corresponding to ``TNULL`` keyword

        bscale : int-like, optional
            bscale value, corresponding to ``TSCAL`` keyword

        bzero : int-like, optional
            bzero value, corresponding to ``TZERO`` keyword

        disp : str, optional
            display format, corresponding to ``TDISP`` keyword

        start : int, optional
            column starting position (ASCII table only), corresponding
            to ``TBCOL`` keyword

        dim : str, optional
            column dimension corresponding to ``TDIM`` keyword
        """
        # any of the input argument (except array) can be a Card or just
        # a number/string
        for cname in _commonNames:
            value = eval(cname)           # get the argument's value

            keyword = _keyNames[_commonNames.index(cname)]
            if isinstance(value, Card):
                setattr(self, cname, value.value)
            else:
                setattr(self, cname, value)

        # if the column data is not ndarray, make it to be one, i.e.
        # input arrays can be just list or tuple, not required to be ndarray
        if format is not None:
            # check format
            try:

                # legit FITS format? convert to record format (e.g. '3J'->'3i4')
                recfmt = _convert_format(format)
            except ValueError:
                try:
                    # legit recarray format?
                    recfmt = format
                    format = _convert_format(recfmt, reverse=1)
                except ValueError:
                    raise ValueError, "Illegal format `%s`." % format

            self.format = format

            # does not include Object array because there is no guarantee
            # the elements in the object array are consistent.
            if not isinstance(array, (np.ndarray, chararray.chararray, Delayed)):
                try: # try to convert to a ndarray first
                    if array is not None:
                        array = np.array(array)
                except:
                    try: # then try to conver it to a strings array
                        array = chararray.array(array, itemsize=eval(recfmt[1:]))

                    # then try variable length array
                    except:
                        if isinstance(recfmt, _FormatP):
                            try:
                                array=_VLF(array)
                            except:
                                try:
                                    # this handles ['abc'] and [['a','b','c']]
                                    # equally, beautiful!
                                    _func = lambda x: chararray.array(x, itemsize=1)
                                    array = _VLF(map(_func, array))
                                except:
                                    raise ValueError, "Inconsistent input data array: %s" % array
                            array._dtype = recfmt._dtype
                        else:
                            raise ValueError, "Data is inconsistent with the format `%s`." % format

        else:
            raise ValueError, "Must specify format to construct Column"

        # scale the array back to storage values if there is bscale/bzero
        if isinstance(array, np.ndarray):

            # boolean needs to be scaled too
            if recfmt[-2:] == _booltype:
                _out = np.zeros(array.shape, dtype=recfmt)
                array = np.where(array==0, ord('F'), ord('T'))

            # make a copy if scaled, so as not to corrupt the original array
            if bzero not in ['', None, 0] or bscale not in ['', None, 1]:
                array = array.copy()
                if bzero not in ['', None, 0]:
                    array += -bzero
                if bscale not in ['', None, 1]:
                    array /= bscale

        array = self.__checkValidDataType(array,self.format)
        self.array = array

    def __checkValidDataType(self,array,format):
        # Convert the format to a type we understand
        if isinstance(array,Delayed):
            return array
        elif (array is None):
            return array
        else:
            if (format.find('A') != -1 and format.find('P') == -1):
                if str(array.dtype).find('S') != -1:
                    # For ASCII arrays, reconstruct the array and ensure
                    # that all elements have enough characters to comply
                    # with the format.  The new array will have the data
                    # left justified in the field with trailing blanks
                    # added to complete the format requirements.
                    fsize=eval(_convert_format(format)[1:])
                    l = []

                    for i in range(len(array)):
                        al = len(array[i])
                        l.append(array[i][:min(fsize,array.itemsize)]+
                                 ' '*(fsize-al))
                    return chararray.array(l)
                else:
                    numpyFormat = _convert_format(format)
                    return array.astype(numpyFormat)
            elif (format.find('X') == -1 and format.find('P') == -1):
                (repeat, fmt, option) = _parse_tformat(format)
                numpyFormat = _convert_format(fmt)
                return array.astype(numpyFormat)
            elif (format.find('X') !=-1):
                return array.astype(np.uint8)
            else:
                return array

    def __repr__(self):
        text = ''
        for cname in _commonNames:
            value = getattr(self, cname)
            if value != None:
                text += cname + ' = ' + `value` + '\n'
        return text[:-1]

    def copy(self):
        """
        Return a copy of this `Column`.
        """
        tmp = Column(format='I') # just use a throw-away format
        tmp.__dict__=self.__dict__.copy()
        return tmp


class ColDefs(object):
    """
    Column definitions class.

    It has attributes corresponding to the `Column` attributes
    (e.g. `ColDefs` has the attribute `~ColDefs.names` while `Column`
    has `~Column.name`). Each attribute in `ColDefs` is a list of
    corresponding attribute values from all `Column` objects.
    """
    def __init__(self, input, tbtype='BinTableHDU'):
        """
        Parameters
        ----------

        input : sequence of `Column` objects
            an (table) HDU

        tbtype : str, optional
            which table HDU, ``"BinTableHDU"`` (default) or
            ``"TableHDU"`` (text table).
        """
        ascii_fmt = {'A':'A1', 'I':'I10', 'E':'E14.6', 'F':'F16.7', 'D':'D24.16'}
        self._tbtype = tbtype

        if isinstance(input, ColDefs):
            self.data = [col.copy() for col in input.data]

        # if the input is a list of Columns
        elif isinstance(input, (list, tuple)):
            for col in input:
                if not isinstance(col, Column):
                    raise TypeError(
                           "Element %d in the ColDefs input is not a Column."
                           % input.index(col))
            self.data = [col.copy() for col in input]

            # if the format of an ASCII column has no width, add one
            if tbtype == 'TableHDU':
                for i in range(len(self)):
                    (type, width) = _convert_ASCII_format(self.data[i].format)
                    if width is None:
                        self.data[i].format = ascii_fmt[self.data[i].format[0]]


        elif isinstance(input, _TableBaseHDU):
            hdr = input._header
            _nfields = hdr['TFIELDS']
            self._width = hdr['NAXIS1']
            self._shape = hdr['NAXIS2']

            # go through header keywords to pick out column definition keywords
            dict = [{} for i in range(_nfields)] # definition dictionaries for each field
            for _card in hdr.ascardlist():
                _key = _tdef_re.match(_card.key)
                try:
                    keyword = _key.group('label')
                except:
                    continue               # skip if there is no match
                if (keyword in _keyNames):
                    col = eval(_key.group('num'))
                    if col <= _nfields and col > 0:
                        cname = _commonNames[_keyNames.index(keyword)]
                        dict[col-1][cname] = _card.value

            # data reading will be delayed
            for col in range(_nfields):
                dict[col]['array'] = Delayed(input, col)

            # now build the columns
            tmp = [Column(**attrs) for attrs in dict]
            self.data = tmp
            self._listener = input
        else:
            raise TypeError, "input to ColDefs must be a table HDU or a list of Columns"

    def __getattr__(self, name):
        """
        Populate the attributes.
        """
        cname = name[:-1]
        if cname in _commonNames and name[-1] == 's':
            attr = [''] * len(self)
            for i in range(len(self)):
                val = getattr(self[i], cname)
                if val != None:
                    attr[i] = val
        elif name == '_arrays':
            attr = [col.array for col in self.data]
        elif name == '_recformats':
            if self._tbtype in ('BinTableHDU', 'CompImageHDU'):
                attr = [_convert_format(fmt) for fmt in self.formats]
            elif self._tbtype == 'TableHDU':
                self._Formats = self.formats
                if len(self) == 1:
                    dummy = []
                else:
                    dummy = map(lambda x, y: x-y, self.starts[1:], [self.starts[0]]+self.starts[1:-1])
                dummy.append(self._width-self.starts[-1]+1)
                attr = map(lambda y: 'a'+`y`, dummy)
        elif name == 'spans':
            # make sure to consider the case that the starting column of
            # a field may not be the column right after the last field
            if self._tbtype == 'TableHDU':
                last_end = 0
                attr = [0] * len(self)
                for i in range(len(self)):
                    (_format, _width) = _convert_ASCII_format(self.formats[i])
                    if self.starts[i] is '':
                        self.starts[i] = last_end + 1
                    _end = self.starts[i] + _width - 1
                    attr[i] = _width
                    last_end = _end
                self._width = _end
            else:
                raise KeyError, 'Attribute %s not defined.' % name
        else:
            raise KeyError, 'Attribute %s not defined.' % name

        self.__dict__[name] = attr
        return self.__dict__[name]


        """
                # make sure to consider the case that the starting column of
                # a field may not be the column right after the last field
                elif tbtype == 'TableHDU':
                    (_format, _width) = _convert_ASCII_format(self.formats[i])
                    if self.starts[i] is '':
                        self.starts[i] = last_end + 1
                    _end = self.starts[i] + _width - 1
                    self.spans[i] = _end - last_end
                    last_end = _end
                    self._Formats = self.formats

                self._arrays[i] = input[i].array
        """

    def __getitem__(self, key):
        x = self.data[key]
        if isinstance(key, (int, long, np.integer)):
            return x
        else:
            return ColDefs(x)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return 'ColDefs'+ `tuple(self.data)`

    def __add__(self, other, option='left'):
        if isinstance(other, Column):
            b = [other]
        elif isinstance(other, ColDefs):
            b = list(other.data)
        else:
            raise TypeError, 'Wrong type of input'
        if option == 'left':
            tmp = list(self.data) + b
        else:
            tmp = b + list(self.data)
        return ColDefs(tmp)

    def __radd__(self, other):
        return self.__add__(other, 'right')

    def __sub__(self, other):
        if not isinstance(other, (list, tuple)):
            other = [other]
        _other = [_get_index(self.names, key) for key in other]
        indx=range(len(self))
        for x in _other:
            indx.remove(x)
        tmp = [self[i] for i in indx]
        return ColDefs(tmp)

    def _update_listener(self):
        if hasattr(self, '_listener'):
            delattr(self._listener, 'data')

    def add_col(self, column):
        """
        Append one `Column` to the column definition.

        .. warning::

            *New in pyfits 2.3*: This function appends the new column
            to the `ColDefs` object in place.  Prior to pyfits 2.3,
            this function returned a new `ColDefs` with the new column
            at the end.
        """
        assert isinstance(column, Column)

        for cname in _commonNames:
            attr = getattr(self, cname+'s')
            attr.append(getattr(column, cname))

        self._arrays.append(column.array)
        # Obliterate caches of certain things
        if hasattr(self, '_recformats'):
            delattr(self, '_recformats')
        if hasattr(self, 'spans'):
            delattr(self, 'spans')

        self.data.append(column)
        # Force regeneration of self._Formats member
        ignored = self._recformats

        # If this ColDefs is being tracked by a Table, inform the
        # table that its data is now invalid.
        self._update_listener()
        return self

    def del_col(self, col_name):
        """
        Delete (the definition of) one `Column`.

        col_name : str or int
            The column's name or index
        """
        indx = _get_index(self.names, col_name)

        for cname in _commonNames:
            attr = getattr(self, cname+'s')
            del attr[indx]

        del self._arrays[indx]
        # Obliterate caches of certain things
        if hasattr(self, '_recformats'):
            delattr(self, '_recformats')
        if hasattr(self, 'spans'):
            delattr(self, 'spans')

        del self.data[indx]
        # Force regeneration of self._Formats member
        ignored = self._recformats

        # If this ColDefs is being tracked by a Table, inform the
        # table that its data is now invalid.
        self._update_listener()
        return self

    def change_attrib(self, col_name, attrib, new_value):
        """
        Change an attribute (in the commonName list) of a `Column`.

        col_name : str or int
            The column name or index to change

        attrib : str
            The attribute name

        value : object
            The new value for the attribute
        """
        indx = _get_index(self.names, col_name)
        getattr(self, attrib+'s')[indx] = new_value

        # If this ColDefs is being tracked by a Table, inform the
        # table that its data is now invalid.
        self._update_listener()

    def change_name(self, col_name, new_name):
        """
        Change a `Column`'s name.

        col_name : str
            The current name of the column

        new_name : str
            The new name of the column
        """
        if new_name != col_name and new_name in self.names:
            raise ValueError, 'New name %s already exists.' % new_name
        else:
            self.change_attrib(col_name, 'name', new_name)

        # If this ColDefs is being tracked by a Table, inform the
        # table that its data is now invalid.
        self._update_listener()

    def change_unit(self, col_name, new_unit):
        """
        Change a `Column`'s unit.

        col_name : str or int
            The column name or index

        new_unit : str
            The new unit for the column
        """
        self.change_attrib(col_name, 'unit', new_unit)

        # If this ColDefs is being tracked by a Table, inform the
        # table that its data is now invalid.
        self._update_listener()

    def info(self, attrib='all'):
        """
        Get attribute(s) information of the column definition.

        Parameters
        ----------
        attrib : str
           Can be one or more of the attributes listed in
           `_commonNames`.  The default is ``"all"`` which will print
           out all attributes.  It forgives plurals and blanks.  If
           there are two or more attribute names, they must be
           separated by comma(s).

        Notes
        -----
        This function doesn't return anything, it just prints to
        stdout.
        """

        if attrib.strip().lower() in ['all', '']:
            list = _commonNames
        else:
            list = attrib.split(',')
            for i in range(len(list)):
                list[i]=list[i].strip().lower()
                if list[i][-1] == 's':
                    list[i]=list[i][:-1]

        for att in list:
            if att not in _commonNames:
                print "'%s' is not an attribute of the column definitions."%att
                continue
            print "%s:" % att
            print '    ', getattr(self, att+'s')

    #def change_format(self, col_name, new_format):
        #new_format = _convert_format(new_format)
        #self.change_attrib(col_name, 'format', new_format)

def _get_tbdata(hdu):
    """
    Get the table data from input (an HDU object).
    """
    tmp = hdu.columns
    # get the right shape for the data part of the random group,
    # since binary table does not support ND yet
    if isinstance(hdu, GroupsHDU):
        tmp._recformats[-1] = `hdu._dimShape()[:-1]` + tmp._dat_format
    elif isinstance(hdu, TableHDU):
        # determine if there are duplicate field names and if there
        # are throw an exception
        _dup = rec.find_duplicate(tmp.names)

        if _dup:
            raise ValueError, "Duplicate field names: %s" % _dup

        itemsize = tmp.spans[-1]+tmp.starts[-1]-1
        dtype = {}

        for j in range(len(tmp)):
            data_type = 'S'+str(tmp.spans[j])

            if j == len(tmp)-1:
                if hdu._header['NAXIS1'] > itemsize:
                    data_type = 'S'+str(tmp.spans[j]+ \
                                hdu._header['NAXIS1']-itemsize)
            dtype[tmp.names[j]] = (data_type,tmp.starts[j]-1)

    if hdu._ffile.memmap:
        if isinstance(hdu, TableHDU):
            hdu._ffile.code = dtype
        else:
            hdu._ffile.code = rec.format_parser(",".join(tmp._recformats),
                                                 tmp.names,None)._descr

        hdu._ffile.dims = tmp._shape
        hdu._ffile.offset = hdu._datLoc
        _data = rec.recarray(shape=hdu._ffile.dims, buf=hdu._ffile._mm,
                             dtype=hdu._ffile.code, names=tmp.names)
    else:
        if isinstance(hdu, TableHDU):
            _data = rec.array(hdu._file, dtype=dtype, names=tmp.names,
                              shape=tmp._shape)
        else:
            _data = rec.array(hdu._file, formats=",".join(tmp._recformats),
                              names=tmp.names, shape=tmp._shape)

    if isinstance(hdu._ffile, _File):
#        _data._byteorder = 'big'
        _data.dtype = _data.dtype.newbyteorder(">")

    # pass datLoc, for P format
    _data._heapoffset = hdu._theap + hdu._datLoc
    _data._file = hdu._file
    _tbsize = hdu._header['NAXIS1']*hdu._header['NAXIS2']
    _data._gap = hdu._theap - _tbsize
    # comment out to avoid circular reference of _pcount

    # pass the attributes
    for attr in ['formats', 'names']:
        setattr(_data, attr, getattr(tmp, attr))
    for i in range(len(tmp)):
       # get the data for each column object from the rec.recarray
        tmp.data[i].array = _data.field(i)

    # delete the _arrays attribute so that it is recreated to point to the
    # new data placed in the column object above
    if tmp.__dict__.has_key('_arrays'):
        del tmp.__dict__['_arrays']

    # TODO: Probably a benign change, but I'd still like to get to
    # the bottom of the root cause...
    #return FITS_rec(_data)
    return _data.view(FITS_rec)

def new_table(input, header=None, nrows=0, fill=False, tbtype='BinTableHDU'):
    """
    Create a new table from the input column definitions.

    Parameters
    ----------
    input : sequence of Column or ColDefs objects
        The data to create a table from.

    header : Header instance
        Header to be used to populate the non-required keywords.

    nrows : int
        Number of rows in the new table.

    fill : bool
        If `True`, will fill all cells with zeros or blanks.  If
        `False`, copy the data from input, undefined cells will still
        be filled with zeros/blanks.

    tbtype : str
        Table type to be created ("BinTableHDU" or "TableHDU").
    """
    # construct a table HDU
    hdu = eval(tbtype)(header=header)

    if isinstance(input, ColDefs):
        if input._tbtype == tbtype:
            # Create a new ColDefs object from the input object and assign
            # it to the ColDefs attribute of the new hdu.
            tmp = hdu.columns = ColDefs(input, tbtype)
        else:
            raise ValueError, 'column definitions have a different table type'
    elif isinstance(input, FITS_rec): # input is a FITS_rec
        # Create a new ColDefs object from the input FITS_rec's ColDefs
        # object and assign it to the ColDefs attribute of the new hdu.
        tmp = hdu.columns = ColDefs(input._coldefs, tbtype)
    elif isinstance(input, np.ndarray):
        tmp = hdu.columns = eval(tbtype)(input).data._coldefs
    else:                 # input is a list of Columns
        # Create a new ColDefs object from the input list of Columns and
        # assign it to the ColDefs attribute of the new hdu.
        tmp = hdu.columns = ColDefs(input, tbtype)

    # read the delayed data
    for i in range(len(tmp)):
        _arr = tmp._arrays[i]
        if isinstance(_arr, Delayed):
            if _arr.hdu().data == None:
                tmp._arrays[i] = None
            else:
                tmp._arrays[i] = rec.recarray.field(_arr.hdu().data,_arr.field)

    # use the largest column shape as the shape of the record
    if nrows == 0:
        for arr in tmp._arrays:
            if (arr is not None):
                dim = arr.shape[0]
            else:
                dim = 0
            if dim > nrows:
                nrows = dim

    if tbtype == 'TableHDU':
        _itemsize = tmp.spans[-1]+tmp.starts[-1]-1
        dtype = {}

        for j in range(len(tmp)):
           data_type = 'S'+str(tmp.spans[j])
           dtype[tmp.names[j]] = (data_type,tmp.starts[j]-1)

        hdu.data = FITS_rec(rec.array(' '*_itemsize*nrows, dtype=dtype,
                                      shape=nrows))
        hdu.data.setflags(write=True)
    else:
        hdu.data = FITS_rec(rec.array(None, formats=",".join(tmp._recformats),
                                      names=tmp.names, shape=nrows))

    hdu.data._coldefs = hdu.columns
    hdu.data.formats = hdu.columns.formats

    # Populate data to the new table from the ndarrays in the input ColDefs
    # object.
    for i in range(len(tmp)):
        # For each column in the ColDef object, determine the number
        # of rows in that column.  This will be either the number of
        # rows in the ndarray associated with the column, or the
        # number of rows given in the call to this function, which
        # ever is smaller.  If the input FILL argument is true, the
        # number of rows is set to zero so that no data is copied from
        # the original input data.
        if tmp._arrays[i] is None:
            size = 0
        else:
            size = len(tmp._arrays[i])

        n = min(size, nrows)
        if fill:
            n = 0

        # Get any scale factors from the FITS_rec
        (_scale, _zero, bscale, bzero) = hdu.data._get_scale_factors(i)[3:]

        if n > 0:
            # Only copy data if there is input data to copy
            # Copy all of the data from the input ColDefs object for this
            # column to the new FITS_rec data array for this column.
            if isinstance(tmp._recformats[i], _FormatX):
                # Data is a bit array
                if tmp._arrays[i][:n].shape[-1] == tmp._recformats[i]._nx:
                    _wrapx(tmp._arrays[i][:n],
                           rec.recarray.field(hdu.data,i)[:n],
                           tmp._recformats[i]._nx)
                else: # from a table parent data, just pass it
                    rec.recarray.field(hdu.data,i)[:n] = tmp._arrays[i][:n]
            elif isinstance(tmp._recformats[i], _FormatP):
                hdu.data._convert[i] = _makep(tmp._arrays[i][:n],
                                            rec.recarray.field(hdu.data,i)[:n],
                                            tmp._recformats[i]._dtype)
            elif tmp._recformats[i][-2:] == _booltype and \
                 tmp._arrays[i].dtype == bool:
                # column is boolean
                rec.recarray.field(hdu.data,i)[:n] = \
                           np.where(tmp._arrays[i]==False, ord('F'), ord('T'))
            else:
                if tbtype == 'TableHDU':

                    # string no need to convert,
                    if isinstance(tmp._arrays[i], chararray.chararray):
                        rec.recarray.field(hdu.data,i)[:n] = tmp._arrays[i][:n]
                    else:
                        hdu.data._convert[i] = np.zeros(nrows,
                                                    dtype=tmp._arrays[i].dtype)
                        if _scale or _zero:
                            _arr = tmp._arrays[i].copy()
                        else:
                            _arr = tmp._arrays[i]
                        if _scale:
                            _arr *= bscale
                        if _zero:
                            _arr += bzero
                        hdu.data._convert[i][:n] = _arr[:n]
                else:
                    rec.recarray.field(hdu.data,i)[:n] = tmp._arrays[i][:n]

        if n < nrows:
            # If there are additional rows in the new table that were not
            # copied from the input ColDefs object, initialize the new data
            if tbtype == 'BinTableHDU':
                if isinstance(rec.recarray.field(hdu.data,i), np.ndarray):
                    # make the scaled data = 0
                    rec.recarray.field(hdu.data,i)[n:] = -bzero/bscale
                else:
                    rec.recarray.field(hdu.data,i)[n:] = ''
            else:
                rec.recarray.field(hdu.data,i)[n:] = \
                                                 ' '*hdu.data._coldefs.spans[i]

    # Update the HDU header to match the data
    hdu.update()

    # Make the ndarrays in the Column objects of the ColDefs object of the HDU
    # reference the same ndarray as the HDU's FITS_rec object.
    for i in range(len(tmp)):
        hdu.columns.data[i].array = hdu.data.field(i)

    # Delete the _arrays attribute so that it is recreated to point to the
    # new data placed in the column objects above
    if hdu.columns.__dict__.has_key('_arrays'):
        del hdu.columns.__dict__['_arrays']

    return hdu


class ErrorURLopener(urllib.FancyURLopener):
    """
    A class to use with `urlretrieve` to allow `IOError` exceptions to
    be raised when a file specified by a URL cannot be accessed.
    """
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        raise IOError, (errcode, errmsg, url)

urllib._urlopener = ErrorURLopener() # Assign the locally subclassed opener
                                     # class to the urllibrary
urllib._urlopener.tempcache = {} # Initialize tempcache with an empty
                                 # dictionary to enable file cacheing



UNDEFINED = Undefined()

__credits__="""

Copyright (C) 2004 Association of Universities for Research in Astronomy (AURA)

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
