import unittest
import pyfits
import numpy as np

class TestPyfitsImageFunctions(unittest.TestCase):

    def setUp(self):
        # Perform set up actions (if any)
        pass
    
    def tearDown(self):
        # Perform clean-up actions (if any)
        pass
    
    def testCardConstructorDefaultArgs(self):
        # Test the constructor with default argument values.
        c=pyfits.Card()
        self.assertEqual('',c.key)

    def testFromstringSetAttributeAscardimage(self):
        # test fromstring() which will overwrite the values in the constructor
        c=pyfits.Card('abc', 99).fromstring('xyz     = 100')
        self.assertEqual(100,c.value)

        # test set attribute and  ascardimage() using the most updated attributes
        c.value=200
        self.assertEqual(c.ascardimage(),"XYZ     =                  200                                                  ")

    def testString(self):
        # test string value
        c=pyfits.Card('abc','<8 ch')
        self.assertEqual(str(c),"ABC     = '<8 ch   '                                                            ")
        c=pyfits.Card('nullstr','')
        self.assertEqual(str(c),"NULLSTR = ''                                                                    ")

    def testBooleanValueCard(self):
        # Boolean value card
        c=pyfits.Card("abc", pyfits.TRUE)
        self.assertEqual(str(c),"ABC     =                    T                                                  ")

        c=pyfits.Card().fromstring('abc     = F')
        self.assertEqual(c.value,False)
        
    def testLongIntegerNumber(self):
        # long integer number
        c=pyfits.Card('long_int', -467374636747637647347374734737437)
        self.assertEqual(str(c),"LONG_INT= -467374636747637647347374734737437                                    ")

    def testFloatingPointNumber(self):
        # floating point number
        c=pyfits.Card('floatnum', -467374636747637647347374734737437.)
        self.assertEqual(str(c),"FLOATNUM= -4.673746367476376E+32                                                ")

    def testComplexValue(self):
        # complex value
        c=pyfits.Card('abc',1.2345377437887837487e88+6324767364763746367e-33j)
        self.assertEqual(str(c),"ABC     = (1.234537743788784E+88, 6.324767364763747E-15)                        ")

## card image constructed from key/value/comment is too long (non-string value)
#>>> c=pyfits.Card('abc',9,'abcde'*20)
#>>> print c
#card is too long, comment is truncated.
#ABC     =                    9 / abcdeabcdeabcdeabcdeabcdeabcdeabcdeabcdeabcdeab
#>>> c=pyfits.Card('abc', 'a'*68, 'abcdefg')
#>>> c
#card is too long, comment is truncated.
#ABC     = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'

## the constrctor will filter out illegal data structures...
#>>> c=pyfits.Card("abc", value=(2,3))
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 105, in __init__
    #self.value = value
  #File "./pyfits.py", line 154, in __setattr__
    #raise ValueError, 'Illegal value %s' % str(val)
#ValueError: Illegal value (2, 3)

#>>> c=pyfits.Card('key',[],'comment')
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 103, in __init__
    #self.value = value
  #File "./pyfits.py", line 146, in __setattr__
    #raise ValueError, 'Illegal value %s' % val
#ValueError: Illegal value []

## or keywords too long
#>>> c=pyfits.Card("abcdefghi", "long")
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 104, in __init__
    #self.key = key
  #File "./pyfits.py", line 145, in __setattr__
    #raise ValueError, 'keyword name %s is too long (> 8)' % val
#ValueError: keyword name abcdefghi is too long (> 8), use HIERARCH.

## will not allow illegal characters in key when using constructor
#>>> c=pyfits.Card('abc+',9)
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 114, in __init__
    #self.key = key
  #File "./pyfits.py", line 153, in __setattr__
    #self._checkKeyText(val)
  #File "./pyfits.py", line 270, in _checkKeyText
    #raise ValueError, 'Illegal keyword name %s' % val
#ValueError: Illegal keyword name 'ABC+'

