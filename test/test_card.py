
from unittest import TestScenario, parse_args, run_scenarios

import fits

tested_modules = ['fits']

class CardTest(TestScenario):
    def setup(self):
        self.card = fits.Card('')
        self.keyre = fits.Card._Card__keywd_RE
        self.valre = fits.Card._Card__value_RE
        self.numre = fits.Card._Card__number_RE
        self.comre = fits.Card._Card__comment_RE
        self.fmtre = fits.Card._Card__format_RE
    
    def shutdown(self):
        pass

    def check___keyword_RE(self):
        "Testing attrib: 4"

        #  Check keyword regex
        excs = [
            ("if self.keyre.match('a-z     ') == None:" \
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.keyre.match('A-Z 0-9 ') == None:" \
             "  raise fits.FITS_SevereError", fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        stms = [
            "if self.keyre.match('A-Z0-9_-') == None: " \
            "  raise fits.FITS_SevereError",
            "if self.keyre.match('        ') == None: " \
            "  raise fits.FITS_SevereError"]
        for stm in stms: self.test_stmt(stm)

    def check___value_RE(self):
        "Testing attrib: 17"

        #  Check value regex
        excs = [
            ("if self.valre.match('\"bad string   \"') == None:"
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.valre.match('\\'a\\tstring \\'') == None:"
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.valre.match('                N') == None:"
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.valre.match('              1..') == None:"
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.valre.match('[      1,      1]') == None:"
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.valre.match('    / a\\tcomment') == None:"
             "  raise fits.FITS_SevereError", fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        stms = [
            "if self.valre.match('              ').group('valu_field') !=" \
            "  '              ': raise fits.FITS_SevereError",
            "if self.valre.match('\\'        \\'      ').group('valu') !=" \
            "  '\\'        \\'': raise fits.FITS_SevereError",
            "if self.valre.match('\\'a\\'\\'string\\' ').group('strg') !=" \
            "  'a\\'\\'string': raise fits.FITS_SevereError",
            "if self.valre.match('                   T').group('bool') !=" \
            "  'T': raise fits.FITS_SevereError",
            "if self.valre.match('              -00100').group('numr') !=" \
            "  '-00100': raise fits.FITS_SevereError",
            "if self.valre.match('       -00100.0E-001').group('numr') !=" \
            "  '-00100.0E-001': raise fits.FITS_SevereError",
            "if self.valre.match('(     -001,    -002)').group('cplx') !=" \
            "  '(     -001,    -002)': raise fits.FITS_SevereError",
            "if self.valre.match('(-0010.E-1,-0020.E-1)').group('cplx') !=" \
            "  '(-0010.E-1,-0020.E-1)': raise fits.FITS_SevereError",
            "if self.valre.match('       / comm ').group('comm_field') !=" \
            "  '/ comm ': raise fits.FITS_SevereError",
            "if self.valre.match('             / comm ').group('sepr') !=" \
            "  '/ ': raise fits.FITS_SevereError",
            "if self.valre.match('         / ---------').group('comm') !=" \
            "  '---------': raise fits.FITS_SevereError"]
        for stm in stms: self.test_stmt(stm)
    
    def check___number_RE(self):
        "Testing attrib: 2"
        stms = [
            "if self.numre.match('-00100').group('sign') != '-': " \
            "  raise fits.FITS_SevereError",
            "if self.numre.match('-00100').group('digt') != '100': " \
            "  raise fits.FITS_SevereError"]
        for stm in stms: self.test_stmt(stm)
    
    def check___comment_RE(self):
        "Testing attrib: 2"
        self.test_exc(
            "if self.comre.match('  a\\tstring   ') == None: " \
            "  raise fits.FITS_SevereError", fits.FITS_SevereError)
        self.test_stmt(
            "if self.comre.match('  a\\'string   ') == None: " \
            "  raise fits.FITS_SevereError")

    def check___format_RE(self):
        "Testing attrib: 7"
        excs = [
            ("if self.fmtre.match('    s  / %s ') == None:" \
             "  raise fits.FITS_SevereError", fits.FITS_SevereError),
            ("if self.fmtre.match('    %s   %s ') == None:" \
             "  raise fits.FITS_SevereError", fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        stms = [
            "if self.fmtre.match('    %s      ') == None:" \
            "  raise fits.FITS_SevereError",
            "if self.fmtre.match(' %5.3f  /   ') == None:" \
            "  raise fits.FITS_SevereError",
            "if self.fmtre.match('(%6.4f, %6.4f)') == None:" \
            "  raise fits.FITS_SevereError",
            "if self.fmtre.match('    %s  / s ') == None:" \
            "  raise fits.FITS_SevereError",
            "if self.fmtre.match('    %s  / %s ') == None:" \
            "  raise fits.FITS_SevereError"]
        for stm in stms: self.test_stmt(stm)
    
    def check___init__(self):
        "Testing method: 23"
        
        #  Check keyword for type, length, and invalid characters
        excs = [
            ("fits.Card(1)", fits.FITS_SevereError),
            ("fits.Card('keyword__')", fits.FITS_SevereError),
            ("fits.Card('keyword!')", fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        self.test_stmt("fits.Card('keyword   ')")
        
        #  Check for bad value and comment strings
        excs = [
            ("fits.Card('VALUE  ', 'bad\\tstring')", fits.FITS_SevereError),
            ("fits.Card('VALUE  ', 1, 2)", fits.FITS_SevereError),
            ("fits.Card('VALUE  ', 1, 'bad\\tstring')", fits.FITS_SevereError),
        
        #  Check for comment cards
            ("fits.Card('COMMENT', comment='a comment')",
             fits.FITS_SevereError),
            ("fits.Card('END    ', 'an END card')", fits.FITS_SevereError),
            ("fits.Card('COMMENT', 1)", fits.FITS_SevereError),
            ("fits.Card('COMMENT', 73*'-')", fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        stms = [
            "fits.Card('end')",
            "fits.Card('comment', 72*'-')",
            "fits.Card('history', 72*'-')",
            "fits.Card('       ', 72*'-')"]
        for stm in stms: self.test_stmt(stm)
        
        #  Check for format option
        excs = [
            ( "fits.Card('VALUE  ', 1, format='d')", fits.FITS_SevereError),
            ( "fits.Card('VALUE  ', 1, format=' / %s')",
              fits.FITS_SevereError)]
        #self.test_exc( "fits.Card('VALUE  ', 1, format='%s')", fits.FITS_SevereError)
        for exc in excs: self.test_exc(exc[0], exc[1])
        stms = [
            "fits.Card('VALUE  ', 1, format='%d')",
            "fits.Card('VALUE  ', 1.-2.j, format='(%f, %f)')",
            "fits.Card('VALUE  ', 1, format='%d /')",
            "fits.Card('VALUE  ', 1, format='%d / %s')",
            "fits.Card('VALUE  ', 1, 'a comment', '%d / %s')",
        
        #  Check fixed format
            "fits.Card('VALUE  ', 'a\\'string', 70*'-')"]
        for stm in stms: self.test_stmt(stm)
    
    def check___getattr__(self):
        "Testing method: 12"

        #  Check key attribute
        stms = [
            "if fits.Card('VALUE  ', 1).key != 'VALUE':"
                       " raise fits.FITS_SevereError",

        #  Check value attribute
            "if fits.Card('COMMENT', 72*'-').value != 72*'-':"
            "  raise fits.FITS_SevereError",
            "if fits.Card('BOOLEAN', fits.FITS.TRUE).value != "
            "fits.FITS.TRUE:  raise fits.FITS_SevereError",
            "if fits.Card('STRING ', \"O'Hara\").value != \"O'Hara\": "
            "  raise fits.FITS_SevereError",
            "if fits.Card('v').fromstring('INTEGER = %-70s' % '-00100')"
            ".value != -100:  raise fits.FITS_SevereError",
            "if fits.Card('v').fromstring('REAL    = %-70s' % '-001.0E2')"
            ".value != -100.0:  raise fits.FITS_SevereError",
            "if fits.Card('v').fromstring('COMPLEX = (%8s, %8s)%-50s' % "
            "('-001.0E2', '-002.0E2', ' ')).value != -100.0-200.0j:"
            "  raise fits.FITS_SevereError",
            "if fits.Card('NONE   ').value != None:"
            "  raise fits.FITS_SevereError"]
        for stm in stms: self.test_stmt(stm)
        self.test_exc(
            "fits.Card('NONBOOL', fits.Boolean('N')).value",
            fits.FITS_SevereError)

        #  Check comment attribute
        stms = [
            "if fits.Card('NO_COMM', 1, 60*'-').comment != 47*'-':"
            "  raise fits.FITS_SevereError",
            "if fits.Card('NO_COMM').comment != None:"
            "  raise fits.FITS_SevereError"]
        for stm in stms: self.test_stmt(stm)

        #  Check for attribute error
        self.test_exc("fits.Card('VALUE').attrib", AttributeError)
    
    def check___setattr__(self):
        "Testing method: 23"

        #  Check END card
        excs = [
            ("fits.Card('END').key = 'END'", fits.FITS_SevereError),
            ("fits.Card('END').value = 1", fits.FITS_SevereError),
            ("fits.Card('END').comment = 'a comment'", fits.FITS_SevereError),

        #  Check key attribute
            ("fits.Card('VALUE  ', 1, 'a comment').key = 1",
             fits.FITS_SevereError),
            ("fits.Card('VALUE  ', 1, 'a comment').key = 'LONGKEYWORD'",
             fits.FITS_SevereError),
            ("fits.Card('VALUE  ', 1, 'a comment').key = 'BAD KEYWD'",
             fits.FITS_SevereError),
            ("fits.Card('VALUE  ', 1, 'a comment').key = 'COMMENT'",
             fits.FITS_SevereError),
            ("fits.Card('VALUE  ', 1, 'a comment').key = 'END'",
             fits.FITS_SevereError),
            ("fits.Card('COMMENT', 'a comment').key = 'VALUE  '",
             fits.FITS_SevereError),
            ("fits.Card('COMMENT', 'a comment').key = 'END'",
             fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        self.test_stmt("fits.Card('VALUE  ', 1, 'a comment').key = "
                       "'NEWVALUE'")
        self.test_stmt("fits.Card('COMMENT', 'a comment').key = 'HISTORY'")

        #  Check value attribute
        excs = [
            ("fits.Card('VALUE  ', 'a string').value = 'bad\tstring'",
             fits.FITS_SevereError),
            ("fits.Card('COMMENT', 'a string').value = 'bad\tstring'",
             fits.FITS_SevereError),
            ("fits.Card('COMMENT', 'a comment').value = 1",
             fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        stms = [
            "fits.Card('COMMENT', 'a comment').value = 'a new comment'",
            "fits.Card('VALUE  ', 1, 'a comment').value = 2",
            "fits.Card('VALUE  ', 1, 'a comment').value = 'a string'",
            "fits.Card('VALUE  ', 1-2j, 'a comment').value = 2-3j",
            "fits.Card('VALUE  ', 1, 'a comment', format='%d / %s').value = 2",

        #  Check comment attribute
            "fits.Card('VALUE  ', 1, 'a comment').comment = 'a new comment'"]
        for stm in stms: self.test_stmt(stm)
        self.test_exc(
            "fits.Card('COMMENT', 'a comment').comment = 'a comment'",
            AttributeError)

        #  Check bad attribute
        self.test_exc(
            "fits.Card('COMMENT', 'a comment').bad = 1", AttributeError)

    def check_fromstring(self):
        "Testing method: 27"
        
        #  Check card length
        self.test_stmt(
            "self.card.fromstring(80*' ')")
        self.test_exc(
            "self.card.fromstring(81*' ')", fits.FITS_SevereError)
        self.test_exc(
            "self.card.fromstring(79*' ')", fits.FITS_SevereError)

        #  Check keyword
        self.test_exc(
            "self.card.fromstring('COM MENT'+72*'.')", fits.FITS_SevereError)
        self.test_exc(
            "self.card.fromstring('a-z0-9_-'+72*'.')", fits.FITS_SevereError)
        self.test_stmt(
            "self.card.fromstring('A-Z0-9_-'+72*'.')")

        #  Check for END card
        self.test_exc(
            "self.card.fromstring('END     '+72*'.')", fits.FITS_SevereError)
        self.test_stmt(
            "self.card.fromstring('END     '+72*' ')")

        #  Check for value card
        stms = [
            "self.card.fromstring('STRING  = %30s' % '\\'a\\\'\\\'string\\''"
            "+40*' ')",
            "self.card.fromstring('BOOLEAN = %30s'%'T'+40*' ')",
            "self.card.fromstring('INTEGER = %30d'%1  +40*' ')",
            "self.card.fromstring('REAL    = %30f'%1.1+40*' ')",
            "self.card.fromstring('REAL    = %30f'% .1+40*' ')",
            "self.card.fromstring('REAL    = %30g'%-1.1e-9+40*' ')",
            "self.card.fromstring('REAL    = %-30s'%'-01e-9' + 40*' ')",
            "self.card.fromstring('COMPLEX = (%13f, %13f)'%(1.1,1.1)+40*' ')",
            "self.card.fromstring('NONE    = '+70*' ')",
            "self.card.fromstring('COMFIELD= %30d / %-37s'%(1, 'a comment'))"]
        for stm in stms: self.test_stmt(stm)
        excs = [
            ("self.card.fromstring('BOOLEAN = %30s' % 'N'+40*' ')",
             fits.FITS_SevereError),
            ("self.card.fromstring('STRING  = %30s' % '\\\"a\\'string\\\"'"
             "+40*' ')", fits.FITS_SevereError),
            ("self.card.fromstring('STRING  = %30s' % '\\\"a\\tstring\\\"'"
             "+40*' ')", fits.FITS_SevereError)]
        for exc in excs: self.test_exc(exc[0], exc[1])
        
        #  Check for comment card
        stms = [
            "self.card.fromstring('COMMENT = '+70*'.')",
            "self.card.fromstring('HISTORY = '+70*'.')",
            "self.card.fromstring('        = '+70*'.')",
            "self.card.fromstring('VALUE     '+70*'.')",
            "self.card.fromstring('VALUE   =='+70*'.')"]
        for stm in stms: self.test_stmt(stm)
        self.test_exc(
            "self.card.fromstring('COMMENT =\t'+70*'.')",
            fits.FITS_SevereError)
    
    def check___asString(self):
        "Testing method: 9"

        stms = [
            "if self.card._Card__asString(fits.FITS.TRUE) != 'T':"
            "  raise fits.FITS_SevereError",
            "if self.card._Card__asString('string') != '\\'string  \\'':"
            "  raise fits.FITS_SevereError",
            "if self.card._Card__asString(-11111) != '-11111':"
            "  raise fits.FITS_SevereError",
            "if self.card._Card__asString(-11111L) != '-11111':"
            "  raise fits.FITS_SevereError",
            "if self.card._Card__asString(1./6.) != '0.1666666666666667':"
            "  raise fits.FITS_SevereError",
            "if self.card._Card__asString(1./3.-1.j/6.) != "
            "'(0.3333333333333333, -0.1666666666666667)':"
            "  raise fits.FITS_SevereError",
            "if self.card._Card__asString(None) != '':"
            "  raise fits.FITS_SevereError",
            ]
        for stm in stms: self.test_stmt(stm)
        excs = [
            ("self.card._Card__asString(70*'-')", fits.FITS_SevereError),
            ("self.card._Card__asString([])", TypeError)]
        for exc in excs: self.test_exc(exc[0], exc[1])

if __name__ == "__main__":
    (scenarios, options) = parse_args()
    run_scenarios(scenarios, options)
