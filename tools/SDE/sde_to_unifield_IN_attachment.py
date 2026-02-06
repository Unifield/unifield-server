#! /usr/bin/env python
# -*- encoding: utf-8 -*-
import sys
import os
import urllib.request
import urllib.error
import json
import random

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

if len(sys.argv) < 3:
    print(r'Call the script with the file to import and at least the PO reference: i.e "%s C:\path_to_file PO_Reference Ship_or_OUT_Reference Supplier_FO_Reference"' % (sys.argv[0]))
    sys.exit(1)

filepath = sys.argv[1]
if not os.path.exists(filepath):
    print('The file "%s" does not exist' % (filepath))
    sys.exit(1)

lang_context = {'lang': 'en_MF'}  # or fr_MF

url_object = f"http://{host}:{port}/jsonrpc/object"
url = f"http://{host}:{port}/jsonrpc/common"

# retrieve the user id
user_id = json_rpc(url, "login", [dbname, user, password])
if not user_id:
    print('Wrong %s password on %s:%s db: %s' % (user, host, port, dbname))
    sys.exit(1)

# the content of the file is read, decode it because JSON can't serialize bytes
file_content = open(filepath, 'rb').read().decode('utf-8')

# attachment message
po_ref = sys.argv[2]
pack_ref, partner_fo_ref = '', ''
if len(sys.argv) > 3:
    pack_ref = sys.argv[3]
if len(sys.argv) > 4:
    partner_fo_ref = sys.argv[4]
msg = json_rpc(url_object, "execute", [dbname, user_id, password, 'sde.import', 'sde_file_to_in', filepath, file_content, po_ref, pack_ref, partner_fo_ref, lang_context])

# display the result message
print('End message: %s' % msg)
