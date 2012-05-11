import os
import textwrap

import numpy as np
from numpy import char

import pyfits
from pyfits.util import StringIO


class FitsDiff(object):
    def __init__(self, input1, input2, ignore_keywords=[], ignore_comments=[],
                 ignore_fields=[], numdiffs=10, threshold=0.,
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
        self.threshold = difference_threshold
        self.ignore_blanks = ignore_blanks

        # General comparison attributes
        self.num_extensions = (1, 1)

        # Per-hdu comparison attributes
        self.common_keywords = []
        self.left_only_keywords = []
        self.right_only_keywords = []

        self.left_only_duplicate_keywords = {}
        self.right_only_duplicate_keywords = {}

        self.different_keyword_values = {}
        self.different_keyword_comments = {}

        self.data_dimensions = []

        # Table comparison attributes
        self.num_columns = []

        try:
            self._diff()
        finally:
            if close_input1:
                self.a.close()
            if close_input2:
                self.b.close()

    def __nonzero__(self):
        return self.identical

    @properties
    def identical(self):
        return (self.num_extensions[0] == self.num_extensions[1] and
                not self.left_only_keywords and
                not self.right_only_keywords and
                not self.left_only_duplicate_keywords and
                not self.right_only_duplicate_keywords and
                not self.different_keyword_values and
                not self.different_keyword_comments)

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

    def _diff_headers(self, hdua, hdub):
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

        valuesa, commentsa = get_header_values_comments(hdua.header)
        valuesb, commentsb = get_header_values_comments(hdub.header)

        keywordsa = set(valuesa)
        keywordsb = set(valuesb)

        self.common_keywords = sorted(keywordsa.intersect(keywordsb))
        self.left_only_keywords = sorted(keywordsa.difference(keywordsb))
        self.right_only_keywords = sorted(keywordsb.difference(keywordsa))

        # Compare count of each common keyword
        for keyword in self.common_keywords:
            counta = len(valuesa[keyword])
            countb = len(valuesb[keyword])
            if counta != countb:
                if counta < countb:
                    extra_values = valuesb
                    extra_comments = commentsb
                    target = self.right_only_duplicate_keywords
                else:
                    extra_values = valuesa
                    extra_comments = commentsb
                    target = self.left_only_duplicate_keywords
                _min = min(counta, countb)
                target[keyword] = zip(extra_values[_min:],
                                      extra_comments[_min:])

            # Compare keywords' values and comments
            if ('*' not in self.ignore_keywords and
                keyword not in self.ignore_keywords):
                dkv = self.different_keyword_values.setdefault(keyword, [])
                for a, b in zip(valuesa[keyword], valuesb[keyword]):
                if isinstance(a, float) and isinstance(b, float):
                    delta = abs(a - b)
                    if delta > self.threshold:
                        dkv.append((a, b))
                elif a != b:
                    dkv.append((a, b))

            if ('*' not in self.ignore_comments and
                keyword not in self.ignore_comments):
                dkc = self.different_keyword_comments.setdefault(keyword, [])
                for a, b in zip(commentsa[keyword], commentsb[keyword]):
                    dkc.append((a, b))

    def _diff_data(self, hdua, hdub):
        # Compare the data
        # First, get the dimensions of the data
        shapea = hdua.data.shape if hdua.data is not None else ()
        shapeb = hdub.data.shape if hdub.data is not None else ()
        self.data_dimensions.append((shapea, shapeb))
        if self.data_dimensions[-1][0] != self.data_dimensions[-1][1]:
            # No sense in comparing data with different dimensions
            return

            # if the extension is tables
            if xtension in ('BINTABLE', 'TABLE'):
                self._diff_table()
            else:
                compare_img(im1[i], im2[i], delta, _maxdiff, dim)

    def _diff_table(self, tablea, tableb):
        if self.ignore_fields == ['*']:
            return
        fieldsa = len(hdua.data.dtype.descr


    def _diff_image(self, hdua, hdub):
        pass

    # if there is no difference
    if nodiff:
        print "\nNo difference is found."

    # close files
    im1.close()
    im2.close()

    # reset sys.stdout back to default
    sys.stdout = sys.__stdout__
    return nodiff

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

#-------------------------------------------------------------------------------
def attach_dir (dirname, list):

    """Attach a directory name to a list of file names"""

    import os

    new_list = list[:]
    for i in range(len(new_list)):
        basename = os.path.basename(new_list[i])
        new_list[i] = os.path.join(dirname, basename)
    return new_list

#-------------------------------------------------------------------------------
def parse_path(f1, f2):

    """Parse two input arguments and return two lists of file names"""

    import glob, os

    if os.path.isdir(f1):

        # if both arguments are directory, use all files
        if os.path.isdir(f2):
            f1 = os.path.join(f1, '*')
            f2 = os.path.join(f2, '*')

        # if one is directory, one is not, recreate the first by
        # attaching the directory name to the other.
        # use glob to parse the wild card, if any
        else:
            list2 = glob.glob(f2)
            list1 = attach_dir (f1, list2)
            return list1, list2
    else:
        if os.path.isdir(f2):
            list1 = glob.glob(f1)
            list2 = attach_dir (f2, list1)
            return list1, list2

    list1 = glob.glob(f1)
    list2 = glob.glob(f2)

    if (list1 == [] or list2 == []):
        str = ""
        if (list1 == []): str += "File `%s` does not exist.  " % f1
        if (list2 == []): str += "File `%s` does not exist.  " % f2
        raise IOError, str
    else:
        return list1, list2



