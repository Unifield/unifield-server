from osv import osv, fields

class SyncMonitor(osv.osv):
    _inherit = 'sync.monitor'
    _columns = {
        # Specifies that this rule is a rule for USB synchronisations
        'usb': fields.boolean('USB Sync'),
    }
    _defaults = {
        'usb' : False
    }
SyncMonitor()
