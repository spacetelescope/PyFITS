from __future__ import division  # confidence high

import os
import shutil
import stat
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
        warnings.resetwarnings()
        warnings.simplefilter('ignore')
        warnings.simplefilter('always', UserWarning)

    def teardown(self):
        shutil.rmtree(self.temp_dir)

    def copy_file(self, filename):
        """Copies a backup of a test data file to the temp dir and sets its
        mode to writeable.
        """

        shutil.copy(self.data(filename), self.temp(filename))
        os.chmod(self.temp(filename), stat.S_IREAD | stat.S_IWRITE)

    def data(self, filename):
        """Returns the path to a test data file."""

        return os.path.join(self.data_dir, filename)

    def temp(self, filename):
        """ Returns the full path to a file in the test temp dir."""

        return os.path.join(self.temp_dir, filename)
