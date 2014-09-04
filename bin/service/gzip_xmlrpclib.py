import zlib
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import logging

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

