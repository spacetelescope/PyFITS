import unittest, fits, os

KeywordRegexSuite = unittest.TestSuite

class InitCase(unittest.TestCase):

    def testName(self):
        self.file = fits.File('tempfile.fits', 'w')
        self.failUnless(self.file.name == 'tempfile.fits')

    def testMode1(self):
        self.file = open('tempfile.fits', 'wb')
        self.file.write(2880*' ')
        self.file.close()
        self.file = fits.File('tempfile.fits')
        self.failUnless(self.file.mode == 'r+b')

    def testMode2(self):
        self.file = fits.File('tempfile.fits', 'w')
        self.failUnless(self.file.mode == 'w+b')

    def testMode3(self):
        self.file = fits.File('tempfile.fits', mode='w+')
        self.failUnless(self.file.mode == 'w+b')

    def tearDown(self):
        self.file.close()
        os.unlink('tempfile.fits')


class ReadHDUCase(unittest.TestCase):
    def setUp(self):
        import struct
        self.temp = open('tempfile.fits', 'w+b')
        cards = [('SIMPLE', fits.TRUE),
                 ('BITPIX', 32),
                 ('NAXIS',   2),
                 ('NAXIS1', 10),
                 ('NAXIS2', 10),
                 ('',       ''),
                 ('',       ''),
                 ('',       ''),
                 ('',       '')]
        self.temp.write(''.join([str(fits.Card(c[0], c[1])) for c in cards]))
        self.temp.write(str(fits.Card('END')))
        self.temp.write((35-len(cards))*80*' ')
        self.temp.write(100*struct.pack('i', 1))
        self.temp.write((2880/4-100)*struct.pack('i', 0))
        self.temp.flush()
        self.fits = fits.open('tempfile.fits')

    def testSimpleHeader(self):
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.PrimaryHDU))

    def testGroupsHeader(self):
        self.temp.seek(3*80)
        self.temp.write(str(fits.Card('NAXIS1', 0)))
        self.temp.seek(6*80)
        self.temp.write(str(fits.Card('GROUPS', fits.TRUE)))
        self.temp.write(str(fits.Card('PCOUNT', 0)))
        self.temp.write(str(fits.Card('GCOUNT', 1)))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.GroupsHDU))

    def testNonConformingHDU1(self):
        self.temp.seek(0*80)
        self.temp.write(str(fits.Card('SIMPLE', fits.FALSE)))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.NonConformingHDU))

    def testTableHDU(self):
        import struct
        cards = [('XTENSION', 'TABLE'),
                 ('BITPIX',  8),
                 ('NAXIS',   2),
                 ('NAXIS1', 10),
                 ('NAXIS2', 10),
                 ('PCOUNT',  0),
                 ('GCOUNT',  1),
                 ('TFIELDS', 2),
                 ('',       ''),
                 ('',       ''),
                 ('TBCOL1',  1),
                 ('TFORM1', 'A8'),
                 ('TBCOL2',  9),
                 ('TFORM2', 'F8.3'),
                 ('',       ''),
                 ('',       '')]
        self.temp.write(''.join([str(fits.Card(c[0], c[1])) for c in cards]))
        self.temp.write(str(fits.Card('END')))
        self.temp.write((35-len(cards))*80*' ')
        self.temp.write(100*struct.pack('i', 1))
        self.temp.write((2880/4-100)*struct.pack('i', 0))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[1], fits.TableHDU))

    def testImageHDU(self):
        import struct
        cards = [('XTENSION', 'IMAGE'),
                 ('BITPIX',  32),
                 ('NAXIS',   2),
                 ('NAXIS1', 10),
                 ('NAXIS2', 10),
                 ('PCOUNT',  0),
                 ('GCOUNT',  1),
                 ('',       ''),
                 ('',       '')]
        self.temp.write(''.join([str(fits.Card(c[0], c[1])) for c in cards]))
        self.temp.write(str(fits.Card('END')))
        self.temp.write((35-len(cards))*80*' ')
        self.temp.write(100*struct.pack('i', 1))
        self.temp.write((2880/4-100)*struct.pack('i', 0))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[1], fits.ImageHDU))

    def testBinTableHDU(self):
        import struct
        cards = [('XTENSION', 'BINTABLE'),
                 ('BITPIX',  8),
                 ('NAXIS',   2),
                 ('NAXIS1', 10),
                 ('NAXIS2', 10),
                 ('PCOUNT',  0),
                 ('GCOUNT',  1),
                 ('TFIELDS', 2),
                 ('',       ''),
                 ('',       ''),
                 ('TFORM1', '1I'),
                 ('TFORM2', '1D'),
                 ('',       ''),
                 ('',       '')]
        self.temp.write(''.join([str(fits.Card(c[0], c[1])) for c in cards]))
        self.temp.write(str(fits.Card('END')))
        self.temp.write((35-len(cards))*80*' ')
        self.temp.write(100*struct.pack('i', 1))
        self.temp.write((2880/4-100)*struct.pack('i', 0))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[1], fits.BinTableHDU))

    def testConformingHDU(self):
        import struct
        cards = [('XTENSION', 'MYTABLE'),
                 ('BITPIX',  8),
                 ('NAXIS',   2),
                 ('NAXIS1', 10),
                 ('NAXIS2', 10),
                 ('',       ''),
                 ('',       ''),
                 ('PCOUNT',  0),
                 ('GCOUNT',  1),
                 ('',       ''),
                 ('',       '')]
        self.temp.write(''.join([str(fits.Card(c[0], c[1])) for c in cards]))
        self.temp.write(str(fits.Card('END')))
        self.temp.write((35-len(cards))*80*' ')
        self.temp.write(100*struct.pack('i', 1))
        self.temp.write((2880/4-100)*struct.pack('i', 0))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[1], fits.ConformingHDU))

    def testNonConformingHDU2(self):
        self.temp.seek(0*80)
        self.temp.write(str(fits.Card('HEADER', 1)))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.NonConformingHDU))

    def testBadKeyword(self):
        self.temp.seek(5*80)
        self.temp.write('%-8s= %20e%-50s'%('BADVALUE', 1.0e-9, ' / bad value'))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.PrimaryHDU))

    def testBadFirstCard(self):
        self.temp.seek(0*80)
        self.temp.write('%-80s'%'The first header card is garbage!')
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.CorruptedHDU))

    def testNoBITPIX(self):
        self.temp.seek(1*80)
        self.temp.write(str(fits.Card()))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.CorruptedHDU))

    def testNoNAXIS(self):
        self.temp.seek(2*80)
        self.temp.write(str(fits.Card()))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.CorruptedHDU))

    def testBadNAXIS2(self):
        self.temp.seek(4*80)
        self.temp.write(str(fits.Card('NAXIS2', -10)))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.CorruptedHDU))

    def testNoNAXIS2(self):
        self.temp.seek(4*80)
        self.temp.write(str(fits.Card()))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.CorruptedHDU))

    def testNoEndCard(self):
        self.temp.seek(9*80)
        self.temp.write(str(fits.Card()))
        self.temp.flush()
        hdu = self.fits.read()
        self.failUnless(isinstance(hdu[0], fits.CorruptedHDU))

    def testBadBlock(self):
        self.temp.truncate(2880-1)
        self.failUnlessRaises(IOError, self.fits.read)

    def tearDown(self):
        self.temp.close()
        self.fits.close()
        os.unlink('tempfile.fits')


