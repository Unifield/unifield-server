from osv import osv, fields

class SyncClientRule(osv.osv):
    _inherit = 'sync.client.rule'
    _name = 'sync.client.rule'
    _columns = {
        # Specifies that this rule is a rule for USB synchronisations
        'usb': fields.boolean('Remote Warehouse Rule', help='Should this rule be used when using the USB Synchronization engine?', required=True),
        
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_usb': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization', required=True),
    }
    
    _defaults = {
        'usb': False,
        'direction_usb': 'bidirectional',
    }
    
SyncClientRule()
