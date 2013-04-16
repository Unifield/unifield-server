from osv import osv, fields

class SyncRule(osv.osv):
    _inherit = 'sync_server.sync_rule'
    _name = 'sync_server.sync_rule'
    _columns = {
        # Specifies that this rule is a rule for USB synchronisations
        'horizontal': fields.boolean('Remote Warehouse Rule', help='Should this rule be used when using the USB Synchronization engine?', required=True),
        
        # specifies the direction of the USB synchronisation - like the 'direction' field
        'direction_remote_warehouse': fields.selection((('rw_to_cp', 'Remote Warehouse to Central Platform'), ('cp_to_rw', 'Central Platform to Remote Warehouse'), ('bidirectional','Bidirectional')), 'Direction', help='The direction of the synchronization', required=True),
    }
    
    _defaults = {
        'horizontal': False,
        'direction_remote_warehouse': 'bidirectional',
    }
    
    def unlink(self, cr, uid, ids, context=None):
        raise osv.except_osv('Cannot Delete','You cannot delete Sync Rules. Instead, please mark them as inactive.')

SyncRule()