import numpy as np

from pyfits import rec
from pyfits.column import Column, ColDefs, FITS2NUMPY
from pyfits.fitsrec import FITS_rec, FITS_record
from pyfits.hdu.base import _AllHDU
from pyfits.hdu.image import _ImageBaseHDU, PrimaryHDU
from pyfits.util import lazyproperty, _is_int


class GroupsHDU(PrimaryHDU):
    """
    FITS Random Groups HDU class.
    """

    _width2format = {8: 'B', 16: 'I', 32: 'J', 64: 'K', -32: 'E', -64: 'D'}

    def __init__(self, data=None, header=None, name=None):
        """
        TODO: Write me
        """

        super(GroupsHDU, self).__init__(data=data, header=header)
        # TODO: The assignment of the header's hdutype should probably be
        # something that happens in _AllHDU, or at least further up the
        # hierarchy
        self._header._hdutype = self.__class__

        if self._header['NAXIS'] <= 0:
            self._header['NAXIS'] = 1
        self._header.update('NAXIS1', 0, after='NAXIS')


    @lazyproperty
    def data(self):
        """
        The data of random group FITS file will be like a binary table's data.
        """

        # Nearly the same code as in _TableBaseHDU
        size = self.size()
        if size:
            data = GroupData(self._get_tbdata())
            data._coldefs = self.columns
            data.formats = self.columns.formats
            data.parnames = self.columns._pnames
        else:
            data = None
        return data

    @lazyproperty
    def columns(self):
        cols = []
        pnames = []
        pcount = self._header['PCOUNT']
        format = self._width2format[self._header['BITPIX']]

        for idx in range(self._header['PCOUNT']):
            bscale = self._header.get('PSCAL' + str(idx + 1), 1)
            bzero = self._header.get('PZERO' + str(idx + 1), 0)
            pnames.append(self._header['PTYPE' + str(idx + 1)].lower())
            cols.append(Column(name='c' + str(idx + 1), format=format,
                               bscale=bscale, bzero=bzero))

        data_shape = self._dimShape()[:-1]
        dat_format = str(int(np.array(data_shape).sum())) + format

        bscale = self._header.get('BSCALE', 1)
        bzero = self._header.get('BZERO', 0)
        cols.append(Column(name='data', format=dat_format, bscale=bscale,
                           bzero=bzero))
        coldefs = ColDefs(cols)
        coldefs._shape = self._header['GCOUNT']
        coldefs._dat_format = FITS2NUMPY[format]
        coldefs._pnames = pnames
        return coldefs

    @lazyproperty
    def _theap(self):
        # Only really a lazyproperty for symmetry with _TableBaseHDU
        return 0

    # 0.6.5.5
    def size(self):
        """
        Returns the size (in bytes) of the HDU's data part.
        """

        size = 0
        naxis = self._header.get('NAXIS', 0)

        # for random group image, NAXIS1 should be 0, so we skip NAXIS1.
        if naxis > 1:
            size = 1
            for idx in range(1, naxis):
                size = size * self._header['NAXIS' + str(idx + 1)]
            bitpix = self._header['BITPIX']
            gcount = self._header.get('GCOUNT', 1)
            pcount = self._header.get('PCOUNT', 0)
            size = abs(bitpix) * gcount * (pcount + size) // 8
        return size

    def _get_tbdata(self):
        # get the right shape for the data part of the random group,
        # since binary table does not support ND yet
        self.columns._recformats[-1] = repr(self._dimShape()[:-1]) + \
                                       self.columns._dat_format
        return super(GroupsHDU, self)._get_tbdata()

    def _verify(self, option='warn'):
        errs = super(GroupsHDU, self)._verify(option=option)

        # Verify locations and values of mandatory keywords.
        self.req_cards('NAXIS', 2,
                       lambda v: (_is_int(v) and v >= 1 and v <= 999), 1,
                       option, errs)
        self.req_cards('NAXIS1', 3, lambda v: (_is_int(v) and v == 0), 0,
                       option, errs)

        after = self._header['NAXIS'] + 3
        pos = lambda x: x >= after

        self.req_cards('GCOUNT', pos, _is_int, 1, option, errs)
        self.req_cards('PCOUNT', pos, _is_int, 0, option, errs)
        self.req_cards('GROUPS', pos, lambda v: (v is True), True, option,
                       errs)
        return errs

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        if self._data_loaded and self.data is not None:
            # We have the data to be used.
            # Check the byte order of the data.  If it is little endian we
            # must swap it before calculating the datasum.
            byteorder = \
                 self.data.dtype.fields[self.data.dtype.names[0]][0].str[0]

            if byteorder != '>':
                byteswapped = True
                d = self.data.byteswap(True)
                d.dtype = d.dtype.newbyteorder('>')
            else:
                byteswapped = False
                d = self.data

            cs = self._compute_checksum(np.fromstring(d, dtype='ubyte'),
                                        blocking=blocking)

            # If the data was byteswapped in this method then return it to
            # its original little-endian order.
            if byteswapped:
                d.byteswap(True)
                d.dtype = d.dtype.newbyteorder('<')

            return cs
        else:
            # This is the case where the data has not been read from the file
            # yet.  We can handle that in a generic manner so we do it in the
            # base class.  The other possibility is that there is no data at
            # all.  This can also be handled in a gereric manner.
            return super(GroupsHDU,self)._calculate_datasum(blocking=blocking)


