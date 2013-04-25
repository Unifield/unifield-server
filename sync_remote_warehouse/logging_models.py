from osv import osv, fields

class UpdateReceived(osv.osv):
    _inherit = 'sync.client.update_received'
    _name = 'sync_remote_warehouse.update_received'

UpdateReceived()

class UpdateToSend(osv.osv):
    _inherit = 'sync.client.update_to_send'
    _name = 'sync_remote_warehouse.update_to_send'
    
    def sync_finished(self, cr, uid, update_ids, sync_field='sync_date', context=None):
        return super(UpdateToSend, self).sync_finished(cr, uid, update_ids, sync_field="usb_sync_date", context=context)

UpdateToSend()

class MessageReceived(osv.osv):
    _inherit = 'sync.client.message_received'
    _name = 'sync_remote_warehouse.message_received'

MessageReceived()

class MessageToSend(osv.osv):
    _inherit = 'sync.client.message_to_send'
    _name = 'sync_remote_warehouse.message_to_send'

MessageToSend()