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
import re
import os
import sys

import cherrypy
from openerp.utils import rpc

from openobject import tools
from openobject import paths
from openobject.tools._expose import expose
from openobject.tools._utils import redirect
import openobject
from openobject import ustr
from openobject.i18n import _

__all__ = ["secured", "unsecured", "login", "change_password"]

def get_db_list():
    dblist = []

    result = {
        'bad_regional':'',
        'tz_offset':'',
        'dblist': []
    }

    if os.name == 'nt':
        try:
            import winreg
            reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 "Control Panel\\International", 0, winreg.KEY_READ)
            value, regtype = winreg.QueryValueEx(reg, "LocaleName")
            winreg.CloseKey(reg)
            if value != 'en-US':
                result['bad_regional'] = _("On the server system user account must have English (United States) as Format in the regional settings")
        except:
            pass
    try:
        dblist = rpc.session.listdb()
        result['tz_offset'] = rpc.session.gateway.execute_noauth('db', 'check_timezone')
    except:
        pass
        #message = _("Could not connect to server")

    dbfilter = cherrypy.request.app.config['openerp-web'].get('dblist.filter')
    if dbfilter:
        headers = cherrypy.request.headers
        host = headers.get('X-Forwarded-Host', headers.get('Host'))

        base = re.split('\.|:|/', host)[0]

        if dbfilter == 'EXACT':
            if dblist is None:
                db = base
                dblist = [db]
            else:
                dblist = [d for d in dblist if d == base]

        elif dbfilter == 'UNDERSCORE':
            base = base + '_'
            if dblist is None:
                if db and not db.startswith(base):
                    db = None
            else:
                dblist = [d for d in dblist if d.startswith(base)]

        elif dbfilter == 'BOTH':
            if dblist is None:
                if db and db != base and not db.startswith(base + '_'):
                    db = None
            else:
                dblist = [d for d in dblist if d.startswith(base + '_') or d == base]
    result['dblist'] = dblist
    return result

@expose(template="/openerp/controllers/templates/login.mako")
def login(target, db=None, user=None, password=None, action=None, message=None, origArgs={}, auto=True):

    url = rpc.session.connection_string
    url = str(url[:-1])

    config_file_name = 'uf_auto_install.conf'
    if sys.platform == 'win32':
        config_file_path = os.path.join(paths.root(), '..', 'UFautoInstall', config_file_name)
    else:
        config_file_path = os.path.join(paths.root(), '..', 'unifield-server', 'UFautoInstall', config_file_name)
    if auto and os.path.exists(config_file_path):
        raise redirect('/openerp/database/auto_create')

    result = get_db_list()
    dblist = result['dblist']
    bad_regional = result['bad_regional']
    tz_offset = result['tz_offset']

    info = None
    try:
        info = rpc.session.execute_noauth('common', 'login_message') or ''
    except:
        pass
    do_login_page = '/openerp/do_login'
    if target != do_login_page:
        origArgs['target'] = target
    return dict(target=do_login_page, url=url, dblist=dblist, db=db, user=user, password=password,
                action=action, message=message, origArgs=origArgs, info=info, bad_regional=bad_regional, tz_offset=tz_offset)

@expose(template="/openerp/controllers/templates/change_password.mako")
def change_password(target, db=None, user=None, password=None,
                    action=None, message=None, origArgs=None, expired=False):

    if origArgs is None:
        origArgs = {}
    url = rpc.session.connection_string
    url = str(url[:-1])

    result = get_db_list()
    dblist = result['dblist']
    bad_regional = result['bad_regional']
    tz_offset = result['tz_offset']

    new_password = origArgs.get('new_password', None)
    confirm_password = origArgs.get('confirm_password', None)

    info = None
    do_change_password_page = '/openerp/do_change_password'
    if target != do_change_password_page:
        origArgs['target'] = target
    return dict(target=do_change_password_page, url=url, dblist=dblist, db=db,
                user=user, password=password, new_password=new_password,
                confirm_password=confirm_password, action=action, message=message,
                origArgs=origArgs, info=info, bad_regional=bad_regional, tz_offset=tz_offset, expired=expired)

