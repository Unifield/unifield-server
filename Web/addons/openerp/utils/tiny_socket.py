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
import pickle
import sys
import struct
import cherrypy
from openobject import ustr
DNS_CACHE = {}

class TinySocketError(Exception):

    def __init__(self, faultCode, faultString):
        self.faultCode = faultCode
        self.faultString = faultString
        self.args = (faultCode, faultString)

SOCKET_TIMEOUT = cherrypy.config.get('openerp.server.timeout')
socket.setdefaulttimeout(SOCKET_TIMEOUT)
class TinySocket(object):

    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.sock.settimeout(SOCKET_TIMEOUT)
        # disables Nagle algorithm (avoids 200ms default delay on Windows)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def connect(self, host, port=False):
        if not port:
            protocol, buf = host.split('//')
            host, port = buf.split(':')
        if host in DNS_CACHE:
            host = DNS_CACHE[host]
        self.sock.connect((host, int(port)))
        DNS_CACHE[host], port = self.sock.getpeername()

    def disconnect(self):
        # on Mac, the connection is automatically shutdown when the server disconnect.
        # see http://bugs.python.org/issue4397
        if sys.platform != 'darwin':
            self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def send(self, msg, exception=False, traceback=None):
        msg = pickle.dumps([msg,traceback], protocol=2, fix_imports=True)
        if len(msg) <= 10**8-1:
            #self.sock.sendall('%8d%s%s' % (len(msg), exception and "1" or "0", msg))
            self.sock.sendall(struct.pack('8ss%ds'%len(msg), ('%8d'%len(msg)).encode('utf8'), (exception and "1" or "0").encode('utf8'), msg))
        else:
            n8size = len(msg)%10**8
            n16size = len(msg)/10**8
            #self.sock.sendall(('%8d%s%16d%s%s' % (n8size, "3", n16size, exception and "1" or "0", msg)).encode('utf8'))
            self.sock.sendall(struct.pack('8ss16ss%ds'%len(msg), ('%8d'%n8size).encode('utf8'), "3".encode('utf8'), ('%16d'%n16size).encode('utf8'), (exception and "1" or "0").encode('utf8'), msg))


    def receive(self):

        def read(socket, size):
            buf=b''
            while len(buf) < size:
                chunk = self.sock.recv(size - len(buf))
                if not chunk:
                    raise RuntimeError("socket connection broken")
                buf += chunk
            return buf

        size = int(read(self.sock, 8))
        buf = read(self.sock, 1)
        if buf == b'3':
            newsize = int(read(self.sock, 16))
            size = newsize*10**8+size
            buf = read(self.sock, 1)
        exception = buf != b'0' and buf or False
        # pickel compat with py2.7
        res = pickle.loads(read(self.sock, size), fix_imports=True, encoding='utf8')

        if isinstance(res[0],Exception):
            if exception:
                raise TinySocketError(ustr(res[0]), ustr(res[1]))
            raise res[0]
        else:
            return res[0]

# vim: ts=4 sts=4 sw=4 si et
