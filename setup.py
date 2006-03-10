from distutils.core import setup
import sys
 
if not hasattr(sys, 'version_info') or sys.version_info < (2,3,0,'alpha',0):
    raise SystemExit, "Python 2.3 or later required to build pyfits."

def dolocal():
    """Adds a command line option --local=<install-dir> which is an abbreviation for
    'put all of pyfits in <install-dir>/pyfits'."""
    if "--help" in sys.argv:
        print >>sys.stderr
        print >>sys.stderr, " options:"
        print >>sys.stderr, "--local=<install-dir>    same as --install-lib=<install-dir>"
    for a in sys.argv:
        if a.startswith("--local="):
            dir = a.split("=")[1]
            sys.argv.extend([
                "--install-lib="+dir,
                ])
            sys.argv.remove(a)

def main():
    dolocal()
    setup(name = "pyfits",
              version = "1.0",
              description = "General Use Python Tools",
              author = "J. C. Hsu",
              maintainer_email = "help@stsci.edu",
              license = "http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE",
              platforms = ["Linux","Solaris","Mac OS X","Win"],
              py_modules = ['pyfits'],
              package_dir={'':'lib'})


if __name__ == "__main__":
    main()
