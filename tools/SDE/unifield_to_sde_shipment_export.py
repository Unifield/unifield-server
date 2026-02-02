#! /usr/bin/env python
# -*- encoding: utf-8 -*-
import xmlrpc.client
import sys
import base64
import os
import time

dbname = 'my_db'
user = 'my_user'
password = 'my_password'
host = 'my_host'
port = 8069  # xml-rpc port, 8069 on prod instance

path = 'C:\\path\\to\\your\\directory'
if not os.path.exists(path):
    os.mkdir(path)
    print('Folder "%s" created' % (path,))

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

try:
    # get the report
    file_res = sock.execute(dbname, user_id, password, 'shipment', 'generate_dispatched_packing_list_report', lang_context)
    if not file_res:
        raise Exception('The Dispatched Shipments report could not be retrieved')

    # create the new file in the given path
    filepath = os.path.join(path, 'dispatched_packing_list_%s.xls' % (time.strftime('%Y_%m_%d_%H_%M'),))
    file = open(filepath, 'w')
    file.write(file_res)
    file.close()
    print('The new Dispatched Shipment report has been created at "%s"' % (path,))
except Exception as e:
    raise
    print(e)
