import re

import numpy as np
from numpy import char as chararray

from pyfits import rec
from pyfits.card import Card, CardList
from pyfits.column import Column, ColDefs
from pyfits.fitsrec import FITS_rec
from pyfits.hdu.base import _AllHDU, _isInt
from pyfits.hdu.extension import _ExtensionHDU


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

        from pyfits.core import DELAYED, _convert_format
        from pyfits.header import Header

        if header is not None:
            if not isinstance(header, Header):
                raise ValueError, "header must be a Header object"

        if data is DELAYED:

            # this should never happen
            if header is None:
                raise ValueError, "No header to setup HDU."

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

                if self.data._coldefs == None:
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

                    try:
                        tbtype = 'BinTableHDU'

                        if self._xtn == 'TABLE':
                            tbtype = 'TableHDU'
                    except AttributeError:
                        pass

                    self.data._coldefs = ColDefs(columns,tbtype=tbtype)

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

    def __getattr__(self, attr):
        """
        Get the `data` or `columns` attribute.
        """

        from pyfits.core import _get_tbdata

        if attr == 'data':
            size = self.size()
            if size:
                self._file.seek(self._datLoc)
                data = _get_tbdata(self)
                data._coldefs = self.columns
                data.formats = self.columns.formats
#                print "Got data?"
            else:
                data = None
            self.__dict__[attr] = data

        elif attr == 'columns':
            class_name = str(self.__class__)
            class_name = class_name[class_name.rfind('.')+1:-2]
            self.__dict__[attr] = ColDefs(self, tbtype=class_name)

        elif attr == '_theap':
            self.__dict__[attr] = self._header.get('THEAP', self._header['NAXIS1']*self._header['NAXIS2'])
        elif attr == '_pcount':
            self.__dict__[attr] = self._header.get('PCOUNT', 0)
        else:
            return _AllHDU.__getattr__(self,attr)

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)


    def _summary(self):
        """
        Summarize the HDU: name, dimensions, and formats.
        """

        class_name  = str(self.__class__)
        type  = class_name[class_name.rfind('.')+1:-2]

        # if data is touched, use data info.
        if 'data' in dir(self):
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
            _format = '['
            for j in range(_ncols):
                _format += self._header['TFORM'+`j+1`] + ', '
            _format = _format[:-2] + ']'
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

        from pyfits.core import Card, _tdef_re, _commonNames, _keyNames, \
                                _FormatX, _FormatP, _convert_format

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
            _key = _tdef_re.match(_card.key)
            try: keyword = _key.group('label')
            except: continue                # skip if there is no match
            if (keyword in _keyNames):
                _list.append(i)
        for i in _list:
            del self._header.ascard[i]
        del _list

        # populate the new table definition keywords
        for i in range(len(_cols)):
            for cname in _commonNames:
                val = getattr(_cols, cname+'s')[i]
                if val != '':
                    keyword = _keyNames[_commonNames.index(cname)]+`i+1`
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
        self._xtn = 'TABLE'
        _TableBaseHDU.__init__(self, data=data, header=header, name=name)
        if self._header[0].rstrip() != self._xtn:
            self._header[0] = self._xtn
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

        from pyfits.core import _padLength

        if self.__dict__.has_key('data') and self.data != None:
            # We have the data to be used.
            # We need to pad the data to a block length before calculating
            # the datasum.

            if self.size() > 0:
                d = np.append(np.fromstring(self.data, dtype='ubyte'),
                              np.fromstring(_padLength(self.size())*' ',
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

        self._xtn = 'BINTABLE'
        _TableBaseHDU.__init__(self, data=data, header=header, name=name)
        hdr = self._header
        if hdr[0] != self._xtn:
            hdr[0] = self._xtn
            hdr.ascard[0].comment = 'binary table extension'

        self._header._hdutype = BinTableHDU

    def _calculate_datasum_from_data(self, data, blocking):
        """
        Calculate the value for the ``DATASUM`` card given the input data
        """

        from pyfits.core import _VLF, _FormatP

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
                    VLA_format =  _fits2rec[option[0]][0]

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
                VLA_formats = VLA_formats + [_fits2rec[option[0]]]
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
