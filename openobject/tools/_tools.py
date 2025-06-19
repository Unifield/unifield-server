###############################################################################
#
#  Copyright (C) 2007-TODAY OpenERP SA. All Rights Reserved.
#
#  $Id$
#
#  Developed by OpenERP (http://openerp.com) and Axelor (http://axelor.com).
#
#  The OpenERP web client is distributed under the "OpenERP Public License".
#  It's based on Mozilla Public License Version (MPL) 1.1 with following
#  restrictions:
#
#  -   All names, links and logos of OpenERP must be kept as in original
#      distribution without any changes in all software screens, especially
#      in start-up page and the software header, even if the application
#      source code has been changed or updated or code has been added.
#
#  You can see the MPL licence at: http://www.mozilla.org/MPL/MPL-1.1.html
#
###############################################################################
import logging
#import urlparse
from urllib import parse
import cherrypy
from formencode import NestedVariables
import sys
from datetime import datetime
import pytz
from dateutil import relativedelta


def nestedvars_tool():
    if hasattr(cherrypy.request, 'params'):
        cherrypy.request.params = NestedVariables.to_python(cherrypy.request.params or {})

cherrypy.tools.nestedvars = cherrypy.Tool("before_handler", nestedvars_tool)
cherrypy.lowercase_api = True

def csrf_check():
    if not cherrypy.request.method == 'POST': return;

    referer = cherrypy.request.headers.get('Referer', '')
    if not(parse.urlsplit(referer).path and referer.startswith(cherrypy.request.base)):
        raise cherrypy.HTTPError(403, "Request Forbidden -- You are not allowed to access this resource.")
cherrypy.tools.csrf = cherrypy.Tool('before_handler', csrf_check)

def cgitb_traceback(ignore=None, severity=logging.DEBUG):
    typ, value, tb = sys.exc_info()
    if ignore and issubclass(typ, tuple(ignore)):
        return
    cherrypy.log('', 'HTTP', severity=severity, traceback=True)
cherrypy.tools.cgitb = cherrypy.Tool('before_error_response', cgitb_traceback)

def cookie_secure_flag():
    """Add the secure cookie attribute."""
    name = cherrypy.request.config.get('tools.sessions.name', 'session_id')
    if cherrypy.response.cookie.get(name):
        cherrypy.response.cookie[name]['secure'] = 1
cherrypy.tools.secure_cookies = cherrypy.Tool('before_finalize', cookie_secure_flag)

def cookie_httponly_flag():
    """Add the HttpOnly cookie attribute."""
    name = cherrypy.request.config.get('tools.sessions.name', 'session_id')
    if cherrypy.response.cookie.get(name):
        cherrypy.response.cookie[name]['httponly'] = 1
cherrypy.tools.httponly_cookies = cherrypy.Tool('before_finalize', cookie_httponly_flag)

def no_session_refresh():
    cherrypy.serving.request._sessionsaved = True
    cherrypy.serving.response.cookie.clear()

def cookie_fix_312_session_persistent_flag():
    """Fix cherrypy 3.1.2 tools.session.persistant = False"""
    from addons.openerp.utils import rpc
    name = cherrypy.request.config.get('tools.sessions.name', 'session_id')
    if cherrypy.request.config.get('tools.sessions.persistent', True):
        if 'expires' in cherrypy.response.cookie.get(name, {}) and cherrypy.session.timeout:
            if hasattr(rpc.session, 'uid') and rpc.session.is_logged():
                cherrypy.response.cookie['session_expired'] = (datetime.now(pytz.utc)+relativedelta.relativedelta(minutes=cherrypy.session.timeout)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
                cherrypy.response.cookie['session_expired']['path'] = '/'
            else:
                cherrypy.response.cookie['session_expired'] = ''
        return True
    cherrypy.response.cookie['session_expired'] = ''
    return True
cherrypy.tools.fix_312_session_persistent = cherrypy.Tool('before_finalize', cookie_fix_312_session_persistent_flag)
