from openobject.tools import expose

import openerp.controllers
from openerp.utils import rpc

class Client_Sync(openerp.controllers.SecuredController):
    _cp_path = "/sync_client_web/synchro_client"

    @expose('json')
    def get_data(self):
        proxy = rpc.RPCProxy('sync.client.entity')
        return {
            'status' : proxy.get_status(),
            'upgrade_status' : proxy.get_upgrade_status(),
        }
