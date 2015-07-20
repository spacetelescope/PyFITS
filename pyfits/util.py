from __future__ import division

import functools
import gzip
import itertools
import io
import mmap
import os
import platform
import signal
import sys
import tempfile
import textwrap
import threading
import warnings
import weakref

from distutils.version import LooseVersion

try:
    from StringIO import StringIO
except ImportError:
    class StringIO(object):
        pass

import numpy as np

from .extern import six
from .extern.six import (iteritems, string_types, integer_types, text_type,
                         binary_type, next)
from .extern.six.moves import zip, reduce


BLOCK_SIZE = 2880  # the FITS block size


if six.PY3:
    cmp = lambda a, b: (a > b) - (a < b)
elif six.PY2:
    cmp = cmp


class NotifierMixin(object):
    """
    Mixin class that provides services by which objects can register
    listeners to changes on that object.

    All methods provided by this class are underscored, since this is intended
    for internal use to communicate between classes in a generic way, and is
    not machinery that should be exposed to users of the classes involved.

    Use the ``_add_listener`` method to register a listener on an instance of
    the notifier.  This registers the listener with a weak reference, so if
    no other references to the listener exist it is automatically dropped from
    the list and does not need to be manually removed.

    Call the ``_notify`` method on the notifier to update all listeners
    upon changes.  ``_notify('change_type', *args, **kwargs)`` results
    in calling ``listener._update_change_type(*args, **kwargs)`` on all
    listeners subscribed to that notifier.

    If a particular listener does not have the appropriate update method
    it is ignored.

    Examples
    --------

    >>> class Widget(NotifierMixin):
    ...     state = 1
    ...     def __init__(self, name):
    ...         self.name = name
    ...     def update_state(self):
    ...         self.state += 1
    ...         self._notify('widget_state_changed', self)
    ...
    >>> class WidgetListener(object):
    ...     def _update_widget_state_changed(self, widget):
    ...         print('Widget {0} changed state to {1}'.format(
    ...             widget.name, widget.state))
    ...
    >>> widget = Widget('fred')
    >>> listener = WidgetListener()
    >>> widget._add_listener(listener)
    >>> widget.update_state()
    Widget fred changed state to 2
    """

    _listeners = None

    def _add_listener(self, listener):
        """
        Add an object to the list of listeners to notify of changes to this
        object.  This adds a weakref to the list of listeners that is
        removed from the listeners list when the listener has no other
        references to it.
        """

        if self._listeners is None:
            self._listeners = []

        def remove(p):
            self._listeners.remove(p)

        # Make sure this object is not already in the listeners:
        for ref in self._listeners:
            if ref() is listener:
                return

        ref = weakref.ref(listener, remove)
        self._listeners.append(ref)

    def _remove_listener(self, listener):
        """
        Removes the specified listener from the listeners list.  This relies
        on object identity (i.e. the ``is`` operator).
        """

        if self._listeners is None:
            return

        for idx, ref in enumerate(self._listeners[:]):
            if ref() is listener:
                del self._listeners[idx]
                break

    def _notify(self, notification, *args, **kwargs):
        """
        Notify all listeners of some particular state change by calling their
        ``_update_<notification>`` method with the given ``*args`` and
        ``**kwargs``.

        The notification does not by default include the object that actually
        changed (``self``), but it certainly may if required.
        """

        if self._listeners is None:
            return

        method_name = '_update_{0}'.format(notification)
        for listener in self._listeners:
            listener = listener()  # dereference weakref
            if hasattr(listener, method_name):
                method = getattr(listener, method_name)
                if callable(method):
                    method(*args, **kwargs)

    def __getstate__(self):
        """
        Exclude listeners when saving the listener's state, since they may be
        ephemeral.
        """

        # TODO: This hasn't come up often, but if anyone needs to pickle HDU
        # objects it will be necessary when HDU objects' states are restored to
        # re-register themselves as listeners on their new column instances.
        try:
            state = super(NotifierMixin, self).__getstate__()
        except AttributeError:
            # Chances are the super object doesn't have a getstate
            state = self.__dict__.copy()

        state['_listeners'] = None
        return state


