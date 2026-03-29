JSONRPC_ALLOWED = set()

def jsonrpc_exposed(service, method=None):
    def decorator(func):
        m = method or func.__name__
        JSONRPC_ALLOWED.add((service, m))
        return func
    return decorator

JSONRPC_ORM_ALLOWED = set()

def jsonrpc_orm_exposed(model, method=None):
    def decorator(func):
        m = method or func.__name__
        JSONRPC_ORM_ALLOWED.add((model, m))
        print(f"Exposed via JSON-RPC: {(model, m)}")
        return func
    return decorator
