Documentation
===============
See the Users Guide and API documentation hosted at
http://packages.python.org/pyfits.

Important notice regarding the future of PyFITS
===============================================

All of the functionality of PyFITS is now available in `Astropy
<http://www.astropy.org>`_ as the `astropy.io.fits
<http://docs.astropy.org/en/stable/io/fits/index.html>`_ package, which is now
publicly available. Although we will continue to release PyFITS separately in
the short term, including any critical bug fixes, we will eventually stop
releasing new versions of PyFITS as a stand-alone product. The exact timing of
when we will discontinue new PyFITS releases is not yet settled, but users
should not expect PyFITS releases to extend much past early 2014. Users of
PyFITS should plan to make suitable changes to support the transition to
Astropy on such a timescale. For the vast majority of users this transition is
mainly a matter of changing the import statements in their code--all APIs are
otherwise identical to PyFITS.  STScI will continue to provide support for
questions related to PyFITS and to the new ``astropy.io.fits package`` in
Astropy.

Development
=============
PyFITS has a Trac site used for development at:
https://trac6.assembla.com/pyfits

All issue numbers mentioned in the changelog (#n) refer to ticket numbers in
Trac.  To report an issue in PyFITS, send an e-mail to help@stsci.edu.

The latest source code can be checked out from SVN with::

 svn checkout https://svn6.assembla.com/svn/pyfits/trunk
