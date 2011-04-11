from __future__ import division # confidence high


import re

import numpy as np
from numpy import char as chararray

from pyfits import rec
from pyfits.card import Card, CardList
# This module may have many dependencies on pyfits.column, but pyfits.column
# has fewer dependencies overall, so it's easier to keep table/column-related
# utilities in pyfits.column
from pyfits.column import FITS2NUMPY, KEYWORD_NAMES, KEYWORD_ATTRIBUTES, \
                          TDEF_RE, DELAYED, Delayed, Column, ColDefs, \
                          _ASCIIColDefs, _FormatX, _FormatP, _wrapx, _makep, \
                          _VLF, _parse_tformat, _convert_format
from pyfits.fitsrec import FITS_rec
from pyfits.hdu.base import _ValidHDU
from pyfits.hdu.extension import _ExtensionHDU
from pyfits.header import Header
from pyfits.util import Extendable, lazyproperty, _is_int, _str_to_num, \
                        _pad_length


class _TableLikeHDU(_ValidHDU):
    """
    A class for HDUs that have table-like data.  This is used for both
    Binary/ASCII tables as well as Random Access Group HDUs (which are
    otherwise too dissimlary for tables to use _TableBaseHDU directly).
    """

    @classmethod
    def match_header(cls, header):
        """
        This is an abstract HDU type for HDUs that contain table-like data.
        This is even more abstract than _TableBaseHDU which is specifically for
        the standard ASCII and Binary Table types.
        """

        raise NotImplementedError

    @lazyproperty
    def columns(self):
        # The base class doesn't make any assumptions about where the column
        # definitions come from, so just return an empty ColDefs
        return ColDefs([])

    def _get_tbdata(self):
        """Get the table data from an input HDU object."""

        columns = self.columns
        formats = ','.join(columns._recformats)
        dtype = rec.format_parser(formats, columns.names, None)._descr
        raw_data = self._file.readarray(offset=self._datLoc, dtype=dtype,
                                        shape=columns._shape)
        data = rec.recarray(shape=raw_data.shape, buf=raw_data,
                            dtype=raw_data.dtype, names=columns.names)
        self._init_tbdata(data)
        return data.view(FITS_rec)

    def _init_tbdata(self, data):
        columns = self.columns

        data.dtype = data.dtype.newbyteorder('>')

        # pass datLoc, for P format
        data._heapoffset = self._theap + self._datLoc
        data._file = self._file
        tbsize = self._header['NAXIS1'] * self._header['NAXIS2']
        data._gap = self._theap - tbsize

        # pass the attributes
        for attr in ['formats', 'names']:
            setattr(data, attr, getattr(columns, attr))
        for idx in range(len(columns)):
           # get the data for each column object from the rec.recarray
            columns.data[idx].array = data.field(idx)

        # delete the _arrays attribute so that it is recreated to point to the
        # new data placed in the column object above
        del columns._arrays


