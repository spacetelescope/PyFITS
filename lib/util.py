import os
import tempfile

import numpy as np

def _fromfile(infile, dtype, count, sep):
    """Create a numpy array from a file or a file-like object."""

    if isinstance(infile, file):
        return np.fromfile(infile, dtype=dtype, count=count, sep=sep)
    else: # treat as file-like object with "read" method
        read_size=np.dtype(dtype).itemsize * count
        str=infile.read(read_size)
        return np.fromstring(str, dtype=dtype, count=count, sep=sep)


def _tofile(arr, outfile):
    """Write a numpy array to a file or a file-like object."""

    if isinstance(outfile, file):
        arr.tofile(outfile)
    else: # treat as file-like object with "write" method
        str=arr.tostring()
        outfile.write(str)


def _chunk_array(arr, CHUNK_SIZE=2 ** 25):
    """
    Yields subviews of the given array.  The number of rows is
    selected so it is as close to CHUNK_SIZE (bytes) as possible.
    """
    if len(arr) == 0:
        return
    if isinstance(arr, FITS_rec):
        arr = np.asarray(arr)
    row_size = arr[0].size
    rows_per_chunk = max(min(CHUNK_SIZE // row_size, len(arr)), 1)
    for i in range(0, len(arr), rows_per_chunk):
        yield arr[i:i+rows_per_chunk,...]


def _unsigned_zero(dtype):
    """Given a numpy dtype, finds it's "zero" point, which is exactly in the
    middle of its range.

    """

    assert dtype.kind == 'u'
    return 1 << (dtype.itemsize * 8 - 1)


def _is_pseudo_unsigned(dtype):
    return dtype.kind == 'u' and dtype.itemsize >= 2


def _normalize_slice(input, naxis):
    """
    Set the slice's start/stop in the regular range.
    """

    def _normalize(indx, npts):
        if indx < -npts:
            indx = 0
        elif indx < 0:
            indx += npts
        elif indx > npts:
            indx = npts
        return indx

    _start = input.start
    if _start is None:
        _start = 0
    elif isinstance(_start, (int, long,np.integer)):
        _start = _normalize(_start, naxis)
    else:
        raise IndexError, 'Illegal slice %s, start must be integer.' % input

    _stop = input.stop
    if _stop is None:
        _stop = naxis
    elif isinstance(_stop, (int, long,np.integer)):
        _stop = _normalize(_stop, naxis)
    else:
        raise IndexError, 'Illegal slice %s, stop must be integer.' % input

    if _stop < _start:
        raise IndexError, 'Illegal slice %s, stop < start.' % input

    _step = input.step
    if _step is None:
        _step = 1
    elif isinstance(_step, (int, long, np.integer)):
        if _step <= 0:
            raise IndexError, 'Illegal slice %s, step must be positive.' % input
    else:
        raise IndexError, 'Illegal slice %s, step must be integer.' % input

    return slice(_start, _stop, _step)


def _tmpName(input):
    """Create a temporary file name which should not already exist.  Use the
    directory of the input file and the base name of the mktemp() output.

    """

    dirName = os.path.dirname(input)
    if dirName != '':
        dirName += '/'
    _name = dirName + os.path.basename(tempfile.mktemp())
    if not os.path.exists(_name):
        return _name
    else:
        raise RuntimeError("%s exists" % _name)