def first(iterable):
    """
    Returns the first item returned by iterating over an iterable object.

    Example:

    >>> a = [1, 2, 3]
    >>> first(a)
    1
    """

    return next(iter(iterable))


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
    [...'tuple', ...'type', ...]

    From http://code.activestate.com/recipes/576949/
    """

    if not isinstance(cls, type):
        raise TypeError('itersubclasses must be called with '
                        'new-style classes, not %.100r' % cls)
    if _seen is None:
        _seen = set()
    try:
        subs = cls.__subclasses__()
    except TypeError:  # fails only when cls is type
        subs = cls.__subclasses__(cls)
    for sub in sorted(subs, key=lambda s: s.__name__):
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

    def __init__(self, fget, fset=None, fdel=None, doc=None):
        self._fget = fget
        self._fset = fset
        self._fdel = fdel
        if doc is None:
            self.__doc__ = fget.__doc__
        else:
            self.__doc__ = doc
        self._key = self._fget.__name__

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        try:
            return obj.__dict__[self._key]
        except KeyError:
            val = self._fget(obj)
            obj.__dict__[self._key] = val
            return val

    def __set__(self, obj, val):
        obj_dict = obj.__dict__
        if self._fset:
            ret = self._fset(obj, val)
            if ret is not None and obj_dict.get(self._key) is ret:
                # By returning the value set the setter signals that it took
                # over setting the value in obj.__dict__; this mechanism allows
                # it to override the input value
                return
        obj_dict[self._key] = val

    def __delete__(self, obj):
        if self._fdel:
            self._fdel(obj)
        if self._key in obj.__dict__:
            del obj.__dict__[self._key]

    def getter(self, fget):
        return self.__ter(fget, 0)

    def setter(self, fset):
        return self.__ter(fset, 1)

    def deleter(self, fdel):
        return self.__ter(fdel, 2)

    def __ter(self, f, arg):
        args = [self._fget, self._fset, self._fdel, self.__doc__]
        args[arg] = f
        cls_ns = sys._getframe(1).f_locals
        for k, v in iteritems(cls_ns):
            if v is self:
                property_name = k
                break

        cls_ns[property_name] = lazyproperty(*args)

        return cls_ns[property_name]


# TODO: This can still be made to work for setters by implementing an
# accompanying metaclass that supports it; we just don't need that right this
# second
class classproperty(property):
    """
    Similar to `property`, but allows class-level properties.  That is,
    a property whose getter is like a `classmethod`.

    The wrapped method may explicitly use the `classmethod` decorator (which
    must become before this decorator), or the `classmethod` may be omitted
    (it is implicit through use of this decorator).

    .. note::

        classproperty only works for *read-only* properties.  It does not
        currently allow writeable/deleteable properties, due to subtleties of how
        Python descriptors work.  In order to implement such properties on a class
        a metaclass for that class must be implemented.

    Parameters
    ----------
    fget : callable
        The function that computes the value of this property (in particular,
        the function when this is used as a decorator) a la `property`.

    doc : str, optional
        The docstring for the property--by default inherited from the getter
        function.

    lazy : bool, optional
        If True, caches the value returned by the first call to the getter
        function, so that it is only called once (used for lazy evaluation
        of an attribute).  This is analogous to `lazyproperty`.  The ``lazy``
        argument can also be used when `classproperty` is used as a decorator
        (see the third example below).  When used in the decorator syntax this
        *must* be passed in as a keyword argument.

    Examples
    --------

    ::

        >>> class Foo(object):
        ...     _bar_internal = 1
        ...     @classproperty
        ...     def bar(cls):
        ...         return cls._bar_internal + 1
        ...
        >>> Foo.bar
        2
        >>> foo_instance = Foo()
        >>> foo_instance.bar
        2
        >>> foo_instance._bar_internal = 2
        >>> foo_instance.bar  # Ignores instance attributes
        2

    As previously noted, a `classproperty` is limited to implementing
    read-only attributes::

        >>> class Foo(object):
        ...     _bar_internal = 1
        ...     @classproperty
        ...     def bar(cls):
        ...         return cls._bar_internal
        ...     @bar.setter
        ...     def bar(cls, value):
        ...         cls._bar_internal = value
        ...
        Traceback (most recent call last):
        ...
        NotImplementedError: classproperty can only be read-only; use a
        metaclass to implement modifiable class-level properties

    When the ``lazy`` option is used, the getter is only called once::

        >>> class Foo(object):
        ...     @classproperty(lazy=True)
        ...     def bar(cls):
        ...         print("Performing complicated calculation")
        ...         return 1
        ...
        >>> Foo.bar
        Performing complicated calculation
        1
        >>> Foo.bar
        1

    If a subclass inherits a lazy `classproperty` the property is still
    re-evaluated for the subclass::

        >>> class FooSub(Foo):
        ...     pass
        ...
        >>> FooSub.bar
        Performing complicated calculation
        1
        >>> FooSub.bar
        1
    """

    def __new__(cls, fget=None, doc=None, lazy=False):
        if fget is None:
            # Being used as a decorator--return a wrapper that implements
            # decorator syntax
            def wrapper(func):
                return cls(func, lazy=lazy)

            return wrapper

        return super(classproperty, cls).__new__(cls)

    def __init__(self, fget, doc=None, lazy=False):
        self._lazy = lazy
        if lazy:
            self._cache = {}
        fget = self._wrap_fget(fget)

        super(classproperty, self).__init__(fget=fget, doc=doc)

        # There is a buglet in Python where self.__doc__ doesn't
        # get set properly on instances of property subclasses if
        # the doc argument was used rather than taking the docstring
        # from fget
        if doc is not None:
            self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if self._lazy and objtype in self._cache:
            return self._cache[objtype]

        if objtype is not None:
            # The base property.__get__ will just return self here;
            # instead we pass objtype through to the original wrapped
            # function (which takes the class as its sole argument)
            val = self.fget.__wrapped__(objtype)
        else:
            val = super(classproperty, self).__get__(obj, objtype=objtype)

        if self._lazy:
            if objtype is None:
                objtype = obj.__class__

            self._cache[objtype] = val

        return val

    def getter(self, fget):
        return super(classproperty, self).getter(self._wrap_fget(fget))

    def setter(self, fset):
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties")

    def deleter(self, fdel):
        raise NotImplementedError(
            "classproperty can only be read-only; use a metaclass to "
            "implement modifiable class-level properties")

    @staticmethod
    def _wrap_fget(orig_fget):
        if isinstance(orig_fget, classmethod):
            orig_fget = orig_fget.__func__

        # Using stock functools.wraps instead of the fancier version
        # found later in this module, which is overkill for this purpose

        @functools.wraps(orig_fget)
        def fget(obj):
            return orig_fget(obj.__class__)

        # Set the __wrapped__ attribute manually for support on Python 2
        fget.__wrapped__ = orig_fget

        return fget


class PyfitsDeprecationWarning(UserWarning):
    pass


class PyfitsPendingDeprecationWarning(UserWarning):
    pass


# TODO: Provide a class deprecation marker as well.
def deprecated(since, message='', name='', alternative='', pending=False):
    """
    Used to mark a function as deprecated.

    To mark an attribute as deprecated, replace that attribute with a
    depcrecated property.

    Parameters
    ------------
    since : str
        The release at which this API became deprecated.  This is required.

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
        If True, uses a PyfitsPendingDeprecationWarning instead of a
        PyfitsDeprecationWarning.

    """

    def deprecate(func, message=message, name=name, alternative=alternative,
                  pending=pending):
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

        if not name:
            name = func.__name__

        altmessage = ''
        if not message or type(message) == type(deprecate):
            if pending:
                message = ('The %(func)s function will be deprecated in a '
                           'future version.')
            else:
                message = (
                    'The %(func)s function is deprecated as of version '
                    '%(since)s and may be removed in a future version.')
            if alternative:
                altmessage = '\n\n        Use %s instead.' % alternative

        message = ((message % {'func': name, 'alternative': alternative,
                               'since': since}) + altmessage)

        @functools.wraps(func)
        def deprecated_func(*args, **kwargs):
            if pending:
                category = PyfitsPendingDeprecationWarning
            else:
                category = PyfitsDeprecationWarning

            warnings.warn(message, category, stacklevel=2)

            return func(*args, **kwargs)

        old_doc = deprecated_func.__doc__
        if not old_doc:
            old_doc = ''
        old_doc = textwrap.dedent(old_doc).strip('\n')
        altmessage = altmessage.strip()
        if not altmessage:
            altmessage = message.strip()
        new_doc = (('\n.. deprecated:: %(since)s'
                    '\n    %(message)s\n\n' %
                    {'since': since, 'message': altmessage.strip()}) + old_doc)
        if not old_doc:
            # This is to prevent a spurious 'unexected unindent' warning from
            # docutils when the original docstring was blank.
            new_doc += r'\ '

        deprecated_func.__doc__ = new_doc

        if is_classmethod:
            deprecated_func = classmethod(deprecated_func)
        return deprecated_func

    if type(message) == type(deprecate):
        return deprecate(message)

    return deprecate


def ignore_sigint(func):
    """
    This decorator registers a custom SIGINT handler to catch and ignore SIGINT
    until the wrapped function is completed.
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        # Get the name of the current thread and determine if this is a single
        # threaded application
        curr_thread = threading.currentThread()
        single_thread = (threading.activeCount() == 1 and
                         curr_thread.getName() == 'MainThread')

        class SigintHandler(object):
            def __init__(self):
                self.sigint_received = False

            def __call__(self, signum, frame):
                warnings.warn('KeyboardInterrupt ignored until %s is '
                              'complete!' % func.__name__)
                self.sigint_received = True

        sigint_handler = SigintHandler()

        # Define new signal interput handler
        if single_thread:
            # Install new handler
            old_handler = signal.signal(signal.SIGINT, sigint_handler)

        try:
            func(*args, **kwargs)
        finally:
            if single_thread:
                if old_handler is not None:
                    signal.signal(signal.SIGINT, old_handler)
                else:
                    signal.signal(signal.SIGINT, signal.SIG_DFL)

                if sigint_handler.sigint_received:
                    raise KeyboardInterrupt

    return wrapped


def pairwise(iterable):
    """Return the items of an iterable paired with its next item.

    Ex: s -> (s0,s1), (s1,s2), (s2,s3), ....
    """

    a, b = itertools.tee(iterable)
    for _ in b:
        # Just a little trick to advance b without having to catch
        # StopIter if b happens to be empty
        break
    return zip(a, b)


def isiterable(obj):
    """Returns true of the given object is iterable."""

    # In Python2.6 and up this is simply a matter of checking isinstance
    # collections.Iterable, but this unavailable in Python 2.5 and below
    try:
        from collections import Iterable
        if isinstance(obj, Iterable):
            return True
    except ImportError:
        pass

    try:
        iter(obj)
        return True
    except TypeError:
        return False


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


def isreadable(f):
    """
    Returns True if the file-like object can be read from.  This is a common-
    sense approximation of io.IOBase.readable.
    """

    if hasattr(f, 'closed') and f.closed:
        # This mimics the behavior of io.IOBase.readable
        raise ValueError('I/O operation on closed file')

    if not hasattr(f, 'read'):
        return False

    if hasattr(f, 'mode') and not any((c in f.mode for c in 'r+')):
        return False

    # Not closed, has a 'read()' method, and either has no known mode or a
    # readable mode--should be good enough to assume 'readable'
    return True


