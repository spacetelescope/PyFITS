import unittest, fits, os

KeywordRegexSuite = unittest.TestSuite

class InitCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(2880*' ')
        self.file.seek(0)

    def testBadSize1(self):
        self.failUnlessRaises(ValueError, fits.Buffer,   -1,  0, self.file)

    def testBadSize2(self):
        self.failUnlessRaises(ValueError, fits.Buffer, 2881,  0, self.file)

    def testBadOffset(self):
        self.failUnlessRaises(ValueError, fits.Buffer, 2880, -1, self.file)

    def testAsArray(self):
        self.failUnless(fits.Buffer(2880)[:] == 2880*' ')

    def testAsArrayWithCards(self):
        self.failUnless(fits.Buffer(2880, cards = \
                                    ['%-80s'%j for j in range(10)])[:] \
                        == ''.join(['%-80s'%j for j in range(10)]) + 2080*' ')

    def testAsFile(self):
        self.failUnless(fits.Buffer(2880, file=self.file, map=0)[:] == \
                        2880*' ')

    def testAsMmap(self):
        self.failUnless(fits.Buffer(2880, file=self.file)[:] == 2880*' ')

    def tearDown(self):
        self.file.close()


class LengthCase(unittest.TestCase):
    def testLength(self):
        self.failUnless(len(fits.Buffer(2880)) == 2880)


