import zlib
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import logging

from timeout_transport import TimeoutTransport, TimeoutSafeTransport

# xmlrpc server side

class GzipXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def do_POST(self):
        if not(self.headers.has_key('accept-encoding') and self.headers['accept-encoding'] == 'gzip'):
            return SimpleXMLRPCRequestHandler.do_POST(self)
        else:
            if not self.is_rpc_path_valid():
                self.report_404()
                return
            try:
                max_chunk_size = 10*1024*1024
                size_remaining = int(self.headers["content-length"])
                L = []
                while size_remaining:
                    chunk_size = min(size_remaining, max_chunk_size)
                    L.append(self.rfile.read(chunk_size))
                    size_remaining -= len(L[-1])
                data = ''.join(L)
                data = zlib.decompress(data) # is_gzip
                response = self.server._marshaled_dispatch(
                        data, getattr(self, '_dispatch', None)
                    )
            except Exception, e:
                self.send_response(500)
                self.end_headers()
            else:
                response = zlib.compress(response, zlib.Z_BEST_COMPRESSION) # is_gzip
                self.send_response(200)
                self.send_header("Content-type", "text/xml")
                self.send_header("Content-length", str(len(response)))
                self.send_header("Accept-Encoding", "gzip") # is_gzip
                self.end_headers()
                self.wfile.write(response)
                self.wfile.flush()
                self.connection.shutdown(1)

# xmlrpc client side
class GzipTransport(TimeoutTransport):

    def __init__(self, timeout=None, *args, **kwargs):
        TimeoutTransport.__init__(self, timeout=timeout, *args, **kwargs)
        self._logger = logging.getLogger('xmlrpc.transport')

    def request(self, host, handler, request_body, verbose=0):
        h = self.make_connection(host)
        if verbose:
            h.set_debuglevel(1)
        self.send_request(h, handler, request_body)
        self.send_host(h, host)
        self.send_user_agent(h)

        # is_gzip
        h.putheader('Accept-Encoding', 'gzip')
        raw_size = len(request_body)
        request_body = zlib.compress(request_body, zlib.Z_BEST_COMPRESSION)
        gzipped_size = len(request_body)
        saving = 100*(float(raw_size-gzipped_size))/gzipped_size if gzipped_size else 0
        self._logger.debug('payload size: raw %s, gzipped %s, saving %.2f%%',
                raw_size, gzipped_size, saving)

        self.send_content(h, request_body)
        errcode, errmsg, headers = h.getreply()
        if errcode != 200:
            raise xmlrpclib.ProtocolError(
                    host + handler,
                    errcode, errmsg,
                    headers
                    )
        self.verbose = verbose
        try:
            sock = h._conn.sock
        except AttributeError:
            sock = None

        # is_gzip
        if headers.has_key('accept-encoding') and headers['accept-encoding'] == 'gzip':
            return self._parse_gzipped_response(h.getfile(), sock)
        return self._parse_response(h.getfile(), sock)

    def _parse_gzipped_response(self, file, sock):
        p, u = self.getparser()
        response_chunks = []
        while 1:
            if sock:
                chunk = sock.recv(1024)
            else:
                chunk = file.read(1024)
            if not chunk:
                break
            response_chunks.append(chunk)
        response = zlib.decompress("".join(response_chunks))
        if self.verbose:
            print "body:", repr(response)
        p.feed(response)
        file.close()
        p.close()
        return u.close()

class GzipSafeTransport(TimeoutSafeTransport, GzipTransport):
    def __init__(self, timeout=None, *args, **kwargs):
        TimeoutSafeTransport.__init__(self, timeout=timeout, *args, **kwargs)
        self._logger = logging.getLogger('xmlrpc.transport')

    def request(self, host, handler, request_body, verbose=0):
        return GzipTransport.request(self, host, handler, request_body, verbose)
