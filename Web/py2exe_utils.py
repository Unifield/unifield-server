import os
import glob
import babel.localedata

__all__ = ['opts']

opts = {
    'console': ['scripts/openerp-web'],
    'options': {'py2exe': {
        'compressed': True,
        'optimize': 2,
        'bundle_files': 2,
        'includes': [
            'mako', 'cherrypy', 'babel', 'formencode', 'simplejson', 'csv',
            'dateutil.relativedelta', 'pytz', 'xml.dom.minidom', 'cgitb',
            'mako.cache', 'zipfile', 'email', 'email.utils', 'email.iterators',
            'email.message','functools'
        ],
        'excludes': [
            'Carbon', 'Carbon.Files', 'Crypto', 'DNS', 'OpenSSL', 'Tkinter',
            '_scproxy', 'elementtree.ElementTree', 'email.Header',
            'flup.server.fcgi', 'flup.server.scgi',
            'markupsafe._speedups', 'memcache', 'mx', 'pycountry', 'routes',
            'simplejson._speedups', 'turbogears.i18n', 'win32api', 'win32con',
            'win32event', 'win32pipe', 'win32service', 'win32serviceutil'
        ],
        'dll_excludes': [
            'w9xpopen.exe', 'POWRPROF.dll', 'CRYPT32.dll', 'MPR.dll',
        ]
    }},
    'data_files' : [
        ('babel/localedata', glob.glob(os.path.join(babel.localedata._dirname, '*.dat'))),
        ('babel', glob.glob(os.path.join(os.path.dirname(babel.__file__), 'global.dat'))),
    ]
}
