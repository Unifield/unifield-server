import http.client
import xmlrpc.client

class TimeoutHTTPConnection(http.client.HTTPConnection):

    def connect(self):
        http.client.HTTPConnection.connect(self)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)

    def set_timeout(self, timeout):
        self.timeout = timeout

class TimeoutTransport(xmlrpc.client.Transport):

    def __init__(self, timeout=None, *args, **kwargs):
        xmlrpc.client.Transport.__init__(self, *args, **kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        chost, self._extra_headers, _ = self.get_host_info(host)
        self._connection = host, TimeoutHTTPConnection(chost)
        self._connection[1].set_timeout(self.timeout)
        return self._connection[1]

class TimeoutHTTPSConnection(http.client.HTTPSConnection):

    def connect(self):
        http.client.HTTPSConnection.connect(self)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)

    def set_timeout(self, timeout):
        self.timeout = timeout

class TimeoutSafeTransport(xmlrpc.client.SafeTransport):

    def __init__(self, timeout=None, *args, **kwargs):
        xmlrpc.client.SafeTransport.__init__(self, *args, **kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        chost, self._extra_headers, _ = self.get_host_info(host)
        self._connection = host, TimeoutHTTPSConnection(chost)
        self._connection[1].set_timeout(self.timeout)
        return self._connection[1]

