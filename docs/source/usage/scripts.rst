******************
Executable Scripts
******************

PyFITS installs a couple of useful utility programs on your system that are
built with PyFITS.

fitsinfo
^^^^^^^^
.. automodule:: pyfits.scripts.fitsinfo

fitsheader
^^^^^^^^^^
.. automodule:: pyfits.scripts.fitsheader

fitscheck
=========
.. automodule:: pyfits.scripts.fitscheck

.. program-output:: fitscheck --help

.. _fitsdiff:

fitsdiff
========

.. currentmodule:: pyfits

``fitsdiff`` provides a thin command-line wrapper around the :class:`FITSDiff`
interface--it outputs the report from a :class:`FITSDiff` of two FITS files,
and like common diff-like commands returns a 0 status code if no differences
were found, and 1 if differences were found:

.. program-output:: fitsdiff --help
