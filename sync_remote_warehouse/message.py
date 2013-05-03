from osv import osv, fields

class MessageReceived(osv.osv):
    _inherit = 'sync.client.message_received'
    _name = 'sync_remote_warehouse.message_received'

MessageReceived()

class MessageToSend(osv.osv):
    _inherit = 'sync.client.message_to_send'
    _name = 'sync_remote_warehouse.message_to_send'

MessageToSend()