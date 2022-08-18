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

import socket
import xmlrpc.client

import openobject.errors

from . import common

from .tiny_socket import TinySocket
from .tiny_socket import TinySocketError
from datetime import datetime, timedelta
from collections import OrderedDict
import cherrypy
from openobject import ustr
from openobject.i18n import _

MAX_IP_COLLECTION = 50
BLOCKED_MIN_COUNT = 5
MAX_BAD_LOGIN = 5


class NotLoggedIn(openobject.errors.TinyError, openobject.errors.AuthenticationError): pass

class RPCException(Exception):
    """A common exeption class for RPC errors.
    """

    def __init__(self, code, backtrace):

        self.code = code
        self.args = backtrace

        if hasattr(code, 'split'):
            lines = code.split('\n')

            self.type = lines[0].split(' -- ')[0]
            self.message = ''
            if len(lines[0].split(' -- ')) > 1:
                self.message = lines[0].split(' -- ')[1]

            self.data = '\n'.join(lines[2:])

        else:
            self.type = 'error'
            self.message = backtrace
            self.data = backtrace

        self.backtrace = backtrace

    def __str__(self):
        return self.message


class RPCGateway(object):
    """Gateway abstraction, that implement common stuffs for rpc gateways.
    All RPC gateway should extends this class.
    """

    def __init__(self, session):
        if not isinstance(session, RPCSession):
            raise TypeError("RPCSession argument expected, got %s" % type(session))
        self.socket_timeout = cherrypy.config.get('openerp.server.timeout')
        self.session = session

    def __rpc__(self, obj, method, args=(), auth=True):
        """Derived classes should owverride this method.

        @param obj: the remote object
        @param method: the method of the remote object
        @param args: arguments to be passed
        @param oauth: authentication is required or not

        @return: the result of the method
        """
        pass

    @property
    def connection_string(self):
        """Get the connection string...
        """
        return "%s://%s:%s/"%(self.session.protocol, self.session.host, self.session.port)

    def __convert(self, result):

        if isinstance(result, str):
            # try to convert into unicode string
            try:
                return ustr(result)
            except Exception:
                return result

        elif isinstance(result, list):
            return [self.__convert(val) for val in result]

        elif isinstance(result, tuple):
            return tuple([self.__convert(val) for val in result])

        elif isinstance(result, dict):
            newres = {}
            for key, val in list(result.items()):
                newres[key] = self.__convert(val)

            return newres

        else:
            return result

    def __execute(self, obj, method, args=(), auth=True):
        try:
            result = self.__rpc__(obj, method, args, auth=auth)
            return self.__convert(result)
        except socket.error as e:
            if hasattr(e, 'message'):
                error = e.message
            else:
                error = e.strerror
            raise openobject.errors.TinyException(error, title=_('Application Error'))

        except RPCException as err:
            if err.type in ('warning', 'UserError'):
                if err.message in ('ConcurrencyException') and len(args) > 4:
                    common.concurrency(err.message, err.data, args)
                else:
                    common.warning(err.data)
            elif err.code.startswith('updater.py'):
                common.error('updater.py', err.code)
            elif err.code.startswith('ServerUpdate'):
                common.error('ServerUpdate', err.code)
            elif err.code.startswith('ForcePasswordChange'):
                common.error('ForcePasswordChange', err.code)
            elif err.code.startswith('PasswordExpired'):
                common.error('PasswordExpired', err.code)
            elif err.code.startswith('PatchFailed'):
                common.error('PatchFailed', err.code)
            elif err.code.startswith('AccessDenied'):
                raise openobject.errors.AccessDenied(err.code, _('Access Denied'))
            elif err.code.startswith('BadRestoration'):
                common.error('BadRestoration', err.code)
            else:
                common.error(_('Application Error'), err.backtrace)

        except Exception as e:
            common.error(_('Application Error'), str(e))

    def execute(self, obj, method, *args):
        """Excecute the method of the obj with the given arguments.

        @param obj: the remote object
        @param method: the method of the remote object
        @param args: arguments to be passed

        @return: the result of the method
        """
        return self.__execute(obj, method, args)

    def execute_noauth(self, obj, method, *args):
        """Excecute the method of the obj with the given arguments without authentication.

        @param obj: the object
        @param method: the method to execute
        @param args: the arguments

        @return: the result of the method
        """
        return self.__execute(obj, method, args, auth=False)


