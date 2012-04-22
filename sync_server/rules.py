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

class sync_rule(osv.osv):
    """ Synchronization Rule """

    _name = "sync_server.sync_rule"
    _description = "Synchronization Rule"

    _columns = {
        'name': fields.char('Rule Name', size=64, required = True),
        'model_id': fields.char('Model', size=128, required = True),
        'applies_to_type': fields.boolean('Applies to type', help='Applies to a group type instead of a specific group'),
        'group_id': fields.many2one('sync.server.entity_group','Group'),
        'type_id': fields.many2one('sync.server.group_type','Group Type'),
        'direction': fields.selection([('up', 'Up'),('down', 'Down'),
                    ('bidirectional', 'Bidirectional'),],
                    'Directionality',required = True,),
        'domain':fields.text('Domain', required = False),
        'sequence_number': fields.integer('Sequence', required = True),
        'included_fields':fields.text('Fields to include', required = True),
        'forced_values':fields.text('Values to force', required = False),
        'fallback_values':fields.text('Fallback values', required = False),
        'active': fields.boolean('Active'),
    }

    _order = 'sequence_number asc,model_id asc'
    
    #TODO add a last update to send only rule that were updated before => problem of dates
    def _get_rule(self, cr, uid, entity, context=None):
        rules_ids = self._compute_rules_to_send(cr, uid, entity, context)
        return (True, self._serialize_rule(cr, uid, rules_ids, context))
        
    def get_groups(self, cr, uid, ids, context=None):
        groups = []
        for entity in self.pool.get("sync.server.entity").browse(cr, uid, ids, context=context):
            groups.extend([group.id for group in entity.group_ids])
        return groups
    
    def _get_ancestor_groups(self, cr, uid, entity, context=None):
        ancestor_list = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, entity.id, context=context)
        return self.get_groups(cr, uid, ancestor_list, context=context)
        
    def _get_children_groups(self, cr, uid, entity, context=None):
        children_list = self.pool.get('sync.server.entity')._get_all_children(cr, uid, entity.id, context=context)
        return self.get_groups(cr, uid, children_list, context=context)
    
    def _get_rules_per_group(self, cr, uid, entity, context=None):
        rules_ids = {}
        for group in entity.group_ids:
            domain = ['|',
                    '&', ('group_id', '=', group.id), ('applies_to_type', '=', False),
                    '&', ('type_id', '=', group.type_id.id), ('applies_to_type', '=', True)]
            ids = self.search(cr, uid, domain, context=context)
            if ids:
                rules_ids[group.id] = ids
        
        return rules_ids
    
    def _get_group_per_rules(self, cr, uid, entity, context=None):
        group_ids = {}
        for group in entity.group_ids:
            domain = ['|',
                    '&', ('group_id', '=', group.id), ('applies_to_type', '=', False),
                    '&', ('type_id', '=', group.type_id.id), ('applies_to_type', '=', True)]
            ids = self.search(cr, uid, domain, context=context)
            for i in ids:
                if not group_ids.get(i):
                    group_ids[i] = [group.id]
                else:
                    group_ids[i].append(group.id)
        
        return group_ids
        
    #TODO check when member of two group with the same type : duplicate rules
    def _compute_rules_to_send(self, cr, uid, entity, context=None):
        rules_ids = self._get_rules_per_group(cr, uid, entity, context)
        ancestor_group = self._get_ancestor_groups(cr, uid, entity, context)
        children_group = self._get_children_groups(cr, uid, entity, context)
        
        rules_to_send = []
        for group_id, rule_ids in rules_ids.items():
            for rule in self.browse(cr, uid, rule_ids):
                if rule.direction == 'bidirectional':
                    rules_to_send.append(rule.id)
                elif rule.direction == 'up' and entity.parent_id: #got a parent in the same group
                    if group_id in ancestor_group:
                        rules_to_send.append(rule.id)
                elif rule.direction == 'down' and entity.children_ids: #got children in the same group
                    if group_id in children_group:
                        rules_to_send.append(rule.id)
                    
        return rules_to_send
    
    def _compute_rules_to_receive(self, cr, uid, entity, context=None):
        rules_ids = self._get_rules_per_group(cr, uid, entity, context)
        rules_to_send = []
        for group_id, rule_ids in rules_ids.items():
            rules_to_send.extend(rule_ids)
                    
        return rules_to_send
    
    def _serialize_rule(self, cr, uid, ids, context=None):
        rules_data = []
        for rule in self.browse(cr, uid, ids, context=context):
            data = {
                    'server_id' : rule.id,
                    'name' : rule.name,
                    'model' : rule.model_id,
                    'domain' : rule.domain,
                    'sequence_number' : rule.sequence_number,
                    'included_fields' : rule.included_fields,
            }
            rules_data.append(data)
        return rules_data
            