class ReadCase(unittest.TestCase):
    def setUp(self):
        pass

    def testNoHDUs(self):
        self.temp = open('tempfile.fits', 'w+b')
        self.temp.close()
        self.temp = fits.File('tempfile.fits')
        hdus = self.temp.read()
        self.failUnless(hdus == [])
        self.temp.close()
        os.unlink('tempfile.fits')

    def testOneHDU(self):
        import struct
        self.temp = open('tempfile.fits', 'w+b')
        cards = [('SIMPLE', fits.TRUE),
                 ('BITPIX', 32),
                 ('NAXIS',   2),
                 ('NAXIS1', 10),
                 ('NAXIS2', 10),
                 ('',       ''),
                 ('',       ''),
                 ('',       ''),
                 ('',       '')]
        self.temp.write(''.join([str(fits.Card(c[0], c[1])) for c in cards]))
        self.temp.write(str(fits.Card('END')))
        self.temp.write((35-len(cards))*80*' ')
        self.temp.write(100*struct.pack('i', 1))
        self.temp.write((2880/4-100)*struct.pack('i', 0))
        self.temp.close()
        self.temp = fits.File('tempfile.fits')
        hdus = self.temp.read()
        self.failUnless(len(hdus) == 1 and isinstance(hdus[0],fits.PrimaryHDU))
        self.temp.close()
        os.unlink('tempfile.fits')

    def tearDown(self):
        pass


class WriteHDUCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


class WriteCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main()
