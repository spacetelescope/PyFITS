from __future__ import with_statement

import os
import time

import numpy as np
from numpy import char as chararray

from nose.tools import assert_equal, assert_true, assert_raises

import pyfits
from pyfits.tests import PyfitsTestCase
from pyfits.tests.test_table import comparerecords


class TestGroupsFunctions(PyfitsTestCase):
    def test_open(self):
        with pyfits.open(self.data('random_groups.fits')) as hdul:
            assert_true(isinstance(hdul[0], pyfits.GroupsHDU))
            naxes = (3, 1, 128, 1, 1)
            parameters = ['UU', 'VV', 'WW', 'BASELINE', 'DATE']
            assert_equal(hdul.info(output=False),
                         [(0, 'PRIMARY', 'GroupsHDU', 147, naxes, 'float32',
                           '3 Groups  5 Parameters')])

            ghdu = hdul[0]
            assert_equal(ghdu.parnames, parameters)
            assert_equal(list(ghdu.data.dtype.names), parameters + ['DATA'])

            assert_true(isinstance(ghdu.data, pyfits.GroupData))
            # The data should be equal to the number of groups
            assert_equal(ghdu.header['GCOUNT'], len(ghdu.data))
            assert_equal(ghdu.data.data.shape, (len(ghdu.data),) + naxes[::-1])
            assert_equal(ghdu.data.parnames, parameters)

            assert_true(isinstance(ghdu.data[0], pyfits.Group))
            assert_equal(len(ghdu.data[0]), len(parameters) + 1)
            assert_equal(ghdu.data[0].data.shape, naxes[::-1])
            assert_equal(ghdu.data[0].parnames, parameters)

    def test_open_groups_in_update_mode(self):
        """
        Test that opening a file containing a groups HDU in update mode and
        then immediately closing it does not result in any unnecessary file
        modifications.

        Similar to
        test_image.TestImageFunctions.test_open_scaled_in_update_mode().
        """

        # Copy the original file before making any possible changes to it
        self.copy_file('random_groups.fits')
        mtime = os.stat(self.temp('random_groups.fits')).st_mtime

        time.sleep(1)

        pyfits.open(self.temp('random_groups.fits'), mode='update',
                    memmap=False).close()

        # Ensure that no changes were made to the file merely by immediately
        # opening and closing it.
        assert_equal(mtime, os.stat(self.temp('random_groups.fits')).st_mtime)

    def test_parnames_round_trip(self):
        """
        Regression test for #130.  Ensures that opening a random groups file in
        update mode or writing it to a new file does not cause any change to
        the parameter names.
        """

        # Because this test tries to update the random_groups.fits file, let's
        # make a copy of it first (so that the file doesn't actually get
        # modified in the off chance that the test fails
        self.copy_file('random_groups.fits')

        parameters = ['UU', 'VV', 'WW', 'BASELINE', 'DATE']
        with pyfits.open(self.temp('random_groups.fits'), mode='update') as h:
            assert_equal(h[0].parnames, parameters)
            h.flush()
        # Open again just in read-only mode to ensure the parnames didn't
        # change
        with pyfits.open(self.temp('random_groups.fits')) as h:
            assert_equal(h[0].parnames, parameters)
            h.writeto(self.temp('test.fits'))

        with pyfits.open(self.temp('test.fits')) as h:
            assert_equal(h[0].parnames, parameters)

    def test_groupdata_slice(self):
        """
        A simple test to ensure that slicing GroupData returns a new, smaller
        GroupData object, as is the case with a normal FITS_rec.  This is a
        regression test for an as-of-yet unreported issue where slicing
        GroupData returned a single Group record.
        """


        with pyfits.open(self.data('random_groups.fits')) as hdul:
            s = hdul[0].data[1:]
            assert_true(isinstance(s, pyfits.GroupData))
            assert_equal(len(s), 2)
            assert_equal(hdul[0].data.parnames, s.parnames)

    def test_group_slice(self):
        """
        Tests basic slicing a single group record.
        """

        # A very basic slice test
        with pyfits.open(self.data('random_groups.fits')) as hdul:
            g = hdul[0].data[0]
            s = g[2:4]
            assert_equal(len(s), 2)
            assert_equal(s[0], g[2])
            assert_equal(s[-1], g[-3])
            s = g[::-1]
            assert_equal(len(s), 6)
            assert_true((s[0] == g[-1]).all())
            assert_equal(s[-1], g[0])
            s = g[::2]
            assert_equal(len(s), 3)
            assert_equal(s[0], g[0])
            assert_equal(s[1], g[2])
            assert_equal(s[2], g[4])

    def test_create_groupdata(self):
        """
        Basic test for creating GroupData from scratch.
        """

        imdata = np.arange(100.0)
        imdata.shape = (10, 1, 1, 2, 5)
        pdata1 = np.arange(10, dtype=np.float32) + 0.1
        pdata2 = 42.0
        x = pyfits.hdu.groups.GroupData(imdata, parnames=['abc', 'xyz'],
                                        pardata=[pdata1, pdata2], bitpix=-32)

        assert_equal(x.parnames, ['abc', 'xyz'])
        assert_true((x.par('abc') == pdata1).all())
        assert_true((x.par('xyz') == ([pdata2] * len(x))).all())
        assert_true((x.data == imdata).all())

        # Test putting the data into a GroupsHDU and round-tripping it
        ghdu = pyfits.GroupsHDU(data=x)
        ghdu.writeto(self.temp('test.fits'))

        with pyfits.open(self.temp('test.fits')) as h:
            hdr = h[0].header
            assert_equal(hdr['GCOUNT'], 10)
            assert_equal(hdr['PCOUNT'], 2)
            assert_equal(hdr['NAXIS'], 5)
            assert_equal(hdr['NAXIS1'], 0)
            assert_equal(hdr['NAXIS2'], 5)
            assert_equal(hdr['NAXIS3'], 2)
            assert_equal(hdr['NAXIS4'], 1)
            assert_equal(hdr['NAXIS5'], 1)
            assert_equal(h[0].data.parnames, ['abc', 'xyz'])
            assert_true(comparerecords(h[0].data, x))

    def test_duplicate_parameter(self):
        """
        Tests support for multiple parameters of the same name, and ensures
        that the data in duplicate parameters are returned as a single summed
        value.
        """

        imdata = np.arange(100.0)
        imdata.shape = (10, 1, 1, 2, 5)
        pdata1 = np.arange(10, dtype=np.float32) + 1
        pdata2 = 42.0
        x = pyfits.hdu.groups.GroupData(imdata, parnames=['abc', 'xyz', 'abc'],
                                        pardata=[pdata1, pdata2, pdata1],
                                        bitpix=-32)

        assert_equal(x.parnames, ['abc', 'xyz', 'abc'])
        assert_true((x.par('abc') == pdata1 * 2).all())
        assert_equal(x[0].par('abc'), 2)

        # Test setting a parameter
        x[0].setpar(0, 2)
        assert_equal(x[0].par('abc'), 3)
        assert_raises(ValueError, x[0].setpar, 'abc', 2)
        x[0].setpar('abc', (2, 3))
        assert_equal(x[0].par('abc'), 5)
        assert_equal(x.par('abc')[0], 5)
        assert_true((x.par('abc')[1:] == pdata1[1:] * 2).all())

        # Test round-trip
        ghdu = pyfits.GroupsHDU(data=x)
        ghdu.writeto(self.temp('test.fits'))

        with pyfits.open(self.temp('test.fits')) as h:
            hdr = h[0].header
            assert_equal(hdr['PCOUNT'], 3)
            assert_equal(hdr['PTYPE1'], 'abc')
            assert_equal(hdr['PTYPE2'], 'xyz')
            assert_equal(hdr['PTYPE3'], 'abc')
            assert_equal(x.parnames, ['abc', 'xyz', 'abc'])
            assert_equal(x.dtype.names, ('abc', 'xyz', '_abc', 'DATA'))
            assert_equal(x.par('abc')[0], 5)
            assert_true((x.par('abc')[1:] == pdata1[1:] * 2).all())
