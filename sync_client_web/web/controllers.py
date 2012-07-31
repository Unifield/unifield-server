
from openobject.tools import expose

import openerp.controllers
from openerp.utils import rpc, TinyDict

class Client_Sync(openerp.controllers.SecuredController):
    _cp_path = "/sync_client_web/synchro_client"

    
    @expose('json')
    def get_data(self):
        status = rpc.RPCProxy('sync.client.entity').get_status()
        upgrade_status = rpc.RPCProxy('sync.client.entity').get_upgrade_status()
        return dict(status=status,upgrade_status=upgrade_status)

