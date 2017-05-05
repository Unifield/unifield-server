#!/usr/bin/python
# -*- coding: utf8 -*-
from __future__ import print_function
import unittest
import HTMLTestRunner
from os import walk
from os import path
import sys
from tests import colors
from oerplib import error

# TODO: Read a file to parse some configuration and read which directory to browse
path_for_tests = 'tests'

def _separator():
    print ('#' * 70)

def main():
    """
    Launch all 'test_' files in a specific directory
    """
    try:
        # Prepare some values
        suite = unittest.TestSuite() # the suite of tests
        test_modules = [] # modules that are in 'tests' directory
        added_paths = [] # path added to PYTHONPATH
        c = colors.TerminalColors()
        
        run_only_modules = False
        if len(sys.argv) > 1:
            # list of module names (without .py) to run only
            # (must exists in tests folder)
            run_only_modules = sys.argv[1:]

        _separator()
        # Browse the directory to search all tests
        print (c.BGreen + 'Browsing' + c.Color_Off + ' %s directory.' % path_for_tests)
        for racine, _, files in walk(path_for_tests):
            directory = path.basename(racine)
            if directory == 'tests':
                for f in files:
                    if (f.startswith('test') and f.endswith('.py') and f != 'test.py'):
                        mod_name = f[:-3]
                        if not run_only_modules or \
                         (run_only_modules and mod_name in run_only_modules):
                            name = path.join(racine, f)
                            test_modules.append((name, mod_name))
        # Inform how many modules was found
        print ('%d module(s) found' % len(test_modules))

#       _separator()
#       # Launch a python script that runs some tasks before tests
#       print ('Launch pre-tasks')
#       execfile('pre_runner.py')

        _separator()
        # Import found modules
        print(c.BGreen + 'Import' + c.Color_Off + ' modules + instanciate them')
        #+ Sort them by module name (x[1])
        for module_info in sorted(test_modules, key=lambda x: x[1]):
            module_path = path.dirname(module_info[0])
            if module_path not in sys.path:
                sys.path.append(module_path)
                added_paths.append(module_path)

            module = __import__(module_info[1])
            if 'get_test_class' in module.__dict__:
                class_type = module.get_test_class()
                print ("%s module:" % (class_type.__module__,))
                test_suite = unittest.TestSuite((unittest.makeSuite(class_type), ))
                suite.addTest(test_suite)

            if 'get_test_suite' in module.__dict__:
                suite_type = module.get_test_suite()
                print ("%s module:" % (suite_type[0].__module__,))
                for class_type in suite_type:
                    test_suite = unittest.TestSuite((unittest.makeSuite(class_type), ))
                    suite.addTest(test_suite)

        _separator()
        # Create a file for the output result
        output = file('output.html', 'wb')
        # Run tests
        campaign = HTMLTestRunner.HTMLTestRunner(
            stream=output,
            verbosity=2,
            title='Example tests',
            description='A suite of tests that permit to test PyUnit class'
        )
        print('Launch UnifieldTest ' + c.BGreen + 'Campaign' + c.Color_Off)
        print('----------------------------\n')
        print('Note: 1 point represents a test. F means Fail. E means Error.')
        campaign.run(suite)

        _separator()
        print ('Clean used paths')
        # Delete all paths added to the PYTHONPATH
        for added_path in added_paths:
            sys.path.remove(added_path)

#       _separator()
#       # Launch a python script that runs some tasks after all tests
#       print ('Launch post-tasks')
#       execfile('post_runner.py')

        _separator()
    except error.RPCError as e:
        print(e.oerp_traceback)
        print(e.message)

if __name__ == "__main__":
    main()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
