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
import sys

import cherrypy
from openerp.utils import rpc
from cherrypy import _cperror
import openobject.errors
from openobject.controllers import BaseController
from openobject.tools import expose, redirect
from openobject.i18n import _
import logging

_cperror._HTTPErrorTemplate = '''<!DOCTYPE html PUBLIC
"-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"></meta>
    <title>%(status)s</title>
    <style type="text/css">
    #powered_by {
        margin-top: 20px;
        border-top: 2px solid black;
        font-style: italic;
    }

    #traceback {
        color: red;
    }
    </style>
</head>
    <body>
        <h2>%(status)s</h2>
        <p>%(message)s</p>
        <pre id="traceback">%(traceback)s</pre>
    <div id="powered_by">
    </div>
    </body>
</html>
'''

class ErrorPage(BaseController):

    _cp_path = "/openerp/errorpage"

    @expose()
    def index(self, *args, **kw):
        raise redirect('/openerp')

    def render(self):
        etype, value, tb = sys.exc_info()

        if isinstance(value, openobject.errors.Concurrency):
            return self.__render(value)

        if not isinstance(value, openobject.errors.TinyException):
            full_tb = _cperror.format_exc()
            tb = ''
            if hasattr(rpc.session, 'uid') and rpc.session.is_logged():
                tb = full_tb
            cherrypy.log.error("500 %s" % full_tb, severity=logging.ERROR)
            return _cperror.get_error_page(500, traceback=tb)

        return self.__render(value)

    @expose(template="/openerp/controllers/templates/error_page.mako")
    def __render(self, value):

        maintenance = None
        concurrency = False

        all_params = cherrypy.request.params

        title=value.title
        error=value.message


        target = cherrypy.request.path_info or '/openerp/form/save'

        if isinstance(value, openobject.errors.Concurrency):
            concurrency = True

        if isinstance(value, openobject.errors.TinyError):
            proxy = rpc.RPCProxy('maintenance.contract')
            maintenance = proxy.status()
            cherrypy.response.headers['X-Maintenance-Error'] = "1"

        return dict(title=title, error=error, maintenance=maintenance,
                    concurrency=concurrency, all_params=all_params, target=target, tb=_cperror.format_exc())

    @expose('json')
    def submit(self, tb, explanation, remarks, name):
        try:
            res = rpc.RPCProxy('maintenance.contract').send(tb, explanation, remarks, name)
            if res:
                return dict(message=_('Your problem has been sent to the quality team\nWe will recontact you after analysing the problem.'))
            else:
                return dict(error=_('Your problem could not be sent to the quality team\nPlease report this error manually at %s') % ('support@openerp.com'))
        except Exception as e:
            return dict(error=str(e))

_ep = ErrorPage()

# vim: ts=4 sts=4 sw=4 si et

