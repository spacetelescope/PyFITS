import pyfits
import sys

def test_with_statement():
    if sys.hexversion >= 0x02050000:
        exec("""from __future__ import with_statement
with pyfits.open("ascii.fits") as f: pass""")