class GetItemCase(unittest.TestCase):
    def testNegativeIndex(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ',':')])
        self.failUnless(buffer[40-2880] == ':')

    def testBadIndex(self):
        buffer = fits.Buffer(2880)
        self.failUnlessRaises(IndexError, buffer.__getitem__, 2881)

    def testGetItemFromArray(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ',':')])
        self.failUnless(buffer[40] == ':')

    def testGetItemFromFile(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ',':') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file, map=0)
        self.failUnless(buffer[40] == ':')
        self.file.close()

    def testGetItemFromMmap(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ',':') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file)
        self.failUnless(buffer[40] == ':')
        self.file.close()


class SetItemCase(unittest.TestCase):
    def testNegativeIndex(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ',':')])
        self.failUnless(buffer[40-2880] == ':')

    def testBadIndex(self):
        buffer = fits.Buffer(2880)
        self.failUnlessRaises(IndexError, buffer.__getitem__, 2881)

    def testBadValueLength(self):
        buffer = fits.Buffer(2880)
        self.failUnlessRaises(ValueError, buffer.__setitem__, 40, '  ')

    def testSetItemFromArray(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ',':')])
        buffer[40] = ' '
        self.failUnless(buffer[40] == ' ')

    def testSetItemFromFile(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ',':') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file, map=0)
        buffer[40] = ' '
        self.failUnless(buffer[40] == ' ')
        self.file.close()

    def testSetItemFromMmap(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ',':') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file)
        buffer[40] = ' '
        self.failUnless(buffer[40] == ' ')
        self.file.close()


class GetSliceCase(unittest.TestCase):
    def testGetItemFromArray(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ','12345')])
        self.failUnless(buffer[40:45] == '12345')

    def testGetItemFromFile(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file, map=0)
        self.failUnless(buffer[40:45] == '12345')
        self.file.close()

    def testGetItemFromMmap(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file)
        self.failUnless(buffer[40:45] == '12345')
        self.file.close()


class SetSliceCase(unittest.TestCase):
    def testSetItemFromArray(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ','12345')])
        buffer[40:45] = '67890'
        self.failUnless(buffer[40:50] == '67890     ')

    def testSetItemFromFile(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file, map=0)
        buffer[40:45] = '67890'
        self.failUnless(buffer[40:50] == '67890     ')
        self.file.close()

    def testSetItemFromMmap(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file)
        buffer[40:45] = '67890'
        self.failUnless(buffer[40:50] == '67890     ')
        self.file.close()


class ReprCase(unittest.TestCase):
    def testReprFromArray(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ','12345')])
        self.failUnless(repr(buffer) == '%40s%-40s'%(' ','12345') + 2800*' ')

    def testReprFromFile(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file, map=0)
        self.failUnless(repr(buffer) == '%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.close()

    def testReprFromMmap(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file)
        self.failUnless(repr(buffer) == '%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.close()


class GetBaseCase(unittest.TestCase):
    def testGetBaseFromArray(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ','12345')])
        self.failUnless(buffer.base() == None)

    def testGetBaseFromFile(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file, map=0)
        self.failUnless(buffer.base() == self.file)
        self.file.close()

    def testGetBaseFromMmap(self):
        self.file = os.tmpfile()
        self.file.write('%40s%-40s'%(' ','12345') + 2800*' ')
        self.file.seek(0)
        buffer = fits.Buffer(2880, file=self.file)
        self.failUnless(buffer.base() == self.file)
        self.file.close()


class GetOffsetCase(unittest.TestCase):
    def testGetOffset(self):
        buffer = fits.Buffer(2880, cards=['%40s%-40s'%(' ','12345')])
        self.failUnless(buffer.offset() == 0)


class ResizeCase(unittest.TestCase):
    def testContractFromArray(self):
        self.buffer = fits.Buffer(2*2880)
        self.failUnless(self.buffer.resize(2880) == 2880)

    def testContractFromFile1(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file, map=0)
        self.failUnless(self.buffer.resize(2880) == 2880)

    def testContractFromFile2(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file, map=0)
        self.buffer.resize(2880)
        self.file.seek(0)
        self.failUnless(self.file.read() == 2*2880*' ')

    def testContractFromMmap1(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file)
        self.failUnless(self.buffer.resize(2880) == 2880)

    def testContractFromMmap2(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file)
        self.buffer.resize(2880)
        self.file.seek(0)
        self.failUnless(self.file.read() == 2*2880*' ')

    def testFalseContractFromArray(self):
        self.buffer = fits.Buffer(2*2880)
        self.failUnless(self.buffer.resize(2960) == 2*2880)

    def testFalseContractFromFile1(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file, map=0)
        self.failUnless(self.buffer.resize(2960) == 2*2880)

    def testFalseContractFromFile2(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file, map=0)
        self.buffer.resize(2960)
        self.file.seek(0)
        self.failUnless(self.file.read() == 3*2880*' ')

    def testFalseContractFromMmap1(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file)
        self.failUnless(self.buffer.resize(2960) == 2*2880)

    def testFalseContractFromMmap2(self):
        self.file = os.tmpfile()
        self.file.write(3*2880*' ')
        self.buffer = fits.Buffer(2*2880, 0, self.file)
        self.buffer.resize(2960)
        self.file.seek(0)
        self.failUnless(self.file.read() == 3*2880*' ')

    def testExpandFromArray(self):
        self.buffer = fits.Buffer(2880)
        self.failUnless(self.buffer.resize(2*2880) == 2*2880)

    def testExpandFromFile1(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file, map=0)
        self.failUnless(self.buffer.resize(2*2880) == 2*2880)

    def testExpandFromFile2(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file, map=0)
        self.buffer.resize(2*2880)
        self.file.seek(0)
        self.failUnless(self.file.read() == 3*2880*' ')

    def testExpandFromMmap1(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file)
        self.failUnless(self.buffer.resize(2*2880) == 2*2880)

    def testExpandFromMmap2(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file)
        self.buffer.resize(2*2880)
        self.file.seek(0)
        self.failUnless(self.file.read() == 3*2880*' ')

    def testFalseExpandFromArray(self):
        self.buffer = fits.Buffer(2880)
        self.failUnless(self.buffer.resize(2880) == 2880)

    def testFalseExpandFromFile1(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file, map=0)
        self.failUnless(self.buffer.resize(2880) == 2880)

    def testFalseExpandFromFile2(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file, map=0)
        self.buffer.resize(2880)
        self.file.seek(0)
        self.failUnless(self.file.read() == 2*2880*' ')

    def testFalseExpandFromMmap1(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file)
        self.failUnless(self.buffer.resize(2880) == 2880)

    def testFalseExpandFromMmap2(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.buffer = fits.Buffer(2880, 0, self.file)
        self.buffer.resize(2880)
        self.file.seek(0)
        self.failUnless(self.file.read() == 2*2880*' ')


if __name__ == "__main__":
    unittest.main()
