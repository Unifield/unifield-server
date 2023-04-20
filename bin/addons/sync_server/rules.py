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

from psycopg2 import IntegrityError
from datetime import datetime

import logging
from sync_common import sync_log, WHITE_LIST_MODEL

_field2type = {
    'text'      : 'str',
    'char'      : 'str',
    'selection' : 'str',
    'integer'   : 'int',
    'boolean'   : 'bool',
    'float'     : 'float',
    'datetime'  : 'str',
}

class ir_model_field(osv.osv):
    _inherit = 'ir.model.fields'

    def _modify_search_args(self, args):
        for index, arg in enumerate(args):
            if isinstance(arg, (list, tuple)) and arg[0] == 'model_id' and arg[1] == 'in' and isinstance(arg[2], (list, tuple)) and isinstance(arg[2][0], tuple) and len(arg[2][0]) == 3 and arg[2][0][0] ==6:
                args[index] = ('model_id', 'in', arg[2][0][2])
        return args

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        args = self._modify_search_args(args)
        return super(ir_model_field, self).name_search(cr, uid, name, args=args, operator=operator, context=context, limit=limit)

    def search(self, cr, uid, args, offset=0, limit=80, order='', context=None, count=False):
        args = self._modify_search_args(args)
        return super(ir_model_field, self).search(cr, uid, args, offset, limit,
                                                  order, context, count)

ir_model_field()

def check_domain(self, cr, uid, rec, context=None):
    error = False
    message = "* Domain syntax... "
    try:
        domain = eval(rec.domain)
        domain.append(('id', 'in', [1, 2, 3]))
        self.pool.get(rec.model_id).search_ext(cr, uid, domain, context=None)
    except:
        message += "failed!\n"
        error = True
    else:
        message += "pass.\n"
    finally:
        if error: message += "Example: ['|', ('name', 'like', 'external_'), ('supplier', '=', True)]\n"
    return (message, error)