## the ascardimage() verifies the comment string to be ASCII text
#>>> c=pyfits.Card().fromstring('abc     = +  2.1   e + 12 / abcde'+chr(0x00))
#>>> print c.ascardimage()
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "/data/litchi5/hsu/python/PyFITS/latest/pyfits.py", line 193, in ascardimage
    #self._check('fix')
  #File "/data/litchi5/hsu/python/PyFITS/latest/pyfits.py", line 457, in _check
    #self._checkText(_str)
  #File "/data/litchi5/hsu/python/PyFITS/latest/pyfits.py", line 275, in _checkText
    #raise ValueError, 'Unprintable string %s' % repr(val)
#ValueError: Unprintable string 'abcde\\x00                                              '

## commentary cards
#>>> c=pyfits.Card("history","A commentary card's value has no quotes around it.")
#>>> print c
#HISTORY A commentary card's value has no quotes around it.                      
#>>> c=pyfits.Card("comment", "A commentary card has no comment.", "comment")
#>>> print c
#COMMENT A commentary card has no comment.                                       

    def testCommentaryCardCreatedByFromstring(self):
        # commentary card created by fromstring()
        c=pyfits.Card().fromstring("COMMENT card has no comments. / text after slash is still part of the value.")
        self.assertEqual(c.value,'card has no comments. / text after slash is still part of the value.')
        self.assertEqual(c.comment,'')

    def testCommentaryCardWillNotParseNumericalValue(self):
        # commentary card will not parse the numerical value
        c=pyfits.Card().fromstring("history  (1, 2)")
        self.assertEqual(str(c.ascardimage()),"HISTORY  (1, 2)                                                                 ")

    def testEqualSignAfterColumn8(self):
        # equal sign after column 8 of a commentary card will be part ofthe string value
        c=pyfits.Card().fromstring("history =   (1, 2)")
        self.assertEqual(str(c.ascardimage()),"HISTORY =   (1, 2)                                                              ")

    def testSpecifyUndefinedValue(self):
        # this is how to specify an undefined value
        c=pyfits.Card("undef", pyfits.UNDEFINED)
        self.assertEqual(str(c),"UNDEF   =                                                                       ")

    def testComplexNumberUsingStringInput(self):
        # complex number using string input
        c=pyfits.Card().fromstring('abc     = (8, 9)')
        self.assertEqual(str(c.ascardimage()),"ABC     =               (8, 9)                                                  ")

    def testFixableNonStandardFITScard(self):
        # fixable non-standard FITS card will keep the original format
        c=pyfits.Card().fromstring('abc     = +  2.1   e + 12')
        self.assertEqual(c.value,2100000000000.0)
        self.assertEqual(str(c.ascardimage()),"ABC     =             +2.1E+12                                                  ")

    def testFixableNonFSC(self):
        # fixable non-FSC: if the card is not parsable, it's value will be assumed
        # to be a string and everything after the first slash will be comment
        c= pyfits.Card().fromstring("no_quote=  this card's value has no quotes / let's also try the comment")
        self.assertEqual(str(c.ascardimage()),"NO_QUOTE= 'this card''s value has no quotes' / let's also try the comment       ")

    def testUndefinedValueUsingStringInput(self):
        # undefined value using string input
        c=pyfits.Card().fromstring('abc     =    ')
        self.assertEqual(str(c.ascardimage()),"ABC     =                                                                       ")

    def testMisalocatedEqualSign(self):
        # test mislocated "=" sign
        c=pyfits.Card().fromstring('xyz= 100')
        self.assertEqual(c.key,'XYZ')
        self.assertEqual(c.value,100)
        self.assertEqual(str(c.ascardimage()),"XYZ     =                  100                                                  ")

    def testEqualOnlyUpToColumn10(self):
        # the test of "=" location is only up to column 10
        c=pyfits.Card().fromstring("histo       =   (1, 2)")
        self.assertEqual(str(c.ascardimage()),"HISTO   = '=   (1, 2)'                                                          ")
        c=pyfits.Card().fromstring("   history          (1, 2)")
        self.assertEqual(str(c.ascardimage()),"HISTO   = 'ry          (1, 2)'                                                  ")

