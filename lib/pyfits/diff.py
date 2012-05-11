#!/usr/bin/env python

# $Id: fitsdiff.py 13225 2011-06-22 23:24:07Z embray $

"""
        fitsdiff: Compare two FITS image files and report the differences
                in header keywords and data.

        License: http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE

        :Usage:
            The basic use of this module has the following syntax::

                fitsdiff.py [options] filename1 filename2

            where filename1 filename2 are the two files to be compared.
            they can be wild cards, in such cases, they must be enclosed
            by double or single quotes.  they can also be directory names:
            if both are directory names, all files in each of the
            directories will be included, if only one is directory name,
            then the directory name will be prefixed to the file name(s)
            specified by the other argument.  for example::

                    fitsdiff.py "*.fits" "/machine/data1"

            will compare all FITS files in the current directory to the
            corresponding files in the directory /machine/data1

            Options are one or more of:

            -c  (list of keywords)
                    a list of keywords whose comments will not be compared.
                    If want to exclude all keywords, use "*", make sure to
                    have double or single quotes around the asterisk.
                    default = None
            -k  (list of keywords)
                    a list of keywords not to be compared.
                    If want to exclude all keywords, use "*", make sure to
                    have double or single quotes around the asterisk.
                    default = None
            -f  (list of column names)
                    a list of fields (i.e. columns) not to be compared.
                    If want to exclude all columns, use "*", make sure to
                    have double or single quotes around the asterisk.
                    default = None
            -n  (non-negative integer)
                    max number of different data (image pixel or table
                    element) to report per extension,
                    default = 10
            -d  (non-negative number)
                    relative difference level below which data are
                    considered equal, this criterion only applies to
                    floating point numbers, both data and keyword values,
                    it does not apply to integers.
                    default = 0.
            -b
                    means trailing blanks in string values (both in header
                    keywords and column values) are significant, i.e.
                    'ABC   ' and 'ABC' mean different things if this
                    swithch is set.
            -o  (output file name)
                    output file name where the result goes
            -h
                    print the help (this text)

            If the two files are identical within the specified conditions,
            it will report "No difference is found."
            If the value(s) of -c and -k takes the form '@filename',
            list is in the text file 'filename', and each line in that
            text file contains one keyword.

        :Example:

                fitsdiff.py -k filename,filtnam1 -n 5 -d 1.e-6 test1.fits test2

                this command will compare files test1.fits and test2.fits,
                report maximum of 5 different pixels values per extension, only
                report data values larger than 1.e-6 relative to each other,
                and will neglect the different values of keywords FILENAME
                and FILTNAM1 (or their very existence).


        fitsdiff commandline arguments can also be set using the
        environment variable FITSDIFF_SETTINGS.  If the
        FITSDIFF_SETTINGS environment variable is present, each
        argument present will override the corresponding argument on
        the commandline.  This environment variable exists to make it
        easier to change the behavior of fitsdiff on a global level,
        such as in a set of regression tests.
"""
# Developed by Science Software Group, STScI, USA.
__version__ = "1.5 (28 Feb 2011)"

import os, sys, types
import pyfits
import numpy as num
from numpy import char

