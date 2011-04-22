"""This fixer wraps str() calls with the strtobytes() helper function, since in
most cases we're treating strings as bytes.
"""

from lib2to3 import fixer_base
from lib2to3.fixer_util import Call, Name, touch_import

class FixWrapstr(fixer_base.BaseFix):
    PATTERN = """power< name='str' trailer< '(' any ')' > >"""

    def transform(self, node, results):
        touch_import('.util', 'strtobytes', node)
        import pdb; pdb.set_trace()
        newnode = node.clone()
        return Call(Name('strtobytes'), newnode)
