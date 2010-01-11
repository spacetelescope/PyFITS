import pyfits
import numpy as np
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

def test_byteswap():
    p = pyfits.PrimaryHDU()
    l = pyfits.HDUList()

    n = np.zeros(3, dtype='i2')
    n[0] = 1
    n[1] = 60000
    n[2] = 2

    c = pyfits.Column(name='foo', format='i2', bscale=1, bzero=32768, array=n)
    t = pyfits.new_table([c])

    l.append(p)
    l.append(t)

    l.writeto('test.fits', clobber=True)

    p = pyfits.open('test.fits')
    assert p[1].data[1]['foo'] == 60000.0