class _TableBaseHDU(_ExtensionHDU, _TableLikeHDU):
    """
    FITS table extension base HDU class.
    """

    def __init__(self, data=None, header=None, name=None):
        """
        Parameters
        ----------
        header : Header instance
            header to be used

        data : array
            data to be used

        name : str
            name to be populated in ``EXTNAME`` keyword
        """

        super(_TableBaseHDU, self).__init__(data=data, header=header)

        if header is not None and not isinstance(header, Header):
            raise ValueError('header must be a Header object.')

        if data is DELAYED:
            # this should never happen
            if header is None:
                raise ValueError('No header to setup HDU.')

            # if the file is read the first time, no need to copy, and keep it unchanged
            else:
                self._header = header
        else:
            # construct a list of cards of minimal header
            cards = CardList([
                Card('XTENSION',      '', ''),
                Card('BITPIX',         8, 'array data type'),
                Card('NAXIS',          2, 'number of array dimensions'),
                Card('NAXIS1',         0, 'length of dimension 1'),
                Card('NAXIS2',         0, 'length of dimension 2'),
                Card('PCOUNT',         0, 'number of group parameters'),
                Card('GCOUNT',         1, 'number of groups'),
                Card('TFIELDS',        0, 'number of table fields')
                ])

            if header is not None:
                # Make a "copy" (not just a view) of the input header, since it
                # may get modified.  the data is still a "view" (for now)
                hcopy = header.copy(strip=True)
                cards.extend(hcopy.ascardlist())

            self._header = Header(cards)

            if isinstance(data, np.ndarray) and data.dtype.fields is not None:
                if isinstance(data, FITS_rec):
                    self.data = data
                elif isinstance(data, rec.recarray):
                    self.data = FITS_rec(data)
                else:
                    self.data = data.view(FITS_rec)

                self._header['NAXIS1'] = self.data.itemsize
                self._header['NAXIS2'] = self.data.shape[0]
                self._header['TFIELDS'] = self.data._nfields

                if self.data._coldefs is None:
                    self.data._coldefs = ColDefs(data)

                self.columns = self.data._coldefs
                self.update()

                try:
                   # Make the ndarrays in the Column objects of the ColDefs
                   # object of the HDU reference the same ndarray as the HDU's
                   # FITS_rec object.
                    for idx in range(len(self.columns)):
                        self.columns.data[idx].array = self.data.field(idx)

                    # Delete the _arrays attribute so that it is recreated to
                    # point to the new data placed in the column objects above
                    del self.columns._arrays
                except (TypeError, AttributeError), e:
                    # This shouldn't happen as long as self.columns._arrays
                    # is a lazyproperty
                    pass
            elif data is None:
                pass
            else:
                raise TypeError('Table data has incorrect type.')

        if self._header[0].rstrip() != self._extension:
            self._header[0] = self._extension
            self._header.ascard[0].comment = self._ext_comment

    #def __del__(self):
    #    for c in self.columns:
    #        if hasattr(c, 'array') and hasattr(c.array, 'copy'):
    #            c.array = c.array.copy()
    #    del self.columns._arrays

    @classmethod
    def match_header(cls, header):
        """
        This is an abstract type that implements the shared functionality of
        the ASCII and Binary Table HDU types, which should be used instead of
        this.
        """

        raise NotImplementedError

    @lazyproperty
    def columns(self):
        return ColDefs(self)

    @lazyproperty
    def data(self):
        size = self.size()
        if size:
            data = self._get_tbdata()
            data._coldefs = self.columns
            data.formats = self.columns.formats
        else:
            data = None
        self._data_loaded = True
        return data

    @lazyproperty
    def _theap(self):
        size = self._header['NAXIS1'] * self._header['NAXIS2']
        return self._header.get('THEAP', size)

    @lazyproperty
    def _pcount(self):
        return self._header.get('PCOUNT', 0)

    def get_coldefs(self):
        """
        **[Deprecated]** Returns the table's column definitions.
        """

        return self.columns

    def update(self):
        """
        Update header keywords to reflect recent changes of columns.
        """

        update = self._header.update
        update('naxis1', self.data.itemsize, after='naxis')
        update('naxis2', self.data.shape[0], after='naxis1')
        update('tfields', len(self.columns), after='gcount')

        self._clear_table_keywords()
        self._populate_table_keywords()

    def copy(self):
        """
        Make a copy of the table HDU, both header and data are copied.
        """

        # touch the data, so it's defined (in the case of reading from a
        # FITS file)
        self.data
        return new_table(self.columns, header=self._header,
                         tbtype=self.columns._tbtype)

    def _verify(self, option='warn'):
        """
        _TableBaseHDU verify method.
        """

        errs = super(_TableBaseHDU, self)._verify(option=option)
        self.req_cards('NAXIS', None, lambda v: (v == 2), 2, option, errs)
        self.req_cards('BITPIX', None, lambda v: (v == 8), 8, option, errs)
        self.req_cards('TFIELDS', 7,
                       lambda v: (_is_int(v) and v >= 0 and v <= 999), 0,
                       option, errs)
        tfields = self._header['TFIELDS']
        for idx in range(tfields):
            self.req_cards('TFORM' + str(idx + 1), None, None, None, option,
                           errs)
        return errs

    def _summary(self):
        """
        Summarize the HDU: name, dimensions, and formats.
        """

        class_name = self.__class__.__name__

        # if data is touched, use data info.
        if self._data_loaded:
            if self.data is None:
                shape, format = (), ''
                nrows = 0
            else:
                nrows = len(self.data)

            ncols = len(self.columns.formats)
            format = self.columns.formats

        # if data is not touched yet, use header info.
        else:
            shape = ()
            nrows = self._header['NAXIS2']
            ncols = self._header['TFIELDS']
            format = ', '.join([self._header['TFORM' + str(j + 1)]
                                for j in range(ncols)])
            format = '[%s]' % format
        dims = "%dR x %dC" % (nrows, ncols)
        ncards = len(self._header.ascard)

        return "%-10s  %-11s  %5d  %-12s  %s" \
               % (self.name, class_name, ncards, dims, format)

    def _clear_table_keywords(self):
        """Wipe out any existing table definition keywords from the header."""

        # Go in reverse so as to not confusing indexing while deleting.
        for idx, card in enumerate(reversed(self._header.ascard)):
            key = TDEF_RE.match(card.key)
            try:
                keyword = key.group('label')
            except:
                continue                # skip if there is no match
            if (keyword in KEYWORD_NAMES):
                del self._header.ascard[idx]

    def _populate_table_keywords(self):
        """Populate the new table definition keywords from the header."""

        cols = self.columns
        append = self._header.ascard.append

        for idx, col in enumerate(cols):
            for attr, keyword in zip(KEYWORD_ATTRIBUTES, KEYWORD_NAMES):
                val = getattr(cols, attr + 's')[idx]
                if val:
                    keyword = keyword + str(idx + 1)
                    append(Card(keyword, val))



