# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022 TeMPO Consulting, MSF. All Rights Reserved
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


class account_employee_ledger(osv.osv_memory):
    """
    This wizard will provide the employee Ledger report by periods, between any two dates.
    """
    _name = 'account.employee.ledger'
    _inherit = 'account.common.employee.report'
    _description = 'Account Employee Ledger'

    def get_payment_methods(self, cr, uid, context):
        pm_obj = self.pool.get('hr.payment.method')
        pm_ids = pm_obj.search(cr, uid, [], context=context)
        pm_names = pm_obj.read(cr, uid, pm_ids, ['name'], context=context)
        res = [('blank', '')]
        res += [(pm_name['name'], pm_name['name']) for pm_name in pm_names]
        return res

    def get_employee_type(self, cr, uid, context):
        return self.pool.get('hr.employee').fields_get(cr, uid, ['employee_type'], context=context)['employee_type']['selection']

    _columns = {
        'reconciled': fields.selection([
            ('empty', ''),
            ('yes', 'Yes'),
            ('no', 'No'),
        ], string='Reconciled'),
        'page_split': fields.boolean('One Employee Per Page', help='Display Ledger Report with One employee per page (PDF version only)'),
        'employee_ids': fields.many2many('hr.employee', 'account_employee_ledger_employee_rel', 'wizard_id', 'identification_id', string='Employees',
                                         help='Display the report for specific employees only'),
        'only_active_employees': fields.boolean('Only active employees', help='Display the report for active employees only'),
        'instance_ids': fields.many2many('msf.instance', 'account_employee_ledger_instance_rel', 'wizard_id', 'instance_id', string='Proprietary Instances',
                                         help='Display the report for specific proprietary instances only'),
        'account_ids': fields.many2many('account.account', 'account_employee_ledger_account_rel', 'wizard_id', 'account_id', string='Accounts',
                                        help='Display the report for specific accounts only'),
        'display_employee': fields.selection([('all', 'All Employees'), ('with_movements', 'With movements'),
                                              ('non-zero_balance', 'With balance is not equal to 0')],
                                             string='Display Employees', required=True),
        'employee_type': fields.selection(get_employee_type, string='Employee Type', required=False),
        'payment_method': fields.selection(get_payment_methods, string='Method of Payment', required=False),
    }

    _defaults = {
        'reconciled': 'empty',
        'page_split': False,
        'result_selection': 'customer_supplier',
        'account_domain': "[('type', 'in', ['payable', 'receivable'])]",
        'only_active_employees': False,
        'fiscalyear_id': False,
        'display_employee': 'with_movements',
        'employee_type': '',
        'payment_method': 'blank',
    }

    def _print_report(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['reconciled', 'page_split', 'employee_ids',
                                                     'only_active_employees', 'instance_ids', 'account_ids',
                                                     'display_employee', 'employee_type', 'payment_method'])[0])
        if not data['form']['employee_type']:
            data['form']['employee_type'] = ''
        self._check_dates_fy_consistency(cr, uid, data, context)
        if data['form']['page_split']:
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'account.employee_ledger',
                'datas': data,
            }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.employee_ledger_other',
            'datas': data,
        }

    def print_report_xls(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        data = {'keep_open': 1, 'ids': context.get('active_ids', []),
                'model': context.get('active_model', 'ir.ui.menu'), 'form': self.read(cr, uid, ids,
                                                                                      ['date_from', 'date_to',
                                                                                       'fiscalyear_id', 'journal_ids',
                                                                                       'period_from', 'period_to',
                                                                                       'filter', 'chart_account_id',
                                                                                       'target_move'])[0]}
        used_context = self._build_contexts(cr, uid, ids, data, context=context)
        data['form']['periods'] = used_context.get('periods', False) and used_context['periods'] or []
        data['form']['used_context'] = used_context

        data = self.pre_print_report(cr, uid, ids, data, context=context)
        data['form'].update(self.read(cr, uid, ids, ['reconciled', 'page_split', 'employee_ids',
                                                     'only_active_employees', 'instance_ids', 'account_ids',
                                                     'display_employee', 'employee_type', 'payment_method'])[0])
        if not data['form']['employee_type']:
            data['form']['employee_type'] = ''
        self._check_dates_fy_consistency(cr, uid, data, context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.employee_ledger_xls',
            'datas': data,
        }


account_employee_ledger()
