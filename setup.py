#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

setup(
    # Don't require stsci.tools until the stsci_python refactoring is closer
    # to being available
    #setup_requires=['d2to1', 'stsci.tools>=2.9'],
    setup_requires=['d2to1'],
    d2to1=True,
    use_2to3=True
)
