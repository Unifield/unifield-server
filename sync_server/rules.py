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
        return []
        obj = self.pool.get('ir.model')
        import ipdb
        ipdb.set_trace()
        ids = obj.search(cr, uid, sync_common.MODELS_TO_IGNORE)
        res = obj.read(cr, uid, ids, ['model', 'id'], context)
        return [(str(r['id']), r['model']) for r in res]

    _columns = {
        'name' : fields.many2one('ir.model.fields', 'Field Name', required = True),
        'value' : fields.reference("Value", selection = _get_fallback_value, size = 128, required = True),
        'sync_rule_id': fields.many2one('sync_server.sync_rule','Sync Rule', required = True),
    }

fallback_values()

class sync_rule_validation(osv.osv_memory):
    _name = "sync_server.sync_rule.validation"

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
        'model_ref': fields.many2one('ir.model', 'Model', required = True),
        'applies_to_type': fields.boolean('Applies to type', help='Applies to a group type instead of a specific group'),
        'group_id': fields.many2one('sync.server.entity_group','Group'),
        'type_id': fields.many2one('sync.server.group_type','Group Type'),
        'direction': fields.selection([('up', 'Up'),('down', 'Down'),
                    ('bidirectional', 'Bidirectional'),],
                    'Directionality',required = True,),
        'domain':fields.text('Domain', required = False),
        'sequence_number': fields.integer('Sequence', required = True),
        'included_fields_sel': fields.many2many('ir.model.fields', 'ir_model_fields_rules_rel', 'field', 'name', 'Select Fields'),
        'included_fields':fields.text('Fields to include', required = True, readonly = True),
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
                    'model' : rule.model_id,
                    'domain' : rule.domain,
                    'sequence_number' : rule.sequence_number,
                    'included_fields' : rule.included_fields,
            }
            rules_data.append(data)
        return rules_data

    def on_change_forced_values(self, cr, uid, ids, values, context=None):
        self.invalidate(cr, uid, ids, context=context)
        sel = {}
        errors = []
        for value in self.resolve_o2m_commands_to_record_dicts(cr, uid, 'forced_values_sel', values, context=context):
            # Get field information
            field = self.pool.get('ir.model.fields').read(cr, uid, \
                (value['name'] if isinstance(value['name'], int) else value['name'][0]), \
                ['name','model','ttype'])
            # Try to evaluate value and stringify it on failed
            try: value = eval(value['value'])
            except: value = '"""'+value['value']+'"""'
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
        res = {'value' : {'forced_values' : (str(sel) if sel else '')}}
        if errors:
            res['warning'] = {
                'title' : 'Error!',
                'message' : "\n".join(errors),
            }
        return res

    def on_change_included_fields(self, cr, uid, ids, fields, context=None):
        self.invalidate(cr, uid, ids, context=context)
        sel = []
        #errors = []
        #for field in self.resolve_o2m_commands_to_record_dicts(cr, uid, 'forced_values_sel', fields, context=context):
        for field in self.pool.get('ir.model.fields').read(cr, uid, fields[0][2], ['name','model','ttype']):
            name = str(field['name'])
            if field['ttype'] in ('many2one','one2many',): name += '/id'
            sel.append(name)
        res = {'value': {'included_fields' : (str(sel) if sel else '')}}
        #if errors:
        #    res['warning'] = {
        #        'title' : 'Error!',
        #        'message' : "\n".join(errors),
        #    }
        return res
            
    def invalidate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'active' : False, 'status' : 'invalid'}, context=context)
        return {}

    def on_change_fallback_values(self, cr, uid, ids, values, context=None):
        sel = {}
        errors = []
        for value in self.resolve_o2m_commands_to_record_dicts(cr, uid, 'fallback_values_sel', values, context=context):
            field = self.pool.get('ir.model.fields').read(cr, uid, value['name'], ['name','model','ttype'])
            try: value = eval(value['value'])
            except: value = eval('"""'+value['value']+'"""')
            name = str(field['name'])
            if field['ttype'] == 'many2one': name += '/id'
            else: sel[name] = value
        res = {'value' : {'fallback_values' : (str(sel) if sel else '')}}
        if errors:
            res['warning'] = {
                'title' : 'Error!',
                'message' : "\n".join(errors),
            }
        return res

    def validate(self, cr, uid, ids, context=None):
        error = False
        message = ''
        for rec in self.browse(cr, uid, ids, context=context):
            # Check domain syntax
            message += "* Domain syntax... "
            try:
                eval(rec.domain)
            except:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
            # Check field syntax
            message += "* Included fields syntax... "
            try:
                included_fields = eval(rec.included_fields)
                for field in included_fields:
                    base_field = field.split('/')[0]
                    if not isinstance(field, str): raise TypeError
                    if not len(self.pool.get('ir.model.fields').search(cr, uid, [('model','=',rec.model_id),('name','=',base_field)], context=context)): raise KeyError
            except TypeError:
                message += "failed (not a list of str)!\n"
                error = True
            except KeyError:
                message += "failed (check fields existence)!\n"
                error = True
            except:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
            finally:
                if error: message += "Example: ['name', 'order_line/product_id/id', 'order_line/product_id/name', 'order_line/product_uom_qty']\n"
            # Check force values syntax (can be empty)
            message += "* Forced values syntax... "
            try:
                eval(rec.forced_values or '1')
            except:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
            # Check fallback values syntax (can be empty)
            message += "* Fallback values syntax... "
            try:
                eval(rec.fallback_values or '1')
            except:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
            # Sequence is unique
            message += "* Sequence is unique... "
            if self.search(cr, uid, [('sequence_number','=',rec.sequence_number)], context=context, count = True) > 1:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
        self.write(cr, uid, ids, {'status': ('valid' if not error else 'invalid')})
        ## FIXME replace the following two-three lines.
        ##       (How to simply print a message box?)
        cr.commit()
        raise osv.except_osv('Unable to comply',
            'This rule cannot be validated for the following reason:\n\n'+message)
        return {'type': 'ir.actions.act_window_close',}

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
        'model_id': fields.function(_get_model_id, string = 'Model', fnct_inv=_get_model_name, type = 'char', size = 64, method = True, store = True, required = True),
        'model_ref': fields.many2one('ir.model', 'Model', required = True),
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

    def invalidate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'active' : False, 'status' : 'invalid'}, context=context)
        return {}

    def validate(self, cr, uid, ids, context=None):
        error = False
        message = ''
        for rec in self.browse(cr, uid, ids, context=context):
            # Check destination_name
            try:
                field_ids = self.pool.get('ir.model.fields').search(cr, uid, [('model','=',rec.model_id),('name','=',rec.destination_name)], context=context)
                if not field_ids: raise StandardError
            except:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
            # Check domain syntax
            message += "* Domain syntax... "
            try:
                domain = eval(rec.domain)
                self.pool.get(rec.model_id).search(cr, uid, domain, context=context)
            except:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
            # Remote Call Possible
            call_tree = rec.remote_call.split('.')
            call_class = '.'.join(call_tree[:-1])
            call_funct = call_tree[-1]
            message += "* Remote call exists... "
            try:
                ##TODO doesn't work because sync_so needed but it needs sync_client to be installed
                if not hasattr(self.pool.get(call_class), call_funct):
                    message += "failed!\n"
                    error = True
                else:
                    message += "pass.\n"
            except AttributeError:
                message += "failed (missing "+call_class+")!\n"
                error = True
            # Arguments of the call syntax and existence
            message += "* Checking arguments... "
            try:
                arguments = eval(rec.arguments)
                for arg in arguments:
                    base_arg = arg.split('/')[0]
                    if not isinstance(arg, str): raise TypeError
                    if not len(self.pool.get('ir.model.fields').search(cr, uid, [('model','=',rec.model_id),('name','=',base_arg)], context=context)): raise KeyError
            except TypeError:
                message += "failed (not a list of str)!\n"
                error = True
            except KeyError:
                message += "failed (check fields existence)!\n"
                error = True
            except:
                message += "failed (syntax error)!\n"
                error = True
            else:
                message += "pass.\n"
            finally:
                if error: message += "Example: ['name', 'order_line/product_id/id', 'order_line/product_id/name', 'order_line/product_uom_qty']\n"
            # Sequence is unique
            message += "* Sequence is unique... "
            if self.search(cr, uid, [('sequence_number','=',rec.sequence_number)], context=context, count = True) > 1:
                message += "failed!\n"
                error = True
            else:
                message += "pass.\n"
        self.write(cr, uid, ids, {'status': ('valid' if not error else 'invalid')})
        ## FIXME replace the following two-three lines.
        ##       (How to simply print a message box?)
        cr.commit()
        if error:
            raise osv.except_osv('Unable to comply',
                'This rule cannot be validated for the following reason:\n\n'+message)
        return {'type': 'ir.actions.act_window_close',}

message_rule()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

