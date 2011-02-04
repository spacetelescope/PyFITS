import numpy as np

from pyfits.card import Card, CardList
from pyfits.hdu.base import _AllHDU, _ValidHDU, _isInt
from pyfits.hdu.extension import _ExtensionHDU

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

    def __init__(self, data=None, header=None, do_not_scale_image_data=False):
        from pyfits.core import DELAYED, Header
        from pyfits.hdu.groups import GroupsHDU

        self._file, self._datLoc = None, None

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
                hcopy = header.copy()
                hcopy._strip()
                _list.extend(hcopy.ascardlist())

            self._header = Header(_list)

        self._do_not_scale_image_data = do_not_scale_image_data

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
            raise ValueError, "incorrect array type"

        self._header['NAXIS'] = len(axes)

        # add NAXISi if it does not exist
        for j in range(len(axes)):
            try:
                self._header['NAXIS'+`j+1`] = axes[j]
            except KeyError:
                if (j == 0):
                    _after = 'naxis'
                else :
                    _after = 'naxis'+`j`
                self._header.update('naxis'+`j+1`, axes[j], after = _after)

        # delete extra NAXISi's
        for j in range(len(axes)+1, old_naxis+1):
            try:
                del self._header.ascard['NAXIS'+`j`]
            except KeyError:
                pass

        if isinstance(self.data, GroupData):
            self._header.update('GROUPS', True, after='NAXIS'+`len(axes)`)
            self._header.update('PCOUNT', len(self.data.parnames), after='GROUPS')
            self._header.update('GCOUNT', len(self.data), after='PCOUNT')
            npars = len(self.data.parnames)
            (_scale, _zero)  = self.data._get_scale_factors(npars)[3:5]
            if _scale:
                self._header.update('BSCALE', self.data._coldefs.bscales[npars])
            if _zero:
                self._header.update('BZERO', self.data._coldefs.bzeros[npars])
            for i in range(npars):
                self._header.update('PTYPE'+`i+1`, self.data.parnames[i])
                (_scale, _zero)  = self.data._get_scale_factors(i)[3:5]
                if _scale:
                    self._header.update('PSCAL'+`i+1`, self.data._coldefs.bscales[i])
                if _zero:
                    self._header.update('PZERO'+`i+1`, self.data._coldefs.bzeros[i])

    def __getattr__(self, attr):
        """
        Get the data attribute.
        """

        from pyfits.core import Section, _fromfile
        from pyfits.hdu.groups import GroupsHDU

        if attr == 'section':
            return Section(self)
        elif attr == 'data':
            self.__dict__[attr] = None
            if self._header['NAXIS'] > 0:
                _bitpix = self._header['BITPIX']
                self._file.seek(self._datLoc)
                if isinstance(self, GroupsHDU):
                    dims = self.size()*8//abs(_bitpix)
                else:
                    dims = self._dimShape()

                code = _ImageBaseHDU.NumCode[self._header['BITPIX']]

                if self._ffile.memmap:
                    self._ffile.code = code
                    self._ffile.dims = dims
                    self._ffile.offset = self._datLoc
                    raw_data = self._ffile._mm
                else:

                    nelements = 1
                    for x in range(len(dims)):
                        nelements = nelements * dims[x]

                    raw_data = _fromfile(self._file, dtype=code,
                                         count=nelements,sep="")

                    raw_data.shape=dims

