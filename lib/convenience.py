# For now any imports from pyfits.core will have to be inline to prevent
# an import cycle; eventually this will mostly go away as we move more
# objects out of pyfits.core

import gzip
import os
import types

import numpy as np

from pyfits import rec
from pyfits.file import PYTHON_MODES, _File
from pyfits.hdu.hdulist import fitsopen

__all__ = ['getheader', 'getdata', 'getval', 'setval', 'delval', 'writeto',
           'append', 'update', 'info', 'tdump', 'tcreate']

# Convenience functions

class _Zero(int):
    def __init__(self):
        self = 0

def _getext(filename, mode, *ext1, **ext2):
    """
    Open the input file, return the `HDUList` and the extension.
    """
    hdulist = fitsopen(filename, mode=mode, **ext2)

    # delete these from the variable keyword argument list so the extension
    # will properly validate
    if ext2.has_key('classExtensions'):
        del ext2['classExtensions']

    if ext2.has_key('ignore_missing_end'):
        del ext2['ignore_missing_end']

    if ext2.has_key('uint16'):
        del ext2['uint16']

    if ext2.has_key('uint'):
        del ext2['uint']

    n_ext1 = len(ext1)
    n_ext2 = len(ext2)
    keys = ext2.keys()

    # parse the extension spec
    if n_ext1 > 2:
        raise ValueError, "too many positional arguments"
    elif n_ext1 == 1:
        if n_ext2 == 0:
            ext = ext1[0]
        else:
            if isinstance(ext1[0], (int, np.integer, tuple)):
                raise KeyError, 'Redundant/conflicting keyword argument(s): %s' % ext2
            if isinstance(ext1[0], str):
                if n_ext2 == 1 and 'extver' in keys:
                    ext = ext1[0], ext2['extver']
                raise KeyError, 'Redundant/conflicting keyword argument(s): %s' % ext2
    elif n_ext1 == 2:
        if n_ext2 == 0:
            ext = ext1
        else:
            raise KeyError, 'Redundant/conflicting keyword argument(s): %s' % ext2
    elif n_ext1 == 0:
        if n_ext2 == 0:
            ext = _Zero()
        elif 'ext' in keys:
            if n_ext2 == 1:
                ext = ext2['ext']
            elif n_ext2 == 2 and 'extver' in keys:
                ext = ext2['ext'], ext2['extver']
            else:
                raise KeyError, 'Redundant/conflicting keyword argument(s): %s' % ext2
        else:
            if 'extname' in keys:
                if 'extver' in keys:
                    ext = ext2['extname'], ext2['extver']
                else:
                    ext = ext2['extname']
            else:
                raise KeyError, 'Insufficient keyword argument: %s' % ext2

    return hdulist, ext

def getheader(filename, *ext, **extkeys):
    """
    Get the header from an extension of a FITS file.

    Parameters
    ----------
    filename : file path, file object, or file like object
        File to get header from.  If an opened file object, its mode
        must be one of the following rb, rb+, or ab+).

    classExtensions : optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    ext
        The rest of the arguments are for extension specification.
        `getdata` for explanations/examples.

    Returns
    -------
    header : `Header` object
    """

    # allow file object to already be opened in any of the valid modes
    # and leave the file in the same state (opened or closed) as when
    # the function was called

    mode = 'readonly'
    closed = True

    if (isinstance(filename, file) and not filename.closed) or \
       (isinstance(filename, gzip.GzipFile) and filename.fileobj != None and
                                            not filename.fileobj.closed):

        if isinstance(filename, gzip.GzipFile):
            fileMode = filename.fileobj.mode
        else:
            fileMode = filename.mode

        for key in PYTHON_MODES.keys():
            if PYTHON_MODES[key] == fileMode:
                mode = key
                break

    if hasattr(filename, 'closed'):
        closed = filename.closed
    elif hasattr(filename, 'fileobj'):
        if filename.fileobj != None:
           closed = filename.fileobj.closed

    hdulist, _ext = _getext(filename, mode, *ext, **extkeys)
    hdu = hdulist[_ext]
    hdr = hdu.header

    hdulist.close(closed=closed)
    return hdr


