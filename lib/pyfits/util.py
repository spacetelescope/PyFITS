import functools
import itertools
import os
import sys
import tempfile
import warnings

import numpy as np


__all__ = ['Extendable', 'register_extension', 'register_extensions',
           'unregister_extensions']


BLOCK_SIZE = 2880 # the FITS block size


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

# TODO: Fix this in Python3--commented out in the meantime
#    def __getattribute__(cls, attr):
#        orig_cls = cls
#        if attr != '_extensions' and cls in cls._extensions:
#            cls = cls._extensions[cls]
#        return super(Extendable, cls).__getattribute__(attr)

    @classmethod
    def register_extension(cls, extension, extends=None, silent=False):
        """
        Register an extension class.  This class will be used in all future
        instances of the class it extends.

        By default, the class it extends
        will automatically be its immediate superclass.  In
        multiple-inheritence cases, the left-most superclass is used.  In other
        words, the first class in the extension's MRO (after itself).

        Parameters
        ----------
        extension : class
            The class object of a superclass of an Extendable class (that is,
            any class with the `Extendable` metaclass

        extends : class, optional
            Override the default behavior of extending the immediate
            superclass.  Either a single class to extend may be specified, or
            an iterable of classes.  The classes to extend must still have the
            `Extendable` metaclass.

        silent : bool, optional
            If `True`, does not output any warnings
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
            if c in cls._extensions:
                if not silent:
                    warnings.warn(
                        "Extension '%s' for '%s' being replaced with '%s'."
                        % (cls._extensions[c].__name__, c.__name__,
                           extension.__name__))
                # This class has already been extended by a different class, so
                # first we need to undo that
                cls._unextend_subclasses(c, extension)
            # It's imperative that _extend_subclasses is called first;
            # otherwise the extension will override c.__subclasses__!
            cls._extend_subclasses(c, extension)
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
            cls._extend_subclasses(v, k)
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
                cls._unextend_subclasses(k, v)

    @classmethod
    def _extend_subclasses(cls, extendable, extension):
        for s in extendable.__subclasses__():
            if s is extension:
                # Don't want the extension to have itself as a base
                continue
            bases = list(s.__bases__)
            idx = bases.index(extendable)
            bases = bases[:idx] + [extension] + bases[idx + 1:]
            s.__bases__ = tuple(bases)

    @classmethod
    def _unextend_subclasses(cls, extendable, extension):
        # Since the subclasses' bases were changed, they will now be listed as
        # subclasses of the extension
        for s in extension.__subclasses__():
            if s is extension:
                continue
            bases = list(s.__bases__)
            idx = bases.index(extension)
            bases = bases[:idx] + [extendable] + bases[idx + 1:]
            s.__bases__ = tuple(bases)

# Some shortcuts
register_extension = Extendable.register_extension
register_extensions = Extendable.register_extensions
# unregister_extension is currently the same as just unregister_extensions (it
# won't balk if you still try to pass more than one)--it's just provided for
# symmetry's sake
unregister_extension = Extendable.unregister_extensions
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

    @functools.wraps(func)
    def _with_extensions_wrapper(*args, **kwargs):
        extension_classes = []
        if 'classExtensions' in kwargs:
            extensions = kwargs['classExtensions']
            warnings.warn('The classExtensions argument is deprecated.  '
                          'Instead call pyfits.register_extensions(%s) once '
                          'before any code that uses those extensions.'
                          % repr(extensions), DeprecationWarning)
            if extensions:
                register_extensions(extensions)
                extension_classes = extensions.values()
            del kwargs['classExtensions']
        try:
            return func(*args, **kwargs)
        finally:
            if extension_classes:
                unregister_extensions(extension_classes)

    return _with_extensions_wrapper


def itersubclasses(cls, _seen=None):
    """
    itersubclasses(cls)

    Generator over all subclasses of a given class, in depth first order.

    >>> list(itersubclasses(int)) == [bool]
    True
    >>> class A(object): pass
    >>> class B(A): pass
    >>> class C(A): pass
    >>> class D(B,C): pass
    >>> class E(D): pass
    >>>
    >>> for cls in itersubclasses(A):
    ...     print(cls.__name__)
    B
    D
    E
    C
    >>> # get ALL (new-style) classes currently defined
    >>> [cls.__name__ for cls in itersubclasses(object)] #doctest: +ELLIPSIS
    ['type', ...'tuple', ...]

    From http://code.activestate.com/recipes/576949/ 
    """

    if not isinstance(cls, type):
        raise TypeError('itersubclasses must be called with '
                        'new-style classes, not %.100r' % cls)
    if _seen is None: _seen = set()
    try:
        subs = cls.__subclasses__()
    except TypeError: # fails only when cls is type
        subs = cls.__subclasses__(cls)
    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in itersubclasses(sub, _seen):
                yield sub


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


def deprecated(message='', name='', alternative='', pending=False):
    """
    Used to mark a function as deprecated.

    TODO: Provide a class deprecation marker as well.

    To mark an attribute as deprecated, replace that attribute with a
    depcrecated property.

    Parameters
    ------------
    message : str, optional
        Override the default deprecation message.  The format specifier
        %(func)s may be used for the name of the function, and %(alternative)s
        may be used in the deprecation message to insert the name of an
        alternative to the deprecated function.

    name : str, optional
        The name of the deprecated function; if not provided the name is
        automatically determined from the passed in function, though this is
        useful in the case of renamed functions, where the new function is just
        assigned to the name of the deprecated function.  For example:
            def new_function():
                ...
            oldFunction = new_function

    alternative : str, optional
        An alternative function that the user may use in place of the
        deprecated function.  The deprecation warning will tell the user about
        this alternative if provided.

    pending : bool, optional
        If True, uses a PendingDeprecationWarning instead of a
        DeprecationWarning.

    """

    def deprecate(func):
        if isinstance(func, classmethod):
            try:
                func = func.__func__
            except AttributeError:
                # classmethods in Python2.6 and below lack the __func__
                # attribute so we need to hack around to get it
                method = func.__get__(None, object)
                if hasattr(method, '__func__'):
                    func = method.__func__
                elif hasattr(method, 'im_func'):
                    func = method.im_func
                else:
                    # Nothing we can do really...  just return the original
                    # classmethod
                    return func
            is_classmethod = True
        else:
            is_classmethod = False

        @functools.wraps(func)
        def deprecated_func(*args, **kwargs):
            # _message and _name are necessary; otherwise assignments to name
            # and message will cause the interpreter to treat them as local
            # variables, instead of encapuslated variables
            _message = message
            _name = name
            if not _name:
                _name = func.__name__

            if not _message or type(_message) == type(deprecate):
                if pending:
                    _message = 'The %(func)s function will be deprecated in' \
                               'a future version.'
                else:
                    _message = 'The %(func)s function is deprecated and may ' \
                               'be removed in a future version.'
                if alternative:
                    _message += '  Use %(alternative)s instead.'

            if pending:
                category = DeprecationPendingWarning
            else:
                category = DeprecationWarning

            warnings.warn(
                _message % {'func': _name, 'alternative': alternative},
                category, stacklevel=2)

            return func(*args, **kwargs)
        if is_classmethod:
            deprecated_func = classmethod(deprecated_func)
        return deprecated_func

    if type(message) == type(deprecate):
        return deprecate(message)

    return deprecate


def pairwise(iterable):
    """Return the items of an iterable paired with its next item.

    Ex: s -> (s0,s1), (s1,s2), (s2,s3), ....
    """

    a, b = itertools.tee(iterable)
    for _ in b:
        # Just a little trick to advance b without having to catch
        # StopIter if b happens to be empty
        break
    return itertools.izip(a, b)


def encode_ascii(s):
    """
    In Python 2 this is a no-op.  Strings are left alone.  In Python 3 this
    will be replaced with a function that actually encodes unicode strings to
    ASCII bytes.
    """

    return s


def decode_ascii(s):
    """
    In Python 2 this is a no-op.  Strings are left alone.  In Python 3 this
    will be replaced with a function that actually decodes ascii bytes to
    unicode.
    """

    return s


def translate(s, table, deletechars):
    """
    This is a version of string/unicode.translate() that can handle string or
    unicode strings the same way using a translation table made with
    string.maketrans.
    """

    if isinstance(s, str):
        return s.translate(table, deletechars)
    elif isinstance(s, unicode):
        table = dict((x, ord(table[x])) for x in range(256)
                     if ord(table[x]) != x)
        for c in deletechars:
            table[ord(c)] = None
        return s.translate(table)



def _fromfile(infile, dtype, count, sep):
    """Create a numpy array from a file or a file-like object."""

    if isinstance(infile, file):
        return np.fromfile(infile, dtype=dtype, count=count, sep=sep)
    else: # treat as file-like object with "read" method
        read_size = np.dtype(dtype).itemsize * count
        s = infile.read(read_size)
        return np.fromstring(s, dtype=dtype, count=count, sep=sep)


def _tofile(arr, outfile):
    """Write a numpy array to a file or a file-like object."""

    if isinstance(outfile, file):
        arr.tofile(outfile)
    else: # treat as file-like object with "write" method
        _write_string(outfile, arr.tostring())


def _write_string(f, s):
    """
    Write a string to a file, encoding to ASCII if the file is open in binary
    mode, or decoding if the file is open in text mode.
    """

    # Assume if the file object doesn't have a specific mode, that the mode is
    # binary
    if hasattr(f, 'mode'):
        binmode = 'b' in f.mode
    else:
        binmode = True

    if binmode and isinstance(s, unicode):
        s = encode_ascii(s)
    elif not binmode and not isinstance(f, unicode):
        s = decode_ascii(s)
    f.write(s)


def _convert_array(array, dtype):
    """
    Converts an array to a new dtype--if the itemsize of the new dtype is
    the same as the old dtype, a view is returned.  Otherwise a new array must
    be created.
    """

    if array.dtype == dtype:
        return array
    elif array.dtype.itemsize == dtype.itemsize:
        return array.view(dtype)
    else:
        return array.astype(dtype)


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


def _str_to_num(val):
    """Converts a given string to either an int or a float if necessary."""

    try:
        num = int(val)
    except ValueError:
        # If this fails then an exception should be raised anyways
        num = float(val)
    return num


def _pad_length(stringlen):
    """Bytes needed to pad the input stringlen to the next FITS block."""

    return (BLOCK_SIZE - (stringlen % BLOCK_SIZE)) % BLOCK_SIZE


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
    directory of the input file as the base name of the mkstemp() output.
    """

    if input is not None:
        input = os.path.dirname(input)
    f, fn = tempfile.mkstemp(dir=input)
    os.close(f)
    return fn
