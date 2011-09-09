import httplib
import xmlrpclib

class TimeoutHTTPConnection(httplib.HTTPConnection):

    def connect(self):
        httplib.HTTPConnection.connect(self)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)

class TimeoutHTTP(httplib.HTTP):

    _connection_class = TimeoutHTTPConnection

    def set_timeout(self, timeout):
        self._conn.timeout = timeout

class TimeoutTransport(xmlrpclib.Transport):

    def __init__(self, timeout=None, *args, **kwargs):
        xmlrpclib.Transport.__init__(self, *args, **kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        # TODO: check make_connection for python > 2.6
        conn = TimeoutHTTP(host)
        conn.set_timeout(self.timeout)
        return conn

