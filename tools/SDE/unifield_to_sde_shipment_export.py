#! /usr/bin/env python
# -*- encoding: utf-8 -*-
import sys
import urllib.request
import urllib.error
import json
import random
import os
import time

dbname = 'my_db'
user = 'my_user'
password = 'my_password'
host = 'my_host'
port = 8069  # json-rpc port, 8069 on prod instance

def json_rpc(url, method, params, timeout=None):
    data = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": random.randint(0, 1000000000),
    }
    req = urllib.request.Request(
        url=url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            reply = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"JSON-RPC request failed: {e}")

    if reply.get("error"):
        raise RuntimeError(reply["error"])

    return reply["result"]

path = 'C:\\path\\to\\your\\directory'
if not os.path.exists(path):
    os.mkdir(path)
    print('Folder "%s" created' % (path,))

lang_context = {'lang': 'en_MF'}  # or fr_MF

url_object = f"http://{host}:{port}/jsonrpc/object"
url = f"http://{host}:{port}/jsonrpc/common"

# retrieve the user id
user_id = json_rpc(url, "login", [dbname, user, password])
if not user_id:
    print('Wrong %s password on %s:%s db: %s' % (user, host, port, dbname))
    sys.exit(1)

try:
    # get the report
    file_res = json_rpc(url_object, "execute", [dbname, user_id, password, 'shipment', 'generate_dispatched_packing_list_report', lang_context])
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