def iswritable(f):
    """
    Returns True if the file-like object can be written to.  This is a common-
    sense approximation of io.IOBase.writable.
    """

    if hasattr(f, 'closed') and f.closed:
        # This mimics the behavior of io.IOBase.writable
        raise ValueError('I/O operation on closed file')

    if not hasattr(f, 'write'):
        return False

    if hasattr(f, 'mode') and not any((c in f.mode for c in 'wa+')):
        return False

    # Note closed, has a 'write()' method, and either has no known mode or a
    # mode that supports writing--should be good enough to assume 'writable'
    return True


def isfile(f):
    """
    Returns True if the given object represents an OS-level file (that is,
    isinstance(f, file)).

    On Python 3 this also returns True if the given object is higher level
    wrapper on top of a FileIO object, such as a TextIOWrapper.
    """

    return isinstance(f, file)


def fileobj_open(filename, mode):
    """
    A wrapper around the `open()` builtin.

    This exists because in Python 3, `open()` returns an `io.BufferedReader` by
    default.  This is bad, because `io.BufferedReader` doesn't support random
    access, which we need in some cases.  In the Python 3 case (implemented in
    the py3compat module) we must call open with buffering=0 to get a raw
    random-access file reader.
    """

    return open(filename, mode)


def fileobj_name(f):
    """
    Returns the 'name' of file-like object f, if it has anything that could be
    called its name.  Otherwise f's class or type is returned.  If f is a
    string f itself is returned.
    """

    if isinstance(f, string_types):
        return f
    elif isinstance(f, gzip.GzipFile):
        # The .name attribute on GzipFiles does not always represent the name
        # of the file being read/written--it can also represent the original
        # name of the file being compressed
        # See the documentation at
        # https://docs.python.org/3/library/gzip.html#gzip.GzipFile
        # As such, for gzip files only return the name of the underlying
        # fileobj, if it exists
        return fileobj_name(f.fileobj)
    elif hasattr(f, 'name'):
        return f.name
    elif hasattr(f, 'filename'):
        return f.filename
    elif hasattr(f, '__class__'):
        return str(f.__class__)
    else:
        return str(type(f))


