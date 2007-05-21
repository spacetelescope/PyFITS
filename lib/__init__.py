#This is the configuration file for the pyfits namespace.  This is needed
#because we have the option of using either a numarray or numpy version
#of pyfits.

#This option is controlled by the NUMERIX environment variable.  Set NUMERIX 
#to 'numarray' for the numarray version of pyfits.  Set NUMERIX to 'numpy'
#for the numpy version of pyfits.

#If only one array package is installed, that package's version of pyfits
#will be imported.  If both packages are installed the NUMERIX value is
#used to decide between the packages.  If no NUMERIX value is set then 
#the numarray version of pyfits will be imported.

#Anything else is an exception.

import os

__version__ = '1.1rc4'

# Check the environment variables for NUMERIX
try:
    numerix = os.environ["NUMERIX"]
except:
    numerix = 'numpy'

# Deteremine if numarray is installed on the system
try:
    import numarray
    numarraystatus = True
except:
    numarraystatus = False

# Determine if numpy is installed on the system
try:
    import numpy
    numpystatus = True
except:
    numpystatus = False


if (numpystatus and numarraystatus):
    # if both array packages are installed, use the NUMERIX environment
    # variable to break the tie.  If NUMERIX doesn't exist, default
    # to numarray
    if numerix == 'numpy':
        from NP_pyfits import *
        import NP_pyfits as core
        __doc__ = NP_pyfits.__doc__
    else:
        from NA_pyfits import *
        import NA_pyfits as core
        __doc__ = NA_pyfits.__doc__
        
elif (numpystatus):
    # if only numpy is installed use the numpy version of pyfits
    from NP_pyfits import *
    import NP_pyfits as core
    __doc__ = NP_pyfits.__doc__

elif (numarraystatus):
    # if only numarray is installed use the numarray version of pyfits
    from NA_pyfits import *
    import NA_pyfits as core
    __doc__ = NA_pyfits.__doc__

else:
    raise RuntimeError, "The numarray or numpy array package is required for use."

_locals = locals().keys()
for n in _locals[::-1]:
    if n[0] == '_' or n in ('re', 'os', 'tempfile', 'exceptions', 'operator', 'num', 'ndarray', 'chararray', 'rec', 'objects', 'Memmap', 'maketrans', 'open'):
        _locals.remove(n)
__all__ = _locals
