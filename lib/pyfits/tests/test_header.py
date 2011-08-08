from __future__ import division # confidence high

import warnings

import pyfits

from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import CaptureStdout, catch_warnings

from nose.tools import assert_equal, assert_raises, assert_true


class TestHeaderFunctions(PyfitsTestCase):
    """Test PyFITS Header and Card objects."""

    def test_card_constructor_default_args(self):
        """Test the constructor with default argument values."""

        c = pyfits.Card()
        assert_equal('', c.key)

    def test_fromstring_set_attribute_ascardimage(self):
        """Test fromstring() which will return a new card."""

        c = pyfits.Card('abc', 99).fromstring('xyz     = 100')
        assert_equal(100, c.value)

        # test set attribute and  ascardimage() using the most updated attributes
        c.value = 200
        assert_equal(c.ascardimage(),
                     "XYZ     =                  200                                                  ")

    def test_string_value_card(self):
        """Test string value"""

        c = pyfits.Card('abc', '<8 ch')
        assert_equal(str(c), 
                     "ABC     = '<8 ch   '                                                            ")
        c = pyfits.Card('nullstr', '')
        assert_equal(str(c),
                     "NULLSTR = ''                                                                    ")

    def test_boolean_value_card(self):
        """Boolean value card"""

        c = pyfits.Card("abc", True)
        assert_equal(str(c),
                     "ABC     =                    T                                                  ")

        c = pyfits.Card.fromstring('abc     = F')
        assert_equal(c.value, False)

    def test_long_integer_value_card(self):
        """long integer number"""

        c = pyfits.Card('long_int', -467374636747637647347374734737437)
        assert_equal(str(c),
                     "LONG_INT= -467374636747637647347374734737437                                    ")

    def test_floating_point_value_card(self):
        """ floating point number"""

        c = pyfits.Card('floatnum', -467374636747637647347374734737437.)

        if (str(c) != "FLOATNUM= -4.6737463674763E+32                                                  " and 
            str(c) != "FLOATNUM= -4.6737463674763E+032                                                 "):
            assert_equal(str(c),
                         "FLOATNUM= -4.6737463674763E+32                                                  ")

    def test_complex_value_card(self):
        """complex value"""

        c = pyfits.Card('abc',
                        1.2345377437887837487e88+6324767364763746367e-33j)

        if (str(c) != "ABC     = (1.23453774378878E+88, 6.32476736476374E-15)                          " and
            str(c) != "ABC     = (1.2345377437887E+088, 6.3247673647637E-015)                          "):
            assert_equal(str(c),
                         "ABC     = (1.23453774378878E+88, 6.32476736476374E-15)                          ")

    def test_card_image_constructed_too_long(self):
        with CaptureStdout():
            # card image constructed from key/value/comment is too long
            # (non-string value)
            c = pyfits.Card('abc', 9, 'abcde'*20)
            assert_equal(str(c),
                         "ABC     =                    9 / abcdeabcdeabcdeabcdeabcdeabcdeabcdeabcdeabcdeab")
            c = pyfits.Card('abc', 'a'*68, 'abcdefg')
            assert_equal(str(c),
                         "ABC     = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'")

    def test_constructor_filter_illegal_data_structures(self):
        # the constrctor will filter out illegal data structures...
        assert_raises(ValueError, pyfits.Card, ('abc',), {'value': (2, 3)})
        assert_raises(ValueError, pyfits.Card, 'key', [], 'comment')

    def test_keyword_too_long(self):
        """Long keywords should be allowed, but a warning should be issued."""
        with catch_warnings():
            warnings.simplefilter('error')
            assert_raises(UserWarning, pyfits.Card, 'abcdefghi', 'long')


    def test_illegal_characters_in_key(self):
        # will not allow illegal characters in key when using constructor
        assert_raises(ValueError, pyfits.Card, 'abc+', 9)


    def test_ascardiage_verifies_the_comment_string_to_be_ascii_text(self):
        # the ascardimage() verifies the comment string to be ASCII text
        c = pyfits.Card.fromstring('abc     = +  2.1   e + 12 / abcde\0')
        assert_raises(Exception, c.ascardimage)

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
        assert_equal(str(c.ascardimage()),
                     "HISTORY  (1, 2)                                                                 ")

    def test_equal_sign_after_column8(self):
        # equal sign after column 8 of a commentary card will be part ofthe string value
        c = pyfits.Card.fromstring("history =   (1, 2)")
        assert_equal(str(c.ascardimage()),
                     "HISTORY =   (1, 2)                                                              ")

    def test_specify_undefined_value(self):
        # this is how to specify an undefined value
        c = pyfits.Card("undef", pyfits.card.UNDEFINED)
        assert_equal(str(c),
                     "UNDEF   =                                                                       ")

    def test_complex_number_using_string_input(self):
        # complex number using string input
        c = pyfits.Card.fromstring('abc     = (8, 9)')
        assert_equal(str(c.ascardimage()),
                     "ABC     =               (8, 9)                                                  ")

    def test_fixable_non_standard_fits_card(self):
        # fixable non-standard FITS card will keep the original format
        c = pyfits.Card.fromstring('abc     = +  2.1   e + 12')
        assert_equal(c.value,2100000000000.0)
        assert_equal(str(c.ascardimage()),
                     "ABC     =             +2.1E+12                                                  ")

    def test_fixable_non_fsc(self):
        # fixable non-FSC: if the card is not parsable, it's value will be
        # assumed
        # to be a string and everything after the first slash will be comment
        c = pyfits.Card.fromstring("no_quote=  this card's value has no quotes / let's also try the comment")
        assert_equal(str(c.ascardimage()),
                     "NO_QUOTE= 'this card''s value has no quotes' / let's also try the comment       ")

    def test_undefined_value_using_string_input(self):
        # undefined value using string input
        c = pyfits.Card.fromstring('abc     =    ')
        assert_equal(str(c.ascardimage()),
                     "ABC     =                                                                       ")

    def test_misalocated_equal_sign(self):
        # test mislocated "=" sign
        c = pyfits.Card.fromstring('xyz= 100')
        assert_equal(c.key, 'xyz')
        assert_equal(c.value, 100)
        assert_equal(str(c.ascardimage()),
                     "XYZ     =                  100                                                  ")

    def test_equal_only_up_to_column_10(self):
        # the test of "=" location is only up to column 10
        c = pyfits.Card.fromstring("histo       =   (1, 2)")
        assert_equal(str(c.ascardimage()),
                     "HISTO   = '=   (1, 2)'                                                          ")
        c = pyfits.Card.fromstring("   history          (1, 2)")
        assert_equal(str(c.ascardimage()),
                     "HISTO   = 'ry          (1, 2)'                                                  ")

    def test_verify_invalid_equal_sign(self):
        # verification
        c = pyfits.Card.fromstring('abc= a6')
        with CaptureStdout() as f:
            c.verify()
            assert_true(f.getvalue().startswith(
                'Output verification result:\n  '
                'Card image is not FITS standard (equal sign not at column 8).\n'))

    def test_fix_invalid_equal_sign(self):
        c = pyfits.Card.fromstring('abc= a6')
        with CaptureStdout() as f:
            c.verify('fix')
            fix_text = 'Fixed card to meet the FITS standard: abc\n'
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
        hdu.header.ascard.append(c)
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
        assert_equal(str(c.ascardimage()),
            "ABC     = 'longstring''s testing  continue with long string but without the &'  "
            "CONTINUE  'ampersand at the endcontinue must have string value (with quotes)&'  "
            "CONTINUE  '&' / comments in line 1 comments with ''.                            ")

    def test_hierarch_card(self):
        c = pyfits.Card('hierarch abcdefghi', 10)
        assert_equal(str(c.ascardimage()),
            "HIERARCH abcdefghi = 10                                                         ")
        c = pyfits.Card('HIERARCH ESO INS SLIT2 Y1FRML', 'ENC=OFFSET+RESOL*acos((WID-(MAX+MIN))/(MAX-MIN)')
        assert_equal(str(c.ascardimage()),
            "HIERARCH ESO INS SLIT2 Y1FRML= 'ENC=OFFSET+RESOL*acos((WID-(MAX+MIN))/(MAX-MIN)'")