def fileobj_closed(f):
    """
    Returns True if the given file-like object is closed or if f is not a
    file-like object.
    """

    if hasattr(f, 'closed'):
        return f.closed
    elif hasattr(f, 'fileobj') and hasattr(f.fileobj, 'closed'):
        return f.fileobj.closed
    elif hasattr(f, 'fp') and hasattr(f.fp, 'closed'):
        return f.fp.closed
    else:
        return False


def fileobj_mode(f):
    """
    Returns the 'mode' string of a file-like object if such a thing exists.
    Otherwise returns None.
    """

    # Go from most to least specific--for example gzip objects have a 'mode'
    # attribute, but it's not analogous to the file.mode attribute
    if hasattr(f, 'fileobj') and hasattr(f.fileobj, 'mode'):
        fileobj = f.fileobj
    elif hasattr(f, 'fp') and hasattr(f.fp, 'mode'):
        fileobj = f.fp
    elif hasattr(f, 'mode'):
        fileobj = f
    else:
        return None

    return _fileobj_normalize_mode(fileobj)


def _fileobj_normalize_mode(f):
    """Takes care of some corner cases in Python where the mode string
    is either oddly formatted or does not truly represent the file mode.
    """

    # I've noticed that sometimes Python can produce modes like 'r+b' which I
    # would consider kind of a bug--mode strings should be normalized.  Let's
    # normalize it for them:
    mode = f.mode

    if isinstance(f, gzip.GzipFile):
        # GzipFiles can be either readonly or writeonly
        if mode == gzip.READ:
            return 'rb'
        elif mode == gzip.WRITE:
            return 'wb'
        else:
            # This shouldn't happen?
            return None

    if '+' in mode:
        mode = mode.replace('+', '')
        mode += '+'

    if _fileobj_is_append_mode(f) and 'a' not in mode:
        mode = mode.replace('r', 'a').replace('w', 'a')

    return mode


def _fileobj_is_append_mode(f):
    """Normally the way to tell if a file is in append mode is if it has
    'a' in the mode string.  However on Python 3 (or in particular with
    the io module) this can't be relied on.  See
    http://bugs.python.org/issue18876.
    """

    if 'a' in f.mode:
        # Take care of the obvious case first
        return True

    # We might have an io.FileIO in which case the only way to know for sure
    # if the file is in append mode is to ask the file descriptor
    if not hasattr(f, 'fileno'):
        # Who knows what this is?
        return False

    # Call platform-specific _is_append_mode
    # If this file is already closed this can result in an error
    try:
        return _is_append_mode_platform(f.fileno())
    except (ValueError, IOError):
        return False


