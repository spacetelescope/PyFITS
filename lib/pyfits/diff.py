import difflib
import fnmatch
import glob
import os
import textwrap

from collections import defaultdict
from itertools import islice, izip

import numpy as np
from numpy import char

import pyfits
from pyfits.header import Header
from pyfits.hdu.hdulist import fitsopen
from pyfits.hdu.table import _TableLikeHDU
from pyfits.util import StringIO


class _GenericDiff(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self._diff()

    def __nonzero__(self):
        return not self.identical

    @property
    def identical(self):
        return not any(getattr(self, attr) for attr in self.__dict__
                       if attr.startswith('diff_'))

    def report(self, fileobj=None):
        return_string = False
        if fileobj is None:
            fileobj = StringIO()
            return_string = True

        self._report(fileobj)

        if return_string:
            return fileobj.getvalue()

    def _diff(self):
        raise NotImplementedError

    def _report(self, fileobj):
        raise NotImplementedError


class FITSDiff(_GenericDiff):
    def __init__(self, a, b, ignore_keywords=[], ignore_comments=[],
                 ignore_fields=[], numdiffs=10, tolerance=0.0,
                 ignore_blanks=True):

        if isinstance(a, basestring):
            a = fitsopen(a)
            close_a = True
        else:
            close_a = False

        if isinstance(b, basestring):
            b = fitsopen(b)
            close_b = True
        else:
            close_b = False

        self.ignore_keywords = set(ignore_keywords)
        self.ignore_comments = set(ignore_comments)
        self.ignore_fields = set(ignore_fields)
        self.numdiffs = numdiffs
        self.tolerance = tolerance
        self.ignore_blanks = ignore_blanks

        self.diff_extension_count = ()
        self.diff_extensions = []

        try:
            super(FITSDiff, self).__init__(a, b)
        finally:
            if close_a:
                a.close()
            if close_b:
                b.close()

    def _diff(self):
        if len(self.a) != len(self.b):
            self.diff_extension_count = (len(self.a), len(self.b))

        # For now, just compare the extensions one by one in order...might
        # allow some more sophisticated types of diffing later...
        # TODO: Somehow or another simplify the passing around of diff
        # options--this will become important as the number of options grows
        for idx in range(min(len(self.a), len(self.b))):
            hdu_diff = HDUDiff(self.a[idx], self.b[idx],
                               ignore_keywords=self.ignore_keywords,
                               ignore_comments=self.ignore_comments,
                               ignore_fields=self.ignore_fields,
                               numdiffs=self.numdiffs,
                               tolerance=self.tolerance,
                               ignore_blanks=self.ignore_blanks)

            if not hdu_diff.identical:
                self.diff_extensions.append((idx, hdu_diff))

    def _report(self, fileobj):
        wrapper = textwrap.TextWrapper(initial_indent='  ',
                                       subsequent_indent='  ')

        # print out heading and parameter values
        filenamea = self.a.filename()
        if not filenamea:
            filenamea = '<%s object at 0x%x>' % (self.a.__class__.__name__,
                                                 id(self.a))

        filenameb = self.b.filename()
        if not filenameb:
            filenameb = '<%s object at 0x%x>' % (self.b.__class__.__name__,
                                                 id(self.b))

        fileobj.write("\n fitsdiff: %s\n" % pyfits.__version__)
        fileobj.write(" a: %s\n b: %s\n" % (filenamea, filenameb))
        if self.ignore_keywords:
            ignore_keywords = ' '.join(sorted(self.ignore_keywords))
            fileobj.write(" Keyword(s) not to be compared:\n%s\n" %
                          wrapper.fill(ignore_keywords))

        if self.ignore_comments:
            ignore_comments = ' '.join(sorted(self.ignore_comments))
            fileobj.write(" Keyword(s) whose comments are not to be compared:"
                          "\n%s\n" % wrapper.fill(ignore_keywords))
        if self.ignore_fields:
            ignore_fields = ' '.join(sorted(self.ignore_fields))
            fileobj.write(" Table column(s) not to be compared:\n%s\n" %
                          wrapper.fill(ignore_fields))
        fileobj.write(" Maximum number of different data values to be "
                      "reported: %s\n" % self.numdiffs)
        fileobj.write(" Data comparison level: %s\n" % self.tolerance)

        for idx, hdu_diff in self.diff_extensions:
            # print out the extension heading
            if idx == 0:
                fileobj.write("\nPrimary HDU:\n")
            else:
                fileobj.write("\nExtension HDU %d:\n" % idx)
            hdu_diff._report(fileobj)


class HDUDiff(_GenericDiff):
    def __init__(self, a, b, ignore_keywords=[], ignore_comments=[],
                 ignore_fields=[], numdiffs=10, tolerance=0.0,
                 ignore_blanks=True):
        self.ignore_keywords = set(ignore_keywords)
        self.ignore_comments = set(ignore_comments)
        self.ignore_fields = set(ignore_fields)
        self.tolerance = tolerance
        self.numdiffs = numdiffs
        self.ignore_blanks = ignore_blanks

        self.diff_extnames = ()
        self.diff_extvers = ()
        self.diff_extension_types = ()
        self.diff_headers = None
        self.diff_data = None

        super(HDUDiff, self).__init__(a, b)

    def _diff(self):
        if self.a.name != self.b.name:
            self.diff_extnames = (self.a.name, self.b.name)

        # TODO: All extension headers should have a .extver attribute;
        # currently they have a hidden ._extver attribute, but there's no
        # reason it should be hidden
        if self.a.header.get('EXTVER') != self.b.header.get('EXTVER'):
            self.diff_extvers = (self.a.header.get('EXTVER'),
                                 self.b.header.get('EXTVER'))

        if self.a.header.get('XTENSION') != self.b.header.get('XTENSION'):
            self.diff_extension_types = (self.a.header.get('XTENSION'),
                                         self.b.header.get('XTENSION'))

        self.diff_headers = HeaderDiff(self.a.header, self.b.header,
                                       ignore_keywords=self.ignore_keywords,
                                       ignore_comments=self.ignore_comments,
                                       tolerance=self.tolerance,
                                       ignore_blanks=self.ignore_blanks)

        if self.a.data is None or self.b.data is None:
            # TODO: Perhaps have some means of marking this case
            pass
        elif self.a.is_image and self.b.is_image:
            self.diff_data = ImageDataDiff(self.a.data, self.b.data,
                                           numdiffs=self.numdiffs,
                                           tolerance=self.tolerance)
        elif (isinstance(self.a, _TableLikeHDU) and
              isinstance(self.b, _TableLikeHDU)):
            # TODO: Replace this if/when _BaseHDU grows a .is_table property
            self.diff_data = TableDataDiff(self.a.data, self.b.data)
        elif not self.diff_extension_types:
            # Don't diff the data for unequal extension types that are not
            # recognized image or table types
            self.diff_data = RawDataDiff(self.a.data, self.b.data)

    def _report(self, fileobj):
        if self.identical:
            fileobj.write(" No differences found.\n")
        if self.diff_extension_types:
            fileobj.write(" Extension types differ:\n  a: %s\n  b: %s\n" %
                          self.diff_extension_types)
        if self.diff_extnames:
            fileobj.write(" Extension names differ:\n  a: %s\n  b: %s\n" %
                          self.diff_extnames)
        if self.diff_extvers:
            fileobj.write(" Extension versions differ:\n  a: %s\n  b: %s\n" %
                          self.diff_extvers)

        if not self.diff_headers.identical:
            fileobj.write("\n Headers contain differences:\n")
            self.diff_headers._report(fileobj)

        if self.diff_data is not None and not self.diff_data.identical:
            fileobj.write("\n Data contains differences:\n")
            self.diff_data._report(fileobj)


class HeaderDiff(_GenericDiff):
    def __init__(self, a, b, ignore_keywords=[], ignore_comments=[],
                 tolerance=0.0, ignore_blanks=True):
        self.ignore_keywords = set(ignore_keywords)
        self.ignore_comments = set(ignore_comments)
        self.tolerance = tolerance
        self.ignore_blanks = ignore_blanks

        self.ignore_keyword_patterns = set()
        self.ignore_comment_patterns = set()
        for keyword in list(self.ignore_keywords):
            if keyword != '*' and glob.has_magic(keyword):
                self.ignore_keywords.remove(keyword)
                self.ignore_keyword_patterns.add(keyword)
        for keyword in list(self.ignore_comments):
            if keyword != '*' and glob.has_magic(keyword):
                self.ignore_comments.remove(keyword)
                self.ignore_comment_patterns.add(keyword)

        # Keywords appearing in each header
        self.common_keywords = []

        # Set to the number of keywords in each header if the counts differ
        self.diff_keyword_count = ()

        # Set if the keywords common to each header (excluding ignore_keywords)
        # appear in different positions within the header
        # TODO: Implement this
        self.diff_keyword_positions = ()

        # Keywords unique to each header (excluding keywords in
        # ignore_keywords)
        self.diff_keywords = ()

        # Keywords that have different numbers of duplicates in each header
        # (excluding keywords in ignore_keywords)
        self.diff_duplicate_keywords = {}

        # Keywords common to each header but having different values (excluding
        # keywords in ignore_keywords)
        self.diff_keyword_values = defaultdict(lambda: [])

        # Keywords common to each header but having different comments
        # (excluding keywords in ignore_keywords or in ignore_comments)
        self.diff_keyword_comments = defaultdict(lambda: [])

        if isinstance(a, basestring):
            a = Header.fromstring(a)
        if isinstance(b, basestring):
            b = Header.fromstring(b)

        if not (isinstance(a, Header) and isinstance(b, Header)):
            raise TypeError('HeaderDiff can only diff pyfits.Header objects '
                            'or strings containing FITS headers.')

        super(HeaderDiff, self).__init__(a, b)

    # TODO: This doesn't pay much attention to the *order* of the keywords,
    # except in the case of duplicate keywords.  The order should be checked
    # too, or at least it should be an option.
    def _diff(self):
        # build dictionaries of keyword values and comments
        def get_header_values_comments(header):
            values = {}
            comments = {}
            for card in header.cards:
                value = card.value
                if self.ignore_blanks and isinstance(value, basestring):
                    value = value.rstrip()
                values.setdefault(card.keyword, []).append(value)
                comments.setdefault(card.keyword, []).append(card.comment)
            return values, comments

        valuesa, commentsa = get_header_values_comments(self.a)
        valuesb, commentsb = get_header_values_comments(self.b)

        keywordsa = set(valuesa)
        keywordsb = set(valuesb)

        self.common_keywords = sorted(keywordsa.intersection(keywordsb))
        if len(self.a) != len(self.b):
            self.diff_keyword_count = (len(self.a), len(self.b))

        # Any other diff attributes should exclude ignored keywords
        keywordsa = keywordsa.difference(self.ignore_keywords)
        keywordsb = keywordsb.difference(self.ignore_keywords)
        if self.ignore_keyword_patterns:
            for pattern in self.ignore_keyword_patterns:
                keywordsa = keywordsa.difference(fnmatch.filter(keywordsa,
                                                                pattern))
                keywordsb = keywordsb.difference(fnmatch.filter(keywordsb,
                                                                pattern))

        if '*' in self.ignore_keywords:
            # Any other differences between keywords are to be ignored
            return

        left_only_keywords = sorted(keywordsa.difference(keywordsb))
        right_only_keywords = sorted(keywordsb.difference(keywordsa))

        if left_only_keywords or right_only_keywords:
            self.diff_keywords = (left_only_keywords, right_only_keywords)

        # Compare count of each common keyword
        for keyword in self.common_keywords:
            if keyword in self.ignore_keywords:
                continue
            if self.ignore_keyword_patterns:
                skip = False
                for pattern in self.ignore_keyword_patterns:
                    if fnmatch.fnmatch(keyword, pattern):
                        skip = True
                        break
                if skip:
                    continue

            counta = len(valuesa[keyword])
            countb = len(valuesb[keyword])
            if counta != countb:
                self.diff_duplicate_keywords[keyword] = (counta, countb)

            # Compare keywords' values and comments
            for a, b in zip(valuesa[keyword], valuesb[keyword]):
                if diff_values(a, b, tolerance=self.tolerance):
                    self.diff_keyword_values[keyword].append((a, b))
                else:
                    # If there are duplicate keywords we need to be able to
                    # index each duplicate; if the values of a duplicate
                    # are identical use None here
                    self.diff_keyword_values[keyword].append(None)

            if not any(self.diff_keyword_values[keyword]):
                # No differences found; delete the array of Nones
                del self.diff_keyword_values[keyword]

            if '*' in self.ignore_comments or keyword in self.ignore_comments:
                continue
            if self.ignore_comment_patterns:
                skip = False
                for pattern in self.ignore_comment_patterns:
                    if fnmatch.fnmatch(keyword, pattern):
                        skip = True
                        break
                if skip:
                    continue

            for a, b in zip(commentsa[keyword], commentsb[keyword]):
                if diff_values(a, b):
                    self.diff_keyword_comments[keyword].append((a, b))
                else:
                    self.diff_keyword_comments[keyword].append(None)

            if not any(self.diff_keyword_comments[keyword]):
                del self.diff_keyword_comments[keyword]

    def _report(self, fileobj):
        if self.diff_keyword_count:
            fileobj.write('  Headers have different number of cards:\n')
            fileobj.write('   a: %d\n' % self.diff_keyword_count[0])
            fileobj.write('   b: %d\n' % self.diff_keyword_count[1])
        if self.diff_keywords:
            for keyword in self.diff_keywords[0]:
                fileobj.write('  Extra keyword %-8s in a\n' % keyword)
            for keyword in self.diff_keywords[1]:
                fileobj.write('  Extra keyword %-8s in b\n' % keyword)

        if self.diff_duplicate_keywords:
            for keyword, count in sorted(self.diff_duplicate_keywords.items()):
                fileobj.write('  Inconsistent duplicates of keyword %-8s:\n' %
                              keyword)
                fileobj.write('   Occurs %d times in a, %d times in b\n' %
                              count)

        if self.diff_keyword_values or self.diff_keyword_comments:
            for keyword in self.common_keywords:
                report_diff_keyword_attr(fileobj, 'values',
                                         self.diff_keyword_values, keyword)
                report_diff_keyword_attr(fileobj, 'comments',
                                         self.diff_keyword_comments, keyword)

# TODO: It might be good if there was also a threshold option for percentage of
# different pixels: For example ignore if only 1% of the pixels are different
# within some threshold.  There are lots of possibilities here, but hold off
# for now until specific cases come up.
class ImageDataDiff(_GenericDiff):
    def __init__(self, a, b, numdiffs=10, tolerance=0.0):
        self.numdiffs = numdiffs
        self.tolerance = tolerance

        self.diff_dimensions = ()
        self.diff_pixels = []
        self.diff_ratio = 0

        # self.diff_pixels only holds up to numdiffs differing pixels, but this
        # self.total_diffs stores the total count of differences between
        # the images, but not the different values
        self.total_diffs = 0

        super(ImageDataDiff, self).__init__(a, b)

    def _diff(self):
        if self.a.shape != self.b.shape:
            self.diff_dimensions = (self.a.shape, self.b.shape)
            # Don't do any further comparison if the dimensions differ
            # TODO: Perhaps we could, however, diff just the intersection
            # between the two images
            return

        # Find the indices where the values are not equal
        diffs = where_not_allclose(self.a, self.b, atol=0.0,
                                   rtol=self.tolerance)

        self.total_diffs = len(diffs[0])

        if self.total_diffs == 0:
            # Then we're done
            return

        self.diff_pixels = [(idx, (self.a[idx], self.b[idx]))
                            for idx in islice(izip(*diffs), 0, self.numdiffs)]
        self.diff_ratio = float(self.total_diffs) / float(len(self.a.flat))

    def _report(self, fileobj):
        if self.diff_dimensions:
            fileobj.write('  Data dimensions differ:\n')
            fileobj.write('   a: %s\n' %
                          ' x '.join(reversed(self.diff_dimensions[0])))
            fileobj.write('   b: %s\n' %
                          ' x '.join(reversed(self.diff_dimensions[1])))
            # For now we don't do any further comparison if the dimensions
            # differ; though in the future it might be nice to be able to
            # compare at least where the images intersect
            fileobj.write('  No further data comparison performed.\n')
            return

        if not self.diff_pixels:
            return

        for index, values in self.diff_pixels:
            index = [x + 1 for x in reversed(index)]
            fileobj.write('  Data differs at %s:\n' % index)
            report_diff_values(fileobj, values[0], values[1])

        fileobj.write('  ...\n')
        fileobj.write('  %d different pixels found (%.2f%% different).\n' %
                      (self.total_diffs, self.diff_ratio * 100))


class RawDataDiff(ImageDataDiff):
    """
    RawDataDiff is just a special case of ImageDataDiff where the images are
    one-dimensional, and the data is treated as bytes instead of pixel values.
    """

    def __init__(self, a, b, numdiffs=10):
        self.diff_dimensions = ()
        self.diff_bytes = []

        super(RawDataDiff, self).__init__(a, b, numdiffs=numdiffs)

    def _diff(self):
        super(RawDataDiff, self)._diff()
        if self.diff_dimensions:
            self.diff_dimensions = (self.diff_dimensions[0][0],
                                    self.diff_dimensions[1][0])

        self.diff_bytes = [(x[0], y) for x, y in self.diff_pixels]
        del self.diff_pixels

    def _report(self, fileobj):
        if self.diff_dimensions:
            fileobj.write('  Data sizes differ:\n')
            fileobj.write('   a: %d bytes\n' % self.diff_dimensions[0])
            fileobj.write('   b: %d bytes\n' % self.diff_dimensions[1])
            # For now we don't do any further comparison if the dimensions
            # differ; though in the future it might be nice to be able to
            # compare at least where the images intersect
            fileobj.write('  No further data comparison performed.\n')
            return

        if not self.diff_bytes:
            return

        for index, values in self.diff_bytes:
            fileobj.write('  Data differs at byte %d:\n' % index)
            report_diff_values(fileobj, values[0], values[1])

        fileobj.write('  ...\n')
        fileobj.write('  %d different bytes found (%.2f%% different).\n' %
                      (self.total_diffs, self.diff_ratio * 100))

class TableDataDiff(_GenericDiff):
    def __init__(self, a, b, ignore_fields=[], numdiffs=10, tolerance=0.0):
        self.ignore_fields = set(ignore_fields)
        self.numdiffs = numdiffs
        self.tolerance = tolerance

        self.common_columns = []
        self.diff_column_count = ()
        self.diff_columns = ()
        self.diff_values = []

        self.diff_ratio = 0
        self.total_diffs = 0

        super(TableDataDiff, self).__init__(a, b)

    def _diff(self):
        # Much of the code for comparing columns is similar to the code for
        # comparing headers--consider refactoring
        colsa = self.a.columns
        colsb = self.b.columns

        if len(colsa) != len(colsb):
            self.diff_column_count = (len(colsa), len(colsb))

        # Even if the number of columns are unequal, we still do comparison of
        # any common columns
        colsa = set(colsa)
        colsb = set(colsb)

        self.common_columns = sorted(colsa.intersection(colsb))

        if '*' in self.ignore_fields:
            # If all columns are to be ignored, ignore any further differences
            # between the columns
            return

        # It might be nice if there were a cleaner way to do this, but for now
        # it'll do
        for fieldname in self.ignore_fields:
            fieldname = fieldname.lower()
            for col in list(colsa):
                if col.name.lower() == fieldname:
                    colsa.remove(col)
            for col in list(colsb):
                if col.name.lower() == fieldname:
                    colsb.remove(col)

        left_only_columns = sorted(colsa.difference(colsb))
        right_only_columns = sorted(colsb.difference(colsa))

        if left_only_columns or right_only_columns:
            self.diff_columns = (left_only_columns, right_only_columns)

        # Like in the old fitsdiff, compare tables on a column by column basis
        # The difficulty here is that, while FITS column names are meant to be
        # case-insensitive, PyFITS still allows, for the sake of flexibility,
        # two columns with the same name but different case.  When columns are
        # accessed in FITS tables, a case-sensitive is tried first, and failing
        # that a case-insensitive match is made.
        # It's conceivable that the same column could appear in both tables
        # being compared, but with different case.
        # Though it *may* lead to inconsistencies in these rare cases, this
        # just assumes that there are no duplicated column names in either
        # table, and that the column names can be treated case-insensitively.
        for col in self.common_columns:
            cola = self.a[col.name]
            colb = self.b[col.name]
            if np.issubdtype(cola, float) and np.issubdtype(colb, float):
                diffs = where_not_allclose(cola, colb, atol=0.0,
                                           rtol=self.tolerance)
            else:
                diffs = np.where(cola != colb)

            self.total_diffs += len(diffs[0])

            if len(self.diff_values) < self.numdiffs:
                # Don't save any more diff values
                continue

            # Add no more diff'd values than this
            max_diffs = self.numdiffs - len(self.diff_values)

            self.diff_values += [
                (idx, (self.a[idx], self.b[idx]))
                for idx in islice(izip(*diffs), 0, max_diffs)
            ]

        total_values = len(self.a) * len(self.a.dtype.fields)
        self.diff_ratio = float(self.total_diffs) / float(total_values)

    def _report(self, fileobj):
        pass


def diff_values(a, b, tolerance=0.0):
    """
    Diff two scalar values.  If both values are floats they are compared to
    within the given relative tolerance.
    """

    # TODO: Handle ifs and nans
    if isinstance(a, float) and isinstance(b, float):
        return not np.allclose(a, b, tolerance, 0.0)
    else:
        return a != b


def report_diff_values(fileobj, a, b):
    """Write a diff between two values to the specified file object."""

    #import pdb; pdb.set_trace()
    for line in difflib.ndiff(str(a).splitlines(), str(b).splitlines()):
        if line[0] == '-':
            line = 'a>' + line[1:]
        elif line[0] == '+':
            line = 'b>' + line[1:]
        else:
            line = ' ' + line
        fileobj.write('   %s\n' % line.rstrip('\n'))


def report_diff_keyword_attr(fileobj, attr, diffs, keyword):
    if keyword in diffs:
        vals = diffs[keyword]
        for idx, val in enumerate(vals):
            if val is None:
                continue
            if idx == 0:
                ind = ''
            else:
                ind = '[%d]' % (idx + 1)
            fileobj.write('  Keyword %-8s%s has different %s:\n' %
                          (keyword, ind, attr))
            report_diff_values(fileobj, val[0], val[1])


def where_not_allclose(a, b, rtol=1e-5, atol=1e-8):
    """
    A version of numpy.allclose that returns the indices where the two arrays
    differ, instead of just a boolean value.
    """

    # TODO: Handle ifs and nans
    if atol == 0.0 and rtol == 0.0:
        # Use a faster comparison for the most simple (and common) case
        return np.where(a != b)
    return np.where(np.abs(a - b) > (atol + rtol * np.abs(b)))


def compare_dim (im1, im2):

    """Compare the dimensions of two images

    If the two images (extensions) have the same dimensions and are
    not zero, return the dimension as a list, i.e.
    [NAXIS, NAXIS1, NAXIS2,...].  Otherwise, return None.

    """

    global nodiff

    dim1 = []
    dim2 = []

    # compare the values of NAXIS first
    dim1.append(im1.header['NAXIS'])
    dim2.append(im2.header['NAXIS'])
    if dim1[0] != dim2[0]:
        nodiff = 0
        print "Input files have different dimensions"
        return None
    if dim1[0] == 0:
        print "Input files have naught dimensions"
        return None

    # compare the values of NAXISi
    for k in range(dim1[0]):
        dim1.append(im1.header['NAXIS'+`k+1`])
        dim2.append(im2.header['NAXIS'+`k+1`])
    if dim1 != dim2:
        nodiff = 0
        print "Input files have different dimensions"
        return None

    return dim1

#-------------------------------------------------------------------------------
def compare_table (img1, img2, delta, maxdiff, dim, xtension, field_excl_list):

    """Compare data in FITS tables"""

    global nodiff

    ndiff = 0

    ncol1 = img1.header['TFIELDS']
    ncol2 = img2.header['TFIELDS']
    if ncol1 != ncol2:
        print "Different no. of columns: file1 has %d, file2 has %d" % (ncol1, ncol2)
        nodiff = 0
    ncol = min(ncol1, ncol2)

    # check for None data
    if img1.data is None or img2.data is None:
        if img1.data is None and img2.data is None:
            return
        else:
            print "One file has no data and the other does."
            nodiff = 0

    # compare the tables column by column
    for col in range(ncol):
        field1 = img1.header['TFORM'+`col+1`]
        field2 = img2.header['TFORM'+`col+1`]
        if field1 != field2:
            print "Different data type at column %d: file1 is %s, file2 is %s" % (col, field1, field2)
            continue

        name1 = img1.data.names[col].upper()
        name2 = img2.data.names[col].upper()
        if name1 in field_excl_list or name2 in field_excl_list:
            continue

        found = diff_num (img1.data.field(col), img2.data.field(col), delta)

        _ndiff = found[0].shape[0]
        ndiff += _ndiff
        nprint = min(maxdiff, _ndiff)
        maxdiff -= _ndiff
        dim = len(found)
        base1 = np.ones(dim)
        if nprint > 0:
            print "    Data differ at column %d: " % (col+1)
            index = np.zeros(dim)

            for p in range(nprint):

                # start from the fastest axis
                for i in range(dim):
                    index[i] = found[i][p]

                # translate the 0-based 1-D locations to 1-based
                # naxis-D locations.  Also the "fast axes"
                # order is properly treated here.
                loc = index[-1::-1] + base1
                index_ = tuple(index)
                if (dim) == 1:
                    str = ''
                else:
                    str = ' at %s,' % loc[:-1]
                print "      Row %3d, %s file 1: %16s    file 2: %16s" % (loc[-1], str, img1.data.field(col)[index_], img2.data.field(col)[index_])


    print '    There are %d different data points.' % ndiff
    if ndiff > 0:
        nodiff = 0

#-------------------------------------------------------------------------------
def compare_img (img1, img2, delta, maxdiff, dim):

    """Compare the image data"""

    global nodiff

    ndiff = 0

    thresh = delta
    bitpix = img1.header['BITPIX']
    if (bitpix > 0): thresh = 0     # for integers, exact comparison is made

    # compare the two images
    found = diff_num (img1.data, img2.data, thresh)

    ndiff = found[0].shape[0]
    nprint = min(maxdiff, ndiff)
    dim = len(found)
    base1 = np.ones(dim, dtype=np.int16)
    if nprint > 0:
        index = np.zeros(dim, dtype=np.int16)

        for p in range(nprint):

            # start from the fastest axis
            for i in range(dim):
                index[i] = int(found[i][p])
            # translate the 0-based 1-D locations to 1-based
            # naxis-D locations.  Also the "fast axes" order is
            # properly treated here.
            loc = index[-1::-1] + base1
            index_ = tuple(index)
            print "    Data differ at %16s, file 1: %11.5G file 2: %11.5G" % (list(loc), img1.data[index_], img2.data[index_])

    print '    There are %d different data points.' % ndiff
    if ndiff > 0:
        nodiff = 0
