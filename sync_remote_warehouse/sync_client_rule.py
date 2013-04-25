from osv import osv, fields

class SyncClientRule(osv.osv):
    _inherit = 'sync.client.rule'

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
    
    def _where_calc(self, cr, user, domain, active_test=True, context=None):
        domain = list(domain or [])
        if not filter(lambda e:hasattr(e, '__iter__') and e[0] == 'usb', domain):
            domain.insert(0, ('usb','=',False))
        return super(SyncClientRule, self)._where_calc(cr, user, domain, active_test=active_test, context=context)
    
SyncClientRule()
