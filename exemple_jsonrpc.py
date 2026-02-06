from bin.jsonrpc import json_rpc

HOST = 'localhost'
PORT = 8069
DB = 'se_HQ1'
USER = 'admin'
PASS = 'admin'

URL_OBJECT = f"http://{HOST}:{PORT}/jsonrpc/object"
URL_COMMON = f"http://{HOST}:{PORT}/jsonrpc/common"

# --- 1. LOGIN ---
uid = json_rpc(URL_COMMON, "login", [DB, USER, PASS])
print("UID:", uid)

# --- 2. CREATE ---
new_user_data = {
    'name': 'Test User',
    'login': 'testuser123',
    'password': 'Test12!',
}
new_user_id = json_rpc(URL_OBJECT, "execute", [
    DB,
    uid,
    PASS,
    'res.users',
    'create',
    new_user_data
], 100)
print("Created user ID:", new_user_id)

# --- 3. SEARCH ---
user_ids = json_rpc(URL_OBJECT, "execute", [
    DB,
    uid,
    PASS,
    'res.users',
    'search',
    [['login', '=', 'testuser123']]
], 100)
print("Search result:", user_ids)

# --- 4. READ ---
user_info = json_rpc(URL_OBJECT, "execute", [
    DB,
    uid,
    PASS,
    'res.users',
    'read',
    user_ids, ['name', 'login']
])
print("User info:", user_info)

# --- 5. WRITE / UPDATE ---
update_result = json_rpc(URL_OBJECT, "execute", [
    DB,
    uid,
    PASS,
    'res.users',
    'write',
    user_ids, {'name': 'Test User Updated'}
])
print("Update result:", update_result)

# --- 6. DELETE / UNLINK ---
delete_result = json_rpc(URL_OBJECT, "execute", [
    DB,
    uid,
    PASS,
    'res.users',
    'unlink',
    user_ids
])
print("Delete result:", delete_result)
