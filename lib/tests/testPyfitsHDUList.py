from __future__ import division # confidence high
from __future__ import with_statement

import os
import sys
import unittest

import numpy as np

import pyfits
from pyfits.tests.util import CaptureStdout


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
        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

        hdul.writeto('testAppend.fits')

        with CaptureStdout() as f:
            pyfits.info('testAppend.fits')
            os.remove('testAppend.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testAppend.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

    def testAppendExtensionToEmptyList(self):
        """Tests appending a Simple ImageHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  (100,)        int32\n')

        hdul.writeto('testAppend.fits')

        with CaptureStdout() as f:
            pyfits.info('testAppend.fits')
            os.remove('testAppend.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testAppend.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  (100,)        int32\n')

    def testAppendTableExtensionToEmptyList(self):
        """Tests appending a Simple Table ExtensionHDU to a empty HDUList."""

        hdul = pyfits.HDUList()
        hdul1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.append(hdul1[1])

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  ()            \n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

        hdul.writeto('testAppend.fits')

        with CaptureStdout() as f:
            pyfits.info('testAppend.fits')
            os.remove('testAppend.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testAppend.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  ()            uint8\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

    def testAppendGroupsHDUToEmptyList(self):
        """Tests appending a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.append(hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    None        GroupsHDU        8  ()               1 Groups  0 Parameters\n')

        hdul.writeto('testAppend.fits')

        with CaptureStdout() as f:
            pyfits.info('testAppend.fits')
            os.remove('testAppend.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testAppend.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0                GroupsHDU        8  ()            uint8   1 Groups  0 Parameters\n')

    def testAppendPrimaryToNonEmptyList(self):
        """Tests appending a Simple PrimaryHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'arange.fits'))
        hdu = pyfits.PrimaryHDU(np.arange(100,dtype=np.int32))
        hdul.append(hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: %s\n' % os.path.join(data_dir, 'arange.fits') +
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       7  (11, 10, 7)   int32\n'
                '1    None        ImageHDU         6  (100,)        int32\n')

        hdul.writeto('testAppend.fits')

        with CaptureStdout() as f:
            pyfits.info('testAppend.fits')
            os.remove('testAppend.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testAppend.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       7  (11, 10, 7)   int32\n'
                '1                ImageHDU         6  (100,)        int32\n')

    def testAppendExtensionToNonEmptyList(self):
        """Tests appending a Simple ExtensionHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.append(hdul[1])

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: %s\n' % os.path.join(data_dir, 'tb.fits') +
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU      11  ()            int16\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n'
                '2                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

        hdul.writeto('testAppend.fits')

        with CaptureStdout() as f:
            pyfits.info('testAppend.fits')
            os.remove('testAppend.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testAppend.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU      11  ()            int16\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n'
                '2                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

    def testAppendGroupsHDUToNonEmptyList(self):
        """Tests appending a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        hdu = pyfits.GroupsHDU()

        try:
            hdul.append(hdu)
            x = "Did not fail as expected."
        except ValueError:
            x = "Failed as expected."
        self.assertEqual(x, "Failed as expected.")

    def testInsertPrimaryToEmptyList(self):
        """Tests inserting a Simple PrimaryHDU to an empty HDUList."""
        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

    def testInsertExtensionToEmptyList(self):
        """Tests inserting a Simple ImageHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.ImageHDU(np.arange(100,dtype=np.int32))
        hdul.insert(0, hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  (100,)        int32\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  (100,)        int32\n')

    def testInsertTableExtensionToEmptyList(self):
        """Tests inserting a Simple Table ExtensionHDU to a empty HDUList."""

        hdul = pyfits.HDUList()
        hdul1 = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.insert(0, hdul1[1])

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  ()            \n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  ()            uint8\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

    def testInsertGroupsHDUToEmptyList(self):
        """Tests inserting a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.insert(0, hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    None        GroupsHDU        8  ()               1 Groups  0 Parameters\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0                GroupsHDU        8  ()            uint8   1 Groups  0 Parameters\n')

    def testInsertPrimaryToNonEmptyList(self):
        """Tests inserting a Simple PrimaryHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'arange.fits'))
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(1, hdu)


        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: %s\n' % os.path.join(data_dir, 'arange.fits') +
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       7  (11, 10, 7)   int32\n'
                '1    None        ImageHDU         6  (100,)        int32\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       7  (11, 10, 7)   int32\n'
                '1                ImageHDU         6  (100,)        int32\n')

    def testInsertExtensionToNonEmptyList(self):
        """Tests inserting a Simple ExtensionHDU to a non-empty HDUList."""

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.insert(1, hdul[1])

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: %s\n' % os.path.join(data_dir, 'tb.fits') +
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU      11  ()            int16\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n'
                '2                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU      11  ()            int16\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n'
                '2                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

    def testInsertGroupsHDUToNonEmptyList(self):
        """Tests inserting a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)
        hdu = pyfits.GroupsHDU()

        try:
            hdul.insert(1,hdu)
            x = "Did not fail as expected."
        except ValueError:
            x = "Failed as expected."
        self.assertEqual(x, "Failed as expected.")

        hdul.insert(0, hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: (No file associated with this HDUList)\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    None        GroupsHDU        8  ()               1 Groups  0 Parameters\n'
                '1    None        ImageHDU         6  (100,)        int32\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0                GroupsHDU        8  ()            uint8   1 Groups  0 Parameters\n'
                '1                ImageHDU         6  (100,)        int32\n')

    def testInsertGroupsHDUToBeginOfHDUListWithGroupsHDUAlreadyThere(self):
        """
        Tests inserting a Simple GroupsHDU to the beginning of an HDUList
        that that already contains a GroupsHDU.
        """

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.insert(0, hdu)

        try:
            hdul.insert(0, hdu)
            x = "Did not fail as expected."
        except ValueError:
            x = "Failed as expected."
        self.assertEqual(x, "Failed as expected.")

    def testInsertExtensionToPrimaryInNonEmptyList(self):
        # Tests inserting a Simple ExtensionHDU to a non-empty HDUList.
        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdul.insert(0, hdul[1])

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: %s\n' % os.path.join(data_dir, 'tb.fits') +
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  ()            \n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n'
                '2    None        ImageHDU        12  ()            \n'
                '3                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4  ()            uint8\n'
                '1                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n'
                '2                ImageHDU        12  ()            uint8\n'
                '3                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

    def testInsertImageExtensionToPrimaryInNonEmptyList(self):
        """
        Tests inserting a Simple Image ExtensionHDU to a non-empty HDUList
        as the primary HDU.
        """

        hdul = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        with CaptureStdout() as f:
            hdul.info()
            self.assertEqual(f.getvalue(),
                'Filename: %s\n' % os.path.join(data_dir, 'tb.fits') +
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n'
                '1    None        ImageHDU        12  ()            \n'
                '2                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

        hdul.writeto('testInsert.fits')

        with CaptureStdout() as f:
            pyfits.info('testInsert.fits')
            os.remove('testInsert.fits')
            self.assertEqual(f.getvalue(),
                'Filename: testInsert.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n'
                '1                ImageHDU        12  ()            uint8\n'
                '2                BinTableHDU     24  2R x 4C       [1J, 3A, 1E, 1L]\n')

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
        sys.stdout = tmpfile
        hdul.writeto(sys.stdout)
        sys.stdout = sys.__stdout__
        tmpfile.close()

        hdul1 = pyfits.open('tmpfile.fits')

        with CaptureStdout() as f:
            pyfits.info('tmpfile.fits')
            os.remove('tmpfile.fits')
            self.assertEqual(f.getvalue(),
                'Filename: tmpfile.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        tmpfile = open('tmpfile.fits', 'w')
        sys.stdout = tmpfile
        hdul = pyfits.open(sys.stdout, mode='ostream')
        hdul.append(hdu)
        hdul.flush()
        sys.stdout = sys.__stdout__
        tmpfile.close()

        hdul2 = pyfits.open('tmpfile.fits')

        with CaptureStdout() as f:
            hdul2.info()
            os.remove('tmpfile.fits')
            self.assertEqual(f.getvalue(),
                'Filename: tmpfile.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

        tmpfile = open('tmpfile.fits', 'w')
        sys.stdout = tmpfile
        pyfits.writeto(sys.stdout, np.arange(100, dtype=np.int32))
        sys.stdout = sys.__stdout__
        tmpfile.close()
        hdul1 = pyfits.open('tmpfile.fits')

        with CaptureStdout() as f:
            pyfits.info('tmpfile.fits')
            os.remove('tmpfile.fits')
            self.assertEqual(f.getvalue(),
                'Filename: tmpfile.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       5  (100,)        int32\n')

if __name__ == '__main__':
    unittest.main()