def secured(fn):
    """A Decorator to make a SecuredController controller method secured.
    """
    def clear_login_fields(kw):

        if not kw.get('login_action'):
            return

        for k in ('db', 'user', 'password'):
            kw.pop(k, None)
        for k in list(kw.keys()):
            if k.startswith('login_'):
                del kw[k]

    def clear_change_password_fields(kw):
        for k in ('db', 'user', 'password', 'new_password', 'confirm_password'):
            if k in kw:
                kw.pop(k, None)
        for k in list(kw.keys()):
            if k.startswith('login_'):
                del kw[k]


    def get_orig_args(kw):
        if not kw.get('login_action'):
            return kw

        new_kw = kw.copy()
        clear_login_fields(new_kw)
        return new_kw

    def wrapper(*args, **kw):
        """The wrapper function to secure exposed methods
        """

        if rpc.session.is_logged() and kw.get('login_action') != 'login':
            # User is logged in and don't need to change his password; allow access
            if fn.__name__ in ('get', 'kill_search_filter'):
                # do not lock session on search view
                clear_login_fields(kw)
                return fn(*args, **kw)

            cherrypy.session.acquire_lock()
            try:
                clear_login_fields(kw)
                return fn(*args, **kw)
            finally:
                cherrypy.session.release_lock()
        else:
            action = kw.get('login_action', '')
            # get some settings from cookies
            try:
                db = cherrypy.request.cookie['terp_db'].value
                user = cherrypy.request.cookie['terp_user'].value
            except:
                db = ''
                user = ''

            db = kw.get('db', db)
            user = ustr(kw.get('user', user))
            password = kw.get('password', '')

            # See if the user just tried to log in
            login_ret = rpc.session.login(db, user, password)
            if action == 'login' and login_ret == -2:
                return login(cherrypy.request.path_info, message=_('Database newer than UniField version'),
                             db=db, user=user, action=action, origArgs=get_orig_args(kw))
            if action == 'login' and login_ret == -3:
                nb_mod = rpc.session.number_update_modules(db) or ''
                return login(cherrypy.request.path_info, message=_('The server is updating %s modules, please wait ...') % (nb_mod,),
                             db=db, user=user, action=action, origArgs=get_orig_args(kw))
            if action == 'login' and login_ret == -4:
                return login(cherrypy.request.path_info, message=_('A script during patch failed! Login is forbidden for the moment. Please contact your administrator'),
                             db=db, user=user, action=action, origArgs=get_orig_args(kw))
            if action == 'login' and login_ret == -8:
                return login(cherrypy.request.path_info, message=_('Login refused. The database restoration has failed, please delete it and try again'),
                             db=db, user=user, action=action, origArgs=get_orig_args(kw))
            if action == 'login' and login_ret in (-5, -7):  # must change password
                if 'confirm_password' in kw:
                    message = rpc.session.change_password(db, user, password, kw['new_password'], kw['confirm_password'])
                    if message is not True:
                        clear_change_password_fields(kw)
                        result = change_password(cherrypy.request.path_info,
                                                 message=message, db=db, user=user, password=password,
                                                 action=action, origArgs=get_orig_args(kw), expired=login_ret==-7)
                        clear_change_password_fields(kw)

                        return result
                    clear_change_password_fields(kw)
                    return login(cherrypy.request.path_info,
                                 message=_('Password changed.'),
                                 db=db, user=user, action=action, origArgs=get_orig_args(kw))

                result = change_password(cherrypy.request.path_info,
                                         message=_('You have to change your password.'),
                                         db=db, user=user, password=password, action=action, origArgs=get_orig_args(kw), expired=login_ret==-7)
                clear_change_password_fields(kw)
                return result
            elif action == 'login' and login_ret == -6:
                return login(cherrypy.request.path_info, message=_('Your IP have been blocked because of too many bad login attempts. It will be unblocked after %s minutes.') % rpc.BLOCKED_MIN_COUNT,
                             db=db, user=user, action=action, origArgs=get_orig_args(kw))
            elif login_ret <= 0:
                # Bad login attempt
                if action == 'login':
                    message = _("Bad username or password")
                    clear_change_password_fields(kw)
                    return login(cherrypy.request.path_info, message=message,
                                 db=db, user=user, action=action, origArgs=get_orig_args(kw))
                else:
                    message = ''

                kwargs = {}
                if action: kwargs['action'] = action
                if message: kwargs['message'] = message
                base = cherrypy.request.path_info
                if cherrypy.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    cherrypy.response.status = 401
                    next_key = 'next'
                else:
                    cherrypy.response.status = 303
                    next_key = 'location' # login?location is the redirection destination w/o next

                if base and base != '/' and cherrypy.request.method == 'GET':
                    kwargs[next_key] = "%s?%s" % (base, cherrypy.request.query_string)

                login_url = openobject.tools.url(
                    '/openerp/login', db=db, user=user, **kwargs
                )
                cherrypy.response.headers['Location'] = login_url
                return """
                    <html>
                        <head>
                            <script type="text/javascript">
                                window.location.href="%s"
                            </script>
                        </head>
                        <body>
                        </body>
                    </html>
                """%(login_url)

            # Authorized. Set db, user name in cookies
            cookie = cherrypy.response.cookie
            cookie['terp_db'] = db
            cookie['terp_user'] = user
            cookie['terp_db']['max-age'] = 3600
            cookie['terp_user']['max-age'] = 3600
            cookie['terp_db']['path'] = '/'
            cookie['terp_user']['path'] = '/'

            # User is now logged in, so show the content
            clear_login_fields(kw)
            return fn(*args, **kw)

    return tools.decorated(wrapper, fn, secured=True)


def unsecured(fn):
    """A Decorator to make a SecuredController controller method unsecured.
    """

    def wrapper(*args, **kw):
        return fn(*args, **kw)

    return tools.decorated(wrapper, fn, secured=False)


# vim: ts=4 sts=4 sw=4 si et