def _fnames_changecase(data, func):
    """
    Convert case of field names.
    """
    if data.dtype.names is None:
        # this data does not have fields
        return

    if data.dtype.descr[0][0] == '':
        # this data does not have fields
        return

    data.dtype.names = [func(n) for n in data.dtype.names]


def getdata(filename, *ext, **extkeys):
    """
    Get the data from an extension of a FITS file (and optionally the
    header).

    Parameters
    ----------
    filename : file path, file object, or file like object
        File to get data from.  If opened, mode must be one of the
        following rb, rb+, or ab+.

    classExtensions : dict, optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    ext
        The rest of the arguments are for extension specification.
        They are flexible and are best illustrated by examples.

        No extra arguments implies the primary header::

            >>> getdata('in.fits')

        By extension number::

            >>> getdata('in.fits', 0)    # the primary header
            >>> getdata('in.fits', 2)    # the second extension
            >>> getdata('in.fits', ext=2) # the second extension

        By name, i.e., ``EXTNAME`` value (if unique)::

            >>> getdata('in.fits', 'sci')
            >>> getdata('in.fits', extname='sci') # equivalent

        Note ``EXTNAME`` values are not case sensitive

        By combination of ``EXTNAME`` and EXTVER`` as separate
        arguments or as a tuple::

            >>> getdata('in.fits', 'sci', 2) # EXTNAME='SCI' & EXTVER=2
            >>> getdata('in.fits', extname='sci', extver=2) # equivalent
            >>> getdata('in.fits', ('sci', 2)) # equivalent

        Ambiguous or conflicting specifications will raise an exception::

            >>> getdata('in.fits', ext=('sci',1), extname='err', extver=2)

    lower, upper : bool, optional
        If `lower` or `upper` are `True`, the field names in the
        returned data object will be converted to lower or upper case,
        respectively.

    view : ndarray view class, optional
        When given, the data will be turned wrapped in the given view
        class, by calling::

           data.view(view)

    Returns
    -------
    array : array, record array or groups data object
        Type depends on the type of the extension being referenced.

        If the optional keyword `header` is set to `True`, this
        function will return a (`data`, `header`) tuple.
    """

    if 'header' in extkeys:
        _gethdr = extkeys['header']
        del extkeys['header']
    else:
        _gethdr = False

    # Code further down rejects unkown keys
    lower=False
    if 'lower' in extkeys:
        lower=extkeys['lower']
        del extkeys['lower']
    upper=False
    if 'upper' in extkeys:
        upper=extkeys['upper']
        del extkeys['upper']
    view=None
    if 'view' in extkeys:
        view=extkeys['view']
        del extkeys['view']

    # allow file object to already be opened in any of the valid modes
    # and leave the file in the same state (opened or closed) as when
    # the function was called

    mode = 'readonly'
    closed = True

    if (isinstance(filename, file) and not filename.closed) or \
       (isinstance(filename, gzip.GzipFile) and filename.fileobj != None and
                                            not filename.fileobj.closed):

        if isinstance(filename, gzip.GzipFile):
            fileMode = filename.fileobj.mode
        else:
            fileMode = filename.mode

        for key in PYTHON_MODES.keys():
            if PYTHON_MODES[key] == fileMode:
                mode = key
                break

    if hasattr(filename, 'closed'):
        closed = filename.closed
    elif hasattr(filename, 'fileobj'):
        if filename.fileobj != None:
           closed = filename.fileobj.closed

    hdulist, _ext = _getext(filename, mode, *ext, **extkeys)
    hdu = hdulist[_ext]
    _data = hdu.data
    if _data is None and isinstance(_ext, _Zero):
        try:
            hdu = hdulist[1]
            _data = hdu.data
        except IndexError:
            raise IndexError, 'No data in this HDU.'
    if _data is None:
        raise IndexError, 'No data in this HDU.'
    if _gethdr:
        _hdr = hdu.header
    hdulist.close(closed=closed)

    # Change case of names if requested
    if lower:
        _fnames_changecase(_data, str.lower)
    elif upper:
        _fnames_changecase(_data, str.upper)

    # allow different views into the underlying ndarray.  Keep the original
    # view just in case there is a problem
    if view is not None:
        _data = _data.view(view)

    if _gethdr:
        return _data, _hdr
    else:
        return _data

