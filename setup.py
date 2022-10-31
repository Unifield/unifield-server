#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

# setup from TinERP
#   taken from straw http://www.nongnu.org/straw/index.html
#   taken from gnomolicious http://www.nongnu.org/gnomolicious/
#   adapted by Nicolas Évrard <nicoe@altern.org>
#

import sys
import os
from os.path import join, isfile, basename
import glob

from setuptools import setup, find_packages
from setuptools.command.install import install
from distutils.sysconfig import get_python_lib
from setup_py2exe_custom import custom_py2exe, fixup_data_pytz_zoneinfo, extra_files

py2exe_keywords = {}
if os.name == 'nt':
    py2exe_keywords['console'] = [
        {"script": join("bin", "openerp-server.py"),
         "icon_resources": [(1, join("pixmaps", "openerp-icon.ico"))]
         }]
    py2exe_keywords['options'] = {
        "py2exe": {
            "compressed": 0,
            "optimize": 0,
            "skip_archive": 1,
            "bundle_files": 3,
            "collected_libs_dir": "libs",
            "collected_libs_data_relocate": "pytz",
            "package_build_extra_dirs": join(os.path.abspath(os.path.dirname(__file__)), "bin"),
            "packages": [
                "lxml", "lxml.builder", "lxml._elementpath", "lxml.etree",
                "lxml.objectify", "decimal", "xml", "xml", "xml.dom",
                "encodings", "dateutil", "wizard", "pychart", "PIL", "pyparsing",
                "pydot", "asyncore", "asynchat", "reportlab",
                "HTMLParser", "select", "mako", "poplib",
                "imaplib", "smtplib", "email", "yaml",
                "uuid", "commands", "mx.DateTime", "json",
                "pylzma", "xlwt", "passlib", "bcrypt", "six", "cffi",
                "psutil", "formencode", "cryptography", "requests",
                "office365", "certifi", "chardet", "ipaddress", "urllib3", "fileinput", "pysftp",
                "openpyxl", "weasyprint", "cssselect2", "tinycss2", "html5lib",
                "cairocffi", "pdfrw", "pyphen", 'CairoSVG'
            ],
            'dist_dir': 'dist',
            'excludes': ["Tkconstants", "Tkinter", "tcl"],
            'dll_excludes': [
                'w9xpopen.exe', 'PSAPI.dll', 'CRYPT32.dll', 'MPR.dll',
                'Secur32.dll', 'SHFOLDER.dll',
                'api-ms-win-core-delayload-l1-1-1.dll',
                'api-ms-win-core-errorhandling-l1-1-1.dll',
                'api-ms-win-core-heap-obsolete-l1-1-0.dll',
                'api-ms-win-core-libraryloader-l1-2-0.dll',
                'api-ms-win-core-processthreads-l1-1-2.dll',
                'api-ms-win-core-profile-l1-1-0.dll',
                'api-ms-win-core-string-obsolete-l1-1-0.dll',
                'api-ms-win-core-sysinfo-l1-2-1.dll',
                'api-ms-win-security-activedirectoryclient-l1-1-0.dll',
            ],
        }
    }

sys.path.append(join(os.path.abspath(os.path.dirname(__file__)), "bin"))

# The following are all overridden in release.py
name = None
description = None
long_desc = None
url = None
author = None
author_email = None
classifiers = None
version = None

execfile(join('bin', 'release.py'))

def find_addons():
    for root, _, names in os.walk(join('bin', 'addons'), followlinks=True):
        if '__openerp__.py' in names or '__terp__.py' in names:
            yield basename(root), root
    # look for extra modules
    try:
        empath = os.getenv('EXTRA_MODULES_PATH', '../addons/')
        for mname in open(join(empath, 'server_modules.list')):
            mname = mname.strip()
            if not mname:
                continue

            terp = join(empath, mname, '__openerp__.py')
            if not os.path.exists(terp):
                terp = join(empath, mname, '__terp__.py')

            if os.path.exists(terp):
                yield mname, join(empath, mname)
            else:
                print "Module %s specified, but no valid path." % mname
    except Exception:
        pass

