from osv import osv, fields

class MessageReceived(osv.osv):
    _inherit = 'sync.client.message_received'
    _name = 'sync_remote_warehouse.message_received'

MessageReceived()

class MessageToSend(osv.osv):
    _inherit = 'sync.client.message_to_send'
    _name = 'sync_remote_warehouse.message_to_send'
    
    def get_message_packet(self, cr, uid, context=None):
        packet = []
        for message in self.browse(cr, uid, self.search(cr, uid, [('sent','=',False)], context=context), context=context):
            packet.append({
                'id' : message.identifier,
                'call' : message.remote_call,
                'dest' : message.destination_name,
                'args' : message.arguments,
            })
            
        return packet

MessageToSend()