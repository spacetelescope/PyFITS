Documentation
===============
See the Users Guide and API documentation hosted at
http://packages.python.org/pyfits.

Development
=============
PyFITS has a Trac site used for development at:
https://trac6.assembla.com/pyfits

All issue numbers mentioned in the changelog (#n) refer to ticket numbers in
Trac.  To report an issue in PyFITS, send an e-mail to help@stsci.edu.

The latest source code can be checked out from SVN with::

 svn checkout https://svn6.assembla.com/svn/pyfits/trunk

For Packagers
===============
As of version 3.2.0 PyFITS supports use of the standard CFITSIO library for
compression support.  A minimal copy of CFITSIO is included in the PyFITS
source under cextern/cfitsio.  Packagers wishing to link with an existing
system CFITSIO remove this directory and modify the setup.cfg as instructed
by the comments in that file.  CFITSIO support has been tested for versions
3.08 through 3.30.  The earliers known fully working version is 3.09.  Version
3.08 mostly works except for a bug in CFITSIO itself when decompressing some
images with BITPIX=-64.  Earlier versions *may* work but YMMV.  Please send in
any results of experimentation with other CFITSIO versions.
