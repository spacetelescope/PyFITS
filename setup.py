#!/usr/bin/env python

from __future__ import division # confidence high

import os
import string
import StringIO
import logging

# Configure the logger to write message to a string buffer.
# This will allow the messages to be output at the end of
# the setup process.
logging.basicConfig(level=logging.WARNING)
finalMessages = StringIO.StringIO()
console = logging.StreamHandler(finalMessages)
logging.getLogger('').addHandler(console)

# We use the local copy of stsci_distutils_hack, unless
# the user asks for the stpytools version
if os.getenv("USE_STPYTOOLS") :
    import pytools.stsci_distutils_hack as H
    pytools_version = "3.0"
else :
    import stsci_distutils_hack as H
    pytools_version = None

H.run(pytools_version = pytools_version)

# Output any warnings issued during the processing.
if finalMessages.getvalue() != '':
    print ""

    s = string.split(finalMessages.getvalue(),'\n')

    for i in range(len(s)):

        if i == 0:
            print "WARNING: %s" % (s[i])
        else:
            print "         %s" % (s[i])


