from osv import osv, fields

class SyncClientUpdateRule(osv.osv):
    _inherit = 'sync.client.rule'

    _columns = {
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_usb': fields.selection((('cp_to_rw', 'Central Platform to Remote Warehouse'), ('rw_to_cp', 'Remote Warehouse to Central Platform'), ('bidirectional','Bidirectional')), 'Direction USB', help='The direction of the synchronization', required=True),
    }
    
    _defaults = {
        'direction_usb': 'bidirectional',
    }
    
SyncClientUpdateRule()
