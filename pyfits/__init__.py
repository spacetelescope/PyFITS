# This is the configuration file for the pyfits namespace.

from __future__ import division  # confidence high

try:
    from .version import __version__
except:
    __version__ = ''

# Import the pyfits core module.
from . import core

# Relative imports of * are not syntactically valid in Python 2.5
from pyfits.core import *
from pyfits.util import *

__doc__ = core.__doc__

__all__ = core.__all__


try:
    import stsci.tools.tester

    def test(*args, **kwds):
        stsci.tools.tester.test(modname=__name__, *args, **kwds)
except ImportError:
    pass
