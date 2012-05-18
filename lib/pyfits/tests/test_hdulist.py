from __future__ import division, with_statement  # confidence high

import glob
import os

import numpy as np

import pyfits
from pyfits.util import BytesIO
from pyfits.verify import VerifyError
from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import catch_warnings, ignore_warnings

from nose.tools import assert_equal, assert_raises, assert_true


class TestHDUListFunctions(PyfitsTestCase):
    def test_update_name(self):
        hdul = pyfits.open(self.data('o4sp040b0_raw.fits'))
        hdul[4].update_ext_name('Jim', "added by Jim")
        hdul[4].update_ext_version(9, "added by Jim")
        assert_equal(hdul[('JIM', 9)].header['extname'], 'JIM')

    def test_hdu_file_bytes(self):
        hdul = pyfits.open(self.data('checksum.fits'))
        res = hdul[0].filebytes()
        assert_equal(res, 11520)
        res = hdul[1].filebytes()
        assert_equal(res, 8640)

    def test_hdulist_file_info(self):
        hdul = pyfits.open(self.data('checksum.fits'))
        res = hdul.fileinfo(0)

        def test_fileinfo(**kwargs):
            assert_equal(res['datSpan'], kwargs.get('datSpan', 2880))
            assert_equal(res['resized'], kwargs.get('resized', False))
            assert_equal(res['filename'], self.data('checksum.fits'))
            assert_equal(res['datLoc'], kwargs.get('datLoc', 8640))
            assert_equal(res['hdrLoc'], kwargs.get('hdrLoc', 0))
            assert_equal(res['filemode'], 'readonly')

        res = hdul.fileinfo(1)
        test_fileinfo(datLoc=17280, hdrLoc=11520)

        hdu = pyfits.ImageHDU(data=hdul[0].data)
        hdul.insert(1, hdu)

        res = hdul.fileinfo(0)
        test_fileinfo(resized=True)

        res = hdul.fileinfo(1)
        test_fileinfo(datSpan=None, resized=True, datLoc=None, hdrLoc=None)

        res = hdul.fileinfo(2)
        test_fileinfo(resized=1, datLoc=17280, hdrLoc=11520)

    def test_create_from_multiple_primary(self):
        """
        Regression test for #145.  Ensure that a validation error occurs when
        saving an HDUList containing multiple PrimaryHDUs.
        """

        hdul = pyfits.HDUList([pyfits.PrimaryHDU(), pyfits.PrimaryHDU()])
        assert_raises(VerifyError, hdul.writeto, self.temp('temp.fits'),
                      output_verify='exception')

    def test_append_primary_to_empty_list(self):
        # Tests appending a Simple PrimaryHDU to an empty HDUList.
        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]
        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-append.fits'))

        assert_equal(pyfits.info(self.temp('test-append.fits'), output=False),
                     info)

    def test_append_extension_to_empty_list(self):
        """Tests appending a Simple ImageHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (100,), 'int32', '')]
        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-append.fits'))

        assert_equal(pyfits.info(self.temp('test-append.fits'), output=False),
                     info)

    def test_append_table_extension_to_empty_list(self):
        """Tests appending a Simple Table ExtensionHDU to a empty HDUList."""

        hdul = pyfits.HDUList()
        hdul1 = pyfits.open(self.data('tb.fits'))
        hdul.append(hdul1[1])
        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (), 'uint8', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-append.fits'))

        assert_equal(pyfits.info(self.temp('test-append.fits'), output=False),
                     info)

    def test_append_groupshdu_to_empty_list(self):
        """Tests appending a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.append(hdu)

        info = [(0, 'PRIMARY', 'GroupsHDU', 8, (), 'uint8',
                 '1 Groups  0 Parameters')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-append.fits'))

        assert_equal(pyfits.info(self.temp('test-append.fits'), output=False),
                     info)

    def test_append_primary_to_non_empty_list(self):
        """Tests appending a Simple PrimaryHDU to a non-empty HDUList."""

        hdul = pyfits.open(self.data('arange.fits'))
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 7, (11, 10, 7), 'int32', ''),
                (1, '', 'ImageHDU', 6, (100,), 'int32', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-append.fits'))

        assert_equal(pyfits.info(self.temp('test-append.fits'), output=False),
                     info)

    def test_append_extension_to_non_empty_list(self):
        """Tests appending a Simple ExtensionHDU to a non-empty HDUList."""

        hdul = pyfits.open(self.data('tb.fits'))
        hdul.append(hdul[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 11, (), 'int16', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', ''),
                (2, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-append.fits'))

        assert_equal(pyfits.info(self.temp('test-append.fits'), output=False),
                     info)

    def test_append_groupshdu_to_non_empty_list(self):
        """Tests appending a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.append(hdu)
        hdu = pyfits.GroupsHDU()

        assert_raises(ValueError, hdul.append, hdu)

    def test_insert_primary_to_empty_list(self):
        """Tests inserting a Simple PrimaryHDU to an empty HDUList."""
        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_extension_to_empty_list(self):
        """Tests inserting a Simple ImageHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (100,), 'int32', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_table_extension_to_empty_list(self):
        """Tests inserting a Simple Table ExtensionHDU to a empty HDUList."""

        hdul = pyfits.HDUList()
        hdul1 = pyfits.open(self.data('tb.fits'))
        hdul.insert(0, hdul1[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (), 'uint8', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_groupshdu_to_empty_list(self):
        """Tests inserting a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'GroupsHDU', 8, (), 'uint8',
                 '1 Groups  0 Parameters')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_primary_to_non_empty_list(self):
        """Tests inserting a Simple PrimaryHDU to a non-empty HDUList."""

        hdul = pyfits.open(self.data('arange.fits'))
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(1, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 7, (11, 10, 7), 'int32', ''),
                (1, '', 'ImageHDU', 6, (100,), 'int32', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_extension_to_non_empty_list(self):
        """Tests inserting a Simple ExtensionHDU to a non-empty HDUList."""

        hdul = pyfits.open(self.data('tb.fits'))
        hdul.insert(1, hdul[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 11, (), 'int16', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', ''),
                (2, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_groupshdu_to_non_empty_list(self):
        """Tests inserting a Simple GroupsHDU to an empty HDUList."""

        hdul = pyfits.HDUList()
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)
        hdu = pyfits.GroupsHDU()

        assert_raises(ValueError, hdul.insert, 1, hdu)

        info = [(0, 'PRIMARY', 'GroupsHDU', 8, (), 'uint8',
                 '1 Groups  0 Parameters'),
                (1, '', 'ImageHDU', 6, (100,), 'int32', '')]

        hdul.insert(0, hdu)

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_groupshdu_to_begin_of_hdulist_with_groupshdu(self):
        """
        Tests inserting a Simple GroupsHDU to the beginning of an HDUList
        that that already contains a GroupsHDU.
        """

        hdul = pyfits.HDUList()
        hdu = pyfits.GroupsHDU()
        hdul.insert(0, hdu)

        assert_raises(ValueError, hdul.insert, 0, hdu)

    def test_insert_extension_to_primary_in_non_empty_list(self):
        # Tests inserting a Simple ExtensionHDU to a non-empty HDUList.
        hdul = pyfits.open(self.data('tb.fits'))
        hdul.insert(0, hdul[1])

        info = [(0, 'PRIMARY', 'PrimaryHDU', 4, (), 'uint8', ''),
                (1, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', ''),
                (2, '', 'ImageHDU', 12, (), 'uint8', ''),
                (3, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_insert_image_extension_to_primary_in_non_empty_list(self):
        """
        Tests inserting a Simple Image ExtensionHDU to a non-empty HDUList
        as the primary HDU.
        """

        hdul = pyfits.open(self.data('tb.fits'))
        hdu = pyfits.ImageHDU(np.arange(100, dtype=np.int32))
        hdul.insert(0, hdu)

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', ''),
                (1, '', 'ImageHDU', 12, (), 'uint8', ''),
                (2, '', 'BinTableHDU', 24, '2R x 4C', '[1J, 3A, 1E, 1L]', '')]

        assert_equal(hdul.info(output=False), info)

        hdul.writeto(self.temp('test-insert.fits'))

        assert_equal(pyfits.info(self.temp('test-insert.fits'), output=False),
                     info)

    def test_filename(self):
        """Tests the HDUList filename method."""

        hdul = pyfits.open(self.data('tb.fits'))
        name = hdul.filename()
        assert_equal(name, self.data('tb.fits'))

    def test_file_like(self):
        """
        Tests the use of a file like object with no tell or seek methods
        in HDUList.writeto(), HDULIST.flush() or pyfits.writeto()
        """

        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        hdul = pyfits.HDUList()
        hdul.append(hdu)
        tmpfile = open(self.temp('tmpfile.fits'), 'wb')
        hdul.writeto(tmpfile)
        tmpfile.close()

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]

        assert_equal(pyfits.info(self.temp('tmpfile.fits'), output=False),
                     info)

    def test_file_like_2(self):
        hdu = pyfits.PrimaryHDU(np.arange(100, dtype=np.int32))
        tmpfile = open(self.temp('tmpfile.fits'), 'wb')
        hdul = pyfits.open(tmpfile, mode='ostream')
        hdul.append(hdu)
        hdul.flush()
        tmpfile.close()
        hdul.close()

        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]
        assert_equal(pyfits.info(self.temp('tmpfile.fits'), output=False),
                     info)

    def test_file_like_3(self):

        tmpfile = open(self.temp('tmpfile.fits'), 'wb')
        pyfits.writeto(tmpfile, np.arange(100, dtype=np.int32))
        tmpfile.close()
        info = [(0, 'PRIMARY', 'PrimaryHDU', 5, (100,), 'int32', '')]
        assert_equal(pyfits.info(self.temp('tmpfile.fits'), output=False),
                     info)

    def test_new_hdu_extname(self):
        """
        Tests that new extension HDUs that are added to an HDUList can be
        properly indexed by their EXTNAME/EXTVER (regression test for
        ticket:48).
        """

        f = pyfits.open(self.data('test0.fits'))
        hdul = pyfits.HDUList()
        hdul.append(f[0].copy())
        hdul.append(pyfits.ImageHDU(header=f[1].header))

        assert_equal(hdul[1].header['EXTNAME'], 'SCI')
        assert_equal(hdul[1].header['EXTVER'], 1)
        assert_equal(hdul.index_of(('SCI', 1)), 1)

    def test_update_filelike(self):
        """Test opening a file-like object in update mode and resizing the
        HDU.
        """

        sf = BytesIO()
        arr = np.zeros((100, 100))
        hdu = pyfits.PrimaryHDU(data=arr)
        hdu.writeto(sf)

        sf.seek(0)
        arr = np.zeros((200, 200))
        hdul = pyfits.open(sf, mode='update')
        hdul[0].data = arr
        hdul.flush()

        sf.seek(0)
        hdul = pyfits.open(sf)
        assert_equal(len(hdul), 1)
        assert_true((hdul[0].data == arr).all())

    def test_flush_readonly(self):
        """Test flushing changes to a file opened in a read only mode."""

        oldmtime = os.stat(self.data('test0.fits')).st_mtime
        hdul = pyfits.open(self.data('test0.fits'))
        hdul[0].header['FOO'] = 'BAR'
        with catch_warnings(record=True) as w:
            hdul.flush()
            assert_equal(len(w), 1)
            assert_true('mode is not supported' in str(w[0].message))
        assert_equal(oldmtime, os.stat(self.data('test0.fits')).st_mtime)

    def test_fix_extend_keyword(self):
        hdul = pyfits.HDUList()
        hdul.append(pyfits.PrimaryHDU())
        hdul.append(pyfits.ImageHDU())
        del hdul[0].header['EXTEND']
        hdul.verify('silentfix')

        assert_true('EXTEND' in hdul[0].header)
        assert_equal(hdul[0].header['EXTEND'], True)

    def test_new_hdulist_extend_keyword(self):
        """
        Tests that adding a PrimaryHDU to a new HDUList object updates the
        EXTEND keyword on that HDU.  Regression test for #114.
        """

        h0 = pyfits.Header()
        hdu = pyfits.PrimaryHDU(header=h0)
        sci = pyfits.ImageHDU(data=np.array(10))
        image = pyfits.HDUList([hdu, sci])
        image.writeto(self.temp('temp.fits'))
        assert_true('EXTEND' in hdu.header)
        assert_equal(hdu.header['EXTEND'], True)

    def test_replace_memmaped_array(self):
        # Copy the original before we modify it
        hdul = pyfits.open(self.data('test0.fits'))
        hdul.writeto(self.temp('temp.fits'))

        hdul = pyfits.open(self.temp('temp.fits'), mode='update', memmap=True)
        old_data = hdul[1].data.copy()
        hdul[1].data = hdul[1].data + 1
        hdul.close()
        hdul = pyfits.open(self.temp('temp.fits'), memmap=True)
        assert_true(((old_data + 1) == hdul[1].data).all())

    def test_open_file_with_end_padding(self):
        """Regression test for #106; open files with end padding bytes."""

        hdul = pyfits.open(self.data('test0.fits'),
                           do_not_scale_image_data=True)
        info = hdul.info(output=False)
        hdul.writeto(self.temp('temp.fits'))
        with open(self.temp('temp.fits'), 'ab') as f:
            f.seek(0, os.SEEK_END)
            f.write('\0'.encode('latin1') * 2880)
        with ignore_warnings():
            assert_equal(info,
                         pyfits.info(self.temp('temp.fits'), output=False,
                                     do_not_scale_image_data=True))

    def test_open_file_with_bad_header_padding(self):
        """
        Regression test for #136; open files with nulls for header block
        padding instead of spaces.
        """

        a = np.arange(100).reshape((10, 10))
        hdu = pyfits.PrimaryHDU(data=a)
        hdu.writeto(self.temp('temp.fits'))

        # Figure out where the header padding begins and fill it with nulls
        end_card_pos = str(hdu.header).index('END' + ' ' * 77)
        padding_start = end_card_pos + 80
        padding_len = 2880 - padding_start
        with open(self.temp('temp.fits'), 'r+b') as f:
            f.seek(padding_start)
            f.write('\0'.encode('ascii') * padding_len)

        with catch_warnings(record=True) as w:
            with pyfits.open(self.temp('temp.fits')) as hdul:
                assert_true('contains null bytes instead of spaces' in
                            str(w[0].message))
                assert_equal(len(w), 1)
                assert_equal(len(hdul), 1)
                assert_equal(str(hdul[0].header), str(hdu.header))
                assert_true((hdul[0].data == a).all())

    def test_update_with_truncated_header(self):
        """
        Regression test for #148.  Test that saving an update where the header
        is shorter than the original header doesn't leave a stump from the old
        header in the file.
        """

        data = np.arange(100)
        hdu = pyfits.PrimaryHDU(data=data)
        idx = 1
        while len(hdu.header) < 34:
            hdu.header['TEST%d' % idx] = idx
            idx += 1
        hdu.writeto(self.temp('temp.fits'), checksum=True)

        with pyfits.open(self.temp('temp.fits'), mode='update') as hdul:
            # Modify the header, forcing it to be rewritten
            hdul[0].header['TEST1'] = 2

        with pyfits.open(self.temp('temp.fits')) as hdul:
            assert_true((hdul[0].data == data).all())

    def test_update_resized_header(self):
        """
        Test saving updates to a file where the header is one block smaller
        than before, and in the case where the heade ris one block larger than
        before.
        """

        data = np.arange(100)
        hdu = pyfits.PrimaryHDU(data=data)
        idx = 1
        while len(str(hdu.header)) <= 2880:
            hdu.header['TEST%d' % idx] = idx
            idx += 1
        orig_header = hdu.header.copy()
        hdu.writeto(self.temp('temp.fits'))

        with pyfits.open(self.temp('temp.fits'), mode='update') as hdul:
            while len(str(hdul[0].header)) > 2880:
                del hdul[0].header[-1]

        with pyfits.open(self.temp('temp.fits')) as hdul:
            assert_equal(hdul[0].header, orig_header[:-1])
            assert_true((hdul[0].data == data).all())

        with pyfits.open(self.temp('temp.fits'), mode='update') as hdul:
            idx = 101
            while len(str(hdul[0].header)) <= 2880 * 2:
                hdul[0].header['TEST%d' % idx] = idx
                idx += 1
            # Touch something in the data too so that it has to be rewritten
            hdul[0].data[0] = 27

        with pyfits.open(self.temp('temp.fits')) as hdul:
            assert_equal(hdul[0].header[:-37], orig_header[:-1])
            assert_equal(hdul[0].data[0], 27)
            assert_true((hdul[0].data[1:] == data[1:]).all())

    def test_update_resized_header2(self):
        """
        Regression test for #150.  This is similar to
        test_update_resized_header, but specifically tests a case of multiple
        consecutive flush() calls on the same HDUList object, where each
        flush() requires a resize.
        """

        data1 = np.arange(100)
        data2 = np.arange(100) + 100
        phdu = pyfits.PrimaryHDU(data=data1)
        hdu = pyfits.ImageHDU(data=data2)

        phdu.writeto(self.temp('temp.fits'))

        with pyfits.open(self.temp('temp.fits'), mode='append') as hdul:
            hdul.append(hdu)

        with pyfits.open(self.temp('temp.fits'), mode='update') as hdul:
            idx = 1
            while len(str(hdul[0].header)) <= 2880 * 2:
                hdul[0].header['TEST%d' % idx] = idx
                idx += 1
            hdul.flush()
            hdul.append(hdu)

        with pyfits.open(self.temp('temp.fits')) as hdul:
            assert_true((hdul[0].data == data1).all())
            assert_equal(hdul[1].header, hdu.header)
            assert_true((hdul[1].data == data2).all())
            assert_true((hdul[2].data == data2).all())

    def test_hdul_fromstring(self):
        """
        Test creating the HDUList structure in memory from a string containing
        an entire FITS file.  This is similar to test_hdu_fromstring but for an
        entire multi-extension FITS file at once.
        """

        # Tests HDUList.fromstring for all of PyFITS' built in test files
        def test_fromstring(filename):
            with pyfits.open(self.data(filename)) as hdul:
                orig_info = hdul.info(output=False)
                with open(self.data(filename), 'rb') as f:
                    dat = f.read()

                hdul2 = pyfits.HDUList.fromstring(dat)

                assert_equal(orig_info, hdul2.info(output=False))
                for idx in range(len(hdul)):
                    assert_equal(hdul[idx].header, hdul2[idx].header)
                    if  hdul[idx].data is None or hdul2[idx].data is None:
                        assert_equal(hdul[idx].data, hdul2[idx].data)
                    else:
                        assert_true((hdul[idx].data == hdul2[idx].data).all())

        for filename in glob.glob(os.path.join(self.data_dir, '*.fits')):
            test_fromstring(os.path.join(self.data_dir, filename))

        # Test that creating an HDUList from something silly raises a TypeError
        assert_raises(TypeError, pyfits.HDUList.fromstring, ['a', 'b', 'c'])
