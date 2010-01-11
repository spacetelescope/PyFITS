from __future__ import division # confidence high

import unittest
import pyfits
import numpy
import numpy as np
import exceptions,os,sys

# Define a junk file for redirection of stdout
jfile = "junkfile.fits"

class TestPyfitsChecksumFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass

    def tearDown(self):
        # Perform clean-up actions (if any)
        pass

    def testSampleFile(self):
        hdul=pyfits.open('checksum.fits',checksum=True)

    def testImageCreate(self):
        n=np.arange(100)
        hdu=pyfits.PrimaryHDU(n)
        hdu.writeto('tmp.fits',clobber=True,checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')

    def testScaledData(self):
        hdul=pyfits.open('scale.fits')
        hdul[0].scale('int16','old')
        hdul.writeto('tmp.fits',clobber=True,checksum=True)
        hdul1=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')

    def testUint16Data(self):
        hdul=pyfits.open('o4sp040b0_raw.fits',uint16=1)
        hdul.writeto('tmp.fits',clobber=True,checksum=True)
        hdul1=pyfits.open('tmp.fits',uint16=1,checksum=True)
        os.remove('tmp.fits')

    def testGroupsHDUData(self):
        imdata = np.arange(100.)
        imdata.shape=(10,1,1,2,5)
        pdata1 = np.arange(10)+0.1
        pdata2 = 42
        x = pyfits.GroupData(imdata,parnames=['abc','xyz'],
                             pardata=[pdata1,pdata2],bitpix=-32)
        hdu=pyfits.GroupsHDU(x)
        hdu.writeto('tmp.fits',clobber=True,checksum=True)
        hdul1=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')

    def testBinaryTableData(self):
        a1 = np.array(['NGC1001','NGC1002','NGC1003'])
        a2 = np.array([11.1,12.3,15.2])
        col1 = pyfits.Column(name='target',format='20A',array=a1)
        col2=pyfits.Column(name='V_mag',format='E',array=a2)
        cols=pyfits.ColDefs([col1, col2])
        tbhdu=pyfits.new_table(cols)
        tbhdu.writeto('tmp.fits',clobber=True,checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')

    def testVariableLengthTableData(self):
        c1 = pyfits.Column(name='var',format='PJ()',\
             array=np.array([[45.,56],np.array([11,12,13])],'O'))
        c2 = pyfits.Column(name='xyz',format='2I',array=[[11,3],[12,4]])
        tbhdu=pyfits.new_table([c1,c2])
        tbhdu.writeto('tmp.fits',clobber=True,checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')

    def testAsciiTableData(self):
        a1 = np.array(['abc','def'])
        r1 = np.array([11.,12.])
        c1 = pyfits.Column(name='abc', format='A3', array=a1)
        c2 = pyfits.Column(name='def', format='E', array=r1, bscale=2.3,
                           bzero=0.6)
        c3 = pyfits.Column(name='t1', format='I', array=[91,92,93])
        x = pyfits.ColDefs([c1,c2,c3], tbtype='TableHDU')
        hdu = pyfits.new_table(x, tbtype='TableHDU')
        hdu.writeto('tmp.fits', clobber=True, checksum=True)
        hdul=pyfits.open('tmp.fits', checksum=True)
        os.remove('tmp.fits')

    def testCompressedImageData(self):
        hdul=pyfits.open('comp.fits')
        hdul.writeto('tmp.fits',clobber=True,checksum=True)
        hdul1=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')
        n=np.arange(100,dtype='int16')
        hdu=pyfits.ImageHDU(n)
        comp_hdu = pyfits.CompImageHDU(hdu.data, hdu.header)
        comp_hdu.writeto('tmp.fits',checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')
        n=np.arange(100, dtype='float32')
        comp_hdu = pyfits.CompImageHDU(n)
        comp_hdu.writeto('tmp.fits',checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)
        os.remove('tmp.fits')

    def testOpenWithNoKeywords(self):
        hdul=pyfits.open('arange.fits',checksum=True)

    def testAppend(self):
        hdul=pyfits.open('tb.fits')
        hdul.writeto('tmp.fits', clobber=True)
        n=np.arange(100)
        pyfits.append('tmp.fits',n,checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)
        self.assertEqual(hdul[0]._checksum, None)
        os.remove('tmp.fits')

    def testWritetoConvenience(self):
        n=np.arange(100)
        pyfits.writeto('tmp.fits',n,clobber=True,checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)

        if not hasattr(hdul[0], '_datasum') or not hdul[0]._datasum:
            os.remove('tmp.fits')
            self.fail(msg="Missing DATASUM keyword")

        if not hasattr(hdul[0], '_checksum') or not hdul[0]._checksum:
            os.remove('tmp.fits')
            self.fail(msg="Missing CHECKSUM keyword")

        if not hasattr(hdul[0], '_datasum_comment') or \
           not hdul[0]._datasum_comment:
            os.remove('tmp.fits')
            self.fail(msg="Missing DATASUM Card comment")

        if not hasattr(hdul[0], '_checksum_comment') or \
           not hdul[0]._checksum_comment:
            os.remove('tmp.fits')
            self.fail(msg="Missing CHECKSUM Card comment")

        os.remove('tmp.fits')

    def testHduWriteto(self):
        n=np.arange(100,dtype='int16')
        hdu=pyfits.ImageHDU(n)
        hdu.writeto('tmp.fits',checksum=True)
        hdul=pyfits.open('tmp.fits',checksum=True)

        if not hasattr(hdul[0], '_datasum') or not hdul[0]._datasum:
            os.remove('tmp.fits')
            self.fail(msg="Missing DATASUM keyword")

        if not hasattr(hdul[0], '_checksum') or not hdul[0]._checksum:
            os.remove('tmp.fits')
            self.fail(msg="Missing CHECKSUM keyword")

        if not hasattr(hdul[0], '_datasum_comment') or \
           not hdul[0]._datasum_comment:
            os.remove('tmp.fits')
            self.fail(msg="Missing DATASUM Card comment")

        if not hasattr(hdul[0], '_checksum_comment') or \
           not hdul[0]._checksum_comment:
            os.remove('tmp.fits')
            self.fail(msg="Missing CHECKSUM Card comment")

        os.remove('tmp.fits')

    def testDatasumOnly(self):
        n=np.arange(100,dtype='int16')
        hdu=pyfits.ImageHDU(n)
        hdu.writeto('tmp.fits',clobber=True,checksum='datasum')
        hdul=pyfits.open('tmp.fits',checksum=True)

        if not hasattr(hdul[0], '_datasum') or not hdul[0]._datasum:
            os.remove('tmp.fits')
            self.fail(msg="Missing DATASUM keyword")

        if not hasattr(hdul[0], '_checksum') or hdul[0]._checksum:
            os.remove('tmp.fits')
            self.fail(msg="Missing CHECKSUM keyword")

        if not hasattr(hdul[0], '_datasum_comment') or \
           not hdul[0]._datasum_comment:
            os.remove('tmp.fits')
            self.fail(msg="Missing DATASUM Card comment")

        if not hasattr(hdul[0], '_checksum_comment') or \
           hdul[0]._checksum_comment:
            os.remove('tmp.fits')
            self.fail(msg="Missing CHECKSUM Card comment")

        os.remove('tmp.fits')



if __name__ == '__main__':
    unittest.main()