if sys.platform.startswith('win32'):
    # This global variable is used in _is_append_mode to cache the computed
    # size of the ioinfo struct from msvcrt which may have a different size
    # depending on the version of the library and how it was compiled
    _sizeof_ioinfo = None

    def _make_is_append_mode():
        # We build the platform-specific _is_append_mode function for Windows
        # inside a function factory in order to avoid cluttering the local
        # namespace with ctypes stuff
        from ctypes import (cdll, c_size_t, c_void_p, c_int, c_char,
                            Structure, POINTER, cast)

        from ctypes.util import find_msvcrt

        def _dummy_is_append_mode(fd):
            warnings.warn(
                'Could not find appropriate MS Visual C Runtime '
                'library or library is corrupt/misconfigured; cannot '
                'determine whether your file object was opened in append '
                'mode.  Please consider using a file object opened in write '
                'mode instead.')
            return False

        msvcrt_dll = find_msvcrt()
        if msvcrt_dll is None:
            # If for some reason the C runtime can't be located then we're dead
            # in the water.  Just return a dummy function
            return _dummy_is_append_mode

        msvcrt = cdll.LoadLibrary(msvcrt_dll)


        # Constants
        IOINFO_L2E = 5
        IOINFO_ARRAY_ELTS = 1 << IOINFO_L2E
        IOINFO_ARRAYS = 64
        FAPPEND = 0x20
        _NO_CONSOLE_FILENO = -2


        # Types
        intptr_t = POINTER(c_int)

        class my_ioinfo(Structure):
            _fields_ = [('osfhnd', intptr_t),
                        ('osfile', c_char)]

        # Functions
        _msize = msvcrt._msize
        _msize.argtypes = (c_void_p,)
        _msize.restype = c_size_t

        # Variables
        # Since we don't know how large the ioinfo struct is just treat the
        # __pioinfo array as an array of byte pointers
        __pioinfo = cast(msvcrt.__pioinfo, POINTER(POINTER(c_char)))

        # Determine size of the ioinfo struct; see the comment above where
        # _sizeof_ioinfo = None is set
        global _sizeof_ioinfo
        if __pioinfo[0] is not None:
            _sizeof_ioinfo = _msize(__pioinfo[0]) // IOINFO_ARRAY_ELTS

        if not _sizeof_ioinfo:
            # This shouldn't happen, but I suppose it could if one is using a
            # broken msvcrt, or just happened to have a dll of the same name
            # lying around.
            return _dummy_is_append_mode

        def _is_append_mode(fd):
            global _sizeof_ioinfo
            if fd != _NO_CONSOLE_FILENO:
                idx1 = fd >> IOINFO_L2E # The index into the __pioinfo array
                # The n-th ioinfo pointer in __pioinfo[idx1]
                idx2 = fd & ((1 << IOINFO_L2E) - 1)
                if 0 <= idx1 < IOINFO_ARRAYS and __pioinfo[idx1] is not None:
                    # Doing pointer arithmetic in ctypes is irritating
                    pio = c_void_p(cast(__pioinfo[idx1], c_void_p).value +
                                   idx2 * _sizeof_ioinfo)
                    ioinfo = cast(pio, POINTER(my_ioinfo)).contents
                    return bool(ord(ioinfo.osfile) & FAPPEND)
            return False

        return _is_append_mode

    _is_append_mode_platform = _make_is_append_mode()
    del _make_is_append_mode
else:
    import fcntl

    def _is_append_mode_platform(fd):
        return bool(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_APPEND)


def fileobj_is_binary(f):
    """
    Returns True if the give file or file-like object has a file open in binary
    mode.  When in doubt, returns True by default.
    """

    # This is kind of a hack for this to work correctly with _File objects,
    # which, for the time being, are *always* binary
    if hasattr(f, 'binary'):
        return f.binary

    if io is not None and isinstance(f, io.TextIOBase):
        return False

    mode = fileobj_mode(f)
    if mode:
        return 'b' in mode
    else:
        return True


def translate(s, table, deletechars):
    """
    This is a version of string/unicode.translate() that can handle string or
    unicode strings the same way using a translation table made with
    string.maketrans.
    """

    if isinstance(s, str):
        return s.translate(table, deletechars)
    elif isinstance(s, text_type):
        table = dict((x, ord(table[x])) for x in range(256)
                     if ord(table[x]) != x)
        for c in deletechars:
            table[ord(c)] = None
        return s.translate(table)