def getval(filename, key, *ext, **extkeys):
    """
    Get a keyword's value from a header in a FITS file.

    Parameters
    ----------
    filename : file path, file object, or file like object
        Name of the FITS file, or file object (if opened, mode must be
        one of the following rb, rb+, or ab+).

    key : str
        keyword name

    classExtensions : (optional)
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    ext
        The rest of the arguments are for extension specification.
        See `getdata` for explanations/examples.

    Returns
    -------
    keyword value : string, integer, or float
    """

    _hdr = getheader(filename, *ext, **extkeys)
    return _hdr[key]

def setval(filename, key, value="", comment=None, before=None, after=None,
           savecomment=False, *ext, **extkeys):
    """
    Set a keyword's value from a header in a FITS file.

    If the keyword already exists, it's value/comment will be updated.
    If it does not exist, a new card will be created and it will be
    placed before or after the specified location.  If no `before` or
    `after` is specified, it will be appended at the end.

    When updating more than one keyword in a file, this convenience
    function is a much less efficient approach compared with opening
    the file for update, modifying the header, and closing the file.

    Parameters
    ----------
    filename : file path, file object, or file like object
        Name of the FITS file, or file object If opened, mode must be
        update (rb+).  An opened file object or `GzipFile` object will
        be closed upon return.

    key : str
        keyword name

    value : str, int, float
        Keyword value, default = ""

    comment : str
        Keyword comment, default = None

    before : str, int
        name of the keyword, or index of the `Card` before which
        the new card will be placed.  The argument `before` takes
        precedence over `after` if both specified. default=`None`.

    after : str, int
        name of the keyword, or index of the `Card` after which the
        new card will be placed. default=`None`.

    savecomment : bool
        when `True`, preserve the current comment for an existing
        keyword.  The argument `savecomment` takes precedence over
        `comment` if both specified.  If `comment` is not specified
        then the current comment will automatically be preserved.
        default=`False`

    classExtensions : dict, optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    ext
        The rest of the arguments are for extension specification.
        See `getdata` for explanations/examples.
    """

    hdulist, ext = _getext(filename, mode='update', *ext, **extkeys)
    hdulist[ext].header.update(key, value, comment, before, after, savecomment)

    # Ensure that data will not be scaled when the file is closed

    for hdu in hdulist:
       hdu._bscale = 1
       hdu._bzero = 0

    hdulist.close()

def delval(filename, key, *ext, **extkeys):
    """
    Delete all instances of keyword from a header in a FITS file.

    Parameters
    ----------

    filename : file path, file object, or file like object
        Name of the FITS file, or file object If opened, mode must be
        update (rb+).  An opened file object or `GzipFile` object will
        be closed upon return.

    key : str, int
        Keyword name or index

    classExtensions : optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    ext
        The rest of the arguments are for extension specification.
        See `getdata` for explanations/examples.
    """

    hdulist, ext = _getext(filename, mode='update', *ext, **extkeys)
    del hdulist[ext].header[key]

    # Ensure that data will not be scaled when the file is closed

    for hdu in hdulist:
       hdu._bscale = 1
       hdu._bzero = 0

    hdulist.close()


def _makehdu(data, header, classExtensions={}):
    from pyfits.core import BinTableHDU, ImageHDU
    if header is None:
        if ((isinstance(data, np.ndarray) and data.dtype.fields is not None)
            or isinstance(data, np.recarray)
            or isinstance(data, rec.recarray)):
            if classExtensions.has_key(BinTableHDU):
                hdu = classExtensions[BinTableHDU](data)
            else:
                hdu = BinTableHDU(data)
        elif isinstance(data, np.ndarray):
            if classExtensions.has_key(ImageHDU):
                hdu = classExtensions[ImageHDU](data)
            else:
                hdu = ImageHDU(data)
        else:
            raise KeyError, 'data must be numarray or table data.'
    else:
        if classExtensions.has_key(header._hdutype):
            header._hdutype = classExtensions[header._hdutype]

        hdu=header._hdutype(data=data, header=header)
    return hdu