## verification
#>>> c=pyfits.Card().fromstring('abc= a6')
#>>> c.verify()
#Output verification result:
#Card image is not FITS standard (equal sign not at column 8).
#>>> print c
#abc= a6                                                                         
#>>> c.verify('fix')
#Output verification result:
  #Fixed card to be FITS standard.: ABC
#>>> c
#ABC     = 'a6      '                                                            

## test long string value
#>>> c=pyfits.Card('abc','long string value '*10, 'long comment '*10)
#>>> print80(str(c))
#ABC     = 'long string value long string value long string value long string &' 
#CONTINUE  'value long string value long string value long string value long &'  
#CONTINUE  'string value long string value long string value &'                  
#CONTINUE  '&' / long comment long comment long comment long comment long        
#CONTINUE  '&' / comment long comment long comment long comment long comment     
#CONTINUE  '&' / long comment                                                    

## if a word in a long string is too long, it will be cut in the middle
#>>> c=pyfits.Card('abc','longstringvalue'*10, 'longcomment'*10)
#>>> print80(str(c))
#ABC     = 'longstringvaluelongstringvaluelongstringvaluelongstringvaluelongstr&'
#CONTINUE  'ingvaluelongstringvaluelongstringvaluelongstringvaluelongstringvalu&'
#CONTINUE  'elongstringvalue&'                                                   
#CONTINUE  '&' / longcommentlongcommentlongcommentlongcommentlongcommentlongcomme
#CONTINUE  '&' / ntlongcommentlongcommentlongcommentlongcomment                  

## long string value via fromstring() method
#>>> c=pyfits.Card().fromstring(pyfits.core._pad("abc     = 'longstring''s testing  &  ' / comments in line 1")+pyfits.core._pad("continue  'continue with long string but without the ampersand at the end' / ")+pyfits.core._pad("continue  'continue must have string value (with quotes)' / comments with ''. "))
#>>> print80(c.ascardimage())
#ABC     = 'longstring''s testing  continue with long string but without the &'  
#CONTINUE  'ampersand at the endcontinue must have string value (with quotes)&'  
#CONTINUE  '&' / comments in line 1 comments with ''.                            

## The function "open" reads a FITS file into an HDUList object.  There are
## three modes to open: "readonly" (the default), "append", and "update".

## Open a file read-only (the default mode), the content of the FITS file
## are read into memory.
#>>> r=pyfits.open('test0.fits')                 # readonly

## data parts are latent instantiation, so if we close the HDUList without
## touching data, data can not be accessed.
#>>> r.close()
#>>> r[1].data[:2,:2]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "pyfits.py", line 765, in __getattr__
    #self._file.seek(self._datLoc)
#ValueError: I/O operation on closed file

#>>> r=pyfits.open('test0.fits')

## Use the "info" method for a summary of the FITS file's content.
#>>> r.info()
#Filename: test0.fits
#No.    Name         Type      Cards   Dimensions   Format
#0    PRIMARY     PrimaryHDU     138  ()            int16
#1    SCI         ImageHDU        61  (400, 400)    int16
#2    SCI         ImageHDU        61  (400, 400)    int16
#3    SCI         ImageHDU        61  (400, 400)    int16
#4    SCI         ImageHDU        61  (400, 400)    int16

## Get a keyword value.  An extension can be referred by name or by number.
## Both extension and keyword names are case insensitive.
#>>> r['primary'].header['naxis']
#0
#>>> r[0].header['naxis']
#0

## If there are more than one extension with the same EXTNAME value, the
## EXTVER can be used (as the second argument) to distinguish the extension.
#>>> r['sci',1].header['detector']
#1

## append (using "update()") a new card
#>>> r[0].header.update('xxx',1.234e56)
#>>> r[0].header.ascard[-3:]
#EXPFLAG = 'NORMAL            ' / Exposure interruption indicator                FILENAME= 'vtest3.fits'        / File name                                      XXX     =            1.234E+56                                                  

