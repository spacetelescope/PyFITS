#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup


setup(
    setup_requires=['d2to1>=0.2.5', 'stsci.distutils>=0.2.1'],
    entry_points={
        'zest.releaser.prereleaser.before': [
            'pyfits.prereleaser.before = '
                'pyfits._release:releaser.prereleaser_before'
        ],
        'zest.releaser.prereleaser.after': [
            'pyfits.prereleaser.after = '
                'pyfits._release:releaser.prereleaser_after'
        ],
        'zest.releaser.postreleaser.before': [
            'pyfits.postreleaser.before = '
                'pyfits._release:releaser.postreleaser_before'
        ],
        'zest.releaser.postreleaser.middle': [
            'pyfits.postreleaser.middle = '
                'pyfits._release:releaser.postreleaser_middle'
        ],
        'zest.releaser.postreleaser.after': [
            'pyfits.postreleaser.after = '
                'pyfits._release:releaser.postreleaser_after'
        ]
    },
    d2to1=True,
    use_2to3=True,
    zip_safe=False
)
