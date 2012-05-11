import os
import textwrap

from collections import defaultdict

import numpy as np
from numpy import char

import pyfits
from pyfits.util import StringIO


class FitsDiff(object):
    def __init__(self, input1, input2, ignore_keywords=[], ignore_comments=[],
                 ignore_fields=[], numdiffs=10, tolerance=0.0,
                 ignore_blanks=True):

        if isinstance(input1, basestring):
            self.a = pyfits.open(input1)
            close_input1 = True
        else:
            self.a = input1
            close_input1 = False

        if isinstance(input2, basestring):
            self.b = pyfits.open(input2)
            close_input2 = True
        else:
            self.b = input2
            close_input2 = False

        self.ignore_keywords = set(ignore_keywords)
        self.ignore_comments = set(ignore_comments)
        self.ignore_fields = set(ignore_fields)
        self.numdiffs = numdiffs
        self.tolerance = tolerance
        self.ignore_blanks = ignore_blanks

        # General comparison attributes
        self.num_extensions = (1, 1)

        self.data_dimensions = []

        # Table comparison attributes
        self.num_columns = []
        self.common_columns = []
        self.left_only_columns = []
        self.right_only_columns = []
        self.different_column_indexes = []
        self.different_column_formats = []
        self.different_cell_values = []

        try:
            self._diff()
        finally:
            if close_input1:
                self.a.close()
            if close_input2:
                self.b.close()

    def __nonzero__(self):
        return self.identical

    @property
    def identical(self):
        return (self.num_extensions[0] == self.num_extensions[1] and
                not any(self.left_only_keywords) and
                not any(self.right_only_keywords) and
                not any(self.left_only_duplicate_keywords) and
                not any(self.right_only_duplicate_keywords) and
                not any(self.different_keyword_values) and
                not any(self.different_keyword_comments))

    def report(self, fileobj=None):
        if fileobj is None:
            fileobj = StringIO()

        wrapper = textwrap.TextWrapper(initial_indent='  ',
                                       subsequent_indent='  ')
        # print out heading and parameter values
        fileobj.write("\n fitsdiff: %s\n" % pyfits.__version__)
        fileobj.write(" a: %s\n b: %s\n" % (self.a, self.b))
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
        fileobj.write(" Maximum number of different pixels to be reported:\n"
                      "%s\n" % self.numdiffs)
        fileobj.write(" Data comparison level: %s\n" % self.threshold)

        for idx in min(self.num_extensions):
            self.report_hdu(idx, fileobj)

        if isinstance(fileobj, StringIO):
            return fileobj.getvalue()

    def report_hdu(self, idx, fileobj=None):
        if fileobj is None:
            fileobj = StringIO()

        # print out the extension heading
        if idx == 0:
            fileobj.write("\nPrimary HDU:\n")
        else:
            xtensiona = self.a[idx].header['XTENSION']
            xtensionb = self.b[idx].header['XTENSION']
            if xtensiona.lower() != xtensionb.lower():
                fileobj.write("\nExtension %d HDU:\n a: %s\n b: %s\n" %
                              (idx, xtensiona, xtensionb))
                fileobj.write(" Extension types differ.\n")
            fileobj.write("\n%s Extension %d\n" % (xtensiona, idx))

        if isinstance(fileobj, StringIO):
            return fileobj.getvalue()

    def _diff(self):
        # TODO: Currently having a different number of HDUs is automatic
        # grounds for failure; instead consider an option to compare just the
        # first n HDUs (until one file or the other runs out of HDUs), or
        # possibly also provide the ability to select specific HDUs to compare,
        # rather than the whole file!

        # compare numbers of extensions
        self.num_extensions = (len(self.a), len(self.b))

        # compare extension header and data
        for hdua, hdub in zip(self.a, self.b):
            self._diff_headers(hdua, hdub)
            self._diff_data(hdua, hdub)

    def _diff_data(self, hdua, hdub):
        # Compare the data
        # First, get the dimensions of the data
        shapea = hdua.data.shape if hdua.data is not None else ()
        shapeb = hdub.data.shape if hdub.data is not None else ()
        self.data_dimensions.append((shapea, shapeb))
        if self.data_dimensions[-1][0] != self.data_dimensions[-1][1]:
            # No sense in comparing data with different dimensions
            # TODO: We could, however, try comparing the intersection between
            # the two arrays so long as they have the same number of dimensions
            return

            # if the extension is tables
            if (hdua.data.dtype.fields is not None and
                hdub.data.dtype.fields is not None):
                self._diff_table(hdua.data, hdub.data)
            elif (hdu.data.dtype.fields is None and
                  hdub.data.dtype.fields is None):
                self._diff_image(hdua.data, hdub.data)
            else:
                # TODO: Figure out what to do here....
                # Perhaps we could coerce a table into a normal array or
                # vice-versa; though it might be safer to just register that
                # the data are fundamentally different and no further
                # comparison is possible
                pass

    def _diff_table(self, tablea, tableb):
        # Diff the column definitions
        colsa = tablea.columns
        colsb = tableb.columns

        self.num_columns.append((len(colsa), len(colsb)))

        namesa = set(colsa)
        namesb = set(colsb)
        common = []
        left_only = []
        right_only = []
        different_indexes = {}
        different_formats = {}
        for idx, cola, colb in zip(xrange(min(len(colsa), len(colsb))),
                                   colsa, colsb):
            if cola.name != colb.name:
                if cola.name not in namesb:
                    # The tables do not share these columns at all
                    left_only.append(cola.name)
                    right_only.append(colb.name)
                    continue
                # The tables do share these columns but they're in a different
                # order
                idxb = namesb.index(cola.name)
                if cola.name not in different_indexes:
                    different_indexes[cola.name] = (idx, idxb)

            common.append(cola.name)
            if cola.format != colb.format:
                different_formats[cola.name] = (cola.format, colb.format)

        if self.ignore_fields == ['*']:
            return


    def _diff_image(self, hdua, hdub):
        pass


