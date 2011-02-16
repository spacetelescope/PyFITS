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
                          _FormatX, _FormatP, _wrapx, _makep, _VLF, \
                          _parse_tformat, _convert_format
from pyfits.fitsrec import FITS_rec
from pyfits.hdu.base import _AllHDU, _isInt
from pyfits.hdu.extension import _ExtensionHDU
from pyfits.util import lazyproperty


class _TableBaseHDU(_ExtensionHDU):
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

        from pyfits.header import Header

        super(_TableBaseHDU, self).__init__(data=data, header=header)

        if header is not None:
            if not isinstance(header, Header):
                raise ValueError, "header must be a Header object"

        if data is DELAYED:

            # this should never happen
            if header is None:
                raise ValueError('No header to setup HDU.')

            # if the file is read the first time, no need to copy, and keep it unchanged
            else:
                self._header = header
        else:

            # construct a list of cards of minimal header
            _list = CardList([
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
                hcopy = header.copy()
                hcopy._strip()
                _list.extend(hcopy.ascardlist())

            self._header = Header(_list)

        if (data is not DELAYED):
            if isinstance(data,np.ndarray) and not data.dtype.fields == None:
                if isinstance(data, FITS_rec):
                    self.data = data
                elif isinstance(data, rec.recarray):
                    self.data = FITS_rec(data)
                else:
                    self.data = data.view(FITS_rec)

                self._header['NAXIS1'] = self.data.itemsize
                self._header['NAXIS2'] = self.data.shape[0]
                self._header['TFIELDS'] = self.data._nfields

                # TODO: This is almost exactly identical to code in 
                # FITS_rec.__array_finalize__; we should centralize it
                # somewhere (the purpose of the code is to create a ColDefs
                # from a recarray-like object
                if self.data._coldefs is None:
                    #
                    # The data does not have a _coldefs attribute so
                    # create one from the underlying recarray.
                    #
                    columns = []

                    for i in range(len(data.dtype.names)):
                       cname = data.dtype.names[i]

                       if data.dtype.fields[cname][0].type == np.string_:
                           format = \
                            'A'+str(data.dtype.fields[cname][0].itemsize)
                       else:
                           format = \
                            _convert_format(data.dtype.fields[cname][0].str[1:],
                            True)

                       c = Column(name=cname,format=format,array=data[cname])
                       columns.append(c)

                    tbtype = 'BinTableHDU'
                    try:
                        if self._extension == 'TABLE':
                            tbtype = 'TableHDU'
                    except AttributeError:
                        pass

                    self.data._coldefs = ColDefs(columns, tbtype=tbtype)

                self.columns = self.data._coldefs
                self.update()

                try:
                   # Make the ndarrays in the Column objects of the ColDefs
                   # object of the HDU reference the same ndarray as the HDU's
                   # FITS_rec object.
                    for i in range(len(self.columns)):
                        self.columns.data[i].array = self.data.field(i)

                    # Delete the _arrays attribute so that it is recreated to
                    # point to the new data placed in the column objects above
                    if self.columns.__dict__.has_key('_arrays'):
                        del self.columns.__dict__['_arrays']
                except (TypeError, AttributeError), e:
                    pass
            elif data is None:
                pass
            else:
                raise TypeError, "table data has incorrect type"

        #  set extension name
        if not name and self._header.has_key('EXTNAME'):
            name = self._header['EXTNAME']
        self.name = name

    @lazyproperty
    def data(self):
        size = self.size()
        if size:
            self._file.seek(self._datLoc)
            data = _get_tbdata(self)
            data._coldefs = self.columns
            data.formats = self.columns.formats
#                print "Got data?"
        else:
            data = None
        self._data_loaded = True
        return data

    @lazyproperty
    def columns(self):
        class_name = str(self.__class__)
        class_name = class_name[class_name.rfind('.')+1:-2]
        return ColDefs(self, tbtype=class_name)

    @lazyproperty
    def _theap(self):
        return self._header.get('THEAP', self._header['NAXIS1']*self._header['NAXIS2'])

    @lazyproperty
    def _pcount(self):
        return self._header.get('PCOUNT', 0)

    def _summary(self):
        """
        Summarize the HDU: name, dimensions, and formats.
        """

        class_name  = str(self.__class__)
        type  = class_name[class_name.rfind('.')+1:-2]

        # if data is touched, use data info.
        if self._data_loaded:
            if self.data is None:
                _shape, _format = (), ''
                _nrows = 0
            else:
                _nrows = len(self.data)

            _ncols = len(self.columns.formats)
            _format = self.columns.formats

        # if data is not touched yet, use header info.
        else:
            _shape = ()
            _nrows = self._header['NAXIS2']
            _ncols = self._header['TFIELDS']
            _format = ', '.join([self._header['TFORM' + str(j + 1)]
                                 for j in range(_ncols)])
            _format = '[%s]' % _format
        _dims = "%dR x %dC" % (_nrows, _ncols)

        return "%-10s  %-11s  %5d  %-12s  %s" % \
            (self.name, type, len(self._header.ascard), _dims, _format)

    def get_coldefs(self):
        """
        Returns the table's column definitions.
        """
        return self.columns

    def update(self):
        """
        Update header keywords to reflect recent changes of columns.
        """

        _update = self._header.update
        _append = self._header.ascard.append
        _cols = self.columns
        _update('naxis1', self.data.itemsize, after='naxis')
        _update('naxis2', self.data.shape[0], after='naxis1')
        _update('tfields', len(_cols), after='gcount')

        # Wipe out the old table definition keywords.  Mark them first,
        # then delete from the end so as not to confuse the indexing.
        _list = []
        for i in range(len(self._header.ascard)-1,-1,-1):
            _card = self._header.ascard[i]
            _key = TDEF_RE.match(_card.key)
            try: keyword = _key.group('label')
            except: continue                # skip if there is no match
            if (keyword in KEYWORD_NAMES):
                _list.append(i)
        for i in _list:
            del self._header.ascard[i]
        del _list

        # populate the new table definition keywords
        for i in range(len(_cols)):
            for cname in KEYWORD_ATTRIBUTES:
                val = getattr(_cols, cname+'s')[i]
                if val != '':
                    keyword = KEYWORD_NAMES[KEYWORD_ATTRIBUTES.index(cname)]+`i+1`
                    if cname == 'format' and isinstance(self, BinTableHDU):
                        val = _cols._recformats[i]
                        if isinstance(val, _FormatX):
                            val = `val._nx` + 'X'
                        elif isinstance(val, _FormatP):
                            VLdata = self.data.field(i)
                            VLdata._max = max(map(len, VLdata))
                            if val._dtype == 'a':
                                fmt = 'A'
                            else:
                                fmt = _convert_format(val._dtype, reverse=1)
                            val = 'P' + fmt + '(%d)' %  VLdata._max
                        else:
                            val = _convert_format(val, reverse=1)
                    #_update(keyword, val)
                    _append(Card(keyword, val))

    def copy(self):
        """
        Make a copy of the table HDU, both header and data are copied.
        """
        # touch the data, so it's defined (in the case of reading from a
        # FITS file)
        self.data
        return new_table(self.columns, header=self._header, tbtype=self.columns._tbtype)

    def _verify(self, option='warn'):
        """
        _TableBaseHDU verify method.
        """
        _err = _ExtensionHDU._verify(self, option=option)
        self.req_cards('NAXIS', None, 'val == 2', 2, option, _err)
        self.req_cards('BITPIX', None, 'val == 8', 8, option, _err)
        self.req_cards('TFIELDS', '== 7', _isInt+" and val >= 0 and val <= 999", 0, option, _err)
        tfields = self._header['TFIELDS']
        for i in range(tfields):
            self.req_cards('TFORM'+`i+1`, None, None, None, option, _err)
        return _err


class TableHDU(_TableBaseHDU):
    """
    FITS ASCII table extension HDU class.
    """

    _extension = 'TABLE'

    __format_RE = re.compile(
        r'(?P<code>[ADEFI])(?P<width>\d+)(?:\.(?P<prec>\d+))?')

    def __init__(self, data=None, header=None, name=None):
        """
        Parameters
        ----------
        data : array
            data of the table

        header : Header instance
            header to be used for the HDU

        name : str
            the ``EXTNAME`` value
        """

        super(TableHDU, self).__init__(data=data, header=header, name=name)

        if self._header[0].rstrip() != self._extension:
            self._header[0] = self._extension
            self._header.ascard[0].comment = 'ASCII table extension'
    '''
    def format(self):
        strfmt, strlen = '', 0
        for j in range(self._header['TFIELDS']):
            bcol = self._header['TBCOL'+`j+1`]
            valu = self._header['TFORM'+`j+1`]
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

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        from pyfits.file import _pad_length

        if self.__dict__.has_key('data') and self.data != None:
            # We have the data to be used.
            # We need to pad the data to a block length before calculating
            # the datasum.

            if self.size() > 0:
                d = np.append(np.fromstring(self.data, dtype='ubyte'),
                              np.fromstring(_pad_length(self.size())*' ',
                                            dtype='ubyte'))

            cs = self._compute_checksum(np.fromstring(d, dtype='ubyte'), blocking=blocking)
            return cs
        else:
            # This is the case where the data has not been read from the file
            # yet.  We can handle that in a generic manner so we do it in the
            # base class.  The other possibility is that there is no data at
            # all.  This can also be handled in a gereric manner.
            return super(TableHDU,self)._calculate_datasum(blocking)

    def _verify(self, option='warn'):
        """
        `TableHDU` verify method.
        """
        _err = _TableBaseHDU._verify(self, option=option)
        self.req_cards('PCOUNT', None, 'val == 0', 0, option, _err)
        tfields = self._header['TFIELDS']
        for i in range(tfields):
            self.req_cards('TBCOL'+`i+1`, None, _isInt, None, option, _err)
        return _err


class BinTableHDU(_TableBaseHDU):
    """
    Binary table HDU class.
    """

    _extension = 'BINTABLE'

    def __init__(self, data=None, header=None, name=None):
        """
        Parameters
        ----------
        data : array
            data of the table

        header : Header instance
            header to be used for the HDU

        name : str
            the ``EXTNAME`` value
        """

        super(BinTableHDU, self).__init__(data=data, header=header, name=name)

        hdr = self._header
        if hdr[0] != self._extension:
            hdr[0] = self._extension
            hdr.ascard[0].comment = 'binary table extension'

        self._header._hdutype = BinTableHDU

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
                    k = 0
                    for j in coldata:
                        if not isinstance(j, chararray.chararray):
                            if j.itemsize > 1:
                                if j.dtype.str[0] != '>':
                                    j[:] = j.byteswap()
                                    j.dtype = j.dtype.newbyteorder('>')
                        if rec.recarray.field(data,i)[k:k+1].dtype.str[0]!='>':
                            rec.recarray.field(data,i)[k:k+1].byteswap(True)
                        k = k + 1
                else:
                    if coldata.itemsize > 1:
                        if data.field(i).dtype.str[0] != '>':
                            data.field(i)[:] = data.field(i).byteswap()
        data.dtype = data.dtype.newbyteorder('>')

        dout=np.fromstring(data, dtype='ubyte')

        for i in range(data._nfields):
            if isinstance(data._coldefs._recformats[i], _FormatP):
                for j in range(len(data.field(i))):
                    coldata = data.field(i)[j]
                    if len(coldata) > 0:
                        dout = np.append(dout,
                                    np.fromstring(coldata,dtype='ubyte'))

        cs = self._compute_checksum(dout, blocking=blocking)
        return cs

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """
        if self.__dict__.has_key('data') and self.data != None:
            # We have the data to be used.
            return self._calculate_datasum_from_data(self.data, blocking)
        else:
            # This is the case where the data has not been read from the file
            # yet.  We can handle that in a generic manner so we do it in the
            # base class.  The other possibility is that there is no data at
            # all.  This can also be handled in a gereric manner.
            return super(BinTableHDU,self)._calculate_datasum(blocking)

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
        # check if the output files already exist
        exceptMessage = 'File '
        files = [datafile, cdfile, hfile]

        for f in files:
            if (isinstance(f,types.StringType) or
                isinstance(f,types.UnicodeType)):
                if (os.path.exists(f) and os.path.getsize(f) != 0):
                    if clobber:
                        warnings.warn(" Overwrite existing file '%s'." % f)
                        os.remove(f)
                    else:
                        exceptMessage = exceptMessage + "'%s', " % f

        if exceptMessage != 'File ':
            exceptMessage = exceptMessage[:-2] + ' already exist.'
            raise IOError, exceptMessage

        # Process the data

        if not datafile:
            root,ext = os.path.splitext(self._file.name)
            datafile = root + '.txt'

        closeDfile = False

        if isinstance(datafile, types.StringType) or \
           isinstance(datafile, types.UnicodeType):
            datafile = __builtin__.open(datafile,'w')
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
                                width = val.itemsize+3
                                str = '"' + val + '" '
                            else:
                                # no whitespace
                                width = val.itemsize+1
                                str = val

                            line = line + '%-*s'%(width,str)
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

            if isinstance(cdfile, types.StringType) or \
               isinstance(cdfile, types.UnicodeType):
                cdfile = __builtin__.open(cdfile,'w')
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
                   (self.columns.names[j],self.columns.formats[j],
                    disp, unit, dim, null, bscale, bzero))

            # Write the column definition lines out to the ASCII column
            # definitions file
            cdfile.writelines(cdlines)

            if closeCdfile:
                cdfile.close()

        # Process the header parameters

        if hfile:
            self.header.toTxtFile(hfile)

    tdumpFileFormat = """

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

    tdump.__doc__ += tdumpFileFormat.replace("\n", "\n        ")

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

        if cdfile:
            closeCdfile = False

            if isinstance(cdfile, types.StringType) or \
               isinstance(cdfile, types.UnicodeType):
                cdfile = __builtin__.open(cdfile,'r')
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
                words = string.split(line[:-1])
                self.columns.names.append(words[0])
                self.columns.formats.append(words[1])
                self.columns.disps.append(string.replace(words[2],'""',''))
                self.columns.units.append(string.replace(words[3],'""',''))
                self.columns.dims.append(string.replace(words[4],'""',''))
                null = string.replace(words[5],'""','')

                if null != '':
                    self.columns.nulls.append(eval(null))
                else:
                    self.columns.nulls.append(null)

                bscale = string.replace(words[6],'""','')

                if bscale != '':
                    self.columns.bscales.append(eval(bscale))
                else:
                    self.columns.bscales.append(bscale)

                bzero = string.replace(words[7],'""','')

                if bzero != '':
                    self.columns.bzeros.append(eval(bzero))
                else:
                    self.columns.bzeros.append(bzero)

        # Process the parameter file

        if hfile:
            self._header.fromTxtFile(hfile, replace)

        # Process the data file

        closeDfile = False

        if isinstance(datafile, types.StringType) or \
           isinstance(datafile, types.UnicodeType):
            datafile = __builtin__.open(datafile,'r')
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
                arrayShape = (len(dlines),X_format_size[i])

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

                idx1 = string.find(line[idx:],'"')

                if idx1 >=0:
                    words = words + string.split(line[idx:idx+idx1])
                    idx2 = string.find(line[idx+idx1+1:],'"')
                    words = words + [line[idx1+1:idx1+idx2+1]]
                    idx = idx + idx1 + idx2 + 2
                else:
                    idx2 = string.find(line[idx:],'VLA_Length= ')

                    if idx2 < 0:
                        words = words + string.split(line[idx:])
                        idx = len(line)
                    else:
                        words = words + string.split(line[idx:idx+idx2])
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

    tcreate.__doc__ += tdumpFileFormat.replace("\n", "\n        ")


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
    if hdu.columns.__dict__.has_key('_arrays'):
        del hdu.columns.__dict__['_arrays']

    return hdu


def _get_tbdata(hdu):
    """Get the table data from an input HDU object."""

    from pyfits.file import _File
    from pyfits.hdu.groups import GroupsHDU

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
