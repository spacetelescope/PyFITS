from __future__ import division  # confidence high
from __future__ import with_statement

import itertools
import warnings

import numpy as np

import pyfits

from pyfits.card import _pad
from pyfits.tests import PyfitsTestCase
from pyfits.tests.util import catch_warnings, ignore_warnings, CaptureStdio

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

    def test_add_commentary(self):
        header = pyfits.Header([('A', 'B', 'C'), ('HISTORY', 1),
                                ('HISTORY', 2), ('HISTORY', 3), ('', '', ''),
                                ('', '', '')])
        header.add_history(4)
        # One of the blanks should get used, so the length shouldn't change
        assert_equal(len(header), 6)
        assert_equal(header.cards[4].value, 4)
        assert_equal(header['HISTORY'], [1, 2, 3, 4])

        header.add_history(0, after='A')
        assert_equal(len(header), 6)
        assert_equal(header.cards[1].value, 0)
        assert_equal(header['HISTORY'], [0, 1, 2, 3, 4])

        header = pyfits.Header([('A', 'B', 'C'), ('', 1), ('', 2), ('', 3),
                                ('', '', ''), ('', '', '')])
        header.add_blank(4)
        # This time a new blank should be added, and the existing blanks don't
        # get used... (though this is really kinda sketchy--there's a
        # distinction between truly blank cards, and cards with blank keywords
        # that isn't currently made int he code)
        assert_equal(len(header), 7)
        assert_equal(header.cards[6].value, 4)
        assert_equal(header[''], [1, 2, 3, '', '', 4])

        header.add_blank(0, after='A')
        assert_equal(len(header), 8)
        assert_equal(header.cards[1].value, 0)
        assert_equal(header[''], [0, 1, 2, 3, '', '', 4])

    def test_has_key(self):
        header = pyfits.Header([('A', 'B', 'C'), ('D', 'E', 'F')])
        assert_true(header.has_key('A'))
        assert_true(header.has_key('D'))
        assert_false(header.has_key('C'))

    def test_totxtfile(self):
        hdul = pyfits.open(self.data('test0.fits'))
        hdul[0].header.toTxtFile(self.temp('header.txt'))
        hdu = pyfits.ImageHDU()
        hdu.header.update('MYKEY', 'FOO', 'BAR')
        hdu.header.fromTxtFile(self.temp('header.txt'), replace=True)
        assert_equal(len(hdul[0].header.ascard), len(hdu.header.ascard))
        assert_false(hdu.header.has_key('MYKEY'))
        assert_false(hdu.header.has_key('EXTENSION'))
        assert_true(hdu.header.has_key('SIMPLE'))

        # Write the hdu out and read it back in again--it should be recognized
        # as a PrimaryHDU
        hdu.writeto(self.temp('test.fits'), output_verify='ignore')
        assert_true(isinstance(pyfits.open(self.temp('test.fits'))[0],
                               pyfits.PrimaryHDU))

        hdu = pyfits.ImageHDU()
        hdu.header.update('MYKEY', 'FOO', 'BAR')
        hdu.header.fromTxtFile(self.temp('header.txt'))
        # hdu.header should have MYKEY keyword, and also adds PCOUNT and
        # GCOUNT, giving it 3 more keywords in total than the original
        assert_equal(len(hdul[0].header.ascard), len(hdu.header.ascard) - 3)
        assert_true(hdu.header.has_key('MYKEY'))
        assert_false(hdu.header.has_key('EXTENSION'))
        assert_true(hdu.header.has_key('SIMPLE'))

        with ignore_warnings():
            hdu.writeto(self.temp('test.fits'), output_verify='ignore',
                        clobber=True)
        hdul2 = pyfits.open(self.temp('test.fits'))
        assert_true(len(hdul2), 2)
        assert_true(hdul2[1].header.has_key('MYKEY'))

    def test_update_comment(self):
        hdul = pyfits.open(self.data('arange.fits'))
        hdul[0].header.update('FOO', 'BAR', 'BAZ')
        assert_equal(hdul[0].header['FOO'], 'BAR')
        assert_equal(hdul[0].header.ascard['FOO'].comment, 'BAZ')

        hdul.writeto(self.temp('test.fits'))

        hdul = pyfits.open(self.temp('test.fits'), mode='update')
        hdul[0].header.ascard['FOO'].comment = 'QUX'
        hdul.close()

        hdul = pyfits.open(self.temp('test.fits'))
        assert_equal(hdul[0].header.ascard['FOO'].comment, 'QUX')

    def test_long_commentary_card(self):
        # Another version of this test using new API methods is found in
        # TestHeaderFunctions
        header = pyfits.Header()
        header.update('FOO', 'BAR')
        header.update('BAZ', 'QUX')
        longval = 'ABC' * 30
        header.add_history(longval)
        header.update('FRED', 'BARNEY')
        header.add_history(longval)

        assert_equal(len(header.ascard), 7)
        assert_equal(header.ascard[2].key, 'FRED')
        assert_equal(str(header.cards[3]), 'HISTORY ' + longval[:72])
        assert_equal(str(header.cards[4]).rstrip(), 'HISTORY ' + longval[72:])

        header.add_history(longval, after='FOO')
        assert_equal(len(header.ascard), 9)
        assert_equal(str(header.cards[1]), 'HISTORY ' + longval[:72])
        assert_equal(str(header.cards[2]).rstrip(), 'HISTORY ' + longval[72:])

    def test_wildcard_slice(self):
        """Test selecting a subsection of a header via wildcard matching."""

        header = pyfits.Header()
        header.update('ABC', 0)
        header.update('DEF', 1)
        header.update('ABD', 2)
        cards = header.ascard['AB*']
        assert_equal(len(cards), 2)
        assert_equal(cards[0].value, 0)
        assert_equal(cards[1].value, 2)

    def test_assign_boolean(self):
        """
        Regression test for #123. Tests assigning Python and Numpy boolean
        values to keyword values.
        """

        fooimg = _pad('FOO     =                    T')
        barimg = _pad('BAR     =                    F')
        h = pyfits.Header()
        h.update('FOO', True)
        h.update('BAR', False)
        assert_equal(h['FOO'], True)
        assert_equal(h['BAR'], False)
        assert_equal(h.ascard['FOO'].cardimage, fooimg)
        assert_equal(h.ascard['BAR'].cardimage, barimg)

        h = pyfits.Header()
        h.update('FOO', np.bool_(True))
        h.update('BAR', np.bool_(False))
        assert_equal(h['FOO'], True)
        assert_equal(h['BAR'], False)
        assert_equal(h.ascard['FOO'].cardimage, fooimg)
        assert_equal(h.ascard['BAR'].cardimage, barimg)

        h = pyfits.Header()
        h.ascard.append(pyfits.Card.fromstring(fooimg))
        h.ascard.append(pyfits.Card.fromstring(barimg))
        assert_equal(h['FOO'], True)
        assert_equal(h['BAR'], False)
        assert_equal(h.ascard['FOO'].cardimage, fooimg)
        assert_equal(h.ascard['BAR'].cardimage, barimg)


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
        with ignore_warnings():
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

    def test_blank_keyword(self):
        c = pyfits.Card('', '       / EXPOSURE INFORMATION')
        assert_equal(str(c),
                     '               / EXPOSURE INFORMATION                                           ')
        c = pyfits.Card.fromstring(str(c))
        assert_equal(c.keyword, '')
        assert_equal(c.value, '       / EXPOSURE INFORMATION')


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
        assert_equal(c.value, 2100000000000.0)
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
        with catch_warnings(record=True) as w:
            with CaptureStdio():
                c.verify()
            err_text1 = ('Card image is not FITS standard (equal sign not at '
                         'column 8)')
            err_text2 = ('Card image is not FITS standard (unparsable value '
                         'string: a6')
            assert_equal(len(w), 2)
            assert_true(err_text1 in str(w[0].message))
            assert_true(err_text2 in str(w[1].message))

    def test_fix_invalid_equal_sign(self):
        c = pyfits.Card.fromstring('abc= a6')
        with catch_warnings(record=True) as w:
            with CaptureStdio():
                c.verify('fix')
            fix_text = 'Fixed card to meet the FITS standard: ABC'
            assert_equal(len(w), 2)
            assert_true(fix_text in str(w[0].message))
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
        c = hdul[0].header.cards['abc']
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
            _pad("abc     = 'longstring''s testing  &  ' / comments in line 1") +
            _pad("continue  'continue with long string but without the ampersand at the end' /") +
            _pad("continue  'continue must have string value (with quotes)' / comments with ''. "))
        assert_equal(str(c),
            "ABC     = 'longstring''s testing  continue with long string but without the &'  "
            "CONTINUE  'ampersand at the endcontinue must have string value (with quotes)&'  "
            "CONTINUE  '&' / comments in line 1 comments with ''.                            ")

    def test_continue_card_with_equals_in_value(self):
        """
        Regression test for #117.
        """

        c = pyfits.Card.fromstring(
            _pad("EXPR    = '/grp/hst/cdbs//grid/pickles/dat_uvk/pickles_uk_10.fits * &'") +
            _pad("CONTINUE  '5.87359e-12 * MWAvg(Av=0.12)&'") +
            _pad("CONTINUE  '&' / pysyn expression"))

        assert_equal(c.keyword, 'EXPR')
        assert_equal(c.value,
                     '/grp/hst/cdbs//grid/pickles/dat_uvk/pickles_uk_10.fits '
                     '* 5.87359e-12 * MWAvg(Av=0.12)')
        assert_equal(c.comment, 'pysyn expression')

    def test_hierarch_card_creation(self):
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

    def test_missing_keyword(self):
        """Test that accessing a non-existent keyword raises a KeyError."""

        header = pyfits.Header()
        assert_raises(KeyError, lambda k: header[k], 'NAXIS')
        # Test the exception message
        try:
            header['NAXIS']
        except KeyError, e:
            assert_equal(e.args[0], "Keyword 'NAXIS' not found.")

    def test_hierarch_card_lookup(self):
        header = pyfits.Header()
        header['hierarch abcdefghi'] = 10
        assert_true('abcdefghi' in header)
        assert_equal(header['abcdefghi'], 10)
        assert_false('ABCDEFGHI' in header)

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

    def test_set_comment_only(self):
        header = pyfits.Header([('A', 'B', 'C')])
        header.set('A', comment='D')
        assert_equal(header['A'], 'B')
        assert_equal(header.comments['A'], 'D')

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

    def test_header_history(self):
        header = pyfits.Header([('ABC', 0), ('HISTORY', 1), ('HISTORY', 2),
                                ('DEF', 3), ('HISTORY', 4), ('HISTORY', 5)])
        assert_equal(header['HISTORY'], [1, 2, 4, 5])

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

    def test_header_items(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        assert_equal(header.items(), list(header.iteritems()))

    def test_header_iterkeys(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        for a, b in itertools.izip(header.iterkeys(), header):
            assert_equal(a, b)

    def test_header_itervalues(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        for a, b in itertools.izip(header.itervalues(), ['B', 'D']):
            assert_equal(a, b)

    def test_header_keys(self):
        hdul = pyfits.open(self.data('arange.fits'))
        assert_equal(hdul[0].header.keys(),
                     ['SIMPLE', 'BITPIX', 'NAXIS', 'NAXIS1', 'NAXIS2',
                      'NAXIS3', 'EXTEND'])

    def test_header_list_like_pop(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F'),
                                ('G', 'H')])

        last = header.pop()
        assert_equal(last, 'H')
        assert_equal(len(header), 3)
        assert_equal(header.keys(), ['A', 'C', 'E'])

        mid = header.pop(1)
        assert_equal(mid, 'D')
        assert_equal(len(header), 2)
        assert_equal(header.keys(), ['A', 'E'])

        first = header.pop(0)
        assert_equal(first, 'B')
        assert_equal(len(header), 1)
        assert_equal(header.keys(), ['E'])

        assert_raises(IndexError, header.pop, 42)

    def test_header_dict_like_pop(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F'),
                                ('G', 'H')])
        assert_raises(TypeError, header.pop, 'A', 'B', 'C')

        last = header.pop('G')
        assert_equal(last, 'H')
        assert_equal(len(header), 3)
        assert_equal(header.keys(), ['A', 'C', 'E'])

        mid = header.pop('C')
        assert_equal(mid, 'D')
        assert_equal(len(header), 2)
        assert_equal(header.keys(), ['A', 'E'])

        first = header.pop('A')
        assert_equal(first, 'B')
        assert_equal(len(header), 1)
        assert_equal(header.keys(), ['E'])

        default = header.pop('X', 'Y')
        assert_equal(default, 'Y')
        assert_equal(len(header), 1)

        assert_raises(KeyError, header.pop, 'X')

    def test_popitem(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F')])
        keyword, value = header.popitem()
        assert_true(keyword not in header)
        assert_equal(len(header), 2)
        keyword, value = header.popitem()
        assert_true(keyword not in header)
        assert_equal(len(header), 1)
        keyword, value = header.popitem()
        assert_true(keyword not in header)
        assert_equal(len(header), 0)
        assert_raises(KeyError, header.popitem)

    def test_setdefault(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F')])
        assert_equal(header.setdefault('A'), 'B')
        assert_equal(header.setdefault('C'), 'D')
        assert_equal(header.setdefault('E'), 'F')
        assert_equal(len(header), 3)
        assert_equal(header.setdefault('G', 'H'), 'H')
        assert_equal(len(header), 4)
        assert_true('G' in header)
        assert_equal(header.setdefault('G', 'H'), 'H')
        assert_equal(len(header), 4)

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

        # Same as above but this time pass the update dict as keyword arguments
        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        header.update(A='E', F='G')
        assert_equal(header['A'], 'E')
        assert_equal(header[0], 'E')
        assert_true('F' in header)
        assert_equal(header['F'], 'G')
        assert_equal(header[-1], 'G')

    def test_update_from_iterable(self):
        """
        Test adding new cards and updating existing cards from an iterable of
        cards and card tuples.
        """

        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        header.update([('A', 'E'), pyfits.Card('F', 'G')])
        assert_equal(header['A'], 'E')
        assert_equal(header[0], 'E')
        assert_true('F' in header)
        assert_equal(header['F'], 'G')
        assert_equal(header[-1], 'G')

    def test_header_extend(self):
        """
        Test extending a header both with and without stripping cards from the
        extension header.
        """

        hdu = pyfits.PrimaryHDU()
        hdu2 = pyfits.ImageHDU()
        hdu2.header['MYKEY'] = ('some val', 'some comment')
        hdu.header += hdu2.header
        assert_equal(len(hdu.header), 5)
        assert_equal(hdu.header[-1], 'some val')

        # Same thing, but using + instead of +=
        hdu = pyfits.PrimaryHDU()
        hdu.header = hdu.header + hdu2.header
        assert_equal(len(hdu.header), 5)
        assert_equal(hdu.header[-1], 'some val')

        # Directly append the other header in full--not usually a desirable
        # operation when the header is coming from another HDU
        hdu.header.extend(hdu2.header, strip=False)
        assert_equal(len(hdu.header), 11)
        assert_equal(hdu.header.keys()[5], 'XTENSION')
        assert_equal(hdu.header[-1], 'some val')
        assert_true(('MYKEY', 1) in hdu.header)

    def test_header_extend_unique(self):
        """
        Test extending the header with and without unique=True.
        """
        hdu = pyfits.PrimaryHDU()
        hdu2 = pyfits.ImageHDU()
        hdu.header['MYKEY'] = ('some val', 'some comment')
        hdu2.header['MYKEY'] = ('some other val', 'some other comment')
        hdu.header.extend(hdu2.header)
        assert_equal(len(hdu.header), 6)
        assert_equal(hdu.header[-2], 'some val')
        assert_equal(hdu.header[-1], 'some other val')

        hdu = pyfits.PrimaryHDU()
        hdu2 = pyfits.ImageHDU()
        hdu.header['MYKEY'] = ('some val', 'some comment')
        hdu.header.extend(hdu2.header, unique=True)
        assert_equal(len(hdu.header), 5)
        assert_equal(hdu.header[-1], 'some val')

    def test_header_extend_update(self):
        """
        Test extending the header with and without update=True.
        """

        hdu = pyfits.PrimaryHDU()
        hdu2 = pyfits.ImageHDU()
        hdu.header['MYKEY'] = ('some val', 'some comment')
        hdu.header['HISTORY'] = 'history 1'
        hdu2.header['MYKEY'] = ('some other val', 'some other comment')
        hdu2.header['HISTORY'] = 'history 1'
        hdu2.header['HISTORY'] = 'history 2'
        hdu.header.extend(hdu2.header)
        assert_equal(len(hdu.header), 9)
        assert_true(('MYKEY', 0) in hdu.header)
        assert_true(('MYKEY', 1) in hdu.header)
        assert_equal(hdu.header[('MYKEY', 1)], 'some other val')
        assert_equal(len(hdu.header['HISTORY']), 3)
        assert_equal(hdu.header[-1], 'history 2')

        hdu = pyfits.PrimaryHDU()
        hdu.header['MYKEY'] = ('some val', 'some comment')
        hdu.header['HISTORY'] = 'history 1'
        hdu.header.extend(hdu2.header, update=True)
        assert_equal(len(hdu.header), 7)
        assert_true(('MYKEY', 0) in hdu.header)
        assert_false(('MYKEY', 1) in hdu.header)
        assert_equal(hdu.header['MYKEY'], 'some other val')
        assert_equal(len(hdu.header['HISTORY']), 2)
        assert_equal(hdu.header[-1], 'history 2')

    def test_header_extend_exact(self):
        """
        Test that extending an empty header with the contents of an existing
        header can exactly duplicate that header, given strip=False and
        end=True.
        """

        header = pyfits.getheader(self.data('test0.fits'))
        header2 = pyfits.Header()
        header2.extend(header, strip=False, end=True)
        assert_equal(header, header2)

    def test_header_count(self):
        header = pyfits.Header([('A', 'B'), ('C', 'D'), ('E', 'F')])
        assert_equal(header.count('A'), 1)
        assert_equal(header.count('C'), 1)
        assert_equal(header.count('E'), 1)
        header['HISTORY'] = 'a'
        header['HISTORY'] = 'b'
        assert_equal(header.count('HISTORY'), 2)
        assert_raises(KeyError, header.count, 'G')

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

    def test_header_append_keyword_only(self):
        """
        Test appending a new card with just the keyword, and no value or
        comment given.
        """

        header = pyfits.Header([('A', 'B'), ('C', 'D')])
        header.append('E')
        assert_equal(len(header), 3)
        assert_equal(header.keys()[-1], 'E')
        assert_equal(header[-1], '')
        assert_equal(header.comments['E'], '')

        # Try appending a blank--normally this can be accomplished with just
        # header.append(), but header.append('') should also work (and is maybe
        # a little more clear)
        header.append('')
        assert_equal(len(header), 4)

        assert_equal(header.keys()[-1], '')
        assert_equal(header[''], '')
        assert_equal(header.comments[''], '')

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

    def test_header_comments(self):
        header = pyfits.Header([('A', 'B', 'C'), ('DEF', 'G', 'H')])
        assert_equal(repr(header.comments),
                     '       A  C\n'
                     '     DEF  H')

    def test_comment_slices_and_filters(self):
        header = pyfits.Header([('AB', 'C', 'D'), ('EF', 'G', 'H'),
                                ('AI', 'J', 'K')])
        s = header.comments[1:]
        assert_equal(list(s), ['H', 'K'])
        s = header.comments[::-1]
        assert_equal(list(s), ['K', 'H', 'D'])
        s = header.comments['A*']
        assert_equal(list(s), ['D', 'K'])

    def test_comment_slice_filter_assign(self):
        header = pyfits.Header([('AB', 'C', 'D'), ('EF', 'G', 'H'),
                                ('AI', 'J', 'K')])
        header.comments[1:] = 'L'
        assert_equal(list(header.comments), ['D', 'L', 'L'])
        assert_equal(header.cards[header.index('AB')].comment, 'D')
        assert_equal(header.cards[header.index('EF')].comment, 'L')
        assert_equal(header.cards[header.index('AI')].comment, 'L')

        header.comments[::-1] = header.comments[:]
        assert_equal(list(header.comments), ['L', 'L', 'D'])

        header.comments['A*'] = ['M', 'N']
        assert_equal(list(header.comments), ['M', 'L', 'N'])

    def test_update_comment(self):
        hdul = pyfits.open(self.data('arange.fits'))
        hdul[0].header['FOO'] = ('BAR', 'BAZ')
        hdul.writeto(self.temp('test.fits'))

        hdul = pyfits.open(self.temp('test.fits'), mode='update')
        hdul[0].header.comments['FOO'] = 'QUX'
        hdul.close()

        hdul = pyfits.open(self.temp('test.fits'))
        assert_equal(hdul[0].header.comments['FOO'], 'QUX')

    def test_update_commentary(self):
        header = pyfits.Header()
        header['FOO'] = 'BAR'
        header['HISTORY'] = 'ABC'
        header['FRED'] = 'BARNEY'
        header['HISTORY'] = 'DEF'
        header['HISTORY'] = 'GHI'

        assert_equal(header['HISTORY'], ['ABC', 'DEF', 'GHI'])

        # Single value update
        header['HISTORY'][0] = 'FOO'
        assert_equal(header['HISTORY'], ['FOO', 'DEF', 'GHI'])

        # Single value partial slice update
        header['HISTORY'][1:] = 'BAR'
        assert_equal(header['HISTORY'], ['FOO', 'BAR', 'BAR'])

        # Multi-value update
        header['HISTORY'][:] = ['BAZ', 'QUX']
        assert_equal(header['HISTORY'], ['BAZ', 'QUX', 'BAR'])

    def test_long_commentary_card(self):
        header = pyfits.Header()
        header['FOO'] = 'BAR'
        header['BAZ'] = 'QUX'
        longval = 'ABC' * 30
        header['HISTORY'] = longval
        header['FRED'] = 'BARNEY'
        header['HISTORY'] = longval

        assert_equal(len(header), 7)
        assert_equal(header.keys()[2], 'FRED')
        assert_equal(str(header.cards[3]), 'HISTORY ' + longval[:72])
        assert_equal(str(header.cards[4]).rstrip(), 'HISTORY ' + longval[72:])

        header.set('HISTORY', longval, after='FOO')
        assert_equal(len(header), 9)
        assert_equal(str(header.cards[1]), 'HISTORY ' + longval[:72])
        assert_equal(str(header.cards[2]).rstrip(), 'HISTORY ' + longval[72:])

    def test_header_fromtextfile(self):
        """Regression test for #122.

        Manually write a text file containing some header cards ending with
        newlines and ensure that fromtextfile can read them back in.
        """

        header = pyfits.Header()
        header['A'] = ('B', 'C')
        header['B'] = ('C', 'D')
        header['C'] = ('D', 'E')

        with open(self.temp('test.hdr'), 'w') as f:
            f.write('\n'.join(str(c).strip() for c in header.cards))

        header2 = pyfits.Header.fromtextfile(self.temp('test.hdr'))
        assert_equal(header, header2)

    def test_unnecessary_move(self):
        """Regression test for #125.

        Ensures that a header is not modified when setting the position of a
        keyword that's already in its correct position.
        """

        header = pyfits.Header([('A', 'B'), ('B', 'C'), ('C', 'D')])

        header.set('B', before=2)
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

        header.set('B', after=0)
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

        header.set('B', before='C')
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

        header.set('B', after='A')
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

        header.set('B', before=2)
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

        # 123 is well past the end, and C is already at the end, so it's in the
        # right place already
        header.set('C', before=123)
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

        header.set('C', after=123)
        assert_equal(header.keys(), ['A', 'B', 'C'])
        assert_false(header._modified)

    def test_invalid_float_cards(self):
        """Regression test for #137."""

        # Create a header containing two of the problematic cards in the test
        # case where this came up:
        hstr = "FOCALLEN= +1.550000000000e+002\nAPERTURE=+0.000000000000e+000"
        h = pyfits.Header.fromstring(hstr, sep='\n')

        # First the case that *does* work prior to fixing this issue
        assert_equal(h['FOCALLEN'], 155.0)
        assert_equal(h['APERTURE'], 0.0)

        # Now if this were reserialized, would new values for these cards be
        # written with repaired exponent signs?
        assert_equal(str(h.cards['FOCALLEN']),
                     _pad("FOCALLEN= +1.550000000000E+002"))
        assert_true(h.cards['FOCALLEN']._modified)
        assert_equal(str(h.cards['APERTURE']),
                     _pad("APERTURE= +0.000000000000E+000"))
        assert_true(h.cards['APERTURE']._modified)
        assert_true(h._modified)

        # This is the case that was specifically causing problems; generating
        # the card strings *before* parsing the values.  Also, the card strings
        # really should be "fixed" before being returned to the user
        h = pyfits.Header.fromstring(hstr, sep='\n')
        assert_equal(str(h.cards['FOCALLEN']),
                     _pad("FOCALLEN= +1.550000000000E+002"))
        assert_true(h.cards['FOCALLEN']._modified)
        assert_equal(str(h.cards['APERTURE']),
                     _pad("APERTURE= +0.000000000000E+000"))
        assert_true(h.cards['APERTURE']._modified)

        assert_equal(h['FOCALLEN'], 155.0)
        assert_equal(h['APERTURE'], 0.0)
        assert_true(h._modified)

        # For the heck of it, try assigning the identical values and ensure
        # that the newly fixed value strings are left intact
        h['FOCALLEN'] = 155.0
        h['APERTURE'] = 0.0
        assert_equal(str(h.cards['FOCALLEN']),
                     _pad("FOCALLEN= +1.550000000000E+002"))
        assert_equal(str(h.cards['APERTURE']),
                     _pad("APERTURE= +0.000000000000E+000"))

    def test_leading_zeros(self):
        """
        Regression test for #137, part 2.

        Ticket #137 also showed that in float values like 0.001 the leading
        zero was unnecessarily being stripped off when rewriting the header.
        Though leading zeros should be removed from integer values to prevent
        misinterpretation as octal by python (for now PyFITS will still
        maintain the leading zeros if now changes are made to the value, but
        will drop them if changes are made).
        """

        c = pyfits.Card.fromstring("APERTURE= +0.000000000000E+000")
        assert_equal(str(c), _pad("APERTURE= +0.000000000000E+000"))
        assert_equal(c.value, 0.0)
        c = pyfits.Card.fromstring("APERTURE= 0.000000000000E+000")
        assert_equal(str(c), _pad("APERTURE= 0.000000000000E+000"))
        assert_equal(c.value, 0.0)
        c = pyfits.Card.fromstring("APERTURE= 017")
        assert_equal(str(c), _pad("APERTURE= 017"))
        assert_equal(c.value, 17)

    def test_assign_boolean(self):
        """
        Regression test for #123. Tests assigning Python and Numpy boolean
        values to keyword values.
        """

        fooimg = _pad('FOO     =                    T')
        barimg = _pad('BAR     =                    F')
        h = pyfits.Header()
        h['FOO'] = True
        h['BAR'] = False
        assert_equal(h['FOO'], True)
        assert_equal(h['BAR'], False)
        assert_equal(str(h.cards['FOO']), fooimg)
        assert_equal(str(h.cards['BAR']), barimg)

        h = pyfits.Header()
        h['FOO'] = np.bool_(True)
        h['BAR'] = np.bool_(False)
        assert_equal(h['FOO'], True)
        assert_equal(h['BAR'], False)
        assert_equal(str(h.cards['FOO']), fooimg)
        assert_equal(str(h.cards['BAR']), barimg)

        h = pyfits.Header()
        h.append(pyfits.Card.fromstring(fooimg))
        h.append(pyfits.Card.fromstring(barimg))
        assert_equal(h['FOO'], True)
        assert_equal(h['BAR'], False)
        assert_equal(str(h.cards['FOO']), fooimg)
        assert_equal(str(h.cards['BAR']), barimg)

    def test_header_method_keyword_normalization(self):
        """
        Regression test for #149.  Basically ensures that all public Header
        methods are case-insensitive w.r.t. keywords.

        Provides a reasonably comprehensive test of several methods at once.
        """

        h = pyfits.Header([('abC', 1), ('Def', 2), ('GeH', 3)])
        assert_equal(h.keys(), ['ABC', 'DEF', 'GEH'])
        assert_true('abc' in h)
        assert_true('dEf' in h)

        assert_equal(h['geh'], 3)

        # Case insensitivity of wildcards
        assert_equal(len(h['g*']), 1)

        h['aBc'] = 2
        assert_equal(h['abc'], 2)
        # ABC already existed so assigning to aBc should not have added any new
        # cards
        assert_equal(len(h), 3)

        del h['gEh']
        assert_equal(h.keys(), ['ABC', 'DEF'])
        assert_equal(len(h), 2)
        assert_equal(h.get('def'), 2)

        h.set('Abc', 3)
        assert_equal(h['ABC'], 3)
        h.set('gEh', 3, before='Abc')
        assert_equal(h.keys(), ['GEH', 'ABC', 'DEF'])

        assert_equal(h.pop('abC'), 3)
        assert_equal(len(h), 2)

        assert_equal(h.setdefault('def', 3), 2)
        assert_equal(len(h), 2)
        assert_equal(h.setdefault('aBc', 1), 1)
        assert_equal(len(h), 3)
        assert_equal(h.keys(), ['GEH', 'DEF', 'ABC'])

        h.update({'GeH': 1, 'iJk': 4})
        assert_equal(len(h), 4)
        assert_equal(h.keys(), ['GEH', 'DEF', 'ABC', 'IJK'])
        assert_equal(h['GEH'], 1)

        assert_equal(h.count('ijk'), 1)
        assert_equal(h.index('ijk'), 3)

        h.remove('Def')
        assert_equal(len(h), 3)
        assert_equal(h.keys(), ['GEH', 'ABC', 'IJK'])

    def test_end_in_comment(self):
        """
        Regression test for #142.  Tests a case where the comment of a card
        ends with END, and is followed by several blank cards.
        """

        data = np.arange(100).reshape((10, 10))
        hdu = pyfits.PrimaryHDU(data=data)
        hdu.header['TESTKW'] = ('Test val', 'This is the END')
        # Add a couple blanks after the END string
        hdu.header.append()
        hdu.header.append()
        hdu.writeto(self.temp('test.fits'))

        with pyfits.open(self.temp('test.fits')) as hdul:
            assert_true('TESTKW' in hdul[0].header)
            assert_equal(hdul[0].header, hdu.header)
            assert_true((hdul[0].data == data).all())

        # Add blanks until the header is extended to two block sizes
        while len(hdu.header) < 36:
            hdu.header.append()
        with ignore_warnings():
            hdu.writeto(self.temp('test.fits'), clobber=True)

        with pyfits.open(self.temp('test.fits')) as hdul:
            assert_true('TESTKW' in hdul[0].header)
            assert_equal(hdul[0].header, hdu.header)
            assert_true((hdul[0].data == data).all())

        # Test parsing the same header when it's written to a text file
        hdu.header.totextfile(self.temp('test.hdr'))
        header2 = pyfits.Header.fromtextfile(self.temp('test.hdr'))
        assert_equal(hdu.header, header2)

    def test_assign_unicode(self):
        """
        Regression test for #134.  Assigning a unicode literal as a header
        value should not fail silently.  If the value can be converted to ASCII
        then it should just work.  Otherwise it should fail with an appropriate
        value error.

        Also tests unicode for keywords and comments.
        """

        erikku = u'\u30a8\u30ea\u30c3\u30af'

        def assign(keyword, val):
            h[keyword] = val

        h = pyfits.Header()
        h[u'FOO'] = 'BAR'
        assert_true('FOO' in h)
        assert_equal(h['FOO'], 'BAR')
        assert_equal(h[u'FOO'], 'BAR')
        assert_equal(repr(h), _pad("FOO     = 'BAR     '"))
        assert_raises(ValueError, assign, erikku, 'BAR')


        h['FOO'] = u'BAZ'
        assert_equal(h[u'FOO'], 'BAZ')
        assert_equal(h[u'FOO'], u'BAZ')
        assert_equal(repr(h), _pad("FOO     = 'BAZ     '"))
        assert_raises(ValueError, assign, 'FOO', erikku)

        h['FOO'] = ('BAR', u'BAZ')
        assert_equal(h['FOO'], 'BAR')
        assert_equal(h['FOO'], u'BAR')
        assert_equal(h.comments['FOO'], 'BAZ')
        assert_equal(h.comments['FOO'], u'BAZ')
        assert_equal(repr(h), _pad("FOO     = 'BAR     '           / BAZ"))

        h['FOO'] = (u'BAR', u'BAZ')
        assert_equal(h['FOO'], 'BAR')
        assert_equal(h['FOO'], u'BAR')
        assert_equal(h.comments['FOO'], 'BAZ')
        assert_equal(h.comments['FOO'], u'BAZ')
        assert_equal(repr(h), _pad("FOO     = 'BAR     '           / BAZ"))

        assert_raises(ValueError, assign, 'FOO', ('BAR', erikku))
        assert_raises(ValueError, assign, 'FOO', (erikku, 'BAZ'))
        assert_raises(ValueError, assign, 'FOO', (erikku, erikku))

    def test_header_strip_whitespace(self):
        """
        Regression test for #146, and for the solution that is optional
        stripping of whitespace from the end of a header value.

        By default extra whitespace is stripped off, but if
        pyfits.STRIP_HEADER_WHITESPACE = False it should not be stripped.
        """

        h = pyfits.Header()
        h['FOO'] = 'Bar      '
        assert_equal(h['FOO'], 'Bar')
        c = pyfits.Card.fromstring("QUX     = 'Bar        '")
        h.append(c)
        assert_equal(h['QUX'], 'Bar')
        assert_equal(h.cards['FOO'].image.rstrip(),
                     "FOO     = 'Bar      '")
        assert_equal(h.cards['QUX'].image.rstrip(),
                     "QUX     = 'Bar        '")

        pyfits.STRIP_HEADER_WHITESPACE = False
        try:
            assert_equal(h['FOO'], 'Bar      ')
            assert_equal(h['QUX'], 'Bar        ')
            assert_equal(h.cards['FOO'].image.rstrip(),
                         "FOO     = 'Bar      '")
            assert_equal(h.cards['QUX'].image.rstrip(),
                         "QUX     = 'Bar        '")
        finally:
            pyfits.STRIP_HEADER_WHITESPACE = True

        assert_equal(h['FOO'], 'Bar')
        assert_equal(h['QUX'], 'Bar')
        assert_equal(h.cards['FOO'].image.rstrip(),
                     "FOO     = 'Bar      '")
        assert_equal(h.cards['QUX'].image.rstrip(),
                     "QUX     = 'Bar        '")


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

        with ignore_warnings():
            c = pyfits.Card('DP1.NAXIS', 'a')
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 'a')
        assert_equal(c.field_specifier, None)

    def test_parse_field_specifier(self):
        """
        Tests that the field_specifier can accessed from a card read from a
        string before any other attributes are accessed.
        """

        c = pyfits.Card.fromstring("DP1     = 'NAXIS: 2' / A comment")
        assert_equal(c.field_specifier, 'NAXIS')
        assert_equal(c.keyword, 'DP1.NAXIS')
        assert_equal(c.value, 2.0)
        assert_equal(c.comment, 'A comment')

    def test_update_field_specifier(self):
        """
        Test setting the field_specifier attribute and updating the card image
        to reflect the new value.
        """

        c = pyfits.Card.fromstring("DP1     = 'NAXIS: 2' / A comment")
        assert_equal(c.field_specifier, 'NAXIS')
        c.field_specifier = 'NAXIS1'
        assert_equal(c.field_specifier, 'NAXIS1')
        assert_equal(c.keyword, 'DP1.NAXIS1')
        assert_equal(c.value, 2.0)
        assert_equal(c.comment, 'A comment')
        assert_equal(str(c).rstrip(), "DP1     = 'NAXIS1: 2' / A comment")

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
        # Test the exception message
        try:
            self._test_header['DP1.AXIS.3']
        except KeyError, e:
            assert_equal(e.args[0], "Keyword 'DP1.AXIS.3' not found.")

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