sync_rule()

class message_rule(osv.osv):
    """ Message creation rules """

    _name = "sync_server.message_rule"
    _description = "Message Rule"

    _columns = {
        'name': fields.char('Rule Name', size=64, required = True),
        'model_id': fields.char('Model', size=128, required = True),
        'applies_to_type': fields.boolean('Applies to type', help='Applies to a group type instead of a specific group'),
        'group_id': fields.many2one('sync.server.entity_group','Group'),
        'type_id': fields.many2one('sync.server.group_type','Group Type'),
        'domain': fields.text('Domain', required = False),
        'sequence_number': fields.integer('Sequence', required = True),
        'remote_call': fields.text('Method to call', required = True),
        'arguments': fields.text('Arguments of the method', required = True),
        'destination_name': fields.char('Fields to extract destination', size=256, required = True),
        'status': fields.selection([('valid','Valid'),('invalid','Invalid'),('not-checked','Not checked'),], 'Status', required = True, readonly = True),
        'active': fields.boolean('Active'),
    }

    _defaults = {
        'status': 'not-checked',
        #FIXME: it is said in analysis that active must be True by default
        #       but it is wrong because it needs validation before proceed
        'active': False,
        'applies_to_type' : True,
    }

    _order = 'sequence_number asc,model_id asc'

    def _get_message_rule(self, cr, uid, entity, context=None):
        rules_ids = self._get_rules(cr, uid, entity, context)
        rules_data = self._serialize_rule(cr, uid, rules_ids, context)
        return rules_data
    
    def _get_rules(self, cr, uid, entity, context=None):
        rules_ids = []
        for group in entity.group_ids:
            domain = ['|',
                    '&', ('group_id', '=', group.id), ('applies_to_type', '=', False),
                    '&', ('type_id', '=', group.type_id.id), ('applies_to_type', '=', True)]
            ids = self.search(cr, uid, domain, context=context)
            if ids:
                rules_ids.extend(ids)
        
        return rules_ids
    
    def _serialize_rule(self, cr, uid, ids, context=None):
        rules_data = []
        for rule in self.browse(cr, uid, ids, context=context):
            data = {
                    'name' : rule.name,
                    'server_id' : rule.id,
                    'model' : rule.model_id,
                    'domain' : rule.domain,
                    'sequence_number' : rule.sequence_number,
                    'remote_call' : rule.remote_call,
                    'arguments' : rule.arguments,
                    'destination_name' : rule.destination_name,
            }
            rules_data.append(data)
        return rules_data

    def validate(self, cr, uid, ids, context=None):
        error = None
        for rec in self.browse(cr, uid, ids, context=context):
            try:
                # Check domain syntax
                try: eval(rec.domain)
                except: raise StandardError, "Syntax error in domain!"
                # TODO Remote Call Possible
                pass
                # Arguments of the call syntax and existence
                try:
                    arguments = eval(rec.arguments)
                except:
                    raise StandardError, "Syntax error in arguments!"
                else:
                    for arg in arguments:
                        # TODO : arguments existence
                        pass
                # Sequence is unique
                if self.search(cr, uid, [('sequence_number','=',rec.sequence_number)], context=context, count = True) > 1:
                    raise StandardError, "The sequence #"+str(rec.sequence_number)+" already exists!"
            except StandardError, e:
                error = 'This rule cannot be validated for the following reason:\n\n'+str(e)
                break
        self.write(cr, uid, ids, {'status': ('valid' if not error else 'invalid')})
        ## FIXME replace the following two-three lines.
        ##       (How to simply print a message box?)
        cr.commit()
        if error: raise osv.except_osv('Unable to comply', error)
        return {'type': 'ir.actions.act_window_close',}

message_rule()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