def indent(s, shift=1, width=4):
    indented = '\n'.join(' ' * (width * shift) + l if l else ''
                         for l in s.splitlines())
    if s[-1] == '\n':
        indented += '\n'

    return indented


def fill(text, width, *args, **kwargs):
    """
    Like :func:`textwrap.wrap` but preserves existing paragraphs which
    :func:`textwrap.wrap` does not otherwise handle well.  Also handles section
    headers.
    """

    paragraphs = text.split('\n\n')

    def maybe_fill(t):
        if all(len(l) < width for l in t.splitlines()):
            return t
        else:
            return textwrap.fill(t, width, *args, **kwargs)

    return '\n\n'.join(maybe_fill(p) for p in paragraphs)


# On MacOS X 10.8 and earlier, there is a bug that causes numpy.fromfile to
# fail when reading over 2Gb of data. If we detect these versions of MacOS X,
# we can instead read the data in chunks. To avoid performance penalties at
# import time, we defer the setting of this global variable until the first
# time it is needed.
CHUNKED_FROMFILE = None

def _array_from_file(infile, dtype, count, sep):
    """Create a numpy array from a file or a file-like object."""

    if isfile(infile):

        global CHUNKED_FROMFILE
        if CHUNKED_FROMFILE is None:
            if sys.platform == 'darwin' and LooseVersion(platform.mac_ver()[0]) < LooseVersion('10.9'):
                CHUNKED_FROMFILE = True
            else:
                CHUNKED_FROMFILE = False

        if CHUNKED_FROMFILE:
            chunk_size = int(1024 ** 3 / dtype.itemsize)  # 1Gb to be safe
            if count < chunk_size:
                return np.fromfile(infile, dtype=dtype, count=count, sep=sep)
            else:
                array = np.empty(count, dtype=dtype)
                for beg in range(0, count, chunk_size):
                    end = min(count, beg + chunk_size)
                    array[beg:end] = np.fromfile(infile, dtype=dtype, count=end - beg, sep=sep)
                return array
        else:
            return np.fromfile(infile, dtype=dtype, count=count, sep=sep)
    else:
        # treat as file-like object with "read" method; this includes gzip file
        # objects, because numpy.fromfile just reads the compressed bytes from
        # their underlying file object, instead of the decompressed bytes
        read_size = np.dtype(dtype).itemsize * count
        s = infile.read(read_size)
        return np.fromstring(s, dtype=dtype, count=count, sep=sep)


_OSX_WRITE_LIMIT = (2 ** 32) - 1
_WIN_WRITE_LIMIT = (2 ** 31) - 1

def _array_to_file(arr, outfile):
    """
    Write a numpy array to a file or a file-like object.

    Parameters
    ----------
    arr : `~numpy.ndarray`
        The Numpy array to write.
    outfile : file-like
        A file-like object such as a Python file object, an `io.BytesIO`, or
        anything else with a ``write`` method.  The file object must support
        the buffer interface in its ``write``.

    If writing directly to an on-disk file this delegates directly to
    `ndarray.tofile`.  Otherwise a slower Python implementation is used.
    """


    if isfile(outfile):
        write = lambda a, f: a.tofile(f)
    else:
        write = _array_to_file_like

    # Implements a workaround for a bug deep in OSX's stdlib file writing
    # functions; on 64-bit OSX it is not possible to correctly write a number
    # of bytes greater than 2 ** 32 and divisible by 4096 (or possibly 8192--
    # whatever the default blocksize for the filesystem is).
    # This issue should have a workaround in Numpy too, but hasn't been
    # implemented there yet: https://github.com/astropy/astropy/issues/839
    #
    # Apparently Windows has its own fwrite bug:
    # https://github.com/numpy/numpy/issues/2256

    if (sys.platform == 'darwin' and arr.nbytes >= _OSX_WRITE_LIMIT + 1 and
            arr.nbytes % 4096 == 0):
        # chunksize is a count of elements in the array, not bytes
        chunksize = _OSX_WRITE_LIMIT // arr.itemsize
    elif sys.platform.startswith('win'):
        chunksize = _WIN_WRITE_LIMIT // arr.itemsize
    else:
        # Just pass the whole array to the write routine
        return write(arr, outfile)

    # Write one chunk at a time for systems whose fwrite chokes on large
    # writes.
    idx = 0
    arr = arr.view(type=np.ndarray).flatten()
    while idx < arr.nbytes:
        write(arr[idx:idx + chunksize], outfile)
        idx += chunksize


