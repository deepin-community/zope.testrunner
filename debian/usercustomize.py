# Work around difficulties with pre-PEP-420 namespace packages: the .pth
# files from build-dependencies are loaded during site initialization,
# adding the system "zope" package directory to sys.path, but we want to
# ensure that subpackages of zope can be imported both from our
# build-dependencies and from this package while running tests.

import os.path

import zope

zope.__path__[:0] = [os.path.join(os.path.dirname(__file__), "zope")]