def fitsdiff (input1, input2, comment_excl_list='', value_excl_list='', field_excl_list='', maxdiff=10, delta=0., neglect_blanks=1, output=None):

    global nodiff

    # if sending output somewhere?
    if output:
        if type(output) == types.StringType:
            outfd = open(output, 'w')
        else:
            outfd = output
        sys.stdout = outfd

    fname = (input1, input2)

    # Parse lists of excluded keyword values and/or keyword comments.
    value_excl_list = list_parse(value_excl_list)
    comment_excl_list = list_parse(comment_excl_list)
    field_excl_list = list_parse(field_excl_list)

    # print out heading and parameter values
    print "\n fitsdiff: ", __version__
    print " file1 = %s\n file2 = %s" % fname
    print " Keyword(s) not to be compared: ", value_excl_list
    print " Keyword(s) whose comments not to be compared: ", \
            comment_excl_list
    print " Column(s) not to be compared: ", field_excl_list
    print " Maximum number of different pixels to be reported: ", maxdiff
    print " Data comparison level: ", delta

    nodiff = 1                              # difference-free flag

    # open input files
    im1 = open_and_read(input1)
    im2 = open_and_read(input2)

    # compare numbers of extensions
    nexten1, nexten2 = len(im1), len(im2)
    if nexten1 != nexten2:
        raise RuntimeError("Different no. of HDU's: file1 has %d, file2 has %d" % (nexten1, nexten2))

    # compare extension header and data
    for i in range(nexten1):

        # print out the extension heading
        if i == 0:
            xtension = ''
            print "\nPrimary HDU:"
        else:
            xtension = im1[i].header['XTENSION'].strip()
            print "\n%s Extension %d HDU:" % (xtension, i)

        # build dictionaries of keyword values and comments
        (dict_value1, dict_comment1) = keyword_dict(im1[i].header.ascard, neglect_blanks)
        (dict_value2, dict_comment2) = keyword_dict(im2[i].header.ascard, neglect_blanks)

        # pick out the "extra" keywords
        extra_keywords(dict_value1, dict_value2, fname)

        # compare keywords' values and comments
        if value_excl_list != ['*']:
            compare_keyword_value(dict_value1, dict_value2, \
                                    value_excl_list, fname, delta)
        if comment_excl_list != ['*']:
            compare_keyword_comment(dict_comment1, dict_comment2, \
                                    comment_excl_list, fname)

        # compare the data
        # First, get the dimensions of the data
        dim = compare_dim(im1[i], im2[i])

        _maxdiff = max(0, maxdiff)
        if dim != None:

            # if the extension is tables
            if xtension in ('BINTABLE', 'TABLE'):
                if field_excl_list != ['*']:
                    compare_table(im1[i], im2[i], delta, _maxdiff, dim, xtension, field_excl_list)
            else:
                compare_img(im1[i], im2[i], delta, _maxdiff, dim)

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
def list_parse (name_list):

    """ Parse a name list (a string list, not a Python list)

    including the case when the list is in a text file, each string
    value is in a different line

    """

    # list in a text file
    if (len(name_list) > 0 and name_list[0] == '@'):
        try:
            fd = open(name_list[1:])
            text = fd.read()
            fd.close()
            kw_list = (text.upper()).split()

            # if the file only have blanks
            if kw_list == []: kw_list = ['']
            return kw_list
        except IOError:
            print "CAUTION: File %s does not exist, assume null list" % name_list[1:]
            return([''])

    else:
        return (name_list.upper()).split(',')

#-------------------------------------------------------------------------------
def open_and_read (filename):
    """Open and read in the whole FITS file"""
    try:
        im = pyfits.open(filename)
    except IOError:
        raise IOError, "\nCan't open or read file %s" % filename

    return im

#-------------------------------------------------------------------------------
def keyword_dict(header, neglect_blanks=1):

    """Build dictionaries of header keyword values and comments.
    Each dictionary item's value list, so we can pick out keywords with
    duplicate entries, including COMMENT and HISTORY, and if they are
    out of order.

    Input parameter, header, is a FITS HDU header.

    Output is a 2-element tuple of dictionaries of keyword values and
    keyword comments respectively.

    """

    dict_value = {}
    dict_comment = {}

    for key in header.keys():
        keyword = key
        value = header[key].value
        try:
            comment = header[key].comment
        except:
            comment = ''
        # keep trailing blanks for a string value?
        if type(value) == types.StringType and neglect_blanks:
            value = value.rstrip()

        # existing keyword
        if dict_value.has_key(keyword):
            dict_value[keyword].append(value)
            dict_comment[keyword].append(comment)

        # new keyword
        else:
            dict_value[keyword] = [value]
            dict_comment[keyword] = [comment]

    return (dict_value, dict_comment)

