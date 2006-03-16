import unittest, fits, os

KeywordRegexSuite = unittest.TestSuite

class InitCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(2880*' ')
        self.file.seek(0)

    def testBadBufferSize(self):
        self.failUnlessRaises(ValueError, fits.CardList,
                              fits.Buffer(2879, 0, self.file))

    def testBadOffset(self):
        self.failUnlessRaises(ValueError, fits.CardList,
                              fits.Buffer(2880, 1, self.file))

    def testBadNumberofCards(self):
        self.failUnlessRaises(ValueError, fits.CardList,
                              fits.Buffer(2880, 0, self.file), -1)

    def testBadListLength(self):
        self.failUnlessRaises(ValueError, fits.CardList,
                              fits.Buffer(400, 0, self.file), 10)

    def tearDown(self):
        self.file.close()


class SetRangeCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(2880*' ')
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testLowStartValue(self):
        self.failUnless(self.flist._CardList__setrange(-11, 0) == (0, 0))

    def testNegStartValue(self):
        self.failUnless(self.flist._CardList__setrange(-5, 0) == (5, 0))

    def testHighStartValue(self):
        self.failUnless(self.flist._CardList__setrange(11, 0) == (10, 0))

    def testLowStopValue(self):
        self.failUnless(self.flist._CardList__setrange(0, -11) == (0, 0))

    def testNegStopValue(self):
        self.failUnless(self.flist._CardList__setrange(0, -5) == (0, 5))

    def testHighStopValue(self):
        self.failUnless(self.flist._CardList__setrange(0, 11) == (0, 10))

    def tearDown(self):
        self.file.close()


class LengthCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(2*2880*' ')
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 36)

    def testLength(self):
        self.failUnless(len(self.flist) == 36)

    def tearDown(self):
        self.file.close()


class GetItemCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testLowIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.__getitem__, -11)

    def testHighIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.__getitem__, 10)

    def testPosIndexValue(self):
        self.failUnless(str(self.flist[5]) == str(fits.Card('comment', '5')))

    def testNegIndexValue(self):
        self.failUnless(str(self.flist[-5]) == str(fits.Card('comment', '5')))

    def tearDown(self):
        self.file.close()


class SetItemCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testCheckValueType(self):
        self.failUnlessRaises(ValueError, self.flist.__setitem__, 5, '')

    def testLowIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.__setitem__, -11,
                              fits.Card())

    def testHighIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.__setitem__, 10,
                              fits.Card())

    def testPosIndexValue(self):
        self.flist[5] = fits.Card('history', '5')
        self.failUnless(str(self.flist[5]) == str(fits.Card('history', '5')))

    def testNegIndexValue(self):
        self.flist[-5] = fits.Card('history', '-5')
        self.failUnless(str(self.flist[-5]) == str(fits.Card('history', '-5')))

    def tearDown(self):
        self.file.close()


class DelItemCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testLowIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.__delitem__, -11)

    def testHighIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.__delitem__, 10)

    def testPosIndexValue(self):
        del self.flist[5]
        self.failUnless(str(self.flist[5]) == str(fits.Card('comment', '6')))

    def testNegIndexValue(self):
        del self.flist[-5]
        self.failUnless(str(self.flist[5]) == str(fits.Card('comment', '6')))

    def testNewLength(self):
        del self.flist[5]
        self.failUnless(len(self.flist) == 9)

    def testNewSize(self):
        self.file.close()
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(37)]))
        self.file.write(''.join([str(fits.Card()) for j in range(35)]))
        self.flist = fits.CardList(fits.Buffer(2*2880, 0, self.file), 37)
        del self.flist[5]
        self.failUnless(self.flist.size() == 2880)

    def tearDown(self):
        self.file.close()


class GetSliceCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testReturnValue(self):
        self.failUnless([str(c) for c in self.flist[2:5]] == \
                         [str(fits.Card('comment', str(j))) \
                          for j in range(2, 5)])

    def tearDown(self):
        self.file.close()


class SetSliceCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testValueType(self):
        self.failUnlessRaises(ValueError, self.flist.__setslice__, 2, 4, '')

    def testLesserLengthList1(self):
        self.flist[:2] = [fits.Card('comment', '10')]
        self.failUnless([str(c) for c in self.flist[:2]] == \
                        [str(fits.Card('comment', str(j))) for j in [10, 2]])

    def testLesserLengthList2(self):
        self.flist[:2] = [fits.Card('comment', '0')]
        self.failUnless(len(self.flist) == 9)

    def testGreaterLengthList1(self):
        self.flist[:2] = [fits.Card('comment', str(j)) for j in [10, 11, 12]]
        self.failUnless([str(c) for c in self.flist[:4]] == \
                        [str(fits.Card('comment', str(j))) \
                         for j in [10, 11, 12, 2]])

    def testGreaterLengthList2(self):
        self.flist[:2] = [fits.Card('comment', str(j)) for j in [10, 11, 12]]
        self.failUnless(len(self.flist) == 11)

    def testEqualLengthList1(self):
        self.flist[:2] = [fits.Card('comment', str(j)) for j in [10, 11]]
        self.failUnless([str(c) for c in self.flist[:3]] == \
                        [str(fits.Card('comment', str(j))) \
                         for j in [10, 11, 2]])

    def testEqualLengthList2(self):
        self.flist[:2] = [fits.Card('comment', str(j)) for j in [10, 11]]
        self.failUnless(len(self.flist) == 10)

    def tearDown(self):
        self.file.close()

class DelSliceCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testDeleteValue(self):
        del self.flist[:2]
        self.failUnless([str(c) for c in self.flist[:2]] == \
                        [str(fits.Card('comment', str(j))) for j in [2, 3]])

    def testListSize(self):
        del self.flist[:2]
        self.failUnless(len(self.flist) == 8)

    def tearDown(self):
        self.file.close()


class StrCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(2)]))
        self.file.write(''.join([str(fits.Card()) for j in range(34)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 2)

    def testToString(self):
        self.failUnless(str(self.flist) == \
                        ''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(2)]))

    def tearDown(self):
        self.file.close()


class ReprCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(2)]))
        self.file.write(''.join([str(fits.Card()) for j in range(34)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 2)

    def testToString(self):
        pass

    def tearDown(self):
        self.file.close()


class InsertCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('comment', str(j))) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testCheckValueType(self):
        self.failUnlessRaises(ValueError, self.flist.insert, 5, '')

    def testLowIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.insert, -11, fits.Card())

    def testHighIndexValue(self):
        self.failUnlessRaises(IndexError, self.flist.insert, 10, fits.Card())

    def testPosIndexValue(self):
        self.flist.insert(5, fits.Card('history', '6'))
        self.failUnless(str(self.flist[5]) == str(fits.Card('history', '6')))

    def testNegIndexValue(self):
        self.flist.insert(-5, fits.Card('history', '-5'))
        self.failUnless(str(self.flist[5]) == str(fits.Card('history', '-5')))

    def testListlength(self):
        self.flist.insert(5, fits.Card('history', '5'))
        self.failUnless(len(self.flist) == 11)

    def tearDown(self):
        self.file.close()


