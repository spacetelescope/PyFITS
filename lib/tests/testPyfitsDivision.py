from __future__ import division # confidence high

import unittest
import numpy as np
import pyfits
import os
import exceptions
import sys

test_dir = os.path.dirname(__file__) + "/"

# Define a junk file for redirection of stdout
jfile = "junkfile.fits"

class TestPyfitsDivisionFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass

    def tearDown(self):
        # Perform clean-up actions (if any)
        try:
            os.remove('newtable.fits')
        except:
            pass

        try:
            os.remove('table1.fits')
        except:
            pass

        try:
            os.remove('table2.fits')
        except:
            pass

    def testRecFromString(self):
        t1=pyfits.open(test_dir+'tb.fits')
        s=t1[1].data.tostring()
        a1=pyfits.rec.array(s,dtype=np.dtype([('c1', '>i4'), ('c2', '|S3'),
                                              ('c3', '>f4'), ('c4', '|i1')]))

    def testCard_ncards(self):
        c1 = pyfits.Card('temp',80.0,'temperature')
        self.assertEqual(type(c1._ncards()), type(1))

    def testCardWithContinue(self):
        h = pyfits.PrimaryHDU()
        tmpfile = open(jfile,'w')
        sys.stdout = tmpfile
        h.header.update('abc','abcdefg'*20)
        sys.stdout = sys.__stdout__
        tmpfile.close()
        tmpfile = open(jfile,'r')
        output = tmpfile.readlines()
        tmpfile.close()
        os.remove(jfile)

        self.assertEqual(output, [])

    def testValidHDUSize(self):
        t1=pyfits.open(test_dir+'tb.fits')
        self.assertEqual(type(t1[1].size()), type(1))

    def testHDUGetSize(self):
        tmpfile = open(jfile,'w')
        sys.stdout = tmpfile
        t1=pyfits.open(test_dir+'tb.fits')
        sys.stdout = sys.__stdout__
        tmpfile.close()
        tmpfile = open(jfile,'r')
        output = tmpfile.readlines()
        tmpfile.close()
        os.remove(jfile)

        self.assertEqual(output, [])

    def testSection(self):
        # section testing
        fs=pyfits.open(test_dir+'arange.fits')
        tmpfile = open(jfile,'w')
        sys.stdout = tmpfile
        self.assertEqual(fs[0].section[3,2,5],np.array([357]))
        sys.stdout = sys.__stdout__
        tmpfile.close()
        tmpfile = open(jfile,'r')
        output = tmpfile.readlines()
        tmpfile.close()
        os.remove(jfile)

        self.assertEqual(output, [])

    def testStreamingHDU(self):
        hd = pyfits.Header()
        hd.update('SIMPLE',True,'conforms to FITS standard')
        hd.update('BITPIX',32,'array data type')
        hd.update('NAXIS',2, 'number of array dimensions')
        hd.update('NAXIS1',5)
        hd.update('NAXIS2',5)
        hd.update('EXTEND', True)
        shdu = pyfits.StreamingHDU('new.fits',hd)

        self.assertEqual(type(shdu.size()), type(1))




if __name__ == '__main__':
    unittest.main()


