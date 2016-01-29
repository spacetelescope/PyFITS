import sys


def py2_only_hook(config):
    """
    d2to1 setup hook to prevent any packages ending with _py2 from
    being installed on Python 3.
    """

    from d2to1.util import split_multiline

    if sys.version_info[0] > 2:
        files = config['files']
        packages = split_multiline(files['packages'])
        packages = [p for p in packages if not p.endswith('_py2')]
        files['packages'] = '\n'.join(packages)
