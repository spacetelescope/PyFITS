from pyfits.diff import FitsDiff
from pyfits.hdu import HDUList, PrimaryHDU
from pyfits.header import Header
from pyfits.tests import PyfitsTestCase

from nose.tools import (assert_true, assert_false, assert_equal,
                        assert_not_equal)


class TestDiff(PyfitsTestCase):
    def test_identical_headers(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        diff = self._diff_from_headers(ha, hb)
        assert_true(diff.identical)

    def test_slightly_different_headers(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        hb['C'] = 4
        diff = self._diff_from_headers(ha, hb)
        assert_false(diff.identical)

    def test_common_keywords(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        hb['C'] = 4
        hb['D'] = (5, 'Comment')
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.common_keywords,
                     [['A', 'B', 'BITPIX', 'C', 'NAXIS', 'SIMPLE']])

    def test_different_keywords(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        hb['C'] = 4
        hb['D'] = (5, 'Comment')
        ha['E'] = (6, 'Comment')
        ha['F'] = (7, 'Comment')
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.left_only_keywords, [['E', 'F']])
        assert_equal(diff.right_only_keywords, [['D']])

    def test_different_keyword_values(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        hb['C'] = 4
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.different_keyword_values, [{'C': [(3, 4)]}])

    def test_different_keyword_comments(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3, 'comment 1')])
        hb = ha.copy()
        hb.comments['C'] = 'comment 2'
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.different_keyword_comments,
                     [{'C': [('comment 1', 'comment 2')]}])

    def test_different_keyword_values_with_duplicate(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        ha.append(('C', 4))
        hb.append(('C', 5))
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.different_keyword_values, [{'C': [None, (4, 5)]}])

    def test_asymmetric_duplicate_keywords(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        ha.append(('A', 2, 'comment 1'))
        ha.append(('A', 3, 'comment 2'))
        hb.append(('B', 4, 'comment 3'))
        hb.append(('C', 5, 'comment 4'))
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.different_keyword_values, [{}])
        assert_equal(diff.left_only_duplicate_keywords,
                     [{'A': [(2, 'comment 1'), (3, 'comment 2')]}])
        assert_equal(diff.right_only_duplicate_keywords,
                     [{'B': [(4, 'comment 3')], 'C': [(5, 'comment 4')]}])

    def test_floating_point_tolerance(self):
        ha = Header([('A', 1), ('B', 2.00001), ('C', 3.000001)])
        hb = ha.copy()
        hb['B'] = 2.00002
        hb['C'] = 3.000002
        diff = self._diff_from_headers(ha, hb)
        assert_equal(diff.different_keyword_values,
                [{'B': [(2.00001, 2.00002)], 'C': [(3.000001, 3.000002)]}])
        diff = self._diff_from_headers(ha, hb, tolerance=1e-6)
        assert_equal(diff.different_keyword_values,
                     [{'B': [(2.00001, 2.00002)]}])

    def test_ignore_blanks(self):
        ha = Header([('A', 1), ('B', 2), ('C', 'A       ')])
        hb = ha.copy()
        hb['C'] = 'A'
        assert_not_equal(ha['C'], hb['C'])
        diff = self._diff_from_headers(ha, hb)
        # Trailing blanks are ignored by default
        assert_true(diff.identical)
        assert_equal(diff.different_keyword_values, [{}])

        # Don't ignore blanks
        diff = self._diff_from_headers(ha, hb, ignore_blanks=False)
        assert_false(diff.identical)
        assert_equal(diff.different_keyword_values,
                     [{'C': [('A       ', 'A')]}])

    def test_ignore_keyword_values(self):
        ha = Header([('A', 1), ('B', 2), ('C', 3)])
        hb = ha.copy()
        hb['B'] = 4
        hb['C'] = 5
        diff = self._diff_from_headers(ha, hb, ignore_keywords=['*'])
        assert_true(diff.identical)
        diff = self._diff_from_headers(ha, hb, ignore_keywords=['B'])
        assert_false(diff.identical)
        assert_equal(diff.different_keyword_values, [{'C': [(3, 5)]}])

    def _diff_from_headers(self, ha, hb, **kwargs):
        a = HDUList([PrimaryHDU(header=ha)])
        b = HDUList([PrimaryHDU(header=hb)])
        return FitsDiff(a, b, **kwargs)
