#! /usr/bin/env python
# -*- encoding: utf-8 -*-
import sys
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
    print(r'Call the script with the type of import and the import data in double quotes: i.e \'%s normal "{\'json\': data}"\'' % (sys.argv[0]))
    sys.exit(1)

if sys.argv[1] not in ['normal', 'updated']:
    print(r'The first argument should be either "normal" or "updated"')
    sys.exit(1)

if not isinstance(sys.argv[2], str):
    print(r'The second argument should be a string')
    sys.exit(1)

lang_context = {'lang': 'en_MF'}  # or fr_MF

url_object = f"http://{host}:{port}/jsonrpc/object"
url = f"http://{host}:{port}/jsonrpc/common"

# retrieve the user id
user_id = json_rpc(url, "login", [dbname, user, password])
if not user_id:
    print('Wrong %s password on %s:%s db: %s' % (user, host, port, dbname))
    sys.exit(1)

msg = ''
try:
    # Normal IN import or import for Available Updated INs
    in_updated = sys.argv[1] == 'updated'

    # import with a timeout of 240s
    msg = json_rpc(url_object, "execute", [dbname, user_id, password, 'sde.import', 'sde_in_import', sys.argv[2], in_updated, lang_context], 240)
except Exception as e:
    msg = e
finally:
    # display the result message
    print('End message: %s' % msg)
