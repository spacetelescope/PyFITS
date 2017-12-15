---------------------------
Important notice for PyFITS
---------------------------

**PyFITS is deprecated and no longer supported! This repo is
archived.**

All of the functionality of PyFITS is available in `Astropy
<http://www.astropy.org>`_ as the `astropy.io.fits
<http://docs.astropy.org/en/stable/io/fits/index.html>`_ package.
We will NOT be releasing new versions of PyFITS as
a stand-alone product.

--------------------
ARCHIVAL INFORMATION
--------------------

Documentation
=============
See the Users Guide and API documentation hosted at
http://pythonhosted.org/pyfits.

Development
===========
PyFITS is now on GitHub at:
https://github.com/spacetelescope/PyFITS

To report an issue in PyFITS, please create an account on GitHub and submit
the issue there, or send an e-mail to help@stsci.edu.  Before submitting an
issue please search the existing issues for similar problems.  Before asking
for help, please check the PyFITS FAQ for answers to your questions:
http://pythonhosted.org/pyfits/appendix/faq.html

The latest source code can be checked out from git with::

  git clone https://github.com/spacetelescope/PyFITS.git

An SVN mirror is still maintained as well::

  svn checkout https://aeon.stsci.edu/ssb/svn/pyfits/trunk

For Packagers
=============
As of version 3.2.0 PyFITS supports use of the standard CFITSIO library for
compression support.  A minimal copy of CFITSIO is included in the PyFITS
source under cextern/cfitsio.  Packagers wishing to link with an existing
system CFITSIO remove this directory and modify the setup.cfg as instructed
by the comments in that file.  CFITSIO support has been tested for versions
3.08 through 3.30.  The earliers known fully working version is 3.09.  Version
3.08 mostly works except for a bug in CFITSIO itself when decompressing some
images with BITPIX=-64.  Earlier versions *may* work but YMMV.  Please send in
any results of experimentation with other CFITSIO versions.