def _stat_filename_or_fileobj(filename):
    closed = True
    name = ''

    if isinstance(filename, file):
        closed = filename.closed
        name = filename.name
    elif isinstance(filename, gzip.GzipFile):
        if filename.fileobj != None:
            closed = filename.fileobj.closed
        name = filename.filename
    elif isinstance(filename, types.StringType):
        name = filename
    else:
        if hasattr(filename, 'closed'):
            closed = filename.closed

        if hasattr(filename, 'name'):
            name = filename.name
        elif hasattr(filename, 'filename'):
            name = filename.filename

    try:
        loc = filename.tell()
    except AttributeError:
        loc = 0

    noexist_or_empty = \
        (name and ((not os.path.exists(name)) or (os.path.getsize(name)==0))) \
         or (not name and loc==0)

    return name, closed, noexist_or_empty

def writeto(filename, data, header=None, **keys):
    """
    Create a new FITS file using the supplied data/header.

    Parameters
    ----------
    filename : file path, file object, or file like object
        File to write to.  If opened, must be opened for append (ab+).

    data : array, record array, or groups data object
        data to write to the new file

    header : Header object, optional
        the header associated with `data`. If `None`, a header
        of the appropriate type is created for the supplied data. This
        argument is optional.

    classExtensions : dict, optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    clobber : bool, optional
        If `True`, and if filename already exists, it will overwrite
        the file.  Default is `False`.

    checksum : bool, optional
        If `True`, adds both ``DATASUM`` and ``CHECKSUM`` cards to the
        headers of all HDU's written to the file.
    """

    from pyfits.core import PrimaryHDU, _TableBaseHDU

    if header is None:
        if 'header' in keys:
            header = keys['header']

    clobber = keys.get('clobber', False)
    output_verify = keys.get('output_verify', 'exception')

    classExtensions = keys.get('classExtensions', {})
    hdu = _makehdu(data, header, classExtensions)
    if not isinstance(hdu, PrimaryHDU) and not isinstance(hdu, _TableBaseHDU):
        if classExtensions.has_key(PrimaryHDU):
            hdu = classExtensions[PrimaryHDU](data, header=header)
        else:
            hdu = PrimaryHDU(data, header=header)
    checksum = keys.get('checksum', False)
    hdu.writeto(filename, clobber=clobber, output_verify=output_verify,
                checksum=checksum, classExtensions=classExtensions)

def append(filename, data, header=None, classExtensions={}, checksum=False,
           verify=True, **keys):
    """
    Append the header/data to FITS file if filename exists, create if not.

    If only `data` is supplied, a minimal header is created.

    Parameters
    ----------
    filename : file path, file object, or file like object
        File to write to.  If opened, must be opened for update (rb+)
        unless it is a new file, then it must be opened for append
        (ab+).  A file or `GzipFile` object opened for update will be
        closed after return.

    data : array, table, or group data object
        the new data used for appending

    header : Header object, optional
        The header associated with `data`.  If `None`, an appropriate
        header will be created for the data object supplied.

    classExtensions : dictionary, optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    checksum : bool, optional
        When `True` adds both ``DATASUM`` and ``CHECKSUM`` cards to
        the header of the HDU when written to the file.

    verify: bool, optional (True)
        When `True`, the existing FITS file will be read in to verify
        it for correctness before appending.  When `False`, content is
        simply appended to the end of the file.  Setting *verify* to
        `False` can be much faster.
    """

    from pyfits.core import PrimaryHDU, ImageHDU

    name, closed, noexist_or_empty = _stat_filename_or_fileobj(filename)

    if noexist_or_empty:
        #
        # The input file or file like object either doesn't exits or is
        # empty.  Use the writeto convenience function to write the
        # output to the empty object.
        #
        writeto(filename, data, header, classExtensions=classExtensions,
                checksum=checksum, **keys)
    else:
        hdu=_makehdu(data, header, classExtensions)

        if isinstance(hdu, PrimaryHDU):
            if classExtensions.has_key(ImageHDU):
                hdu = classExtensions[ImageHDU](data, header)
            else:
                hdu = ImageHDU(data, header)

        if verify or not closed:
            f = fitsopen(filename, mode='append', classExtensions=classExtensions)
            f.append(hdu, classExtensions=classExtensions)

            # Set a flag in the HDU so that only this HDU gets a checksum
            # when writing the file.
            hdu._output_checksum = checksum
            f.close(closed=closed)
        else:
            f = _File(filename, mode='append')
            hdu._output_checksum = checksum
            f.writeHDU(hdu)
            f.close()

