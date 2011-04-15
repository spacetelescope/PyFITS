import sys
import numpy as np

from pyfits.card import Card, CardList
from pyfits.column import DELAYED
from pyfits.hdu.base import _ValidHDU
from pyfits.hdu.extension import _ExtensionHDU
from pyfits.hdu.base import _ValidHDU
from pyfits.header import Header
from pyfits.util import Extendable, _is_pseudo_unsigned, _unsigned_zero, \
                        _is_int, _pad_length, _normalize_slice, lazyproperty

class _ImageBaseHDU(_ValidHDU):
    """FITS image HDU base class.

    Attributes
    ----------
    header
        image header

    data
        image data

    _file
        file associated with array

    _datLoc
        starting byte location of data block in file
    """

    # mappings between FITS and numpy typecodes
#    NumCode = {8:'int8', 16:'int16', 32:'int32', 64:'int64', -32:'float32', -64:'float64'}
#    ImgCode = {'<i2':8, '<i4':16, '<i8':32, '<i16':64, '<f8':-32, '<f16':-64}
    NumCode = {8:'uint8', 16:'int16', 32:'int32', 64:'int64', -32:'float32', -64:'float64'}
    ImgCode = {'uint8':8, 'int16':16, 'uint16':16, 'int32':32,
               'uint32':32, 'int64':64, 'uint64':64,
               'float32':-32, 'float64':-64}

    def __init__(self, data=None, header=None, do_not_scale_image_data=False,
                 uint=False):
        from pyfits.hdu.extension import _ExtensionHDU
        from pyfits.hdu.groups import GroupsHDU

        super(_ImageBaseHDU, self).__init__(data=data, header=header)

        if header is not None:
            if not isinstance(header, Header):
                raise ValueError('header must be a Header object')


        if data is DELAYED:

            # this should never happen
            if header is None:
                raise ValueError('No header to setup HDU.')

            # if the file is read the first time, no need to copy, and keep it unchanged
            else:
                self._header = header
        else:
            # TODO: Some of this card manipulation should go into the
            # PrimaryHDU and GroupsHDU subclasses
            # construct a list of cards of minimal header
            if isinstance(self, _ExtensionHDU):
                c0 = Card('XTENSION', 'IMAGE', 'Image extension')
            else:
                c0 = Card('SIMPLE', True, 'conforms to FITS standard')

            _list = CardList([
                c0,
                Card('BITPIX',    8, 'array data type'),
                Card('NAXIS',     0, 'number of array dimensions'),
                ])
            if isinstance(self, GroupsHDU):
                _list.append(Card('GROUPS', True, 'has groups'))

            if isinstance(self, (_ExtensionHDU, GroupsHDU)):
                _list.append(Card('PCOUNT',    0, 'number of parameters'))
                _list.append(Card('GCOUNT',    1, 'number of groups'))

            if header is not None:
                hcopy = header.copy(strip=True)
                _list.extend(hcopy.ascardlist())

            self._header = Header(_list)

        self._do_not_scale_image_data = do_not_scale_image_data
        self._uint = uint

        if do_not_scale_image_data:
            self._bzero = 0
            self._bscale = 1
        else:
            self._bzero = self._header.get('BZERO', 0)
            self._bscale = self._header.get('BSCALE', 1)

        if (data is DELAYED): return

        self.data = data

        # update the header
        self.update_header()
        self._bitpix = self._header['BITPIX']

        if not do_not_scale_image_data:
            # delete the keywords BSCALE and BZERO
            del self._header['BSCALE']
            del self._header['BZERO']

    @classmethod
    def match_header(cls, header):
        """
        _ImageBaseHDU is sort of an abstract class for HDUs containing image
        data (as opposed to table data) and should never be used directly.
        """

        raise NotImplementedError

    @property
    def section(self):
        return Section(self)

    @lazyproperty
    def data(self):
        self._data_loaded = True

        if self._header['NAXIS'] < 1:
            return

        bitpix = self._header['BITPIX']
        dims = self._dimShape()

        code = _ImageBaseHDU.NumCode[bitpix]

        raw_data = self._file.readarray(offset=self._datLoc, dtype=code,
                                        shape=dims)
        raw_data.dtype = raw_data.dtype.newbyteorder('>')

        if (self._bzero == 0 and self._bscale == 1):
            return raw_data

        data = None
        # Handle "pseudo-unsigned" integers, if the user
        # requested it.  In this case, we don't need to
        # handle BLANK to convert it to NAN, since we
        # can't do NaNs with integers, anyway, i.e. the
        # user is responsible for managing blanks.
        if self._uint and self._bscale == 1:
            for bits, dtype in ((16, np.uint16),
                                (32, np.uint32),
                                (64, np.uint64)):
                if bitpix == bits and self._bzero == 1 << (bits - 1):
                    # Convert the input raw data into an unsigned
                    # integer array and then scale the data
                    # adjusting for the value of BZERO.  Note
                    # that we subtract the value of BZERO instead
                    # of adding because of the way numpy converts
                    # the raw signed array into an unsigned array.
                    data = np.array(raw_data, dtype=dtype)
                    data -= (1 << (bits - 1))
                    break

        if data is None:
            # In these cases, we end up with
            # floating-point arrays and have to apply
            # bscale and bzero. We may have to handle
            # BLANK and convert to NaN in the resulting
            # floating-point arrays.
            if 'BLANK' in self._header:
                nullDvals = np.array(self._header['BLANK'],
                                     dtype='int64')
                blanks = (raw_data == nullDvals)

            if bitpix > 16:  # scale integers to Float64
                data = np.array(raw_data, dtype=np.float64)
            elif bitpix > 0:  # scale integers to Float32
                data = np.array(raw_data, dtype=np.float32)
            else:  # floating point cases
                if self._file.memmap:
                    data = raw_data.copy()
                # if not memmap, use the space already in memory
                else:
                    data = raw_data

            if self._bscale != 1:
                np.multiply(data, self._bscale, data)
            if self._bzero != 0:
                data += self._bzero

            if self._header.has_key('BLANK'):
                data = np.where(blanks, np.nan, data)

        if not self._do_not_scale_image_data:
           # delete the keywords BSCALE and BZERO after scaling
           del self._header['BSCALE']
           del self._header['BZERO']

        self._header['BITPIX'] = _ImageBaseHDU.ImgCode[data.dtype.name]

        return data

    def update_header(self):
        """
        Update the header keywords to agree with the data.
        """

        from pyfits.hdu.groups import GroupData

        old_naxis = self._header.get('NAXIS', 0)

        if isinstance(self.data, GroupData):
            self._header['BITPIX'] = _ImageBaseHDU.ImgCode[
                      self.data.dtype.fields[self.data.dtype.names[0]][0].name]
            axes = list(self.data.data.shape)[1:]
            axes.reverse()
            axes = [0] + axes

        elif isinstance(self.data, np.ndarray):
            self._header['BITPIX'] = _ImageBaseHDU.ImgCode[self.data.dtype.name]
            axes = list(self.data.shape)
            axes.reverse()

        elif self.data is None:
            axes = []
        else:
            raise ValueError('incorrect array type')

        self._header['NAXIS'] = len(axes)

        # add NAXISi if it does not exist
        for idx, axis in enumerate(axes):
            try:
                self._header['NAXIS'+ str(idx + 1)] = axis
            except KeyError:
                if (idx == 0):
                    after = 'naxis'
                else :
                    after = 'naxis' + str(idx)
                self._header.update('naxis' + str(idx + 1), axis, after=after)

        # delete extra NAXISi's
        for idx in range(len(axes)+1, old_naxis+1):
            try:
                del self._header.ascard['NAXIS' + str(idx)]
            except KeyError:
                pass

        if isinstance(self.data, GroupData):
            self._header.update('GROUPS', True, after='NAXIS' + str(len(axes)))
            self._header.update('PCOUNT', len(self.data.parnames),
                                after='GROUPS')
            self._header.update('GCOUNT', len(self.data), after='PCOUNT')
            npars = len(self.data.parnames)
            (_scale, _zero)  = self.data._get_scale_factors(npars)[3:5]
            if _scale:
                self._header.update('BSCALE',
                                    self.data._coldefs.bscales[npars])
            if _zero:
                self._header.update('BZERO', self.data._coldefs.bzeros[npars])
            for idx in range(npars):
                self._header.update('PTYPE' + str(idx + 1),
                                    self.data.parnames[idx])
                (_scale, _zero)  = self.data._get_scale_factors(idx)[3:5]
                if _scale:
                    self._header.update('PSCAL' + str(idx + 1),
                                        self.data._coldefs.bscales[idx])
                if _zero:
                    self._header.update('PZERO' + str(idx + 1),
                                        self.data._coldefs.bzeros[idx])

    def scale(self, type=None, option="old", bscale=1, bzero=0):
        """
        Scale image data by using ``BSCALE``/``BZERO``.

        Call to this method will scale `data` and update the keywords
        of ``BSCALE`` and ``BZERO`` in `_header`.  This method should
        only be used right before writing to the output file, as the
        data will be scaled and is therefore not very usable after the
        call.

        Parameters
        ----------
        type : str, optional
            destination data type, use a string representing a numpy
            dtype name, (e.g. ``'uint8'``, ``'int16'``, ``'float32'``
            etc.).  If is `None`, use the current data type.

        option : str
            How to scale the data: if ``"old"``, use the original
            ``BSCALE`` and ``BZERO`` values when the data was
            read/created. If ``"minmax"``, use the minimum and maximum
            of the data to scale.  The option will be overwritten by
            any user specified `bscale`/`bzero` values.

        bscale, bzero : int, optional
            User-specified ``BSCALE`` and ``BZERO`` values.
        """

        if self.data is None:
            return

        # Determine the destination (numpy) data type
        if type is None:
            type = self.NumCode[self._bitpix]
        _type = getattr(np, type)

        # Determine how to scale the data
        # bscale and bzero takes priority
        if (bscale != 1 or bzero !=0):
            _scale = bscale
            _zero = bzero
        else:
            if option == 'old':
                _scale = self._bscale
                _zero = self._bzero
            elif option == 'minmax':
                if isinstance(_type, np.floating):
                    _scale = 1
                    _zero = 0
                else:

                    # flat the shape temporarily to save memory
                    dims = self.data.shape
                    self.data.shape = self.data.size
                    min = np.minimum.reduce(self.data)
                    max = np.maximum.reduce(self.data)
                    self.data.shape = dims

                    if _type == np.uint8:  # uint8 case
                        _zero = min
                        _scale = (max - min) / (2.**8 - 1)
                    else:
                        _zero = (max + min) / 2.

                        # throw away -2^N
                        _scale = (max - min) / (2.**(8*_type.bytes) - 2)

        # Do the scaling
        if _zero != 0:
            self.data += -_zero # 0.9.6.3 to avoid out of range error for BZERO = +32768
            self._header.update('BZERO', _zero)
        else:
            del self._header['BZERO']

        if _scale != 1:
            self.data /= _scale
            self._header.update('BSCALE', _scale)
        else:
            del self._header['BSCALE']

        if self.data.dtype.type != _type:
            self.data = np.array(np.around(self.data), dtype=_type) #0.7.7.1
        #
        # Update the BITPIX Card to match the data
        #
        self._header['BITPIX'] = _ImageBaseHDU.ImgCode[self.data.dtype.name]

    def _writedata(self, fileobj):
        offset = 0
        size = 0

        if not fileobj.simulateonly:
            fileobj.flush()
            try:
                offset = fileobj.tell()
            except (AttributeError, IOError):
                # TODO: as long as we're assuming fileobj is a FITSFile,
                # AttributeError won't happen here
                offset = 0

        if self.data is not None:
            # Based on the system type, determine the byteorders that
            # would need to be swapped to get to big-endian output
            if sys.byteorder == 'little':
                swap_types = ('<', '=')
            else:
                swap_types = ('<',)
            # deal with unsigned integer 16, 32 and 64 data
            if _is_pseudo_unsigned(self.data.dtype):
                # Convert the unsigned array to signed
                output = np.array(
                    self.data - _unsigned_zero(self.data.dtype),
                    dtype='>i%d' % self.data.dtype.itemsize)
                should_swap = False
            else:
                output = self.data
                byteorder = output.dtype.str[0]
                should_swap = (byteorder in swap_types)

            if not fileobj.simulateonly:
                if should_swap:
                    output.byteswap(True)
                    try:
                        fileobj.write(output)
                    finally:
                        output.byteswap(True)
                else:
                    fileobj.write(output)
        # flush, to make sure the content is written
        if not fileobj.simulateonly:
            fileobj.flush()

        # return both the location and the size of the data area
        return offset, size + _pad_length(size)

    def _writeto(self, fileobj, checksum=False):
        self.update_header()
        super(_ImageBaseHDU, self)._writeto(fileobj, checksum)

    def _dimShape(self):
        """
        Returns a tuple of image dimensions, reverse the order of ``NAXIS``.
        """
        naxis = self._header['NAXIS']
        axes = naxis*[0]
        for idx in range(naxis):
            axes[idx] = self._header['NAXIS' + str(idx + 1)]
        axes.reverse()
