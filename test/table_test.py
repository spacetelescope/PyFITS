"""
>>> import pyfits
>>> import os
>>> import numarray as num
>>> import numarray.strings as chararray

# open some existing FITS files:
>>> tt=pyfits.open('tb.fits')
>>> fd=pyfits.open('test0.fits')

# create some local arrays
>>> a1=chararray.array(['abc','def','xx'])
>>> r1=num.array([11.,12.])

# create a table from scratch, using a mixture of columns from existing
# tables and locally created arrays:

# first, create individual column definitions

>>> c1=pyfits.Column(name='abc',format='3A', array=a1)
>>> c2=pyfits.Column(name='def',format='E', array=r1)
>>> c3=pyfits.Column(name='xyz',format='I', array=num.array([3,4,5]))
>>> c4=pyfits.Column(name='t1', format='I', array=tt[1].data.field(0))
>>> c5=pyfits.Column(name='t2', format='C', array=num.array([3+3j,4+4j,5+5j]))

# second, create a column-definitions object for all columns in a table

>>> x=pyfits.ColDefs([c1,c2,c3,c4,c5])

# create a new binary table HDU object by using the new_table function
# Note that the data array for each field has different length, the new
# table will have the length of the longest array.

>>> tbhdu=pyfits.new_table(x)

# another way to create a table is by using existing table's information:

>>> x2=pyfits.ColDefs(tt[1])
>>> t2=pyfits.new_table(x2, nrows=3)
>>> print t2.data
RecArray[
(1, 'abc', 3.7000002861022949, 0),
(2, 'xy', 6.6999998092651367, 1),
(0, ' ', 0.40000000596046448, 0)
]

# the table HDU's data is a subclass of a record array, so we can access
# one row like this:

>>> print tbhdu.data[1]
('def', 12.0, 4, 2, (4+4j))

# and a column like this:

>>> print tbhdu.data.field('abc')
['abc', 'def', 'xx']

# An alternative way to create a column-definitions object is from an
# existing table.
# xx=pyfits.ColDefs(tt[1])

# now we write out the newly created table HDU to a FITS file:
>>> fout = pyfits.HDUList(pyfits.PrimaryHDU())
>>> fout.append(tbhdu)
>>> fout.writeto('tableout1.fits')

# An alternative way to create an output table FITS file:
# fout2=pyfits.open('tableout2.fits','append')
# fout2.append(fd[0])
# fout2.append(tbhdu)
# fout2.close()

# binary table:
>>> t=pyfits.open('tb.fits')
>>> t[1].header['tform1']
'1J'
>>> t[1].columns.info()
name:
     ['c1', 'c2', 'c3', 'c4']
format:
     ['i4', 'a3', 'f4', 'i1']
unit:
     ['', '', '', '']
null:
     [-2147483647, '', '', '']
bscale:
     ['', '', 3, '']
bzero:
     ['', '', 0.40000000000000002, '']
disp:
     ['I11', 'A3', 'G15.7', 'L6']
start:
     ['', '', '', '']
dim:
     ['', '', '', '']

>>> print t[1].data
RecArray[
(1, 'abc', 3.7000002861022949, 0),
(2, 'xy', 6.6999998092651367, 1)
]

# Change scaled field and scale back to the original array
>>> t[1].data.field('c4')[0] = 1
>>> t[1].data._scale_back()
>>> print t[1].data._parent.field('c4')
[84 84]

# look at data column-wise
>>> t[1].data.field(0)
array([1, 2])

# When there are scaled columns, the raw data are in data._parent


# ASCII table
>>> a=pyfits.open('ascii.fits')
>>> print a[1].data
RecArray[
(10.123000144958496, 37),
(5.1999998092651367, 23),
(15.609999656677246, 17),
(0.0, 0),
(345.0, 345)
]

# Test slicing
>>> a2=a[1].data[2:]
>>> print a2
RecArray[
(15.609999656677246, 17),
(0.0, 0),
(345.0, 345)
]
>>> a2.field(1)
array([ 17,   0, 345])
>>> print a[1].data[::2]
RecArray[
(10.123000144958496, 37),
(15.609999656677246, 17),
(345.0, 345)
]

>>> os.remove('tableout1.fits')


"""
import pyfits
import numarray.records as recarray
import numarray as num
import os, sys, string


def test():
    import doctest, table_test
    return doctest.testmod(table_test)

if __name__ == "__main__":
    test()
    print 'The numarray version used is:', num.__version__
    print 'The recarray version used is:', recarray.__version__
    print 'The pyfits version used is:', pyfits.__version__
    sys.exit(0)
