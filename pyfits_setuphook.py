# This module is actually part of the stsci_python.pytools package, but it's
# included with PyFITS for now.

import sys

try:
    from distutils2.util import strtobool
except ImportError:
    from distutils.util import strtobool


def is_display_option():
    """A hack to test if one of the arguments passed to setup.py is a display
    argument that should just display a value and exit.  If so, don't bother
    running this hook (this capability really ought to be included with
    distutils2).
    """

    from setuptools.dist import Distribution

    # If there were no arguments in argv (aside from the script name) then this
    # is an implied display opt
    if len(sys.argv) < 2:
        return True

    display_opts = ['--command-packages']

    for opt in Distribution.global_options:
        if opt[0]:
            display_opts.append('--' + opt[0])
        if opt[1]:
            display_opts.append('-' + opt[1])

    for opt in Distribution.display_options:
        display_opts.append('--' + opt[0])

    for arg in sys.argv:
        if arg in display_opts:
            return True

    return False


def numpy_extension_hook(config):
    """A distutils2 setup_hook needed for building extension modules that use
    NumPy.

    To use this hook, add 'requires_numpy = True' to the setup.cfg section for
    an extension module.  This hook will add the necessary numpy header paths
    to the include_dirs option.
    """

    if is_display_option():
        return

    try:
        import numpy
    except ImportError:
        # It's virtually impossible to automatically install numpy through
        # setuptools; I've tried.  It's not pretty.
        # Besides, we don't want users complaining that our software doesn't
        # work just because numpy didn't build on their system.
        sys.stderr.write('\n\nNumpy is required to build this package.\n'
                         'Please install Numpy on your system first.\n\n')
        sys.exit(1)

    includes = [numpy.get_include(), numpy.get_numarray_include()]
    for section in config:
        if not section.startswith('extension='):
            continue
        options = config[section]
        key = 'requires_numpy'
        if key in options and strtobool(options[key]):
            del options[key]
            if 'include_dirs' in options:
                option = options['include_dirs']
                for include in includes:
                    if include not in option:
                        # Have to manipulate the option as a raw string, as it
                        # has not been split into a list at this point
                        option += '\n' + include
                options['include_dirs'] = option
            else:
                options['include_dirs'] = '\n'.join(includes)
