import numpy as np
from numpy import char as chararray

from pyfits.card import Card


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

        from pyfits.core import Delayed, _convert_format, _FormatP, _VLF, \
                                _commonNames, _keyNames, _booltype

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
        from pyfits.core import Delayed, _convert_format, _parse_tformat

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
        from pyfits.core import _commonNames
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

        from pyfits.core import Delayed, _convert_ASCII_format, _tdef_re, \
                                _keyNames, _commonNames
        from pyfits.hdu.table import _TableBaseHDU

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

        from pyfits.core import _convert_format, _convert_ASCII_format, \
                                _commonNames

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
        from pyfits.core import _get_index

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
        from pyfits.core import _commonNames

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
        from pyfits.core import _commonNames, _get_index

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

        from pyfits.core import _get_index

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

        from pyfits.core import _commonNames

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
