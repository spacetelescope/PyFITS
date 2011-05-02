import gzip
import os
import sys
import tempfile
import urllib
import warnings
import zipfile

import numpy as np
from numpy import memmap as Memmap

from pyfits.rec import _fix_dtype
from pyfits.util import Extendable, _fromfile, _tofile


# For Py3k; use the correct file type
# TODO: Consider moving this to the py3kcompat module and add file to builtins
if sys.version_info[0] >= 3:
    import io
    file = io.FileIO


PYTHON_MODES = {'readonly': u'rb', 'copyonwrite': u'rb', 'update': u'rb+',
                'append': u'ab+', 'ostream': u'w'}  # open modes
MEMMAP_MODES = {'readonly': 'r', 'copyonwrite': 'c', 'update': 'r+'}


class _File(object):
    """
    Represents a FITS file on disk (or in some other file-like object).
    """

    __metaclass__ = Extendable

    def __init__(self, fileobj=None, mode='copyonwrite', memmap=False):
        if fileobj is None:
            self.simulateonly = True
            return
        else:
            self.simulateonly = False

        if mode not in PYTHON_MODES:
            raise ValueError("Mode '%s' not recognized" % mode)

        # Determine what the _File object's name should be
        if isinstance(fileobj, file):
            self.name = fileobj.name
        elif isinstance(fileobj, basestring):
            if mode != 'append' and not os.path.exists(fileobj) and \
               not os.path.splitdrive(fileobj)[0]:
                #
                # Not writing file and file does not exist on local machine and
                # name does not begin with a drive letter (Windows), try to
                # get it over the web.
                #
                self.name, fileheader = urllib.urlretrieve(fileobj)
            else:
                self.name = fileobj
        else:
            if hasattr(fileobj, 'name'):
                self.name = fileobj.name
            elif hasattr(fileobj, 'filename'):
                self.name = fileobj.filename
            elif hasattr(fileobj, '__class__'):
                self.name = str(fileobj.__class__)
            else:
                self.name = str(type(fileobj))

        self.closed = False
        self.mode = mode
        self.memmap = memmap

        # Underlying fileobj is a file-like object, but an actual file object
        self.file_like = False

        self.compressed = False
        if isinstance(fileobj, (gzip.GzipFile, zipfile.ZipFile)):
            self.comrpessed = True

        self.readonly = False
        self.writeonly = False
        if mode in ('readonly', 'copyonwrite') or \
                (isinstance(fileobj, gzip.GzipFile) and mode == 'update'):
            self.readonly = True
        elif mode == 'ostream' or \
                (isinstance(fileobj, gzip.GzipFile) and mode == 'append'):
            self.writeonly = True

        if memmap and mode not in ('readonly', 'copyonwrite', 'update'):
            raise ValueError(
                   "Memory mapping is not implemented for mode `%s`." % mode)
        else:
            # Initialize the internal self.__file object
            if isinstance(fileobj, (file, gzip.GzipFile)):
                if hasattr(fileobj, 'closed'):
                    closed = fileobj.closed
                    foMode = fileobj.mode
                else:
                    if fileobj.fileobj is not None:
                        closed = fileobj.fileobj.closed
                        foMode = fileobj.fileobj.mode
                    else:
                        closed = True
                        foMode = PYTHON_MODES[mode]

                if not closed:
                    if PYTHON_MODES[mode] != foMode:
                        raise ValueError(
                            "Input mode '%s' (%s) does not match mode of the "
                            "input file (%s)." % (mode, PYTHON_MODES[mode],
                                                  fileobj.mode))
                    self.__file = fileobj
                elif isinstance(fileobj, file):
                    self.__file = open(self.name, PYTHON_MODES[mode])
                else:
                    self.__file = gzip.open(self.name, PYTHON_MODES[mode])
            elif isinstance(fileobj, basestring):
                if os.path.splitext(self.name)[1] == '.gz':
                    # Handle gzip files
                    if mode in ['update', 'append']:
                        raise ValueError(
                              "Writing to gzipped fits files is not supported")
                    zfile = gzip.GzipFile(self.name)
                    self.tfile = tempfile.NamedTemporaryFile('rb+', -1, '.fits')
                    self.name = self.tfile.name
                    self.__file = self.tfile.file
                    self.__file.write(zfile.read())
                    zfile.close()
                elif os.path.splitext(self.name)[1] == '.zip':
                    # Handle zip files
                    if mode in ['update', 'append']:
                        raise NotImplementedError(
                              "Writing to zipped fits files is not supported")
                    zfile = zipfile.ZipFile(self.name)
                    namelist = zfile.namelist()
                    if len(namelist) != 1:
                        raise NotImplementedError(
                          "Zip files with multiple members are not supported.")
                    self.tfile = tempfile.NamedTemporaryFile('rb+', -1,
                                                             '.fits')
                    self.name = self.tfile.name
                    self.__file = self.tfile.file
                    self.__file.write(zfile.read(namelist[0]))
                    zfile.close()
                else:
                    self.__file = open(self.name, PYTHON_MODES[mode])
            else:
                # We are dealing with a file like object.
                # Assume it is open.
                self.file_like = True
                self.__file = fileobj

                # If there is not seek or tell methods then set the mode to
                # output streaming.
                if not hasattr(self.__file, 'seek') or \
                   not hasattr(self.__file, 'tell'):
                    self.mode = mode = 'ostream'

                if (self.mode in ('copyonwrite', 'update', 'append') and
                    not hasattr(self.__file, 'write')):
                    raise IOError("File-like object does not have a 'write' "
                                  "method, required for mode '%s'."
                                  % self.mode)

                if self.mode == 'readonly' and \
                   not hasattr(self.__file, 'read'):
                    raise IOError("File-like object does not have a 'read' "
                                  "method, required for mode 'readonly'."
                                  % self.mode)

            # For 'ab+' mode, the pointer is at the end after the open in
            # Linux, but is at the beginning in Solaris.
            if mode == 'ostream':
                # For output stream start with a truncated file.
                self.size = 0
            elif isinstance(self.__file, gzip.GzipFile):
                pos = self.__file.tell()
                self.__file.fileobj.seek(0, 2)
                self.size = self.__file.fileobj.tell()
                self.__file.fileobj.seek(0)
                self.__file.seek(pos)
            elif hasattr(self.__file, 'seek'):
                pos = self.__file.tell()
                self.__file.seek(0, 2)
                self.size = self.__file.tell()
                self.__file.seek(pos)
            else:
                self.size = 0

    def __repr__(self):
        return '<%s.%s %s>' % (self.__module__, self.__class__.__name__,
                               self.__file)

    # Support the 'with' statement
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def getfile(self):
        """**Deprecated** Will be going away as soon as I figure out how."""
        return self.__file

    def read(self, size=None):
        return self.__file.read(size)

    def readarray(self, size=None, offset=None, dtype=np.uint8, shape=None):
        """
        Similar to file.read(), but returns the contents of the underlying
        file as a numpy array (or mmap'd array if memmap=True) rather than a
        string.

        Usually it's best not to use the `size` argument with this method, but
        it's provided for compatibility.
        """

        if not hasattr(self.__file, 'read'):
            raise EOFError

        if not isinstance(dtype, np.dtype):
            dtype = np.dtype(dtype)

        dtype = _fix_dtype(dtype)

        if size and size % dtype.itemsize != 0:
            raise ValueError('size %d not a multiple of %s' % (size, dtype))

        if isinstance(shape, int):
            shape = (shape,)

        if size and shape:
            actualsize = sum(dim * dtype.itemsize for dim in shape)
            if actualsize < size:
                raise ValueError('size %d is too few bytes for a %s array of '
                                 '%s' % (size, shape, dtype))
            if actualsize < size:
                raise ValueError('size %d is too many bytes for a %s array of '
                                 '%s' % (size, shape, dtype))

        if size and not shape:
            shape = (size / dtype.itemsize,)

        if not (size or shape):
            # TODO: Maybe issue a warning or raise an error instead?
            shape = (1,)

        if self.memmap:
            return Memmap(self.__file, offset=offset,
                          mode=MEMMAP_MODES[self.mode], dtype=dtype,
                          shape=shape)
        else:
            count = reduce(lambda x, y: x * y, shape)
            pos = self.__file.tell()
            self.__file.seek(offset)
            data = _fromfile(self.__file, dtype, count, '')
            data.shape = shape
            self.__file.seek(pos)
            return data

    def write(self, string):
        if 'b' in self.__file.mode and isinstance(string, unicode):
            string = string.encode('raw-unicode-escape')
        elif 'b' not in self.__file.mode and not isinstance(string, unicode):
            string = string.decode('raw-unicode-escape')
        self.__file.write(string)

    def writearray(self, array):
        """
        Similar to file.write(), but writes a numpy array instead of a

        Also like file.write(), a flush() or close() may be needed before
        the file on disk reflects the data written.
        """

        _tofile(array, self.__file)

    def flush(self):
        if hasattr(self.__file, 'flush'):
            self.__file.flush()

    def seek(self, offset, whence=0):
        # In newer Python versions, GzipFiles support the whence argument, but
        # I don't think it was added until 2.6; instead of assuming it's
        # present, we implement our own support for it here
        if isinstance(self.__file, gzip.GzipFile):
            if whence:
                if whence == 1:
                    offset = self.__file.offset + offset
                else:
                    raise ValueError('Seek from end not supported')
            self.__file.seek(offset)
        else:
            self.__file.seek(offset, whence)

        pos = self.__file.tell()
        if pos > self.size:
            warnings.warn('Warning: File may have been truncated: actual '
                          'file length (%i) is smaller than the expected '
                          'size (%i)' % (self.size, pos))

    def tell(self):
        if not hasattr(self.__file, 'tell'):
            raise EOFError
        return self.__file.tell()

    def truncate(self, size=None):
        if hasattr(self.__file, 'truncate'):
            self.__file.truncate(size)

    def close(self):
        """
        Close the 'physical' FITS file.
        """

        if hasattr(self.__file, 'close'):
            self.__file.close()

        if hasattr(self, 'tfile'):
            del self.tfile

        self.closed = True

