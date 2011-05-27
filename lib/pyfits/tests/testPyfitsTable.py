from __future__ import division # confidence high
from __future__ import with_statement

import os
import sys
import unittest

import numpy as np
from numpy import char as chararray

import pyfits
from pyfits import rec
from pyfits.util import decode_ascii
from pyfits.tests.util import CaptureStdout


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def comparefloats(a, b):
    """
    Compare two float scalars or arrays and see if they are consistent

    Consistency is determined ensuring the difference is less than the
    expected amount. Return True if consistent, False if any differences.
    """

    aa = a
    bb = b
    # compute expected precision
    if aa.dtype.name=="float32" or bb.dtype.name=='float32':
        precision = 0.000001
    else:
        precision = 0.0000000000000001
    precision = 0.00001 # until precision problem is fixed in pyfits
    diff = np.absolute(aa - bb)
    mask0 = aa == 0
    masknz = aa != 0.
    if np.any(mask0):
        if diff[mask0].max() != 0.:
            return False
    if np.any(masknz):
        if (diff[masknz]/np.absolute(aa[masknz])).max() > precision:
            return False
    return True

def comparerecords(a, b):
    """
    Compare two record arrays

    Does this field by field, using approximation testing for float columns
    (Complex not yet handled.)
    Column names not compared, but column types and sizes are.
    """

    nfieldsa = len(a.dtype.names)
    nfieldsb = len(b.dtype.names)
    if nfieldsa != nfieldsb:
        print "number of fields don't match"
        return False
    for i in range(nfieldsa):
        fielda = a.field(i)
        fieldb = b.field(i)
        if fielda.dtype.char == 'S':
            fielda = decode_ascii(fielda)
        if fieldb.dtype.char == 'S':
            fieldb = decode_ascii(fieldb)
        if type(fielda) != type(fieldb):
            print "type(fielda): ",type(fielda)," fielda: ",fielda
            print "type(fieldb): ",type(fieldb)," fieldb: ",fieldb
            print 'field %d type differs' % i
            return False
        if isinstance(fielda[0], np.floating):
            if not comparefloats(fielda, fieldb):
                print "fielda: ",fielda
                print "fieldb: ",fieldb
                print 'field %d differs' % i
                return False
        else:
            if np.any(fielda != fieldb):
                print "fielda: ",fielda
                print "fieldb: ",fieldb
                print 'field %d differs' % i
                return False
    return True


class TestPyfitsTableFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass

    def tearDown(self):
        # Perform clean-up actions (if any)
        for tmpfile in ['newtable.fits', 'table1.fits', 'table2.fits',
                        'tableout1.fits', 'tableout2.fits', 'toto.fits',
                        'testendian.fits']:
            try:
                os.remove(tmpfile)
            except:
                pass

    def testOpen(self):
        # open some existing FITS files:
        tt =pyfits.open(os.path.join(data_dir, 'tb.fits'))
        fd =pyfits.open(os.path.join(data_dir, 'test0.fits'))

        # create some local arrays
        a1 =chararray.array(['abc', 'def', 'xx'])
        r1 = np.array([11.,12.,13.], dtype=np.float32)

        # create a table from scratch, using a mixture of columns from existing
        # tables and locally created arrays:

        # first, create individual column definitions

        c1 = pyfits.Column(name='abc', format='3A', array=a1)
        c2 = pyfits.Column(name='def', format='E', array=r1)
        a3 = np.array([3,4,5], dtype='i2')
        c3 = pyfits.Column(name='xyz', format='I', array=a3)
        a4 = np.array([1,2,3], dtype='i2')
        c4 = pyfits.Column(name='t1', format='I', array=a4)
        a5 = np.array([3+3j,4+4j,5+5j], dtype='c8')
        c5 = pyfits.Column(name='t2', format='C', array=a5)

        # Note that X format must be two-D array
        a6 = np.array([[0], [1], [0]], dtype=np.uint8)
        c6 = pyfits.Column(name='t3', format='X', array=a6)
        a7 = np.array([101, 102, 103],dtype='i4')
        c7 = pyfits.Column(name='t4', format='J', array=a7)
        a8 = np.array([[1, 1, 0, 1, 0, 1, 1, 1, 0, 0, 1],
                       [0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0],
                       [1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1]], dtype=np.uint8)
        c8=pyfits.Column(name='t5', format='11X', array=a8)

        # second, create a column-definitions object for all columns in a table

        x = pyfits.ColDefs([c1, c2, c3, c4, c5, c6, c7, c8])

        # create a new binary table HDU object by using the new_table function

        tbhdu = pyfits.new_table(x)

        # another way to create a table is by using existing table's information:

        x2 = pyfits.ColDefs(tt[1])
        t2 = pyfits.new_table(x2, nrows=2)
        ra = rec.array([
            (1, 'abc', 3.7000002861022949, 0),
            (2, 'xy ', 6.6999998092651367, 1)], names='c1, c2, c3, c4')

        self.assertEqual(comparerecords(t2.data, ra),True)

        # the table HDU's data is a subclass of a record array, so we can access
        # one row like this:

        self.assertEqual(tbhdu.data[1][0], a1[1])
        self.assertEqual(tbhdu.data[1][1], r1[1])
        self.assertEqual(tbhdu.data[1][2], a3[1])
        self.assertEqual(tbhdu.data[1][3], a4[1])
        self.assertEqual(tbhdu.data[1][4], a5[1])
        self.assertEqual(tbhdu.data[1][5], a6[1])
        self.assertEqual(tbhdu.data[1][6], a7[1])
        self.assertEqual(tbhdu.data[1][7].all(), a8[1].all())

        # and a column like this:
        self.assertEqual(str(tbhdu.data.field('abc')), "['abc' 'def' 'xx']")

        # An alternative way to create a column-definitions object is from an
        # existing table.
        xx = pyfits.ColDefs(tt[1])

        # now we write out the newly created table HDU to a FITS file:
        fout = pyfits.HDUList(pyfits.PrimaryHDU())
        fout.append(tbhdu)
        fout.writeto('tableout1.fits', clobber=True)

        f2 = pyfits.open('tableout1.fits')
        temp = f2[1].data.field(7)
        self.assertEqual(str(temp[0]),
            "[ True  True False  True False  True  True  True False False  True]")
        f2.close()
        os.remove('tableout1.fits')


        # An alternative way to create an output table FITS file:
        fout2 = pyfits.open('tableout2.fits', 'append')
        fout2.append(fd[0])
        fout2.append(tbhdu)
        fout2.close()
        tt.close()
        fd.close()
        os.remove("tableout2.fits")

    def testBinaryTable(self):
        # binary table:
        t = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        self.assertEqual(t[1].header['tform1'], '1J')

        with CaptureStdout() as f:
            t[1].columns.info()
            self.assertEqual(f.getvalue(),
                "name:\n"
                "     ['c1', 'c2', 'c3', 'c4']\n"
                "format:\n"
                "     ['1J', '3A', '1E', '1L']\n"
                "unit:\n"
                "     ['', '', '', '']\n"
                "null:\n"
                "     [-2147483647, '', '', '']\n"
                "bscale:\n"
                "     ['', '', 3, '']\n"
                "bzero:\n"
                "     ['', '', %r, '']\n"
                "disp:\n"
                "     ['I11', 'A3', 'G15.7', 'L6']\n"
                "start:\n"
                "     ['', '', '', '']\n"
                "dim:\n"
                "     ['', '', '', '']\n" % 0.4)

        ra = rec.array([
            (1, 'abc', 3.7000002861022949, 0),
            (2, 'xy ', 6.6999998092651367, 1)], names='c1, c2, c3, c4')

        self.assertEqual(comparerecords(t[1].data, ra[:2]), True)

        # Change scaled field and scale back to the original array
        t[1].data.field('c4')[0] = 1
        t[1].data._scale_back()
        self.assertEqual(str(rec.recarray.field(t[1].data,'c4')), "[84 84]")

        # look at data column-wise
        self.assertEqual(t[1].data.field(0).all(), np.array([1, 2]).all())

        # When there are scaled columns, the raw data are in data._parent

        t.close()

    def testAsciiTable(self):
        # ASCII table
        a = pyfits.open(os.path.join(data_dir, 'ascii.fits'))
        ra1 = rec.array([
            (10.123000144958496, 37),
            (5.1999998092651367, 23),
            (15.609999656677246, 17),
            (0.0, 0),
            (345.0, 345)], names='c1, c2')
        self.assertEqual(comparerecords(a[1].data, ra1), True)

        # Test slicing
        a2 = a[1].data[2:][2:]
        ra2 = rec.array([(345.0,345)],names='c1, c2')

        self.assertEqual(comparerecords(a2, ra2), True)

        self.assertEqual(a2.field(1).all(),np.array([345]).all())

        ra3 = rec.array([
            (10.123000144958496, 37),
            (15.609999656677246, 17),
            (345.0, 345)
            ], names='c1, c2')

        self.assertEqual(comparerecords(a[1].data[::2], ra3), True)

        # Test Start Column

        a1 = chararray.array(['abcd','def'])
        r1 = np.array([11.,12.])
        c1 = pyfits.Column(name='abc',format='A3',start=19, array=a1)
        c2 = pyfits.Column(name='def',format='E',start=3, array=r1)
        c3 = pyfits.Column(name='t1',format='I',array=[91, 92, 93])
        hdu = pyfits.new_table([c2, c1, c3],tbtype='TableHDU')


        self.assertEqual(dict(hdu.data.dtype.fields),
                         {'abc': (np.dtype('|S3'), 18),
                          'def': (np.dtype('|S15'), 2),
                          't1': (np.dtype('|S10'), 21)})
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data), True)
        hdul.close()
        a.close()
        os.remove('toto.fits')

    def testVariableLengthColumns(self):
        col_list = []
        col_list.append(pyfits.Column(name='QUAL_SPE', format='PJ()',
                        array=[[0]*1571]*225))
        tb_hdu = pyfits.new_table(col_list)
        pri_hdu = pyfits.PrimaryHDU()
        hdu_list = pyfits.HDUList([pri_hdu,tb_hdu])
        hdu_list.writeto('toto.fits', clobber=True)
        toto = pyfits.open('toto.fits')
        q = toto[1].data.field('QUAL_SPE')
        self.assertEqual(q[0][4:8].all(),
                         np.array([0, 0, 0, 0],dtype=np.uint8).all())
        toto.close()
        os.remove('toto.fits')

    def testEndianness(self):
        x = np.ndarray((1,), dtype=object)
        channelsIn = np.array([3], dtype='uint8')
        x[0] = channelsIn
        col = pyfits.Column(name="Channels", format="PB()", array=x)
        cols = pyfits.ColDefs([col])
        tbhdu = pyfits.new_table(cols)
        tbhdu.name = "RFI"
        tbhdu.writeto('testendian.fits', clobber=True)
        hduL = pyfits.open('testendian.fits')
        rfiHDU = hduL['RFI']
        data = rfiHDU.data
        channelsOut = data.field('Channels')[0]
        self.assertEqual(channelsIn.all(),channelsOut.all())
        hduL.close()
        os.remove('testendian.fits')

    def testPyfitsRecarrayToBinTableHDU(self):
        bright=rec.array([(1,'Serius',-1.45,'A1V'),\
                          (2,'Canopys',-0.73,'F0Ib'),\
                          (3,'Rigil Kent',-0.1,'G2V')],\
                         formats='int16,a20,float32,a10',\
                         names='order,name,mag,Sp')
        hdu=pyfits.BinTableHDU(bright)
        self.assertEqual(comparerecords(hdu.data, bright), True)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        self.assertEqual(comparerecords(bright,hdul[1].data),True)
        hdul.close()
        os.remove('toto.fits')

    def testNumpyNdarrayToBinTableHDU(self):
        desc = np.dtype({'names': ['order','name','mag','Sp'],
                         'formats': ['int','S20','float32','S10']})
        a = np.array([(1,'Serius',-1.45,'A1V'),
                      (2,'Canopys',-0.73,'F0Ib'),
                      (3,'Rigil Kent',-0.1,'G2V')], dtype=desc)
        hdu=pyfits.BinTableHDU(a)
        self.assertEqual(comparerecords(hdu.data, a.view(pyfits.FITS_rec)),
                         True)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        hdul.close()
        os.remove('toto.fits')

    def testNewTableFromPyfitsRecarray(self):
        bright = rec.array([(1,'Serius',-1.45,'A1V'),
                            (2,'Canopys',-0.73,'F0Ib'),
                            (3,'Rigil Kent',-0.1,'G2V')],
                           formats='int16,a20,float32,a10',
                           names='order,name,mag,Sp')
        hdu=pyfits.new_table(bright,nrows=2,tbtype='TableHDU')

        # Verify that all ndarray objects within the HDU reference the
        # same ndarray.
        self.assertEqual(id(hdu.data._coldefs.columns[0].array),
                         id(hdu.data._coldefs._arrays[0]))
        self.assertEqual(id(hdu.data._coldefs.columns[0].array),
                         id(hdu.columns.data[0].array))
        self.assertEqual(id(hdu.data._coldefs.columns[0].array),
                         id(hdu.columns._arrays[0]))

        # Ensure I can change the value of one data element and it effects
        # all of the others.
        hdu.data[0][0] = 213

        self.assertEqual(hdu.data[0][0], 213)
        self.assertEqual(hdu.data._coldefs._arrays[0][0], 213)
        self.assertEqual(hdu.data._coldefs.columns[0].array[0], 213)
        self.assertEqual(hdu.columns._arrays[0][0], 213)
        self.assertEqual(hdu.columns.data[0].array[0], 213)

        hdu.data._coldefs._arrays[0][0] = 100

        self.assertEqual(hdu.data[0][0], 100)
        self.assertEqual(hdu.data._coldefs._arrays[0][0], 100)
        self.assertEqual(hdu.data._coldefs.columns[0].array[0], 100)
        self.assertEqual(hdu.columns._arrays[0][0], 100)
        self.assertEqual(hdu.columns.data[0].array[0], 100)

        hdu.data._coldefs.columns[0].array[0] = 500
        self.assertEqual(hdu.data[0][0], 500)
        self.assertEqual(hdu.data._coldefs._arrays[0][0], 500)
        self.assertEqual(hdu.data._coldefs.columns[0].array[0], 500)
        self.assertEqual(hdu.columns._arrays[0][0], 500)
        self.assertEqual(hdu.columns.data[0].array[0], 500)

        hdu.columns._arrays[0][0] = 600
        self.assertEqual(hdu.data[0][0], 600)
        self.assertEqual(hdu.data._coldefs._arrays[0][0], 600)
        self.assertEqual(hdu.data._coldefs.columns[0].array[0], 600)
        self.assertEqual(hdu.columns._arrays[0][0], 600)
        self.assertEqual(hdu.columns.data[0].array[0], 600)

        hdu.columns.data[0].array[0] = 800
        self.assertEqual(hdu.data[0][0], 800)
        self.assertEqual(hdu.data._coldefs._arrays[0][0], 800)
        self.assertEqual(hdu.data._coldefs.columns[0].array[0], 800)
        self.assertEqual(hdu.columns._arrays[0][0], 800)
        self.assertEqual(hdu.columns.data[0].array[0], 800)

        self.assertEqual(hdu.data.field(0).all(),
                         np.array([1, 2],dtype=np.int16).all())
        self.assertEqual(hdu.data[0][1], 'Serius')
        self.assertEqual(hdu.data[1][1], 'Canopys')
        self.assertEqual(hdu.data.field(2).all(),
                         np.array([-1.45, -0.73], dtype=np.float32).all())
        self.assertEqual(hdu.data[0][3], 'A1V')
        self.assertEqual(hdu.data[1][3], 'F0Ib')
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(hdul[1].data.field(0).all(),
                         np.array([1, 2], dtype=np.int16).all())
        self.assertEqual(hdul[1].data[0][1], 'Serius')
        self.assertEqual(hdul[1].data[1][1], 'Canopys')
        self.assertEqual(hdul[1].data.field(2).all(),
                         np.array([-1.45, -0.73], dtype=np.float32).all())
        self.assertEqual(hdul[1].data[0][3], 'A1V')
        self.assertEqual(hdul[1].data[1][3], 'F0Ib')

        hdul.close()
        os.remove('toto.fits')
        hdu=pyfits.new_table(bright,nrows=2)
        tmp=rec.array([(1,'Serius',-1.45,'A1V'),
                       (2,'Canopys',-0.73,'F0Ib')],
                      formats='int16,a20,float32,a10',
                      names='order,name,mag,Sp')
        self.assertEqual(comparerecords(hdu.data,tmp), True)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        hdul.close()
        os.remove('toto.fits')

    def testNewFitsrec(self):
        """
        Tests creating a new FITS_rec object from a multi-field ndarray.
        """

        h = pyfits.open(os.path.join(data_dir, 'tb.fits'))
        data = h[1].data
        new_data = np.array([(3, 'qwe', 4.5, False)], dtype=data.dtype)
        appended = np.append(data, new_data).view(pyfits.FITS_rec)
        self.assertEqual(repr(appended),
            "FITS_rec([(1, 'abc', 1.1, False), (2, 'xy', 2.0999999, True),\n"
            "       (3, 'qwe', 4.5, False)], \n"
            "      dtype=[('c1', '>i4'), ('c2', '|S3'), ('c3', '>f4'), ('c4', '|i1')])")

    def testAppendingAColumn(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])
        tbhdu=pyfits.new_table(coldefs)
        tbhdu.writeto('table1.fits')

        counts = np.array([412, 434, 408, 417])
        names = np.array(['NGC5', 'NGC6', 'NGC7', 'NCG8'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[0, 1, 0, 0])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])
        tbhdu = pyfits.new_table(coldefs)
        tbhdu.writeto('table2.fits')

        # Append the rows of table 2 after the rows of table 1
        # The column definitions are assumed to be the same

        # Open the two files we want to append
        t1 = pyfits.open('table1.fits')
        t2 = pyfits.open('table2.fits')

        # Get the number of rows in the table from the first file
        nrows1 = t1[1].data.shape[0]

        # Get the total number of rows in the resulting appended table
        nrows = t1[1].data.shape[0] + t2[1].data.shape[0]

        self.assertEqual(t1[1].columns._arrays[1] is
                         t1[1].columns.data[1].array, True)

        # Create a new table that consists of the data from the first table
        # but has enough space in the ndarray to hold the data from both tables
        hdu = pyfits.new_table(t1[1].columns, nrows=nrows)

        # For each column in the tables append the data from table 2 after the
        # data from table 1.
        for i in range(len(t1[1].columns)):
            hdu.data.field(i)[nrows1:] = t2[1].data.field(i)

        hdu.writeto('newtable.fits')

        with CaptureStdout() as f:
            pyfits.info('newtable.fits')
            self.assertEqual(f.getvalue(),
                'Filename: newtable.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4   ()           uint8\n'
                '1                BinTableHDU     19   8R x 5C      [10A, J, 10A, 5E, L]\n')

        self.assertEqual(str(hdu.data),
            "[ ('NGC1', 312, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NGC2', 334, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NGC3', 308, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NCG4', 317, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NGC5', 412, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NGC6', 434, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NGC7', 408, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NCG8', 417, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)]")

        # Verify that all of the references to the data point to the same
        # numarray
        hdu.data[0][1] = 300
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 300)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 300)
        self.assertEqual(hdu.columns._arrays[1][0], 300)
        self.assertEqual(hdu.columns.data[1].array[0], 300)
        self.assertEqual(hdu.data[0][1], 300)

        hdu.data._coldefs._arrays[1][0] = 200
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 200)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 200)
        self.assertEqual(hdu.columns._arrays[1][0], 200)
        self.assertEqual(hdu.columns.data[1].array[0], 200)
        self.assertEqual(hdu.data[0][1], 200)

        hdu.data._coldefs.columns[1].array[0] = 100
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 100)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(hdu.columns._arrays[1][0], 100)
        self.assertEqual(hdu.columns.data[1].array[0], 100)
        self.assertEqual(hdu.data[0][1], 100)

        hdu.columns._arrays[1][0] = 90
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 90)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 90)
        self.assertEqual(hdu.columns._arrays[1][0], 90)
        self.assertEqual(hdu.columns.data[1].array[0], 90)
        self.assertEqual(hdu.data[0][1], 90)

        hdu.columns.data[1].array[0] = 80
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 80)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 80)
        self.assertEqual(hdu.columns._arrays[1][0], 80)
        self.assertEqual(hdu.columns.data[1].array[0], 80)
        self.assertEqual(hdu.data[0][1], 80)

        # Same verification from the file
        hdul = pyfits.open('newtable.fits')
        hdu = hdul[1]
        hdu.data[0][1] = 300
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 300)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 300)
        self.assertEqual(hdu.columns._arrays[1][0], 300)
        self.assertEqual(hdu.columns.data[1].array[0], 300)
        self.assertEqual(hdu.data[0][1], 300)

        hdu.data._coldefs._arrays[1][0] = 200
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 200)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 200)
        self.assertEqual(hdu.columns._arrays[1][0], 200)
        self.assertEqual(hdu.columns.data[1].array[0], 200)
        self.assertEqual(hdu.data[0][1], 200)

        hdu.data._coldefs.columns[1].array[0] = 100
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 100)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(hdu.columns._arrays[1][0], 100)
        self.assertEqual(hdu.columns.data[1].array[0], 100)
        self.assertEqual(hdu.data[0][1], 100)

        hdu.columns._arrays[1][0] = 90
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 90)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 90)
        self.assertEqual(hdu.columns._arrays[1][0], 90)
        self.assertEqual(hdu.columns.data[1].array[0], 90)
        self.assertEqual(hdu.data[0][1], 90)

        hdu.columns.data[1].array[0] = 80
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 80)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 80)
        self.assertEqual(hdu.columns._arrays[1][0], 80)
        self.assertEqual(hdu.columns.data[1].array[0], 80)
        self.assertEqual(hdu.data[0][1], 80)

        t1.close()
        t2.close()
        hdul.close()
        os.remove('newtable.fits')
        os.remove('table1.fits')
        os.remove('table2.fits')

    def testAddingAColumn(self):
        # Tests adding a column to a table.
        counts = np.array([312,334,308,317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4])
        tbhdu = pyfits.new_table(coldefs)

        self.assertEqual(tbhdu.columns.names,
                         ['target', 'counts', 'notes', 'spectrum'])
        coldefs1 = coldefs + c5

        tbhdu1=pyfits.new_table(coldefs1)
        self.assertEqual(tbhdu1.columns.names,
                         ['target', 'counts', 'notes', 'spectrum', 'flag'])

        self.assertEqual(str(tbhdu1.data),
            "[ ('NGC1', 312, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NGC2', 334, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NGC3', 308, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NCG4', 317, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)]")

    def testMergeTables(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])
        tbhdu = pyfits.new_table(coldefs)
        tbhdu.writeto('table1.fits')

        counts = np.array([412, 434, 408, 417])
        names = np.array(['NGC5', 'NGC6', 'NGC7', 'NCG8'])
        c1 = pyfits.Column(name='target1', format='10A', array=names)
        c2 = pyfits.Column(name='counts1', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes1', format='A10')
        c4 = pyfits.Column(name='spectrum1',format='5E')
        c5 = pyfits.Column(name='flag1',format='L',array=[0,1,0,0])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])
        tbhdu = pyfits.new_table(coldefs)
        tbhdu.writeto('table2.fits')

        # Merge the columns of table 2 after the columns of table 1
        # The column names are assumed to be different

        # Open the two files we want to append
        t1 = pyfits.open('table1.fits')
        t2 = pyfits.open('table2.fits')

        hdu = pyfits.new_table(t1[1].columns+t2[1].columns)

        self.assertEqual(str(hdu.data),
            "[ ('NGC1', 312, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True, 'NGC5', 412, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NGC2', 334, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False, 'NGC6', 434, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NGC3', 308, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True, 'NGC7', 408, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NCG4', 317, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True, 'NCG8', 417, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)]")

        hdu.writeto('newtable.fits')

        # Verify that all of the references to the data point to the same
        # numarray
        hdu.data[0][1] = 300
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 300)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 300)
        self.assertEqual(hdu.columns._arrays[1][0], 300)
        self.assertEqual(hdu.columns.data[1].array[0], 300)
        self.assertEqual(hdu.data[0][1], 300)

        hdu.data._coldefs._arrays[1][0] = 200
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 200)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 200)
        self.assertEqual(hdu.columns._arrays[1][0], 200)
        self.assertEqual(hdu.columns.data[1].array[0], 200)
        self.assertEqual(hdu.data[0][1], 200)

        hdu.data._coldefs.columns[1].array[0] = 100
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 100)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(hdu.columns._arrays[1][0], 100)
        self.assertEqual(hdu.columns.data[1].array[0], 100)
        self.assertEqual(hdu.data[0][1], 100)

        hdu.columns._arrays[1][0] = 90
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 90)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 90)
        self.assertEqual(hdu.columns._arrays[1][0], 90)
        self.assertEqual(hdu.columns.data[1].array[0], 90)
        self.assertEqual(hdu.data[0][1], 90)

        hdu.columns.data[1].array[0] = 80
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 80)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 80)
        self.assertEqual(hdu.columns._arrays[1][0], 80)
        self.assertEqual(hdu.columns.data[1].array[0], 80)
        self.assertEqual(hdu.data[0][1], 80)

        with CaptureStdout() as f:
            pyfits.info('newtable.fits')
            self.assertEqual(f.getvalue(),
                'Filename: newtable.fits\n'
                'No.    Name         Type      Cards   Dimensions   Format\n'
                '0    PRIMARY     PrimaryHDU       4   ()           uint8\n'
                '1                BinTableHDU     30   4R x 10C     [10A, J, 10A, 5E, L, 10A, J, 10A, 5E, L]\n')

        hdul = pyfits.open('newtable.fits')
        hdu = hdul[1]

        self.assertEqual(hdu.columns.names,
                         ['target', 'counts', 'notes', 'spectrum', 'flag',
                          'target1', 'counts1', 'notes1', 'spectrum1', 'flag1'])

        self.assertEqual(str(hdu.data),
            "[ ('NGC1', 312, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True, 'NGC5', 412, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NGC2', 334, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False, 'NGC6', 434, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True)\n"
            " ('NGC3', 308, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True, 'NGC7', 408, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)\n"
            " ('NCG4', 317, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), True, 'NCG8', 417, '0.0', array([ 0.,  0.,  0.,  0.,  0.], dtype=float32), False)]")

        # Same verification from the file
        hdu.data[0][1] = 300
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 300)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 300)
        self.assertEqual(hdu.columns._arrays[1][0], 300)
        self.assertEqual(hdu.columns.data[1].array[0], 300)
        self.assertEqual(hdu.data[0][1], 300)

        hdu.data._coldefs._arrays[1][0] = 200
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 200)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 200)
        self.assertEqual(hdu.columns._arrays[1][0], 200)
        self.assertEqual(hdu.columns.data[1].array[0], 200)
        self.assertEqual(hdu.data[0][1], 200)

        hdu.data._coldefs.columns[1].array[0] = 100
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 100)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(hdu.columns._arrays[1][0], 100)
        self.assertEqual(hdu.columns.data[1].array[0], 100)
        self.assertEqual(hdu.data[0][1], 100)

        hdu.columns._arrays[1][0] = 90
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 90)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 90)
        self.assertEqual(hdu.columns._arrays[1][0], 90)
        self.assertEqual(hdu.columns.data[1].array[0], 90)
        self.assertEqual(hdu.data[0][1], 90)

        hdu.columns.data[1].array[0] = 80
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 80)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 80)
        self.assertEqual(hdu.columns._arrays[1][0], 80)
        self.assertEqual(hdu.columns.data[1].array[0], 80)
        self.assertEqual(hdu.data[0][1], 80)

        t1.close()
        t2.close()
        hdul.close()
        os.remove('table1.fits')
        os.remove('table2.fits')
        os.remove('newtable.fits')

    def testMaskArray(self):
        t = pyfits.open(os.path.join(data_dir, 'table.fits'))
        tbdata = t[1].data
        mask = tbdata.field('V_mag') > 12
        newtbdata = tbdata[mask]
        hdu = pyfits.BinTableHDU(newtbdata)
        hdu.writeto('newtable.fits')

        hdul = pyfits.open('newtable.fits')

        self.assertEqual(str(hdu.data),
                         "[('NGC1002', 12.3) ('NGC1003', 15.2)]")

        self.assertEqual(str(hdul[1].data),
                         "[('NGC1002', 12.3) ('NGC1003', 15.2)]")

        t.close()
        hdul.close()
        os.remove('newtable.fits')

    def testSliceARow(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])
        tbhdu = pyfits.new_table(coldefs)
        tbhdu.writeto('table1.fits')

        t1=pyfits.open('table1.fits')
        row = t1[1].data[2]
        self.assertEqual(row['counts'], 308)
        a,b,c = row[1:4]
        self.assertEqual(a, counts[2])
        self.assertEqual(b, '0.0')
        self.assertEqual(c.all(), np.array([ 0.,  0.,  0.,  0.,  0.],
                                           dtype=np.float32).all())
        row['counts'] = 310
        self.assertEqual(row['counts'], 310)

        row[1] = 315
        self.assertEqual(row['counts'], 315)

        self.assertEqual(row[1:4]['counts'], 315)

        self.assertRaises(KeyError, lambda r: r[1:4]['flag'], row)

        row[1:4]['counts'] = 300
        self.assertEqual(row[1:4]['counts'], 300)
        self.assertEqual(row['counts'], 300)

        row[1:4][0] = 400
        self.assertEqual(row[1:4]['counts'], 400)
        row[1:4]['counts'] = 300
        self.assertEqual(row[1:4]['counts'], 300)

        self.assertRaises(KeyError, lambda r: r[1:4]['flag'], row)

        self.assertEqual(row[1:4].field(0), 300)
        self.assertEqual(row[1:4].field('counts'), 300)

        self.assertRaises(KeyError, row[1:4].field, 'flag')

        row[1:4].setfield('counts', 500)
        self.assertEqual(row[1:4].field(0), 500)

        self.assertRaises(KeyError, row[1:4].setfield, 'flag', False)

        self.assertEqual(t1[1].data._coldefs._arrays[1][2], 500)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[2], 500)
        self.assertEqual(t1[1].columns._arrays[1][2], 500)
        self.assertEqual(t1[1].columns.data[1].array[2], 500)
        self.assertEqual(t1[1].data[2][1], 500)

        t1.close()
        os.remove('table1.fits')

    def testFITSrecordLen(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])
        tbhdu = pyfits.new_table(coldefs)
        tbhdu.writeto('table1.fits')

        t1 = pyfits.open('table1.fits')

        self.assertEqual(len(t1[1].data[0]), 5)
        self.assertEqual(len(t1[1].data[0][0:4]), 4)
        self.assertEqual(len(t1[1].data[0][0:5]), 5)
        self.assertEqual(len(t1[1].data[0][0:6]), 5)
        self.assertEqual(len(t1[1].data[0][0:7]), 5)
        self.assertEqual(len(t1[1].data[0][1:4]), 3)
        self.assertEqual(len(t1[1].data[0][1:5]), 4)
        self.assertEqual(len(t1[1].data[0][1:6]), 4)
        self.assertEqual(len(t1[1].data[0][1:7]), 4)

        t1.close()
        os.remove('table1.fits')

    def testAddDataByRows(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu1=pyfits.new_table(coldefs)

        c1 = pyfits.Column(name='target', format='10A')
        c2 = pyfits.Column(name='counts', format='J', unit='DN')
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L')
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu = pyfits.new_table(coldefs, nrows=5)

        # Test assigning data to a tables row using a FITS_record
        tbhdu.data[0] = tbhdu1.data[0]
        tbhdu.data[4] = tbhdu1.data[3]

        # Test assigning data to a tables row using a tuple
        tbhdu.data[2] = ('NGC1', 312, 'A Note',
                         np.array([1.1, 2.2, 3.3, 4.4, 5.5], dtype=np.float32),
                         True)

        # Test assigning data to a tables row using a list
        tbhdu.data[3] = ['JIM1', '33', 'A Note',
                         np.array([1., 2., 3., 4., 5.],dtype=np.float32),True]

        # Verify that all ndarray objects within the HDU reference the
        # same ndarray.
        self.assertEqual(id(tbhdu.data._coldefs.columns[0].array),
                         id(tbhdu.data._coldefs._arrays[0]))
        self.assertEqual(id(tbhdu.data._coldefs.columns[0].array),
                         id(tbhdu.columns.data[0].array))
        self.assertEqual(id(tbhdu.data._coldefs.columns[0].array),
                         id(tbhdu.columns._arrays[0]))

        self.assertEqual(tbhdu.data[0][1], 312)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][0], 312)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[0], 312)
        self.assertEqual(tbhdu.columns._arrays[1][0], 312)
        self.assertEqual(tbhdu.columns.data[1].array[0], 312)
        self.assertEqual(tbhdu.columns.data[0].array[0], 'NGC1')
        self.assertEqual(tbhdu.columns.data[2].array[0], '0.0')
        self.assertEqual(tbhdu.columns.data[3].array[0].all(),
                         np.array([0., 0., 0., 0., 0.],dtype=np.float32).all())
        self.assertEqual(tbhdu.columns.data[4].array[0], True)

        self.assertEqual(tbhdu.data[3][1], 33)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][3], 33)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[3], 33)
        self.assertEqual(tbhdu.columns._arrays[1][3], 33)
        self.assertEqual(tbhdu.columns.data[1].array[3], 33)
        self.assertEqual(tbhdu.columns.data[0].array[3], 'JIM1')
        self.assertEqual(tbhdu.columns.data[2].array[3], 'A Note')
        self.assertEqual(tbhdu.columns.data[3].array[3].all(),
                         np.array([1., 2., 3., 4., 5.],dtype=np.float32).all())
        self.assertEqual(tbhdu.columns.data[4].array[3], True)

    def testAssignMultipleRowsToTable(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu1 = pyfits.new_table(coldefs)

        counts = np.array([112, 134, 108, 117])
        names = np.array(['NGC5', 'NGC6', 'NGC7', 'NCG8'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[0, 1, 0, 0])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu = pyfits.new_table(coldefs)
        tbhdu.data[0][3] = np.array([1., 2., 3., 4., 5.], dtype=np.float32)

        tbhdu2 = pyfits.new_table(tbhdu1.data, nrows=9)

        # Assign the 4 rows from the second table to rows 5 thru 8 of the
        # new table.  Note that the last row of the new table will still be
        # initialized to the default values.
        tbhdu2.data[4:] = tbhdu.data

        # Verify that all ndarray objects within the HDU reference the
        # same ndarray.
        self.assertEqual(id(tbhdu2.data._coldefs.columns[0].array),
                         id(tbhdu2.data._coldefs._arrays[0]))
        self.assertEqual(id(tbhdu2.data._coldefs.columns[0].array),
                         id(tbhdu2.columns.data[0].array))
        self.assertEqual(id(tbhdu2.data._coldefs.columns[0].array),
                         id(tbhdu2.columns._arrays[0]))

        self.assertEqual(tbhdu2.data[0][1], 312)
        self.assertEqual(tbhdu2.data._coldefs._arrays[1][0], 312)
        self.assertEqual(tbhdu2.data._coldefs.columns[1].array[0], 312)
        self.assertEqual(tbhdu2.columns._arrays[1][0], 312)
        self.assertEqual(tbhdu2.columns.data[1].array[0], 312)
        self.assertEqual(tbhdu2.columns.data[0].array[0], 'NGC1')
        self.assertEqual(tbhdu2.columns.data[2].array[0], '0.0')
        self.assertEqual(tbhdu2.columns.data[3].array[0].all(),
                         np.array([0., 0., 0., 0., 0.],dtype=np.float32).all())
        self.assertEqual(tbhdu2.columns.data[4].array[0], True)

        self.assertEqual(tbhdu2.data[4][1], 112)
        self.assertEqual(tbhdu2.data._coldefs._arrays[1][4], 112)
        self.assertEqual(tbhdu2.data._coldefs.columns[1].array[4], 112)
        self.assertEqual(tbhdu2.columns._arrays[1][4], 112)
        self.assertEqual(tbhdu2.columns.data[1].array[4], 112)
        self.assertEqual(tbhdu2.columns.data[0].array[4], 'NGC5')
        self.assertEqual(tbhdu2.columns.data[2].array[4], '0.0')
        self.assertEqual(tbhdu2.columns.data[3].array[4].all(),
                         np.array([1., 2., 3., 4., 5.],dtype=np.float32).all())
        self.assertEqual(tbhdu2.columns.data[4].array[4], False)

        self.assertEqual(tbhdu2.columns.data[1].array[8], 0)
        self.assertEqual(tbhdu2.columns.data[0].array[8], '0.0')
        self.assertEqual(tbhdu2.columns.data[2].array[8], '0.0')
        self.assertEqual(tbhdu2.columns.data[3].array[8].all(),
                         np.array([0., 0., 0., 0., 0.],dtype=np.float32).all())
        self.assertEqual(tbhdu2.columns.data[4].array[8], False)

    def testVerifyDataReferences(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs=pyfits.ColDefs([c1, c2, c3, c4, c5])

        # Verify that original ColDefs object has independent ndarray from
        # original array object.
        self.assertNotEqual(id(names), id(c1.array))
        self.assertNotEqual(id(counts), id(c2.array))

        tbhdu = pyfits.new_table(coldefs)

        # Verify that original ColDefs object has independent Column
        # objects.
        self.assertNotEqual(id(coldefs.columns[0]), id(c1))

        # Verify that original ColDefs object has independent ndarray
        # objects.
        self.assertNotEqual(id(coldefs.columns[0].array), id(names))

        # Verify that original ColDefs object references the same data
        # object as the original Column object.
        self.assertEqual(id(coldefs.columns[0].array), id(c1.array))
        self.assertEqual(id(coldefs.columns[0].array), id(coldefs._arrays[0]))

        # Verify new HDU has an independent ColDefs object.
        self.assertNotEqual(id(coldefs), id(tbhdu.columns))

        # Verify new HDU has independent Column objects.
        self.assertNotEqual(id(coldefs.columns[0]), id(tbhdu.columns.data[0]))

        # Verify new HDU has independent ndarray objects.
        self.assertNotEqual(id(coldefs.columns[0].array),
                            id(tbhdu.columns.data[0].array))

        # Verify that both ColDefs objects in the HDU reference the same
        # Coldefs object.
        self.assertEqual(id(tbhdu.columns), id(tbhdu.data._coldefs))

        # Verify that all ndarray objects within the HDU reference the
        # same ndarray.
        self.assertEqual(id(tbhdu.data._coldefs.columns[0].array),
                         id(tbhdu.data._coldefs._arrays[0]))
        self.assertEqual(id(tbhdu.data._coldefs.columns[0].array),
                         id(tbhdu.columns.data[0].array))
        self.assertEqual(id(tbhdu.data._coldefs.columns[0].array),
                         id(tbhdu.columns._arrays[0]))

        tbhdu.writeto('table1.fits')

        t1 = pyfits.open('table1.fits')

        t1[1].data[0][1] = 213

        self.assertEqual(t1[1].data[0][1], 213)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 213)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 213)
        self.assertEqual(t1[1].columns._arrays[1][0], 213)
        self.assertEqual(t1[1].columns.data[1].array[0], 213)

        t1[1].data._coldefs._arrays[1][0] = 100

        self.assertEqual(t1[1].data[0][1], 100)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 100)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 100)
        self.assertEqual(t1[1].columns._arrays[1][0], 100)
        self.assertEqual(t1[1].columns.data[1].array[0], 100)

        t1[1].data._coldefs.columns[1].array[0] = 500
        self.assertEqual(t1[1].data[0][1], 500)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 500)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 500)
        self.assertEqual(t1[1].columns._arrays[1][0], 500)
        self.assertEqual(t1[1].columns.data[1].array[0], 500)

        t1[1].columns._arrays[1][0] = 600
        self.assertEqual(t1[1].data[0][1], 600)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 600)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 600)
        self.assertEqual(t1[1].columns._arrays[1][0], 600)
        self.assertEqual(t1[1].columns.data[1].array[0], 600)

        t1[1].columns.data[1].array[0] = 800
        self.assertEqual(t1[1].data[0][1], 800)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 800)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 800)
        self.assertEqual(t1[1].columns._arrays[1][0], 800)
        self.assertEqual(t1[1].columns.data[1].array[0], 800)

        t1.close()
        os.remove('table1.fits')

    def testNewTableWithNdarray(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu = pyfits.new_table(coldefs)

        tbhdu1 = pyfits.new_table(tbhdu.data.view(np.ndarray))

        # Verify that all ndarray objects within the HDU reference the
        # same ndarray.
        self.assertEqual(id(tbhdu1.data._coldefs.columns[0].array),
                         id(tbhdu1.data._coldefs._arrays[0]))
        self.assertEqual(id(tbhdu1.data._coldefs.columns[0].array),
                         id(tbhdu1.columns.data[0].array))
        self.assertEqual(id(tbhdu1.data._coldefs.columns[0].array),
                         id(tbhdu1.columns._arrays[0]))

        # Ensure I can change the value of one data element and it effects
        # all of the others.
        tbhdu1.data[0][1] = 213

        self.assertEqual(tbhdu1.data[0][1], 213)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 213)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 213)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 213)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 213)

        tbhdu1.data._coldefs._arrays[1][0] = 100

        self.assertEqual(tbhdu1.data[0][1], 100)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 100)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 100)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 100)

        tbhdu1.data._coldefs.columns[1].array[0] = 500
        self.assertEqual(tbhdu1.data[0][1], 500)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 500)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 500)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 500)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 500)

        tbhdu1.columns._arrays[1][0] = 600
        self.assertEqual(tbhdu1.data[0][1], 600)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 600)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 600)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 600)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 600)

        tbhdu1.columns.data[1].array[0] = 800
        self.assertEqual(tbhdu1.data[0][1], 800)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 800)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 800)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 800)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 800)

        tbhdu1.writeto('table1.fits')

        t1=pyfits.open('table1.fits')

        t1[1].data[0][1] = 213

        self.assertEqual(t1[1].data[0][1], 213)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 213)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 213)
        self.assertEqual(t1[1].columns._arrays[1][0], 213)
        self.assertEqual(t1[1].columns.data[1].array[0], 213)

        t1[1].data._coldefs._arrays[1][0] = 100

        self.assertEqual(t1[1].data[0][1], 100)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 100)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 100)
        self.assertEqual(t1[1].columns._arrays[1][0], 100)
        self.assertEqual(t1[1].columns.data[1].array[0], 100)

        t1[1].data._coldefs.columns[1].array[0] = 500
        self.assertEqual(t1[1].data[0][1], 500)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 500)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 500)
        self.assertEqual(t1[1].columns._arrays[1][0], 500)
        self.assertEqual(t1[1].columns.data[1].array[0], 500)

        t1[1].columns._arrays[1][0] = 600
        self.assertEqual(t1[1].data[0][1], 600)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 600)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 600)
        self.assertEqual(t1[1].columns._arrays[1][0], 600)
        self.assertEqual(t1[1].columns.data[1].array[0], 600)

        t1[1].columns.data[1].array[0] = 800
        self.assertEqual(t1[1].data[0][1], 800)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 800)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 800)
        self.assertEqual(t1[1].columns._arrays[1][0], 800)
        self.assertEqual(t1[1].columns.data[1].array[0], 800)

        t1.close()
        os.remove('table1.fits')

    def testNewTableWithFITSrec(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu=pyfits.new_table(coldefs)

        tbhdu.data[0][1] = 213

        self.assertEqual(tbhdu.data[0][1], 213)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][0], 213)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[0], 213)
        self.assertEqual(tbhdu.columns._arrays[1][0], 213)
        self.assertEqual(tbhdu.columns.data[1].array[0], 213)

        tbhdu.data._coldefs._arrays[1][0] = 100

        self.assertEqual(tbhdu.data[0][1], 100)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][0], 100)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(tbhdu.columns._arrays[1][0], 100)
        self.assertEqual(tbhdu.columns.data[1].array[0], 100)

        tbhdu.data._coldefs.columns[1].array[0] = 500
        self.assertEqual(tbhdu.data[0][1], 500)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][0], 500)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[0], 500)
        self.assertEqual(tbhdu.columns._arrays[1][0], 500)
        self.assertEqual(tbhdu.columns.data[1].array[0], 500)

        tbhdu.columns._arrays[1][0] = 600
        self.assertEqual(tbhdu.data[0][1], 600)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][0], 600)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[0], 600)
        self.assertEqual(tbhdu.columns._arrays[1][0], 600)
        self.assertEqual(tbhdu.columns.data[1].array[0], 600)

        tbhdu.columns.data[1].array[0] = 800
        self.assertEqual(tbhdu.data[0][1], 800)
        self.assertEqual(tbhdu.data._coldefs._arrays[1][0], 800)
        self.assertEqual(tbhdu.data._coldefs.columns[1].array[0], 800)
        self.assertEqual(tbhdu.columns._arrays[1][0], 800)
        self.assertEqual(tbhdu.columns.data[1].array[0], 800)

        tbhdu.columns.data[1].array[0] = 312

        tbhdu.writeto('table1.fits')

        t1=pyfits.open('table1.fits')

        t1[1].data[0][1] = 1
        fr = t1[1].data
        self.assertEqual(t1[1].data[0][1], 1)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 1)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 1)
        self.assertEqual(t1[1].columns._arrays[1][0], 1)
        self.assertEqual(t1[1].columns.data[1].array[0], 1)
        self.assertEqual(fr[0][1], 1)
        self.assertEqual(fr._coldefs._arrays[1][0], 1)
        self.assertEqual(fr._coldefs.columns[1].array[0], 1)

        fr._coldefs.columns[1].array[0] = 312

        tbhdu1 = pyfits.new_table(fr)
        #tbhdu1 = pyfits.new_table(t1[1].data)

        i = 0
        for row in tbhdu1.data:
            for j in range(0,len(row)):
                if isinstance(row[j], np.ndarray):
                    self.assertEqual(row[j].all(), tbhdu.data[i][j].all())
                else:
                    self.assertEqual(row[j], tbhdu.data[i][j])
            i = i + 1

        tbhdu1.data[0][1] = 213

        self.assertEqual(t1[1].data[0][1], 312)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 312)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 312)
        self.assertEqual(t1[1].columns._arrays[1][0], 312)
        self.assertEqual(t1[1].columns.data[1].array[0], 312)
        self.assertEqual(fr[0][1], 312)
        self.assertEqual(fr._coldefs._arrays[1][0], 312)
        self.assertEqual(fr._coldefs.columns[1].array[0], 312)
        self.assertEqual(tbhdu1.data[0][1], 213)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 213)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 213)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 213)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 213)

        t1[1].data[0][1] = 10

        self.assertEqual(t1[1].data[0][1], 10)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 10)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 10)
        self.assertEqual(t1[1].columns._arrays[1][0], 10)
        self.assertEqual(t1[1].columns.data[1].array[0], 10)
        self.assertEqual(fr[0][1], 10)
        self.assertEqual(fr._coldefs._arrays[1][0], 10)
        self.assertEqual(fr._coldefs.columns[1].array[0], 10)
        self.assertEqual(tbhdu1.data[0][1], 213)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 213)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 213)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 213)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 213)

        tbhdu1.data._coldefs._arrays[1][0] = 666

        self.assertEqual(t1[1].data[0][1], 10)
        self.assertEqual(t1[1].data._coldefs._arrays[1][0], 10)
        self.assertEqual(t1[1].data._coldefs.columns[1].array[0], 10)
        self.assertEqual(t1[1].columns._arrays[1][0], 10)
        self.assertEqual(t1[1].columns.data[1].array[0], 10)
        self.assertEqual(fr[0][1], 10)
        self.assertEqual(fr._coldefs._arrays[1][0], 10)
        self.assertEqual(fr._coldefs.columns[1].array[0], 10)
        self.assertEqual(tbhdu1.data[0][1], 666)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 666)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 666)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 666)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 666)

        t1.close()
        os.remove('table1.fits')

    def testBinTableHDUConstructor(self):
        counts = np.array([312, 334, 308, 317])
        names = np.array(['NGC1', 'NGC2', 'NGC3', 'NCG4'])
        c1 = pyfits.Column(name='target', format='10A', array=names)
        c2 = pyfits.Column(name='counts', format='J', unit='DN', array=counts)
        c3 = pyfits.Column(name='notes', format='A10')
        c4 = pyfits.Column(name='spectrum', format='5E')
        c5 = pyfits.Column(name='flag', format='L', array=[1, 0, 1, 1])
        coldefs = pyfits.ColDefs([c1, c2, c3, c4, c5])

        tbhdu1=pyfits.new_table(coldefs)

        hdu = pyfits.BinTableHDU(tbhdu1.data)

        # Verify that all ndarray objects within the HDU reference the
        # same ndarray.
        self.assertEqual(id(hdu.data._coldefs.columns[0].array),
                         id(hdu.data._coldefs._arrays[0]))
        self.assertEqual(id(hdu.data._coldefs.columns[0].array),
                         id(hdu.columns.data[0].array))
        self.assertEqual(id(hdu.data._coldefs.columns[0].array),
                         id(hdu.columns._arrays[0]))

        # Verify that the references in the original HDU are the same as the
        # references in the new HDU.
        self.assertEqual(id(tbhdu1.data._coldefs.columns[0].array),
                         id(hdu.data._coldefs._arrays[0]))


        # Verify that a change in the new HDU is reflected in both the new
        # and original HDU.

        hdu.data[0][1] = 213

        self.assertEqual(hdu.data[0][1], 213)
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 213)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 213)
        self.assertEqual(hdu.columns._arrays[1][0], 213)
        self.assertEqual(hdu.columns.data[1].array[0], 213)
        self.assertEqual(tbhdu1.data[0][1], 213)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 213)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 213)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 213)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 213)

        hdu.data._coldefs._arrays[1][0] = 100

        self.assertEqual(hdu.data[0][1], 100)
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 100)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(hdu.columns._arrays[1][0], 100)
        self.assertEqual(hdu.columns.data[1].array[0], 100)
        self.assertEqual(tbhdu1.data[0][1], 100)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 100)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 100)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 100)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 100)

        hdu.data._coldefs.columns[1].array[0] = 500
        self.assertEqual(hdu.data[0][1], 500)
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 500)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 500)
        self.assertEqual(hdu.columns._arrays[1][0], 500)
        self.assertEqual(hdu.columns.data[1].array[0], 500)
        self.assertEqual(tbhdu1.data[0][1], 500)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 500)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 500)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 500)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 500)

        hdu.columns._arrays[1][0] = 600
        self.assertEqual(hdu.data[0][1], 600)
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 600)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 600)
        self.assertEqual(hdu.columns._arrays[1][0], 600)
        self.assertEqual(hdu.columns.data[1].array[0], 600)
        self.assertEqual(tbhdu1.data[0][1], 600)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 600)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 600)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 600)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 600)

        hdu.columns.data[1].array[0] = 800
        self.assertEqual(hdu.data[0][1], 800)
        self.assertEqual(hdu.data._coldefs._arrays[1][0], 800)
        self.assertEqual(hdu.data._coldefs.columns[1].array[0], 800)
        self.assertEqual(hdu.columns._arrays[1][0], 800)
        self.assertEqual(hdu.columns.data[1].array[0], 800)
        self.assertEqual(tbhdu1.data[0][1], 800)
        self.assertEqual(tbhdu1.data._coldefs._arrays[1][0], 800)
        self.assertEqual(tbhdu1.data._coldefs.columns[1].array[0], 800)
        self.assertEqual(tbhdu1.columns._arrays[1][0], 800)
        self.assertEqual(tbhdu1.columns.data[1].array[0], 800)

    def testBinTableWithLogicalArray(self):
        c1 = pyfits.Column(name='flag', format='2L',
                           array=[[True, False], [False, True]])
        coldefs = pyfits.ColDefs([c1])

        tbhdu1 = pyfits.new_table(coldefs)

        self.assertEqual(tbhdu1.data.field('flag')[0].all(),
                         np.array([True, False],
                                  dtype = np.bool).all())
        self.assertEqual(tbhdu1.data.field('flag')[1].all(),
                         np.array([False, True],
                                  dtype = np.bool).all())

        tbhdu = pyfits.new_table(tbhdu1.data)

        self.assertEqual(tbhdu.data.field('flag')[0].all(),
                         np.array([True, False],
                                  dtype = np.bool).all())
        self.assertEqual(tbhdu.data.field('flag')[1].all(),
                         np.array([False, True],
                                  dtype = np.bool).all())

    def testVariableLengthTableFormatPDFromObjectArray(self):
        a = np.array([np.array([7.2e-20, 7.3e-20]), np.array([0.0]),
                      np.array([0.0])], 'O')
        acol = pyfits.Column(name='testa', format='PD()', array=a)
        tbhdu = pyfits.new_table([acol])
        tbhdu.writeto('newtable.fits')
        tbhdu1 = pyfits.open('newtable.fits')

        for j in range(0,3):
            for i in range(0,len(a[j])):
                self.assertEqual(tbhdu1[1].data.field(0)[j][i], a[j][i])

        tbhdu1.close()
        os.remove('newtable.fits')

    def testVariableLengthTableFormatPDFromList(self):
        a = [np.array([7.2e-20,7.3e-20]),np.array([0.0]),np.array([0.0])]
        acol = pyfits.Column(name='testa',format='PD()',array=a)
        tbhdu = pyfits.new_table([acol])
        tbhdu.writeto('newtable.fits')
        tbhdu1 = pyfits.open('newtable.fits')

        for j in range(0,3):
            for i in range(0,len(a[j])):
                self.assertEqual(tbhdu1[1].data.field(0)[j][i], a[j][i])

        tbhdu1.close()
        os.remove('newtable.fits')

    def testVariableLengthTableFormatPAFromObjectArray(self):
        a = np.array([np.array(['a', 'b', 'c']), np.array(['d', 'e']),
                      np.array(['f'])], 'O')
        acol = pyfits.Column(name='testa', format='PA()', array=a)
        tbhdu = pyfits.new_table([acol])
        tbhdu.writeto('newtable.fits')
        hdul = pyfits.open('newtable.fits')

        for j in range(0,3):
            for i in range(0,len(a[j])):
                self.assertEqual(hdul[1].data.field(0)[j][i], a[j][i])

        hdul.close()
        os.remove('newtable.fits')

    def testVariableLengthTableFormatPAFromList(self):
        a = ['a', 'ab', 'abc']
        acol = pyfits.Column(name='testa', format='PA()', array=a)
        tbhdu = pyfits.new_table([acol])
        tbhdu.writeto('newtable.fits')
        hdul = pyfits.open('newtable.fits')

        for j in range(0,3):
            for i in range(0,len(a[j])):
                self.assertEqual(hdul[1].data.field(0)[j][i], a[j][i])

        hdul.close()
        os.remove('newtable.fits')

    def testFITS_recColumnAccess(self):
        t=pyfits.open(os.path.join(data_dir, 'table.fits'))
        tbdata = t[1].data
        self.assertEqual(tbdata.V_mag.all(), tbdata.field('V_mag').all())
        self.assertEqual(tbdata.V_mag.all(), tbdata['V_mag'].all())

        t.close()

    def testTableWithZeroWidthColumn(self):
        hdul = pyfits.open(os.path.join(data_dir, 'zerowidth.fits'))
        tbhdu = hdul[2] # This HDU contains a zero-width column 'ORBPARM'
        self.assert_('ORBPARM' in tbhdu.columns.names)
        # The ORBPARM column should not be in the data, though the data should
        # be readable
        self.assert_('ORBPARM' not in tbhdu.data.names)
        # Verify that some of the data columns are still correctly accessible
        # by name
        self.assert_(comparefloats(
            tbhdu.data[0]['STABXYZ'],
            np.array([499.85566663, -1317.99231554, -735.18866164],
                     dtype=np.float64)))
        self.assertEqual(tbhdu.data[0]['NOSTA'], 1)
        self.assertEqual(tbhdu.data[0]['MNTSTA'], 0)
        hdul.writeto('newtable.fits')
        hdul.close()
        hdul = pyfits.open('newtable.fits')
        tbhdu = hdul[2]
        # Verify that the previous tests still hold after writing
        self.assert_('ORBPARM' in tbhdu.columns.names)
        self.assert_('ORBPARM' not in tbhdu.data.names)
        self.assert_(comparefloats(
            tbhdu.data[0]['STABXYZ'],
            np.array([499.85566663, -1317.99231554, -735.18866164],
                     dtype=np.float64)))
        self.assertEqual(tbhdu.data[0]['NOSTA'], 1)
        self.assertEqual(tbhdu.data[0]['MNTSTA'], 0)
        hdul.close()
        os.remove('newtable.fits')

    def testStringColumnPadding(self):
        a = ['img1', 'img2', 'img3a', 'p']
        s = 'img1\x00\x00\x00\x00\x00\x00' \
            'img2\x00\x00\x00\x00\x00\x00' \
            'img3a\x00\x00\x00\x00\x00' \
            'p\x00\x00\x00\x00\x00\x00\x00\x00\x00'

        acol = pyfits.Column(name='MEMNAME', format='A10',
                             array=np.char.array(a))
        ahdu = pyfits.new_table([acol])
        self.assertEqual(ahdu.data.tostring().decode('raw-unicode-escape'), s)

        ahdu = pyfits.new_table([acol], tbtype='TableHDU')
        self.assertEqual(ahdu.data.tostring().decode('raw-unicode-escape'),
                         s.replace('\x00', ' '))

    def testMultiDimensionalColumns(self):
        """
        Tests the multidimensional column implementation with both numeric
        arrays and string arrays.
        """

        data = pyfits.rec.array(
            [([1, 2, 3, 4], 'row1' * 2),
             ([5, 6, 7, 8], 'row2' * 2),
             ([9, 1, 2, 3], 'row3' * 2)], formats='4i4,a8')

        thdu = pyfits.new_table(data)
        # Modify the TDIM fields to my own specification
        thdu.header.update('TDIM1', '(2,2)')
        thdu.header.update('TDIM2', '(4,2)')

        thdu.writeto('newtable.fits')

        hdul = pyfits.open('newtable.fits')
        thdu = hdul[1]

        c1 = thdu.data.field(0)
        c2 = thdu.data.field(1)

        hdul.close()
        os.remove('newtable.fits')

        self.assertEqual(c1.shape, (3, 2, 2))
        self.assertEqual(c2.shape, (3, 2))
        self.assertTrue((c1 == np.array([[[1, 2], [3, 4]],
                                         [[5, 6], [7, 8]],
                                         [[9, 1], [2, 3]]])).all())
        self.assertTrue((c2 == np.array([['row1', 'row1'],
                                         ['row2', 'row2'],
                                         ['row3', 'row3']])).all())

        # Test setting the TDIMn header based on the column data
        data = np.zeros(3, dtype=[('x', 'f4'), ('s', 'S5', 4)])
        data['x'] = 1, 2, 3
        data['s'] = 'ok'
        pyfits.writeto('newtable.fits', data)

        t = pyfits.getdata('newtable.fits')
        os.remove('newtable.fits')

        self.assertEqual(t.field(1).dtype.str[-1], '5')
        self.assertEqual(t.field(1).shape, (3, 4))

        # Like the previous test, but with an extra dimension (a bit more
        # complicated)
        data = np.zeros(3, dtype=[('x', 'f4'), ('s', 'S5', (4, 3))])
        data['x'] = 1, 2, 3
        data['s'] = 'ok'
        pyfits.writeto('newtable.fits', data)

        t = pyfits.getdata('newtable.fits')
        os.remove('newtable.fits')

        self.assertEqual(t.field(1).dtype.str[-1], '5')
        self.assertEqual(t.field(1).shape, (3, 4, 3))

    def testSlicing(self):
        """Regression test for #52."""

        f = pyfits.open(os.path.join(data_dir, 'table.fits'))
        data = f[1].data
        targets = data.field('target')
        s = data[:]
        self.assert_((s.field('target') == targets).all())
        for n in range(len(targets) + 2):
            s = data[:n]
            self.assert_((s.field('target') == targets[:n]).all())
            s = data[n:]
            self.assert_((s.field('target') == targets[n:]).all())
        s = data[::2]
        self.assert_((s.field('target') == targets[::2]).all())
        s = data[::-1]
        self.assert_((s.field('target') == targets[::-1]).all())

    def testArraySlicing(self):
        """Regression test for #55."""

        f = pyfits.open(os.path.join(data_dir, 'table.fits'))
        data = f[1].data
        s1 = data[data['target'] == 'NGC1001']
        s2 = data[np.where(data['target'] == 'NGC1001')]
        s3 = data[[0]]
        s4 = data[:1]
        for s in [s1, s2, s3, s4]:
            self.assert_(isinstance(s, pyfits.FITS_rec))
        self.assert_((s1 == s2).all())
        self.assert_((s2 == s3).all())
        self.assert_((s3 == s4).all())


if __name__ == '__main__':
    unittest.main()