class TableHDU(_TableBaseHDU):
    """
    FITS ASCII table extension HDU class.
    """

    __metaclass__ = Extendable

    _extension = 'TABLE'
    _ext_comment = 'ASCII table extension'

    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')

    def __init__(self, data=None, header=None, name=None):
        super(TableHDU, self).__init__(data, header, name)
        if self._data_loaded and self.data is not None and \
           not isinstance(self.data._coldefs, _ASCIIColDefs):
            self.data._coldefs = _ASCIIColDefs(self.data._coldefs)

    @classmethod
    def match_header(cls, header):
        card = header.ascard[0]
        xtension = card.value.rstrip()
        return card.key == 'XTENSION' and xtension == cls._extension

    def _get_tbdata(self):
        columns = self.columns

        # determine if there are duplicate field names and if there
        # are throw an exception
        dup = rec.find_duplicate(columns.names)

        if dup:
            raise ValueError("Duplicate field names: %s" % dup)

        itemsize = columns.spans[-1] + columns.starts[-1]-1
        dtype = {}

        for idx in range(len(columns)):
            data_type = 'S' + str(columns.spans[idx])

            if idx == len(columns) - 1:
                # The last column is padded out to the value of NAXIS1
                if self._header['NAXIS1'] > itemsize:
                    data_type = 'S' + str(columns.spans[idx] + \
                                self._header['NAXIS1'] - itemsize)
            dtype[columns.names[idx]] = (data_type, columns.starts[idx] - 1)

        raw_data = self._file.readarray(offset=self._datLoc, dtype=dtype,
                                        shape=columns._shape)
        data = rec.recarray(shape=raw_data.shape, buf=raw_data,
                            dtype=raw_data.dtype, names=columns.names)

        self._init_tbdata(data)
        return data.view(FITS_rec)

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        if self._data_loaded and self.data is not None:
            # We have the data to be used.
            # We need to pad the data to a block length before calculating
            # the datasum.

            if self.size() > 0:
                d = np.append(np.fromstring(self.data, dtype='ubyte'),
                              np.fromstring(_pad_length(self.size()) * ' ',
                                            dtype='ubyte'))

            cs = self._compute_checksum(np.fromstring(d, dtype='ubyte'),
                                        blocking=blocking)
            return cs
        else:
            # This is the case where the data has not been read from the file
            # yet.  We can handle that in a generic manner so we do it in the
            # base class.  The other possibility is that there is no data at
            # all.  This can also be handled in a gereric manner.
            return super(TableHDU, self)._calculate_datasum(blocking)

    def _verify(self, option='warn'):
        """
        `TableHDU` verify method.
        """

        errs = super(TableHDU, self)._verify(option=option)
        self.req_cards('PCOUNT', None, lambda v: (v == 0), 0, option, errs)
        tfields = self._header['TFIELDS']
        for idx in range(tfields):
            self.req_cards('TBCOL' + str(idx + 1), None, _is_int, None, option,
                           errs)
        return errs


