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

class field_access_rule_line(osv.osv):
	"""
	Lets user create access and sync propagation rules for fields of models.
	This class specifies the fields and their access and sync propagation rules are implemented by the field_access_rule.
	"""

	_name = "msf_access_rights.field_access_rule_line"

	_columns = {
		'field': fields.many2one('ir.model.fields', 'Field', help='The field of the model for which this rule applies', required=True),
		'field_name': fields.char('Field Name', size=256, help='The technical name for the field. This is used to make searching for Field Access Rule Lines easier.'),
		'write_access': fields.boolean('Write Access', help='If checked, the user has access to write on this field.'),
		'value_not_synchronized_on_create': fields.boolean('Value NOT Synchronized on Create', help='If checked, the value for this field given by a synchronization or import is ignored when this record is created.'),
		'value_not_synchronized_on_write': fields.boolean('Value NOT Synchronized on Write', help='If checked, the value for this field given by a synchronization or import is ignored when this record is editted.'),

		'field_access_rule': fields.many2one('msf_access_rights.field_access_rule', 'Field Access Rule', required=True),
	}

field_access_rule_line()