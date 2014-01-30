************
Introduction
************

The PyFITS module is a Python library providing access to FITS files. FITS
(Flexible Image Transport System) is a portable file standard widely used in
the astronomy community to store images and tables.


Installation
============

PyFITS requires Python version 2.5 or newer. PyFITS also requires the numpy
package. Information about numpy can be found at:

    http://numpy.scipy.org/

To download numpy, go to:

    http://sourceforge.net/project/numpy

PyFITS' source code is mostly pure Python, but includes an optional C module
which wraps CFITSIO for compression support.  The latest source distributions
and binary installers for Windows can be downloaded from:

    http://www.stsci.edu/resources/software_hardware/pyfits/Download

Or from the Python Package Index (PyPI) at:

    https://pypi.python.org/pypi/pyfits

PyFITS uses Python's distutils for its installation. To install it, unpack the
tar file and type:

.. parsed-literal::

    python setup.py install

This will install PyFITS in the system's Python site-packages directory. If
your system permissions do not allow this kind of installation, use of
`virtualenv <http://www.virtualenv.org>`_ for personal installations is
recommended.

In this guide, we'll assume that the reader has basic familiarity with Python.
Familiarity with numpy is not required, but it will help to understand the data
structures in PyFITS.


User Support
============

The official PyFITS web page is:

    http://www.stsci.edu/resources/software_hardware/pyfits

If you have any question or comment regarding PyFITS, user support is available
through the STScI Help Desk:

.. parsed-literal::

    \* **E-mail:** help@stsci.edu
    \* **Phone:** (410) 338-1082
