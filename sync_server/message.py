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
import pprint
import logging
pp = pprint.PrettyPrinter(indent=4)

def log(model, cr, uid, message, ids=False, data=False, context=None):
    #more complete log system
    print("Error : " + message)
    pp.pprint(data)

class message(osv.osv):
    _name = "sync.server.message"
    _rec_name = 'identifier'
    
    __logger = logging.getLogger('sync.server')
    _columns = {
        'identifier': fields.char('Identifier', size=128, select=True),
        'sent': fields.boolean('Sent to destination ?'),
        'remote_call': fields.text('Method to call', required = True),
        'arguments': fields.text('Arguments of the method', required = True), 
        'destination': fields.many2one('sync.server.entity', string="Destination Instance", select=True),
        'source': fields.many2one('sync.server.entity', string="Source Instance"), 
        'sequence': fields.integer('Sequence', required = True),
    }
    
    _order = 'sequence asc'

    _defaults = {
        'sequence' : lambda self, cr, uid, *a: int(self.pool.get('ir.sequence').get(cr, uid, 'sync.message')),
    }

    def unfold_package(self, cr, uid, entity, package, context=None):
        for data in package:
            
            destination = self._get_destination(cr, uid, data['dest'], context=context)
            if not destination:
                log(self, cr, uid, 'destination %s does not exist' % data['dest'])
                continue
            ids = self.search(cr, uid, [('identifier', '=', data['id'])], context=context)
            if ids: 
                log(self, cr, uid, 'Message %s already in the server database' % data['id'])
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
        entity_obj = self.pool.get('sync.server.entity')
        ids = entity_obj.get(cr, uid, name=dest, context=context)
        if ids:
            return ids[0]
        else:
            return False
        
    def get_message_packet(self, cr, uid, entity, size, context=None):
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
        ids = self.search(cr, uid, [('identifier', 'in', message_uuids), ('destination', '=', entity.id)], context=context)
        if ids:
            self.write(cr, uid, ids, {'sent' : True}, context=context)
        return True
        
    def recovery(self, cr, uid, entity, start_seq, context=None):
        ids = self.search(cr, uid, [('sequence', '>', start_seq), ('destination', '=', entity.id)], context=context)
        if ids:
            print "recovery", ids
            self.write(cr, uid, ids, {'sent' : False}, context=context)
            self.__logger.debug("These ids will be recovered: %s" % str(ids))
        else:
            self.__logger.debug("No ids to be recover! domain=%s" % str([('sequence', '>=', start_seq), ('destination', '=', entity.id)]))
        return True
        
message()
    
