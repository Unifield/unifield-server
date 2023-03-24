from openobject.tools import expose, no_session_refresh

import openerp.controllers
from openerp.utils import rpc

class Client_Sync(openerp.controllers.SecuredController):
    _cp_path = "/sync_client_web/synchro_client"

    @expose('json')
    def get_data(self, nb_shortcut_used=0):
        no_session_refresh()
        try:
            proxy = rpc.RPCProxy('sync.client.entity')
            return {
                'status' : proxy.get_status(),
                'upgrade_status' : proxy.get_upgrade_status(),
                'update_nb_shortcut_used': proxy.update_nb_shortcut_used(int(nb_shortcut_used)),
            }
        except:
            return {}
