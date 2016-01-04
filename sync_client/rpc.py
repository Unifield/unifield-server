#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
OpenObject Client Library
"""

import sys
import socket
import zlib
import xmlrpclib
from timeout_transport import TimeoutTransport
from gzip_xmlrpclib import GzipTransport, GzipSafeTransport
from osv import osv
from tools.translate import _
import tools

try:
    import cPickle as pickle
except:
    import pickle

try:
    import cStringIO as StringIO
except:
    import StringIO

import logging
#import logging.config

#logging.config.fileConfig('logging.cfg')

GZIP_MAGIC = '\x78\xda' # magic when max compression used
NB_RETRY = 10

# Safer Unpickler, in case the server is untrusted, from Nadia Alramli
# http://nadiana.com/python-pickle-insecure#How_to_Make_Unpickling_Safer
class SafeUnpickler(object):
    PICKLE_SAFE = {
        'exceptions': set(['Exception']),
    }

    @classmethod
    def find_class(cls, module, name):
        if not module in cls.PICKLE_SAFE:
            raise pickle.UnpicklingError(
                'Attempting to unpickle unsafe module %s' % module
            )
        __import__(module)
        mod = sys.modules[module]
        if not name in cls.PICKLE_SAFE[module]:
            raise pickle.UnpicklingError(
                'Attempting to unpickle unsafe class %s' % name
            )
        klass = getattr(mod, name)
        return klass

    @classmethod
    def loads(cls, pickle_string):
        pickle_obj = pickle.Unpickler(StringIO.StringIO(pickle_string))
        pickle_obj.find_global = cls.find_class
        return pickle_obj.load()


class Connector(object):
    """
    Connector class
    """

    _logger = logging.getLogger('connector')

    def __init__(self, hostname, port, timeout):
        """
        :param hostname: Host name of the server
        :param port: Port for the connection to the server
        """
        self.hostname = hostname
        self.port = port
        self.timeout = timeout

class XmlRPCConnector(Connector):
    """
    This class supports the XmlRPC protocol
    """
    PROTOCOL = 'xmlrpc'

    def __init__(self, hostname, port=8069, timeout=10.0, retry=0):
        Connector.__init__(self, hostname, port, timeout=timeout)
        self._logger = logging.getLogger('connector.xmlrpc')
        self.url = 'http://%s:%s/xmlrpc' % (self.hostname, self.port)
        self.retry = retry

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        transport = TimeoutTransport(timeout=self.timeout)
        service = xmlrpclib.ServerProxy(url, allow_none=1, transport=transport)
        return self._send(service, method, *args)

    def _send(self, service, method, *args):
        i = 0
        retry = True
        while retry:
            try:
                retry = False
                return getattr(service, method)(*args)
            except Exception, e:
                error = e
                if i < self.retry:
                    print 'retry xml_rpc', i
                    retry = True
                    self._logger.debug("retry to connect %s, error : %s" ,i, e)
                i += 1
        if error:
            raise osv.except_osv(_('Error!'), "Unable to proceed for the following reason:\n%s" % (e.faultCode if hasattr(e, 'faultCode') else tools.ustr(e)))


"""Modified version of xmlrcpclib.Transport.request (same in Python 2.4, 2.5, 2.6)
   to workaround Python bug http://bugs.python.org/issue1223
   for Python versions before 2.6
   This patch is inspired by http://www.cherrypy.org/ticket/743.
   See LP bug https://bugs.launchpad.net/openobject-client/+bug/673775
