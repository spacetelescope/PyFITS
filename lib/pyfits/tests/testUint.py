from __future__ import division

import os
import platform
import sys
import unittest

import numpy as np

import pyfits

class TestPyfitsUintFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass

    def tearDown(self):
        # Perform clean-up actions (if any)
        try:
            os.remove('tempfile.fits')
        except:
            pass

        try:
            os.remove('tempfile1.fits')
        except:
            pass


    def testUint16(self):
        hdu = pyfits.PrimaryHDU(np.array([-3,-2,-1,0,1,2,3]))
        hdu.scale('int16', '', bzero=2**15)
        hdu.writeto('tempfile.fits')
        hdul = pyfits.open('tempfile.fits', uint=True)
        self.assertEqual(hdul[0].data.dtype, np.uint16)
        self.assertEqual(np.all(hdul[0].data == 
                         np.array([(2**16)-3, (2**16)-2, (2**16)-1, 0, 1, 2, 3],
                                  dtype=np.uint16)), True)
        hdul.writeto('tempfile1.fits')
        hdul1 = pyfits.open('tempfile1.fits', uint16=True)
        self.assertEqual(np.all(hdul[0].data == hdul1[0].data), True)
        self.assertEqual(hdul[0].section[:1].dtype, np.dtype('uint16'))
        hdul.close()
        hdul1.close()
        os.remove('tempfile1.fits')
        os.remove('tempfile.fits')

    def testUint32(self):
        hdu = pyfits.PrimaryHDU(np.array([-3, -2, -1, 0, 1, 2, 3]))
        hdu.scale('int32', '', bzero=2**31)
        hdu.writeto('tempfile.fits')
        hdul = pyfits.open('tempfile.fits', uint=True)
        self.assertEqual(hdul[0].data.dtype, np.uint32)
        self.assertEqual(np.all(hdul[0].data == 
                         np.array([(2**32)-3, (2**32)-2, (2**32)-1, 0, 1, 2, 3],
                         dtype=np.uint32)), True)
        hdul.writeto('tempfile1.fits')
        hdul1 = pyfits.open('tempfile1.fits', uint=True)
        self.assertEqual(np.all(hdul[0].data == hdul1[0].data), True)
        self.assertEqual(hdul[0].section[:1].dtype, np.dtype('uint32'))
        hdul.close()
        hdul1.close()
        os.remove('tempfile1.fits')
        os.remove('tempfile.fits')

    def testUint64(self):
        if platform.architecture()[0] == '64bit':
            hdu = pyfits.PrimaryHDU(np.array([-3,-2,-1,0,1,2,3]))
            hdu.scale('int64', '', bzero=2**63)
            hdu.writeto('tempfile.fits')
            hdul = pyfits.open('tempfile.fits', uint=True)
            self.assertEqual(hdul[0].data.dtype, np.uint64)
            self.assertEqual(np.all(hdul[0].data == 
                             np.array([(2**64)-3,(2**64)-2,(2**64)-1,0,1,2,3],
                             dtype=np.uint64)), True)
            hdul.writeto('tempfile1.fits')
            hdul1 = pyfits.open('tempfile1.fits',uint=True)
            self.assertEqual(np.all(hdul[0].data == hdul1[0].data), True)
            self.assertEqual(hdul[0].section[:1].dtype, np.dtype('uint64'))
            hdul.close()
            hdul1.close()
            os.remove('tempfile1.fits')
            os.remove('tempfile.fits')


if __name__ == '__main__':
    unittest.main()


