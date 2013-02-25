# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from osv import fields
from tools.translate import _

import logging
from sync_common.common import sync_log

class message(osv.osv):
    _name = "sync.server.message"
    _rec_name = 'identifier'
    
    _columns = {
        'identifier': fields.char('Identifier', size=128, select=True),
        'sent': fields.boolean('Sent to destination ?', select=True),
        'remote_call': fields.text('Method to call', required = True),
        'arguments': fields.text('Arguments of the method', required = True), 
        'destination': fields.many2one('sync.server.entity', string="Destination Instance", select=True),
        'source': fields.many2one('sync.server.entity', string="Source Instance"), 
        'sequence': fields.integer('Sequence', required=True, select=True),
    }
    
    _order = 'sequence asc'

    _defaults = {
        'sequence' : lambda self, cr, uid, *a: int(self.pool.get('ir.sequence').get(cr, uid, 'sync.message')),
    }

    _logger = logging.getLogger('sync.server')

    def unfold_package(self, cr, uid, entity, package, context=None):
        """
            unfold_package() is called by the XML RPC method receive_package() when the client instance try to push
            packages on the synchro server.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param size : dict : package with datas
            @param context : context

            @return : tuple : (a,b)
                     a : boolean : is True is if the call is succesfull, False otherwise
                     b : string : is an error message if a is False
        """
        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Pushing messages...'))

        for data in package:
            destination = self._get_destination(cr, uid, data['dest'], context=context)
            if not destination:
                sync_log(self, 'destination %s does not exist' % data['dest'])
                continue
            ids = self.search(cr, uid, [('identifier', '=', data['id'])], context=context)
            if ids: 
                sync_log(self, 'Message %s already in the server database' % data['id'])
                continue
            self.create(cr, uid, {
                'identifier': data['id'],
                'remote_call': data['call'],
                'arguments': data['args'],
                'destination': destination,
                'source': entity.id,
            }, context=context)

        return (True, "Message received")
    
    def _get_destination(self, cr, uid, dest, context=None):
        """
            Private destination getter.

            @param cr : cr
            @param uid : uid
            @param dest : str : destination name
            @param context : context

            @return : id of the entity which have name matching the argument
        """
        entity_obj = self.pool.get('sync.server.entity')
        ids = entity_obj.get(cr, uid, name=dest, context=context)
        if ids:
            return ids[0]
        else:
            return False
        
    def get_message_packet(self, cr, uid, entity, size, context=None):
        """
            get_message_packet() is called by the XML RPC method get_message() when the client instance try to pull its
            messages.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param size : The number of message max per request.
            @param context : context

            @return : list : list of messages
        """
        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Pulling messages...'))

        ids = self.search(cr, uid, [('destination', '=', entity.id), ('sent', '=', False)], limit=size, context=context)
        if not ids:
            return False

        packet = []
        for data in self.browse(cr, uid, ids, context=context):
            message = {
                'id': data.identifier,
                'call': data.remote_call,
                'args': data.arguments, 
                'source': data.source.name,
                'sequence' : data.sequence,
            }
            packet.append(message)
             
        return packet
    
    def set_message_as_received(self, cr, uid, entity, message_uuids, context=None):
        """
            Called by XML RPC method message_received when the client instance pull messages and it succeeds.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param message_uuids : list of message uuids to mark as 'sent'
            @param context : context

            @return : True or raise an error
        """
        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Confirm messages...'))

        ids = self.search(cr, uid, [('identifier', 'in', message_uuids), ('destination', '=', entity.id)], context=context)
        if ids:
            self.write(cr, uid, ids, {'sent' : True}, context=context)

        return True
        
    def recovery(self, cr, uid, entity, start_seq, context=None):
        """
            Mark all messages owned by the entity itself as not sent.
            Called by message_received() when client instance try pull all messages, including its self-owned messages.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param start_seq : starting sequence of the messages
            @param context : context

            @return : True or raise an error
        """
        ids = self.search(cr, uid, [('sequence', '>', start_seq), ('destination', '=', entity.id)], context=context)
        if ids:
            self._logger.debug("recovery %s" % ids)
            self.write(cr, uid, ids, {'sent' : False}, context=context)
            self._logger.debug("These ids will be recovered: %s" % str(ids))
        else:
            self._logger.debug("No ids to be recover! domain=%s" % str([('sequence', '>=', start_seq), ('destination', '=', entity.id)]))
        return True
        
message()
    
