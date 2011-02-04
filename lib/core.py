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
from pyfits.card import Card, CardList, RecordValuedKeywordCard, createCard, \
                        upperKey
from pyfits.file import _File
from pyfits.hdu.base import _CorruptedHDU, _NonstandardHDU, _ValidHDU
from pyfits.hdu.extension import _NonstandardExtHDU
from pyfits.hdu.image import _ImageBaseHDU
from pyfits.hdu.table import _TableBaseHDU
from pyfits.verify import _Verify

# API compatibility imports
from pyfits.column import Column, ColDefs
from pyfits.convenience import * 
from pyfits.fitsrec import *
from pyfits.hdu import *
from pyfits.hdu.hdulist import fitsopen as open
from pyfits.header import Header

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