class sync_rule(osv.osv):
    """ Synchronization Rule """

    _name = "sync_server.sync_rule"
    _description = "Synchronization Rule"
    _trace = True

    _logger = logging.getLogger('sync.server')

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

    def _get_all_model(self, cr, uid, ids, field, args, context=None):
        res = dict.fromkeys(ids)
        for rule_data in self.read(cr, uid, ids, ['model_id'], context=context):
            if rule_data.get('model_id'):
                res[rule_data['id']] = self.pool.get(rule_data.get('model_id')).get_model_ids(cr, uid, context=context)
        return res


    _columns = {
        'name': fields.char('Rule Name', size=64, required = True),
        #'model_id': fields.char('Model', size=128, required = True),
        'model_id': fields.function(_get_model_id, string = 'Model', fnct_inv=_get_model_name, type = 'char', size = 64, method = True, store = True),
        'model_ref': fields.many2one('ir.model', 'Model'),
        'applies_to_type': fields.boolean('Applies to type', help='Applies to a group type instead of a specific group'),
        'group_id': fields.many2one('sync.server.entity_group','Group', select=True),
        'type_id': fields.many2one('sync.server.group_type','Group Type', select=True),
        'type_name': fields.related('type_id', 'name', type='char', string='Group Name'),
        'direction': fields.selection([
            ('up', 'Up'),
            ('down', 'Down'),
            ('bidirectional', 'Bidirectional'),
            ('bi-private', 'Bidirectional-Private'),
            ('mission-private', 'Mission-Private'),
        ], 'Directionality', required = True,),
        'domain':fields.text('Domain', required = False),
        'owner_field':fields.char('Owner Field', size = 64, required = False),
        'sequence_number': fields.integer('Sequence', required = True, group_operator="count"),
        'included_fields_sel': fields.many2many('ir.model.fields', 'ir_model_fields_rules_rel', 'field', 'name', 'Select Fields'),
        'included_fields':fields.text('Fields to include', required = False),
        'forced_values_sel': fields.one2many('sync_server.sync_rule.forced_values', 'sync_rule_id', 'Select Forced Values'),
        'forced_values':fields.text('Values to force', required = False),
        'fallback_values_sel': fields.one2many('sync_server.sync_rule.fallback_values', 'sync_rule_id', 'Select Fallback Values'),
        'fallback_values':fields.text('Fallback values', required = False),
        'can_delete': fields.boolean('Can delete record?', help='Propagate the delete of old unused records'),
        'status': fields.selection([('valid','Valid'),('invalid','Invalid'),], 'Status', required = True),
        'active': fields.boolean('Active'),
        'model_ids' : fields.function(_get_all_model, string="Parents Model", type="many2many", relation="ir.model", method=True),
        'handle_priority': fields.boolean('Handle Priority'),
        'master_data': fields.boolean('Master Data'),
    }

    _defaults = {
        'master_data': True,
        'domain': '[]',
        'active': False,
        'status': 'valid',
        'handle_priority' : False,
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
        if not entity.group_ids:
            raise osv.except_osv(_("Warning"), "Your instace does not belong "
                                 "to any group. Instance must be member of at least one "
                                 "group to be able to synchronize.")
        cr.execute("""SELECT g.id, array_agg(r.id)
                      FROM sync_server_entity_group g
                           JOIN sync_server_group_type t ON (g.type_id=t.id or t.name = 'USB')
                           JOIN sync_server_sync_rule r
                                ON (((r.group_id = g.id AND NOT r.applies_to_type)
                                     OR (r.type_id = t.id AND r.applies_to_type))
                                    AND r.active)
                      WHERE g.id IN %s
                      GROUP BY g.id""", (tuple(x.id for x in entity.group_ids),))
        return dict(cr.fetchall())

    def _get_groups_per_rule(self, cr, uid, entity, context=None):
        cr.execute("""SELECT r.id, array_agg(g.id)
                      FROM sync_server_entity_group g
                           JOIN sync_server_group_type t ON (g.type_id=t.id)
                           JOIN sync_server_sync_rule r
                                ON (((r.group_id = g.id AND NOT r.applies_to_type)
                                     OR (r.type_id = t.id AND r.applies_to_type))
                                    AND r.active)
                      WHERE g.id IN %s
                      GROUP BY r.id""", (tuple(x.id for x in entity.group_ids),))
        return dict(cr.fetchall())

    def _compute_rules_to_send(self, cr, uid, entity, context=None):
        rules_ids = self._get_rules_per_group(cr, uid, entity, context)
        ancestor_group = self._get_ancestor_groups(cr, uid, entity, context)
        children_group = self._get_children_groups(cr, uid, entity, context)

        rules_to_send = set()
        for group_id, rule_ids in rules_ids.items():
            for rule in self.browse(cr, uid, rule_ids):
                if rule.direction == 'up' and entity.parent_id: #got a parent in the same group
                    if group_id in ancestor_group:
                        rules_to_send.add(rule.id)
                elif rule.direction == 'down' and entity.children_ids: #got children in the same group
                    if group_id in children_group:
                        rules_to_send.add(rule.id)
                else:
                    rules_to_send.add(rule.id)

        return list(rules_to_send)

    def _compute_rules_to_receive(self, cr, uid, entity, context=None):
        rules_ids = self._get_rules_per_group(cr, uid, entity, context)
        rules_to_send = set()
        for group_id, rule_ids in rules_ids.items():
            rules_to_send.update(rule_ids)

        return list(rules_to_send)

    _rules_serialization_mapping = {
        'id' : 'server_id',
        'name' : 'name',
        'owner_field' : 'owner_field',
        'model_id' : 'model',
        'domain' : 'domain',
        'sequence_number' : 'sequence_number',
        'included_fields' : 'included_fields',
        'can_delete' : 'can_delete',
        'type_name' : 'type',
        'handle_priority' : 'handle_priority',
        'direction': 'direction',
    }

    def _serialize_rule(self, cr, uid, ids, context=None):
        if not ids:
            return []
        rules_data = []
        if ids:
            rules_serialization_mapping = dict(
                sum((c._rules_serialization_mapping.items()
                     for c in reversed(self.__class__.mro())
                     if hasattr(c, '_rules_serialization_mapping')), [])
            )
            for rule in self.browse(cr, uid, ids, context=context):
                rules_data.append(dict(
                    (data, rule[column]) for column, data
                    in rules_serialization_mapping.items()
                ))
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
                except Exception, e:
                    sync_log(self, e, 'error')
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
        model = ''
        model_ids = []
        if model_ref:
            model = self.pool.get('ir.model').browse(cr, uid, model_ref, context=context).model
            model_ids = self.pool.get(model).get_model_ids(cr, uid, context=context)

        return { 'value' : {'active' : False, 'status' : 'invalid', 'model_id' : model, 'model_ids' : model_ids} }

    def create(self, cr, uid, values, context=None):
        if values.get('model_id'):
            model_ids = self.pool.get('ir.model').search(cr, uid, [('model','=',values.get('model_id'))], context=context)
            if model_ids:
                values['model_ref'] = model_ids[0]

        if 'included_fields_sel' in values and values.get('included_fields_sel')[0][2]:
            values['included_fields'] = self._compute_included_field(cr, uid,
                                                                     [], values['included_fields_sel'][0][2], context)
        new_id = super(sync_rule, self).create(cr, uid, values, context=context)
        check = self.validate_rules(cr, uid, [new_id], context=context)
        if check['state'] != 'valid':
            raise osv.except_osv(_("Warning"), check['message'])

        return new_id

    def write(self, cr, uid, ids, values, context=None):
        if not ids:
            return True
        if 'included_fields_sel' in values and values.get('included_fields_sel')[0][2]:
            values['included_fields'] = self._compute_included_field(cr, uid, ids, values['included_fields_sel'][0][2], context)

        if not isinstance(ids, (list, tuple)):
            ids = [ids]

        rule_to_check = []
        for rule_data in self.read(cr, uid, ids, ['model_id', 'domain', 'sequence_number','included_fields','status'], context=context):
            dirty = False
            for k in rule_data.keys():
                if k in values and values[k] != rule_data[k]:
                    dirty = True

            if dirty:
                rule_to_check.append(rule_data['id'])
                #values.update({'active' : False, 'status' : 'invalid'})

        if 'applies_to_type' in values:
            if values['applies_to_type']:
                values['group_id'] = False
            else:
                values['type_id'] = False

        res = super(sync_rule, self).write(cr, uid, ids, values, context=context)
        if rule_to_check:
            check = self.validate_rules(cr, uid, rule_to_check, context=context)
            if check['state'] != 'valid':
                raise osv.except_osv(_("Warning"), check['message'])
        return res

    def unlink(self, cr, uid, ids, context=None):
        cr.execute("""SAVEPOINT unlink_rule""")
        try:
            return super(sync_rule, self).unlink(cr, uid, ids, context=context)
        except IntegrityError:
            cr.execute("""ROLLBACK TO SAVEPOINT unlink_rule""")
            self._logger.warn("Cannot delete rule(s) %s, disable them" % ids)
            return self.write(cr, uid, ids, {'active':False}, context=context)

    ## Checkers & Validator ##################################################

    def check_fields(self, cr, uid, rec, title="", context=None):
        message = title
        error = False
        try:
            included_fields = eval(rec.included_fields)
            for field in included_fields:
                base_field = field.split('/')[0]
                if not isinstance(field, str): raise TypeError
                model_ids = self.pool.get(rec.model_id).get_model_ids(cr, uid, context=context)
                if not self.pool.get('ir.model.fields').search(cr, uid,
                                                               [('model_id','in', model_ids),('name','=',base_field)],
                                                               limit=1, order='NO_ORDER', context=context): raise KeyError
        except TypeError:
            message += "failed (Fields list should be a list of string)!\n"
            error = True
        except KeyError:
            message += "failed (Field %s doesn't exist for the selected model/object)!\n" % base_field
            error = True
        except:
            message += "failed! (Syntax Error : not a python expression) \n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: ['name', 'order_line/product_id/id', 'order_line/product_id/name', 'order_line/product_uom_qty']\n"

        return (message, error)

    def check_forced_values(self, cr, uid, rec, context=None):
        error = False
        message = "* Forced values syntax... "
        try:
            forced_value = eval(rec.forced_values or '{}')
            if not isinstance(forced_value, dict): raise TypeError
        except TypeError:
            message += "failed (Forced values should be a dictionnary)!\n"
            error = True
        except:
            message += "failed! (Syntax error) \n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: {'field_name' : 'str_value', 'field_name' : 10, 'field_name' : True}\n"

        return (message, error)



    def check_fallback_values(self, cr, uid, rec, context=None):
        error = False
        message = "* Fallback values syntax... "
        try:
            fallback_value = eval(rec.fallback_values or '{}')
            if not isinstance(fallback_value, dict): raise TypeError
        except TypeError:
            message += "failed (Fallback values should be a dictionnary)!\n"
            error = True
        except:
            message += "failed!\n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: {'field_name/id' : 'sd.xml_id'}\n"
            # Sequence is unique
        return (message, error)

    def check_owner_field(self, cr, uid, rec, context=None):
        if rec.direction not in ('bi-private', 'mission-private'):
            return ('', False)
        error = False
        message = "* Owner field existence... "
        try:
            fields = []
            ir_model_fields = self.pool.get('ir.model.fields')
            model_ids = self.pool.get(rec.model_id).get_model_ids(cr, uid, context=context)
            fields_ids = ir_model_fields.search(cr, uid, [('model_id','in', model_ids)], context=context)
            fields = ir_model_fields.browse(cr, uid, fields_ids, context=context)
            fields = [x.name for x in fields]
            included_fields = eval(rec.included_fields or '[]')
            if not rec.owner_field in fields: raise KeyError
            if not (rec.owner_field in included_fields or rec.owner_field+'/id' in included_fields): raise KeyError
        except KeyError:
            message += "failed!\n"
            message += "The owner field must be present in the included fields!\n"
            error = True
        except:
            message += "failed!\n"
            message += "Please choose one of these: %s\n" % (", ".join(fields),)
            error = True
        else:
            message += "pass.\n"
        return (message, error)

    check_domain = check_domain

    def validate_rules(self, cr, uid, ids, context=None):
        error = False
        message = []
        for rec in self.browse(cr, uid, ids, context=context):
            mess, err = self.check_domain(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            # Check field syntax
            mess, err = self.check_fields(cr, uid, rec, title="* Included fields syntax... ", context=context)
            error = err or error
            message.append(mess)
            # Check for valid status
            message.append(_("* Valid status... "))
            if rec.status == 'invalid':
                message.append('failed! Rule has status=invalid\n')
                error=True
            else:
                message.append('pass.\n')
            # Check force values syntax (can be empty)
            mess, err = self.check_forced_values(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            # Check fallback values syntax (can be empty)
            mess, err = self.check_fallback_values(cr, uid, rec, context)
            error = err or error
            message.append(mess)
            # Check Owner Field
            mess, err = self.check_owner_field(cr, uid, rec, context)
            error = err or error
            message.append(mess)

            message.append("* Sequence is unique... ")
            if self.search(cr, uid,
                           [('sequence_number','=',rec.sequence_number)],
                           order='NO_ORDER', context=context, count=True) > 1:
                message.append("failed!\n")
                error = True
            else:
                message.append("pass.\n")

        message_header = 'This rule is valid:\n\n' if not error else 'This rule cannot be validated for the following reason:\n\n'
        message_body = ''.join(message)
        return {
            'state': 'valid' if not error else 'invalid',
            'message' : message_header + message_body,
            'sync_rule' : rec.id
        }

    def validate(self, cr, uid, ids, context=None):
        message_data = self.validate_rules(cr, uid, ids, context=context)
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
    _trace = True

    _logger = logging.getLogger('sync.server')

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
        'group_id': fields.many2one('sync.server.entity_group','Group', select=True),
        'type_id': fields.many2one('sync.server.group_type','Group Type', select=True),
        'type_name': fields.related('type_id', 'name', type='char', string='Group Name'),
        'domain': fields.text('Domain', required = False),
        'filter_method' : fields.char('Filter Method', size=64, help='The method to use to find target records instead of a domain.'),
        'sequence_number': fields.integer('Sequence', required = True, group_operator="count"),
        'remote_call': fields.text('Method to call', required = True),
        'arguments': fields.text('Arguments of the method', required = True),
        'destination_name': fields.char('Field to extract destination', size=256, required = True),
        'status': fields.selection([('valid','Valid'),('invalid','Invalid'),], 'Status', required = True ),
        'active': fields.boolean('Active'),
        'wait_while': fields.text('Wait while', required=False, help='Wait during a specified domain to send the message'),
    }

    _defaults = {
        'domain': '[]',
        'active': False,
        'status': 'valid',
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
            domain = ['|', '|',
                      '&', ('group_id', '=', group.id), ('applies_to_type', '=', False),
                      '&', ('type_id', '=', group.type_id.id), ('applies_to_type', '=', True),
                      ('type_name', '=', 'USB')]
            ids = self.search(cr, uid, domain, context=context)
            if ids:
                rules_ids.extend(ids)
        return list(set(rules_ids))

    _rules_serialization_mapping = {
        'name' : 'name',
        'id': 'server_id',
        'model_id': 'model',
        'domain': 'domain',
        'filter_method': 'filter_method',
        'sequence_number': 'sequence_number',
        'remote_call': 'remote_call',
        'arguments': 'arguments',
        'destination_name': 'destination_name',
        'active': 'active',
        'type_name' : 'type',
        'wait_while': 'wait_while',
    }

    def _serialize_rule(self, cr, uid, ids, context=None):
        if not ids:
            return []
        rules_data = []
        if ids:
            rules_serialization_mapping = dict(
                sum((c._rules_serialization_mapping.items()
                     for c in reversed(self.__class__.mro())
                     if hasattr(c, '_rules_serialization_mapping')), [])
            )
            for rule in self.browse(cr, uid, ids, context=context):
                rules_data.append(dict(
                    (data, rule[column]) for column, data
                    in rules_serialization_mapping.items()
                ))
        return rules_data

    def invalidate(self, cr, uid, ids, model_ref, context=None):
        model = ''
        if model_ref:
            model = self.pool.get('ir.model').browse(cr, uid, model_ref, context=context).model

        return { 'value' : {'active' : False, 'status' : 'invalid', 'model_id' : model} }

    def create(self, cr, uid, values, context=None):
        new_id = super(message_rule, self).create(cr, uid, values, context=context)
        check = self.validate_rules(cr, uid, [new_id], context=context)
        if check['state'] != 'valid':
            raise osv.except_osv(_("Warning"), check['message'])
        return new_id

    def write(self, cr, uid, ids, values, context=None):
        if not ids:
            return True
        if 'included_fields_sel' in values:
            values['included_fields'] = self._compute_included_field(cr, uid, ids, values['included_fields_sel'][0][2], context)

        if not isinstance(ids, (list, tuple)):
            ids = [ids]

        rule_to_check = []
        for rule_data in self.read(cr, uid, ids, ['model_id', 'domain', 'sequence_number','remote_call', 'arguments', 'destination_name', 'status'], context=context):
            dirty = False
            for k in rule_data.keys():
                if k in values and values[k] != rule_data[k]:
                    dirty = True
            if dirty:
                rule_to_check.append(rule_data['id'])
                #values.update({'active' : False, 'status' : 'invalid'})
        res = super(message_rule, self).write(cr, uid, ids, values, context=context)
        if rule_to_check:
            check = self.validate_rules(cr, uid, rule_to_check, context=context)
            if check['state'] != 'valid':
                raise osv.except_osv(_("Warning"), check['message'])
        return res

    ## Checkers & Validator ##################################################

    check_domain = check_domain

    def check_arguments(self, cr, uid, rec, title="", context=None):
        message = title
        error = False
        try:
            field_error = False
            arguments = eval(rec.arguments)
            for field in arguments:
                base_field = field.split('/')[0]
                if not isinstance(field, str): raise TypeError
                model_ids = self.pool.get(rec.model_id).get_model_ids(cr, uid, context=context)
                if not self.pool.get('ir.model.fields').search(cr, uid,
                                                               [('model_id','in', model_ids),('name','=',base_field)],
                                                               limit=1, order='NO_ORDER', context=context):
                    field_error = field
                    raise KeyError
        except TypeError:
            message += "failed (Fields list should be a list of string)!\n"
            error = True
        except KeyError:
            message += "failed (Field %s doesn't exist for the selected model/object)!\n" % field_error
            error = True
        except:
            message += "failed! (Syntax Error : not a python expression) \n"
            error = True
        else:
            message += "pass.\n"
        finally:
            if error: message += "Example: ['name', 'order_line/product_id/id', 'order_line/product_id/name', 'order_line/product_uom_qty']\n"

        return (message, error)


    def validate_rules(self, cr, uid, ids, context=None):
        error = False
        message = []
        for rec in self.browse(cr, uid, ids, context=context):
            # Check destination_name
            message.append(_("* Destination Name... "))
            try:
                field_ids = self.pool.get('ir.model.fields').search(cr, uid,
                                                                    [('model','=',rec.model_id),('name','=',rec.destination_name)],
                                                                    limit=1, order='NO_ORDER', context=context)
                if not field_ids: raise StandardError
            except Exception, e:
                sync_log(self, e, 'error')
                message.append("failed! Field %s doesn't exist\n" % rec.destination_name)
                error = True
            else:
                message.append("pass.\n")

            if not rec.filter_method:
                mess, err = self.check_domain(cr, uid, rec, context)
                error = err or error
                message.append(mess)
            elif not hasattr(self.pool.get(rec.model_id), rec.filter_method):
                message.append('Filter Method %s does not exist on object %s\n' % (rec.filter_method, rec.model_id))
                error = True

            message.append(_("* Valid status... "))
            if rec.status == 'invalid':
                message.append('failed! Rule has status=invalid\n')
                error = True
            else:
                message.append('pass.\n')

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

            mess, err = self.check_arguments(cr, uid, rec, title="* Checking arguments..." , context=context)
            error = err or error
            message.append(mess)

            # Sequence is unique
            message.append("* Sequence is unique... ")
            if self.search(cr, uid,
                           [('sequence_number','=',rec.sequence_number)],
                           order='NO_ORDER', context=context, count=True) > 1:
                message.append("failed!\n")
                error = True
            else:
                message.append("pass.\n")

        message_header = 'This rule is valid:\n\n' if not error else 'This rule cannot be validated for the following reason:\n\n'
        message_body = ' '.join(message)
        return {
            'state': 'valid' if not error else 'invalid',
            'message' : message_header + message_body,
            'message_rule' : rec.id
        }

    def validate(self, cr, uid, ids, context=None):
        message_data = self.validate_rules(cr, uid, ids, context=context)
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
        model = self.pool.get('ir.model')
        ids = model.search(cr, uid, [('model', 'not in', WHITE_LIST_MODEL)])
        res = model.read(cr, uid, ids, ['model'], context)
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
