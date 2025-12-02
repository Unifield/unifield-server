import mimetypes
mimetypes.init()
mimetypes.types_map['.dwg']='image/x-dwg'
mimetypes.types_map['.ico']='image/x-icon'

import os
import stat
import cherrypy
from cherrypy.lib import cptools, httputil, file_generator_limited

def serve_file(path, content_type=None, disposition=None, name=None, delete=False):
    """Set status, headers, and body in order to serve the given file.

    The Content-Type header will be set to the content_type arg, if provided.
    If not provided, the Content-Type will be guessed by the file extension
    of the 'path' argument.

    If disposition is not None, the Content-Disposition header will be set
    to "<disposition>; filename=<name>". If name is None, it will be set
    to the basename of path. If disposition is None, no Content-Disposition
    header will be written.
    """

    response = cherrypy.response

    # If path is relative, users should fix it by making path absolute.
    # That is, CherryPy should not guess where the application root is.
    # It certainly should *not* use cwd (since CP may be invoked from a
    # variety of paths). If using tools.static, you can make your relative
    # paths become absolute by supplying a value for "tools.static.root".
    if not os.path.isabs(path):
        raise ValueError("'%s' is not an absolute path." % path)

    try:
        st = os.stat(path)
    except OSError:
        raise cherrypy.NotFound()

    # Check if path is a directory.
    if stat.S_ISDIR(st.st_mode):
        # Let the caller deal with it as they like.
        raise cherrypy.NotFound()

    # Set the Last-Modified response header, so that
    # modified-since validation code can work.
    response.headers['Last-Modified'] = httputil.HTTPDate(st.st_mtime)
    cptools.validate_since()

    if content_type is None:
        # Set content-type based on filename extension
        ext = ""
        i = path.rfind('.')
        if i != -1:
            ext = path[i:].lower()
        content_type = mimetypes.types_map.get(ext, "text/plain")
    response.headers['Content-Type'] = content_type

    if disposition is not None:
        if name is None:
            name = os.path.basename(path)
        cd = '%s; filename="%s"' % (disposition, name)
        response.headers["Content-Disposition"] = cd

    # Set Content-Length and use an iterable (file object)
    #   this way CP won't load the whole file in memory
    c_len = st.st_size
    if delete:
        flag = os.O_RDWR | os.O_EXCL
        if hasattr(os, 'O_BINARY'):
            flag |= os.O_BINARY
        if os.name == 'nt':
            flag |= os.O_TEMPORARY
        fd = os.open(path, flag)
        file = os.fdopen(fd, 'rb')
        bodyfile = file
    else:
        bodyfile = open(path, 'rb')

    # HTTP/1.0 didn't have Range/Accept-Ranges headers, or the 206 code
    if cherrypy.request.protocol >= (1, 1):
        response.headers["Accept-Ranges"] = "bytes"
        r = httputil.get_ranges(cherrypy.request.headers.get('Range'), c_len)
        if r == []:
            response.headers['Content-Range'] = "bytes */%s" % c_len
            message = "Invalid Range (first-byte-pos greater than Content-Length)"
            raise cherrypy.HTTPError(416, message)
        if r:
            if len(r) == 1:
                # Return a single-part response.
                start, stop = r[0]
                if stop > c_len:
                    stop = c_len
                r_len = stop - start
                response.status = "206 Partial Content"
                response.headers['Content-Range'] = ("bytes %s-%s/%s" %
                                                     (start, stop - 1, c_len))
                response.headers['Content-Length'] = r_len
                bodyfile.seek(start)
                response.body = file_generator_limited(bodyfile, r_len)
            else:
                # Return a multipart/byteranges response.
                response.status = "206 Partial Content"
                import mimetools
                boundary = mimetools.choose_boundary()
                ct = "multipart/byteranges; boundary=%s" % boundary
                response.headers['Content-Type'] = ct
                if "Content-Length" in response.headers:
                    # Delete Content-Length header so finalize() recalcs it.
                    del response.headers["Content-Length"]

                def file_ranges():
                    # Apache compatibility:
                    yield "\r\n"

                    for start, stop in r:
                        yield "--" + boundary
                        yield "\r\nContent-type: %s" % content_type
                        yield ("\r\nContent-range: bytes %s-%s/%s\r\n\r\n"
                               % (start, stop - 1, c_len))
                        bodyfile.seek(start)
                        for chunk in file_generator_limited(bodyfile, stop-start):
                            yield chunk
                        yield "\r\n"
                    # Final boundary
                    yield "--" + boundary + "--"

                    # Apache compatibility:
                    yield "\r\n"
                response.body = file_ranges()
        else:
            response.headers['Content-Length'] = c_len
            response.body = bodyfile
    else:
        response.headers['Content-Length'] = c_len
        response.body = bodyfile
    response.stream = True
    return response.body