class BinTableHDU(_TableBaseHDU):
    """
    Binary table HDU class.
    """

    __metaclass__ = Extendable

    _extension = 'BINTABLE'
    _ext_comment = 'binary table extension'

    @classmethod
    def match_header(cls, header):
        card = header.ascard[0]
        xtension = card.value.rstrip()
        return card.key == 'XTENSION' and \
               xtension in (cls._extension, 'A3DTABLE')

    def _calculate_datasum_from_data(self, data, blocking):
        """
        Calculate the value for the ``DATASUM`` card given the input data
        """

        # Check the byte order of the data.  If it is little endian we
        # must swap it before calculating the datasum.
        for i in range(data._nfields):
            coldata = data.field(i)

            if not isinstance(coldata, chararray.chararray):
                if isinstance(coldata, _VLF):
                    for j, d in enumerate(coldata):
                        if not isinstance(d, chararray.chararray):
                            if d.itemsize > 1:
                                if d.dtype.str[0] != '>':
                                    d[:] = d.byteswap()
                                    d.dtype = d.dtype.newbyteorder('>')
                        # TODO: Any reason this isn't just data.field(i)?
                        field = rec.recarray.field(data, i)[j:j + 1]
                        if field.dtype.str[0] != '>':
                            field.byteswap(True)
                else:
                    if coldata.itemsize > 1:
                        if data.field(i).dtype.str[0] != '>':
                            data.field(i)[:] = data.field(i).byteswap()
        data.dtype = data.dtype.newbyteorder('>')

        dout = np.fromstring(data, dtype='ubyte')

        for i in range(data._nfields):
            if isinstance(data._coldefs._recformats[i], _FormatP):
                for coldata in data.field(i):
                    if len(coldata) > 0:
                        dout = np.append(dout,
                                         np.fromstring(coldata, dtype='ubyte'))

        cs = self._compute_checksum(dout, blocking=blocking)
        return cs

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        if self._data_loaded and self.data is not None:
            # We have the data to be used.
            return self._calculate_datasum_from_data(self.data, blocking)
        else:
            # This is the case where the data has not been read from the file
            # yet.  We can handle that in a generic manner so we do it in the
            # base class.  The other possibility is that there is no data at
            # all.  This can also be handled in a gereric manner.
            return super(BinTableHDU,self)._calculate_datasum(blocking)

    def _populate_table_keywords(self):
        """Populate the new table definition keywords from the header."""

        cols = self.columns
        append = self._header.ascard.append

        for idx, col in enumerate(cols):
            for attr, keyword in zip(KEYWORD_ATTRIBUTES, KEYWORD_NAMES):
                val = getattr(cols, attr + 's')[idx]
                if val:
                    keyword = keyword + str(idx + 1)
                    if attr == 'format':
                        val = cols._recformats[idx]
                        if isinstance(val, _FormatX):
                            val = repr(val._nx) + 'X'
                        elif isinstance(val, _FormatP):
                            VLdata = self.data.field(idx)
                            VLdata._max = max(map(len, VLdata))
                            if val._dtype == 'a':
                                fmt = 'A'
                            else:
                                fmt = _convert_format(val._dtype, reverse=True)
                            val = 'P%s(%d)' % (fmt, VLdata._max)
                        else:
                            val = _convert_format(val, reverse=True)
                    append(Card(keyword, val))

    tdump_file_format = """

- **datafile:** Each line of the data file represents one row of table
  data.  The data is output one column at a time in column order.  If
  a column contains an array, each element of the column array in the
  current row is output before moving on to the next column.  Each row
  ends with a new line.

  Integer data is output right-justified in a 21-character field
  followed by a blank.  Floating point data is output right justified
  using 'g' format in a 21-character field with 15 digits of
  precision, followed by a blank.  String data that does not contain
  whitespace is output left-justified in a field whose width matches
  the width specified in the ``TFORM`` header parameter for the
  column, followed by a blank.  When the string data contains
  whitespace characters, the string is enclosed in quotation marks
  (``""``).  For the last data element in a row, the trailing blank in
  the field is replaced by a new line character.

  For column data containing variable length arrays ('P' format), the
  array data is preceded by the string ``'VLA_Length= '`` and the
  integer length of the array for that row, left-justified in a
  21-character field, followed by a blank.

  For column data representing a bit field ('X' format), each bit
  value in the field is output right-justified in a 21-character field
  as 1 (for true) or 0 (for false).

- **cdfile:** Each line of the column definitions file provides the
  definitions for one column in the table.  The line is broken up into
  8, sixteen-character fields.  The first field provides the column
  name (``TTYPEn``).  The second field provides the column format
  (``TFORMn``).  The third field provides the display format
  (``TDISPn``).  The fourth field provides the physical units
  (``TUNITn``).  The fifth field provides the dimensions for a
  multidimensional array (``TDIMn``).  The sixth field provides the
  value that signifies an undefined value (``TNULLn``).  The seventh
  field provides the scale factor (``TSCALn``).  The eighth field
  provides the offset value (``TZEROn``).  A field value of ``""`` is
  used to represent the case where no value is provided.

- **hfile:** Each line of the header parameters file provides the
  definition of a single HDU header card as represented by the card
  image.
"""

    def tdump(self, datafile=None, cdfile=None, hfile=None, clobber=False):
        """
        Dump the table HDU to a file in ASCII format.  The table may be dumped
        in three separate files, one containing column definitions, one
        containing header parameters, and one for table data.

        Parameters
        ----------
        datafile : file path, file object or file-like object, optional
            Output data file.  The default is the root name of the
            fits file associated with this HDU appended with the
            extension ``.txt``.

        cdfile : file path, file object or file-like object, optional
            Output column definitions file.  The default is `None`, no
            column definitions output is produced.

        hfile : file path, file object or file-like object, optional
            Output header parameters file.  The default is `None`,
            no header parameters output is produced.

        clobber : bool
            Overwrite the output files if they exist.

        Notes
        -----
        The primary use for the `tdump` method is to allow editing in a
        standard text editor of the table data and parameters.  The
        `tcreate` method can be used to reassemble the table from the
        three ASCII files.
        """

        # TODO: This is looking pretty long and complicated--might be a few
        # places we can break this up into smaller functions

        # check if the output files already exist
        exist = []
        files = [datafile, cdfile, hfile]

        for f in files:
            if isinstance(f, basestring):
                if os.path.exists(f) and os.path.getsize(f) != 0:
                    if clobber:
                        warnings.warn("Overwriting existing file '%s'." % f)
                        os.remove(f)
                    else:
                        exist.append(f)

        if exist:
            raise IOError('  '.join(["File '%s' already exists."
                                     for f in exist]))

        # Process the data

        if not datafile:
            root, ext = os.path.splitext(self._file.name)
            datafile = root + '.txt'

        closeDfile = False

        if isinstance(datafile, basestring):
            datafile = open(datafile, 'w')
            closeDfile = True

        dlines = []   # lines to go out to the data file

        # Process each row of the table and output the result to the dlines
        # list.

        for i in range(len(self.data)):
            line = ''   # the line for this row of the table

            # Process each column of the row.

            for name in self.columns.names:
                VLA_format = None   # format of data in a variable length array
                                    # where None means it is not a VLA
                fmt = _convert_format(
                      self.columns.formats[self.columns.names.index(name)])

                if isinstance(fmt, _FormatP):
                    # P format means this is a variable length array so output
                    # the length of the array for this row and set the format
                    # for the VLA data
                    line = line + "VLA_Length= %-21d " % \
                                  len(self.data.field(name)[i])
                    (repeat,dtype,option) = _parse_tformat(
                         self.columns.formats[self.columns.names.index(name)])
                    VLA_format =  FITS2NUMPY[option[0]][0]

                if self.data.dtype.fields[name][0].subdtype:
                    # The column data is an array not a single element

                    if VLA_format:
                        arrayFormat = VLA_format
                    else:
                        arrayFormat = \
                              self.data.dtype.fields[name][0].subdtype[0].char

                    # Output the data for each element in the array

                    for val in self.data.field(name)[i].flat:
                        if arrayFormat == 'S':
                            # output string

                            if len(string.split(val)) != 1:
                                # there is whitespace in the string so put it
                                # in quotes
                                width = val.itemsize + 3
                                str = '"' + val + '" '
                            else:
                                # no whitespace
                                width = val.itemsize + 1
                                str = val

                            line = line + '%-*s' % (width, str)
                        elif arrayFormat in np.typecodes['AllInteger']:
                            # output integer
                            line = line + '%21d ' % val
                        elif arrayFormat in np.typecodes['AllFloat']:
                            # output floating point
                            line = line + '%#21.15g ' % val
                else:
                    # The column data is a single element
                    arrayFormat = self.data.dtype.fields[name][0].char

                    if arrayFormat == 'S':
                        # output string

                        if len(string.split(self.data.field(name)[i])) != 1:
                            # there is whitespace in the string so put it
                            # in quotes
                            width = self.data.dtype.fields[name][0].itemsize+3
                            str = '"' + self.data.field(name)[i] + '" '
                        else:
                            # no whitespace
                            width = self.data.dtype.fields[name][0].itemsize+1
                            str = self.data.field(name)[i]

                        line = line + '%-*s'%(width,str)
                    elif arrayFormat in np.typecodes['AllInteger']:
                        # output integer
                        line = line + '%21d ' % self.data.field(name)[i]
                    elif arrayFormat in np.typecodes['AllFloat']:
                        # output floating point
                        line = line + '%21.15g ' % self.data.field(name)[i]

            # Replace the trailing blank in the line with a new line
            # and append the line for this row to the list of data lines
            line = line[:-1] + '\n'
            dlines.append(line)

        # Write the data lines out to the ASCII data file
        datafile.writelines(dlines)

        if closeDfile:
            datafile.close()

        # Process the column definitions

        if cdfile:
            closeCdfile = False

            if isinstance(cdfile, basestring):
                cdfile = open(cdfile, 'w')
                closeCdfile = True

            cdlines = []   # lines to go out to the column definitions file

            # Process each column of the table and output the result to the
            # cdlines list

            for j in range(len(self.columns.formats)):
                disp = self.columns.disps[j]

                if disp == '':
                    disp = '""'  # output "" if value is not set

                unit = self.columns.units[j]

                if unit == '':
                    unit = '""'

                dim = self.columns.dims[j]

                if dim == '':
                    dim = '""'

                null = self.columns.nulls[j]

                if null == '':
                    null = '""'

                bscale = self.columns.bscales[j]

                if bscale == '':
                    bscale = '""'

                bzero = self.columns.bzeros[j]

                if bzero == '':
                    bzero = '""'

                #Append the line for this column to the list of output lines
                cdlines.append(
                   "%-16s %-16s %-16s %-16s %-16s %-16s %-16s %-16s\n" %
                   (self.columns.names[j], self.columns.formats[j],
                    disp, unit, dim, null, bscale, bzero))

            # Write the column definition lines out to the ASCII column
            # definitions file
            cdfile.writelines(cdlines)

            if closeCdfile:
                cdfile.close()

        # Process the header parameters

        if hfile:
            self.header.toTxtFile(hfile)
    tdump.__doc__ += tdump_file_format.replace('\n', '\n        ')

    def tcreate(self, datafile, cdfile=None, hfile=None, replace=False):
        """
        Create a table from the input ASCII files.  The input is from up to
        three separate files, one containing column definitions, one containing
        header parameters, and one containing column data.  The column
        definition and header parameters files are not required.  When absent
        the column definitions and/or header parameters are taken from the
        current values in this HDU.

        Parameters
        ----------
        datafile : file path, file object or file-like object
            Input data file containing the table data in ASCII format.

        cdfile : file path, file object, file-like object, optional
            Input column definition file containing the names,
            formats, display formats, physical units, multidimensional
            array dimensions, undefined values, scale factors, and
            offsets associated with the columns in the table.  If
            `None`, the column definitions are taken from the current
            values in this object.

        hfile : file path, file object, file-like object, optional
            Input parameter definition file containing the header
            parameter definitions to be associated with the table.  If
            `None`, the header parameter definitions are taken from
            the current values in this objects header.

        replace : bool
            When `True`, indicates that the entire header should be
            replaced with the contents of the ASCII file instead of
            just updating the current header.

        Notes
        -----
        The primary use for the `tcreate` method is to allow the input
        of ASCII data that was edited in a standard text editor of the
        table data and parameters.  The `tdump` method can be used to
        create the initial ASCII files.
        """
        # Process the column definitions file

        # TODO: This also might be good to break up a bit.

        if cdfile:
            closeCdfile = False

            if isinstance(cdfile, basestring):
                cdfile = open(cdfile, 'r')
                closeCdfile = True

            cdlines = cdfile.readlines()

            if closeCdfile:
                cdfile.close()

            self.columns.names = []
            self.columns.formats = []
            self.columns.disps = []
            self.columns.units = []
            self.columns.dims = []
            self.columns.nulls = []
            self.columns.bscales = []
            self.columns.bzeros = []

            for line in cdlines:
                words = line[:-1].split()
                self.columns.names.append(words[0])
                self.columns.formats.append(words[1])
                self.columns.disps.append(words[2].replace('""', ''))
                self.columns.units.append(words[3].replace('""', ''))
                self.columns.dims.append(words[4].replace('""', ''))
                null = words[5].replace('""', '')

                if null:
                    self.columns.nulls.append(_str_to_num(null))
                else:
                    self.columns.nulls.append(null)

                bscale = words[6].replace('""', '')

                if bscale:
                    self.columns.bscales.append(_str_to_num(bscape))
                else:
                    self.columns.bscales.append(bscale)

                bzero = words[7].replace('""', '')

                if bzero:
                    self.columns.bzeros.append(_str_to_num(bzero))
                else:
                    self.columns.bzeros.append(bzero)

        # Process the parameter file

        if hfile:
            self._header.fromTxtFile(hfile, replace)

        # Process the data file

        closeDfile = False

        if isinstance(datafile, basestring):
            datafile = open(datafile, 'r')
            closeDfile = True

        dlines = datafile.readlines()

        if closeDfile:
            datafile.close()

        arrays = []
        VLA_formats = []
        X_format_size = []
        recFmts = []

        for i in range(len(self.columns.names)):
            arrayShape = len(dlines)
            recFmt = _convert_format(self.columns.formats[i])
            recFmts.append(recFmt[0])
            X_format_size = X_format_size + [-1]

            if isinstance(recFmt, _FormatP):
                recFmt = 'O'
                (repeat,dtype,option) = _parse_tformat(self.columns.formats[i])
                VLA_formats = VLA_formats + [FITS2NUMPY[option[0]]]
            elif isinstance(recFmt, _FormatX):
                recFmt = np.uint8
                (X_format_size[i],dtype,option) = \
                                     _parse_tformat(self.columns.formats[i])
                arrayShape = (len(dlines), X_format_size[i])

            arrays.append(np.empty(arrayShape,recFmt))

        lineNo = 0

        for line in dlines:
            words = []
            idx = 0
            VLA_Lengths = []

            while idx < len(line):
                if line[idx:idx+12] == 'VLA_Length= ':
                    VLA_Lengths = VLA_Lengths + [int(line[idx+12:idx+34])]
                    idx += 34

                idx1 = line[idx:].find('"')

                if idx1 >=0:
                    words = words + line[idx:idx+idx1].split()
                    idx2 = line[idx+idx1+1:].find('"')
                    words = words + [line[idx1+1:idx1+idx2+1]]
                    idx = idx + idx1 + idx2 + 2
                else:
                    idx2 = line[idx:].find('VLA_Length= ')

                    if idx2 < 0:
                        words = words + line[idx:].split()
                        idx = len(line)
                    else:
                        words = words + line[idx:idx+idx2].split()
                        idx = idx + idx2

            idx = 0
            VLA_idx = 0

            for i in range(len(self.columns.names)):

                if arrays[i].dtype == 'object':
                    arrays[i][lineNo] = np.array(
                     words[idx:idx+VLA_Lengths[VLA_idx]],VLA_formats[VLA_idx])
                    idx += VLA_Lengths[VLA_idx]
                    VLA_idx += 1
                elif X_format_size[i] >= 0:
                    arrays[i][lineNo] = words[idx:idx+X_format_size[i]]
                    idx += X_format_size[i]
                elif isinstance(arrays[i][lineNo], np.ndarray):
                    arrays[i][lineNo] = words[idx:idx+arrays[i][lineNo].size]
                    idx += arrays[i][lineNo].size
                else:
                    if recFmts[i] == 'a':
                        # make sure character arrays are blank filled
                        arrays[i][lineNo] = words[idx]+(arrays[i].itemsize-
                                                        len(words[idx]))*' '
                    else:
                        arrays[i][lineNo] = words[idx]

                    idx += 1

            lineNo += 1

        columns = []

        for i in range(len(self.columns.names)):
            columns.append(Column(name=self.columns.names[i],
                                  format=self.columns.formats[i],
                                  disp=self.columns.disps[i],
                                  unit=self.columns.units[i],
                                  null=self.columns.nulls[i],
                                  bscale=self.columns.bscales[i],
                                  bzero=self.columns.bzeros[i],
                                  dim=self.columns.dims[i],
                                  array=arrays[i]))

        tmp = new_table(columns, self.header)
        self.__dict__ = tmp.__dict__
    tcreate.__doc__ += tdump_file_format.replace("\n", "\n        ")


