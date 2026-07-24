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

# Not needed if the instance is HTTPs
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

if len(sys.argv) < 2:
    print(r'Call the script with the import data in double quotes: i.e \'%s "{\'json\': data}"\'' % (sys.argv[0]))
    sys.exit(1)

if not isinstance(sys.argv[1], str):
    print(r'The first argument should be a string')
    sys.exit(1)

lang_context = {'lang': 'en_MF'}  # or fr_MF

# Comment both linse and uncomment the other two in case the instance is HTTPs
url_object = f"http://{host}:{port}/jsonrpc/object"
url = f"http://{host}:{port}/jsonrpc/common"
# url_object = f"https://{host}/jsonrpc/object"
# url = f"https://{host}/jsonrpc/common"

# retrieve the user id
user_id = json_rpc(url, "login", [dbname, user, password])
if not user_id:
    print('Wrong %s password on %s:%s db: %s' % (user, host, port, dbname))
    sys.exit(1)

result = {}
try:
    # import with a timeout of 240s
    result = json_rpc(url_object, "execute", [dbname, user_id, password, 'sde.import', 'sde_picking_ticket_msg', sys.argv[1], lang_context], 240)
except Exception as e:
    result = {'error': True, 'message': e}
finally:
    # display the result message
    print(result)
