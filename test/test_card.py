
import unittest, fits

KeywordRegexSuite = unittest.TestSuite

class KeywordRegexCase(unittest.TestCase):
    def setUp(self):
        self.keyre = fits.Card._Card__keywd_RE
    
    def testNotUpperCase(self):
        self.failIf(self.keyre.match("a-z     "))

    def testNoEmbeddedSpaces(self):
        self.failIf(self.keyre.match("A-Z 0-9 "))

    def testKeywordCharacters(self):
        self.failUnless(self.keyre.match("A-Z0-9_-"))

    def testBlankKeyword(self):
        self.failUnless(self.keyre.match("        "))


class ValueRegexCase(unittest.TestCase):

    def setUp(self):
        self.valre = fits.Card._Card__value_RE

    def testNotString(self):
        self.failIf(self.valre.match('\"bad string   \"'))

    def testNotPrintableString(self):
        self.failIf(self.valre.match("'a\tstring '"))

    def testNotBoolean(self):
        self.failIf(self.valre.match("                N"))

    def testNotNumber(self):
        self.failIf(self.valre.match("              1.."))

    def testNotComplex(self):
        self.failIf(self.valre.match("[      1,      1]"))

    def testNotPrintableComment(self):
        self.failIf(self.valre.match("    / a\tcomment"))

    def testValuFieldGroup(self):
        self.failUnless(self.valre.match(14*" ").group("valu_field") == 14*" ")

    def testValuGroup(self):
        self.failUnless(
            self.valre.match("'        '      ").group("valu") == "'        '")

    def testStrgGroup(self):
        self.failUnless(
            self.valre.match("'a''string' ").group("strg") == "a''string")

    def testBoolGroup(self):
        self.failUnless(self.valre.match("%20s" % "T").group("bool") == "T")

    def testNumrGroup1(self):
        self.failUnless(
            self.valre.match("              -00100").group("numr") == "-00100")

    def testNumrGroup2(self):
        self.failUnless(
            self.valre.match("       -00100.0E-001").group("numr") == \
            "-00100.0E-001")

    def testCplxGroup1(self):
        self.failUnless(
            self.valre.match("(     -001,    -002)").group("cplx") == \
            "(     -001,    -002)")

    def testCplxGroup2(self):
        self.failUnless(
            self.valre.match("(-0010.E-1,-0020.E-1)").group("cplx") == \
            "(-0010.E-1,-0020.E-1)")

    def testCommFieldGroup(self):
        self.failUnless(
            self.valre.match("       / comm ").group("comm_field") == \
            "/ comm ")

    def testSeprGroup(self):
        self.failUnless(
            self.valre.match("             / comm ").group("sepr") == "/ ")

    def testCommGroup(self):
        self.failUnless(
            self.valre.match("         / ---------").group("comm") == \
            "---------")


class NumberRegexCase(unittest.TestCase):

    def setUp(self):
        self.numre = fits.Card._Card__number_RE

    def testSignGroup(self):
        self.failUnless(self.numre.match("-00100").group("sign") == "-")

    def testDigtGroup(self):
        self.failUnless(self.numre.match("-00100").group("digt") == "100")


class CommentRegexCase(unittest.TestCase):

    def setUp(self):
        self.comre = fits.Card._Card__comment_RE

    def testNotPrintable(self):
        self.failIf(self.comre.match("  a\tstring   "))

    def testNotPrintable(self):
        self.failUnless(self.comre.match("  a'string   "))


class FormatRegexCase(unittest.TestCase):

    def setUp(self):
        self.fmtre = fits.Card._Card__format_RE
        
    def testBadValueFormat(self):
        self.failIf(self.fmtre.match("    s  / %s "))

    def testNoSeprFormat(self):
        self.failIf(self.fmtre.match("    %s   %s "))

    def testValueFormat(self):
        self.failUnless(self.fmtre.match("    %s      "))

    def testValueSeprFormat(self):
        self.failUnless(self.fmtre.match(" %5.3f  /   "))

    def testCplxFormat(self):
        self.failUnless(self.fmtre.match("(%6.4f, %6.4f)"))

    def testBadCommentFormat(self):
        self.failUnless(self.fmtre.match("    %s  / s "))

    def testEmbeddedPercent(self):
        self.failUnless(self.fmtre.match("    %s  / % %s "))


