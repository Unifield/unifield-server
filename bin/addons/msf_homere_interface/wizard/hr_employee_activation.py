# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2019 MSF, TeMPO Consulting
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

from osv import fields, osv
from tools.translate import _


class hr_employee_activation(osv.osv_memory):
    _name = 'hr.employee.activation'

    _columns = {
        'active_status': fields.boolean('Set selected employees as active'),
    }

    def _get_default_status(self, cr, uid, context=None):
        if context is None:
            context = {}
        emp_ids = context.get('active_ids', [])
        if self.pool.get('hr.employee').search_exist(cr, uid,
                                                     [('id', 'in', emp_ids), ('employee_type', '=', 'ex'), ('not_to_be_used', '=', True)],
                                                     context=context):
            return False

        return True

    _defaults = {
        'active_status': _get_default_status,
    }

    def onchange_active(self, cr, uid, ids, active, context=None):
        if context is None:
            context = {}
        if active:
            emp_obj = self.pool.get('hr.employee')
            not_to_be_used_ids = emp_obj.search(cr, uid,
                                                [('id', 'in', context.get('active_ids', [])), ('employee_type', '=', 'ex'), ('not_to_be_used', '=', True), ('active', '=', False)],
                                                context=context)
            if not_to_be_used_ids:
                emp_names = emp_obj.browse(cr, uid, not_to_be_used_ids[0:10], fields_to_fetch=['name'], context=context)
                return {
                    'warning': {
                        'message': '%s : %s' % (_('You can not activate an employee flagged as not to be used'), '\n'.join([x.name for x in emp_names]))
                    },
                    'value': {'active_status': False}
                }
        return {}

    def change_employee_status(self, cr, uid, ids, context=None):
        """
        Sets the selected employees to active or inactive
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        employee_obj = self.pool.get('hr.employee')
        data = self.read(cr, uid, ids, ['active_status'], context=context)[0]
        emp_ids = context.get('active_ids', [])
        if emp_ids and data['active_status']:
            emp_ids = employee_obj.search(cr, uid,
                                          [('id', 'in', emp_ids), ('active', '=', False), '|', ('employee_type', '=', 'local'), ('not_to_be_used', '=', False)],
                                          context=context)
        if emp_ids:
            employee_obj.write(cr, uid, emp_ids, {'active': data['active_status']}, context=context)
        return {'type': 'ir.actions.act_window_close'}


hr_employee_activation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
