#! /usr/bin/env python
# -*- encoding: utf-8 -*-
import xmlrpc.client
import sys
import os
import urllib

dbname = 'my_db'
user = 'my_user'
password = 'my_password'
host = 'my_host'
port = 8069  # xml-rpc port, 8069 on prod instance

if len(sys.argv) < 2:
    print(r'Call the script with the file to import: i.e "%s C:\path_to_file"' % (sys.argv[0]))
    sys.exit(1)

filepath = sys.argv[1]
if not os.path.exists(filepath):
    print('The file "%s" does not exist' % (filepath))
    sys.exit(1)

if len(sys.argv) > 2 and sys.argv[2] and sys.argv[2] not in ['normal', 'updated']:
    print(r'The second argument should be either "normal" or "updated"')
    sys.exit(1)

lang_context = {'lang': 'en_MF'}  # or fr_MF

url = 'http://%s:%s/xmlrpc/' % (host, port)

# retrieve the user id : http://<host>:<xmlrpcport>/xmlrpc/common
sock = xmlrpc.client.ServerProxy(url + 'common')
user_id = sock.login(dbname, user, password)
if not user_id:
    print('Wrong %s password on %s:%s db: %s' % (user, host, port, dbname))
    sys.exit(1)

# to query the server: http://<host>:<xmlrpcport>/xmlrpc/object
sock = xmlrpc.client.ServerProxy(url + 'object', allow_none=True)

# set connection timeout (240s)
transport = xmlrpc.client.Transport()
u = urllib.parse.urlparse(url)
connection = transport.make_connection(u.hostname)
connection.timeout = 240

msg = ''
try:
    # the content of the file is read
    file_content = open(filepath, 'rb').read()

    # Normal IN import or import for Available Updated INs
    in_updated = sys.argv[2] == 'updated'

    # import
    msg = sock.execute(dbname, user_id, password, 'sde.import', 'sde_in_import', filepath, file_content, in_updated, lang_context)
except Exception as e:
    msg = e
finally:
    # display the result message
    print('End message: %s' % msg)
