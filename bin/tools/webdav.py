# -*- coding: utf-8 -*-

import requests

from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.runtime.client_request import ClientRequest
from office365.sharepoint.client_context import ClientContext
from office365.runtime.utilities.request_options import RequestOptions
from office365.runtime.utilities.http_method import HttpMethod
import cgi
import uuid
import logging
import os

class ConnectionFailed(Exception):
    pass

class PasswordFailed(Exception):
    pass

class Client(object):
    def __init__(self, host, port=0, auth=None, username=None, password=None, protocol='http', path=None):
        self.requests_timeout = 45
        self.session_uuid = False
        self.session_offset = -1
        self.session_nb_error = 0

        self.username = username
        self.password = password

        if not port:
            port = 443 if protocol == 'https' else 80
        self.path = path or ''
        if not self.path.endswith('/'):
            self.path = '%s/' % self.path

        # oneDrive: need to split /site/ and path
        # in our config site is /personal/unifield_xxx_yyy/
        # path is /Documents/Unifield/
        self.baseurl = '{0}://{1}:{2}/{3}/'.format(protocol, host, port, '/'.join(self.path.split('/')[0:3]) )

        if len(self.path.split('/')) < 5:
            self.path = '%sDocuments/' % self.path

        self.login()

    def login(self):
        ctx_auth = AuthenticationContext(self.baseurl)

        if ctx_auth.acquire_token_for_user(self.username, cgi.escape(self.password)):
            self.request = ClientRequest(ctx_auth)
            self.request.context = ClientContext(self.baseurl, ctx_auth)

            if not ctx_auth.provider.FedAuth or not ctx_auth.provider.rtFa:
                raise ConnectionFailed(ctx_auth.get_last_error())
        else:
            raise requests.exceptions.RequestException(ctx_auth.get_last_error())

    def format_request(self, url, method='POST', data="", session=False):
        assert(method in ['POST', 'DELETE'])
        r_meth = {
            'POST': HttpMethod.Post,
            'DELETE': HttpMethod.Delete,
        }
        options = RequestOptions(url)
        options.method = r_meth[method]
        options.set_header("X-HTTP-Method", method)
        options.set_header('Accept', 'application/json')
        options.set_header('Content-Type', 'application/json')

        self.request.context.authenticate_request(options)
        self.request.context.ensure_form_digest(options)

        if session:
            return session.post(url, data=data, headers=options.headers, auth=options.auth, timeout=self.requests_timeout)

        return requests.post(url, data=data, headers=options.headers, auth=options.auth, timeout=self.requests_timeout)

    def parse_error(self, result):
        try:
            if 'application/json' in result.headers.get('Content-Type'):
                resp_content = result.json()
                msg = resp_content['odata.error']['message']
                error = []
                if isinstance(msg, dict):
                    error = [msg['value']]
                else:
                    error = [msg]
                if resp_content['odata.error'].get('code'):
                    error.append('Code: %s' % resp_content['odata.error']['code'])
                return ' '.join(error)
        except:
            pass
        return result.content

    def create_folder(self, remote_path):
        webUri = '%s%s' % (self.path, remote_path)
        request_url = "%s/_api/web/GetFolderByServerRelativeUrl('%s')" % (self.baseurl, webUri)
        result = self.format_request(request_url, 'POST')
        if result.status_code not in (200, 201):
            result = self.format_request("%s/_api/Web/Folders/add('%s')" % (self.baseurl, webUri), 'POST')
            if result.status_code not in (200, 201):
                raise Exception(self.parse_error(result))
        return True

    def delete(self, remote_path):
        webUri = '%s%s' % (self.path, remote_path)
        request_url = "%s/_api/web/getfilebyserverrelativeurl('%s')" % (self.baseurl, webUri)
        result = self.format_request(request_url, 'DELETE')
        if result.status_code not in (200, 201):
            raise Exception(self.parse_error(result))
        return True

    def move(self, remote_path, dest):
        webUri = '%s%s' % (self.path, remote_path)
        destUri = '%s%s' % (self.path, dest)
        # falgs=1 to overwrite existing file
        request_url = "%s_api/web/getfilebyserverrelativeurl('%s')/moveto(newurl='%s',flags=1)" % (self.baseurl, webUri, destUri)
        result = self.format_request(request_url, 'POST')
        if result.status_code not in (200, 201):
            raise Exception(self.parse_error(result))
        return True

    def upload(self, fileobj, remote_path, buffer_size=None, log=False, progress_obj=False):
        if not self.session_uuid:
            self.session_uuid = uuid.uuid1()

        if progress_obj:
            log = True

        if log:
            logger = logging.getLogger('cloud.backup')
            try:
                size = os.path.getsize(fileobj.name)
            except:
                size = None

        if self.session_offset != -1:
            fileobj.seek(self.session_offset)

        if not buffer_size:
            buffer_size = 10* 1024 * 1024

        x = ""
        split_name = remote_path.split('/')
        new_file = split_name.pop()
        split_name.insert(0, self.path)
        path  = '/'.join(split_name)
        if path[-1] != '/':
            path += '/'
        webUri = '%s%s' % (path, new_file)
        s = requests.Session()

        while True:
            if self.session_offset == -1:
                # first loop create an empty file
                request_url = "%s/_api/web/GetFolderByServerRelativeUrl('%s')/Files/add(url='%s',overwrite=true)" % (self.baseurl, path, new_file)
                self.session_offset = 0
            else:
                x = fileobj.read(buffer_size)
                if not x:
                    break
                if not self.session_offset:
                    # 2nd loop
                    if len(x) == buffer_size:
                        # split needed
                        request_url="%s/_api/web/getfilebyserverrelativeurl('%s')/startupload(uploadId=guid'%s')" % (self.baseurl, webUri, self.session_uuid)
                    else:
                        # file size < buffer: no need to split
                        request_url = "%s/_api/web/GetFolderByServerRelativeUrl('%s')/Files/add(url='%s',overwrite=true)" % (self.baseurl, path, new_file)
                elif len(x) == buffer_size:
                    request_url = "%s/_api/web/getfilebyserverrelativeurl('%s')/continueupload(uploadId=guid'%s',fileOffset=%s)" % (self.baseurl, webUri, self.session_uuid, self.session_offset)
                else:
                    request_url = "%s/_api/web/getfilebyserverrelativeurl('%s')/finishupload(uploadId=guid'%s',fileOffset=%s)" % (self.baseurl, webUri, self.session_uuid, self.session_offset)

            result = self.format_request(request_url, method='POST', data=x, session=s)
            if result.status_code not in (200, 201):
                return (False, self.parse_error(result))
            self.session_nb_error = 0
            self.session_offset += len(x)

            if log and self.session_offset and self.session_offset % (buffer_size*5) == 0:
                percent_txt = ''
                if size:
                    percent = round(self.session_offset*100/size)
                    percent_txt = '%d%%' % percent
                    if progress_obj:
                        progress_obj.write({'name': percent})

                logger.info('OneDrive: %d bytes sent on %s bytes %s' % (self.session_offset, size or 'unknown', percent_txt))
        return (True, '')

