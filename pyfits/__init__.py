# This is the configuration file for the pyfits namespace.

from __future__ import division

try:
    from .version import __version__
except:
    __version__ = ''

# Import the pyfits core module.
from . import core
from .core import *
from .util import *

__doc__ = core.__doc__

__all__ = core.__all__


try:
    import stsci.tools.tester

    def test(*args, **kwds):
        stsci.tools.tester.test(modname=__name__, *args, **kwds)
except ImportError:
    pass