"""
def fixed_request(self, host, handler, request_body, verbose=0):
    h = self.make_connection(host)
    if verbose:
        h.set_debuglevel(1)
    self.send_request(h, handler, request_body)
    self.send_host(h, host)
    self.send_user_agent(h)
    self.send_content(h, request_body)
    errcode, errmsg, headers = h.getreply()
    if errcode != 200:
        raise xmlrpclib.ProtocolError(host + handler, errcode, errmsg,
                    headers)
    self.verbose = verbose
    # below we make sure to call parse_response() and
    # not _parse_response(), and don't pass the socket,
    # so it will have to use the file instead, and avoid
    # the problem of the original code.
    return self.parse_response(h.getfile())

# Rude monkey-patch to fix the SSL connection error in Python 2.5-,
# as last resort solution to fix it all at once.
if sys.version_info < (2,6):
    xmlrpclib.SafeTransport.request = fixed_request

class SecuredXmlRPCConnector(XmlRPCConnector):
    """
    This class supports the XmlRPC protocol over HTTPS
    """
    PROTOCOL = 'xmlrpcs'

    def __init__(self, hostname, port=8070, timeout=10.0, retry=0):
        XmlRPCConnector.__init__(self, hostname, port, timeout=timeout, retry=retry)
        self.url = 'https://%s:%s/xmlrpc' % (self.hostname, self.port)

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        service = xmlrpclib.ServerProxy(url, allow_none=1)
        return self._send(service, method, *args)

class GzipXmlRPCConnector(XmlRPCConnector):
    """
    This class supports the XmlRPC protocol with gzipped payload
    """
    PROTOCOL = 'gzipxmlrpc'

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        gzip_transport = GzipTransport(timeout=self.timeout)
        service = xmlrpclib.ServerProxy(url, allow_none=1, transport=gzip_transport)
        return self._send(service, method, *args)

class GzipXmlRPCSConnector(GzipXmlRPCConnector):
    PROTOCOL = 'gzipxmlrpcs'

    def __init__(self, hostname, port=8069, *args, **kwargs):
        GzipXmlRPCConnector.__init__(self, hostname, port, *args, **kwargs)
        self.url = 'https://%s:%s/xmlrpc' % (self.hostname, self.port)

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        gzip_safe_transport = GzipSafeTransport(timeout=self.timeout)
        service = xmlrpclib.ServerProxy(url, allow_none=1, transport=gzip_safe_transport)
        return getattr(service, method)(*args)

class NetRPC_Exception(Exception):
    def __init__(self, faultCode, faultString):
        self.faultCode = faultCode
        self.faultString = faultString
        self.args = (faultCode, faultString)

class NetRPC:
    def __init__(self, sock=None, is_gzip=False, timeout=10.0):
        if sock is None:
            self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.sock.settimeout(timeout)
        self.is_gzip = is_gzip
        self._logger = logging.getLogger('netrpc')

    def connect(self, host, port=False):
        if not port:
            protocol, buf = host.split('//')
            host, port = buf.split(':')
        try:
            self.sock.connect((host, int(port)))
        except Exception, e:
            raise NetRPC_Exception(tools.ustr(e), "Could not connect to %s:%s" % (host, port))

    def disconnect(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def mysend(self, msg, exception=False, traceback=None):
        #self._logger.debug("rpc message : %s", msg)
        msg = pickle.dumps([msg,traceback])
        if self.is_gzip:
            raw_size = len(msg)
            msg = zlib.compress(msg, zlib.Z_BEST_COMPRESSION)
            gzipped_size = len(msg)
            #saving = 100*(float(raw_size-gzipped_size))/gzipped_size if gzipped_size else 0
            #self._logger.debug('payload size: raw %s, gzipped %s, saving %.2f%%', raw_size, gzipped_size, saving)
        size = len(msg)
        self.sock.send('%8d' % size)
        self.sock.send(exception and "1" or "0")
        totalsent = 0
        while totalsent < size:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError, "socket connection broken"
            totalsent = totalsent + sent

    def myreceive(self):
        buf=''
        while len(buf) < 8:
            chunk = self.sock.recv(8 - len(buf))
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            buf += chunk
        size = int(buf)
        buf = self.sock.recv(1)
        if buf != "0":
            exception = buf
        else:
            exception = False
        msg = ''
        while len(msg) < size:
            chunk = self.sock.recv(size-len(msg))
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            msg = msg + chunk
        if msg.startswith(GZIP_MAGIC):
            gzipped_size = len(msg)
            msg = zlib.decompress(msg)
            raw_size = len(msg)
            #saving = 100*(float(raw_size-gzipped_size))/gzipped_size if gzipped_size else 0
            #self._logger.debug('payload size: raw %s, gzipped %s, saving %.2f%%', raw_size, gzipped_size, saving)
        res = SafeUnpickler.loads(msg)

        if isinstance(res[0],Exception):
            if exception:
                raise NetRPC_Exception(unicode(res[0]), str(res[1]))
            raise res[0]
        else:
            return res[0]

class NetRPCConnector(Connector):
    PROTOCOL = 'netrpc'

    def __init__(self, hostname, port=8070, is_gzip=False, timeout=10.0, retry=10):
        Connector.__init__(self, hostname, port, timeout=timeout)
        self._logger = logging.getLogger('connector.netrpc')
        self.is_gzip = is_gzip
        self.retry = retry

    def send(self, service_name, method, *args):
        i = 0
        retry = True
        result = False
        error = False
        while retry:
            try:
                retry = False
                #US-309: Reset value of error in the previous rounds, otherwise the system will raise exception regardless of the result of the next try!
                error = False
                socket = NetRPC(is_gzip=self.is_gzip, timeout=self.timeout)
                socket.connect(self.hostname, self.port)
                socket.mysend((service_name, method, )+args)
                result = socket.myreceive()
            except Exception, e:
                error = e
                if i < self.retry:
                    retry = True
                    self._logger.debug("retry to connect %s, error : %s" ,i, e)
                i += 1
                
        socket.disconnect()
        if error:
            raise osv.except_osv(_('Error!'), "Unable to proceed for the following reason:\n%s" % (e.faultCode if hasattr(e, 'faultCode') else tools.ustr(e)))
        return result

class GzipNetRPCConnector(NetRPCConnector):
    PROTOCOL = 'netrpc_gzip'

    def __init__(self, *args, **kwargs):
        super(GzipNetRPCConnector, self).__init__(is_gzip=True, *args, **kwargs)

class Common(object):
    _logger = logging.getLogger('connection.common')

    def __init__(self, connector):
        self.connector = connector

    def __getattr__(self, method):
        """
        :param method: The method for the linked object (search, read, write, unlink, create, ...)
        """
        #self._logger.debug('method: %r', method)
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            #self._logger.debug('args: %r', args)
            result = self.connector.send('common', method, *args)
            #self._logger.debug('result: %r' % result)
            return result
        return proxy
    


class Database(object):
    _logger = logging.getLogger('connection.database')

    def __init__(self, connector):
        self.connector = connector

    def __getattr__(self, method):
        """
        :param method: The method for the linked object (search, read, write, unlink, create, ...)
        """
        #self._logger.debug('method: %r', method)
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            #self._logger.debug('args: %r', args)
            result = self.connector.send('db', method, *args)
            #self._logger.debug('result: %r' % result)
            return result
        return proxy
    
class Connection(object):
    """
    TODO: Document this class
    """
    _logger = logging.getLogger('connection')

    def __init__(self, connector,
                 database,
                 login=None,
                 password=None,
                 user_id=None):
        """
        :param connector:
        :param database:
        :param login:
        :param password:
        """
        self.connector = connector
        self.database, self.login, self.password = database, login, password
        self.user_id = user_id
        if user_id is None:
            self.user_id = Common(self.connector).login(self.database, self.login, self.password)
            
        if self.user_id is False:
            raise osv.except_osv(_('Error!'), _('Unable to connect to the distant server with this user!'))
        self._logger.debug(self.user_id)

    def __repr__(self):
        """
        Return a readable representation of the Connection object
        """
        url = "%(protocol)s://%(login)s:%(password)s@" \
              "%(hostname)s:%(port)d/%(database)s" % {
            'protocol' : self.connector.PROTOCOL,
            'login' : self.login,
            'password' : self.password,
            'hostname' : self.connector.hostname,
            'port' : self.connector.port,
            'database' : self.database,
        }
 
        return "Connection: %s" % url

class Object(object):
    """
    TODO: Document this class
    """
    _logger = logging.getLogger('object')

    def __repr__(self):
        """
        """
        return "Object <%s>" % (self.model)

    def __init__(self, connection, model, context=None):
        """
        :param connection:
        :param model:
        """
        self.connection = connection
        self.model = model

        self.context = context

    def __getattr__(self, method):
        """
        :param method: The method for the linked object (search, read, write, unlink, create, ...)
        """
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            return self.__send__(method, *args)
        return proxy

    def __send__(self, method, *args):
        #self._logger.debug('method: %r', method)
        #self._logger.debug('args: %r', args)
        
        result = self.connection.connector.send('object', 'execute',
                                                self.connection.database,
                                                self.connection.user_id,
                                                self.connection.password,
                                                self.model,
                                                method,
                                                *args)
        #self._logger.debug('result: %r', result)
        return result

    def __add_context(self, arguments, context=None):
        if context is None:
            context = {}

        if self.context is not None:
            context.update(self.context)

        arguments.append(context)
        return arguments

    def exists(self, oid, context=None):
        # TODO: Fucking bug, we can't use the read(fields=['id']), 
        # because the server returns a positive value but the record does not exist
        # into the database
        value = self.search_count([('id', '=', oid)], context=context)
        
        return value > 0
        
    def read(self, ids, fields=None, context=None):
        if fields is None:
            fields = []

        arguments = [ids, fields]
        arguments = self.__add_context(arguments, context)

        records = self.__send__('read', *arguments)

        if isinstance(ids, (list, tuple,)):
            records.sort(lambda x, y: cmp(ids.index(x['id']),
                                          ids.index(y['id'])))

        return records

    def search(self, domain=None, offset=0, limit=None, order=None,
            force_no_order=False, context=None):
        if domain is None:
            domain = []

        if limit is None:
            limit = self.search_count(domain)

        arguments = [domain, offset, limit, not force_no_order and order is not None and order or False]

        arguments = self.__add_context(arguments, context)

        return self.__send__('search', *arguments)
        
    def search_count(self, domain, context=None):
        if context is None:
            context = {}
            
        return self.__send__('search_count', domain, context)

    def write(self, ids, values, context=None):
        if not isinstance(ids, (tuple, list)):
            ids = [ids]
        arguments = self.__add_context([ids, values], context)

        return self.__send__('write', *arguments)

    def create(self, values, context=None):
        arguments = self.__add_context([values], context)

        return self.__send__('create', *arguments)

    def unlink(self, ids, context=None):
        if not isinstance(ids, (tuple, list)):
            ids = [ids]
        arguments = self.__add_context([ids], context)

        return self.__send__('unlink', *arguments)

    def select(self, domain=None, fields=None, offset=0, limit=None, order=None, context=None):
        record_ids = self.search(domain, offset=offset, limit=limit, order=order, context=context)

        return self.read(record_ids, fields=fields, context=context)

