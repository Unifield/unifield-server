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
        'model': fields.many2one('ir.model', 'Model', help='The model for which this rule applies', required=True),
        'model_name': fields.char('Model Name', size=256, help='The technical name for the model. This is used to make searching for Field Access Rules easier.'),
        'instance_level': fields.selection((('hq','HQ'), ('coordo','Coordo'), ('project','Project')), 'Instance Level', help='The Instance Level that this rule applies to', required=True),
        'domain_filter': fields.many2one('ir.filters', 'Domain Filter', help='Choose a pre-defined Domain Filter to filter which records this rule applies to. Click the Create New Filter button, define some seach criteria, save your custom filter, then return to this form and type your new filters name here to use it for this rule.'),
        'domain': fields.text('Domain', help='The Domain Filter that chooses which records this rule applies to'),
        'groups': fields.many2many('res.groups', 'field_access_rule_groups_rel', 'field_access_rule_id', 'group_id', 'Groups', help='A list of groups that should be affected by this rule. If you leave this empty, this rule will apply to all groups.'),
        'field_access_rule_line_ids': fields.one2many('msf_access_rights.field_access_rule_line', 'field_access_rule', 'Field Access Rule Lines', help='A list of fields and their specific access and synchronization propagation rules that will be implemented by this rule. If you have left out any fields, users will have full write access, and all values will be synchronized when the record is created or editted.', required=True),
        'comment': fields.text('Comment', help='A description of what this rule does'),
        'active': fields.boolean('Active', help='If checked, this rule will be applied'),
        'status': fields.selection((('not_validated','Not Validated'), ('validated', 'Validated')), 'Status', help='The validation status of the rule. The Domain Filter must be valid for this rule to be validated.', required=True),
	}

	_defaults = {
		'active' : False,
	}

	def _add_model_name_to_values(self, cr, uid, values, context={}):
		if 'model' in values and ('model_name' not in values or not values['model_name']):
			values['model_name'] = self._get_model_name_from_model(cr, uid, values['model'])
		return values

	def _get_model_name_from_model(self, cr, uid, model, context={}):
		"""
		Returns the user friendly model name from the selected model
		"""
		if model:
			m = self.pool.get('ir.model').browse(cr, uid, model, context=context)
			return m.model
		else:
			return ''

	def create(self, cr, uid, values, context={}):
		values = self._add_model_name_to_values(cr, uid, values, context)
		return super(field_access_rule, self).create(cr, uid, values, context=context)

	def write(self, cr, uid, ids, values, context={}):
		values = self._add_model_name_to_values(cr, uid, values, context)
		return super(field_access_rule, self).write(cr, uid, ids, values, context=context)

	def onchange_model(self, cr, uid, ids, model, context={}):
		model_name = self._get_model_name_from_model(cr, uid, model, context)
		return {'value': {'model_name' : model_name}}
				
	def onchange_domain_filter(self, cr, uid, ids, domain_filter):
		"""
		Returns the corresponding domain for the selected pre-defined domain filter
		"""
		if domain_filter:
			df = self.pool.get('ir.filters').browse(cr, uid, domain_filter)
			if ids:
				res = {}
				for i in ids:
					res[i] = {'domain' : df.domain}
				return {'value': res}
			else:
				return {'value': {'domain' : df.domain}}
		else:
			return {}

	def create_new_filter_button(self, cr, uid, ids, context={}):
		"""
		Send the user to the list view of the selected model so they can save a new filter
		"""
		print '======================== create new filter button'
		print ids

		field_access_rule = self.browse(cr, uid, ids[0])

		res = {
				'name' : 'Create a New Filter For: %s' % field_access_rule.model.name,
				'view_type': 'tree',
				'view_mode': 'tree',
				'res_model': field_access_rule.model.model,
				'type' : 'ir.actions.act_window',
				'context' : context,

                'hilight_menu_id': None,
                'type' : 'ir.actions.act_window',
                'target' : 'current', #'target' : None,
                'views': [],
		}

		print res
		return res

	def generate_rules_button(self, cr, uid, ids, context={}):
		"""
		Generate and return field_access_rule_line's for each field of the model and all inherited models, with Write Access checked
		"""
		print '======================== generate rules button'
		print ids

		field_access_rule = self.browse(cr, uid, ids[0])

		fields_pool = self.pool.get('ir.model.fields')
		fields_search = fields_pool.search(cr, uid, [('model_id','=',field_access_rule.model.id)], context=context)
		fields = fields_pool.read(cr, uid, fields_search, context=context)

		res = []
		for field in fields:
			res.append({'field_name' : field['name']})

		print res
		return {'values' : {'field_access_rule_line_ids' : res}}

	def manage_rule_lines_button():
		"""
		Send the user to a list view of field_access_rule_line's for this field_access_rule.
		"""
		pass

	def validate_button():
		"""
		Validates the domain filter, and if successful, changes the Status field to validated
		"""
		pass

field_access_rule()