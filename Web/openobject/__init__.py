import logging
import os
import sys


libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lib')
if os.path.exists(libdir) and libdir not in sys.path:
    sys.path.insert(0, libdir)

import cherrypy
from logging import handlers

__all__ = ['ustr', 'application', 'configure', 'enable_static_paths',
           'WSGI_STATIC_PATHS']

# handle static files & paths via the WSGI server
# (using cherrypy's tools.staticfile and tools.staticdir)
WSGI_STATIC_PATHS = False

def ustr(value):
    """This method is similar to the builtin `str` method, except
    it will return Unicode string.

    @param value: the value to convert

    @rtype: unicode
    @return: unicode string
    """

    if isinstance(value, str):
        return value

    if hasattr(value, "__unicode__"):
        return str(value)

    if isinstance(value, bytes):
        return str(value, 'utf8')

    try: # first try without encoding
        return str(value)
    except:
        pass

    try: # then try with utf-8
        return str(value, 'utf8')
    except:
        pass

    try: # then try with extened iso-8858
        return str(value, 'iso-8859-15')
    except:
        pass

    try:
        return ustr(str(value))
    except:
        return " ".join([ustr(s) for s in value])

from . import controllers
import openobject

application = cherrypy.tree.mount(controllers._root.Root(), '/')
def enable_static_paths():
    ''' Enables handling of static paths by CherryPy:
    * /openobject/static
    * /favicon.ico
    * LICENSE.txt
    '''
    global WSGI_STATIC_PATHS
    WSGI_STATIC_PATHS = True

    static_dir = os.path.abspath(
        openobject.paths.root('openobject', 'static'))
    application.merge(
        {
            '/openobject/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': static_dir,
                'tools.sessions.on': False,
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.sessions.on': False,
                'tools.staticfile.filename': os.path.join(static_dir,
                                                          "images", "favicon.ico")
            },
            '/LICENSE.txt': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': os.path.join(static_dir, '..', '..',
                                                          'doc', 'LICENSE.txt')
            }})

BASE_CONFIG = {
    # Conversion of input parameters via formencode.variabledecode.NestedVariables
    'tools.nestedvars.on': True
}
def configure(app_config):
    """ Configures OpenERP Web Client. Takes a configuration dict
    (as output by cherrypy._cpconfig.as_dict), from it configures
    cherrypy globally and configure the OpenERP WSGI Application.
    """
    _global = app_config.pop('global', {})

    if _global.get('log.error_file'):
        dirname = os.path.dirname(_global.get('log.error_file'))
        if dirname and not os.path.isdir(dirname):
            os.makedirs(dirname)

    cherrypy.config.update(BASE_CONFIG)
    cherrypy.config.update(_global)
    application.merge(app_config)

    # logging config
    log = cherrypy.log

    error_level = _global.get('log.error_level', 'WARNING')
    access_level = _global.get('log.access_level', 'INFO')
    log.error_log.setLevel(error_level)
    log.access_log.setLevel(access_level)

    rotate = getattr(log, 'rotate', None)
    if rotate is not None: # allow empty log.rotate dict
        # Replace cherrypy's FileHandlers by TimedRotatingFileHandler
        access_file  = log.access_file
        error_file = log.error_file
        for handler in cherrypy.log.error_log.handlers:
            cherrypy.log.error_log.removeHandler(handler)

        for handler in cherrypy.log.access_log.handlers:
            cherrypy.log.access_log.removeHandler(handler)

        # Make a new RotatingFileHandler for the error log.
        error_handler = handlers.TimedRotatingFileHandler(error_file, **rotate)
        error_handler.setLevel(error_level)
        log.error_log.addHandler(error_handler)
        log.error_file = ''

        # Make a new RotatingFileHandler for the access log.
        if access_file:
            access_handler = handlers.TimedRotatingFileHandler(access_file, **rotate)
            access_handler.setLevel(access_level)
            log.access_log.addHandler(access_handler)
            log.access_file = ''