class _GenericDiff(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b
        self._diff()

    @property
    def identical(self):
        return not any(getattr(self, attr) for attr in self.__dict__
                       if attr.startswith('diff_'))

    def _diff(self):
        raise NotImplementedError


class HDUDiff(_GenericDiff):
    pass


class HeaderDiff(_GenericDiff):
    def __init__(self, a, b, ignore_keywords=[], ignore_comments=[],
                 tolerance=0.0, ignore_blanks=True):
        self.ignore_keywords = set(ignore_keywords)
        self.ignore_comments = set(ignore_comments)
        self.tolerance = tolerance
        self.ignore_blanks = ignore_blanks

        # Keywords appearing in each header
        self.common_keywords = []

        # Set to the number of keywords in each header if the counts differ
        self.diff_keyword_count = ()

        # Set if the keywords common to each header (excluding ignore_keywords)
        # appear in different positions within the header
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

            counta = len(valuesa[keyword])
            countb = len(valuesb[keyword])
            if counta != countb:
                self.diff_duplicate_keywords[keyword] = (counta, countb)

            # Compare keywords' values and comments
            for a, b in zip(valuesa[keyword], valuesb[keyword]):
                if isinstance(a, float) and isinstance(b, float):
                    if not np.allclose(a, b, self.tolerance, 0.0):
                        self.diff_keyword_values[keyword].append((a, b))
                elif a != b:
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

            for a, b in zip(commentsa[keyword], commentsb[keyword]):
                if a != b:
                    self.diff_keyword_comments[keyword].append((a, b))
                else:
                    self.diff_keyword_comments[keyword].append(None)

            if not any(self.diff_keyword_comments[keyword]):
                del self.diff_keyword_comments[keyword]


class DataDiff(_GenericDiff):
    pass
    # if there is no difference
    #if nodiff:
    #    print "\nNo difference is found."

    # close files
    #im1.close()
    #im2.close()

    # reset sys.stdout back to default
    #sys.stdout = sys.__stdout__
    #return nodiff

#-------------------------------------------------------------------------------
def row_parse (row, img):

    """Parse a row in a text table into a list of values

    These value correspond to the fields (columns).

    """

    result = []

    for col in range(len(row)):

        # get the format (e.g. I8, A10, or G25.16) of the field (column)
        tform = img.header['TFORM'+str(col+1)]

        item = row[col].strip()

        # evaluate the substring
        if (tform[0] != 'A'):
            item = eval(item)
        result.append(item)
    return result

#-------------------------------------------------------------------------------
def compare_keyword_value (dict1, dict2, keywords_to_skip, name, delta):

    """ Compare header keyword values

    compare header keywords' values by using the value dictionary,
    the value(s) for each keyword is in the form of a list.  Don't do
    the comparison if the keyword is in the keywords_to_skip list.

    """

    global nodiff                   # no difference flag

    keys = dict1.keys()
    keys.sort()

    for kw in keys:
        if kw in dict2.keys() and kw not in keywords_to_skip:
            values1 = dict1[kw]
            values2 = dict2[kw]

            # if the same keyword has different number of entries
            # in different files, it is regarded as extra and will
            # be dealt with in a separate routine.
            nvalues = min(len(values1), len(values2))
            for i in range(nvalues):

                if diff_obj(values1[i], values2[i], delta):
                    indx = ''
                    if i > 0: indx = `[i+1]`

                    print "  Keyword %-8s%s has different values: " % (kw, indx)
                    print '    %s: %s' % (name[0], values1[i])
                    print '    %s: %s' % (name[1], values2[i])
                    nodiff = 0

#-------------------------------------------------------------------------------
def compare_keyword_comment (dict1, dict2, keywords_to_skip, name):

    """Compare header keywords' comments

    compare header keywords' comments by using the comment dictionary, the
    comment(s) for each keyword is in the form of a list.  Don't do the
    comparison if the keyword is in the keywords_to_skip list.

    """

    global nodiff                   # no difference flag

    keys = dict1.keys()
    keys.sort()

    for kw in keys:
        if kw in dict2.keys() and kw not in keywords_to_skip:
            comments1 = dict1[kw]
            comments2 = dict2[kw]

            # if the same keyword has different number of entries
            # in different files, it is regarded as extra and it
            # taken care of in a separate routine.
            ncomments = min(len(comments1), len(comments2))
            for i in range(ncomments):
                if comments1[i] != comments2[i]:
                    indx = ''
                    if i > 0: indx = `[i+1]`

                    print '  Keyword %-8s%s has different comments: ' % (kw, indx)
                    print '    %s: %s' % (name[0], comments1[i])
                    print '    %s: %s' % (name[1], comments2[i])
                    nodiff = 0

#-------------------------------------------------------------------------------
def diff_obj (obj1, obj2, delta = 0):

    """Compare two objects

    return 1 if they are different, for two floating numbers, if their
    relative difference is within delta, they are treated as same numbers.

    """

    if isinstance(obj1, float) and isinstance(obj2, float):
        diff = abs(obj2-obj1)
        a = diff > abs(obj1*delta)
        b = diff > abs(obj2*delta)
        return a or b
    else:
        return (obj1 != obj2)

#-------------------------------------------------------------------------------
def diff_num(num1, num2, delta=0):
    """Compare two num/char-arrays

    If their relative difference is larger than delta,
    returns a tuple of index arrays where there is difference.
    The number of elements in the tuple is the dimension of the images
    been compared.  Each index array in the tuple is 1-D and its length is
    the number of differences found.

    """
    # if arrays are chararrays
    if isinstance (num1, char.chararray):
        delta = 0

    # if delta is zero, it is a simple case.  Use the more general __ne__()
    if delta == 0:
        diff = num1.__ne__(num2)        # diff is a boolean array
    else:
        diff = np.absolute(num2-num1)/delta # diff is a float array

    diff_indices = np.nonzero(diff)        # a tuple of (shorter) arrays

    # how many occurrences of difference
    n_nonzero = diff_indices[0].size

    # if there is no difference, or delta is zero, stop here
    if n_nonzero == 0 or delta == 0:
        return diff_indices

    # if the difference occurrence is rare enough (less than one-third
    # of all elements), use an algorithm which saves space.
    # Note: "compressed" arrays are 1-D only.
    elif n_nonzero < (diff.size)/3:
        cram1 = np.compress(diff.__ne__(0.0).ravel(), num1)
        cram2 = np.compress(diff.__ne__(0.0).ravel(), num2)
        cram_diff = np.compress(diff.__ne__(0.0).ravel(), diff)
        a = np.greater(cram_diff, np.absolute(cram1))
        b = np.greater(cram_diff, np.absolute(cram2))
        r = np.logical_or(a, b)
        list = []
        for i in range(len(diff_indices)):
            list.append(np.compress(r, diff_indices[i]))
        return tuple(list)

    # regular and more expensive way
    else:
        a = np.greater(diff, np.absolute(num1))
        b = np.greater(diff, np.absolute(num2))
        r = np.logical_or(a, b)
        return np.nonzero(r)

#-------------------------------------------------------------------------------
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
