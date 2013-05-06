from osv import osv, fields

class local_message_rule_usb(osv.osv):

    _inherit = 'sync.client.message_rule'

    _columns = {
        # Specifies that this rule is a rule for USB synchronisations
        'usb': fields.boolean('Remote Warehouse Rule', help='Should this rule be used when using the USB Synchronization engine?', required=True),
    }
    
    _defaults = {
        'usb': False,
    }
    
    def _where_calc(self, cr, user, domain, active_test=True, context=None):
        domain = list(domain or [])
        if not filter(lambda e:hasattr(e, '__iter__') and e[0] == 'usb', domain):
            domain.insert(0, ('usb','=',False))
        return super(local_message_rule_usb, self)._where_calc(cr, user, domain, active_test=active_test, context=context)

local_message_rule_usb()