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
        entity = self.pool.get('sync.client.entity').get_entity(cr, uid, context)
        # UF-2377: The order of message created and put into the zip file must respect the order of creation of rw messages
        message_to_send_ids = self.search(cr, uid, [('sent', '=', False)], order='id asc', context=context)
        for message in self.browse(cr, uid, message_to_send_ids, context=context):
            packet.append({
                'id' : message.identifier,
                'remote_call' : message.remote_call,
                'source' : entity.name,
                'arguments' : message.arguments,
            })
            
        return packet

MessageToSend()