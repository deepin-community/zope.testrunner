#!/usr/bin/python3
"""A very quick and dirty script to test a package using the debian/test/control file in a throw away VM.

This script needs to run as root and installs a lot of packages arbitrarily. If
it breaks the installation it's run on, you get to keep both pieces.

Usage:

    test_one_package_in_throwaway_vm.py zope.interface
        (apt-get source zope.interface, unpack and test)
"""

import shutil
import tempfile
import os
import stat
import sys
import unittest
import logging
import subprocess

class Dependency(object):

    def __init__(self, package):
        self.package = package

class _Test(unittest.TestCase):

    def __init__(self, tests_dir, name, restrictions=frozenset(), features=frozenset(), depends=(), parse_context=None):
        unittest.TestCase.__init__(self, methodName='runTest')
        self._name = name
        self._restrictions = restrictions
        self._features = features
        self._depends = depends
        self._tests_dir = tests_dir
        if parse_context is None:
            parse_context = {}
        self._parse_context = parse_context

    def assertDependencies(self):
        """Install dependencies/check if they are installed or error"""
        for d in self._depends:
            logging.info("Installing: %s", d.package)
            subprocess.check_call(['apt-get', '--force-yes', '-y', 'install', d.package])

    def runTest(self):
        self.assertDependencies()
        logging.info("RUNNING %s", self._name)
        binary = os.path.join(self._tests_dir, self._name)
        binary = os.path.abspath(binary)
        subprocess.check_call(['/bin/chmod', 'a+x', binary])
        tmpdir = tempfile.mkdtemp()
        try:
            env = {'TMPDIR': tmpdir}
            env.update(os.environ) # ??? 
            p = subprocess.Popen(['sudo', '-u', 'nobody', binary],
                                 stdin=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 env=env)
            stdout, stderr = p.communicate()
        finally:
            shutil.rmtree(tmpdir)
        msg = ""
        if stderr:
            msg = msg + "Test Printed to stderr:\n\n%s\n" % stderr.decode('utf-8')
        self.assertFalse(stderr, msg)
        if p.returncode != 0:
            logging.error(msg)
        self.assertEquals(p.returncode, 0)

class Parser(object):
    
    def __init__(self):
        self.tests = []

    def _add_test(self, stanza, filename, lineno):
        pc = dict(filename=filename, lineno=lineno)
        tests = stanza.pop('tests')
        tests_dir = stanza.pop('tests_dir', 'debian/tests')
        if 'depends' not in stanza:
            stanza['depends'] = tuple(self._normalize_dep('@'))
        for test in tests:
            self.tests.append(_Test(tests_dir, test, parse_context=pc, **stanza))

    def _normalize_dep(self, dep):
        dep = dep.strip()
        assert ' ' not in dep, dep
        assert dep, dep
        if dep != '@':
            return [Dependency(dep)]
        deps = []
        data = open('debian/control', 'r', encoding='utf-8').read()
        for line in data.splitlines():
            if not line.startswith("Package:"):
                continue
            line = line[8:].strip()
            deps.append(Dependency(line))
        return deps

    def parse(self):
        filename = 'debian/tests/control'
        data = open(filename, 'r').read()
        stanza = {}
        skipping = False
        startline = 1
        for lineno, line in enumerate(data.splitlines()):
            if not line:
                if skipping:
                    skipping = False
                    stanza = {}
                    startline = lineno + 1
                    continue
                if stanza:
                    self._add_test(stanza, filename, startline)
                    stanza = {}
                startline = lineno + 1
            elif skipping:
                continue
            elif line.startswith("Tests:"):
                line = line[6:].strip()
                stanza['tests'] = frozenset(line.split())
            elif line.startswith("Depends:"):
                line = line[8:].strip()
                deps = []
                for d in line.split(','):
                    deps.extend(self._normalize_dep(d))
                stanza['depends'] = tuple(deps)
            elif line.startswith("Features:"):
                line = line[9:].strip()
                stanza['features'] = features= frozenset(line.split())
            elif line.startswith("Restrictions:"):
                line = line[13:].strip()
                stanza['restrictions'] = restrictions = frozenset(line.split())
            elif line.startswith("Tests-Directory:"):
                line = line[16:].strip()
                stanza['tests_dir'] = frozenset(line.split())
            else:
                logging.warn("Skipped stanza due to unknown field: %s: %s" % (lineno, line))
                skipping = True
        if stanza and not skipping:
            # catch last parsed stanza
            self._add_test(stanza, filename, startline)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.info("Updating")
    subprocess.check_call(['apt-get', 'install', 'sudo'])
    subprocess.check_call(['apt-get', 'update'])
    mytemp = tempfile.mkdtemp()
    subprocess.check_call(['/bin/chmod', 'a+rx', mytemp])
    os.chdir(mytemp)
    logging.info("Getting and un-packing source")
    subprocess.check_call(['apt-get', 'source', sys.argv[1]])
    for d in os.listdir(mytemp):
        sourcedir = os.path.join(mytemp, d)
        if os.path.isdir(sourcedir):
            break
    else:
        raise Exception("Could not find unpacked source in %s" % mytemp)
    os.chdir(sourcedir)
    logging.info("Running tests from %s" % sourcedir)
    p = Parser()
    p.parse()
    suite = unittest.TestSuite(tests=p.tests)
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    logging.info("Tests were run in %s" % sourcedir)
    sys.exit(not result.wasSuccessful())
