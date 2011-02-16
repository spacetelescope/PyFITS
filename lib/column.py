import operator
import re
import warnings
import weakref

import numpy as np
from numpy import char as chararray

from pyfits.card import Card
from pyfits.util import lazyproperty


__all__ = ['Column', 'ColDefs']


# mapping from TFORM data type to numpy data type (code)
# L: Logical (Boolean)
# B: Unsigned Byte
# I: 16-bit Integer
# J: 32-bit Integer
# K: 64-bit Integer
# E: Single-precision Floating Point
# D: Double-precision Floating Point
# C: Single-precision Complex
# M: Double-precision Complex
# A: Character
FITS2NUMPY = {'L': 'i1', 'B': 'u1', 'I': 'i2', 'J': 'i4', 'K': 'i8', 'E': 'f4',
              'D': 'f8', 'C': 'c8', 'M': 'c16', 'A': 'a'}

# the inverse dictionary of the above
NUMPY2FITS = dict([(val, key) for key, val in FITS2NUMPY.iteritems()])

# lists of column/field definition common names and keyword names, make
# sure to preserve the one-to-one correspondence when updating the list(s).
# Use lists, instead of dictionaries so the names can be displayed in a
# preferred order.
KEYWORD_NAMES = ['TTYPE', 'TFORM', 'TUNIT', 'TNULL', 'TSCAL', 'TZERO',
                 'TDISP', 'TBCOL', 'TDIM']
KEYWORD_ATTRIBUTES = ['name', 'format', 'unit', 'null', 'bscale', 'bzero',
                      'disp', 'start', 'dim']

# TFORM regular expression
TFORMAT_RE = re.compile(r'(?P<repeat>^[0-9]*)(?P<dtype>[A-Za-z])'
                         '(?P<option>[!-~]*)')

# table definition keyword regular expression
TDEF_RE = re.compile(r'(?P<label>^T[A-Z]*)(?P<num>[1-9][0-9 ]*$)')

ASCIITNULL = 0          # value for ASCII table cell with value = TNULL
                        # this can be reset by user.

DELAYED = "delayed"     # used for lazy instantiation of table column data


class Delayed:
    """Delayed file-reading data."""

    def __init__(self, hdu=None, field=None):
        self.hdu = weakref.ref(hdu)
        self.field = field

    def __getitem__(self, key):
        # This forces the data for the HDU to be read, which will replace
        # the corresponding Delayed objects in the Tables Columns to be
        # transformed into ndarrays.  It will also return the value of the
        # requested data element.
        return self.hdu().data[key][self.field]


class _FormatX(str):
    """For X format in binary tables."""

    pass


class _FormatP(str):
    """For P format in variable length table."""

    pass


