#!/usr/bin/python
# -*- coding: utf8 -*-
import unittest
import HTMLTestRunner
from os import walk
from os import path
import sys

# TODO: Read a file to parse some configuration and read which directory to browse
path_for_tests = 'tests'

def _separator():
    print ('#' * 70)

def main():
    """
    Launch all 'test_' files in a specific directory
    """
    # Prepare some values
    suite = unittest.TestSuite() # the suite of tests
    test_modules = [] # modules that are in 'tests' directory
    added_paths = [] # path added to PYTHONPATH

    _separator()

    # Browse the directory to search all tests
    print ('Browsing %s directory.' % path_for_tests)
    for racine, _, files in walk(path_for_tests):
        directory = path.basename(racine)
        if directory == 'tests':
            for f in files:
                if (f.startswith('test') and f.endswith('.py') and f != 'test.py'):
                    name = path.join(racine, f)
                    test_modules.append((name, f[:-3]))
    # Inform how many modules was found
    print ('%d module(s) found' % len(test_modules))

    _separator()

    # Launch a python script that runs some tasks before tests
    print ('Launch pre-tasks')
    execfile('pre_runner.py')

    _separator()

    # Import found modules
    print ('Import these modules:')
    #+ Sort them by module name (x[1])
    for module_info in sorted(test_modules, key=lambda x: x[1]):
        module_path = path.dirname(module_info[0])
        if module_path not in sys.path:
            sys.path.append(module_path)
            added_paths.append(module_path)

        module = __import__(module_info[1])
        if 'get_test_class' in module.__dict__:
            class_type = module.get_test_class()
            print (" - Module %s" % (class_type.__module__,))
            test_suite = unittest.TestSuite((unittest.makeSuite(class_type), ))
            suite.addTest(test_suite)

    _separator()

    # Create a file for the output result
    output = file('output.html', 'wb')
    # Run tests
    campaign = HTMLTestRunner.HTMLTestRunner(
        stream=output,
        title='Example tests',
        description='A suite of tests that permit to test PyUnit class'
    )
    print ('TESTING...')
    campaign.run(suite)

    _separator()

    print ('Clean paths')
    # Delete all paths added to the PYTHONPATH
    for added_path in added_paths:
        sys.path.remove(added_path)

    _separator()

    # Launch a python script that runs some tasks after all tests
    print ('Launch post-tasks')
    execfile('post_runner.py')

    _separator()

if __name__ == "__main__":
    main()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: