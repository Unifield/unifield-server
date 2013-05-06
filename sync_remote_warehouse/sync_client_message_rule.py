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

local_message_rule_usb()