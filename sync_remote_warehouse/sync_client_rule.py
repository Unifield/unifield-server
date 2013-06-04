from osv import osv, fields

class SyncClientRule(osv.osv):
    _inherit = 'sync.client.rule'

    _columns = {
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_usb': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization', required=True),
    }
    
    _defaults = {
        'direction_usb': 'bidirectional',
    }
    
SyncClientRule()
