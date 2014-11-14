from .extern import six

if six.PY3:
    # Stuff to do if Python 3
    import io

    # Make the decode_ascii utility function actually work
    import pyfits.util
    import numpy

    def encode_ascii(s):
        if isinstance(s, str):
            return s.encode('ascii')
        elif (isinstance(s, numpy.ndarray) and
              issubclass(s.dtype.type, numpy.str_)):
            ns = numpy.char.encode(s, 'ascii').view(type(s))
            if ns.dtype.itemsize != s.dtype.itemsize / 4:
                ns = ns.astype((numpy.bytes_, s.dtype.itemsize / 4))
            return ns
        elif (isinstance(s, numpy.ndarray) and
              not issubclass(s.dtype.type, numpy.bytes_)):
            raise TypeError('string operation on non-string array')
        return s
    pyfits.util.encode_ascii = encode_ascii

    def decode_ascii(s):
        if isinstance(s, bytes):
            return s.decode('ascii')
        elif (isinstance(s, numpy.ndarray) and
              issubclass(s.dtype.type, numpy.bytes_)):
            # np.char.encode/decode annoyingly don't preserve the type of the
            # array, hence the view() call
            # It also doesn't necessarily preserve widths of the strings,
            # hence the astype()
            if s.size == 0:
                # Numpy apparently also has a bug that if a string array is
                # empty calling np.char.decode on it returns an empty float64
                # array wth
                dt = s.dtype.str.replace('S', 'U')
                ns = numpy.array([], dtype=dt).view(type(s))
            else:
                ns = numpy.char.decode(s, 'ascii').view(type(s))
            if ns.dtype.itemsize / 4 != s.dtype.itemsize:
                ns = ns.astype((numpy.str_, s.dtype.itemsize))
            return ns
        elif (isinstance(s, numpy.ndarray) and
              not issubclass(s.dtype.type, numpy.str_)):
            # Don't silently pass through on non-string arrays; we don't want
            # to hide errors where things that are not stringy are attempting
            # to be decoded
            raise TypeError('string operation on non-string array')
        return s
    pyfits.util.decode_ascii = decode_ascii

    # Here we monkey patch (yes, I know) numpy to fix a few numpy Python 3
    # bugs.  The only behavior that's modified is that bugs are fixed, so that
    # should be OK.

    # Fix chararrays; this is necessary in numpy 1.5.1 and below--hopefully
    # should not be necessary later.  See
    # http://projects.scipy.org/numpy/ticket/1817
    # TODO: Maybe do a version check on numpy for this?  (Note: the fix for
    # this hasn't been accepted in Numpy yet, so a version number check would
    # not be helpful yet...)

    _chararray = numpy.char.chararray

    class chararray(_chararray):
        def __getitem__(self, obj):
            val = numpy.ndarray.__getitem__(self, obj)
            if isinstance(val, numpy.character):
                temp = val.rstrip()
                if numpy.char._len(temp) == 0:
                    val = ''
                else:
                    val = temp
            return val
    for m in [numpy.char, numpy.core.defchararray, numpy.core.records]:
        m.chararray = chararray

    # See the docstring for pyfits.util.fileobj_open for why we need to replace
    # this function
    def fileobj_open(filename, mode):
        return open(filename, mode, buffering=0)
    pyfits.util.fileobj_open = fileobj_open

    # Support the io.IOBase.readable/writable methods
    from pyfits.util import isreadable as _isreadable

    def isreadable(f):
        if hasattr(f, 'readable'):
            return f.readable()
        return _isreadable(f)
    pyfits.util.isreadable = isreadable

    from pyfits.util import iswritable as _iswritable

    def iswritable(f):
        if hasattr(f, 'writable'):
            return f.writable()
        return _iswritable(f)
    pyfits.util.iswritable = iswritable

    # isfile needs to support the higher-level wrappers around FileIO
    def isfile(f):
        if isinstance(f, io.FileIO):
            return True
        elif hasattr(f, 'buffer'):
            return isfile(f.buffer)
        elif hasattr(f, 'raw'):
            return isfile(f.raw)
        return False
    pyfits.util.isfile = isfile

    # Replace pyfits.util.maketrans and translate with versions that work
    # with Python 3 unicode strings
    pyfits.util.maketrans = str.maketrans

    def translate(s, table, deletechars):
        if deletechars:
            table = table.copy()
            for c in deletechars:
                table[ord(c)] = None
        return s.translate(table)
    pyfits.util.translate = translate
else:
    # Stuff to do if not Python 3
    import string
    import pyfits.util
    pyfits.util.maketrans = string.maketrans


try:
    from contextlib import ignored
except ImportError:
    from contextlib import contextmanager
    @contextmanager
    def ignored(*exceptions):
        """A context manager for ignoring exceptions.  Equivalent to::

            try:
                <body>
            except exceptions:
                pass

        Example::

            >>> import os
            >>> with ignored(OSError):
            ...     os.remove('file-that-does-not-exist')

        """

        try:
            yield
        except exceptions:
            pass
