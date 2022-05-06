# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022 TeMPO Consulting, MSF
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


class account_employee_balance(osv.osv_memory):
    """
        This wizard will provide the employee balance report by periods, between any two dates.
    """
    _inherit = 'account.common.employee.report'
    _name = 'account.employee.balance'
    _description = 'Print Account Employee Balance'
    _columns = {
        'display_employee': fields.selection([('non-zero_balance', 'With balance is not equal to 0'),
                                              ('all', 'All Employees')], 'Display Employees'),
    }

    _defaults = {
        'display_employee': 'non-zero_balance',
    }

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['display_employee'])[0])
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.employee.balance',
            'datas': data,
        }


account_employee_balance()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