class GroupData(FITS_rec):
    """
    Random groups data object.

    Allows structured access to FITS Group data in a manner analogous
    to tables.
    """

    def __new__(subtype, input=None, bitpix=None, pardata=None, parnames=[],
                bscale=None, bzero=None, parbscales=None, parbzeros=None):
        """
        Parameters
        ----------
        input : array or FITS_rec instance
            input data, either the group data itself (a
            `numpy.ndarray`) or a record array (`FITS_rec`) which will
            contain both group parameter info and the data.  The rest
            of the arguments are used only for the first case.

        bitpix : int
            data type as expressed in FITS ``BITPIX`` value (8, 16, 32,
            64, -32, or -64)

        pardata : sequence of arrays
            parameter data, as a list of (numeric) arrays.

        parnames : sequence of str
            list of parameter names.

        bscale : int
            ``BSCALE`` of the data

        bzero : int
            ``BZERO`` of the data

        parbscales : sequence of int
            list of bscales for the parameters

        parbzeros : sequence of int
            list of bzeros for the parameters
        """

        if not isinstance(input, FITS_rec):
            _formats = ''
            _cols = []
            if pardata is None:
                npars = 0
            else:
                npars = len(pardata)

            if parbscales is None:
                parbscales = [None]*npars
            if parbzeros is None:
                parbzeros = [None]*npars

            if bitpix is None:
                bitpix = _ImageBaseHDU.ImgCode[input.dtype.name]
            fits_fmt = GroupsHDU._width2format[bitpix] # -32 -> 'E'
            _fmt = FITS2NUMPY[fits_fmt] # 'E' -> 'f4'
            _formats = (_fmt+',') * npars
            data_fmt = '%s%s' % (str(input.shape[1:]), _fmt)
            _formats += data_fmt
            gcount = input.shape[0]
            for idx in range(npars):
                _cols.append(Column(name='c'+ str(idx + 1),
                                    format = fits_fmt,
                                    bscale = parbscales[idx],
                                    bzero = parbzeros[idx]))
            _cols.append(Column(name='data',
                                format = fits_fmt,
                                bscale = bscale,
                                bzero = bzero))
            _coldefs = ColDefs(_cols)

            self = FITS_rec.__new__(subtype,
                                    rec.array(None,
                                              formats=_formats,
                                              names=_coldefs.names,
                                              shape=gcount))
            self._coldefs = _coldefs
            self.parnames = [i.lower() for i in parnames]

            for idx in range(npars):
                (_scale, _zero)  = self._get_scale_factors(idx)[3:5]
                if _scale or _zero:
                    self._convert[idx] = pardata[idx]
                else:
                    rec.recarray.field(self,idx)[:] = pardata[idx]
            (_scale, _zero)  = self._get_scale_factors(npars)[3:5]
            if _scale or _zero:
                self._convert[npars] = input
            else:
                rec.recarray.field(self, npars)[:] = input
        else:
             self = FITS_rec.__new__(subtype, input)
        return self

    def __getitem__(self, key):
        return _Group(self, key, self.parnames)

    @property
    def data(self):
        return self.field('data')

    @lazyproperty
    def _unique(self):
        return _unique(self.parnames)

    def par(self, parname):
        """
        Get the group parameter values.
        """

        if _is_int(parname):
            result = self.field(parname)
        else:
            indx = self._unique[parname.lower()]
            if len(indx) == 1:
                result = self.field(indx[0])

            # if more than one group parameter have the same name
            else:
                result = self.field(indx[0]).astype('f8')
                for i in indx[1:]:
                    result += self.field(i)

        return result


class _Group(FITS_record):
    """
    One group of the random group data.
    """

    def __init__(self, input, row, parnames):
        super(_Group, self).__init__(input, row)
        self.parnames = parnames

    def __str__(self):
        """
        Print one row.
        """

        if isinstance(self.row, slice):
            if self.row.step:
                step = self.row.step
            else:
                step = 1

            if self.row.stop > len(self.array):
                stop = len(self.array)
            else:
                stop = self.row.stop

            outlist = []

            for idx in range(self.row.start, stop, step):
                rowlist = []

                for jdx in range(self.array._nfields):
                    rowlist.append(repr(self.array.field(jdx)[idx]))

                outlist.append(' (%s)' % ', '.join(rowlist))

            return '[%s]' % ',\n'.join(outlist)
        else:
            return super(_Group, self).__str__()

    @lazyproperty
    def _unique(self):
        return _unique(self.parnames)

    def par(self, parname):
        """
        Get the group parameter value.
        """

        if _is_int(parname):
            result = self.array[self.row][parname]
        else:
            indx = self._unique[parname.lower()]
            if len(indx) == 1:
                result = self.array[self.row][indx[0]]

            # if more than one group parameter have the same name
            else:
                result = self.array[self.row][indx[0]].astype('f8')
                for i in indx[1:]:
                    result += self.array[self.row][i]

        return result


    def setpar(self, parname, value):
        """
        Set the group parameter value.
        """

        if _is_int(parname):
            self.array[self.row][parname] = value
        else:
            indx = self._unique[parname.lower()]
            if len(indx) == 1:
                self.array[self.row][indx[0]] = value

            # if more than one group parameter have the same name, the
            # value must be a list (or tuple) containing arrays
            else:
                if isinstance(value, (list, tuple)) and \
                   len(indx) == len(value):
                    for i in range(len(indx)):
                        self.array[self.row][indx[i]] = value[i]
                else:
                    raise ValueError('Parameter value must be a sequence '
                                     'with %d arrays/numbers.' % len(indx))

def _unique(names):
    unique = {}
    for idx, name in enumerate(names):
        if name in unique:
            unique[name].append(idx)
        else:
            unique[name] = [idx]
    return unique

