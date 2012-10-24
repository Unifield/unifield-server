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

from __future__ import with_statement

from osv import orm, osv
from osv import fields
import tools
import pprint
pp = pprint.PrettyPrinter(indent=4)
import logging
from tools.safe_eval import safe_eval as eval
import threading

class SavePullerCache(object):
    def __init__(self, model):
        self.__model__ = model
        self.__cache__ = []
        self.__lock__ = threading.Lock()

    def add(self, entity, updates):
        if not updates:
            return
        if isinstance(updates[0], orm.browse_record):
            update_ids = (x.id for x in updates)
        else:
            update_ids = tuple(updates)
        if isinstance(entity, orm.browse_record):
            entity_id = entity.id
        else:
            entity_id = entity
        with self.__lock__:
            self.__cache__.append( (entity_id, update_ids) )

    def merge(self, cr, uid, context=None):
        if not self.__cache__:
            return
        with self.__lock__:
            cache, self.__cache__ = self.__cache__, type(self.__cache__)()
        todo = {}
        for entity_id, updates in cache:
            for update_id in updates:
                try:
                    todo[update_id].add( entity_id )
                except KeyError:
                    todo[update_id] = set([entity_id])
        for id, entity_ids in todo.items():
            puller_ids = [(4, x) for x in entity_ids]
            self.__model__.write(cr, uid, [id], {'puller_ids': puller_ids}, context)