# TODO: Allow tbtype to be either a string or a class; perhaps eventually
# replace this with separate functions for creating tables (possibly in the
# form of a classmethod)
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
    # TODO: Something needs to be done about this....
    hdu = eval(tbtype)(header=header)

    if isinstance(input, ColDefs):
        # NOTE: This previously raised an error if the tbtype didn't match the
        # tbtype of the input ColDefs. This should no longer be necessary, but
        # just beware.
        tmp = hdu.columns = ColDefs(input)
    elif isinstance(input, FITS_rec): # input is a FITS_rec
        # Create a new ColDefs object from the input FITS_rec's ColDefs
        # object and assign it to the ColDefs attribute of the new hdu.
        tmp = hdu.columns = ColDefs(input._coldefs, tbtype)
    else: # input is a list of Columns or possibly a recarray
        # Create a new ColDefs object from the input list of Columns and
        # assign it to the ColDefs attribute of the new hdu.
        tmp = hdu.columns = ColDefs(input, tbtype)

    # read the delayed data
    for i in range(len(tmp)):
        _arr = tmp._arrays[i]
        if isinstance(_arr, Delayed):
            if _arr.hdu().data is None:
                tmp._arrays[i] = None
            else:
                # TODO: Why not _arr.hdu().data.field()?
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
        tmp = hdu.columns = _ASCIIColDefs(hdu.columns)
        _itemsize = tmp.spans[-1] + tmp.starts[-1]-1
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
    hdu._data_loaded = True

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
            elif tmp._recformats[i][-2:] == FITS2NUMPY['L'] and \
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
    del hdu.columns._arrays

    return hdu
