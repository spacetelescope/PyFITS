from __future__ import division, with_statement

import platform

import numpy as np

import pyfits as fits
from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import ignore_warnings


class TestUintFunctions(PyfitsTestCase):
    utypes = ('u2', 'u4', 'u8')
    utype_map = {'u2' :np.uint16, 'u4': np.uint32, 'u8': np.uint64}
    itype_map = {'u2': np.int16, 'u4': np.int32, 'u8': np.int64}
    format_map = {'u2': 'I', 'u4': 'J', 'u8': 'K'}

    def test_uint(self):
        # Test of 64-bit compressed image is disabled.  cfitsio library doesn't
        # seem to like it
        # TODO: Confirm whether the 64-bit compressed case is still broken on
        # CFITSIO
        for utype, compressed in [
                ('u2',False), ('u4',False), ('u8',False), ('u2',True),
                ('u4',True)]:  # ,('u8',True)
            self._test_uint(utype, compressed)

    def _test_uint(self, utype, compressed):
        bits = 8 * int(utype[1])
        if platform.architecture()[0] == '64bit' or bits != 64:
            if compressed:
                hdu = fits.CompImageHDU(np.array([-3, -2, -1, 0, 1, 2, 3]))
                hdu_number = 1
            else:
                hdu = fits.PrimaryHDU(np.array([-3, -2, -1, 0, 1, 2, 3]))
                hdu_number = 0
            hdu.scale('int%s' % bits, '', bzero=2 ** (bits-1))

            with ignore_warnings():
                hdu.writeto(self.temp('tempfile.fits'), clobber=True)

            with fits.open(self.temp('tempfile.fits'), uint=True) as hdul:
                assert hdul[hdu_number].data.dtype == self.utype_map[utype]
                assert (hdul[hdu_number].data == np.array(
                    [(2 ** bits) - 3, (2 ** bits) - 2, (2 ** bits) - 1,
                    0, 1, 2, 3],
                    dtype=self.utype_map[utype])).all()

                with ignore_warnings():
                    hdul.writeto(self.temp('tempfile1.fits'), clobber=True)

                with fits.open(self.temp('tempfile1.fits'),
                               uint16=True) as hdul1:
                    d1 = hdul[hdu_number].data
                    d2 = hdul1[hdu_number].data
                    assert (d1 == d2).all()
                    if not compressed:
                        # TODO: Enable these lines if CompImageHDUs ever grow
                        # .section support
                        sec = hdul[hdu_number].section[:1]
                        assert sec.dtype.name == 'uint%s' % bits
                        assert (sec == d1[:1]).all()

    def test_uint_columns(self):
        """Test basic functionality of tables with columns containing
        pseudo-unsigned integers.  See
        https://github.com/astropy/astropy/pull/906
        """

        for utype in ('u2', 'u4', 'u8'):
            self._test_uint_columns(utype)

    def _test_uint_columns(self, utype):
        # Construct array
        bits = 8*int(utype[1])
        if platform.architecture()[0] == '64bit' or bits != 64:
            bzero = self.utype_map[utype](2**(bits-1))
            one = self.utype_map[utype](1)
            u0 = np.arange(bits+1,dtype=self.utype_map[utype])
            u = 2**u0 - one
            if bits == 64:
                u[63] = bzero - one
                u[64] = u[63] + u[63] + one
            uu = (u - bzero).view(self.itype_map[utype])

            # Construct a table from explicit column
            col = fits.Column(name=utype, array=u,
                              format=self.format_map[utype], bzero=bzero)

            table = fits.new_table([col])
            assert (table.data[utype] == u).all()
            # This used to be table.data.base, but now after adding a table to
            # a BinTableHDU it gets stored as a view of the original table,
            # even if the original was already a FITS_rec.  So now we need
            # table.data.base.base
            assert (table.data.base.base[utype] == uu).all()
            hdu0 = fits.PrimaryHDU()
            hdulist = fits.HDUList([hdu0,table])

            with ignore_warnings():
                hdulist.writeto(self.temp('tempfile.fits'), clobber=True)

            # Test write of unsigned int
            del hdulist
            with fits.open(self.temp('tempfile.fits'), uint=True) as hdulist2:
                hdudata = hdulist2[1].data
                assert (hdudata[utype] == u).all()
                assert (hdudata[utype].dtype == self.utype_map[utype])
                assert (hdudata.base[utype] == uu).all()

            # Construct recarray then write out that.
            v = u.view(dtype=[(utype, self.utype_map[utype])])

            with ignore_warnings():
                fits.writeto(self.temp('tempfile2.fits'), v, clobber=True)

            with fits.open(self.temp('tempfile2.fits'), uint=True) as hdulist3:
                hdudata3 = hdulist3[1].data
                assert (hdudata3.base[utype] ==
                        table.data.base.base[utype]).all()
                assert (hdudata3[utype] == table.data[utype]).all()
                assert (hdudata3[utype] == u).all()
