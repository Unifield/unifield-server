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
import sync_common.common
from tools.translate import _
from datetime import datetime

_field2type = {
    'text'      : 'str',
    'char'      : 'str',
    'selection' : 'str',
    'integer'   : 'int',
    'boolean'   : 'bool',
    'float'     : 'float',
    'datetime'  : 'str',
}

class sync_rule(osv.osv):
    """ Synchronization Rule """

    _name = "sync_server.sync_rule"
    _description = "Synchronization Rule"

    def _get_model_id(self, cr, uid, ids, field, args, context=None):
        res = {}
        for rec in self.read(cr, uid, ids, ['model_ref'], context=context):
            if not rec['model_ref']: continue
            model = self.pool.get('ir.model').read(cr, uid, [rec['model_ref'][0]], ['model'])[0]
            res[rec['id']] = model['model']
        return res

    def _get_model_name(self, cr, uid, ids, field, value, args, context=None):
        model_ids = self.pool.get('ir.model').search(cr, uid, [('model','=',value)], context=context)
        if model_ids:
            self.write(cr, uid, ids, {'model_ref' : model_ids[0]}, context=context)
        return True

    _columns = {
        'name': fields.char('Rule Name', size=64, required = True),
        #'model_id': fields.char('Model', size=128, required = True),
        'model_id': fields.function(_get_model_id, string = 'Model', fnct_inv=_get_model_name, type = 'char', size = 64, method = True, store = True),
        'model_ref': fields.many2one('ir.model', 'Model'),
        'applies_to_type': fields.boolean('Applies to type', help='Applies to a group type instead of a specific group'),
        'group_id': fields.many2one('sync.server.entity_group','Group'),
        'type_id': fields.many2one('sync.server.group_type','Group Type'),
        'direction': fields.selection([
                    ('up', 'Up'),
                    ('down', 'Down'),
                    ('bidirectional', 'Bidirectional'),
                    ('bi-private', 'Bidirectional-Private'),
                    ], 'Directionality', required = True,),
        'domain':fields.text('Domain', required = False),
        'owner_field':fields.char('Owner Field', size = 64, required = False),
        'sequence_number': fields.integer('Sequence', required = True),
        'included_fields_sel': fields.many2many('ir.model.fields', 'ir_model_fields_rules_rel', 'field', 'name', 'Select Fields'),
        'included_fields':fields.text('Fields to include', required = False, readonly = True),
        'forced_values_sel': fields.one2many('sync_server.sync_rule.forced_values', 'sync_rule_id', 'Select Forced Values'),
        'forced_values':fields.text('Values to force', required = False, readonly = True),
        'fallback_values_sel': fields.one2many('sync_server.sync_rule.fallback_values', 'sync_rule_id', 'Select Fallback Values'),
        'fallback_values':fields.text('Fallback values', required = False),
        'status': fields.selection([('valid','Valid'),('invalid','Invalid'),], 'Status', required = True, readonly = True),
        'active': fields.boolean('Active'),
    }

    _defaults = {
        'active': False,
        'status': 'invalid',
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
                    'owner_field' : rule.owner_field,
                    'model' : rule.model_id,
                    'domain' : rule.domain,
                    'sequence_number' : rule.sequence_number,
                    'included_fields' : rule.included_fields,
            }
            rules_data.append(data)
        return rules_data

    
    """
        Usability Part
    """
    
    def on_change_included_fields(self, cr, uid, ids, fields, model_ref, context=None):
        values = self.invalidate(cr, uid, ids, model_ref, context=context)['value']
        sel = self._compute_included_field(cr, uid, ids, fields[0][2], context)
        values.update( {'included_fields' : sel})
        return {'value': values}
    
    def _compute_included_field(self, cr, uid, ids, fields, context=None):
        sel = []
        for field in self.pool.get('ir.model.fields').read(cr, uid, fields, ['name','model','ttype']):
            name = str(field['name'])
            if field['ttype'] in ('many2one','one2many', 'many2many'): name += '/id'
            sel.append(name)
        return (str(sel) if sel else '')
    
    def compute_forced_value(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'active' : False, 'status' : 'invalid' }, context=context)
        sel = {}
        errors = []
        for rule in self.browse(cr, uid, ids, context=context):
            for value in rule.forced_values_sel:
                
                print value
                # Get field information
                field = self.pool.get('ir.model.fields').read(cr, uid, value.name.id, ['name','model','ttype'])
                # Try to evaluate value and stringify it on failed
                try: value = eval(value.value)
                except: value = '"""'+ value.value +'"""'
                # Type checks
                try:
                    if not (isinstance(value, bool) and value == False):
                        # Cast value to the destination type
                        if field['ttype'] in _field2type: value = eval('%s(%s)' % (_field2type[field['ttype']], value))
                        # Evaluate date/datetime
                        if field['ttype'] == 'date': datetime.strptime(value, '%Y-%m-%d')
                        if field['ttype'] == 'datetime': datetime.strptime(value, '%Y-%m-%d %H:%M')
                except:
                    errors.append("%s: type %s incompatible with field of type %s" % (field['name'], type(value).__name__, field['ttype']))
                    continue
                sel[str(field['name'])] = value
            self.write(cr, uid, rule.id, {'forced_values' : (str(sel) if sel else '')}, context=context)
        if errors:
            raise osv.except_osv(_("Warning"), "\n".join(errors))
        
        return True

        
   

    def compute_fallback_value(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'active' : False, 'status' : 'invalid' }, context=context)
        sel = {}
        errors = []
        print "compute fallback value"
        for rule in self.browse(cr, uid, ids, context=context):
            for value in rule.fallback_values_sel:
                field = self.pool.get('ir.model.fields').read(cr, uid, value.name.id, ['name','model','ttype'], context=context)
                
                xml_ids = value.value.get_xml_id(context=context)
                name = str(field['name'])
                if field['ttype'] == 'many2one': 
                    name += '/id'
                sel[name] = xml_ids[value.value.id]

            self.write(cr, uid, rule.id, {'fallback_values' : (str(sel) if sel else '')}, context=context)
        if errors:
            raise osv.except_osv(_("Warning"), "\n".join(errors))
        
        return True 
    
    def invalidate(self, cr, uid, ids, model_ref, context=None):
        print model_ref
        model = ''
        if model_ref:
            model = self.pool.get('ir.model').browse(cr, uid, model_ref, context=context).model
        
        return { 'value' : {'active' : False, 'status' : 'invalid', 'model_id' : model} }
    
    def write(self, cr, uid, ids, values, context=None):
        if 'included_fields_sel' in values and values.get('included_fields_sel')[0][2]:
            print values.get('included_fields_sel')
            values['included_fields'] = self._compute_included_field(cr, uid, ids, values['included_fields_sel'][0][2], context)
        
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
               
        for rule_data in self.read(cr, uid, ids, ['model_id', 'domain', 'sequence_number','included_fields'], context=context):
            dirty = False
            for k in rule_data.keys():
                if k in values and values[k] != rule_data[k]:
                    dirty = True
                    
            if dirty:
                values.update({'active' : False, 'status' : 'invalid'})
        return super(sync_rule, self).write(cr, uid, ids, values, context=context)

    def validate(self, cr, uid, ids, context=None):
        error = False
        message = []
        check_obj = self.pool.get('sync.check_common')
        for rec in self.browse(cr, uid, ids, context=context):
            mess, err = check_obj._check_domain(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            # Check field syntax
            mess, err = check_obj._check_fields(cr, uid, rec, title="* Included fields syntax... ", context=context)
            error = err or error
            message.append(mess)
            # Check force values syntax (can be empty)
            mess, err = check_obj._check_forced_values(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            # Check fallback values syntax (can be empty)
            mess, err = check_obj._check_fallback_values(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            # Check Owner Field
            import ipdb
            ipdb.set_trace()
            mess, err = check_obj._check_owner_field(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            
            message.append("* Sequence is unique... ")
            if self.search(cr, uid, [('sequence_number','=',rec.sequence_number)], context=context, count = True) > 1:
                message.append("failed!\n")
                error = True
            else:
                message.append("pass.\n")
            
            message_header = 'This rule is valid:\n\n' if not error else 'This rule cannot be validated for the following reason:\n\n'
            message_body = ''.join(message)
            message_data = {'state': 'valid' if not error else 'invalid',
                            'message' : message_header + message_body,
                            'sync_rule' : rec.id}
        wiz_id = self.pool.get('sync_server.rule.validation.message').create(cr, uid, message_data, context=context)
        return {
            'name': 'Rule Validation Message',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sync_server.rule.validation.message',
            'res_id' : wiz_id,
            'type': 'ir.actions.act_window',
            'context' : context,
            'target' : 'new',
            }

sync_rule()

class message_rule(osv.osv):
    """ Message creation rules """

    _name = "sync_server.message_rule"
    _description = "Message Rule"

    def _get_model_id(self, cr, uid, ids, field, args, context=None):
        res = {}
        for rec in self.read(cr, uid, ids, ['model_ref'], context=context):
            if not rec['model_ref']: continue
            model = self.pool.get('ir.model').read(cr, uid, [rec['model_ref'][0]], ['model'])[0]
            res[rec['id']] = model['model']
        return res

    def _get_model_name(self, cr, uid, ids, field, value, args, context=None):
        model_ids = self.pool.get('ir.model').search(cr, uid, [('model','=',value)], context=context)
        if model_ids:
            self.write(cr, uid, ids, {'model_ref' : model_ids[0]}, context=context)
        return True

    _columns = {
        'name': fields.char('Rule Name', size=64, required = True),
        'model_id': fields.function(_get_model_id, string = 'Model', fnct_inv=_get_model_name, type = 'char', size = 64, method = True, store = True),
        'model_ref': fields.many2one('ir.model', 'Model'),
        'applies_to_type': fields.boolean('Applies to type', help='Applies to a group type instead of a specific group'),
        'group_id': fields.many2one('sync.server.entity_group','Group'),
        'type_id': fields.many2one('sync.server.group_type','Group Type'),
        'domain': fields.text('Domain', required = False),
        'sequence_number': fields.integer('Sequence', required = True),
        'remote_call': fields.text('Method to call', required = True),
        'arguments': fields.text('Arguments of the method', required = True),
        'destination_name': fields.char('Field to extract destination', size=256, required = True),
        'status': fields.selection([('valid','Valid'),('invalid','Invalid'),], 'Status', required = True, readonly = True),
        'active': fields.boolean('Active'),
    }

    _defaults = {
        'active': False,
        'status': 'invalid',
        'applies_to_type' : True,
    }

    _order = 'sequence_number asc,model_id asc'

    #def default_get(self, cr, uid, fields, context=None):
    #    res = super(message_rule, self).default_get(cr, uid, fields, context=context)
    #    import ipdb
    #    ipdb.set_trace()
    #    return res

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

    def invalidate(self, cr, uid, ids, model_ref, context=None):
        model = ''
        if model_ref:
            model = self.pool.get('ir.model').browse(cr, uid, model_ref, context=context).model
        
        return { 'value' : {'active' : False, 'status' : 'invalid', 'model_id' : model} }
    
    def write(self, cr, uid, ids, values, context=None):
        if 'included_fields_sel' in values:
            values['included_fields'] = self._compute_included_field(cr, uid, ids, values['included_fields_sel'][0][2], context)
            
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
            
        for rule_data in self.read(cr, uid, ids, ['model_id', 'domain', 'sequence_number','remote_call', 'arguments', 'destination_name'], context=context):
            dirty = False
            for k in rule_data.keys():
                if k in values and values[k] != rule_data[k]:
                    dirty = True
            if dirty:
                values.update({'active' : False, 'status' : 'invalid'})
        return super(message_rule, self).write(cr, uid, ids, values, context=context)
    
    def validate(self, cr, uid, ids, context=None):
        error = False
        message = []
        check_obj = self.pool.get('sync.check_common')
        for rec in self.browse(cr, uid, ids, context=context):
            # Check destination_name
            message.append(_("* Destination Name... "))
            try:
                field_ids = self.pool.get('ir.model.fields').search(cr, uid, [('model','=',rec.model_id),('name','=',rec.destination_name)], context=context)
                if not field_ids: raise StandardError
            except:
                message.append("failed! Field %s doesn't exist\n" % rec.destination_name)
                error = True
            else:
                message.append("pass.\n")
                
                
            mess, err = check_obj._check_domain(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            
            # Remote Call Possible
            call_tree = rec.remote_call.split('.')
            call_class = '.'.join(call_tree[:-1])
            call_funct = call_tree[-1]
            message.append(_("* Remote call exists... "))
            ##TODO doesn't work because sync_so needed but it needs sync_client to be installed
            obj = self.pool.get(call_class)
            if not obj:
                message.append("failed! Object %s does not exist \n" % call_class)
                error = True
            elif not hasattr(obj, call_funct):
                message.append("failed! Call %s does not exist \n" % call_funct)
                error = True
            else:
                message.append("pass.\n")
            # Arguments of the call syntax and existence
            
            mess, err = check_obj._check_arguments(cr, uid, rec, title="* Checking arguments..." , context=context)
            error = err or error
            message.append(mess)
            
            # Sequence is unique
            message.append("* Sequence is unique... ")
            if self.search(cr, uid, [('sequence_number','=',rec.sequence_number)], context=context, count = True) > 1:
                message.append("failed!\n")
                error = True
            else:
                message.append("pass.\n")
                
            message_header = 'This rule is valid:\n\n' if not error else 'This rule cannot be validated for the following reason:\n\n'
            message_body = ' '.join(message)
            message_data = {'state': 'valid' if not error else 'invalid',
                            'message' : message_header + message_body,
                            'message_rule' : rec.id}
        wiz_id = self.pool.get('sync_server.rule.validation.message').create(cr, uid, message_data, context=context)
        return {
            'name': 'Rule Validation Message',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sync_server.rule.validation.message',
            'res_id' : wiz_id,
            'type': 'ir.actions.act_window',
            'context' : context,
            'target' : 'new',
            }

message_rule()

class forced_values(osv.osv):
    _name = "sync_server.sync_rule.forced_values"

    _columns = {
        'name' : fields.many2one('ir.model.fields', 'Field Name', required = True),
        'value' : fields.char("Value", size = 1024, required = True),
        'sync_rule_id': fields.many2one('sync_server.sync_rule','Sync Rule', required = True),
    }

forced_values()

class fallback_values(osv.osv):
    _name = "sync_server.sync_rule.fallback_values" 

    def _get_fallback_value(self, cr, uid, context=None):
        obj = self.pool.get('ir.model')
        ids = obj.search(cr, uid, sync_common.common.MODELS_TO_IGNORE)
        res = obj.read(cr, uid, ids, ['model'], context)
        return [(r['model'], r['model']) for r in res]

    _columns = {
        'name' : fields.many2one('ir.model.fields', 'Field Name', required = True),
        'value' : fields.reference("Value", selection = _get_fallback_value, size = 128, required = True),
        'sync_rule_id': fields.many2one('sync_server.sync_rule','Sync Rule', required = True),
    }

fallback_values()
   
    
class validation_message(osv.osv):
    _name = 'sync_server.rule.validation.message'
    
    _rec_name = 'state'
    
    _columns = {
                'message' : fields.text('Message'),
                'sync_rule' : fields.many2one('sync_server.sync_rule', 'Sync Rule'),
                'message_rule' : fields.many2one('sync_server.message_rule', 'Mesage Rule'),
                'state' : fields.selection([('valid','Valid'),('invalid','Invalid'),], 'Status', required = True, readonly = True),
    }
    
    def validate(self, cr, uid, ids, context=None):
        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.sync_rule:
                self.pool.get('sync_server.sync_rule').write(cr, uid, wizard.sync_rule.id, {'status' : wizard.state }, context=context)
            if wizard.message_rule:
                self.pool.get('sync_server.message_rule').write(cr, uid, wizard.message_rule.id, {'status' : wizard.state }, context=context)
        return {'type': 'ir.actions.act_window_close'}

            
validation_message()      
    
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