#-------------------------------------------------------------------------------
def extra_keywords (dict1, dict2, name):

    """Pick out extra keywords between the two input dictionaries

    each dictionary's value is a list, this routine also works if the same
    keyword has different number of values in diffferent dictionary.

    name is a 2-element tuple of files names corresponding to
    dictionaries dict1 and dict2.

    """

    global nodiff

    keys = dict1.keys()
    keys.sort()

    for kw in keys:
        if kw not in dict2.keys():
            nodiff = 0
            print "  Extra keyword %-8s in %s" % (kw, name[0])
        else:

            # compare the number of occurrence
            nval1 = len(dict1[kw])
            nval2 = len(dict2[kw])
            if nval1 != nval2:
                nodiff = 0
                print "  Inconsistent occurrence of keyword %-8s %s has %d, %s has %d" % (kw, name[0], nval1, name[1], nval2)

    for kw in dict2.keys():
        if kw not in dict1.keys():
            nodiff = 0
            print "  Extra keyword %-8s in %s" % (kw, name[1])

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

    if type(obj1) == types.FloatType and type(obj2) == types.FloatType:
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
#    num1 = num.asarray(num1)
#    num2 = num.asarray(num2)
    # if arrays are chararrays
    if isinstance (num1, char.chararray):
        delta = 0

    # if delta is zero, it is a simple case.  Use the more general __ne__()
    if delta == 0:
        diff = num1.__ne__(num2)        # diff is a boolean array
    else:
        diff = num.absolute(num2-num1)/delta # diff is a float array

    diff_indices = num.nonzero(diff)        # a tuple of (shorter) arrays

    # how many occurrences of difference
    n_nonzero = diff_indices[0].size

    # if there is no difference, or delta is zero, stop here
    if n_nonzero == 0 or delta == 0:
        return diff_indices

    # if the difference occurrence is rare enough (less than one-third
    # of all elements), use an algorithm which saves space.
    # Note: "compressed" arrays are 1-D only.
    elif n_nonzero < (diff.size)/3:
        cram1 = num.compress(diff.__ne__(0.0).ravel(), num1)
        cram2 = num.compress(diff.__ne__(0.0).ravel(), num2)
        cram_diff = num.compress(diff.__ne__(0.0).ravel(), diff)
        a = num.greater(cram_diff, num.absolute(cram1))
        b = num.greater(cram_diff, num.absolute(cram2))
        r = num.logical_or(a, b)
        list = []
        for i in range(len(diff_indices)):
            list.append(num.compress(r, diff_indices[i]))
        return tuple(list)

    # regular and more expensive way
    else:
        a = num.greater(diff, num.absolute(num1))
        b = num.greater(diff, num.absolute(num2))
        r = num.logical_or(a, b)
        return num.nonzero(r)

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
        base1 = num.ones(dim)
        if nprint > 0:
            print "    Data differ at column %d: " % (col+1)
            index = num.zeros(dim)

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
    base1 = num.ones(dim, dtype=num.int16)
    if nprint > 0:
        index = num.zeros(dim, dtype=num.int16)

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


#-------------------------------------------------------------------------------
# a main program for running fitsdiff from the command line


def main() :

    import getopt

    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'c:k:f:n:d:o:bh')
    except getopt.error, e:
        print str(e)
        print __doc__
        print "\t", __version__

    if 'FITSDIFF_SETTINGS' in os.environ:
        optlist_argv = os.environ['FITSDIFF_SETTINGS'].split()
        optlist_env, optlist_args = getopt.getopt(optlist_argv, 'c:k:f:n:d:o:bh')
        optlist += optlist_env

    # initialize default values
    help = 0
    comment_excl_list = ''
    value_excl_list = ''
    field_excl_list = ''
    maxdiff = 10
    delta = 0.
    output = None
    neglect_blanks = 1

    # read options
    for opt, value in optlist:
        if opt == "-c":
            comment_excl_list = value
        elif opt == "-k":
            value_excl_list = value
        elif opt == "-f":
            field_excl_list = value
        elif opt == "-n":
            maxdiff = eval(value)
        elif opt == "-d":
            delta = eval(value)

            # delta must be positive
            if delta < 0:
                delta = 0
        elif opt == "-o":
            output = value
        elif opt == "-b":
            neglect_blanks = 0
        elif opt == "-h":
            help = 1

    if (help):
        print __doc__
        print "\t", __version__
        return 0
    else:
        if len(args) == 2:
            (list1, list2) = parse_path (args[0], args[1])
            npairs = min (len(list1), len(list2))
            nodiff = 1
            for i in range(npairs):

                # fitsdiff() returns 1 for same, 0 for different
                if not fitsdiff(list1[i], list2[i], comment_excl_list, value_excl_list, field_excl_list, maxdiff, delta, neglect_blanks, output) :
                    nodiff = 0

            if nodiff :
                return 0
            else :
                return 1

        else:
            print "Needs pair(s) of input files.  Use -h for help"
            return 2


if __name__ == "__main__":
    sys.exit(main())


"""
Copyright (C) 2003 Association of Universities for Research in Astronomy (AURA)

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.

    3. The name of AURA and its representatives may not be used to
      endorse or promote products derived from this software without
      specific prior written permission.

THIS SOFTWARE IS PROVIDED BY AURA ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL AURA BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
DAMAGE.
"""
