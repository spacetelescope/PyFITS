# This is the configuration file for the pyfits namespace.

from __future__ import division  # confidence high

# Delete any existing pyfits subpackages from sys.modules;
# This is a hack specifically to work with ./setup.py nosetests:
# When running setup.py, python gets imported from the source checkout during
# the build process. ./setup.py nosetests, however, runs the 'build' command
# and then tries to import pyfits from out of the 'build/' directory.  Since
# pyfits has already been partially imported from 'lib/' this leads to
# confusion.
# nose already attempts to handle this case, but it only works on single
# modules; it fails to delete any *submodules* that are already in sys.modules.
# This should be considered a bug in nose.
import sys
if 'pyfits' in sys.modules:
    for kw in [kw for kw in sys.modules if kw.startswith('pyfits.')]:
        del sys.modules[kw]

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