class Column(object):
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
        for attr in KEYWORD_ATTRIBUTES:
            value = locals()[attr]           # get the argument's value

            if isinstance(value, Card):
                setattr(self, attr, value.value)
            else:
                setattr(self, attr, value)

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
                    format = _convert_format(recfmt, reverse=True)
                except ValueError:
                    raise ValueError('Illegal format `%s`.' % format)

            self.format = format

            # does not include Object array because there is no guarantee
            # the elements in the object array are consistent.
            if not isinstance(array,
                              (np.ndarray, chararray.chararray, Delayed)):
                try: # try to convert to a ndarray first
                    if array is not None:
                        array = np.array(array)
                except:
                    try: # then try to conver it to a strings array
                        array = chararray.array(array,
                                                itemsize=eval(recfmt[1:]))

                    # then try variable length array
                    except:
                        if isinstance(recfmt, _FormatP):
                            try:
                                array = _VLF(array)
                            except:
                                try:
                                    # this handles ['abc'] and [['a','b','c']]
                                    # equally, beautiful!
                                    _func = lambda x: \
                                                chararray.array(x, itemsize=1)
                                    array = _VLF(map(_func, array))
                                except:
                                    raise ValueError('Inconsistent input data '
                                                     'array: %s' % array)
                            array._dtype = recfmt._dtype
                        else:
                            raise ValueError('Data is inconsistent with the '
                                             'format `%s`.' % format)

        else:
            raise ValueError('Must specify format to construct Column.')

        # scale the array back to storage values if there is bscale/bzero
        if isinstance(array, np.ndarray):

            # boolean needs to be scaled too
            if recfmt[-2:] == FITS2NUMPY['L']:
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
        for cname in KEYWORD_ATTRIBUTES:
            value = getattr(self, cname)
            if value != None:
                text += cname + ' = ' + `value` + '\n'
        return text[:-1]

    def copy(self):
        """
        Return a copy of this `Column`.
        """
        tmp = Column(format='I') # just use a throw-away format
        tmp.__dict__ = self.__dict__.copy()
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

        from pyfits.hdu.table import _TableBaseHDU

        ascii_fmt = {'A': 'A1', 'I': 'I10', 'E': 'E14.6', 'F': 'F16.7',
                     'D': 'D24.16'}
        self._tbtype = tbtype

        if isinstance(input, ColDefs):
            self.data = [col.copy() for col in input.data]

        # if the input is a list of Columns
        elif isinstance(input, (list, tuple)):
            for col in input:
                if not isinstance(col, Column):
                    raise TypeError(
                           'Element %d in the ColDefs input is not a Column.'
                           % input.index(col))
            self.data = [col.copy() for col in input]

            # if the format of an ASCII column has no width, add one
            if tbtype == 'TableHDU':
                for i in range(len(self)):
                    (type, width) = _convert_ascii_format(self.data[i].format)
                    if width is None:
                        self.data[i].format = ascii_fmt[self.data[i].format[0]]


        elif isinstance(input, _TableBaseHDU):
            hdr = input._header
            _nfields = hdr['TFIELDS']
            self._width = hdr['NAXIS1']
            self._shape = hdr['NAXIS2']

            # go through header keywords to pick out column definition keywords
            # definition dictionaries for each field
            fdicts = [{} for i in range(_nfields)]
            for _card in hdr.ascardlist():
                _key = TDEF_RE.match(_card.key)
                try:
                    keyword = _key.group('label')
                except:
                    continue               # skip if there is no match
                if (keyword in KEYWORD_NAMES):
                    col = int(_key.group('num'))
                    if col <= _nfields and col > 0:
                        idx = KEYWORD_NAMES.index(keyword)
                        cname = KEYWORD_ATTRIBUTES[idx]
                        fdicts[col-1][cname] = _card.value

            # data reading will be delayed
            for col in range(_nfields):
                fdicts[col]['array'] = Delayed(input, col)

            # now build the columns
            tmp = [Column(**attrs) for attrs in fdicts]
            self.data = tmp
            self._listener = input
        else:
            raise TypeError('Input to ColDefs must be a table HDU or a list '
                            'of Columns.')

    def __getattr__(self, name):
        """
        Automatically returns the values for the given keyword attribute for
        all `Column`s in this list.

        Implements for example self.units, self.formats, etc.
        """

        cname = name[:-1]
        if cname in KEYWORD_ATTRIBUTES and name[-1] == 's':
            attr = [''] * len(self)
            for idx in range(len(self)):
                val = getattr(self[idx], cname)
                if val != None:
                    attr[idx] = val
            self.__dict__[name] = attr
            return self.__dict__[name]
        raise AttributeError(name)

    @lazyproperty
    def _arrays(self):
        return [col.array for col in self.data]

    @lazyproperty
    def _recformats(self):
        if self._tbtype in ('BinTableHDU', 'CompImageHDU'):
            return [_convert_format(fmt) for fmt in self.formats]
        elif self._tbtype == 'TableHDU':
            self._Formats = self.formats
            if len(self) == 1:
                dummy = []
            else:
                dummy = map(lambda x, y: x - y, self.starts[1:],
                            [self.starts[0]] + self.starts[1:-1])
            dummy.append(self._width - self.starts[-1] + 1)
            return map(lambda y: 'a' + repr(y), dummy)

    @lazyproperty
    def spans(self):
        # make sure to consider the case that the starting column of
        # a field may not be the column right after the last field
        if self._tbtype == 'TableHDU':
            last_end = 0
            spans = [0] * len(self)
            for i in range(len(self)):
                (_format, _width) = _convert_ascii_format(self.formats[i])
                if self.starts[i] is '':
                    self.starts[i] = last_end + 1
                _end = self.starts[i] + _width - 1
                spans[i] = _width
                last_end = _end
            self._width = _end
            return spans
        else:
            raise AttributeError('Attribute spans not defined.')

