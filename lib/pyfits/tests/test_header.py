from __future__ import division # confidence high
from __future__ import with_statement

import warnings

import pyfits

from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import CaptureStdout, catch_warnings

from nose.tools import assert_equal, assert_false, assert_raises, assert_true


class TestOldApiHeaderFunctions(PyfitsTestCase):
    """
    Tests that specifically use attributes and methods from the old
    Header/CardList API from PyFITS 3.0 and prior.

    This tests backward compatibility support for those interfaces.
    """

    def test_ascardimage_verifies_the_comment_string_to_be_ascii_text(self):
        # the ascardimage() verifies the comment string to be ASCII text
        c = pyfits.Card.fromstring('abc     = +  2.1   e + 12 / abcde\0')
        assert_raises(Exception, c.ascardimage)

    def test_rename_key(self):
        """Test backwards compatibility support for Header.rename_key()"""
        header = pyfits.Header([('A', 'B', 'C'), ('D', 'E', 'F')])
        header.rename_key('A', 'B')
        assert_true('A' not in header)
        assert_true('B' in header)
        assert_equal(header[0], 'B')
        assert_equal(header['B'], 'B')
        assert_equal(header.comments['B'], 'C')


class TestHeaderFunctions(PyfitsTestCase):
    """Test PyFITS Header and Card objects."""

    def test_card_constructor_default_args(self):
        """Test Card constructor with default argument values."""

        c = pyfits.Card()
        assert_equal('', c.key)

    def test_string_value_card(self):
        """Test Card constructor with string value"""

        c = pyfits.Card('abc', '<8 ch')
        assert_equal(str(c),
                     "ABC     = '<8 ch   '                                                            ")
        c = pyfits.Card('nullstr', '')
        assert_equal(str(c),
                     "NULLSTR = ''                                                                    ")

    def test_boolean_value_card(self):
        """Test Card constructor with boolean value"""

        c = pyfits.Card("abc", True)
        assert_equal(str(c),
                     "ABC     =                    T                                                  ")

        c = pyfits.Card.fromstring('abc     = F')
        assert_equal(c.value, False)

    def test_long_integer_value_card(self):
        """Test Card constructor with long integer value"""

        c = pyfits.Card('long_int', -467374636747637647347374734737437)
        assert_equal(str(c),
                     "LONG_INT= -467374636747637647347374734737437                                    ")

    def test_floating_point_value_card(self):
        """Test Card constructor with floating point value"""

        c = pyfits.Card('floatnum', -467374636747637647347374734737437.)

        if (str(c) != "FLOATNUM= -4.6737463674763E+32                                                  " and
            str(c) != "FLOATNUM= -4.6737463674763E+032                                                 "):
            assert_equal(str(c),
                         "FLOATNUM= -4.6737463674763E+32                                                  ")

    def test_complex_value_card(self):
        """Test Card constructor with complex value"""

        c = pyfits.Card('abc',
                        1.2345377437887837487e88+6324767364763746367e-33j)

        if (str(c) != "ABC     = (1.23453774378878E+88, 6.32476736476374E-15)                          " and
            str(c) != "ABC     = (1.2345377437887E+088, 6.3247673647637E-015)                          "):
            assert_equal(str(c),
                         "ABC     = (1.23453774378878E+88, 6.32476736476374E-15)                          ")

    def test_card_image_constructed_too_long(self):
        """Test that over-long cards truncate the comment"""

        # card image constructed from key/value/comment is too long
        # (non-string value)
        c = pyfits.Card('abc', 9, 'abcde'*20)
        assert_equal(str(c),
                     "ABC     =                    9 / abcdeabcdeabcdeabcdeabcdeabcdeabcdeabcdeabcdeab")
        c = pyfits.Card('abc', 'a'*68, 'abcdefg')
        assert_equal(str(c),
                     "ABC     = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'")

    def test_constructor_filter_illegal_data_structures(self):
        """Test that Card constructor raises exceptions on bad arguments"""

        assert_raises(ValueError, pyfits.Card, ('abc',), {'value': (2, 3)})
        assert_raises(ValueError, pyfits.Card, 'key', [], 'comment')

    def test_keyword_too_long(self):
        """Test that long Card keywords are allowed, but with a warning"""

        with catch_warnings():
            warnings.simplefilter('error')
            assert_raises(UserWarning, pyfits.Card, 'abcdefghi', 'long')


    def test_illegal_characters_in_key(self):
        """
        Test that Card constructor disallows illegal characters in the keyword
        """

        assert_raises(ValueError, pyfits.Card, 'abc+', 9)

    def test_commentary_cards(self):
        # commentary cards
        c = pyfits.Card("history",
                        "A commentary card's value has no quotes around it.")
        assert_equal(str(c),
                     "HISTORY A commentary card's value has no quotes around it.                      ")
        c = pyfits.Card("comment",
                        "A commentary card has no comment.", "comment")
        assert_equal(str(c),
                     "COMMENT A commentary card has no comment.                                       ")

    def test_commentary_card_created_by_fromstring(self):
        # commentary card created by fromstring()
        c = pyfits.Card.fromstring("COMMENT card has no comments. / text after slash is still part of the value.")
        assert_equal(c.value,
                     'card has no comments. / text after slash is still part of the value.')
        assert_equal(c.comment, '')

    def test_commentary_card_will_not_parse_numerical_value(self):
        # commentary card will not parse the numerical value
        c = pyfits.Card.fromstring("history  (1, 2)")
        assert_equal(str(c),
                     "HISTORY  (1, 2)                                                                 ")

    def test_equal_sign_after_column8(self):
        # equal sign after column 8 of a commentary card will be part ofthe string value
        c = pyfits.Card.fromstring("history =   (1, 2)")
        assert_equal(str(c),
                     "HISTORY =   (1, 2)                                                              ")

    def test_specify_undefined_value(self):
        # this is how to specify an undefined value
        c = pyfits.Card("undef", pyfits.card.UNDEFINED)
        assert_equal(str(c),
                     "UNDEF   =                                                                       ")

    def test_complex_number_using_string_input(self):
        # complex number using string input
        c = pyfits.Card.fromstring('abc     = (8, 9)')
        assert_equal(str(c),
                     "ABC     =               (8, 9)                                                  ")

    def test_fixable_non_standard_fits_card(self):
        # fixable non-standard FITS card will keep the original format
        c = pyfits.Card.fromstring('abc     = +  2.1   e + 12')
        assert_equal(c.value,2100000000000.0)
        assert_equal(str(c),
                     "ABC     =             +2.1E+12                                                  ")

    def test_fixable_non_fsc(self):
        # fixable non-FSC: if the card is not parsable, it's value will be
        # assumed
        # to be a string and everything after the first slash will be comment
        c = pyfits.Card.fromstring("no_quote=  this card's value has no quotes / let's also try the comment")
        assert_equal(str(c),
                     "NO_QUOTE= 'this card''s value has no quotes' / let's also try the comment       ")

    def test_undefined_value_using_string_input(self):
        # undefined value using string input
        c = pyfits.Card.fromstring('abc     =    ')
        assert_equal(str(c),
                     "ABC     =                                                                       ")

    def test_misalocated_equal_sign(self):
        # test mislocated "=" sign
        c = pyfits.Card.fromstring('xyz= 100')
        assert_equal(c.keyword, 'XYZ')
        assert_equal(c.value, 100)
        assert_equal(str(c),
                     "XYZ     =                  100                                                  ")

    def test_equal_only_up_to_column_10(self):
        # the test of "=" location is only up to column 10
        c = pyfits.Card.fromstring("histo       =   (1, 2)")
        assert_equal(str(c),
                     "HISTO   = '=   (1, 2)'                                                          ")
        c = pyfits.Card.fromstring("   history          (1, 2)")
        assert_equal(str(c),
                     "HISTO   = 'ry          (1, 2)'                                                  ")

    def test_verify_invalid_equal_sign(self):
        # verification
        c = pyfits.Card.fromstring('abc= a6')
        with CaptureStdout() as f:
            c.verify()
            assert_true(
                'Card image is not FITS standard (equal sign not at column 8)'
                in f.getvalue())

    def test_fix_invalid_equal_sign(self):
        c = pyfits.Card.fromstring('abc= a6')
        with CaptureStdout() as f:
            c.verify('fix')
            fix_text = 'Fixed card to meet the FITS standard: ABC'
            assert_true(fix_text in f.getvalue())
        assert_equal(str(c),
                     "ABC     = 'a6      '                                                            ")

    def test_long_string_value(self):
        # test long string value
        c = pyfits.Card('abc', 'long string value '*10, 'long comment '*10)
        assert_equal(str(c),
            "ABC     = 'long string value long string value long string value long string &' "
            "CONTINUE  'value long string value long string value long string value long &'  "
            "CONTINUE  'string value long string value long string value &'                  "
            "CONTINUE  '&' / long comment long comment long comment long comment long        "
            "CONTINUE  '&' / comment long comment long comment long comment long comment     "
            "CONTINUE  '&' / long comment                                                    ")

    def test_long_string_from_file(self):
        c = pyfits.Card('abc', 'long string value '*10, 'long comment '*10)
        hdu = pyfits.PrimaryHDU()
        hdu.header.append(c)
        hdu.writeto(self.temp('test_new.fits'))

        hdul = pyfits.open(self.temp('test_new.fits'))
        c = hdul[0].header.ascard['abc']
        hdul.close()
        assert_equal(str(c),
            "ABC     = 'long string value long string value long string value long string &' "
            "CONTINUE  'value long string value long string value long string value long &'  "
            "CONTINUE  'string value long string value long string value &'                  "
            "CONTINUE  '&' / long comment long comment long comment long comment long        "
            "CONTINUE  '&' / comment long comment long comment long comment long comment     "
            "CONTINUE  '&' / long comment                                                    ")


    def test_word_in_long_string_too_long(self):
        # if a word in a long string is too long, it will be cut in the middle
        c = pyfits.Card('abc', 'longstringvalue'*10, 'longcomment'*10)
        assert_equal(str(c),
            "ABC     = 'longstringvaluelongstringvaluelongstringvaluelongstringvaluelongstr&'"
            "CONTINUE  'ingvaluelongstringvaluelongstringvaluelongstringvaluelongstringvalu&'"
            "CONTINUE  'elongstringvalue&'                                                   "
            "CONTINUE  '&' / longcommentlongcommentlongcommentlongcommentlongcommentlongcomme"
            "CONTINUE  '&' / ntlongcommentlongcommentlongcommentlongcomment                  ")

    def test_long_string_value_via_fromstring(self):
        # long string value via fromstring() method
        c = pyfits.Card.fromstring(
            pyfits.card._pad("abc     = 'longstring''s testing  &  ' / comments in line 1") +
            pyfits.card._pad("continue  'continue with long string but without the ampersand at the end' /") +
            pyfits.card._pad("continue  'continue must have string value (with quotes)' / comments with ''. "))
        assert_equal(str(c),
            "ABC     = 'longstring''s testing  continue with long string but without the &'  "
            "CONTINUE  'ampersand at the endcontinue must have string value (with quotes)&'  "
            "CONTINUE  '&' / comments in line 1 comments with ''.                            ")

    def test_hierarch_card(self):
        # Test automatic upgrade to hierarch card
        with catch_warnings(record=True) as w:
            c = pyfits.Card('ESO INS SLIT2 Y1FRML',
                            'ENC=OFFSET+RESOL*acos((WID-(MAX+MIN))/(MAX-MIN)')
            assert_equal(len(w), 1)
            assert_true('HIERARCH card will be created' in str(w[0].message))
            assert_equal(str(c),
                         "HIERARCH ESO INS SLIT2 Y1FRML= "
                         "'ENC=OFFSET+RESOL*acos((WID-(MAX+MIN))/(MAX-MIN)'")

        # Test manual creation of hierarch card
        c = pyfits.Card('hierarch abcdefghi', 10)
        assert_equal(str(c),
            "HIERARCH abcdefghi = "
            "10                                                         ")
        c = pyfits.Card('HIERARCH ESO INS SLIT2 Y1FRML',
                        'ENC=OFFSET+RESOL*acos((WID-(MAX+MIN))/(MAX-MIN)')
        assert_equal(str(c),
                     "HIERARCH ESO INS SLIT2 Y1FRML= "
                     "'ENC=OFFSET+RESOL*acos((WID-(MAX+MIN))/(MAX-MIN)'")

    def test_header_setitem_invalid(self):
        header = pyfits.Header()
        def test():
            header['FOO'] = ('bar', 'baz', 'qux')
        assert_raises(ValueError, test)

    def test_header_setitem_1tuple(self):
        header = pyfits.Header()
        header['FOO'] = ('BAR',)
        assert_equal(header['FOO'], 'BAR')
        assert_equal(header[0], 'BAR')
        assert_equal(header.comments[0], '')
        assert_equal(header.comments['FOO'], '')

    def test_header_setitem_2tuple(self):
        header = pyfits.Header()
        header['FOO'] = ('BAR', 'BAZ')
        assert_equal(header['FOO'], 'BAR')
        assert_equal(header[0], 'BAR')
        assert_equal(header.comments[0], 'BAZ')
        assert_equal(header.comments['FOO'], 'BAZ')

    def test_header_set_value_to_none(self):
        """
        Setting the value of a card to None should simply give that card a
        blank value.
        """

        header = pyfits.Header()
        header['FOO'] = 'BAR'
        assert_equal(header['FOO'], 'BAR')
        header['FOO'] = None
        assert_equal(header['FOO'], '')

    def test_header_iter(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        assert_equal(list(header), ['A', 'C'])

    def test_header_slice(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F')])
        newheader = header[1:]
        assert_equal(len(newheader), 2)
        assert_true('A' not in newheader)
        assert_true('C' in newheader)
        assert_true('E' in newheader)

        newheader = header[::-1]
        assert_equal(len(newheader), 3)
        assert_equal(newheader[0], 'F')
        assert_equal(newheader[1], 'D')
        assert_equal(newheader[2], 'B')

        newheader = header[::2]
        assert_equal(len(newheader), 2)
        assert_true('A' in newheader)
        assert_true('C' not in newheader)
        assert_true('E' in newheader)

    def test_header_slice_assignment(self):
        """
        Assigning to a slice should just assign new values to the cards
        included in the slice.
        """

        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F')])

        # Test assigning slice to the same value; this works similarly to numpy
        # arrays
        header[1:] = 1
        assert_equal(header[1], 1)
        assert_equal(header[2], 1)

        # Though strings are iterable they should be treated as a scalar value
        header[1:] = 'GH'
        assert_equal(header[1], 'GH')
        assert_equal(header[2], 'GH')

        # Now assign via an iterable
        header[1:] = ['H', 'I']
        assert_equal(header[1], 'H')
        assert_equal(header[2], 'I')

    def test_header_slice_delete(self):
        """Test deleting a slice of cards from the header."""

        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F')])
        del header[1:]
        assert_equal(len(header), 1)
        assert_equal(header[0], 'B')
        del header[:]
        assert_equal(len(header), 0)

    def test_wildcard_slice(self):
        """Test selecting a subsection of a header via wildcard matching."""

        header = pyfits.Header([('ABC', 0), ('DEF', 1), ('ABD', 2)])
        newheader = header['AB*']
        assert_equal(len(newheader), 2)
        assert_equal(newheader[0], 0)
        assert_equal(newheader[1], 2)

    def test_wildcard_slice_assignment(self):
        """Test assigning to a header slice selected via wildcard matching."""

        header = pyfits.Header([('ABC', 0), ('DEF', 1), ('ABD', 2)])

        # Test assigning slice to the same value; this works similarly to numpy
        # arrays
        header['AB*'] = 1
        assert_equal(header[0], 1)
        assert_equal(header[2], 1)

        # Though strings are iterable they should be treated as a scalar value
        header['AB*'] = 'GH'
        assert_equal(header[0], 'GH')
        assert_equal(header[2], 'GH')

        # Now assign via an iterable
        header['AB*'] = ['H', 'I']
        assert_equal(header[0], 'H')
        assert_equal(header[2], 'I')

    def test_wildcard_slice_deletion(self):
        """Test deleting cards from a header that match a wildcard pattern."""

        header = pyfits.Header([('ABC', 0), ('DEF', 1), ('ABD', 2)])
        del header['AB*']
        assert_equal(len(header), 1)
        assert_equal(header[0], 1)

    def test_header_clear(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        header.clear()
        assert_true('A' not in header)
        assert_true('C' not in header)
        assert_equal(len(header), 0)

    def test_header_fromkeys(self):
        header = pyfits.Header.fromkeys(['A', 'B'])
        assert_true('A' in header)
        assert_equal(header['A'], '')
        assert_equal(header.comments['A'], '')
        assert_true('B' in header)
        assert_equal(header['B'], '')
        assert_equal(header.comments['B'], '')

    def test_header_fromkeys_with_value(self):
        header = pyfits.Header.fromkeys(['A', 'B'], 'C')
        assert_true('A' in header)
        assert_equal(header['A'], 'C')
        assert_equal(header.comments['A'], '')
        assert_true('B' in header)
        assert_equal(header['B'], 'C')
        assert_equal(header.comments['B'], '')

    def test_header_fromkeys_with_value_and_comment(self):
        header = pyfits.Header.fromkeys(['A'], ('B', 'C'))
        assert_true('A' in header)
        assert_equal(header['A'], 'B')
        assert_equal(header.comments['A'], 'C')

    def test_header_fromkeys_with_duplicates(self):
        header = pyfits.Header.fromkeys(['A', 'B', 'A'], 'C')
        assert_true('A' in header)
        assert_true(('A', 0) in header)
        assert_true(('A', 1) in header)
        assert_true(('A', 2) not in header)
        assert_equal(header[0], 'C')
        assert_equal(header['A'], 'C')
        assert_equal(header[('A', 0)], 'C')
        assert_equal(header[2], 'C')
        assert_equal(header[('A', 1)], 'C')

    def test_header_keys(self):
        hdul = pyfits.open(self.data('arange.fits'))
        assert_equal(hdul[0].header.keys(),
                     ['SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2',
                      'NAXIS3', 'EXTEND'])

    def test_update_from_dict(self):
        """
        Test adding new cards and updating existing cards from a dict using
        Header.update()
        """

        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        header.update({'A': 'E', 'F': 'G'})
        assert_equal(header['A'], 'E')
        assert_equal(header[0], 'E')
        assert_true('F' in header)
        assert_equal(header['F'], 'G')
        assert_equal(header[-1], 'G')

    def test_header_append_use_blanks(self):
        """
        Tests that blank cards can be appended, and that future appends will
        use blank cards when available (unless useblanks=False)
        """

        header = pyfits.Header([('A', 'B'), ('C', 'D')])

        # Append a couple blanks
        header.append()
        header.append()
        assert_equal(len(header), 4)
        assert_equal(header[-1], '')
        assert_equal(header[-2], '')

        # New card should fill the first blank by default
        header.append(('E', 'F'))
        assert_equal(len(header), 4)
        assert_equal(header[-2], 'F')
        assert_equal(header[-1], '')

        # This card should not use up a blank spot
        header.append(('G', 'H'), useblanks=False)
        assert_equal(len(header), 5)
        assert_equal(header[-1], '')
        assert_equal(header[-2], 'H')

    def test_header_insert_use_blanks(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D')])

        # Append a couple blanks
        header.append()
        header.append()

        # Insert a new card; should use up one of the blanks
        header.insert(1, ('E', 'F'))
        assert_equal(len(header), 4)
        assert_equal(header[1], 'F')
        assert_equal(header[-1], '')
        assert_equal(header[-2], 'D')

        # Insert a new card without using blanks
        header.insert(1, ('G', 'H'), useblanks=False)
        assert_equal(len(header), 5)
        assert_equal(header[1], 'H')
        assert_equal(header[-1], '')

    def test_update_comment(self):
        hdul = pyfits.open(self.data('arange.fits'))
        hdul[0].header['FOO'] = ('BAR', 'BAZ')
        hdul.writeto(self.temp('test.fits'))

        hdul = pyfits.open(self.temp('test.fits'), mode='update')
        hdul[0].header.comments['FOO'] = 'QUX'
        hdul.close()

        hdul = pyfits.open(self.temp('test.fits'))
        assert_equal(hdul[0].header.comments['FOO'], 'QUX')


class TestRecordValuedKeywordCards(PyfitsTestCase):
    """
    Tests for handling of record-valued keyword cards as used by the FITS WCS
    Paper IV proposal.

    These tests are derived primarily from the release notes for PyFITS 1.4 (in
    which this feature was first introduced.
    """

    def setup(self):
        super(TestRecordValuedKeywordCards, self).setup()
        self._test_header = pyfits.Header()
        self._test_header.set('DP1', 'NAXIS: 2')
        self._test_header.set('DP1', 'AXIS.1: 1')
        self._test_header.set('DP1', 'AXIS.2: 2')
        self._test_header.set('DP1', 'NAUX: 2')
        self._test_header.set('DP1', 'AUX.1.COEFF.0: 0')
        self._test_header.set('DP1', 'AUX.1.POWER.0: 1')
        self._test_header.set('DP1', 'AUX.1.COEFF.1: 0.00048828125')
        self._test_header.set('DP1', 'AUX.1.POWER.1: 1')

    def test_initialize_rvkc(self):
        """
        Test different methods for initializing a card that should be
        recognized as a RVKC
        """

        c = pyfits.Card.fromstring("DP1     = 'NAXIS: 2' / A comment")
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.0)
        assert_equal(c.field_specifier, 'NAXIS')
        assert_equal(c.comment, 'A comment')

        c = pyfits.Card.fromstring("DP1     = 'NAXIS: 2.1'")
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.1)
        assert_equal(c.field_specifier, 'NAXIS')

        c = pyfits.Card.fromstring("DP1     = 'NAXIS: a'")
        assert_equal(c.keyword, 'DP1')
        assert_equal(c.value, 'NAXIS: a')
        assert_equal(c.field_specifier, None)

        c = pyfits.Card('DP1', 'NAXIS: 2')
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.0)
        assert_equal(c.field_specifier, 'NAXIS')

        c = pyfits.Card('DP1', 'NAXIS: 2.0')
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.0)
        assert_equal(c.field_specifier, 'NAXIS')

        c = pyfits.Card('DP1', 'NAXIS: a')
        assert_equal(c.keyword, 'DP1')
        assert_equal(c.value, 'NAXIS: a')
        assert_equal(c.field_specifier, None)

        c = pyfits.Card('DP1.NAXIS', 2)
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.0)
        assert_equal(c.field_specifier, 'NAXIS')

        c = pyfits.Card('DP1.NAXIS', 2.0)
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.0)
        assert_equal(c.field_specifier, 'NAXIS')

        c = pyfits.Card('DP1.NAXIS', 'a')
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 'a')
        assert_equal(c.field_specifier, None)

    def test_field_specifier_case_senstivity(self):
        """
        The keyword portion of an RVKC should still be case-insensitive, but
        the field-specifier portion should be case-sensitive.
        """

        header = pyfits.Header()
        header.set('abc.def', 1)
        header.set('abc.DEF', 2)
        assert_equal(header['abc.def'], 1)
        assert_equal(header['ABC.def'], 1)
        assert_equal(header['aBc.def'], 1)
        assert_equal(header['ABC.DEF'], 2)
        assert_false('ABC.dEf' in header)

    def test_get_rvkc_by_index(self):
        """
        Returning a RVKC from a header via index lookup should return the
        float value of the card.
        """

        assert_equal(self._test_header[0], 2.0)
        assert_true(isinstance(self._test_header[0], float))
        assert_equal(self._test_header[1], 1.0)
        assert_true(isinstance(self._test_header[1], float))

    def test_get_rvkc_by_keyword(self):
        """
        Returning a RVKC just via the keyword name should return the floating
        point value of the first card with that keyword.
        """

        assert_equal(self._test_header['DP1'], 2.0)

    def test_get_rvkc_by_keyword_and_field_specifier(self):
        """
        Returning a RVKC via the full keyword/field-specifier combination
        should return the floating point value associated with the RVKC.
        """

        assert_equal(self._test_header['DP1.NAXIS'], 2.0)
        assert_true(isinstance(self._test_header['DP1.NAXIS'], float))
        assert_equal(self._test_header['DP1.AUX.1.COEFF.1'], 0.00048828125)

    def test_access_nonexistent_rvkc(self):
        """
        Accessing a nonexistent RVKC should raise an IndexError for
        index-based lookup, or a KeyError for keyword lookup (like a normal
        card).
        """

        assert_raises(IndexError, lambda x: self._test_header[x], 8)
        assert_raises(KeyError, lambda k: self._test_header[k], 'DP1.AXIS.3')

    def test_update_rvkc(self):
        """A RVKC can be updated either via index or keyword access."""

        self._test_header[0] = 3
        assert_equal(self._test_header['DP1.NAXIS'], 3.0)
        assert_true(isinstance(self._test_header['DP1.NAXIS'], float))

        self._test_header['DP1.AXIS.1'] = 1.1
        assert_equal(self._test_header['DP1.AXIS.1'], 1.1)

    def test_rvkc_insert_after(self):
        """
        It should be possible to insert a new RVKC after an existing one
        specified by the full keyword/field-specifier combination."""

        self._test_header.set('DP1', 'AXIS.3: 1', 'a comment',
                              after='DP1.AXIS.2')
        assert_equal(self._test_header[3], 1)
        assert_equal(self._test_header['DP1.AXIS.3'], 1)

    def test_rvkc_delete(self):
        """
        Deleting a RVKC should work as with a normal card by using the full
        keyword/field-spcifier combination.
        """

        del self._test_header['DP1.AXIS.1']
        assert_equal(len(self._test_header), 7)
        assert_equal(self._test_header.keys()[0], 'DP1.NAXIS')
        assert_equal(self._test_header[0], 2)
        assert_equal(self._test_header.keys()[1], 'DP1.AXIS.2')
        assert_equal(self._test_header[1], 2)

    def test_pattern_matching_keys(self):
        """Test the keyword filter strings with RVKCs."""

        cl = self._test_header['DP1.AXIS.*']
        assert_true(isinstance(cl, pyfits.Header))
        assert_equal(
            [str(c).strip() for c in cl.cards],
            ["DP1     = 'AXIS.1: 1'",
             "DP1     = 'AXIS.2: 2'"])

        cl = self._test_header['DP1.N*']
        assert_equal(
            [str(c).strip() for c in cl.cards],
            ["DP1     = 'NAXIS: 2'",
             "DP1     = 'NAUX: 2'"])

        cl = self._test_header['DP1.AUX...']
        assert_equal(
            [str(c).strip() for c in cl.cards],
            ["DP1     = 'AUX.1.COEFF.0: 0'",
             "DP1     = 'AUX.1.POWER.0: 1'",
             "DP1     = 'AUX.1.COEFF.1: 0.00048828125'",
             "DP1     = 'AUX.1.POWER.1: 1'"])

        cl = self._test_header['DP?.NAXIS']
        assert_equal(
            [str(c).strip() for c in cl.cards],
            ["DP1     = 'NAXIS: 2'"])

        cl = self._test_header['DP1.A*S.*']
        assert_equal(
            [str(c).strip() for c in cl.cards],
            ["DP1     = 'AXIS.1: 1'",
             "DP1     = 'AXIS.2: 2'"])

    def test_pattern_matching_key_deletion(self):
        """Deletion by filter strings should work."""

        del self._test_header['DP1.A*...']
        assert_equal(len(self._test_header), 2)
        assert_equal(self._test_header.keys()[0], 'DP1.NAXIS')
        assert_equal(self._test_header[0], 2)
        assert_equal(self._test_header.keys()[1], 'DP1.NAUX')
        assert_equal(self._test_header[1], 2)

    def test_successive_pattern_matching(self):
        """
        A card list returned via a filter string should be further filterable.
        """

        cl = self._test_header['DP1.A*...']
        assert_equal(
            [str(c).strip() for c in cl.cards],
            ["DP1     = 'AXIS.1: 1'",
             "DP1     = 'AXIS.2: 2'",
             "DP1     = 'AUX.1.COEFF.0: 0'",
             "DP1     = 'AUX.1.POWER.0: 1'",
             "DP1     = 'AUX.1.COEFF.1: 0.00048828125'",
             "DP1     = 'AUX.1.POWER.1: 1'"])

        cl2 = cl['*.*AUX...']
        assert_equal(
            [str(c).strip() for c in cl2.cards],
            ["DP1     = 'AUX.1.COEFF.0: 0'",
             "DP1     = 'AUX.1.POWER.0: 1'",
             "DP1     = 'AUX.1.COEFF.1: 0.00048828125'",
             "DP1     = 'AUX.1.POWER.1: 1'"])

    def test_rvkc_in_cardlist_keys(self):
        """
        The CardList.keys() method should return full keyword/field-spec values
        for RVKCs.
        """

        cl = self._test_header['DP1.AXIS.*']
        assert_equal(cl.keys(), ['DP1.AXIS.1', 'DP1.AXIS.2'])

    def test_rvkc_in_cardlist_values(self):
        """
        The CardList.values() method should return the values of all RVKCs as
        floating point values.
        """

        cl = self._test_header['DP1.AXIS.*']
        assert_equal(cl.values(), [1.0, 2.0])

    def test_rvkc_value_attribute(self):
        """
        Individual card values should be accessible by the .value attribute
        (which should return a float).
        """

        cl = self._test_header['DP1.AXIS.*']
        assert_equal(cl.cards[0].value, 1.0)
        assert_true(isinstance(cl.cards[0].value, float))