class update(osv.osv):
    """
        States : to_send : need to be sent to the server or the server ack still not received
                 sended : Ack for this update received but session not ended
                 validated : ack for the session of the update received, this update can be deleted
    """
    _name = "sync.server.update"
    _rec_name = 'source'
    
    _logger = logging.getLogger('sync.server')

    _columns = {
        'source': fields.many2one('sync.server.entity', string="Source Instance", select=True), 
        'owner': fields.many2one('sync.server.entity', string="Owner Instance", select=True), 
        'model': fields.char('Model', size=128, readonly=True),
        'session_id': fields.char('Session Id', size=128),
        'sequence': fields.integer('Sequence', select=True),
        'version': fields.integer('Record Version'),
        'rule_id': fields.many2one('sync_server.sync_rule','Generating Rule', readonly=True, ondelete="set null", select=True),
        'fields': fields.text("Fields"),
        'values': fields.text("Values"),
        'create_date': fields.datetime('Synchro Date/Time', readonly=True),
        'puller_ids': fields.many2many('sync.server.entity', 'sync_server_entity_rel', 'entity_id', 'update_id', string="Pulled by")
    }

    _order = 'sequence, create_date desc'
    
    def __init__(self, pool, cr):
        self._cache_pullers = SavePullerCache(self)
        super(update, self).__init__(pool, cr)

    def _save_puller(self, cr, uid, context=None):
        return self._cache_pullers.merge(cr, uid, context)

    def unfold_package(self, cr, uid, entity, packet, context=None):
        data = {
            'source': entity.id,
            'model': packet['model'],
            'session_id': packet['session_id'],
            'rule_id': packet['rule_id'],
            'fields': packet['fields']
        }
        
        for update in packet['load']:
            if 'owner' not in update: raise Exception, "Packet field 'owner' absent"
            else:
                owner = self.pool.get('sync.server.entity').search(cr, uid, [('name','=',update['owner'])], limit=1)
                owner = owner[0] if owner else 0
            data.update({
                'version': update['version'],
                'values': update['values'],
                'owner': owner,
            })
            ids = self.search(cr, uid, [('version', '=', data['version']), 
                                        ('session_id', '=', data['session_id']),
                                        ('owner','=', data['owner']),
                                        ('values', '=', data['values'])], context=context)
            if ids: #Avoid add two time the same update.
                continue
            self.create(cr, uid, data,context=context)
            
        return True
    
    
    def confirm_updates(self, cr, uid, entity, session_id, context=None):
        update_ids = self.search(cr, uid, [('session_id', '=', session_id), ('source', '=', entity.id)], context=context)
        sequence = self._get_next_sequence(cr, uid, context=context)
        self.write(cr, 1, update_ids, {'sequence' : sequence}, context=context)
        return (True, "Push session validated")
        
    def _get_next_sequence(self, cr, uid, context=None):
        return self.get_last_sequence(cr, uid, context) + 1
    
    def get_last_sequence(self, cr, uid, context=None):
        ids = self.search(cr, uid, [('sequence', '!=', 0)], order="sequence desc, id desc", limit=1, context=context)
        if not ids:
            return 0
        seq = self.browse(cr, uid, ids, context=context)[0].sequence
        return seq
    
    def get_update_to_send(self,cr, uid, entity, update_ids, recover=False, context=None):
        update_to_send = []
        ancestor = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, entity.id, context=context) 
        children = self.pool.get('sync.server.entity')._get_all_children(cr, uid, entity.id, context=context)
        for update in self.browse(cr, uid, update_ids, context=context):
            if update.rule_id.direction == 'bi-private':
                if not update.owner:
                    privates = []
                else:
                    privates = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, update.owner.id, context=context) + \
                               [update.owner.id]
            else:
                privates = []
            if (update.rule_id.direction == 'up' and update.source.id in children) or \
               (update.rule_id.direction == 'down' and update.source.id in ancestor) or \
               (update.rule_id.direction == 'bidirectional') or \
               (entity.id in privates) or \
               (recover and entity.id == update.source.id):
                
                source_rules_ids = self.pool.get('sync_server.sync_rule')._get_groups_per_rule(cr, uid, update.source, context)
                s_group = source_rules_ids.get(update.rule_id.id, [])
                for group in entity.group_ids:
                    if group.id in s_group:
                        update_to_send.append(update)
        return update_to_send

    def get_package(self, cr, uid, entity, last_seq, offset, max_size, max_seq, recover=False, context=None):
        rules = self.pool.get('sync_server.sync_rule')._compute_rules_to_receive(cr, uid, entity, context)
        if not rules:
            return None
        
        base_query = ("""SELECT "sync_server_update".id FROM "sync_server_update" WHERE sync_server_update.rule_id in ("""+"%s,"*(len(rules)-1)+"%s"+""") AND sync_server_update.sequence > %s AND sync_server_update.sequence <= %s""") % (tuple(rules) + (last_seq, max_seq))

        ## Recover add own client updates to the list
        if not recover:
            base_query += " AND sync_server_update.source != %s" % entity.id

        base_query += " ORDER BY sequence ASC, id ASC OFFSET %s LIMIT %s"

        ## Search first update which is "master", then find next updates to send
        ids = []
        update_to_send = []
        update_master = None
        while not ids or not update_to_send:
            query = base_query % (offset, max_size)
            cr.execute(query)
            ids = map(lambda x:x[0], cr.fetchall())
            if not ids and update_master is None:
                return None
            for update in self.get_update_to_send(cr, uid, entity, ids, recover, context):
                if update_master is None:
                    update_master = update
                    update_to_send.append(update_master)
                elif update.model == update_master.model and \
                   update.rule_id.id == update_master.rule_id.id and \
                   update.source.id == update_master.source.id and \
                   len(update_to_send) < max_size:
                    update_to_send.append(update)
                else:
                    ids = ids[:ids.index(update.id)]
                    break
            offset += len(ids)

        if not update_to_send:
            self._logger.debug("No update to send to %s" % (entity.name,))
            return None

        # Point of no return
        self._cache_pullers.add(entity, update_to_send)

        ## Prepare package
        complete_fields, forced_values = self.get_additional_forced_field(update_master) 
        data = {
            'model' : update_master.model,
            'source_name' : update_master.source.name,
            'fields' : tools.ustr(complete_fields),
            'sequence' : update_master.sequence,
            'rule' : update_master.rule_id.sequence_number,
            'fallback_values' : update_master.rule_id.fallback_values,
            'load' : list(),
            'offset' : offset,
        }

        ## Process & Push all updates in the packet
        for update in update_to_send:
            values = dict(zip(complete_fields[:len(update.values)], eval(update.values)) + \
                          forced_values.items())
            data['load'].append({
                'version' : update.version,
                'values' : tools.ustr([values[k] for k in complete_fields]),
                'owner_name' : update.owner.name if update.owner else '',
            })

        return data
    
    def get_additional_forced_field(self, update): 
        fields = eval(update.fields)
        forced_values = eval(update.rule_id.forced_values or '{}')
        if forced_values:
            fields += list(set(forced_values.keys()) - set(fields))
            obj = self.pool.get(update.model)
            columns = dict(obj._inherit_fields.items() + \
                           obj._columns.items())
            for k, v in forced_values.items():
                if columns[k]._type == 'boolean':
                    forced_values[k] = unicode(v)
        return fields, forced_values

    _order = 'sequence asc, id asc'
    
update()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

