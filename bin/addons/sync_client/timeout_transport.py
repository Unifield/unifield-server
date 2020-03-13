import httplib
import xmlrpclib

class TimeoutHTTPConnection(httplib.HTTPConnection):

    def connect(self):
        httplib.HTTPConnection.connect(self)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)

    def set_timeout(self, timeout):
        self.timeout = timeout

class TimeoutTransport(xmlrpclib.Transport):

    def __init__(self, timeout=None, *args, **kwargs):
        xmlrpclib.Transport.__init__(self, *args, **kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        chost, self._extra_headers, _ = self.get_host_info(host)
        self._connection = host, TimeoutHTTPConnection(chost)
        self._connection[1].set_timeout(self.timeout)
        return self._connection[1]

class TimeoutHTTPSConnection(httplib.HTTPSConnection):

    def connect(self):
        httplib.HTTPSConnection.connect(self)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)

    def set_timeout(self, timeout):
        self.timeout = timeout

class TimeoutSafeTransport(xmlrpclib.SafeTransport):

    def __init__(self, timeout=None, *args, **kwargs):
        xmlrpclib.SafeTransport.__init__(self, *args, **kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        chost, self._extra_headers, _ = self.get_host_info(host)
        self._connection = host, TimeoutHTTPSConnection(chost)
        self._connection[1].set_timeout(self.timeout)
        return self._connection[1]

