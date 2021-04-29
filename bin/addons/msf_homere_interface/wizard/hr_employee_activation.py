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


class hr_employee_activation(osv.osv_memory):
    _name = 'hr.employee.activation'

    _columns = {
        'active_status': fields.boolean('Set selected employees as active'),
    }

    _defaults = {
        'active_status': True,
    }

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
        for employee_id in context.get('active_ids', []):
            employee_obj.write(cr, uid, employee_id, {'active': data['active_status']}, context=context)
        return {'type': 'ir.actions.act_window_close'}


hr_employee_activation()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
