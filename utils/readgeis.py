#!/usr/bin/env python2.2

"""
        readgeis: Read GEIS file and convert it to a FITS extension file.

        Usage:

                readgeis.py [options] GEISname FITSname

                GEISname is the input GEIS file in GEIS format, and FITSname
                is the output file in FITS format.

                Option:

                -h
                        print the help (this text)

        Example:

                readgeis.py test1.hhh test1.fits

                this command will convert the input GEIS file test1.hhh to
                a FITS file test1.fits.

        If used in Pythons script, a user can, e. g.:

                import readgeis
                hdulist = readgeis.readgeis(GEISFileName)
                (do whatever with hdulist)
                hdulist.writeto(FITSFileName)

"""

# Developed by Science Software Branch, STScI, USA.
__version__ = "Version 1.1 (04 March, 2003), \xa9 AURA"

import sys, string
import pyfits
import numarray
import recarray
import memmap

def stsci(hdulist):
    """For STScI GEIS files, need to do extra steps."""

    instrument = hdulist[0].header.get('INSTRUME', '')

    # Update extension header keywords
    if instrument in ("WFPC2", "FOC"):
        rootname = hdulist[0].header.get('ROOTNAME', '')
        filetype = hdulist[0].header.get('FILETYPE', '')
        for i in range(1, len(hdulist)):
            hdulist[i].header.update(key='EXPNAME', value=rootname, comment="9 character exposure identifier")
            hdulist[i].header.update(key='EXTVER', value=i, comment="extension version number")
            hdulist[i].header.update(key='EXTNAME', value=filetype, comment="extension name")
            hdulist[i].header.update(key='INHERIT', value=pyfits.TRUE, comment="inherit the primary header")
            hdulist[i].header.update(key='ROOTNAME', value=rootname, comment="rootname of the observation set")


def stsci2(hdulist, filename):
    """For STScI GEIS files, need to do extra steps."""

    # Write output file name to the primary header
    instrument = hdulist[0].header.get('INSTRUME', '')
    if instrument in ("WFPC2", "FOC"):
        hdulist[0].header.update('FILENAME', filename)


def readgeis(input):

    """Input GEIS files "input" will be read and a HDUList object will
       be returned.

       The user can use the writeto method to write the HDUList object to
       a FITS file.
    """

    global dat
    cardLen = pyfits.Card.length

    # print out heading and parameter values
    print "\n readgeis: ", __version__

    # input file(s) must be of the form *.??h and *.??d
    if input[-1] != 'h' or input[-4] != '.':
        raise "Illegal input GEIS file name %s" % input

    data_file = input[:-1]+'d'

    _os = sys.platform
    if _os[:5] == 'linux' or _os[:5] == 'sunos':
        bytes_per_line = cardLen+1
    else:
        raise "Platform %s is supported (yet)." % _os

    geis_fmt = {'REAL':'f', 'INTEGER':'i', 'LOGICAL':'i'}
    end_card = 'END'+' '* (cardLen-3)

    # open input file
    im = open(input)

    # Use copy on write since in UInt16 case the data will be scaled.
    dat = memmap.open(data_file, mode='c')

    # Generate the primary HDU
    cards = []
    while 1:
        line = im.read(bytes_per_line)[:cardLen]
        line = line[:8].upper() + line[8:]
        if line == end_card:
            break
        cards.append(pyfits.Card('').fromstring(line))

    phdr = pyfits.Header(pyfits.CardList(cards))

    _naxis0 = phdr.get('NAXIS', 0)
    _naxis = [phdr['NAXIS'+`j`] for j in range(1, _naxis0+1)]
    _naxis.insert(0, _naxis0)
    _bitpix = phdr['BITPIX']
    _psize = phdr['PSIZE']
    if phdr['DATATYPE'][:4] == 'REAL':
        _bitpix = -_bitpix
    if _naxis0 > 0:
        size = reduce(lambda x,y:x*y, _naxis[1:])
        data_size = abs(_bitpix) * size / 8
    else:
        data_size = 0
    group_size = data_size + _psize / 8

    # decode the group parameter definitions,
    # group parameters will become extension header
    groups = phdr['GROUPS']
    gcount = phdr['GCOUNT']
    pcount = phdr['PCOUNT']

    formats = ''
    bools = []
    floats = []

    # Construct record array formats for the group parameters
    for i in range(1, pcount+1):
        dtype = phdr['PDTYPE'+`i`]
        star = dtype.find('*')
        _type = dtype[:star]
        _bytes = dtype[star+1:]

        # collect boolean keywords since they need special attention later
        if _type == 'LOGICAL':
            bools.append(i)
        if dtype == 'REAL*4':
            floats.append(i)
        if _type[:2] == 'CH':
            fmt = _bytes + 'a'
        else:
            fmt = geis_fmt[_type] + _bytes
        formats += fmt + ','

    _shape = _naxis[1:]
    _shape.reverse()
    _code = pyfits.ImageBaseHDU.NumCode[_bitpix]
    _bscale = phdr.get('BSCALE', 1)
    _bzero = phdr.get('BZERO', 0)
    if phdr['DATATYPE'][:10] == 'UNSIGNED*2':
        _uint16 = 1
        _bzero = 32768
    else:
        _uint16 = 0

    _range = range(1, pcount+1)
    key = [phdr['PTYPE'+`j`] for j in _range]
    comm = [phdr.ascard['PTYPE'+`j`].comment for j in _range]

    # delete group parameter definition header keywords
    _list = ['PTYPE'+`j` for j in _range] + \
            ['PDTYPE'+`j` for j in _range] + \
            ['PSIZE'+`j` for j in _range] + \
            ['DATATYPE', 'PSIZE', 'GCOUNT', 'PCOUNT', 'BSCALE', 'BZERO']

    # delete from the end, so it will not conflict with previous delete
    for i in range(len(phdr.ascard)-1, -1, -1):
        if phdr.ascard[i].key in _list:
            del phdr[i]

    # clean up other primary header keywords
    phdr['SIMPLE']=pyfits.TRUE
    phdr['BITPIX']=16
    phdr['GROUPS']=pyfits.FALSE
    _after = 'NAXIS'
    if _naxis0 > 0:
        _after += `_naxis0`
    phdr.update(key='EXTEND', value=pyfits.TRUE, comment="FITS dataset may contain extensions", after=_after)
    phdr.update(key='NEXTEND', value=gcount, comment="Number of standard extensions")

    hdulist = pyfits.HDUList([pyfits.PrimaryHDU(header=phdr, data=None)])
    loc = 0
    for k in range(gcount):
        ext_dat = numarray.array(dat[loc:loc+data_size], type=_code, shape=_shape)
        if (_uint16):
            ext_dat += _bzero
        ext_hdu = pyfits.ImageHDU(data=ext_dat)

        rec = recarray.RecArray(dat[loc+data_size:loc+group_size], formats=formats[:-1], shape=1)
        loc += group_size

        for i in range(1, pcount+1):
            val = rec.field(i-1)[0]
            if i in bools:
                if val:
                    val = pyfits.TRUE
                else:
                    val = pyfits.FALSE
            _format = None
            if i in floats:
                _format = '%20.7G / %s'
            _card = pyfits.Card(key=key[i-1], value=val, comment=comm[i-1], format = _format)
            ext_hdu.header.ascard.append(_card)

        # deal with bscale/bzero
        if (_bscale != 1 or _bzero != 0):
            ext_hdu.header.update('BSCALE', _bscale)
            ext_hdu.header.update('BZERO', _bzero)

        hdulist.append(ext_hdu)

    stsci(hdulist)
    return hdulist

#-------------------------------------------------------------------------------
# special initialization when this is the main program

if __name__ == "__main__":

    import getopt

    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'o:bh')
    except getopt.error, e:
        print str(e)
        print __doc__
        print "\t", __version__

    # initialize default values
    help = 0

    # read options
    for opt, value in optlist:
        if opt == "-h":
            help = 1

    if (help):
        print __doc__
        print "\t", __version__
    else:
        if len(args) == 2:
            hdulist = readgeis(args[0])
            stsci2(hdulist, args[1])
            hdulist.writeto(args[1])
        else:
            print "Needs pair(s) of input files.  Use -h for help"
