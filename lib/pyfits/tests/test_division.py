from __future__ import division # confidence high
from __future__ import with_statement

import numpy as np

import pyfits
from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import catch_warnings

from nose.tools import assert_equal


class TestDivisionFunctions(PyfitsTestCase):
    """Test code units that rely on correct integer division."""

    def test_rec_from_string(self):
        t1 = pyfits.open(self.data('tb.fits'))
        s = t1[1].data.tostring()
        a1 = np.rec.array(
                s,
                dtype=np.dtype([('c1', '>i4'), ('c2', '|S3'),
                                ('c3', '>f4'), ('c4', '|i1')]))

    def test_card_with_continue(self):
        h = pyfits.PrimaryHDU()
        with catch_warnings(record=True) as w:
            h.header['abc'] = 'abcdefg' * 20
            assert_equal(len(w), 0)

    def test_valid_hdu_size(self):
        t1 = pyfits.open(self.data('tb.fits'))
        assert_equal(type(t1[1].size), type(1))

    def test_hdu_get_size(self):
        with catch_warnings(record=True) as w:
            t1 = pyfits.open(self.data('tb.fits'))
            assert_equal(len(w), 0)

    def test_section(self):
        # section testing
        fs = pyfits.open(self.data('arange.fits'))
        with catch_warnings(record=True) as w:
            assert_equal(fs[0].section[3, 2, 5], np.array([357]))
            assert_equal(len(w), 0)
