from __future__ import division # confidence high
from __future__ import with_statement

import os
import sys
import unittest

import numpy as np

import pyfits
from pyfits.tests.util import CaptureStdout


data_dir = os.path.join(os.path.dirname(__file__), 'data')


class TestPyfitsDivisionFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass

    def tearDown(self):
        # Perform clean-up actions (if any)
        try:
            os.remove('new.fits')
        except:
            pass

    def testRecFromString(self):
        t1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        s = t1[1].data.tostring()
        a1 = pyfits.rec.array(
                s,
                dtype=np.dtype([('c1', '>i4'), ('c2', '|S3'),
                                ('c3', '>f4'), ('c4', '|i1')]))

    def testCard_ncards(self):
        c1 = pyfits.Card('temp', 80.0, 'temperature')
        self.assertEqual(type(c1._ncards()), type(1))

    def testCardWithContinue(self):
        h = pyfits.PrimaryHDU()
        with CaptureStdout() as f:
            h.header.update('abc', 'abcdefg'*20)
            self.assertEqual(f.getvalue(), '')

    def testValidHDUSize(self):
        t1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        self.assertEqual(type(t1[1].size()), type(1))

    def testHDUGetSize(self):
        with CaptureStdout() as f:
            t1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
            self.assertEqual(f.getvalue(), '')

    def testSection(self):
        # section testing
        fs = pyfits.open(os.path.join(data_dir, 'arange.fits'))
        with CaptureStdout() as f:
            self.assertEqual(fs[0].section[3,2,5], np.array([357]))
            self.assertEqual(f.getvalue(), '')

    def testStreamingHDU(self):
        hd = pyfits.Header()
        hd.update('SIMPLE', True, 'conforms to FITS standard')
        hd.update('BITPIX', 32, 'array data type')
        hd.update('NAXIS', 2, 'number of array dimensions')
        hd.update('NAXIS1', 5)
        hd.update('NAXIS2', 5)
        hd.update('EXTEND', True)
        shdu = pyfits.StreamingHDU('new.fits', hd)

        self.assertEqual(type(shdu.size()), type(1))


if __name__ == '__main__':
    unittest.main()


