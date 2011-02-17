import os
import tempfile
import warnings

import numpy as np


__all__ = ['Extendable', 'register_extension', 'register_extensions',
           'unregister_extensions']


# TODO: I'm somewhat of the opinion that this should go in pyfits.core, but for
# now that would create too much complication with imports (as many modules
# need to use this).  Eventually all the intra-package imports will be removed
# from pyfits.core, simplifying matters.  But for now they remain for
# backwards-compatibility.
class Extendable(type):
    _extensions = {}

    def __call__(cls, *args, **kwargs):
        if cls in cls._extensions:
            cls = cls._extensions[cls]
        self = cls.__new__(cls, *args, **kwargs)
        self.__init__(*args, **kwargs)
        return self

    # TODO: Touch up docstrings for sphinx
    @classmethod
    def register_extension(cls, extension, extends=None, silent=False):
        """
        Register an extension class.  This class will be used in all future
        instances of the class it extends.

        By default, the class it extends
        will automatically be its immediate superclass.  In
        multiple-inheritence cases, the left-most superclass is used.  In other
        words, the first class in the extension's MRO (after itself).

        Use the optional `extends` parameter to override the default behavior.
        Either a single class to extend may be specified, or an iterable of
        classes.  The classes to extend must still use the Extendable
        metaclass.

        Set `silent` to `True` to not output any warnings.
        """

        # If the extension class itself is not Extendable then we know it's no
        # good, since it has to be a sublcass of an Extendable.
        if not isinstance(extension, Extendable):
            raise TypeError("Class '%s' is not a subclass of an Extendable "
                            "class." % extension.__name__)

        if extends:
            try:
                extends = iter(extends)
            except TypeError:
                extends = [extends]
        else:
            extends = [extension.mro()[1]]

        # Don't allow the extension to be registered if *any* of the classes it
        # extends are not Extendable
        for c in extends:
            if not isinstance(c, Extendable):
                raise TypeError("Class '%s' is not an Extendable class."
                                % c.__name__)

        for c in extends:
            if not silent and c in cls._extensions:
                warnings.showwarning(
                    "Extension '%s' for '%s' being replaced with '%s'."
                    % (cls._extensions[c].__name__, c.__name__,
                       extension.__name__))
            cls._extensions[c] = extension

    @classmethod
    def register_extensions(cls, extensions, silent=False):
        """
        Register multiple extensions at once from a dict mapping extensions to
        the classes they extend.
        """

        for k, v in extensions.iteritems():
            if not isinstance(k, Extendable):
                raise TypeError("Extension class '%s' is not a subclass of "
                                "an Extendable class." % k.__name__)
            if not isinstance(v, Extendable):
                raise TypeError("Class '%s' is not an Extendable class.")

        for k, v in extensions.iteritems():
            if not silent and v in cls._extensions:
                warnings.showwarning(
                    "Extension '%s' for '%s' being replaced with '%s'."
                    % (cls._extensions[v].__name__, v.__name__, k.__name__))
            cls._extensions[v] = k

    @classmethod
    def unregister_extensions(cls, extensions):
        """
        Remove one or more extension classes from the extension registry.

        If the class is not in the registry this is silently ignored.
        """

        try:
            extensions = set(extensions)
        except TypeError:
            extensions = set([extensions])

        for k, v in cls._extensions.items():
            if v in extensions:
                del cls._extensions[k]

# Some shortcuts
register_extension = Extendable.register_extension
register_extensions = Extendable.register_extensions
unregister_extensions = Extendable.unregister_extensions


def _with_extensions(func):
    """
    This decorator exists mainly to support use of the new extension system in
    functions that still have a classExtensions keyword argument (which should
    be deprecated).

    This registers the extensions passed in classExtensions and unregisters
    them when the function exits.  It should be clear that any objects that
    persist after the function exits will still use the extension classes they
    were created from.
    """

    def _with_extensions_wrapper(*args, **kwargs):
        extension_classes = []
        if 'classExtensions' in kwargs:
            extensions = kwargs['classExtensions']
            if extensions:
                register_extensions(extensions)
                extension_classes = extensions.values()
            del kwargs['classExtensions']
        try:
            return func(*args, **kwargs)
        finally:
            if extension_classes:
                unregister_extensions(extension_classes)

    _with_extensions_wrapper.__doc__ = func.__doc__

    return _with_extensions_wrapper


class lazyproperty(object):
    """
    Works similarly to property(), but computes the value only once.

    Adapted from the recipe at
    http://code.activestate.com/recipes/363602-lazy-property-evaluation
    """

    def __init__(self, fget, fset=None, fdel=None):
        self._fget = fget
        self._fset = fset
        self._fdel = fdel

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        key = self._fget.func_name
        if key not in obj.__dict__:
            val = self._fget(obj)
            obj.__dict__[key] = val
            return val
        else:
            return obj.__dict__[key]

    def __set__(self, obj, val):
        if self._fset:
            self._fset(obj, val)
        obj.__dict__[self._fget.func_name] = val

    def __delete__(self, obj):
        if self._fdel:
            self._fdel(obj)
        key = self._fget.func_name
        if key in obj.__dict__:
            del obj.__dict__[key]


def _fromfile(infile, dtype, count, sep):
    """Create a numpy array from a file or a file-like object."""

    if isinstance(infile, file):
        return np.fromfile(infile, dtype=dtype, count=count, sep=sep)
    else: # treat as file-like object with "read" method
        read_size=np.dtype(dtype).itemsize * count
        s = infile.read(read_size)
        return np.fromstring(s, dtype=dtype, count=count, sep=sep)


def _tofile(arr, outfile):
    """Write a numpy array to a file or a file-like object."""

    if isinstance(outfile, file):
        arr.tofile(outfile)
    else: # treat as file-like object with "write" method
        s = arr.tostring()
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
    for idx in range(0, len(arr), rows_per_chunk):
        yield arr[idx:idx + rows_per_chunk,...]


def _unsigned_zero(dtype):
    """
    Given a numpy dtype, finds its "zero" point, which is exactly in the
    middle of its range.
    """

    assert dtype.kind == 'u'
    return 1 << (dtype.itemsize * 8 - 1)


def _is_pseudo_unsigned(dtype):
    return dtype.kind == 'u' and dtype.itemsize >= 2


def _is_int(val):
    return isinstance(val, (int, long, np.integer))


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
    elif _is_int(_start):
        _start = _normalize(_start, naxis)
    else:
        raise IndexError('Illegal slice %s; start must be integer.' % input)

    _stop = input.stop
    if _stop is None:
        _stop = naxis
    elif _is_int(_stop):
        _stop = _normalize(_stop, naxis)
    else:
        raise IndexError('Illegal slice %s; stop must be integer.' % input)

    if _stop < _start:
        raise IndexError('Illegal slice %s; stop < start.' % input)

    _step = input.step
    if _step is None:
        _step = 1
    elif _is_int(_step):
        if _step <= 0:
            raise IndexError('Illegal slice %s; step must be positive.'
                             % input)
    else:
        raise IndexError('Illegal slice %s; step must be integer.' % input)

    return slice(_start, _stop, _step)


def _tmp_name(input):
    """
    Create a temporary file name which should not already exist.  Use the
    directory of the input file and the base name of the mktemp() output.
    """

    dirname = os.path.dirname(input)
    name = os.path.join(dirname, os.path.basename(tempfile.mktemp()))
    if not os.path.exists(name):
        return name
    else:
        raise IOError('%s exists' % name)
