"""Fixer that changes bytes % whatever to a function that actually formats
it."""

from lib2to3 import fixer_base
from lib2to3.fixer_util import is_tuple, Call, Comma, Name, touch_import

def isnumberremainder(formatstr, data):
    try:
        if data.value.isdigit():
            return True
    except AttributeError:
        return False

class FixBytesmod(fixer_base.BaseFix):
    # XXX: There's one case (I suppose) I can't handle: when a remainder
    # operation like foo % bar is performed, I can't really know what the
    # contents of foo and bar are. I believe the best approach is to "correct"
    # the to-be-converted code and let bytesformatter handle that case in
    # runtime.
    PATTERN = '''
              term< formatstr=STRING '%' data=STRING > |
              term< formatstr=STRING '%' data=atom > |
              term< formatstr=NAME '%' data=any > |
              term< formatstr=any '%' data=any >
              '''

    imported_compat = False

    def transform(self, node, results):
        if not self.filename.endswith('pyfits/py3kcompat.py') and \
           not self.imported_compat:
            # This should only be done once, somewhere in the code
            touch_import('.', 'py3kcompat', node=node)
            self.imported_compat = True

        formatstr = results['formatstr'].clone()

        if not str(formatstr).strip()[0] == 'b':
            return

        data = results['data'].clone()
        formatstr.prefix = '' # remove spaces from start

        if isnumberremainder(formatstr, data):
            return

        # We have two possibilities:
        # 1- An identifier or name is passed, it is going to be a leaf, thus, we
        #    just need to copy its value as an argument to the formatter;
        # 2- A tuple is explicitly passed. In this case, we're gonna explode it
        # to pass to the formatter
        # TODO: Check for normal strings. They don't need to be translated

        if is_tuple(data):
            args = [formatstr, Comma().clone()] + \
                   [c.clone() for c in data.children[:]]
        else:
            args = [formatstr, Comma().clone(), data]

        call = Call(Name('bytesformatter', prefix = ' '), args)
        return call