#                print "raw_data.shape: ",raw_data.shape
#                raw_data._byteorder = 'big'
                raw_data.dtype = raw_data.dtype.newbyteorder('>')

                if (self._bzero != 0 or self._bscale != 1):
                    data = None
                    # Handle "pseudo-unsigned" integers, if the user
                    # requested it.  In this case, we don't need to
                    # handle BLANK to convert it to NAN, since we
                    # can't do NaNs with integers, anyway, i.e. the
                    # user is responsible for managing blanks.
                    if self._ffile.uint and self._bscale == 1:
                        for bits, dtype in ((16, np.uint16),
                                            (32, np.uint32),
                                            (64, np.uint64)):
                            if _bitpix == bits and self._bzero == 1 << (bits - 1):
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
                        if self._header.has_key('BLANK'):
                            nullDvals = np.array(self._header['BLANK'],
                                                 dtype='int64')
                            blanks = (raw_data == nullDvals)

                        if _bitpix > 16:  # scale integers to Float64
                            data = np.array(raw_data, dtype=np.float64)
                        elif _bitpix > 0:  # scale integers to Float32
                            data = np.array(raw_data, dtype=np.float32)
                        else:  # floating point cases
                            if self._ffile.memmap:
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

                    self.data = data

                    if not self._do_not_scale_image_data:
                       # delete the keywords BSCALE and BZERO after scaling
                       del self._header['BSCALE']
                       del self._header['BZERO']

                    self._header['BITPIX'] = _ImageBaseHDU.ImgCode[self.data.dtype.name]
                else:
                    self.data = raw_data

        else:
            return _AllHDU.__getattr__(self, attr)

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def _dimShape(self):
        """
        Returns a tuple of image dimensions, reverse the order of ``NAXIS``.
        """
        naxis = self._header['NAXIS']
        axes = naxis*[0]
        for j in range(naxis):
            axes[j] = self._header['NAXIS'+`j+1`]
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
        if 'data' in dir(self):
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
            for j in range(self._header['NAXIS']):
                if isinstance(self, GroupsHDU) and j == 0:
                    continue
                _shape += (self._header['NAXIS'+`j+1`],)
            _format = self.NumCode[self._header['BITPIX']]

        if isinstance(self, GroupsHDU):
            _gcount = '   %d Groups  %d Parameters' % (self._header['GCOUNT'], self._header['PCOUNT'])
        else:
            _gcount = ''
        return "%-10s  %-11s  %5d  %-12s  %s%s" % \
            (self.name, type, len(self._header.ascard), _shape, _format, _gcount)

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

    def _calculate_datasum(self, blocking):
        """
        Calculate the value for the ``DATASUM`` card in the HDU.
        """

        from pyfits.core import _is_pseudo_unsigned, _unsigned_zero

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

            cs = self._compute_checksum(np.fromstring(d, dtype='ubyte'), blocking=blocking)

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
            return super(_ImageBaseHDU,self)._calculate_datasum(blocking=blocking)


class ImageHDU(_ExtensionHDU, _ImageBaseHDU):
    """
    FITS image extension HDU class.
    """

    def __init__(self, data=None, header=None, name=None,
                 do_not_scale_image_data=False):
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
        """

        # no need to run _ExtensionHDU.__init__ since it is not doing anything.
        _ImageBaseHDU.__init__(self, data=data, header=header,
                               do_not_scale_image_data=do_not_scale_image_data)
        self._xtn = 'IMAGE'

        self._header._hdutype = ImageHDU

        # insert the require keywords PCOUNT and GCOUNT
        dim = `self._header['NAXIS']`
        if dim == '0':
            dim = ''


        #  set extension name
        if (name is None) and self._header.has_key('EXTNAME'):
            name = self._header['EXTNAME']
        self.name = name

    def _verify(self, option='warn'):
        """
        ImageHDU verify method.
        """

        _err = _ValidHDU._verify(self, option=option)
        naxis = self.header.get('NAXIS', 0)
        self.req_cards('PCOUNT', '== '+`naxis+3`, _isInt+" and val == 0",
                       0, option, _err)
        self.req_cards('GCOUNT', '== '+`naxis+4`, _isInt+" and val == 1",
                       1, option, _err)
        return _err


class PrimaryHDU(_ImageBaseHDU):
    """
    FITS primary HDU class.
    """
    def __init__(self, data=None, header=None, do_not_scale_image_data=False):
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
        """

        _ImageBaseHDU.__init__(self, data=data, header=header,
                               do_not_scale_image_data=do_not_scale_image_data)
        self.name = 'PRIMARY'

        # insert the keywords EXTEND
        if header is None:
            dim = `self._header['NAXIS']`
            if dim == '0':
                dim = ''
            self._header.update('EXTEND', True, after='NAXIS'+dim)
