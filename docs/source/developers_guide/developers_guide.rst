#######################
PyFITS Developers Guide
#######################

This "developers guide" will be brief, as PyFITS will, in the near future,
be deprecated in favor of Astropy (which includes a port of PyFITS now dubbed
``astropy.io.fits``.  As such, it should be sufficient for any developers
wishing to contribute to PyFITS to look at the developer documentation for
Astropy, as much of it applies equally well.  In particular, please look at
the Astropy `Coding Guidelines`_ and the `Documentation Guidelines`_ before
getting started with any major contributions to PyFITS (don't worry if you
don't immediately absorb *everything* in those guidelines--it's just good to
be aware that they exist and have a rough understanding of how to approach the
source code).

Getting the source code
=======================

PyFITS was originally developed in SVN, but now most development has moved to
Git, primarily for ease of syncing changes to Astropy.  That said, the SVN
repository is still maintained for legacy purposes.  PyFITS' lead maintainer
at STScI will handle synchronizing the Git and SVN repositories, but the steps
for configuring git-svn are documented below for posterity.  Outside users
wishing to contribute to the source code should start with Astropy's guide to
`Contributing to Astropy`_.

The official PyFITS GitHub page is at: https://github.com/spacetelescope/pyfits

The best way to contribute to PyFITS is to create an account on GitHub, fork
your own copy of the PyFITS repository, and then make your changes in your
personal fork and make a pull request when they are ready to share.  The entire
process is described in Astropy's `Workflow for Developers`_ document.  That
documention was written for Astropy, but applies all the same to PyFITS.
Just replace any instance of ``astropy/astropy.git`` with
``spacetelescope/PyFITS.git`` and so on.  Use of virtualenv and
``./setup.py develop`` are strongly encouraged for developing on PyFITS--use of
this tools is also described in the aforementioned Workflow for Developers
document.

Synchronizing with SVN
----------------------

This section is primarily intended for developers at STScI who have commit
access to the PyFITS SVN repository (http://svn6.assembla.com/svn/pyfits).
The PyFITS Git and SVN repositories are synced using the git-svn command.
git-svn can be tricky to install as it requires the Perl bindings for SVN, as
well as SVN itself and of course Git.  The easiest way to get git-svn is to
ask a system administrator to install it from the OS packaging system.

Most guides for setting up git-svn start out with either the ``git svn init``
command or ``git svn clone``.  But because the work of synchronizing the Git
and SVN repositories up until this point has already been done, a faster,
though seemingly less straightforward approach, is to just clone the GitHub
reposiotry and add the git-svn metadata manually:

1. Clone the main spacetelescope GitHub repository::

       git clone git@github.com:spacetelescope/PyFITS.git

2. cd into the repository and open ``.git/config`` in an editor and add the
   following::

       [svn-remote "svn"]
           url = http://svn6.assembla.com/svn/pyfits
           fetch = trunk:refs/remotes/trunk
           branches = branches/*:refs/remotes/branches/*
           tags = tags/*:refs/remotes/tags/*
       [branch "3.0-stable"]
           remote = .
           merge = refs/remotes/branches/3.0-stable
       [branch "3.1-stable"]
           remote = .
           merge = refs/remotes/branches/3.1-stable

   Repeat the ``[branch "X.Y-stable"]`` section following the above pattern
   for any actively maintained release branches (see the "Maintenance" section
   below for more details on release branches).

3. Put the hash of the latest revision of the upstream master branch in refs
   file for trunk, so git-svn knows where to start synchronizing with SVN's
   trunk::

       git rev-parse origin/master > .git/refs/remotes/trunk

4. Finally, do::

       git svn fetch

   to synchronize any new revisions in the SVN repository.

Syncing new changes to SVN
^^^^^^^^^^^^^^^^^^^^^^^^^^

The command for committing new changes in git to the SVN repository is
`git svn dcommit`.  This command goes through all commits on the current
branch that have *not* yet been committed to SVN and does so.

Whenever you are about to push new changes on the master branch to the remote
remote repository on GitHub it is best to first cross-commit those changes to
SVN.  This is because git-svn rewrites the commit messages on all your commits
to include a reference to the SVN revision that was created from that commit.
So if you push first, and then run `git svn dcommit` you will now have
different commits (as far as their SHA has is concerned) on your local
repository from what you just pushed to the remote repository.  The simplest
way to resolve this, when it happens, is to `git push --force`.  This will
override the old history with the new history that includes the SVN revisions
in the commit messages.

It's easier, however, to remember to always run `git svn dcommit` before doing
a `git push`.


Maintenance
===========

At any given time there are two to three lines of development on PyFITS
(possibly more if some critical bug is discovered that needs to be backported
to older release lines, though such situations are rare).  Typically there is
the mainline development in the 'master' branch, and at least one branch named
after the last minor release.  For example, if the version being developed in
the mainline is '3.2.0' there will be, at a minimum, a '3.1-stable' branch into
which bug fixes can be ported.  There may also be a '3.0-stable' branch and so
on so long as new bugfix releases are being made with '3.0.z' versions.

Bug fix releases should never add new public APIs or change existing ones--they
should only correct bugs or major oversights.  "Minor" releases, where the
second number in the version is increased, may introduce new APIs and may
*deprecate* old interfaces (see the ``@deprecated`` decorated in
``pyfits.util``, but may not otherwise remove or change (non-buggy) behavior of
old interfaces without backwards compatibility with the previous versions in
the same major version line.  Major releases may break backwards compatibility
so long as warning has been given through ``@deprecated`` markers and
documentation that those interfaces will break in future versions.

In general all development should be done in the 'master' branch, including
development of new features and bug fixes (though temporary branches should
certainly be used aggressively for any individual feature or fix being
developed, they should be merged back into 'master' when ready).

The only exception to this rule is when developing a bug fix that *only*
applies to an older release line.  For example it's possible for a bug to exist
in version '3.1.1' that no longer exists in the 'master' branch (perhaps
because it pertains to an older API), but that still exists in the '3.1-stable'
branch.  Then that bug should be fixed in the '3.1-stable' branch to be
included in the version '3.1.2' bugfix release (assuming a bugfix release is
planned).  If that bug pertains to any older release branches (such as
'3.0-stable') it should also be backported to those branches by way of
``git cherry-pick``.


Releasing
=========

Creating a PyFITS release consists 3 main stages each with several sub-steps
according to this rough outline:

1. Pre-release

   a. Set the version string for the release in the setup.cfg file

   b. Set the release date in the changelog (CHANGES.txt)

   c. Test that README.txt and CHANGES.txt can be correctly parsed as
      RestructuredText.

   d. Commit these preparations to the repository, creating a specific commit
      to tag as the "release"

2. Release

   a. Create a tag from the commit created in the pre-release stage

   b. Register the new release on PyPI

   c. Build a source distribution of the release and test that it is
      installable (specifically, installable with pip) and that all the tests
      pass from an installed version

3. Post-release

   a. Upload the source distribution to PyPI

   b. Set the version string for the "next" release in the setup.cfg file (the
      choice of the next version is based on inference, and does not mean the
      "next" version can't be changed later if desired)

   c. Create a new section in CHANGES.txt for the next release (using the same
      "next" version as in part b)

   d. Commit these "post-release" changes to the repository

   e. Push the release commits and the new tag to the remote repository
      (GitHub)

   f. Update the PyFITS website to reflect the new version

   g. Build Windows installers for all supported Python versions and upload
      them to PyPI

Most of these steps are automated by using `zest.releaser`_ along with some
hooks designed specifically for PyFITS that automate actions such as updating
the PyFITS website.

Prerequisites for performing a release
--------------------------------------

1. Because PyFITS is released (registered and uploaded to) on PyPI it is
   necessary to create an account on PyPI and get assigned a "Maintainer"
   role for the PyFITS package.  Currently the package owners--the only two
   people who can add additional Maintainers are Erik Bray <embray@stsci.edu>
   and Nicolas Barbey <nicolas.a.barbey@gmail.com>.  (It remains a "todo" item
   to add a shared "space telescope" account.  In the meantime, should both of
   those people be hit by a bus simultaneously the PyPI administrators will be
   reasonable if the situation is explained to them with proper documentation).

   Once your PyPI account is set up, it is necessary to add your PyPI
   credentials (username and password) to the ``.pypirc`` file in your home
   directory with the following format::

       [server-login]
       username: <your PyPI username>
       password: <your PyPI password>

   Unfortunately some the ``setup.py`` commands for interacting with PyPI
   are broken in that they don't allow interactive password entry.  Creating
   the ``.pypirc`` file is *currently* the most reliable way to make
   authentication with PyPI "just work".  Be sure to ``chmod 600`` this file.

2. Also make sure to have an account on readthedocs.org with administrative
   access to the PyFITS project on Read the Docs:
   https://readthedocs.org/projects/pyfits/
   This hosts documentation for all (recent) versions of PyFITS.  (TODO: Here
   also we need a "space telescope" account with administrative rights to all
   STScI projects that use RtD.)

3. It's best to do the release in a relatively "clean" Python environment, so
   make sure you have `virtualenv`_ installed and that you've had some practice
   in using it.

4. Make sure you have Numpy and nose installed and are able to run the PyFITS
   tests successfully without any errors.  Even better if you can do this with
   tox.

5. Make sure that at least someone can make the Windows builds.  This requires
   a Windows machine with at least Windows XP, Mingw32 with msys, and all of
   the Python development packages.  Python versions 2.5, 2.6, 2.7, 3.1, and
   3.2 should be installed with the installers from python.org, as well as a
   recent version of Numpy for each of those Python versions (currently Numpy
   1.6.x), as well as Git.  (TODO: More detailed instructions for setting up
   a Windows development environment.)

6. PyFITS also has a page on STScI's website:
   http://www.stsci.edu/institute/software_hardware/pyfits.  This is normally
   the first hit when Googling 'pyfits' so it's important to keep up to date.
   At a minimum each release should update the front page to mention the most
   recent release, the Release Notes page with an HTML rendering of the most
   recent changelog, and the download page with links to all the current
   versions.  See the exisint site for examples.  The STScI website has both
   a test server and a production server.  It's difficult for content creators
   to get direct access to the production server, but at least make sure you
   have access to the test server on port 8072, and that IT has given you
   permission to write to the PyFITS section of the site.

   Part of the PyFITS automated release script attempts to update the PyFITS
   website (on the test server) as part of the standard release process.  So
   it's important to test your access to the site and ability to make edits.
   If for any reason the automatic update fails (e.g. your authentication
   fails) it is still possible to update the site manually.

   Once the updates are made it's necessary to have IT push the updates to the
   production server.  As of writing the best person to ask is George Smyth--
   asking him directly is the fastest way to get it done, though if you send a
   ticket to IT it will be handled eventually.

Release procedure
-----------------

(These instructions are adapted from the `Astropy release process`_
which itself was adapted from PyFITS' release process--the former just got
written down first.)

1. In a directory outside the pyfits repository, create an activate a
   virtualenv in which to do the release (it's okay to use
   ``--system-site-packages`` for dependencies like Numpy)::

       $ virtualenv --system-site-packages --distribute pyfits-release
       $ source pyfits-release/bin/activate

2. Obtain a *clean* version of the PyFITS repository. That is, one where you
   don’t have any intermediate build files. It is best to use a fresh
   ``git clone`` from the main repository on GitHub without any of the git-svn
   configuration. This is because the git-svn support in zest.releaser does not
   handle tagging in branches very well yet.

3. Use ``git checkout`` to switch to the appropriate branch from which to do
   the release.  For a new major or minor release (such as 3.0.0 or 3.1.0)
   this should be the 'master' branch.  When making a bugfix release it is
   necessary to switch to the appropriate bugfix branch (e.g.
   ``git checkout 3.1-stable`` to release 3.1.2 up from 3.1.1).

4. Install ``zest.releaser`` into the virtualenv; use ``--upgrade --force`` to
   ensure that the latest version is installed in the virtualenv (if you’re
   running a csh variant make sure to run rehash afterwards too)::

       $ pip install zest.releaser --upgrade --force

5. Install ``stsci.distutils`` which includes some additional releaser hooks
   that are useful::

       $ pip install stsci.distutils --upgrade --force

6. Ensure that any lingering changes to the code have been committed, then
   start the release by running::

       $ fullrelease

7. You will be asked to enter the version to be released.  Press enter to
   accept the default (which will normally be correct) or enter a specific
   version string.  A diff will then be shown of CHANGES.txt and setup.cfg
   showing that a release date has been added to the changelog, and that the
   version has been updated in setup.cfg.  Enter 'Y' when asked to commit these
   changes.

8. You will then be shown the command that will be run to tag the release.
   Enter 'Y' to confirm and run the command.

9. When asked "Check out the tag (for tweaks or pypi/distutils server upload)"
   enter 'Y': This feature is used when uploading the source distribution to
   our local package index.  When asked to 'Register and upload' to PyPI enter
   'N'.  We will do this manually later in the process once we've tested the
   release out first.

10. You will be asked to enter a new development version.  Normally the next
    logical version will be selected--press enter to accept the default, or
    enter a specific version string.  Do not add ".dev" to the version, as this
    will be appended automatically (ignore the message that says ".dev0 will be
    appended"--it will actually be ".dev" without the 0).  For example, if the
    just-released version was "3.1.0" the default next version will be "3.1.1".
    If we want the next version to be, say "3.2.0" then that must be entered
    manually.

11. You will be shown a diff of CHANGES.txt showing that a new section has been
    added for the new development version, and showing that the version has
    been updated in setup.py.  Enter 'Y' to commit these changes.

12. When asked to push the changes to a remote repository, enter 'N'.  We want
    to test the release out before pushing changes to the remote repository or
    registering in PyPI.

13. When asked to update the PyFITS homepage enter 'Y'.  The enter the name of
    the previous version (in the same MAJOR.MINOR.x branch) and then the name
    of the just released version.  The defaults will usually be correct.  When
    asked, enter the username and password for your Zope login.  As of writing
    this is not necessarily the same as your Exchange password.  If the update
    succeeeds make sure to e-mail IT and ask them to push the updated pages
    from the test site to the production site.

    This should complete the portion of the process that's automated at this point
    (though future versions will automate these steps as well, after a few needed
    features are added to zest.releaser).

14. Check out the tag of the released version.  For example::

        $ git checkout v3.1.0

15. Create the source distribution by doing::

        $ python setup.py sdist

16. Now, outside the repository create and activate another new virtualenv
    for testing the release::

        $ virtualenv --system-site-packages --distribute pyfits-release-test
        $ source pyfits-release-test/bin/activate

17. Use ``pip`` to install the source distribution built in step 13 into the
    new test virtualenv.  This will look something like::

        $ pip install PyFITS/dist/pyfits-3.2.0.tar.gz

    where the path should be to the sole ``.tar.gz`` file in the ``dist/``
    directory under your repository clone.

18. Try running the tests in the installed PyFITS::

        $ pip install nose --force --upgrade
        $ nosetests pyfits

    If any of the tests fail abort the process and start over.  Undo the
    previous git commit (where you bumped the version)::

        $ git reset --hard HEAD^

    Resolve the test failure, commit any new fixes, and start the release
    procedure over again (it's rare for this to be an issue if the tests
    passed *before* starting the release, but it is possible--the most likely
    case being if some file that *should* be installed is either not getting
    installed or is not included in the source distribution in the first
    place).

19. Assuming the test installation worked, change directories back into the
    repository and register the release on PyPI with::

        $ python setup.py register

    Upload the source distribution to PyPI; this is preceded by re-running the
    sdist command, which is necessary for the upload command to know which
    distribution to upload::

        $ python setup.py sdist upload

20. When releasing a new major or minor version, create a bugfix branch for
    that version.  Starting from the tagged changset, just checkout a new
    branch and push it to the remote server.  For example, after releasing
    version 3.2.0, do::

        $ git checkout -b 3.2-stable

    Then edit the setup.cfg so that the version is ``'3.2.1.dev'``, and commit
    that change. Then, do::

        $ git push origin +3.2-stable

    .. note::
        You may need to replace ``origin`` here with ``upstream`` or whatever
        remote name you use for the main PyFITS repository on GitHub.

    The purpose of this branch is for creating bugfix releases like "3.2.1" and
    "3.2.2", while allowing development of new features to continue in the
    master branch.  Only changesets that fix bugs without making significant
    API changes should be merged to the bugfix branches.

21. Log into the Read the Docs control panel for PyFITS at
    https://readthedocs.org/projects/pyfits/.  Click on "Admin" and then
    "Versions".  Find the just-released version (it might not appear for a few
    minutes) and click the check mark next to "Active" under that version.
    Leave the dropdown list on "Public", then scroll to the bottom of the page
    and click "Submit".

22. We also mirror the most recent documentation at pythonhosted.org/pyfits (
    formerly packages.python.org).  The easiest way to do this is to wait until
    the documentation has been built by Read the Docs (otherwise it is
    necessary to build the docs yourself) and download it as a zip file.  For
    version 3.2.0 the URL would be:

    https://media.readthedocs.org/htmlzip/pyfits/v3.2.0/pyfits.zip

    (just replace the version part of the URL with the appropriate version).

    Then on the package management page on PyPI
    (https://pypi.python.org/pypi?%3Aaction=pkg_edit&name=pyfits) locate the
    documentation upload form and upload the just-downloaded zip file.

23. Build and upload the Windows installers:

    a. Launch a MinGW shell.

    b. Just as before make sure you have a ``pypirc`` file in your home
       directory with your authentication info for PyPI.  On Windows the file
       should be called just ``pypirc`` without the leading ``.`` because
       having some consistency would make this too easy :)

    c. Do a ``git clone`` of the repository or, if you already have a clone
       of the repository do ``git fetch --tags`` to get the new tags.

    d. Check out the tag for the just released version.  For example::

           $ git checkout v3.2.0

       (ignore the message about being in "detached HEAD" state).

    e. For each Python version installed, build with the mingw32 compiler,
       create the binary installer, and upload it.  It's best to use the full
       path to each Python version to avoid ambiguity.  It is also best to
       clean the repository between builds for each version.  For example::

           $ /C/Python25/python setup.py build -c mingw32 bdist_wininst upload
           < ... builds and uploads successfully ... >
           $ git clean -dfx
           $ /C/Python26/python setup.py build -c mingw32 bdist_wininst upload
           < ... builds and puloads successfully ... >
           $ git clean -dfx
           $ < ... and so on, for all currently supported Python versions ... >


.. _Coding Guidelines: http://astropy.readthedocs.org/en/v0.2.1/development/codeguide.html
.. _Documentation Guidelines: http://astropy.readthedocs.org/en/v0.2.1/development/docguide.html
.. _Contributing to Astropy: http://astropy.readthedocs.org/en/v0.2.1/development/workflow/index.html
.. _Workflow for Developers: http://astropy.readthedocs.org/en/v0.2.1/development/workflow/development_workflow.html
.. _Astropy release process: http://astropy.readthedocs.org/en/v0.2.1/development/building_packaging.html#release
.. _zest.releaser: https://pypi.python.org/pypi/zest.releaser/3.44
.. _virtualenv: https://pypi.python.org/pypi/virtualenv/1.9.1