def update(filename, data, *ext, **extkeys):
    """
    Update the specified extension with the input data/header.

    Parameters
    ----------
    filename : file path, file object, or file like object
        File to update.  If opened, mode must be update (rb+).  An
        opened file object or `GzipFile` object will be closed upon
        return.

    data : array, table, or group data object
        the new data used for updating

    classExtensions : dict, optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    ext
        The rest of the arguments are flexible: the 3rd argument can
        be the header associated with the data.  If the 3rd argument
        is not a `Header`, it (and other positional arguments) are
        assumed to be the extension specification(s).  Header and
        extension specs can also be keyword arguments.  For example::

            >>> update(file, dat, hdr, 'sci')  # update the 'sci' extension
            >>> update(file, dat, 3)  # update the 3rd extension
            >>> update(file, dat, hdr, 3)  # update the 3rd extension
            >>> update(file, dat, 'sci', 2)  # update the 2nd SCI extension
            >>> update(file, dat, 3, header=hdr)  # update the 3rd extension
            >>> update(file, dat, header=hdr, ext=5)  # update the 5th extension
    """

    # parse the arguments
    header = None
    if len(ext) > 0:
        if isinstance(ext[0], Header):
            header = ext[0]
            ext = ext[1:]
        elif not isinstance(ext[0], (int, long, np.integer, str, tuple)):
            raise KeyError, 'Input argument has wrong data type.'

    if 'header' in extkeys:
        header = extkeys['header']
        del extkeys['header']

    classExtensions = extkeys.get('classExtensions', {})

    new_hdu=_makehdu(data, header, classExtensions)

    if not isinstance(filename, file) and hasattr(filename, 'closed'):
        closed = filename.closed
    else:
        closed = True

    hdulist, _ext = _getext(filename, 'update', *ext, **extkeys)
    hdulist[_ext] = new_hdu

    hdulist.close(closed=closed)


def info(filename, classExtensions={}, **parms):
    """
    Print the summary information on a FITS file.

    This includes the name, type, length of header, data shape and type
    for each extension.

    Parameters
    ----------
    filename : file path, file object, or file like object
        FITS file to obtain info from.  If opened, mode must be one of
        the following: rb, rb+, or ab+.

    classExtensions : dict, optional
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    parms : optional keyword arguments

        - **uint** : bool

            Interpret signed integer data where ``BZERO`` is the
            central value and ``BSCALE == 1`` as unsigned integer
            data.  For example, `int16` data with ``BZERO = 32768``
            and ``BSCALE = 1`` would be treated as `uint16` data.

            Note, for backward compatibility, the kwarg **uint16** may
            be used instead.  The kwarg was renamed when support was
            added for integers of any size.

        - **ignore_missing_end** : bool

            Do not issue an exception when opening a file that is
            missing an ``END`` card in the last header.  Default is
            `True`.
    """

    # allow file object to already be opened in any of the valid modes
    # and leave the file in the same state (opened or closed) as when
    # the function was called

    mode = 'copyonwrite'
    closed = True

    if not isinstance(filename, types.StringType) and \
       not isinstance(filename, types.UnicodeType):
        if hasattr(filename, 'closed'):
            closed = filename.closed
        elif hasattr(filename, 'fileobj') and filename.fileobj != None:
            closed = filename.fileobj.closed

    if not closed and hasattr(filename, 'mode'):

        if isinstance(filename, gzip.GzipFile):
            fmode = filename.fileobj.mode
        else:
            fmode = filename.mode

        for key in PYTHON_MODES.keys():
            if PYTHON_MODES[key] == fmode:
                mode = key
                break

    # Set the default value for the ignore_missing_end parameter
    if not parms.has_key('ignore_missing_end'):
        parms['ignore_missing_end'] = True

    f = fitsopen(filename,mode=mode,classExtensions=classExtensions, **parms)
    f.info()

    if closed:
        f.close()

