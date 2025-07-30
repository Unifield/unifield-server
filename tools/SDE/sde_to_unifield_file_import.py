#! /usr/bin/env python
# -*- encoding: utf-8 -*-
import xmlrpc.client
import sys
import os

dbname = 'my_db'
user = 'my_user'
password = 'my_password'
host = 'my_host'
port = 8069  # xml-rpc port, 8069 on prod instance

filepath = 'C:\\path\\to\\your\\file.xls'
if not os.path.exists(filepath):
    print('The file "%s" does not exist' % (filepath))
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

# the content of the file is read
file_content = open(filepath, 'rb').read()

# import
msg = sock.execute(dbname, user_id, password, 'sde.import', 'sde_file_import', filepath, file_content, lang_context)

# display the result message
print('End message: %s' % msg)