class XMLRPCGateway(RPCGateway):
    """XMLRPC implementation.
    """

    def __init__(self, session):
        """Create new instance of XMLRPCGateway.

        @param session: a session
        """
        super(XMLRPCGateway, self).__init__(session)
        self._url = self.connection_string + 'xmlrpc/'

    def __rpc__(self, obj, method, args=(), auth=True):
        sock = xmlrpc.client.ServerProxy(self._url + str(obj))
        try:
            if auth:
                args = (self.session.db, self.session.uid, self.session.password) + args
            return getattr(sock, method)(*args)
        except xmlrpc.client.Fault as err:
            raise RPCException(err.faultCode, err.faultString)


class NETRPCGateway(RPCGateway):
    """NETRPC Implementation.
    """

    def __rpc__(self, obj, method, args=(), auth=True):
        sock = TinySocket()
        try:
            sock.connect(self.session.host, self.session.port)
            sock.sock.settimeout(self.socket_timeout)
            if auth:
                args = (self.session.db, self.session.uid, self.session.password) + args
            sock.send((obj, method) + args)
            res = sock.receive()
            sock.disconnect()
            return res

        except xmlrpc.client.Fault as err:
            raise RPCException(err.faultCode, err.faultString)

        except TinySocketError as err:
            raise RPCException(err.faultCode, err.faultString)


# XXX: Fix openobject server to return PyTZ compatible timezone name
_TZ_ALIASES = {
    'IST' : 'Asia/Calcutta'
}


