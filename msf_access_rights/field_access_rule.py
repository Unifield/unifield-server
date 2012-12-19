#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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


class field_access_rule(osv.osv):
    """
    Lets user create access and sync propagation rules for fields of models.
    This class defines which model, instance level and groups to target
    """

    _name = "msf_access_rights.field_access_rule"

    _columns = {
        'name': fields.char('Name', size=256, required=True),
        'model_id': fields.many2one('ir.model', 'Model', help='The type of data to which this rule applies', required=True),
        'model_name': fields.char('Model Name', size=256, help='The technical name for the model. This is used to make searching for Field Access Rules easier.'),
        'instance_level': fields.selection((('hq', 'HQ'), ('coordo', 'Coordo'), ('project', 'Project')), 'Instance Level', help='The Instance Level that this rule applies to'),
        'domain_id': fields.many2one('ir.filters', 'Filter', help='Choose a pre-defined Filter to filter which records this rule applies to. Click the Create New Filter button, define some seach criteria, save your custom filter, then return to this form and type your new filters name here to use it for this rule.'),
        'domain_text': fields.text('Advanced Filter', help='The Filter that chooses which records this rule applies to'),
        'group_ids': fields.many2many('res.groups', 'field_access_rule_groups_rel', 'field_access_rule_id', 'group_id', 'Groups', help='A list of groups that should be affected by this rule. If you leave this empty, this rule will apply to all groups.'),
        'field_access_rule_line_ids': fields.one2many('msf_access_rights.field_access_rule_line', 'field_access_rule', 'Field Access Rule Lines', help='A list of fields and their specific access and synchronization propagation rules that will be implemented by this rule. If you have left out any fields, users will have full write access, and all values will be synchronized when the record is created or editted.', required=True),
        'comment': fields.text('Comment', help='A description of what this rule does'),
        'active': fields.boolean('Active', help='If checked, this rule will be applied. This rule must be validated first.'),
        'status': fields.selection((('not_validated', 'Not Validated'), ('validated', 'Model Validated'), ('domain_validated', 'Filter Validated')), 'Status', help='The validation status of the rule. The Filter must be valid for this rule to be validated.', required=True),
    }

    _defaults = {
        'active': False,
        'status': 'not_validated'
    }

    _sql_constraints = [
        ('name_unique', 'unique (name)', """The name you have chosen has already been used, and it must be unique. Please choose a different name."""),
    ]

    def write(self, cr, uid, ids, values, context=None):

    	# get model_name from model
    	if 'model_id' in values:
            values['model_name'] = ''
            if values['model_id']:
                model_name = self.pool.get('ir.model').browse(cr, uid, values['model_id'], context=context).model


        # if domain_text has changed, change status to not_validated
        if values.get('domain_text'):
            if len(ids) == 1:
                record = self.browse(cr, uid, ids[0], context=context)
                domain_text = getattr(record, 'domain_text', '')

                if domain_text != values['domain_text']:
                    values['status'] = 'validated'
            else:
                values['status'] = 'validated'


        # deactivate if not validated
        if 'status' in values and values['status'] == 'validated':
            values['active'] = False

        return super(field_access_rule, self).write(cr, uid, ids, values, context=context)

    def onchange_model_id(self, cr, uid, ids, model, context=None):
        if model:
            model = self.pool.get('ir.model').browse(cr, uid, model, context=context)
            return {'value': {'model_name': model.model}}
        else:
            return {'value': {'model_name': ''}}

    def onchange_domain_id(self, cr, uid, ids, domain_id):
        """
        Returns the corresponding domain for the selected pre-defined domain filter
        """
        if domain_id:
            df = self.pool.get('ir.filters').browse(cr, uid, domain_id)
            return {'value': {'domain_text': df.domain}}
        else:
            return {'value': {'domain_text': ''}}

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
        assert len(ids) <= 1, "Cannot work on list of ids != 1"

        record = self.browse(cr, uid, ids[0])

        res = {
            'name': 'Create a New Filter For: %s' % record.model_id.name,
            'res_model': record.model_id.model,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
			'view_mode':'tree,form',
            'target': 'new', 
        }

        return res

    def generate_rules_button(self, cr, uid, ids, context=None):
        """
        Generate and return field_access_rule_line's for each field of the model and all inherited models, with Write Access checked
        """
        assert len(ids) <= 1, "Cannot work on list of ids != 1"

        record = self.browse(cr, uid, ids[0])
        if record.field_access_rule_line_ids:
            raise osv.except_osv('Remove Field Access Rune Lines First', 'Please remove all existing field access rule lines before generating new ones')

        fields_pool = self.pool.get('ir.model.fields')
        fields_search = fields_pool.search(cr, uid, [('model_id', '=', record.model_id.id)], context=context)
        fields = fields_pool.browse(cr, uid, fields_search, context=context)

        res = [(0, 0, {'field': i.id, 'field_name': i.name}) for i in fields]
        self.write(cr, uid, ids, {'field_access_rule_line_ids': res})

        return True

    def manage_rule_lines_button(self, cr, uid, ids, context=None):
        """
        Send the user to a list view of field_access_rule_line's for this field_access_rule.
        """
        assert len(ids) <= 1, "Cannot work on list of ids != 1"

        this = self.browse(cr, uid, ids, context=context)[0]
        x, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_access_rights', 'field_access_rule_full_tree_view')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Field Access Rule Lines for rule: %s' % this.name,
            'view_type': 'form',
			'view_mode':'tree,form',
			'view_id': [view_id],
            'target': 'new',
            'res_model': 'msf_access_rights.field_access_rule_line',
            'context': {
            	'search_default_field_access_rule': ids[0],
            },
        }

    def validate_domain_button(self, cr, uid, ids, context=None):
        """
        Validates the domain_text filter, and if successful, changes the Status field to validated
        """
        assert len(ids) <= 1, "Cannot work on list of ids != 1"

        exception_title = 'Invalid Filter'
        exception_body = 'The filter you have typed is invalid. You can create a filter using the Create New Filter button'

        record = self.browse(cr, uid, ids[0], context=context)

        if record.domain_text:
            pool = self.pool.get(record.model_name)
            if not pool:
                raise osv.except_osv('Invalid Model', 'The model you have chosen is invalid. Please use the auto-complete to choose a valid one.')

            try:
                domain = eval(record.domain_text)
                if not isinstance(domain, list):
                    raise osv.except_osv(exception_title, exception_body)
            except SyntaxError:
                raise osv.except_osv(exception_title, exception_body)

            try:
                pool.search(cr, uid, domain, context=context)
            except ValueError:
                raise osv.except_osv(exception_title, exception_body)

            self.write(cr, uid, ids, {'status': 'domain_validated'}, context=context)
            return True
        else:
            self.write(cr, uid, ids, {'status': 'domain_validated'}, context=context)
            return True

field_access_rule()
