#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Usage for setup.py:
#
# from distutils.core import setup
# import py2exe
# from setup_py2exe_custom import custom_py2exe
#
# setup(...,
#       cmdclass={'py2exe': custom_py2exe},
#       options={'py2exe': {
#           skip_archive=1,   # mandatory overwith will be opt-out
#           compressed=0,     # do not compress - mandatory when skip_archive=1
#           bundle_files=3,   # keep pythonXX.dll out of exe
#           optimize=0,       # do not compile .py files
#           collected_libs_dir='libs',  # move all collected libs into this director
#           collected_libs_data_relocate='babel,pytz',  # force moving collected libs data into collected libs dir
#       }},
#       data_files=fixup_data_pytz_zoneinfo() # to add pytz zoneinfo files
#      )
#
#

import os
import tempfile

if os.name == 'nt':
    from py2exe.build_exe import py2exe as build_exe, fancy_split
else:
    # fake it for non-Windows, so that setup.py can be run for
    # installing dependencies.
    class _be(dict):
        def __init__(self, arg1,arg2,arg3):
            pass
        def __dir__(self):
            return tuple(self)
        def __getattribute__(self, name):
            if name == 'user_options':
                return []
            else:
                raise AttributeError(name)
    build_exe = _be(1, 2, 3)
    fancy_split = None

def extra_files():
    r = []
    try:
        import certifi
    except:
        return []
    main_path = os.path.relpath(os.path.dirname(certifi.__file__))
    cert_path = os.path.join(main_path, 'cacert.pem')
    r.append(('libs/certifi', [cert_path]))

    try:
        import office365
    except:
        return []
    main_path = os.path.relpath(os.path.dirname(office365.__file__))
    xml_file = os.path.join(main_path, 'runtime/auth/SAML.xml')
    r.append(('libs/office365/runtime/auth', [xml_file]))

    import pyphen
    main_path = os.path.relpath(os.path.dirname(pyphen.__file__))
    dic_files = []
    for root, _, filenames in os.walk(os.path.join(main_path, 'dictionaries')):
        for filename in filenames:
            dic_files.append(os.path.join(main_path, 'dictionaries', filename))
    r.append(('libs/pyphen/dictionaries',dic_files))
    return r

def fixup_data_pytz_zoneinfo():
    r = {}
    import pytz
    tzdir = os.path.relpath(os.path.dirname(pytz.__file__))
    for root, _, filenames in os.walk(os.path.join(tzdir, "zoneinfo")):
        base = os.path.join('pytz', root[len(tzdir) + 1:])
        r[base] = [os.path.join(root, f) for f in filenames]
    return list(r.items())

def byte_compile_noop(py_files, optimize=0, force=0,
                      target_dir=None, verbose=1, dry_run=0,
                      direct=None):

    compiled_files = []
    from distutils.dir_util import mkpath
    from distutils.dep_util import newer
    from distutils.file_util import copy_file

    for file in py_files:
        # Terminology from the py_compile module:
        #   cfile - byte-compiled file
        #   dfile - purported source filename (same as 'file' by default)
        cfile = file.__name__.replace('.', '\\')

        if file.__path__:
            dfile = cfile + '\\__init__.py'
        else:
            dfile = cfile + '.py'
        if target_dir:
            cfile = os.path.join(target_dir, dfile)

        if force or newer(file.__file__, cfile):
            if verbose:
                print("fake-byte-compiling %s to %s" % (file.__file__, dfile))
            if not dry_run:
                mkpath(os.path.dirname(cfile))
                copy_file(file.__file__, cfile, preserve_mode=0)
        else:
            if verbose:
                print("skipping byte-compilation of %s to %s" % \
                      (file.__file__, dfile))
        compiled_files.append(dfile)
    return compiled_files

# byte_compile()