class InitCase(unittest.TestCase):

    def setUp(self):
        self.fmtre = fits.Card._Card__format_RE

    #  Test keyword values
    def testBadKey1(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card, 1)

    def testBadKey2(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card, "keyword__")

    def testBadKey3(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card, "keyword!")

    def testGoodKey(self):
        self.failUnless(str(fits.Card("keyword   ")) == "%-80s"%"KEYWORD =")

    #  Test for bad values
    def testBadValueString(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "VALUE  ", "bad\tstring")

    def testBadComment(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "VALUE  ", 1, 2)

    def testBadCommentString(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "VALUE  ", 1, "bad\tstring")

    def testBadComment1(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "COMMENT", comment="a comment")

    def testBadEND(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "END    ", "an END card")

    def testBadComment2(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "COMMENT", 1)

    def testCommentString(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "COMMENT", 73*"-")

    #  Test commentary cards
    def testLowerCaseEND(self):
        self.failUnless(str(fits.Card("end")) == "%-80s"%"END")

    def testCOMMENTCard(self):
        self.failUnless(str(fits.Card("comment",72*"-")) == "COMMENT "+72*"-")

    def testHISTORYCard(self):
        self.failUnless(str(fits.Card("history",72*"-")) == "HISTORY "+72*"-")

    def testBLANKCard(self):
        self.failUnless(str(fits.Card("       ",72*"-")) == "        "+72*"-")

    def testBadFormat1(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "VALUE  ", 1, format="d")

    def testBadFormat2(self):
        self.failUnlessRaises(
            fits.FITS_SevereError, fits.Card, "VALUE  ", 1, format=" / %s")

    def testNumberFormat1(self):
        self.failUnless(str(fits.Card("VALUE  ", 1, format="%d")) \
                        == "VALUE   = 1"+69*" ")

    def testComplexFormat(self):
        self.failUnless(str(fits.Card("VALUE  ", 1.-2.j, format="(%f, %f)")) \
                        == "VALUE   = (1.000000, -2.000000)"+49*" ")

    def testNumberFormat2(self):
        self.failUnless(str(fits.Card("VALUE  ", 1, format="%d /")) \
                        == "VALUE   = 1 / "+66*" ")

    def testNumberFormat3(self):
        self.failUnless(str(fits.Card("VALUE  ", 1, format="%d / %s")) \
                        == "VALUE   = 1 / "+66*" ")

    def testCommentFormat(self):
        self.failUnless(str(fits.Card("VALUE  ", 1, "a comment", "%d / %s")) \
                        == "VALUE   = 1 / a comment"+57*" ")

    def testFixedFormat(self):
        self.failUnless(str(fits.Card("VALUE  ", "a'string", 70*"-")) \
                        == "VALUE   = 'a''string'          / "+47*"-")

    #  Check for fixed-format mandatory keywords
    def testMandatoryFormat1(self):
        self.failUnless(str(fits.Card("SIMPLE", fits.FITS.TRUE, "comment")) \
                        == "%-8s= %20s / %-47s" % ("SIMPLE", fits.FITS.TRUE,
                                                   "comment"))

    def testMandatoryFormat2(self):
        self.failUnless(str(fits.Card("NAXIS99", 100, "comment")) \
                        == "%-8s= %20d / %-47s" % ("NAXIS99", 100, "comment"))

    def testMandatoryFormat3(self):
        self.failUnless(str(fits.Card("XTENSION", "IMAGE", "comment")) \
                        == "%-8s= %-20s / %-47s" % ("XTENSION", "'IMAGE   '",
                                                    "comment"))

    def testMandatoryFormat4(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card,
                              "SIMPLE", "T", "comment", "%-20s / %s")

    def testMandatoryFormat5(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card,
                              "NAXIS99", 100, "comment", "%-d / %s")

    def testMandatoryFormat6(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card,
                              "XTENSION", "IMAGE", "comment", "%20s / %s")


class GetAttrCase(unittest.TestCase):

    def setUp(self):
        self.card = fits.Card("")

    #  Check key attribute
    def testKeyAttrib(self):
        self.failUnless(fits.Card("VALUE  ", 1).key == "VALUE")

    #  Check value attribute
    def testCommentValAttr(self):
        self.failUnless(fits.Card("COMMENT", 72*"-").value == 72*"-")

    def testBooleanValAttr(self):
        self.failUnless(fits.Card("BOOLEAN", fits.FITS.TRUE).value \
                        == fits.FITS.TRUE)

    def testStringValAttr(self):
        self.failUnless(fits.Card("STRING ", "O'Hara").value == "O'Hara")

    def testIntegerValAttr(self):
        self.failUnless(fits.Card("v").fromstring("INTEGER = %-70s" % \
                                                  "-00100").value == -100)

    def testFloatValAttr(self):
        self.failUnless(
            fits.Card("v").fromstring(
            "REAL    = %-70s" % "-001.0E2").value == -100.0)

    def testComplexValAttr(self):
        self.failUnless(
            fits.Card("v").fromstring(
            "COMPLEX = (%8s, %8s)%-50s" % (
            "-001.0E2", "-002.0E2", " ")).value == -100.0-200.0j)

    def testNullValAttr(self):
        self.failUnless(fits.Card("NONE   ").value == None)

    def testNonBooleanValAttr(self):
        self.failUnlessRaises(fits.FITS_SevereError, fits.Card(
            "NONBOOL", fits.Boolean("N")).__getattr__, "value")

    #  Check comment attribute
    def testCommentAttr1(self):
        self.failUnless(fits.Card("NO_COMM", 1, 60*"-").comment == 47*"-")

    def testCommentAttr2(self):
        self.failUnless(fits.Card("NO_COMM").comment == None)

    #  Check for attribute error
    def testAttrError(self):
        self.failUnlessRaises(
            AttributeError, fits.Card("VALUE").__getattr__, "attrib")


class SetAttrCase(unittest.TestCase):

    def setUp(self):
        self.card = fits.Card("")

    #  Check END card
    def testEND1(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("END").__setattr__, "key", "END")

    def testEND2(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("END").__setattr__, "value", 1)

    def testEND3(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("END").__setattr__, "comment",
                              "a comment")

    #  Check key attribute
    def testBadKey1(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("VALUE  ", 1,
                                        "a comment").__setattr__, "key", 1)

    def testLongKey(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("VALUE  ", 1, "a comment").__setattr__,
                              "key", "LONGKEYWORD")

    def testBadKey2(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("VALUE  ", 1, "a comment").__setattr__,
                              "key", "BAD KEYWD")

    def testBadValueKey1(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("VALUE  ", 1, "a comment").__setattr__,
                              "key", "COMMENT")

    def testBadValueKey2(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("VALUE  ", 1, "a comment").__setattr__,
                              "key", "END")

    def testBadCommentKey1(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("COMMENT", "a comment").__setattr__,
                              "key", "VALUE  ")

    def testBadCommentKey2(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("COMMENT", "a comment").__setattr__,
                              "key", "END")

    def testGoodValueKey(self):
        self.failIf(fits.Card("VALUE  ", 1, "a comment").__setattr__(
            "key", "NEWVALUE"))

    def testGoodCommentKey(self):
        self.failIf(fits.Card("COMMENT", "a comment").__setattr__(
            "key", "HISTORY"))

    #  Check value attribute
    def testBadStringValue(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("VALUE  ", "a string").__setattr__,
                              "value", "bad\tstring")

    def testBadCommentValue1(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("COMMENT", "a string").__setattr__,
                              "value", "bad\tstring")

    def testBadCommentValue2(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              fits.Card("COMMENT", "a comment").__setattr__,
                              "value", 1)

    def testGoodCommentValue(self):
        self.failIf(fits.Card("COMMENT", "a comment").__setattr__(
            "value", "a new comment"))

    def testGoodNumberValue(self):
        self.failIf(fits.Card("VALUE  ", 1, "a comment").__setattr__(
            "value", 2))

    def testGoodStringValue(self):
        self.failIf(fits.Card("VALUE  ", 1, "a comment").__setattr__(
            "value", "a string"))

    def testGoodComplexValue(self):
        self.failIf(fits.Card("VALUE  ", 1-2j, "a comment").__setattr__(
            "value", 2-3j))

    def testGoodValueFormatted(self):
        self.failIf(fits.Card("VALUE  ", 1, "a comment",
                              format="%d / %s").__setattr__("value", 2))

    #  Check comment attribute
    def testGoodComment(self):
        self.failIf(fits.Card("VALUE  ", 1, "a comment").__setattr__(
            "comment", "a new comment"))

    def testBadComment(self):
        self.failUnlessRaises(AttributeError,
                              fits.Card("COMMENT", "a comment").__setattr__,
                              "comment", "a comment")

    #  Check bad attribute
    def testBadAttrib(self):
        self.failUnlessRaises(AttributeError,
                              fits.Card("COMMENT", "a comment").__setattr__,
                              "bad", 1)

