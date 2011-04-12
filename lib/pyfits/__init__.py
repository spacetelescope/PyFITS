#This is the configuration file for the pyfits namespace.

from __future__ import division # confidence high

# I've seen one example of code that's using datetime from pyfits;
# That code should be fixed, but in the meantime this is here for
# compatibility
import datetime

# Define the version of the pyfits package.
try:
    from pyfits import svn_version
    __svn_version__ = svn_version.__svn_version__
except ImportError:
    __svn_version__ = 'Unable to determine SVN revision'

__version__ = '2.4.0' + __svn_version__

# Import the pyfits core module.
import pyfits.core
import pyfits.util
from pyfits.core import *
from pyfits.util import *

__doc__ = pyfits.core.__doc__

__all__ = pyfits.core.__all__ + pyfits.util.__all__

try:
    import pytools.tester
    def test(*args,**kwds):
        pytools.tester.test(modname=__name__, *args, **kwds)
except ImportError:
    pass

