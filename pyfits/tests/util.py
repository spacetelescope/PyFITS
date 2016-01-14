"""Test utility functions."""

from __future__ import with_statement

import functools
import sys
import warnings

from ..extern.six import StringIO


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


class ignore_warnings(warnings.catch_warnings):
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
