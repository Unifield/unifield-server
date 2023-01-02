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

class button_access_rule(osv.osv):
    """
    Lets user create access rules for buttons in views.
    This class defines which model, view, button, and groups to target
    """

    _name = "msf_button_access_rights.button_access_rule"
    _inherit = 'common.import.ur'
    _auto = True

    def _get_group_names(self, cr, uid, ids, field_name, arg, context):
        res = dict.fromkeys(ids, '')
        records = self.browse(cr, uid, ids)
        for record in records:
            res[record.id] = ', '.join([g.name for g in record.group_ids])
        return res

    _columns = {
        'create_date': fields.date('Creation date', readonly=True),
        'name': fields.char('Name', size=256, required=True),
        'label': fields.char('Label', size=256),
        'type': fields.selection((('workflow','Workflow'), ('object','Object'), ('action', 'Action')), 'Button Type'),
        'xmlname': fields.char('Button action name', size=1024),
        'model_id': fields.many2one('ir.model', 'Model', help='The type of data to which this rule applies', required=True, ondelete='cascade'),
        'view_id': fields.many2one('ir.ui.view', 'View', help='The view to which this rule applies', required=True, ondelete='cascade'),
        'group_ids': fields.many2many('res.groups', 'button_access_rule_groups_rel', 'button_access_rule_id', 'group_id', 'Groups', help='A list of groups who have access to this button. If you leave this empty, everybody will have access.', order_by='name'),
        'comment': fields.text('Comment', help='A description of what this rule does'),
        'group_names': fields.function(_get_group_names, type='char', method=True, string='Group Names', help='A list of all group names given button access by this rule'),
        'active': fields.boolean('Active', help='If checked, this rule will be applied.'),
        'deprecated': fields.boolean('Deprecated'),
        'bar_type': fields.selection([('IT', 'IT'), ('Supply', 'Supply'), ('Finance', 'Finance')], string='Type'),
    }

    _defaults = {
        'active': True,
        'deprecated': True,
        'bar_type': False,
    }

    _sql_constraints = [
        ('name_view_unique', 'unique (name, view_id)', "The combination of Button Name and View ID must be unique - i.e. you cannot have two rules for the same button in the same view"),
    ]

    def _update_name_for_action(self, cr, uid, xmlname):
        module, xml = xmlname.split('.', 1)
        data_obj = self.pool.get('ir.model.data')
        data_ids = data_obj.search(cr, uid, [('module', '=', module), ('name', '=', xml)])
        if data_ids:
            return data_obj.read(cr, uid, data_ids[0], ['res_id'])['res_id']
        return False

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('sync_update_execution') and vals.get('type') == 'action' and vals.get('xmlname'):
            new_name = self._update_name_for_action(cr, uid, vals['xmlname'])
            if new_name:
                vals['name'] = new_name
        elif not context.get('sync_update_execution') and vals.get('type') == 'action' and not vals.get('xmlname') and vals.get('name'):
            vals['xmlname'] = self.pool.get('ir.ui.view')._get_xmlname(cr, uid, vals.get('type'), vals.get('name'))

        vals['deprecated'] = False
        return super(button_access_rule, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if context.get('sync_update_execution') and vals.get('xmlname'):
            new_name = self._update_name_for_action(cr, uid, vals['xmlname'])
            if new_name:
                vals['name'] = new_name
        vals['deprecated'] = False
        return super(button_access_rule, self).write(cr, uid, ids, vals, context)

    def get_family_ids(self, cr, uid, view_id):
        """
        Return a list of ids for all the children of view_id (and contains the view_id itself)
        """
        family_ids = [view_id]
        last_ids = [view_id]
        view_pool = self.pool.get('ir.ui.view')

        while(last_ids):
            last_ids = view_pool.search(cr, 1, [('inherit_id','in',last_ids)])
            family_ids = family_ids + last_ids

        return family_ids

button_access_rule()

class res_groups(osv.osv):
    _inherit = 'res.groups'
    _columns = {
        'bar_ids': fields.many2many('msf_button_access_rights.button_access_rule', 'button_access_rule_groups_rel', 'group_id', 'button_access_rule_id', 'Buttons Access Rules', readonly=1),
    }
res_groups()
