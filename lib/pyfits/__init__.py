#This is the configuration file for the pyfits namespace.

from __future__ import division # confidence high

try:
    from pyfits.version import __version__
except:
    __version__ = ''

# Import the pyfits core module.
import pyfits.core
from pyfits.core import *
from pyfits.util import *

__doc__ = pyfits.core.__doc__

__all__ = pyfits.core.__all__


try:
    import stsci.tools.tester
    def test(*args,**kwds):
        stsci.tools.tester.test(modname=__name__, *args, **kwds)
except ImportError:
    pass