class custom_py2exe(build_exe):
    user_options = build_exe.user_options + [
        ("collected-libs-dir", None,
         "Place all collected libs under a specific sub-directory"),
        ("collected-libs-data-relocate", None,
         "List of prefix to rellocate under collected-libs-dir directory"),
        ("package-build-extra-dirs", None,
         "List extra packages dirs to check for - moving them to exe root dir"),
    ]

    def initialize_options(self):
        build_exe.initialize_options(self)
        self.collected_libs_dir = '.'
        self.collected_libs_data_relocate = []
        self.package_build_extra_dirs = []

    def finalize_options(self):
        build_exe.finalize_options(self)
        self.collected_libs_data_relocate = fancy_split(self.collected_libs_data_relocate)
        self.package_build_extra_dirs = fancy_split(self.package_build_extra_dirs)

    def create_directories(self):
        build_exe.create_directories(self)
        self.lib_dir = os.path.join(self.lib_dir, self.collected_libs_dir)
        self.mkpath(self.lib_dir)
        self.boot_tmp_dir = tempfile.mkdtemp()

    def get_boot_script(self, boot_type):
        py2exe_boot_file = build_exe.get_boot_script(self, boot_type)
        custom_boot_file = os.path.join(self.boot_tmp_dir, os.path.basename(py2exe_boot_file))
        if not os.path.exists(custom_boot_file):
            cbootfile = open(custom_boot_file, 'wb')
            obootfile = open(py2exe_boot_file, 'rb')

            # copy original file
            cbootfile.write(obootfile.read())
            obootfile.close()

            # write special custom handlers
            if boot_type in ['common', 'service']:
                cbootfile.write("""
import sys, os

if hasattr(sys, 'frozen'):
    # executable is frozen, add executable directory to sys.path
    sys.path.append(os.path.dirname(sys.executable))

""")
            elif boot_type == 'service':
                pass

            cbootfile.close()
        return custom_boot_file

    def create_binaries(self, py_files, extensions, dlls):
        dist = self.distribution

        # Do not try compiling .py files for 'packages', we
        # want them into the exe directory - and only collected
        # dependencies with 'collected libbs dir'
        src_build_cmd = dist.get_command_obj('build')
        src_build_cmd.ensure_finalized()
        build_lib = getattr(src_build_cmd, 'build_lib', None)
        if build_lib is None:
            raise Exception("Could not continue with no 'build_lib' set")

        dist_packages_py_files = []
        def is_forced_packages_files(m):
            if m.__file__:
                for build_dir in [build_lib] + self.package_build_extra_dirs:
                    if m.__file__.startswith(build_dir):
                        dist_packages_py_files.append((m.__file__, m.__file__[len(build_dir)+1:]))
                        return True
            return False
        py_files = [ m for m in py_files if not is_forced_packages_files(m) ]

        if dist_packages_py_files:
            print("*** copy package's python file to root directory ***")
            for (srcfile, relfile) in dist_packages_py_files:
                dstfile = os.path.join(self.exe_dir, *os.path.split(relfile))
                dstfile_dir = os.path.dirname(dstfile)
                self.mkpath(dstfile_dir)
                self.copy_file(srcfile, dstfile, preserve_mode=0)

        # Run fake compilation - just copy raw .py file into their
        # destination directory
        self.no_compiled_files = byte_compile_noop(py_files,
                                                   target_dir=self.collect_dir,
                                                   optimize=self.optimize,
                                                   force=0,
                                                   verbose=self.verbose,
                                                   dry_run=self.dry_run)

        # Force relocate of specific packages data within collected libs dir
        def fixup_location(l):
            if isinstance(l, tuple) and any([ l[0].startswith(reloc_prefix)
                                              for reloc_prefix in self.collected_libs_data_relocate ]):
                return (os.path.join(self.collected_libs_dir, l[0]), l[1])
            return l
        if dist.has_data_files():
            dist.data_files = [ fixup_location(f) for f in dist.data_files ]

        # Call parent create_binaries() without any py_files, so that py2exe
        # do no force their compilations
        return build_exe.create_binaries(self, [], extensions, dlls)

    def make_lib_archive(self, zip_filename, base_dir, files,
                         verbose=0, dry_run=0):
        allfiles = files + self.no_compiled_files
        return build_exe.make_lib_archive(self, zip_filename, base_dir, allfiles, verbose=verbose, dry_run=dry_run)