def tdump(fitsFile, datafile=None, cdfile=None, hfile=None, ext=1,
          clobber=False, classExtensions={}):
    """
    Dump a table HDU to a file in ASCII format.  The table may be
    dumped in three separate files, one containing column definitions,
    one containing header parameters, and one for table data.

    Parameters
    ----------
    fitsFile : file path, file object or file-like object
        Input fits file.

    datafile : file path, file object or file-like object, optional
        Output data file.  The default is the root name of the input
        fits file appended with an underscore, followed by the
        extension number (ext), followed by the extension ``.txt``.

    cdfile : file path, file object or file-like object, optional
        Output column definitions file.  The default is `None`,
        no column definitions output is produced.

    hfile : file path, file object or file-like object, optional
        Output header parameters file.  The default is `None`,
        no header parameters output is produced.

    ext : int
        The number of the extension containing the table HDU to be
        dumped.

    clobber : bool
        Overwrite the output files if they exist.

    classExtensions : dict
        A dictionary that maps pyfits classes to extensions of those
        classes.  When present in the dictionary, the extension class
        will be constructed in place of the pyfits class.

    Notes
    -----
    The primary use for the `tdump` function is to allow editing in a
    standard text editor of the table data and parameters.  The
    `tcreate` function can be used to reassemble the table from the
    three ASCII files.
    """

    # allow file object to already be opened in any of the valid modes
    # and leave the file in the same state (opened or closed) as when
    # the function was called

    mode = 'copyonwrite'
    closed = True

    if not isinstance(fitsFile, types.StringType) and \
       not isinstance(fitsFile, types.UnicodeType):
        if hasattr(fitsFile, 'closed'):
            closed = fitsFile.closed
        elif hasattr(fitsFile, 'fileobj') and fitsFile.fileobj != None:
            closed = fitsFile.fileobj.closed

    if not closed and hasattr(fitsFile, 'mode'):

        if isinstance(fitsFile, gzip.GzipFile):
            fmode = fitsFile.fileobj.mode
        else:
            fmode = fitsFile.mode

        for key in PYTHON_MODES.keys():
            if PYTHON_MODES[key] == fmode:
                mode = key
                break

    f = fitsopen(fitsFile,mode=mode,classExtensions=classExtensions)

    # Create the default data file name if one was not provided

    if not datafile:
        root,tail = os.path.splitext(f._HDUList__file.name)
        datafile = root + '_' + `ext` + '.txt'

    # Dump the data from the HDU to the files
    f[ext].tdump(datafile, cdfile, hfile, clobber)

    if closed:
        f.close()

#tdump.__doc__ += BinTableHDU.tdumpFileFormat.replace("\n", "\n    ")

def tcreate(datafile, cdfile, hfile=None):
    """
    Create a table from the input ASCII files.  The input is from up
    to three separate files, one containing column definitions, one
    containing header parameters, and one containing column data.  The
    header parameters file is not required.  When the header
    parameters file is absent a minimal header is constructed.

    Parameters
    ----------
    datafile : file path, file object or file-like object
        Input data file containing the table data in ASCII format.

    cdfile : file path, file object or file-like object
        Input column definition file containing the names, formats,
        display formats, physical units, multidimensional array
        dimensions, undefined values, scale factors, and offsets
        associated with the columns in the table.

    hfile : file path, file object or file-like object, optional
        Input parameter definition file containing the header
        parameter definitions to be associated with the table.
        If `None`, a minimal header is constructed.

    Notes
    -----
    The primary use for the `tcreate` function is to allow the input of
    ASCII data that was edited in a standard text editor of the table
    data and parameters.  The tdump function can be used to create the
    initial ASCII files.
    """

    from pyfits.core import BinTableHDU

    # Construct an empty HDU
    hdu = BinTableHDU()

    # Populate and return that HDU
    hdu.tcreate(datafile, cdfile, hfile, replace=True)
    return hdu

#tcreate.__doc__ += BinTableHDU.tdumpFileFormat.replace("\n", "\n    ")