class RPCSession(object):
    """Maintains client session and provides way to authenticate
    client & invoce RPC requested by clients.
    """

    __slots__ = ['host', 'port', 'protocol', 'storage', 'gateway']
    connection_attempt_dict = OrderedDict()  # an OrderedDict is needed here to
    # be able to remove old entries

    def __init__(self, host, port, protocol='socket', storage={}):
        """Create new instance of RPCSession.

        @param host: the openobject-server host
        @params port: the openobject-server port
        @params protocol: the openobject-server protocol
        @param storage: a dict like storage that will be used to store session data
        """
        self.host = host
        self.port = port
        self.protocol = protocol
        self.storage = storage

        if protocol in ('http', 'https'):
            self.gateway = XMLRPCGateway(self)

        elif protocol == 'socket':
            self.gateway = NETRPCGateway(self)

        else:
            raise common.message(_("Unsupported protocol."))

    def __getattr__(self, name):
        try:
            return super(RPCSession, self).__getattribute__(name)
        except:
            pass

        return self.storage.get(name)

    def __setattr__(self, name, value):
        if name in self.__slots__:
            super(RPCSession, self).__setattr__(name, value)
        else:
            self.storage[name] = value

    def __getitem__(self, name):
        return self.storage[name]

    def __setitem__(self, name, value):
        self.storage[name] = value

    def __delitem__(self, name):
        try:
            del self.storage[name]
        except:
            pass

    def get(self, name, default=None):
        return self.storage.get(name, default)

    @property
    def context(self):
        return (self._context or {}).copy()

    @property
    def connection_string(self):
        return self.gateway.connection_string

    def listdb(self):
        try:
            return self.execute_noauth('db', 'list')
        except openobject.errors.TinyError as e:
            if e.message == 'AccessDenied':
                return None
            raise

    def unifield_version(self):
        return self.execute_noauth('db', 'server_version')

    def number_update_modules(self, db):
        return self.execute_noauth('common', 'number_update_modules', db)

    def unban(self, ip_address):
        if ip_address in self.connection_attempt_dict:
            self.connection_attempt_dict.pop(ip_address)

    def is_banned(self, ip_address):
        '''Return True if the ip is banned and cannot retry login before a
        certain amount of time
        '''
        if ip_address in self.connection_attempt_dict and\
                self.connection_attempt_dict[ip_address].get('fail_login_count') >= MAX_BAD_LOGIN:
            current_time = datetime.now()
            last_attempt_time = self.connection_attempt_dict[ip_address]['last_attempt_time']

            if current_time - last_attempt_time > timedelta(minutes=BLOCKED_MIN_COUNT):
                # the ip ban is over, delete it from the dict
                self.unban(ip_address)
                return False
            return True
        else:
            return False

    def fail_login_attempt(self, ip_address):
        '''Increase the counter of fail login attemps'''
        if ip_address in self.connection_attempt_dict:
            self.connection_attempt_dict[ip_address]['fail_login_count'] += 1
        else:
            if len(self.connection_attempt_dict) >= MAX_IP_COLLECTION:
                # the max size of the dict has been reach. To prevent fulfill
                # the memory by multi-ip login attempt, remove the first imput
                # element (FIFO) before to add a new one.
                self.connection_attempt_dict.popitem(last=False)
            self.connection_attempt_dict[ip_address] = {'fail_login_count': 1}
        self.connection_attempt_dict[ip_address]['last_attempt_time'] = datetime.now()

    def login(self, db, user, password):

        if not (db and user and password):
            return -1

        client_ip = cherrypy.request.wsgi_environ.get('HTTP_X_FORWARDED_FOR', False) \
            or cherrypy.request.wsgi_environ.get('REMOTE_ADDR', 'NO_IP_FOUND')

        if self.is_banned(client_ip):
            return -6

        try:
            uid = self.execute_noauth('common', 'login', db, user, password)
            if uid is False:
                self.fail_login_attempt(client_ip)
            else:
                self.unban(client_ip)
        except Exception as e:
            if e.title == 'updater.py':
                return -2
            elif e.title == 'ServerUpdate':
                return -3
            elif e.title == 'PatchFailed':
                return -4
            elif e.title == 'ForcePasswordChange':
                return -5
            elif e.title == 'PasswordExpired':
                return -7
            elif e.title == 'BadRestoration':
                return -8
            return -1

        if uid <= 0:
            return -1

        self._logged_as(db, uid, password)
        return uid

    def _logged_as(self, db, uid, password):
        self.storage['uid'] = uid
        self.storage['db'] = db
        self.storage['password'] = password
        self.storage['open'] = True

        # read the full name of the user
        res_users = self.execute('object', 'execute', 'res.users', 'read',
                                 [uid], ['name', 'company_id', 'login', 'force_password_change'])[0]
        self.storage['user_name'] = res_users['name']
        self.storage['company_id'], self.storage['company_name'] = res_users['company_id']
        self.storage['loginname'] = res_users['login']
        self.storage['force_password_change'] = res_users['force_password_change']

        # set the context
        self.context_reload()

    def logout(self):
        try:
            self.storage.clear()
            cherrypy.session.delete()
        except Exception:
            pass

    def is_logged(self):
        return self.uid and self.open

    def change_password(self, db, user, password, new_password,
                        confirm_password):

        if not (db and user and password and new_password and confirm_password):
            return _('All fields are required.')

        try:
            error_message = self.execute_noauth('common', 'change_password', db, user,
                                                password, new_password, confirm_password)
        except Exception as e:
            error_message = e.message
        return error_message

    def context_reload(self):
        """Reload the context for the current user
        """

        self.storage['_context'] = {'client': 'web'}

        # self.uid
        context = self.execute('object', 'execute', 'res.users', 'context_get')
        self._context.update(context or {})

        self.storage['remote_timezone'] = 'utc'
        self.storage['client_timezone'] = self.context.get("tz", False)

        if self.storage.get('client_timezone'):
            self.storage['remote_timezone'] = self.execute('common', 'timezone_get')
            try:
                import pytz
                assert pytz
            except:
                raise common.warning(_('You select a timezone but OpenERP could not find pytz library!\nThe timezone functionality will be disable.'))

        # set locale in session
        self.storage['locale'] = self.context.get('lang', 'en_US')
        lang_ids = self.execute(
            'object', 'execute', 'res.lang',
            'search', [('code', '=', self.storage['locale'])])
        if lang_ids:
            self.storage['lang'] = self.execute(
                'object', 'execute', 'res.lang', 'read', lang_ids[0], [])

    def execute(self, obj, method, *args):
        if not self.is_logged():
            raise NotLoggedIn(_('Not logged...'), _('Authorization Error'))

        self.socket_timeout = cherrypy.config.get('openerp.server.timeout')
        return self.gateway.execute(obj, method, *args)

    def execute_noauth(self, obj, method, *args):
        return self.gateway.execute_noauth(obj, method, *args)

    def execute_db(self, method, *args):
        self.gateway.socket_timeout = cherrypy.config.get('openerp.server.timeout') * 10
        cherrypy.response.timeout = 60000
        return self.execute_noauth('db', method, *args)