#        print "axes in _dimShape line 2081:",axes
        return tuple(axes)

    def _summary(self):
        """
        Summarize the HDU: name, dimensions, and formats.
        """
        from pyfits.hdu.groups import GroupsHDU

        class_name  = str(self.__class__)
        type  = class_name[class_name.rfind('.')+1:-2]

        if type.find('_') != -1:
            type = type[type.find('_')+1:]

        # if data is touched, use data info.
        if self._data_loaded:
            if self.data is None:
                _shape, _format = (), ''
            else:

                # the shape will be in the order of NAXIS's which is the
                # reverse of the numarray shape
                if isinstance(self, GroupsHDU):
                    _shape = list(self.data.data.shape)[1:]
                    _format = \
                       self.data.dtype.fields[self.data.dtype.names[0]][0].name
                else:
                    _shape = list(self.data.shape)
                    _format = self.data.dtype.name
                _shape.reverse()
                _shape = tuple(_shape)
                _format = _format[_format.rfind('.')+1:]

        # if data is not touched yet, use header info.
        else:
            _shape = ()
            for idx in range(self._header['NAXIS']):
                if isinstance(self, GroupsHDU) and idx == 0:
                    continue
                _shape += (self._header['NAXIS' + str(idx + 1)],)
            _format = self.NumCode[self._header['BITPIX']]

        if isinstance(self, GroupsHDU):
            _gcount = '   %d Groups  %d Parameters' \
                      % (self._header['GCOUNT'], self._header['PCOUNT'])
        else:
            _gcount = ''
        return "%-10s  %-11s  %5d  %-12s  %s%s" \
               % (self.name, type, len(self._header.ascard), _shape, _format,
                  _gcount)

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        if self.__dict__.has_key('data') and self.data != None:
            # We have the data to be used.
            d = self.data

            # First handle the special case where the data is unsigned integer
            # 16, 32 or 64
            if _is_pseudo_unsigned(self.data.dtype):
                d = np.array(self.data - _unsigned_zero(self.data.dtype),
                             dtype='i%d' % self.data.dtype.itemsize)

            # Check the byte order of the data.  If it is little endian we
            # must swap it before calculating the datasum.
            if d.dtype.str[0] != '>':
                byteswapped = True
                d = d.byteswap(True)
                d.dtype = d.dtype.newbyteorder('>')
            else:
                byteswapped = False

            cs = self._compute_checksum(np.fromstring(d, dtype='ubyte'),
                                        blocking=blocking)

            # If the data was byteswapped in this method then return it to
            # its original little-endian order.
            if byteswapped and not _is_pseudo_unsigned(self.data.dtype):
                d.byteswap(True)
                d.dtype = d.dtype.newbyteorder('<')

            return cs
        else:
            # This is the case where the data has not been read from the file
            # yet.  We can handle that in a generic manner so we do it in the
            # base class.  The other possibility is that there is no data at
            # all.  This can also be handled in a gereric manner.
            return super(_ImageBaseHDU,self)._calculate_datasum(
                    blocking=blocking)


