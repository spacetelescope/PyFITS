"""
>>> import pyfits
>>> import os
>>> import numarray as num
>>> import numarray.records as rec
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

# Note that X format must be two-D array
>>> c6=pyfits.Column(name='t3', format='X', array=num.array([[0],[1]]))
>>> c7=pyfits.Column(name='t4', format='J', array=num.array([101,102,103]))

# if there are more flags than needed, they will be truncated
>>> c8=pyfits.Column(name='t5', format='11X', array=num.array([[1,1,0,1,0,1,1,1,0,0,1,1],[0,1,1,1,1,0,0,0,0,1,0,0],[1,1,1,0,0,1,1,1,1,1,1,1]]))

# second, create a column-definitions object for all columns in a table

>>> x=pyfits.ColDefs([c1,c2,c3,c4,c5,c6,c7,c8])

# create a new binary table HDU object by using the new_table function
# Note that the data array for each field has different length, the new
# table will have the length of the longest array.

>>> tbhdu=pyfits.new_table(x)

# another way to create a table is by using existing table's information:

>>> x2=pyfits.ColDefs(tt[1])
>>> t2=pyfits.new_table(x2, nrows=3)
>>> ra = rec.array([
... (1, 'abc', 3.7000002861022949, 0),
... (2, 'xy', 6.6999998092651367, 1),
... (0, ' ', 0.40000000596046448, 0)
... ], names='c1, c2, c3, c4')
>>> comparerecords(t2.data, ra)
True

# the table HDU's data is a subclass of a record array, so we can access
# one row like this:

>>> print tbhdu.data[1]
('def', 12.0, 4, 2, (4+4j), array([1], type=Bool), 102, array([0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0], type=Bool))

# and a column like this:

>>> print tbhdu.data.field('abc')
['abc' 'def' 'xx']

# An alternative way to create a column-definitions object is from an
# existing table.
# xx=pyfits.ColDefs(tt[1])

# now we write out the newly created table HDU to a FITS file:
>>> fout = pyfits.HDUList(pyfits.PrimaryHDU())
>>> fout.append(tbhdu)
>>> fout.writeto('tableout1.fits')

>>> f2 = pyfits.open('tableout1.fits')
>>> temp = f2[1].data.field(7)
>>> print temp[0]
[1 1 0 1 0 1 1 1 0 0 1]

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

>>> comparerecords(t[1].data, ra[:2])
True

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
>>> ra1 = rec.array([
... (10.123000144958496, 37),
... (5.1999998092651367, 23),
... (15.609999656677246, 17),
... (0.0, 0),
... (345.0, 345)
... ], names='c1, c2')
>>> comparerecords(a[1].data, ra1)
True

# Test slicing
>>> a2=a[1].data[2:]
>>> ra2 = rec.array([
... (15.609999656677246, 17),
... (0.0, 0),
... (345.0, 345)
... ], names='c1, c2')
>>> comparerecords(a2, ra2)
True
>>> a2.field(1)
array([ 17,   0, 345])
>>> ra3 = rec.array([
... (10.123000144958496, 37),
... (15.609999656677246, 17),
... (345.0, 345)
... ], names='c1, c2')
>>> comparerecords(a[1].data[::2], ra3)
True

>>> os.remove('tableout1.fits')


"""
import pyfits
import numarray.records as recarray
import numarray as num
import os, sys, string

def comparefloats(a, b):
    """Compare two float scalars or arrays and see if they are consistent
    
    Consistency is determined ensuring the difference is less than the
    expected amount. Return True if consistent, False if any differences"""
    aa = num.ravel(num.array(a))
    bb = num.ravel(num.array(b))
    # compute expected precision
    if aa.type()==num.Float32 or bb.type()==num.Float32:
        precision = 0.000001
    else:
        precision = 0.0000000000000001
    precision = 0.00001 # until precision problem is fixed in pyfits
    diff = num.abs(aa-bb)
    mask0 = aa == 0
    masknz = aa != 0. 
    if num.any(mask0):
        if diff[mask0].max() != 0.:
            return False
    if num.any(masknz):
        if (diff[masknz]/aa[masknz]).max() > precision:
            return False
    return True
    
def comparerecords(a, b):
    """Compare two record arrays
    
    Does this field by field, using approximation testing for float columns
    (Complex not yet handled.)
    Column names not compared, but column types and sizes are.
    """
    nfieldsa = a._nfields
    nfieldsb = b._nfields
    if nfieldsa != nfieldsb:
        print "number of fields don't match"
        return False
    for i in range(nfieldsa):
        fielda = a.field(i)
        fieldb = b.field(i)
        if type(fielda) != type(fieldb):
            print 'field %d type differs' % i
            return False
        if not isinstance(fielda, num.strings.CharArray) and \
               isinstance(fielda.type(), num.FloatingType):
            if not comparefloats(fielda, fieldb):
                print 'field %d differs' % i
                return False
        else:
            if num.any(fielda != fieldb):
                print 'field %d differs' % i
                return False
    return True
    
        
    
def test():
    import doctest, table_test
    return doctest.testmod(table_test)

if __name__ == "__main__":
    test()
    print 'The numarray version used is:', num.__version__
    print 'The recarray version used is:', recarray.__version__
    print 'The pyfits version used is:', pyfits.__version__
    sys.exit(0)
