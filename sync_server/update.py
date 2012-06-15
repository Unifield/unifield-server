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
import tools
import pprint
pp = pprint.PrettyPrinter(indent=4)

from tools.safe_eval import safe_eval as eval

class update(osv.osv):
    """
        States : to_send : need to be sent to the server or the server ack still not received
                 sended : Ack for this update received but session not ended
                 validated : ack for the session of the update received, this update can be deleted
    """
    _name = "sync.server.update"
    _rec_name = 'source'

    _columns = {
        'source': fields.many2one('sync.server.entity', string="Source Instance", select=True), 
        'owner': fields.many2one('sync.server.entity', string="Owner Instance", select=True), 
        'model': fields.char('Model', size=128, readonly=True),
        'session_id': fields.char('Session Id', size=128),
        'sequence': fields.integer('Sequence'),
        'version': fields.integer('Record Version'),
        'rule_id': fields.many2one('sync_server.sync_rule','Generating Rule', readonly=True, ondelete="set null", select=True),
        'fields': fields.text("Fields"),
        'values': fields.text("Values"),
        'create_date': fields.datetime('Synchro Date/Time', readonly=True),
        'puller_ids': fields.many2many('sync.server.entity', 'sync_server_entity_rel', 'entity_id', 'update_id', string="Pulled by")
    }

    _order = 'sequence, create_date desc'
    
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
    
    def get_update_to_send(self,cr, uid, entity, update_ids, context=None):
        update_to_send = []
        ancestor = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, entity.id, context=context) 
        children = self.pool.get('sync.server.entity')._get_all_children(cr, uid, entity.id, context=context)
        for update in self.browse(cr, uid, update_ids, context=context):
            if update.rule_id.direction == 'bi-private':
                if not update.owner:
                    print "No owner specified even if in bi-private rule! => Works like a bidirectional rule"
                    privates = [entity.id]
                else:
                    privates = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, update.owner.id, context=context) + \
                               self.pool.get('sync.server.entity')._get_all_children(cr, uid, update.owner.id, context=context) + \
                               [update.owner.id]
            else:
                privates = []
            if (update.rule_id.direction == 'up' and update.source.id in children) or \
               (update.rule_id.direction == 'down' and update.source.id in ancestor) or \
               (update.rule_id.direction == 'bidirectional') or \
               (entity.id in privates):
                
                source_rules_ids = self.pool.get('sync_server.sync_rule')._get_group_per_rules(cr, uid, update.source, context)
                s_group = source_rules_ids.get(update.rule_id.id, [])
                for group in entity.group_ids:
                    if group.id in s_group:
                        update_to_send.append(update)
                        print "Update prepared for %s (source %s)" % (entity.name, update.source.name)
        return update_to_send

    def _save_puller(self, cr, uid, ids, context, entity_id):
        return self.write(cr, 1, ids, {'puller_ids': [(4, entity_id)]}, context)

    
    def get_package(self, cr, uid, entity, last_seq, offset, max_size, max_seq, recover=False, context=None):
        rules = self.pool.get('sync_server.sync_rule')._compute_rules_to_receive(cr, uid, entity, context)
        
        if not recover:
            ids = self.search(cr, uid, [('rule_id', 'in', rules), 
                                    ('source', '!=', entity.id), #avoid receiving his own update
                                    ('sequence', '>', last_seq), 
                                    ('sequence', '<=', max_seq)], context=context)
        else:
            ids = self.search(cr, uid, [('rule_id', 'in', rules), 
                                    ('sequence', '>', last_seq), 
                                    ('sequence', '<=', max_seq)], context=context)
        update_to_send = self.get_update_to_send(cr, uid, entity, ids, context)
        #offset + limit 
        update_to_send = update_to_send[offset:offset+max_size]
        self._save_puller(cr, uid, [up.id for up in update_to_send], context, entity.id)
        if not update_to_send:
            print "No update to send to %s" %(entity.name,)
            return False
        update_master = update_to_send[0]
        complete_fields = self.get_additional_forced_field(update_master) 
        data = {
            'model' : update_master.model,
            'source_name' : update_master.source.name,
            'fields' : tools.ustr(complete_fields),
            'sequence' : update_master.sequence,
            'fallback_values' : update_master.rule_id.fallback_values
        }
        load = []
        for update in update_to_send:
            if update.model != update_master.model or \
               update.rule_id.id != update_master.rule_id.id or \
               update_master.source.id != update.source.id:
                break
            load.append({
                'version' : update.version,
                'values' : self.set_forced_values(update, complete_fields),
                'owner_name' : update.owner.name if update.owner else '',
            })
        data['load'] = load
        return data
    
    def get_additional_forced_field(self, update): 
        if not update.rule_id.forced_values:
            return eval(update.fields)
        
        fields = eval(update.fields)
        forced_values = eval(update.rule_id.forced_values)  
        
        for key in forced_values.keys():
            if not key in fields:
                fields.append(key)
                
        return fields
                
    def set_forced_values(self, update, fields):
        if not update.rule_id.forced_values:
            return update.values
        
        values = eval(update.values)
        forced_values = eval(update.rule_id.forced_values)
        
        #step 1 : inside the values
        for key in fields[:len(values)]:
            val = forced_values.get(key)
            if val:
                i = fields.index(key)
                values[i] = val
                
        #step 2 : outside the values    
        for key in fields[len(values):]:
            val = forced_values.get(key)
            if val:
                values.append(val)      

        return tools.ustr(values)
    
    _order = 'sequence asc, id asc'
    
update()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