class AppendCaseToArray(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.flist = fits.CardList(fits.Buffer())

    def testCardToEmptyList(self):
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('comment', '1')))

    def testEndToEmptyList(self):
        self.flist.append(fits.Card('end'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testCardToListWithoutReplace1(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('comment', '1')))

    def testCardToListWithoutReplace2(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '1')))

    def testCardToListWithReplace1(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '1'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '1')))

    def testCardToListWithReplace2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '2'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '2')))

    def testCardToListWithReplace3(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card('end'))
        self.flist.append(fits.Card('comment', '2'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '2')))

    def testEndToListWithoutEnd1(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testEndToListWithoutEnd2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'), replace=1)
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testEndToListWithEnd1(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card('comment', '2'))
        self.flist.append(fits.Card('end'))
        self.failUnlessRaises(ValueError, self.flist.append, fits.Card('end'))

    def testEndToListWithEnd2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.failUnlessRaises(ValueError, self.flist.append, fits.Card('end'),
                              replace=1)

    def tearDown(self):
        self.file.close()


class AppendCaseToFile(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.flist = fits.CardList(fits.Buffer(0, 0, self.file, map=0))

    def testCardToEmptyList(self):
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('comment', '1')))

    def testEndToEmptyList(self):
        self.flist.append(fits.Card('end'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testCardToListWithoutReplace1(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('comment', '1')))

    def testCardToListWithoutReplace2(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '1')))

    def testCardToListWithReplace1(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '1'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '1')))

    def testCardToListWithReplace2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '2'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '2')))

    def testCardToListWithReplace3(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card('end'))
        self.flist.append(fits.Card('comment', '2'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '2')))

    def testEndToListWithoutEnd1(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testEndToListWithoutEnd2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'), replace=1)
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testEndToListWithEnd1(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card('comment', '2'))
        self.flist.append(fits.Card('end'))
        self.failUnlessRaises(ValueError, self.flist.append, fits.Card('end'))

    def testEndToListWithEnd2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.failUnlessRaises(ValueError, self.flist.append, fits.Card('end'),
                              replace=1)

    def tearDown(self):
        self.file.close()


class AppendCaseToMmap(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.flist = fits.CardList(fits.Buffer(0, 0, self.file))

    def testCardToEmptyList(self):
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('comment', '1')))

    def testEndToEmptyList(self):
        self.flist.append(fits.Card('end'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testCardToListWithoutReplace1(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('comment', '1')))

    def testCardToListWithoutReplace2(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.flist.append(fits.Card('comment', '1'))
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '1')))

    def testCardToListWithReplace1(self):
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '1'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '1')))

    def testCardToListWithReplace2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('comment', '2'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '2')))

    def testCardToListWithReplace3(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card('end'))
        self.flist.append(fits.Card('comment', '2'), replace=1)
        self.failUnless(str(self.flist[-2]) == str(fits.Card('comment', '2')))

    def testEndToListWithoutEnd1(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testEndToListWithoutEnd2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'), replace=1)
        self.failUnless(str(self.flist[-1]) == str(fits.Card('end')))

    def testEndToListWithEnd1(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card('comment', '2'))
        self.flist.append(fits.Card('end'))
        self.failUnlessRaises(ValueError, self.flist.append, fits.Card('end'))

    def testEndToListWithEnd2(self):
        self.flist.append(fits.Card('comment', '1'))
        self.flist.append(fits.Card())
        self.flist.append(fits.Card('end'))
        self.failUnlessRaises(ValueError, self.flist.append, fits.Card('end'),
                              replace=1)

    def tearDown(self):
        self.file.close()


class KeysCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('naxis%d'%j, j)) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testReturnValue(self):
        self.failUnless(self.flist.keys() == ['NAXIS%d'%j for j in range(10)])

    def tearDown(self):
        self.file.close()


class IndexOfCase(unittest.TestCase):
    def setUp(self):
        self.file = os.tmpfile()
        self.file.write(''.join([str(fits.Card('naxis%d'%j, j)) \
                                 for j in range(10)]))
        self.file.write(''.join([str(fits.Card()) for j in range(26)]))
        self.flist = fits.CardList(fits.Buffer(2880, 0, self.file), 10)

    def testReturnValue(self):
        self.failUnless(self.flist.index_of('naxis4') == 4)

    def testKeyNotFound(self):
        self.failUnlessRaises(KeyError, self.flist.index_of, 'naxis10')

    def tearDown(self):
        self.file.close()


if __name__ == "__main__":
    unittest.main()