## rename a keyword
#>>> r[0].header.rename_key('filename','fname')
#>>> r[0].header.rename_key('fname','history')
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "/data/litchi5/hsu/python/PyFITS/latest/pyfits.py", line 949, in rename_key
    #raise ValueError, 'Regular and commentary keys can not be renamed to each other.'
#ValueError: Regular and commentary keys can not be renamed to each other.
#>>> r[0].header.rename_key('fname','simple')
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "/data/litchi5/hsu/python/PyFITS/latest/pyfits.py", line 951, in rename_key
    #raise ValueError, 'Intended keyword %s already exists in header.' % newkey
#ValueError: Intended keyword SIMPLE already exists in header.
#>>> r[0].header.rename_key('fname','filename')

## get a subsection of data
#>>> r[2].data[:3,:3]
#array([[349, 349, 348],
       #[348, 348, 348],
       #[349, 349, 350]], dtype=int16)

## We can create a new FITS file by opening a new file with "append" mode.
#>>> n=pyfits.open('test_new.fits',mode='append')

## Append the primary header and the 2nd extension to the new file.
#>>> n.append(r[0])
#>>> n.append(r[2])

## The flush method will write the current HDUList object back to the newly
## created file on disk.  The HDUList is still open and can be further operated.
#>>> n.flush()
#>>> n[1].data[1,1]
#348

## modify a data point
#>>> n[1].data[1,1]=99

## When the file is closed, the most recent additions of extension(s) since
## last flush() will be appended, but any HDU already existed at the last
## flush will not be modified
#>>> n.close()

## If an existing file is opened with "append" mode, like the readonly mode,
## the HDU's will be read into the HDUList which can be modified in memory
## but can not be written back to the original file.  A file opened with
## append mode can only add new HDU's.
#>>> os.rename('test_new.fits', 'test_append.fits')
#>>> a=pyfits.open('test_append.fits',mode='append')

## The above change did not take effect since this was made after the flush().
#>>> a[1].data[1,1]
#348

#>>> a.append(r[1])
#>>> a.close()

## When changes are made to an HDUList which was opened with "update" mode,
## they will be written back to the original file when a flush/close is called.
#>>> os.rename('test_append.fits', 'test_update.fits')
#>>> u=pyfits.open('test_update.fits',mode='update')

## When the changes do not alter the size structures of the original (or since
## last flush) HDUList, the changes are written back "in place".
#>>> u[0].header['rootname']
#'U2EQ0201T'
#>>> u[0].header['rootname']='abc'
#>>> u[1].data[1,1]
#348
#>>> u[1].data[1,1]=99
#>>> u.flush()

## If the changes affect the size structure, e.g. adding or deleting HDU(s),
## header was expanded or reduced beyond existing number of blocks (2880 bytes
## in each block), or change the data size, the HDUList is written to a
## temporary file, the original file is deleted, and the temporary file is
## renamed to the original file name and reopened in the update mode.
## To a user, these two kinds of updating writeback seem to be the same, unless
## the optional argument in flush or close is set to 1.
#>>> del u[2]
#>>> u.flush()

## the write method in HDUList class writes the current HDUList, with
## all changes made up to now, to a new file.  This method works the same
## disregard the mode the HDUList was opened with.
#>>> u.append(r[3])
#>>> u.writeto('test_new.fits')


## Another useful new HDUList method is readall.  It will "touch" the data parts
## in all HDUs, so even if the HDUList is closed, we can still operate on
## the data.
#>>> r=pyfits.open('test0.fits')
#>>> r.readall()
#>>> r.close()
#>>> r[1].data[1,1]
#314

## create an HDU with data only
#>>> data = numpy.ones((3,5), dtype=np.float32)
#>>> hdu=pyfits.ImageHDU(data=data, name='SCI')
#>>> hdu.data
#array([[ 1.,  1.,  1.,  1.,  1.],
       #[ 1.,  1.,  1.,  1.,  1.],
       #[ 1.,  1.,  1.,  1.,  1.]], dtype=float32)


