import os
import re
import sys

from setuptools import setup
from setup_py2exe_custom import custom_py2exe, fixup_data_pytz_zoneinfo

# To make pyflakes happy
version = None
name = None
description = None
long_description = None
author = None
author_email = None
url = None
download_url = None

execfile(os.path.join("openobject", "release.py"))

version_dash_incompatible = False
if 'bdist_rpm' in sys.argv:
    version_dash_incompatible = True
try:
    import py2exe
    assert py2exe

    from py2exe_utils import opts
    opts['options'].setdefault('py2exe',{})
    opts['options']['py2exe'].setdefault('includes',[])
    opts['options']['py2exe']['includes'].extend([
        'win32api',
        'win32con',
        'win32event',
        'win32service',
        'win32serviceutil',
    ])
    opts['options']['py2exe'].update(
        skip_archive=1,
        compressed=0,
        bundle_files=3,
        optimize=0,
        collected_libs_dir='libs',
        collected_libs_data_relocate='babel,pytz',
        packages=[
            "Queue",
            "appdirs",
            "pkg_resources._vendor.packaging",
            "pyparsing",
            "email.mime.application",
            "email.mime.audio",
            "email.mime.base",
            "email.mime.image",
            "email.mime.message",
            "email.mime.multipart",
            "email.mime.nonmultipart",
            "email.mime.text",
        ],
    )
    opts.setdefault('data_files', []).extend(fixup_data_pytz_zoneinfo())
    opts.update(cmdclass={'py2exe': custom_py2exe},)

    version_dash_incompatible = True
except ImportError:
    opts = {}
if version_dash_incompatible:
    version = version.split('-')[0]

FILE_PATTERNS = \
    r'.+\.(py|cfg|po|pot|mo|txt|rst|gif|png|jpg|ico|mako|html|js|css|htc|swf)$'
def find_data_files(source, patterns=FILE_PATTERNS):
    file_matcher = re.compile(patterns, re.I)
    out = []
    for base, _, files in os.walk(source):
        cur_files = []
        for f in files:
            if file_matcher.match(f):
                cur_files.append(os.path.join(base, f))
        if cur_files:
            out.append(
                (base, cur_files))

    return out

setup(
    name=name,
    version=version,
    description=description,
    long_description=long_description,
    author=author,
    author_email=author_email,
    url=url,
    download_url=download_url,
    license=license,
    python_requires = ">=2.7.12",
    install_requires=[
        "CherryPy==10.2.1",
        "Mako==1.0.6",
        "Babel==2.4.0",
        "formencode==1.3.1",
        "simplejson==3.10.0",
        "python-dateutil==2.6.0",
        "pytz==2017.2",
        "appdirs==1.4.3",
    ],
    zip_safe=False,
    packages=[
        'openobject',
        'openobject.admin',
        'openobject.admin.i18n',
        'openobject.controllers',
        'openobject.i18n',
        'openobject.test',
        'openobject.tools',
        'openobject.widgets'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Environment :: Web Environment',
        'Topic :: Office/Business :: Financial',
    ],
    scripts=['scripts/openerp-web'],
    data_files=(find_data_files('addons/openerp')
                + find_data_files('addons/view_calendar')
                + find_data_files('addons/view_diagram')
                + find_data_files('addons/view_graph')
                + find_data_files('addons/widget_ckeditor')
                + find_data_files('addons/sync_client_web')
                + find_data_files('doc', patterns='')
                + find_data_files('openobject', patterns=r'.+\.(cfg|css|js|mako|gif|png|jpg|ico)')
                + find_data_files('revprox', patterns='')
                + opts.pop('data_files', [])
                ),
    **opts
)