class FromstringCase(unittest.TestCase):

    def setUp(self):
        self.card = fits.Card("")

    #  Test card length
    def testShortCardLength(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              self.card.fromstring, 81*" ")

    def testLongCardLength(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              self.card.fromstring, 79*" ")

    def testCardLength(self):
        self.failUnless(str(self.card.fromstring(80*" ") == 80*" "))

    #  Check keyword syntax
    def testEmbeddedSpaceKey(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              self.card.fromstring, "COM MENT"+72*".")

    def testLowerCaseKey(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              self.card.fromstring, "a-z0-9_-"+72*".")

    def testGoodKey(self):
        self.failUnless(str(self.card.fromstring("A-Z0-9_-"+72*".")) \
                        == "A-Z0-9_-"+72*".")

    #  Check for END card
    def testBadENDCard(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              self.card.fromstring, "END     "+72*".")

    def testGoodENDCard(self):
        self.failUnless(str(self.card.fromstring("END     "+72*" ")) \
                        == "END     "+72*" ")

    #  Check for value card
    def testStringValue(self):
        self.failUnless(
            self.card.fromstring("STRING  = %30s"%"'  a''string  '"+40*" "))

    def testBooleanValue(self):
        self.failUnless(self.card.fromstring("BOOLEAN = %30s"%"T"+40*" "))
        
    def testIntegerValue(self):
        self.failUnless(self.card.fromstring("INTEGER = %30d"%1  +40*" "))

    def testFloatValue1(self):
        self.failUnless(self.card.fromstring("REAL    = %30f"%1.1+40*" "))

    def testFloatValue2(self):
        self.failUnless(self.card.fromstring("REAL    = %30f"% .1+40*" "))

    def testFloatValue3(self):
        self.failUnless(self.card.fromstring("REAL    = %30G"%-1.1E-9+40*" "))

    def testFloatValue4(self):
        self.failUnless(
            self.card.fromstring("REAL    = %-30s"%"-01E-9"+40*" "))

    def testComplexValue(self):
        self.failUnless(
            self.card.fromstring("COMPLEX = (%13f, %13f)"%(1.1,1.1)+40*" "))

    def testNullValue(self):
        self.failUnless(self.card.fromstring("NONE    = "+70*" "))

    def testComment(self):
        self.failUnless(
            self.card.fromstring("COMFIELD= %30d / %-37s"%(1, "a comment")))

    def testBadBoolean(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "BOOLEAN = %30s" % "N" + 40*" ")

    def testBadString1(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "STRING  = %30s" % "\"a'string\""+40*" ")

    def testBadString2(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "STRING  = %30s" % "'a\tstring '"+40*" ")

    def testLowerCaseE(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "REAL    = %30g" % -1.1e-9+40*" ")

    #  Check for fixed-format mandatory keywords
    def testMandatoryFormat1(self):
        self.failUnless(self.card.fromstring("SIMPLE  = %20s" % "T" + 50*" "))

    def testMandatoryFormat2(self):
        self.failUnless(self.card.fromstring("NAXIS99 = %20d" % 100 + 50*" "))

    def testMandatoryFormat3(self):
        self.failUnless(self.card.fromstring("XTENSION= %-70s"% "'IMAGE   '"))

    def testMandatoryFormat4(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "SIMPLE  = %-20s" % "T" + 50*" ")

    def testMandatoryFormat5(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "NAXIS99 = %-20d" % 100 + 50*" ")

    def testMandatoryFormat6(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                             "XTENSION=   %-20s"%"'IMAGE   '")

    #  Check for comment card
    def testCommentCard(self):
        self.failUnless(self.card.fromstring("COMMENT = "+70*"."))

    def testHistoryCard(self):
        self.failUnless(self.card.fromstring("HISTORY = "+70*"."))

    def testBlankCard(self):
        self.failUnless(self.card.fromstring("        = "+70*"."))

    def testValueCard(self):
        self.failUnless(self.card.fromstring("VALUE     "+70*"."))

    def testNonValueCard(self):
        self.failUnless(self.card.fromstring("VALUE   =="+70*"."))

    def testBadCommentCard(self):
        self.failUnlessRaises(fits.FITS_SevereError, self.card.fromstring,
                              "COMMENT =\t"+70*".")


class FormatterCase(unittest.TestCase):

    def setUp(self):
        self.card = fits.Card("")

    def testBooleanFormat(self):
        self.failUnless(self.card._Card__formatter(fits.FITS.TRUE) == "T")

    def testStringFormat(self):
        self.failUnless(self.card._Card__formatter("string") == "'string  '")

    def testIntegerFormat(self):
        self.failUnless(self.card._Card__formatter(-11111) == "-11111")

    def testLongIntFormat(self):
        self.failUnless(self.card._Card__formatter(-11111L) == "-11111")

    def testFloatFormat(self):
        self.failUnless(self.card._Card__formatter(1./6.) == \
                        "0.1666666666666667")

    def testComplexFormat(self):
        self.failUnless(self.card._Card__formatter(1./3.-1.j/6.) == \
                        "(0.3333333333333333, -0.1666666666666667)")

    def testNullFormat(self):
        self.failUnless(self.card._Card__formatter(None) == "")

    def testLongString(self):
        self.failUnlessRaises(fits.FITS_SevereError,
                              self.card._Card__formatter, 70*"-")

    def testInvalidType(self):
        self.failUnlessRaises(TypeError, self.card._Card__formatter, [])


if __name__ == "__main__":
    unittest.main()

