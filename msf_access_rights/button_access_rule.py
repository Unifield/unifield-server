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

class button_access_rule(osv.osv):
    """
    Lets user create access rules for buttons in views.
    This class defines which model, view, button, and groups to target
    """

    _name = "msf_access_rights.button_access_rule"
    
    def _get_group_names(self, cr, uid, ids, field_name, arg, context):
        res = dict.fromkeys(ids, '')
        records = self.browse(cr, uid, ids)
        for record in records:
            group_names = ''
            for g in record.group_ids:
                group_names = group_names + g.name + ', '
            res[record.id] = group_names
        return res

    _columns = {
        'name': fields.char('Name', size=256, required=True),
        'label': fields.char('Label', size=256),
        'type': fields.selection((('Workflow','workflow'), ('Object','object'), ('Action', 'action')), 'Button Type'),
        'model_id': fields.many2one('ir.model', 'Model', help='The type of data to which this rule applies', required=True),
        'view_id': fields.many2one('ir.ui.view', 'View', help='The view to which this rule applies', required=True),
        'group_ids': fields.many2many('res.groups', 'button_access_rule_groups_rel', 'button_access_rule_id', 'group_id', 'Groups', help='A list of groups who have access to this button. If you leave this empty, everybody will have access.'),
        'comment': fields.text('Comment', help='A description of what this rule does'),
        'group_names': fields.function(_get_group_names, type='char', method=True, string='Group Names', help='A list of all group names given button access by this rule'),
        'active': fields.boolean('Active', help='If checked, this rule will be applied.'),
    }

    _defaults = {
        'active': True,
    }
    
    _sql_constraints = [
        ('name_view_unique', 'unique (name, view_id)', "The combination of Button Name and View ID must be unique - i.e. you cannot have two rules for the same button in the same view"),
    ]
               
button_access_rule()