## create an HDU with header and data
## notice that the header has the right NAXIS's since it is constructed with
## ImageHDU
#>>> hdu2=pyfits.ImageHDU(header=r[1].header, data=numpy.array([1,2]))
#>>> hdu2.header.ascard[1:5]
#BITPIX  =                   32 / array data type                                NAXIS   =                    1 / number of array dimensions                     NAXIS1  =                    2                                                  PCOUNT  =                    0 / number of parameters                           

## memory mapping
#>>> f1 = pyfits.open('test0.fits', memmap=1)
#>>> f1.close()

## verification on output
## make a defect HDUList first
#>>> x = pyfits.ImageHDU()
#>>> hdu = pyfits.HDUList(x)     # HDUList can take a list or one single HDU
#>>> hdu.verify()
#Output verification result:
#HDUList's 0th element is not a primary HDU.
#>>> hdu.writeto('test_new2.fits','fix')
#Output verification result:
#HDUList's 0th element is not a primary HDU.  Fixed by inserting one as 0th HDU.

    def testSection(self):
        # section testing
        fs=pyfits.open('arange.fits')
        self.assertEqual(fs[0].section[3,2,5],np.array([357]))
        self.assertEqual(fs[0].section[3,2,:].all(),np.array([352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362]).all())
        self.assertEqual(fs[0].section[3,2,4:].all(),np.array([356, 357, 358, 359, 360, 361, 362]).all())
        self.assertEqual(fs[0].section[3,2,:8].all(),np.array([352, 353, 354, 355, 356, 357, 358, 359]).all())
        self.assertEqual(fs[0].section[3,2,-8:8].all(),np.array([355, 356, 357, 358, 359]).all())
        self.assertEqual(fs[0].section[3,2:5,:].all(),np.array([[352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362],
                                                                [363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373],
                                                                [374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384]]).all())

        self.assertEqual(fs[0].section[3,:,:][:3,:3].all(),np.array([[330, 331, 332],
                                                                     [341, 342, 343],
                                                                     [352, 353, 354]]).all())

#>>> fs[0].section[3,2:5,:8]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 1588, in __getitem__
    #raise IndexError, 'Subsection data is not contiguous.'
#IndexError: Subsection data is not contiguous.

#>>> fs[0].section[3,2:5,3]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 1588, in __getitem__
    #raise IndexError, 'Subsection data is not contiguous.'
#IndexError: Subsection data is not contiguous.

#>>> dtp(fs[0].section[3:6,:,:][:3,:3,:3])
#. array([[[330, 331, 332],
#.         [341, 342, 343],
#.         [352, 353, 354]],
#.
#.        [[440, 441, 442],
#.         [451, 452, 453],
#.         [462, 463, 464]],
#.
#.        [[550, 551, 552],
#.         [561, 562, 563],
#.         [572, 573, 574]]])

#>>> dtp(fs[0].section[:,:,:][:3,:2,:2])
#. array([[[  0,   1],
#.         [ 11,  12]],
#.
#.        [[110, 111],
#.         [121, 122]],
#.
#.        [[220, 221],
#.         [231, 232]]])

#>>> fs[0].section[:,2,:]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 1588, in __getitem__
    #raise IndexError, 'Subsection data is not contiguous.'
#IndexError: Subsection data is not contiguous.
#>>> fs[0].section[:,2:5,:]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 1588, in __getitem__
    #raise IndexError, 'Subsection data is not contiguous.'
#IndexError: Subsection data is not contiguous.
#>>> fs[0].section[3:6,3,:]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 1588, in __getitem__
    #raise IndexError, 'Subsection data is not contiguous.'
#IndexError: Subsection data is not contiguous.
#>>> fs[0].section[3:6,3:7,:]
#Traceback (innermost last):
  #File "<console>", line 1, in ?
  #File "./pyfits.py", line 1588, in __getitem__
    #raise IndexError, 'Subsection data is not contiguous.'
#IndexError: Subsection data is not contiguous.


## clean up
#>>> os.remove('test_update.fits')
#>>> os.remove('test_new.fits')
#>>> os.remove('test_new2.fits')


    #def testopen(self):
        #...
        
    #def testclose(self):
        #...
    
if __name__ == '__main__':
    unittest.main()
    
