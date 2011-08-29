import datetime
import getpass
import logging
import os
import re
import sys
import xmlrpclib

try:
    from docutils.core import publish_parts
except ImportError:
    print >> sys.stderr, \
           'docutils is required to convert the PyFITS changelog to HTML ' \
           'for updating the PyFITS homepage\n\n' \
           'Try `pip install docutils` or `easy_install docutils`.'
    sys.exit(1)

from zest.releaser.choose import version_control
from zest.releaser.utils import get_last_tag, ask


PYFITS_HOMEPAGE_BASE_URL = \
    'http://www.stsci.edu/resources/software_hardware/pyfits'
# These are the pages to run find/replace of the version number on
PYFITS_HOMEPAGE_SUBPAGES = ['localProductDescription', 'Download']

# The website will only have final release up on it, so we can use a simplified
# version regexp
VERSION_RE = re.compile(r'(?P<MAJOR>\d+)\.(?P<MINOR>\d+)(?:\.(?P<MICRO>\d+))?')

# This is the format used to search for/replace the previous version
# This is based on simply a manual analysis of where the PyFITS version number
# appears on the website; note that the version alone shouldn't be used since
# other version strings (i.e. Python versions) can appear on the site
# NOTE: The MICRO version number is appended to the format later, since it is
# optional if the micro format is 0
SEARCH_VERSION_RE_FORMAT = (r'(?P<prefix>v|V|[vV]ersion\s+|pyfits-)'
                             '%(major)s\.%(minor)s(?:\s*\((?P<date>.+)\))?')

DATE_FORMAT = '%B %d %Y'


class ReleaseManager(object):
    def __init__(self):
        self.vcs = version_control()
        self.history_lines = []
        self.previous_version = ''

    def prereleaser_after(self, data):
        """Before preforming the release, get the previously released version
        from the latest tag in version control.
        """

        if data['name'] != 'pyfits':
            return

        self.previous_version = get_last_tag(self.vcs)
        self.history_lines = data['history_lines']

    def postreleaser_after(self, data):
        """Used to update the PyFITS website.

        TODO: If at any point we get a Windows build machine that we can remote
        into, use this as a point to create Windows builds as well.
        """

        log = logging.getLogger('postrelease')

        if data['name'] != 'pyfits':
            return

        if not ask('Update PyFITS homepage'):
            return


        previous_version = raw_input(
            'Enter previous version [%s]: ' % self.previous_version).strip()
        if not previous_version:
            previous_version = self.previous_version

        new_version = raw_input(
            'Enter new version [%s]: ' % data['new_version']).strip()
        if not new_version:
            new_version = data['new_version']

        username = raw_input(
                'Enter your Zope username [%s]: ' % getpass.getuser()).strip()
        if not username:
            username = getpass.getuser()

        password = getpass.getpass(
            'Enter your Zope password (password will not be displayed): ')

        match = VERSION_RE.match(previous_version)
        if not match:
            log.error('Previous version (%s) is invalid: Version must be in '
                      'the MAJOR.MINOR[.MICRO] format.' % previous_version)
            sys.exit()

        micro = int(match.group('MICRO')) if match.group('MICRO') else 0

        previous_version = (int(match.group('MAJOR')),
                            int(match.group('MINOR')), micro)

        match = VERSION_RE.match(new_version)
        if not match:
            log.error('New version (%s) is invalid: Version must be in '
                      'the MAJOR.MINOR[.MICRO] format.' % new_version)
            sys.exit()

        micro = int(match.group('MICRO')) if match.group('MICRO') else 0

        new_version = (int(match.group('MAJOR')), int(match.group('MINOR')),
                       micro)

        # This is the regular expression to search for version replacement
        format_args = {'major': str(previous_version[0]),
                       'minor': str(previous_version[1])}
        if previous_version[2] != 0:
            # Append the micro version after the minor version if nonzero
            format_args['minor'] += r'\.%d' % previous_version[2]
        search_version_re = re.compile(SEARCH_VERSION_RE_FORMAT % format_args)

        new_version_str = '.'.join((str(new_version[0]), str(new_version[1])))
        if new_version[2] != 0:
            new_version_str += '.%d' % new_version[2]

        basic_auth = ':'.join((username, password))

        def version_replace(match):
            repl = match.group('prefix') + new_version_str
            if match.group('date'):
                today = datetime.datetime.today().strftime(DATE_FORMAT)
                repl += ' (%s)' % today
            return repl

        # Go ahead and do the find/replace on supported subpages
        for page in PYFITS_HOMEPAGE_SUBPAGES:
            proto, rest = PYFITS_HOMEPAGE_BASE_URL.split('://', 1)
            url = '%s://%s@%s/%s' % (proto, basic_auth, rest, page)
            try:
                log.info('Updating %s...' % url)
                proxy = xmlrpclib.ServerProxy(url)
                content = proxy.document_src()
                content = search_version_re.sub(version_replace, content)
                proxy.manage_upload(content)
            except Exception, e:
                # Lots of things could go wrong here; maybe some specific
                # exceptions could be caught and dealt with if they turn out to
                # be common for some reason
                # TODO: Catch bad authentication and let the user enter a new
                # username/password
                # Display a url with password hidden
                url = '%s://%s:********@%s/%s' % (proto, username, rest, page)
                log.error('Failed to update %s: %s' % (url, str(e)))

        # Update the release notes
        # TODO: This little routine should maybe be a function or something
        proto, rest = PYFITS_HOMEPAGE_BASE_URL.split('://', 1)
        url = '%s://%s@%s/%s' % (proto, basic_auth, rest, 'release')
        try:
            log.info('Updating %s...' % url)
            parts = publish_parts('\n'.join(self.history_lines),
                                  writer_name='html')
            # Get just the body of the HTML and convert headers to <h3> tags
            # instead of <h1> (there might be a 'better' way to do this, but
            # this is a simple enough case to suffice for our purposes
            content = parts['html_body']
            # A quickie regexp--no good for general use, but should work fine
            # in this case; this will prevent replacement of the <h1> tag in
            # the title, but will take care of all the others
            content = re.sub(r'<h1>([^<]+)</h1>', r'<h3>\1</h3>', content)

            # And upload...
            proxy = xmlrpclib.ServerProxy(url)
            proxy.manage_upload(content)
        except Exception, e:
            url = '%s://%s:********@%s/%s' % (proto, username, rest, page)
            log.error('Failed to update %s: %s' % (url, str(e)))


releaser = ReleaseManager()
