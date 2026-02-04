def rpc_access(xmlrpc=True, jsonrpc=True):
    def decorator(func):
        func._rpc_access = {
            'xmlrpc': xmlrpc,
            'jsonrpc': jsonrpc,
        }
        return func
    return decorator
