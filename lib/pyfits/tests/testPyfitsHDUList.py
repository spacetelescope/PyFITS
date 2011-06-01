from __future__ import division # confidence high
from __future__ import with_statement

import os
import sys
import unittest

import numpy as np

import pyfits


data_dir = os.path.join(os.path.dirname(__file__), 'data')


class TestPyfitsHDUListFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass

    def tearDown(self):
        # Perform clean-up actions (if any)
        try:
            os.remove('testAppend.fits')
        except:
            pass

        try:
            os.remove('testInsert.fits')
        except:
            pass

        try:
            os.remove('tmpfile.fits')
        except:
            pass

    def testUpdateName(self):
        hdul = pyfits.open(os.path.join(data_dir, 'o4sp040b0_raw.fits'))
        hdul[4].update_ext_name('Jim', "added by Jim")
        hdul[4].update_ext_version(9, "added by Jim")
        self.assertEqual(hdul[('JIM', 9)].header['extname'], 'JIM')

    def testHDUFileBytes(self):
        hdul = pyfits.open(os.path.join(data_dir, 'checksum.fits'))
        res = hdul[0].filebytes()
        self.assertEqual(res, 11520)
        res = hdul[1].filebytes()
        self.assertEqual(res, 8640)

    def testHDUListFileInfo(self):
        hdul = pyfits.open(os.path.join(data_dir, 'checksum.fits'))
        res = hdul.fileinfo(0)

        def test_fileinfo(**kwargs):
            self.assertEqual(res['datSpan'], kwargs.get('datSpan', 2880))
            self.assertEqual(res['resized'], kwargs.get('resized', 0))
            self.assertEqual(res['filename'],
                             os.path.join(data_dir, 'checksum.fits'))
            self.assertEqual(res['datLoc'], kwargs.get('datLoc', 8640))
            self.assertEqual(res['hdrLoc'], kwargs.get('hdrLoc', 0))
            self.assertEqual(res['filemode'], 'copyonwrite')

        res = hdul.fileinfo(1)
        test_fileinfo(datLoc=17280, hdrLoc=11520)

        hdu = pyfits.ImageHDU(data=hdul[0].data)
        hdul.insert(1, hdu)

        res = hdul.fileinfo(0)
        test_fileinfo(resized=1)

        res = hdul.fileinfo(1)
        test_fileinfo(datSpan=None, resized=1, datLoc=None, hdrLoc=None)

        res = hdul.fileinfo(2)
        test_fileinfo(resized=1, datLoc=17280, hdrLoc=11520)

    def testAppendPrimaryToEmptyList(self):
        # Tests appending a Simple PrimaryHDU to an empty HDUList.
        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]
        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testAppend.fits')

        try:
            self.assertEqual(pyfits.info('testAppend.fits', output=False),
                             info)
        finally:
            os.remove('testAppend.fits')

    def testAppendExtensionToEmptyList(self):
        """Tests appending a Simple ImageHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (100,), 'int32', '')]
        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testAppend.fits')

        try:
            self.assertEqual(pyfits.info('testAppend.fits', output=False),
                             info)
        finally:
            os.remove('testAppend.fits')

    def testAppendTableExtensionToEmptyList(self):
        """Tests appending a Simple Table ExtensionHDU to a empty HDUList."""

        hdul = pyfits.HDUList()
        hdul1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.append(hdul1[1])
        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (), 'uint8', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testAppend.fits')

        try:
            self.assertEqual(pyfits.info('testAppend.fits', output=False),
                             info)
        finally:
            os.remove('testAppend.fits')

    def testAppendGroupsHDUToEmptyList(self):
        """Tests appending a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.append(hdu)

        info = [(0, 'PRIMARY', 'GroupsHDU', 8, (), 'uint8',
                 '   1 Groups  0 Parameters')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testAppend.fits')

        try:
            self.assertEqual(pyfits.info('testAppend.fits', output=False),
                             info)
        finally:
            os.remove('testAppend.fits')

    def testAppendPrimaryToNonEmptyList(self):
        """Tests appending a Simple PrimaryHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'arange.fits'))
        hdu = pyfits.PrimaryHDU(np.arange(100,dtype=np.int32))
        hdul.append(hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 7, (11, 10, 7), 'int32', ''),
                (1, '', 'ImageHDU', 6, (100,), 'int32', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testAppend.fits')

        try:
            self.assertEqual(pyfits.info('testAppend.fits', output=False),
                             info)
        finally:
            os.remove('testAppend.fits')

    def testAppendExtensionToNonEmptyList(self):
        """Tests appending a Simple ExtensionHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.append(hdul[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 11, (), 'int16', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', ''),
                (2, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testAppend.fits')

        try:
            self.assertEqual(pyfits.info('testAppend.fits', output=False),
                             info)
        finally:
            os.remove('testAppend.fits')

    def testAppendGroupsHDUToNonEmptyList(self):
        """Tests appending a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        hdu = pyfits.GroupsHDU()

        self.assertRaises(ValueError, hdul.append, hdu)

    def testInsertPrimaryToEmptyList(self):
        """Tests inserting a Simple PrimaryHDU to an empty HDUList."""
        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertExtensionToEmptyList(self):
        """Tests inserting a Simple ImageHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.ImageHDU(np.arange(100,dtype=np.int32))
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (100,), 'int32', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertTableExtensionToEmptyList(self):
        """Tests inserting a Simple Table ExtensionHDU to a empty HDUList."""

        hdul = pyfits.HDUList()
        hdul1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.insert(0, hdul1[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (), 'uint8', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertGroupsHDUToEmptyList(self):
        """Tests inserting a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'GroupsHDU', 8, (), 'uint8',
                 '   1 Groups  0 Parameters')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertPrimaryToNonEmptyList(self):
        """Tests inserting a Simple PrimaryHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'arange.fits'))
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(1, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 7, (11, 10, 7), 'int32', ''),
                (1, '', 'ImageHDU', 6, (100,), 'int32', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertExtensionToNonEmptyList(self):
        """Tests inserting a Simple ExtensionHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.insert(1, hdul[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 11, (), 'int16', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', ''),
                (2, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertGroupsHDUToNonEmptyList(self):
        """Tests inserting a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)
        hdu = pyfits.GroupsHDU()

        self.assertRaises(ValueError, hdul.insert, hdul, 1, hdu)

        info = [(0, 'PRIMARY', 'GroupsHDU', 8, (), 'uint8',
                 '   1 Groups  0 Parameters'),
                (1, '', 'ImageHDU', 6, (100,), 'int32', '')]

        hdul.insert(0, hdu)

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertGroupsHDUToBeginOfHDUListWithGroupsHDUAlreadyThere(self):
        """
        Tests inserting a Simple GroupsHDU to the beginning of an HDUList
        that that already contains a GroupsHDU.
        """

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.insert(0, hdu)

        self.assertRaises(ValueError, hdul.insert, hdul, 0, hdu)

    def testInsertExtensionToPrimaryInNonEmptyList(self):
        # Tests inserting a Simple ExtensionHDU to a non-empty HDUList.
        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.insert(0, hdul[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (), 'uint8', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', ''),
                (2, '', 'ImageHDU', 12, (), 'uint8', ''),
                (3, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testInsertImageExtensionToPrimaryInNonEmptyList(self):
        """
        Tests inserting a Simple Image ExtensionHDU to a non-empty HDUList
        as the primary HDU.
        """

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', ''),
                (1, '', 'ImageHDU', 12, (), 'uint8', ''),
                (2, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        self.assertEqual(hdul.info(output=False), info)

        hdul.writeto('testInsert.fits')

        try:
            self.assertEqual(pyfits.info('testInsert.fits', output=False),
                             info)
        finally:
            os.remove('testInsert.fits')

    def testFilename(self):
        """Tests the HDUList filename method."""

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        name = hdul.filename()
        self.assertEqual(name, os.path.join(data_dir, 'tb.fits'))

    def testFileLike(self):
        """
        Tests the use of a file like object with no tell or seek methods
        in HDUList.writeto(), HDULIST.flush() or pyfits.writeto()
        """

        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul = pyfits.HDUList()
        hdul.append(hdu)
        tmpfile = open('tmpfile.fits', 'w')
        hdul.writeto(tmpfile)
        tmpfile.close()

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]

        try:
            self.assertEqual(pyfits.info('tmpfile.fits', output=False), info)
        finally:
            os.remove('tmpfile.fits')

        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        tmpfile = open('tmpfile.fits', 'w')
        hdul = pyfits.open(tmpfile, mode='ostream')
        hdul.append(hdu)
        hdul.flush()
        tmpfile.close()

        hdul2 = pyfits.open('tmpfile.fits')

        try:
            self.assertEqual(hdul2.info(output=False), info)
        finally:
            os.remove('tmpfile.fits')

        tmpfile = open('tmpfile.fits', 'w')
        pyfits.writeto(tmpfile, np.arange(100, dtype=np.int32))
        tmpfile.close()

        try:
            self.assertEqual(pyfits.info('tmpfile.fits', output=False), info)
        finally:
            os.remove('tmpfile.fits')

    def testNewHDUExtname(self):
        """
        Tests that new extension HDUs that are added to an HDUList can be
        properly indexed by their EXTNAME/EXTVER (regression test for
        ticket:48).
        """

        f = pyfits.open(os.path.join(data_dir, 'test0.fits'))
        hdul = pyfits.HDUList()
        hdul.append(f[0].copy())
        hdul.append(pyfits.ImageHDU(header=f[1].header))

        self.assertEqual(hdul[1].header['EXTNAME'], 'SCI')
        self.assertEqual(hdul[1].header['EXTVER'], 1)
        self.assertEqual(hdul.index_of(('SCI', 1)), 1)

if __name__ == '__main__':
    unittest.main()