def data_files():
    '''Build list of data files to be installed'''
    files = []
    if os.name == 'nt':
        files.append(('.', [join('bin', 'histogram.py')]))
        files.append(('.', [join('bin', 'unifield-version.txt')]))
        files.append(('tools', [join('bin', 'tools', 'import_po.dtd')]))
        files.append(('tools', [join('bin', 'tools', 'validators.py')]))
        files.append(('tools', [join('bin', 'tools', 'webdav.py')]))
        files.append(('fonts', filter(isfile, glob.glob('bin/fonts/*'))))
        files.append(('rsync', filter(isfile, glob.glob('bin/rsync/*'))))
        os.chdir('bin')
        for (dp, dn, names) in os.walk('addons'):
            files.append((dp, map(lambda x: join('bin', dp, x), names)))
        os.chdir('..')
        # for root, _, names in os.walk(join('bin','addons')):
        #    files.append((root, [join(root, name) for name in names]))
        for root, _, names in os.walk('doc'):
            files.append((root, [join(root, name) for name in names]))
        # for root, _, names in os.walk('pixmaps'):
        #    files.append((root, [join(root, name) for name in names]))
        files.append(('.', [join('bin', 'import_xml.rng'), ]))
        files.extend(fixup_data_pytz_zoneinfo())
        files.extend(extra_files())
    else:
        man_directory = join('share', 'man')
        files.append((join(man_directory, 'man1'), ['man/openerp-server.1']))
        files.append((join(man_directory, 'man5'), ['man/openerp_serverrc.5']))

        doc_directory = join('share', 'doc', 'openerp-server-%s' % version)
        files.append((doc_directory, filter(isfile, glob.glob('doc/*'))))
        files.append((join(doc_directory, 'migrate', '3.3.0-3.4.0'),
                      filter(isfile, glob.glob('doc/migrate/3.3.0-3.4.0/*'))))
        files.append((join(doc_directory, 'migrate', '3.4.0-4.0.0'),
                      filter(isfile, glob.glob('doc/migrate/3.4.0-4.0.0/*'))))

        openerp_site_packages = join(get_python_lib(prefix=''), 'openerp-server')

        files.append((openerp_site_packages, [join('bin', 'import_xml.rng'), ]))

        for addonname, add_path in find_addons():
            addon_path = join(get_python_lib(prefix=''), 'openerp-server', 'addons', addonname)
            for root, dirs, innerfiles in os.walk(add_path):
                innerfiles = filter(lambda fil: os.path.splitext(fil)[1] not in ('.pyc', '.pyd', '.pyo'), innerfiles)
                if innerfiles:
                    res = os.path.normpath(join(addon_path, root.replace(join(add_path), '.')))
                    files.extend(((res, map(lambda fil: join(root, fil),
                                            innerfiles)),))

    return files

f = file('openerp-server', 'w')
f.write("""#!/bin/sh
echo "Error: the content of this file should have been replaced during "
echo "installation\n"
exit 1
""")
f.close()

def find_package_dirs():
    package_dirs = {'openerp-server': 'bin'}
    for mod, path in find_addons():
        package_dirs['openerp-server.addons.' + mod] = path
    return package_dirs

class openerp_server_install(install):
    def run(self):
        # create startup script
        start_script = "#!/bin/sh\ncd %s\nexec %s ./openerp-server.py $@\n"\
            % (join(self.install_libbase, "openerp-server"), sys.executable)
        # write script
        f = open('openerp-server', 'w')
        f.write(start_script)
        f.close()
        install.run(self)


setup(name=name,
      version=version,
      description=description,
      long_description=long_desc,
      url=url,
      author=author,
      author_email=author_email,
      classifiers=filter(None, classifiers.split("\n")),
      license=license,
      data_files=data_files(),
      cmdclass={
          'install': openerp_server_install,
          'py2exe': custom_py2exe,
      },
      scripts=['openerp-server'],
      packages=[
          '.'.join(['openerp-server'] + package.split('.')[1:])
          for package in find_packages()
      ],
      include_package_data=True,
      package_data={
          '': ['*.yml', '*.xml', '*.po', '*.pot', '*.csv'],
      },
      package_dir=find_package_dirs(),
      python_requires=">=2.7.12",
      install_requires=[
          'cffi==1.11.4',
          'MarkupSafe==1.0',
          'pycparser==2.18',
          'pyparsing==2.2.0',
          'six==1.11.0',
          'lxml==3.7.3',
          'mako==1.0.6',
          'python-dateutil==2.6.0',
          'formencode==1.3.1',
          'psycopg2==2.7.1',
          'pydot==1.2.3',
          'pytz==2017.2',
          'pylzma==0.4.8',
          'Pillow==1.7.8',
          'reportlab==2.5',
          'pyyaml==3.12',
          'egenix-mx-base==3.2.9',
          'passlib==1.7.1',
          'bcrypt==3.1.3',
          'xlwt==1.2.0',
          'psutil==5.2.2',
          'bsdiff4==1.1.4',
          'Office365-REST-Python-Client==2.0.0',
          'asn1crypto==0.24.0',
          'cryptography==2.1.4',
          'enum34==1.1.6',
          'urllib3==1.22',
          'idna==2.6',
          'ipaddress==1.0.19',
          'certifi==2018.1.18',
          'chardet==3.0.4',
          'requests==2.18.4',
          'pyasn1==0.4.3',
          'PyNaCl==1.2.1',
          'paramiko==2.4.1',
          'pysftp==0.2.9',
          'openpyxl==2.6.4',
          'jdcal==1.4.1',
          'et-xmlfile==1.0.1',
          'cairocffi==0.9.0',
          'CairoSVG==1.0.22',
          'cssselect2==0.2.2',
          'pdfrw==0.4',
          'Pyphen==0.10.0',
          'tinycss2==0.6.1',
          'WeasyPrint==0.42.3',
      ],
      **py2exe_keywords
      )

