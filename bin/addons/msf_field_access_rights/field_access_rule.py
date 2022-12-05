#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Max Mumford
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
from osv import orm
import psycopg2

class field_access_rule(osv.osv):
    """
    Lets user create access and sync propagation rules for fields of models.
    This class defines which model, instance level and groups to target
    """

    _name = "msf_field_access_rights.field_access_rule"
    _description = 'Field Access Rule'
    _inherit = 'common.import.ur'
    _auto = True

    def _get_all_model_ids(self, cr, uid, model_name):
        def recur_get_model(model, res):
            ids = self.pool.get('ir.model').search(cr, 1, [('model','=',model._name)])
            res.extend(ids)
            for parent in list(model._inherits.keys()):
                new_model = self.pool.get(parent)
                recur_get_model(new_model, res)
            return res
        model = self.pool.get(model_name)
        return recur_get_model(model, [])

    def _get_family_model_ids(self, cr, uid, ids, field, args, context=None):
        res = dict.fromkeys(ids, [])
        for field_access_rule in self.browse(cr, 1, ids, context=context):
            if field_access_rule.model_id:
                res[field_access_rule.id] = self._get_all_model_ids(cr, 1, field_access_rule.model_name)
        return res

    _columns = {
        'name': fields.char('Name', size=256, required=True),
        'model_id': fields.many2one('ir.model', 'Model', help='The type of data to which this rule applies', required=True, ondelete='cascade'),
        'model_name': fields.char('Model Name', size=256, help='The technical name for the model. This is used to make searching for Field Access Rules easier.'),
        'instance_level': fields.selection((('hq', 'HQ'), ('coordo', 'Coordo'), ('project', 'Project')), 'Instance Level', help='The Instance Level that this rule applies to'),
        'domain_id': fields.many2one('ir.filters', 'Filter', domain='[("model_id","=",model_name)]', ondelete="set null", help='Choose a pre-defined Filter to filter which records this rule applies to. Click the Create New Filter button, define some seach criteria, save your custom filter, then return to this form and type your new filters name here to use it for this rule. Note: Due to a technical constraint, all "like" or "ilike" operators will be automatically replaced with "=".'),
        'domain_text': fields.text('Advanced Filter', help='The Filter that chooses which records this rule applies to'),
        'group_ids': fields.many2many('res.groups', 'field_access_rule_groups_rel', 'field_access_rule_id', 'group_id', 'Groups', help='A list of groups that should be affected by this rule. If you leave this empty, this rule will apply to all groups.', order_by='name'),
        'field_access_rule_line_ids': fields.one2many('msf_field_access_rights.field_access_rule_line', 'field_access_rule', 'Field Access Rule Lines', help='A list of fields and their specific access and synchronization propagation rules that will be implemented by this rule. If you have left out any fields, users will have full write access, and all values will be synchronized when the record is created or editted.', required=True),
        'comment': fields.text('Comment', help='A description of what this rule does'),
        'active': fields.boolean('Active', help='If checked, this rule will be applied. This rule must be validated first.'),
        'status': fields.selection((('not_validated', 'Not Validated'), ('validated', 'Model Validated'), ('domain_validated', 'Filter Validated')), 'Status', help='The validation status of the rule. The Filter must be valid for this rule to be validated.', required=True),

        'family_model_ids': fields.function(_get_family_model_ids, string='Family Model IDs', type='many2many', relation='ir.model', method=True),
    }

    _defaults = {
        'active': False,
        'status': 'not_validated'
    }

    _sql_constraints = [
        ('name_unique', 'unique (name)', "The name you have chosen has already been used, and it must be unique. Please choose a different name."),
        ('domaintext_ilike1', 'check(domain_text <> $$"like"$$)', 'Due to technical constraints, you cannot use the operator "ilike" in a domain'),
        ('domaintext_ilike2', "check(domain_text <> $$'like'$$)", 'Due to technical constraints, you cannot use the operator "ilike" in a domain'),
        ('domaintext_like1', 'check(domain_text <> $$"ilike"$$)', 'Due to technical constraints, you cannot use the operator "like" in a domain'),
        ('domaintext_like2', "check(domain_text <> $$'ilike'$$)", 'Due to technical constraints, you cannot use the operator "like" in a domain'),
    ]

    def create(self, cr, user, vals, context=None):
        if context is None:
            context = {}
        # get model_name from model
        vals['model_name'] = self.pool.get('ir.model').browse(cr, user, vals['model_id'], context=context).model
        if not context.get('sync_update_execution') and vals.get('model_name') and vals.get('domain_text'):
            self.validate_domain_action(cr, user, vals['model_name'], vals['domain_text'])
        return super(field_access_rule, self).create(cr, user, vals, context=context)

    def write(self, cr, uid, ids, values, context=None):
        if not ids:
            return True

        if context is None:
            context = {}

        if not isinstance(ids, (list, tuple)):
            ids = [ids]

        # if domain_text has changed, check new domain syntax
        if values.get('domain_text') and not context.get('sync_update_execution'):
            for rule in self.read(cr, uid, ids, ['domain_text', 'model_name', 'active'], context=context):
                if rule['domain_text'] != values['domain_text']:
                    self.validate_domain_action(cr, uid, values.get('model_name', rule['model_name']), values['domain_text'])

        return super(field_access_rule, self).write(cr, uid, ids, values, context=context)

    def copy(self, cr, uid, id, default, context=None):
        raise orm.except_orm('Duplication Disabled', 'The duplication feature has been disabled for Field Access Rules')

    def onchange_model_id(self, cr, uid, ids, model, context=None):
        if model:
            model = self.pool.get('ir.model').browse(cr, uid, model, context=context)
            return {'value': {'model_name': model.model}}
        else:
            return {'value': {'model_name': ''}}

    def onchange_domain_id(self, cr, uid, ids, domain_id):
        """
        Returns the corresponding domain for the selected pre-defined domain filter after replacing like and ilike with '='
        """
        if domain_id:
            df = self.pool.get('ir.filters').browse(cr, uid, domain_id)
            df.domain = df.domain.replace("'ilike'", "'='").replace('"ilike"', '"="').replace("'like'","'='").replace('"like"','"="')
            return {'value': {'domain_text': df.domain, 'status': 'validated', 'active': False}}
        else:
            return {'value': {'domain_text': '', 'status': 'validated', 'active': False}}

    def onchange_domain_text(self, cr, uid, ids, domain_text, context=None):
        if domain_text:
            return {'value': {'status': 'validated', 'active': False}}
        else:
            return True

    def validate_button(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'status':'validated'}, context=context)

    def create_new_filter_button(self, cr, uid, ids, context=None):
        """
        Send the user to the list view of the selected model so they can save a new filter
        """
        assert len(ids) <= 1, "Cannot work on list of ids longer than one"

        record = self.browse(cr, uid, ids[0])

        # search in ir.ui.view for form and tree views for this model. If they exist, return action, else return None, otherwise openerp will error
        view_pool = self.pool.get('ir.ui.view')
        form = view_pool.search(cr, 1, [('type','=','form'),('model','=',record.model_name)])
        tree = view_pool.search(cr, 1, [('type','=','tree'),('model','=',record.model_name)])

        if form and tree:
            res = {
                'name': 'Create a New Filter For: %s' % record.model_id.name,
                'res_model': record.model_id.model,
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode':'tree,form',
                'target': 'new',
            }
            return res
        else:
            raise osv.except_osv('No List View', 'The chosen model has no List view so this feature cannot be used. You can still manually type a filter in the Advanced Filter field...')

    def generate_rules_button(self, cr, uid, ids, context=None):
        """
        Generate and return field_access_rule_lines for each field of the model and all inherited models, with Write Access checked
        """
        if ids:
            fields_pool = self.pool.get('ir.model.fields')

            for id in ids:
                record = self.browse(cr, uid, id)
                if record.field_access_rule_line_ids:
                    raise osv.except_osv('Remove Field Access Rule Lines First From %s' % id, 'Please remove all existing Field Access Rule Lines before generating new ones')

                fields_search = fields_pool.search(cr, uid, [('model_id', 'in', [f.id for f in record.family_model_ids])], context=context)
                fields = fields_pool.browse(cr, uid, fields_search, context=context)

                res = [(0, 0, {'field': i.id, 'field_name': i.name}) for i in fields]
                self.write(cr, uid, id, {'field_access_rule_line_ids': res})
        return True

    def manage_rule_lines_button(self, cr, uid, ids, context=None):
        """
        Send the user to a list view of field_access_rule_line's for this field_access_rule.
        """
        assert len(ids) <= 1, "Cannot work on list of ids != 1"

        this = self.browse(cr, uid, ids, context=context)[0]
        x, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_field_access_rights', 'field_access_rule_full_tree_view')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Field Access Rule Lines for rule: %s' % this.name,
            'view_type': 'form',
            'view_mode':'tree,form',
            'view_id': [view_id],
            'target': 'new',
            'res_model': 'msf_field_access_rights.field_access_rule_line',
            'context': {
                'search_default_field_access_rule': ids[0],
            },
        }

    def validate_domain_action(self, cr, uid, model_name, domain_text, context=None):
        exception_title = 'Invalid Filter'
        exception_body = "\nThe filter you have typed is invalid. You can create a filter using the Create New Filter button"
        if domain_text:
            pool = self.pool.get(model_name)
            if not pool:
                raise osv.except_osv('Invalid Model', 'The model you have chosen is invalid. Please use the auto-complete to choose a valid one.')

            try:
                domain = eval(domain_text)
                if not isinstance(domain, list):
                    raise osv.except_osv(exception_title, exception_body)
            except SyntaxError:
                raise osv.except_osv(exception_title, exception_body)

            try:
                pool.search(cr, uid, domain, context=context)
            except (ValueError, psycopg2.ProgrammingError):
                raise osv.except_osv(exception_title, exception_body)

        return True

    def validate_domain_button(self, cr, uid, ids, context=None):
        """
        Validates the domain_text filter, and if successful, changes the Status field to validated
        """
        assert len(ids) <= 1, "Cannot work on list of ids != 1"


        record = self.browse(cr, uid, ids[0], context=context)

        self.validate_domain_action(cr, uid, record.model_name, record.domain_text, context)
        self.write(cr, uid, ids, {'status': 'domain_validated'}, context=context)
        return True

field_access_rule()

class res_groups(osv.osv):
    _inherit = 'res.groups'
    _columns = {
        'far_ids': fields.many2many('msf_field_access_rights.field_access_rule', 'field_access_rule_groups_rel', 'group_id', 'field_access_rule_id', 'Fields Access Rules', readonly=1),
    }
res_groups()