class Section(object):
    """
    Image section.

    TODO: elaborate
    """

    def __init__(self, hdu):
        self.hdu = hdu

    def __getitem__(self, key):
        dims = []
        if not isinstance(key, tuple):
            key = (key,)
        naxis = self.hdu.header['NAXIS']
        if naxis < len(key):
            raise IndexError('too many indices')
        elif naxis > len(key):
            key = key + (slice(None),) * (naxis-len(key))

        offset = 0

        # Declare outside of loop scope for use below--don't abuse for loop
        # scope leak defect
        idx = 0
        for idx in range(naxis):
            _naxis = self.hdu.header['NAXIS'+ str(naxis - idx)]
            indx = _iswholeline(key[idx], _naxis)
            offset = offset * _naxis + indx.offset

            # all elements after the first WholeLine must be WholeLine or
            # OnePointAxis
            if isinstance(indx, (_WholeLine, _LineSlice)):
                dims.append(indx.npts)
                break
            elif isinstance(indx, _SteppedSlice):
                raise IndexError('Stepped Slice not supported')

        contiguousSubsection = True

        for jdx in range(idx + 1, naxis):
            _naxis = self.hdu.header['NAXIS' + str(naxis - jdx)]
            indx = _iswholeline(key[jdx], _naxis)
            dims.append(indx.npts)
            if not isinstance(indx, _WholeLine):
                contiguousSubsection = False

            # the offset needs to multiply the length of all remaining axes
            else:
                offset *= _naxis

        if contiguousSubsection:
            if not dims:
                dims = [1]

            # Now, get the data (does not include bscale/bzero for now XXX)
            _bitpix = self.hdu.header['BITPIX']
            code = _ImageBaseHDU.NumCode[_bitpix]
            offset = self.hdu._datLoc + (offset * abs(_bitpix) // 8)
            raw_data = self.hdu._file.readarray(offset=offset, dtype=code,
                                                shape=dims)
            raw_data.dtype = raw_data.dtype.newbyteorder('>')
            return raw_data
        else:
            out = self._getdata(key)
            return out

    def _getdata(self, keys):
        out = []
        naxis = self.hdu.header['NAXIS']

        # Determine the number of slices in the set of input keys.
        # If there is only one slice then the result is a one dimensional
        # array, otherwise the result will be a multidimensional array.
        numSlices = 0
        for idx, key in enumerate(keys):
            if isinstance(key, slice):
                numSlices = numSlices + 1

        for idx, key in enumerate(keys):
            if isinstance(key, slice):
                # OK, this element is a slice so see if we can get the data for
                # each element of the slice.
                _naxis = self.hdu.header['NAXIS' + str(naxis - idx)]
                ns = _normalize_slice(key, _naxis)

                for k in range(ns.start, ns.stop):
                    key1 = list(keys)
                    key1[idx] = k
                    key1 = tuple(key1)

                    if numSlices > 1:
                        # This is not the only slice in the list of keys so
                        # we simply get the data for this section and append
                        # it to the list that is output.  The out variable will
                        # be a list of arrays.  When we are done we will pack
                        # the list into a single multidimensional array.
                        out.append(self[key1])
                    else:
                        # This is the only slice in the list of keys so if this
                        # is the first element of the slice just set the output
                        # to the array that is the data for the first slice.
                        # If this is not the first element of the slice then
                        # append the output for this slice element to the array
                        # that is to be output.  The out variable is a single
                        # dimensional array.
                        if k == ns.start:
                            out = self[key1]
                        else:
                            out = np.append(out,self[key1])

                # We have the data so break out of the loop.
                break

        if isinstance(out, list):
            out = np.array(out)

        return out


class PrimaryHDU(_ImageBaseHDU):
    """
    FITS primary HDU class.
    """

    __metaclass__ = Extendable

    def __init__(self, data=None, header=None, do_not_scale_image_data=False,
                 uint=False):
        """
        Construct a primary HDU.

        Parameters
        ----------
        data : array or DELAYED, optional
            The data in the HDU.

        header : Header instance, optional
            The header to be used (as a template).  If `header` is
            `None`, a minimal header will be provided.

        do_not_scale_image_data : bool, optional
            If `True`, image data is not scaled using BSCALE/BZERO values
            when read.

        uint : bool, optional
            Interpret signed integer data where ``BZERO`` is the
            central value and ``BSCALE == 1`` as unsigned integer
            data.  For example, `int16` data with ``BZERO = 32768``
            and ``BSCALE = 1`` would be treated as `uint16` data.
        """

        super(PrimaryHDU, self).__init__(
            data=data, header=header,
            do_not_scale_image_data=do_not_scale_image_data, uint=uint)
        self.name = 'PRIMARY'
        self._extver = 1

        # insert the keywords EXTEND
        if header is None:
            dim = repr(self._header['NAXIS'])
            if dim == '0':
                dim = ''
            self._header.update('EXTEND', True, after='NAXIS' + dim)

    @classmethod
    def match_header(cls, header):
        card = header.ascard[0]
        return card.key == 'SIMPLE' and \
               ('GROUPS' not in header or header['GROUPS'] != True) and \
               card.value == True


class ImageHDU(_ImageBaseHDU, _ExtensionHDU):
    """
    FITS image extension HDU class.
    """

    __metaclass__ = Extendable

    _extension = 'IMAGE'

    def __init__(self, data=None, header=None, name=None,
                 do_not_scale_image_data=False, uint=False):
        """
        Construct an image HDU.

        Parameters
        ----------
        data : array
            The data in the HDU.

        header : Header instance
            The header to be used (as a template).  If `header` is
            `None`, a minimal header will be provided.

        name : str, optional
            The name of the HDU, will be the value of the keyword
            ``EXTNAME``.

        do_not_scale_image_data : bool, optional
            If `True`, image data is not scaled using BSCALE/BZERO values
            when read.

        uint : bool, optional
            Interpret signed integer data where ``BZERO`` is the
            central value and ``BSCALE == 1`` as unsigned integer
            data.  For example, `int16` data with ``BZERO = 32768``
            and ``BSCALE = 1`` would be treated as `uint16` data.
        """

        super(ImageHDU, self).__init__(
            data=data, header=header,
            do_not_scale_image_data=do_not_scale_image_data, uint=uint)

        # set extension name; normally this would be done by
        # _ExtensionHDU.__init__, but we can't send the name argument to
        # super().__init__ since it's not supported by _ImageBaseHDU.__init__;
        # the perils of multiple inheritance...
        if not name and 'EXTNAME' in self._header:
            name = self._header['EXTNAME']
        else:
            name = ''
        self.name = name

    @classmethod
    def match_header(cls, header):
        card = header.ascard[0]
        xtension = card.value.rstrip()
        return card.key == 'XTENSION' and xtension == cls._extension

    def _verify(self, option='warn'):
        """
        ImageHDU verify method.
        """

        errs = super(ImageHDU, self)._verify(option=option)
        naxis = self._header.get('NAXIS', 0)
        # PCOUNT must == 0, GCOUNT must == 1; the former is verifed in
        # _ExtensionHDU._verify, however _ExtensionHDU._verify allows PCOUNT
        # to be >= 0, so we need to check it here
        self.req_cards('PCOUNT', naxis + 3, lambda v: (_is_int(v) and v == 0),
                       0, option, errs)
        return errs

def _iswholeline(indx, naxis):
    if isinstance(indx, (int, long,np.integer)):
        if indx >= 0 and indx < naxis:
            if naxis > 1:
                return _SinglePoint(1, indx)
            elif naxis == 1:
                return _OnePointAxis(1, 0)
        else:
            raise IndexError('Index %s out of range.' % indx)
    elif isinstance(indx, slice):
        indx = _normalize_slice(indx, naxis)
        if (indx.start == 0) and (indx.stop == naxis) and (indx.step == 1):
            return _WholeLine(naxis, 0)
        else:
            if indx.step == 1:
                return _LineSlice(indx.stop-indx.start, indx.start)
            else:
                return _SteppedSlice((indx.stop-indx.start) // indx.step,
                                     indx.start)
    else:
        raise IndexError('Illegal index %s' % indx)


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




