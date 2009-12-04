import pyfits
import sys

def test_with_statement():
    if sys.hexversion >= 0x02050000:
        exec("""from __future__ import with_statement
with pyfits.open("ascii.fits") as f: pass""")

def test_naxisj_check():
    hdulist = pyfits.open("o4sp040b0_raw.fits")

    hdulist[1].header.update("NAXIS3", 500)

    assert 'NAXIS3' in hdulist[1].header
    hdulist.verify('fix')
    assert 'NAXIS3' not in hdulist[1].header
