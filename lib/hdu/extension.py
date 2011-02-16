from pyfits.card import Card
from pyfits.hdu.base import _ValidHDU, _getClassExtension
from pyfits.util import _is_int


class _ExtensionHDU(_ValidHDU):
    """
    An extension HDU class.

    This class is the base class for the `TableHDU`, `ImageHDU`, and
    `BinTableHDU` classes.
    """

    _extension = ''

    def __setattr__(self, attr, value):
        """
        Set an HDU attribute.
        """

        from pyfits.core import EXTENSION_NAME_CASE_SENSITIVE

        if attr == 'name' and value:
            if not isinstance(value, str):
                raise TypeError, 'bad value type'
            if not EXTENSION_NAME_CASE_SENSITIVE:
                value = value.upper()
            if self._header.has_key('EXTNAME'):
                self._header['EXTNAME'] = value
            else:
                self._header.ascard.append(Card('EXTNAME', value, 'extension name'))

        _ValidHDU.__setattr__(self,attr,value)

    def writeto(self, name, output_verify='exception', clobber=False,
                classExtensions={}, checksum=False):
        from pyfits.hdu.hdulist import HDUList
        from pyfits.hdu.image import PrimaryHDU

        hdulist_cls = _getClassExtension(classExtensions, HDUList)
        hdulist = hdulist_cls([PrimaryHDU(), self])
        hdulist.writeto(name, output_verify, clobber=clobber,
                        checksum=checksum, classExtensions=classExtensions)

    def _verify(self, option='warn'):

        errs = super(_ExtensionHDU, self)._verify(option=option)

        # Verify location and value of mandatory keywords.
        naxis = self._header.get('NAXIS', 0)
        self.req_cards('PCOUNT', naxis + 3, lambda v: (_is_int(v) and v >= 0),
                       0, option, errs)
        self.req_cards('GCOUNT', naxis + 4, lambda v: (_is_int(v) and v == 1),
                       1, option, errs)
        return errs


class _NonstandardExtHDU(_ExtensionHDU):
    """
    A Non-standard Extension HDU class.

    This class is used for an Extension HDU when the ``XTENSION``
    `Card` has a non-standard value.  In this case, pyfits can figure
    out how big the data is but not what it is.  The data for this HDU
    is read from the file as a byte stream that begins at the first
    byte after the header ``END`` card and continues until the
    beginning of the next header or the end of the file.
    """
    def __init__(self, data=None, header=None):
        super(_NonstandardExtHDU, self).__init__(data, header)
        self._file, self._offset, self._datLoc = None, None, None
        self.name = None

    def _summary(self):
        return "%-6s  %-10s  %3d" % (self.name, "NonstandardExtHDU",
                                     len(self._header.ascard))

    def __getattr__(self, attr):
        """
        Get the data attribute.
        """
        if attr == 'data':
            self.__dict__[attr] = None
            self._file.seek(self._datLoc)
            self.data = self._file.read(self.size())
        else:
            return _ValidHDU.__getattr__(self, attr)

        try:
            return self.__dict__[attr]
        except KeyError:
            raise AttributeError(attr)

    def writeto(self, name, output_verify='exception', clobber=False,
                classExtensions={}, checksum=False):
        """
        Write the HDU to a new file.  This is a convenience method to
        provide a user easier output interface if only one HDU needs
        to be written to a file.

        Parameters
        ----------
        name : file path, file object or file-like object
            Output FITS file.  If opened, must be opened for append
            (ab+)).

        output_verify : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.

        clobber : bool
            Overwrite the output file if exists.

        classExtensions : dict
            A dictionary that maps pyfits classes to extensions of
            those classes.  When present in the dictionary, the
            extension class will be constructed in place of the pyfits
            class.

        checksum : bool
            When `True`, adds both ``DATASUM`` and ``CHECKSUM`` cards
            to the header of the HDU when written to the file.
        """

        from pyfits.hdu.hdulist import HDUList

        if classExtensions.has_key(HDUList):
            hdulist = classExtensions[HDUList]([PrimaryHDU(),self])
        else:
            hdulist = HDUList([PrimaryHDU(),self])

        hdulist.writeto(name, output_verify, clobber=clobber,
                        checksum=checksum, classExtensions=classExtensions)
