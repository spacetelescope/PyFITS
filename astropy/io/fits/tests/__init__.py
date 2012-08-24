from __future__ import division  # confidence high

import os
import shutil
import tempfile
import warnings

import pyfits


class PyfitsTestCase(object):
    def setup(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.temp_dir = tempfile.mkdtemp(prefix='pyfits-test-')

        # Restore global settings to defaults
        for name, value in pyfits.core.GLOBALS:
            setattr(pyfits, name, value)

        # Ignore deprecation warnings--this only affects Python 2.5 and 2.6,
        # since deprecation warnings are ignored by defualt on 2.7
        warnings.simplefilter('ignore', DeprecationWarning)

    def teardown(self):
        shutil.rmtree(self.temp_dir)

    def data(self, filename):
        return os.path.join(self.data_dir, filename)

    def temp(self, filename):
        return os.path.join(self.temp_dir, filename)