# TODO: Not sure why this is commented out; should it just go away?
#                # make sure to consider the case that the starting column of
#                # a field may not be the column right after the last field
#                elif tbtype == 'TableHDU':
#                    (_format, _width) = _convert_ascii_format(self.formats[i])
#                    if self.starts[i] is '':
#                        self.starts[i] = last_end + 1
#                    _end = self.starts[i] + _width - 1
#                    self.spans[i] = _end - last_end
#                    last_end = _end
#                    self._Formats = self.formats
#
#                self._arrays[i] = input[i].array

    def __getitem__(self, key):
        x = self.data[key]
        if isinstance(key, (int, long, np.integer)):
            return x
        else:
            return ColDefs(x)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return 'ColDefs' + repr(tuple(self.data))

    def __add__(self, other, option='left'):
        if isinstance(other, Column):
            b = [other]
        elif isinstance(other, ColDefs):
            b = list(other.data)
        else:
            raise TypeError('Wrong type of input.')
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
        indx = range(len(self))
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

        for cname in KEYWORD_ATTRIBUTES:
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

        for cname in KEYWORD_ATTRIBUTES:
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
            raise ValueError('New name %s already exists.' % new_name)
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
           `KEYWORD_ATTRIBUTES`.  The default is ``"all"`` which will print
           out all attributes.  It forgives plurals and blanks.  If
           there are two or more attribute names, they must be
           separated by comma(s).

        Notes
        -----
        This function doesn't return anything, it just prints to
        stdout.
        """

        if attrib.strip().lower() in ['all', '']:
            list = KEYWORD_ATTRIBUTES
        else:
            list = attrib.split(',')
            for i in range(len(list)):
                list[i]=list[i].strip().lower()
                if list[i][-1] == 's':
                    list[i]=list[i][:-1]

        for att in list:
            if att not in KEYWORD_ATTRIBUTES:
                print "'%s' is not an attribute of the column definitions."%att
                continue
            print "%s:" % att
            print '    ', getattr(self, att+'s')

    #def change_format(self, col_name, new_format):
        #new_format = _convert_format(new_format)
        #self.change_attrib(col_name, 'format', new_format)


class _VLF(np.ndarray):
    """Variable length field object."""

    def __new__(cls, args):
        """
        Parameters
        ----------
        args
            a sequence of variable-sized elements.
        """

        a = np.array(args, dtype=np.object)
        self = np.ndarray.__new__(cls, shape=(len(args)), buffer=a,
                                  dtype=np.object)
        self._max = 0
        return self

    def __array_finalize__(self, obj):
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

    if isinstance(key, (int, long, np.integer)):
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
                raise KeyError("Key '%s' does not exist." % key)
            else:              # multiple match
                raise KeyError("Ambiguous key name '%s'." % key)
    else:
        raise KeyError("Illegal key '%s'." % repr(key))

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


def _parse_tformat(tform):
    """Parse the ``TFORM`` value into `repeat`, `dtype`, and `option`."""

    try:
        (repeat, dtype, option) = TFORMAT_RE.match(tform.strip()).groups()
    except:
        warnings.warn('Format "%s" is not recognized.' % tform)


    if repeat == '': repeat = 1
    else: repeat = eval(repeat)

    return (repeat, dtype, option)


def _convert_format(input_format, reverse=0):
    """
    Convert FITS format spec to record format spec.  Do the opposite if
    reverse = 1.
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
        if dtype in FITS2NUMPY.keys():                            # FITS format
            if dtype == 'A':
                output_format = FITS2NUMPY[dtype]+`repeat`
                # to accomodate both the ASCII table and binary table column
                # format spec, i.e. A7 in ASCII table is the same as 7A in
                # binary table, so both will produce 'a7'.
                if fmt.lstrip()[0] == 'A' and option != '':
                    output_format = FITS2NUMPY[dtype]+`int(option)` # make sure option is integer
            else:
                _repeat = ''
                if repeat != 1:
                    _repeat = `repeat`
                output_format = _repeat+FITS2NUMPY[dtype]

        elif dtype == 'X':
            nbytes = ((repeat-1) // 8) + 1
            # use an array, even if it is only ONE u1 (i.e. use tuple always)
            output_format = _FormatX(`(nbytes,)`+'u1')
            output_format._nx = repeat

        elif dtype == 'P':
            output_format = _FormatP('2i4')
            output_format._dtype = FITS2NUMPY[option[0]]
        elif dtype == 'F':
            output_format = 'f8'
        else:
            raise ValueError('Illegal format %s.' % fmt)
    else:
        if dtype == 'a':
            # This is a kludge that will place string arrays into a
            # single field, so at least we won't lose data.  Need to
            # use a TDIM keyword to fix this, declaring as (slength,
            # dim1, dim2, ...)  as mwrfits does

            ntot = int(repeat)*int(option)

            output_format = str(ntot)+NUMPY2FITS[dtype]
        elif isinstance(dtype, _FormatX):
            warnings.warn('X format')
        elif dtype+option in NUMPY2FITS.keys():                    # record format
            _repeat = ''
            if repeat != 1:
                _repeat = `repeat`
            output_format = _repeat+NUMPY2FITS[dtype+option]
        else:
            raise ValueError('Illegal format %s.' % fmt)

    return output_format


def _convert_ascii_format(input_format):
    """Convert ASCII table format spec to record format spec."""

    ascii2rec = {'A': 'a', 'I': 'i4', 'F': 'f4', 'E': 'f4', 'D': 'f8'}
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
        raise ValueError('Illegal format `%s` for ASCII table.'
                         % input_format)

    return (dtype, width)
