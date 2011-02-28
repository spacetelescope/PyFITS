from __future__ import division # confidence high

import os
import sys

import numpy as np

import pyfits


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def test_with_statement():
    if sys.hexversion >= 0x02050000:
        exec("""from __future__ import with_statement
with pyfits.open(os.path.join(data_dir, 'ascii.fits')) as f: pass""")


def test_naxisj_check():
    hdulist = pyfits.open(os.path.join(data_dir, 'o4sp040b0_raw.fits'))

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
    os.remove('test.fits')


def test_add_del_columns():
    p = pyfits.ColDefs([])
    p.add_col(pyfits.Column(name='FOO', format='3J'))
    p.add_col(pyfits.Column(name='BAR', format='1I'))
    assert p.names == ['FOO', 'BAR']
    p.del_col('FOO')
    assert p.names == ['BAR']


def test_add_del_columns2():
    hdulist = pyfits.open(os.path.join(data_dir, 'tb.fits'))
    table = hdulist[1]
    assert table.data.dtype.names == ('c1', 'c2', 'c3', 'c4')
    assert table.columns.names == ['c1', 'c2', 'c3', 'c4']
    table.columns.del_col('c1')
    assert table.data.dtype.names == ('c2', 'c3', 'c4')
    assert table.columns.names == ['c2', 'c3', 'c4']
    table.columns.del_col('c3')
    assert table.data.dtype.names == ('c2', 'c4')
    assert table.columns.names == ['c2', 'c4']
    table.columns.add_col(pyfits.Column('foo', '3J'))
    assert table.data.dtype.names == ('c2', 'c4', 'foo')
    assert table.columns.names == ['c2', 'c4', 'foo']

    hdulist.writeto('test.fits', clobber=True)
    hdulist = pyfits.open('test.fits')
    table = hdulist[1]
    assert table.data.dtype.names == ('c1', 'c2', 'c3')
    assert table.columns.names == ['c1', 'c2', 'c3']
    os.remove('test.fits')


def test_uint():
    hdulist_f = pyfits.open(os.path.join(data_dir, 'o4sp040b0_raw.fits'))
    hdulist_i = pyfits.open(os.path.join(data_dir, 'o4sp040b0_raw.fits'),
                            uint=True)

    assert hdulist_f[1].data.dtype == np.float32
    assert hdulist_i[1].data.dtype == np.uint16
    assert np.all(hdulist_f[1].data == hdulist_i[1].data)
