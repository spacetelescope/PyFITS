import unittest
import pyfits
import numpy
import exceptions,os,sys
import numpy as num
from pyfits import rec
from numpy import char as chararray

# Define a junk file for redirection of stdout
jfile = "junkfile.fits"

def comparefloats(a, b):
    """Compare two float scalars or arrays and see if they are consistent
    
    Consistency is determined ensuring the difference is less than the
    expected amount. Return True if consistent, False if any differences"""
    aa = a
    bb = b
    # compute expected precision
    if aa.dtype.name=="float32" or bb.dtype.name=='float32':
        precision = 0.000001
    else:
        precision = 0.0000000000000001
    precision = 0.00001 # until precision problem is fixed in pyfits
#    print aa,aa.shape,type(aa)
#    print bb,bb.shape,type(bb)
    diff = num.absolute(aa-bb)
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
    
    nfieldsa = len(a.dtype.names)
    nfieldsb = len(b.dtype.names)
    if nfieldsa != nfieldsb:
        print "number of fields don't match"
        return False
    for i in range(nfieldsa):
        fielda = a.field(i)
        fieldb = b.field(i)
        if type(fielda) != type(fieldb):
            print "type(fielda): ",type(fielda)," fielda: ",fielda
            print "type(fieldb): ",type(fieldb)," fieldb: ",fieldb
            print 'field %d type differs' % i
            return False
        if not isinstance(fielda, num.chararray) and \
               isinstance(fielda[0], num.floating):
            if not comparefloats(fielda, fieldb):
                print "fielda: ",fielda
                print "fieldb: ",fieldb
                print 'field %d differs' % i
                return False
        else:
            if num.any(fielda != fieldb):
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
        pass

    def testOpen(self):
        # open some existing FITS files:
        tt=pyfits.open('tb.fits')
        fd=pyfits.open('test0.fits')

        # create some local arrays
        a1=chararray.array(['abc','def','xx'])
        r1=num.array([11.,12.,13.],dtype=num.float32)

        # create a table from scratch, using a mixture of columns from existing
        # tables and locally created arrays:

        # first, create individual column definitions

        c1=pyfits.Column(name='abc',format='3A', array=a1)
        c2=pyfits.Column(name='def',format='E', array=r1)
        c3=pyfits.Column(name='xyz',format='I', array=num.array([3,4,5],dtype='i2'))
        c4=pyfits.Column(name='t1', format='I', array=num.array([1,2,3],dtype='i2'))
        c5=pyfits.Column(name='t2', format='C', array=num.array([3+3j,4+4j,5+5j],dtype='c8'))

        # Note that X format must be two-D array
        c6=pyfits.Column(name='t3', format='X', array=num.array([[0],[1],[0]],dtype=num.uint8))
        c7=pyfits.Column(name='t4', format='J', array=num.array([101,102,103],dtype='i4'))
        c8=pyfits.Column(name='t5', format='11X', array=num.array([[1,1,0,1,0,1,1,1,0,0,1],[0,1,1,1,1,0,0,0,0,1,0],[1,1,1,0,0,1,1,1,1,1,1]],dtype=num.uint8))

        # second, create a column-definitions object for all columns in a table

        x = pyfits.ColDefs([c1,c2,c3,c4,c5,c6,c7,c8])

        # create a new binary table HDU object by using the new_table function

        tbhdu=pyfits.new_table(x)

        # another way to create a table is by using existing table's information:

        x2=pyfits.ColDefs(tt[1])
        t2=pyfits.new_table(x2, nrows=2)
        ra = rec.array([
            (1, 'abc', 3.7000002861022949, 0),
            (2, 'xy ', 6.6999998092651367, 1)], names='c1, c2, c3, c4')

        self.assertEqual(comparerecords(t2.data, ra),True)

        # the table HDU's data is a subclass of a record array, so we can access
        # one row like this:

        self.assertEqual(str(tbhdu.data[1]),"('def', 12.0, 4, 2, (4+4j), array([ True], dtype=bool), 102, array([False,  True,  True,  True,  True, False, False, False, False,\n        True, False], dtype=bool))")

        # and a column like this:
        self.assertEqual(str(tbhdu.data.field('abc')),"['abc' 'def' 'xx']")

        # An alternative way to create a column-definitions object is from an
        # existing table.
        xx=pyfits.ColDefs(tt[1])

        # now we write out the newly created table HDU to a FITS file:
        fout = pyfits.HDUList(pyfits.PrimaryHDU())
        fout.append(tbhdu)
        fout.writeto('tableout1.fits')

        f2 = pyfits.open('tableout1.fits')
        temp = f2[1].data.field(7)
        self.assertEqual(str(temp[0]),"[ True  True False  True False  True  True  True False False  True]")
        os.remove('tableout1.fits')


        # An alternative way to create an output table FITS file:
        fout2=pyfits.open('tableout2.fits','append')
        fout2.append(fd[0])
        fout2.append(tbhdu)
        fout2.close()
        os.remove("tableout2.fits")

    def testBinaryTable(self):
        # binary table:
        t=pyfits.open('tb.fits')
        self.assertEqual(t[1].header['tform1'],'1J')
        
        tmpfile = open(jfile,'w')
        sys.stdout = tmpfile
        t[1].columns.info()
        sys.stdout = sys.__stdout__
        tmpfile.close()
        tmpfile = open(jfile,'r')
        tmplist = tmpfile.readlines()
        tmpfile.close()
        os.remove(jfile)
        self.assertEqual(tmplist,['name:\n', "     ['c1', 'c2', 'c3', 'c4']\n",
                                  'format:\n', "     ['1J', '3A', '1E', '1L']\n", 
                                  'unit:\n', "     ['', '', '', '']\n", 'null:\n', 
                                  "     [-2147483647, '', '', '']\n", 'bscale:\n', 
                                  "     ['', '', 3, '']\n", 'bzero:\n', 
                                  "     ['', '', 0.40000000000000002, '']\n", 
                                  'disp:\n', "     ['I11', 'A3', 'G15.7', 'L6']\n", 
                                  'start:\n', "     ['', '', '', '']\n", 'dim:\n', 
                                  "     ['', '', '', '']\n"])
        ra = rec.array([
            (1, 'abc', 3.7000002861022949, 0),
            (2, 'xy ', 6.6999998092651367, 1)], names='c1, c2, c3, c4')

        self.assertEqual(comparerecords(t[1].data, ra[:2]),True)

        # Change scaled field and scale back to the original array
        t[1].data.field('c4')[0] = 1
        t[1].data._scale_back()
        self.assertEqual(str(rec.recarray.field(t[1].data,'c4')),"[84 84]")

        # look at data column-wise
        self.assertEqual(t[1].data.field(0).all(),num.array([1, 2]).all())

        # When there are scaled columns, the raw data are in data._parent

    def testAsciiTable(self):
        # ASCII table
        a=pyfits.open('ascii.fits')
        ra1 = rec.array([
            (10.123000144958496, 37),
            (5.1999998092651367, 23),
            (15.609999656677246, 17),
            (0.0, 0),
            (345.0, 345)], names='c1, c2')
        self.assertEqual(comparerecords(a[1].data, ra1),True)

        # Test slicing
        a2 = a[1].data[2:][2:]
        ra2 = rec.array([(345.0,345)],names='c1, c2')

        self.assertEqual(comparerecords(a2, ra2),True)

        self.assertEqual(a2.field(1).all(),num.array([345]).all())

        ra3 = rec.array([
            (10.123000144958496, 37),
            (15.609999656677246, 17),
            (345.0, 345)
            ], names='c1, c2')

        self.assertEqual(comparerecords(a[1].data[::2], ra3),True)

        # Test Start Column

        a1 = chararray.array(['abcd','def'])
        r1 = numpy.array([11.,12.])
        c1 = pyfits.Column(name='abc',format='A3',start=19,array=a1)
        c2 = pyfits.Column(name='def',format='E',start=3,array=r1)
        c3 = pyfits.Column(name='t1',format='I',array=[91,92,93])
        hdu = pyfits.new_table([c2,c1,c3],tbtype='TableHDU')


        self.assertEqual(hdu.data.dtype.fields,{'abc':(numpy.dtype('|S3'),18),
                                                'def':(numpy.dtype('|S14'),2),
                                                't1':(numpy.dtype('|S10'),21)})
        hdu.writeto('toto.fits',clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        os.remove('toto.fits')
        

    def testVariableLengthColumns(self):
        col_list = []
        col_list.append(pyfits.Column(name='QUAL_SPE',format='PJ()',array=[[0]*1571]*225))
        tb_hdu = pyfits.new_table(col_list)
        pri_hdu = pyfits.PrimaryHDU()
        hdu_list = pyfits.HDUList([pri_hdu,tb_hdu])
        hdu_list.writeto('toto.fits', clobber=True)
        toto = pyfits.open('toto.fits')
        q = toto[1].data.field('QUAL_SPE') 
        self.assertEqual(q[0][4:8].all(),num.array([0,0,0,0],dtype=numpy.uint8).all())
        os.remove('toto.fits')
    
    def testEndianness(self):
        x = num.ndarray((1,), dtype=object)
        channelsIn = num.array([3], dtype='uint8')
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
        os.remove('testendian.fits')

    def testPyfitsRecarrayToBinTableHDU(self):
        bright=pyfits.rec.array([(1,'Serius',-1.45,'A1V'),\
                                 (2,'Canopys',-0.73,'F0Ib'),\
                                 (3,'Rigil Kent',-0.1,'G2V')],\
                                formats='int16,a20,float32,a10',\
                                names='order,name,mag,Sp')
        hdu=pyfits.BinTableHDU(bright)
        self.assertEqual(comparerecords(hdu.data,bright),True)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        os.remove('toto.fits')

    def testNumpyNdarrayToBinTableHDU(self):
        desc=numpy.dtype({'names':['order','name','mag','Sp'],\
                          'formats':['int','S20','float32','S10']})
        a=numpy.array([(1,'Serius',-1.45,'A1V'),\
                       (2,'Canopys',-0.73,'F0Ib'),\
                       (3,'Rigil Kent',-0.1,'G2V')],dtype=desc)
        hdu=pyfits.BinTableHDU(a)
        self.assertEqual(comparerecords(hdu.data,a.view(pyfits.rec.recarray)),\
                         True)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        os.remove('toto.fits')

    def testNewTableFromPyfitsRecarray(self):
        bright=pyfits.rec.array([(1,'Serius',-1.45,'A1V'),\
                                 (2,'Canopys',-0.73,'F0Ib'),\
                                 (3,'Rigil Kent',-0.1,'G2V')],\
                                formats='int16,a20,float32,a10',\
                                names='order,name,mag,Sp')
        hdu=pyfits.new_table(bright,nrows=2,tbtype='TableHDU')
        s="[(1, 'Serius', -1.45000004768, 'A1V')\n (2, 'Canopys', -0.730000019073, 'F0Ib')]"
        self.assertEqual(str(hdu.data[:]),s)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(str(hdul[1].data[:]),s)
        os.remove('toto.fits')
        hdu=pyfits.new_table(bright,nrows=2)
        tmp=pyfits.rec.array([(1,'Serius',-1.45,'A1V'),\
                              (2,'Canopys',-0.73,'F0Ib')],\
                             formats='int16,a20,float32,a10',\
                             names='order,name,mag,Sp')
        self.assertEqual(comparerecords(hdu.data,tmp),True)
        hdu.writeto('toto.fits', clobber=True)
        hdul = pyfits.open('toto.fits')
        self.assertEqual(comparerecords(hdu.data,hdul[1].data),True)
        os.remove('toto.fits')

if __name__ == '__main__':
    unittest.main()
    
