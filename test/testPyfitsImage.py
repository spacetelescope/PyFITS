import unittest
import pyfits

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
#>>> c=pyfits.Card('nullstr','')
#>>> print c
#NULLSTR = ''                                                                    

## Boolean value card
#>>> c=pyfits.Card("abc", pyfits.TRUE)
#>>> print c
#ABC     =                    T                                                  

#>>> c=pyfits.Card().fromstring('abc     = F')
#>>> print c.value
#False

## long integer number
#>>> c=pyfits.Card('long_int', -467374636747637647347374734737437)
#>>> print c
#LONG_INT= -467374636747637647347374734737437                                    

## floating point number
#>>> c=pyfits.Card('floatnum', -467374636747637647347374734737437.)
#>>> print c
#FLOATNUM= -4.673746367476376E+32                                                

## complex value
#>>> c=pyfits.Card('abc',1.2345377437887837487e88+6324767364763746367e-33j)
#>>> print c
#ABC     = (1.234537743788784E+88, 6.324767364763747E-15)                        
    #def testopen(self):
        #...
        
    #def testclose(self):
        #...
    
if __name__ == '__main__':
    unittest.main()
    
