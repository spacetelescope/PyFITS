"""This module is required to support stsci_python's build system.

This generic defsetup.py can be dropped in to any project that uses d2to1 in
order to support stsci_python integration.  From stsci_python's point of view
it will be no different from any other defsetup.py, which is required to
contain a `pkg` variable listing the Python packages in this project, and a
`setupargs` variable, containing all other arguments that would normally be
passed to a `setup()` call.
"""


import os
import sys

try:
    __file__
except NameError:
    # __file__ won't necessarily be set if this file was run with the exec
    # keyword (as is the case in stsci_python's setup.py)
    import inspect
    __file__ = inspect.currentframe().f_code.co_filename

oldcwd = os.getcwd()
os.chdir(os.path.dirname(__file__))

if '' not in sys.path:
    sys.path.insert(0, '')

try:
    try:
        from setuptools.dist import Distribution
    except ImportError:
        from distribute_setup import use_setuptools
        use_setuptools()
        from setuptools.dist import Distribution

    # Require d2to1
    Distribution(attrs={'setup_requires': 'd2to1'})

    from d2to1.util import cfg_to_args

    # This is the dict stsci_python's setup.py looks for
    setupargs = cfg_to_args()

    # It also looks for a separate list of the packages that are installed
    pkg = setupargs['packages']

    # We need to touch up the package_dir option, about which the stsci_python
    # setup.py makes certain assumptions
    package_root = setupargs['package_dir'].get('')
    if package_root:
        setupargs['package_dir'] = \
            dict((p, os.path.join(package_root, *(p.split('.'))))
                 for p in pkg)

    # Problem: Because packages built using d2to1 use setuptools, setuptools
    # patches the Extension class.  However, since the rest of stsci_python
    # does not use setuptools at all yet, the other packages use the unpackaged
    # Extension class.  This leads to silly problems when the build_ext command
    # runs (specifically, the build_ext.check_extensions_list() method does a
    # type check on Extension, but it's checking for the *patched* Extension
    # class--unpatched Extension classes fail the type check).
    #
    # Solution: It's too hard to completely unpatch distutils, but that's OK
    # because having setuptools (actually in this case distribute) in there is
    # mostly harmless.  But we still need the already created Extension objects
    # from other projects' defsetups to work, so we actually patch setuptools
    # to go back to using the original Extension class.  Serve with a side of
    # baked macaroni.

    from setuptools.dist import _get_unpatched
    from distutils.core import Extension as _Extension
    Extension = _get_unpatched(_Extension)

    import distutils.core, distutils.extension
    import setuptools, setuptools.extension
    distutils.core.Extension = Extension
    distutils.extension.Extension = Extension
    setuptools.Extension = Extension
    setuptools.extension.Extension = Extension

    if 'distutils.command.build_ext' in sys.modules:
        sys.modules['distutils.command.build_ext'].Extension = Extension

    for ext in setupargs['ext_modules']:
        ext.__class__ = Extension

    # Delicious!

finally:
    os.chdir(oldcwd)

