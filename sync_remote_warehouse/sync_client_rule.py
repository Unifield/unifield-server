from osv import osv, fields

class SyncClientRule(osv.osv):
    _inherit = 'sync.client.rule'
    _name = 'sync.client.rule'
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
    
    # override unlink to instead mark rule as inactive
    def unlink(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'active': False});

    # TODO: REMOVE ME WHEN MERGED INTO DELETE RULES BRANCH AS THIS CHANGE HAS BEEN MADE GENERIC THERE
    # override create to check if rule already exists and update it (and activate it, as at start of rule update process all rules are deleted, thus inactive)
    def create(self, cr, uid, vals, context=None):
        existing_search = self.search(cr, uid, [('server_id','=',vals['server_id']), '|', ('active','=',False), ('active','=',True)])
        if existing_search:
            self.write(cr, uid, existing_search, vals)
            return existing_search[0]
        else:
            return super(SyncClientRule, self).create(cr, uid, vals, context=context)

SyncClientRule()
