from __future__ import division  # confidence high
from __future__ import with_statement

import numpy as np

import pyfits as fits
from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import catch_warnings


class TestDivisionFunctions(PyfitsTestCase):
    """Test code units that rely on correct integer division."""

    def test_rec_from_string(self):
        t1 = fits.open(self.data('tb.fits'))
        s = t1[1].data.tostring()
        a1 = np.rec.array(
            s,
            dtype=np.dtype([('c1', '>i4'), ('c2', '|S3'),
                         ('c3', '>f4'), ('c4', '|i1')]))

    def test_card_with_continue(self):
        h = fits.PrimaryHDU()
        with catch_warnings(record=True) as w:
            h.header['abc'] = 'abcdefg' * 20
            assert len(w) == 0

    def test_valid_hdu_size(self):
        t1 = fits.open(self.data('tb.fits'))
        assert type(t1[1].size) == type(1)

    def test_hdu_get_size(self):
        with catch_warnings(record=True) as w:
            t1 = fits.open(self.data('tb.fits'))
            assert len(w) == 0

    def test_section(self):
        # section testing
        fs = fits.open(self.data('arange.fits'))
        with catch_warnings(record=True) as w:
            assert np.all(fs[0].section[3, 2, 5] == np.array([357]))
            assert len(w) == 0