def _array_to_file_like(arr, fileobj):
    """
    Write a `~numpy.ndarray` to a file-like object (which is not supported by
    `numpy.ndarray.tofile`).
    """

    if arr.flags.contiguous:
        # It suffices to just pass the underlying buffer directly to the
        # fileobj's write (assuming it supports the buffer interface, which
        # unfortunately there's no simple way to check)
        fileobj.write(arr.data)
    elif hasattr(np, 'nditer'):
        # nditer version for non-contiguous arrays
        for item in np.nditer(arr):
            fileobj.write(item.tostring())
    else:
        # Slower version for Numpy versions without nditer;
        # The problem with flatiter is it doesn't preserve the original
        # byteorder
        byteorder = arr.dtype.byteorder
        if ((sys.byteorder == 'little' and byteorder == '>')
                or (sys.byteorder == 'big' and byteorder == '<')):
            for item in arr.flat:
                fileobj.write(item.byteswap().tostring())
        else:
            for item in arr.flat:
                fileobj.write(item.tostring())


def _write_string(f, s):
    """
    Write a string to a file, encoding to ASCII if the file is open in binary
    mode, or decoding if the file is open in text mode.
    """

    # Assume if the file object doesn't have a specific mode, that the mode is
    # binary
    binmode = fileobj_is_binary(f)

    if binmode and isinstance(s, text_type):
        s = encode_ascii(s)
    elif not binmode and not isinstance(f, text_type):
        s = decode_ascii(s)
    elif isinstance(f, StringIO) and isinstance(s, np.ndarray):
        # Workaround for StringIO/ndarray incompatibility
        s = s.data
    f.write(s)


def _convert_array(array, dtype):
    """
    Converts an array to a new dtype--if the itemsize of the new dtype is
    the same as the old dtype and both types are not numeric, a view is
    returned.  Otherwise a new array must be created.
    """

    if array.dtype == dtype:
        return array
    elif (array.dtype.itemsize == dtype.itemsize and not
            (np.issubdtype(array.dtype, np.number) and
             np.issubdtype(dtype, np.number))):
        # Includes a special case when both dtypes are at least numeric to
        # account for ticket #218: https://aeon.stsci.edu/ssb/trac/pyfits/ticket/218
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
    return isinstance(val, integer_types + (np.integer,))


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


def _words_group(input, strlen):
    """
    Split a long string into parts where each part is no longer
    than `strlen` and no word is cut into two pieces.  But if
    there is one single word which is longer than `strlen`, then
    it will be split in the middle of the word.
    """

    words = []
    nblanks = input.count(' ')
    nmax = max(nblanks, len(input) // strlen + 1)
    arr = np.fromstring((input + ' '), dtype=(binary_type, 1))

    # locations of the blanks
    blank_loc = np.nonzero(arr == ' '.encode('latin1'))[0]
    offset = 0
    xoffset = 0
    for idx in range(nmax):
        try:
            loc = np.nonzero(blank_loc >= strlen + offset)[0][0]
            offset = blank_loc[loc - 1] + 1
            if loc == 0:
                offset = -1
        except:
            offset = len(input)

        # check for one word longer than strlen, break in the middle
        if offset <= xoffset:
            offset = xoffset + strlen

        # collect the pieces in a list
        words.append(input[xoffset:offset])
        if len(input) == offset:
            break
        xoffset = offset

    return words


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


def _get_array_mmap(array):
    """
    If the array has an mmap.mmap at base of its base chain, return the mmap
    object; otherwise return None.
    """

    if isinstance(array, mmap.mmap):
        return array

    base = array
    while hasattr(base, 'base') and base.base is not None:
        if isinstance(base.base, mmap.mmap):
            return base.base
        base = base.base
