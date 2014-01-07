"""Test utility functions."""

from __future__ import with_statement

import functools
import sys
import warnings

from pyfits.util import StringIO


class CaptureStdio(object):
    """
    A simple context manager for redirecting stdout and stderr to a StringIO
    buffer.
    """

    def __init__(self, stdout=True, stderr=True):
        self.stdout = StringIO()
        self.stderr = StringIO()

    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        return self.stdout, self.stderr

    def __exit__(self, *args, **kwargs):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self.stdout.close()
        self.stderr.close()


if hasattr(warnings, 'catch_warnings'):
    catch_warnings = warnings.catch_warnings
else:
    # For Python2.5, backport the catch_warnings context manager
    class WarningMessage(object):

        """Holds the result of a single showwarning() call."""

        _WARNING_DETAILS = ("message", "category", "filename", "lineno",
                            "file", "line")

        def __init__(self, message, category, filename, lineno, file=None,
                     line=None):
            local_values = locals()
            for attr in self._WARNING_DETAILS:
                setattr(self, attr, local_values[attr])
            self._category_name = category.__name__ if category else None

        def __str__(self):
            return ("{message : %r, category : %r, filename : %r, lineno : %s,"
                    " line : %r}" % (self.message, self._category_name,
                                     self.filename, self.lineno, self.line))

    class catch_warnings(object):

        """A context manager that copies and restores the warnings filter upon
        exiting the context.

        The 'record' argument specifies whether warnings should be captured by
        a custom implementation of warnings.showwarning() and be appended to a
        list returned by the context manager. Otherwise None is returned by the
        context manager. The objects appended to the list are arguments whose
        attributes mirror the arguments to showwarning().

        The 'module' argument is to specify an alternative module to the module
        named 'warnings' and imported under that name. This argument is only
        useful when testing the warnings module itself.

        """

        def __init__(self, record=False, module=None):
            """Specify whether to record warnings and if an alternative module
            should be used other than sys.modules['warnings'].

            For compatibility with Python 3.0, please consider all arguments to
            be keyword-only.

            """
            self._record = record
            self._module = (sys.modules['warnings']
                            if module is None else module)
            self._entered = False

        def __repr__(self):
            args = []
            if self._record:
                args.append("record=True")
            if self._module is not sys.modules['warnings']:
                args.append("module=%r" % self._module)
            name = type(self).__name__
            return "%s(%s)" % (name, ", ".join(args))

        def __enter__(self):
            if self._entered:
                raise RuntimeError("Cannot enter %r twice" % self)
            self._entered = True
            self._filters = self._module.filters
            self._module.filters = self._filters[:]
            self._showwarning = self._module.showwarning
            if self._record:
                log = []

                def showwarning(*args, **kwargs):
                    log.append(WarningMessage(*args, **kwargs))

                self._module.showwarning = showwarning
                return log
            else:
                return None

        def __exit__(self, *exc_info):
            if not self._entered:
                raise RuntimeError("Cannot exit %r without entering first" %
                                   self)
            self._module.filters = self._filters
            self._module.showwarning = self._showwarning


class ignore_warnings(catch_warnings):
    """
    This can be used either as a context manager or function decorator to
    ignore all warnings that occur within a function or block of code.

    An optional category option can be supplied to only ignore warnings of a
    certain category or categories (if a list is provided).
    """

    def __init__(self, category=None):
        super(ignore_warnings, self).__init__()

        if isinstance(category, type) and issubclass(category, Warning):
            self.category = [category]
        else:
            self.category = category

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Originally this just reused self, but that doesn't work if the
            # function is called more than once so we need to make a new
            # context manager instance for each call
            with self.__class__(category=self.category):
                return func(*args, **kwargs)

        return wrapper

    def __enter__(self):
        retval = super(ignore_warnings, self).__enter__()
        if self.category is not None:
            for category in self.category:
                warnings.simplefilter('ignore', category)
        else:
            warnings.simplefilter('ignore')
        return retval