# global session variable, will be initialized with connect
session = None


def initialize(host, port, protocol='socket', storage=None):
    """ Initialize the default rpc session.
    """
    global session
    session = RPCSession(host, port, protocol, storage=storage)


class RPCProxy(object):
    """A wrapper arround xmlrpclib, provides pythonic way to access tiny resources.

    For example,

    >>> users = RPCProxy("ir.users")
    >>> res = users.read([1], ['name', 'active_id'], session.context)
    """

    def __init__(self, resource):
        """Create new instance of RPCProxy for the give tiny resource

        @param resource: the tinyresource
        """
        self._resource = resource
        self._session = session
        self._attrs = {}

    def _func_getter(self, name):
        return lambda *args: self(name, *args)

    def __getattr__(self, name):
        if name not in self._attrs:
            return self._attrs.setdefault(name, self._func_getter(name))
        return self._attrs[name]

    def __call__(self, *args):
        return self._session.execute('object', 'execute',
                                     self._resource, *args)

    def fields_get(self, fields, context=None, with_uom_rounding=False):
        if context is None:
            context = self._session.context
        return self('fields_get', fields, context, with_uom_rounding)
    def fields_view_get(self, view_id, view_type, context=None,
                        hastoolbar=False, hassubmenu=False):
        if context is None:
            context = self._session.context
        return self('fields_view_get', view_id or False, view_type, context,
                    hastoolbar, hassubmenu)

    def search(self, criteria, offset=0, limit=False, order=False, context=None):
        if context is None:
            context = self._session.context
        return self('search_web', criteria, offset, limit, order, context)

def name_get(model, id, context=None):

    id = (id or False) and int(id)
    name = (id or str('')) and str(id)

    if model and id:

        ctx = session.context.copy()
        ctx.update(context or {})

        proxy = RPCProxy(model)

        try:
            name = proxy.name_get([id], ctx)
            name = name and name[0][1] or ''
        except openobject.errors.TinyWarning:
            name = _("== Access Denied ==")

    return name


if __name__=="__main__":

    host = 'localhost'
    port = 8070
    protocol = 'socket'

    initialize(host, port, protocol, storage=dict())

    res = session.listdb()
    print(res)

    res = session.login('t1', 'admin', 'admin')
    print(res)

    res = RPCProxy('res.users').read([session.uid], ['name'])
    print(res)

    print((session.context))


# vim: ts=4 sts=4 sw=4 si et
