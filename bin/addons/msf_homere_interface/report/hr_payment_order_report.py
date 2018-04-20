# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from report import report_sxw


class hr_payment_order_report(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(hr_payment_order_report, self).__init__(cr, uid, name, context=context)
        self.context = {}
        self.payment_method_id = False
        self.period_id = False
        self.localcontext.update({
            'lines': self._get_lines,
            'period_selected': self._get_period_selected,
            'payment_method_selected': self._get_payment_method_selected,
        })

    def _get_period_selected(self):
        """
        Returns the name of the period selected or "-"
        """
        if not self.period_id:
            return '-'
        period_obj = self.pool.get('account.period')
        period = period_obj.browse(self.cr, self.uid, self.period_id, fields_to_fetch=['name'], context=self.context)
        return period.name

    def _get_payment_method_selected(self):
        """
        Returns the name of the payment method selected or "-"
        """
        if not self.payment_method_id:
            return '-'
        payment_method_obj = self.pool.get('hr.payment.method')
        payment_method = payment_method_obj.browse(self.cr, self.uid, self.payment_method_id, fields_to_fetch=['name'],
                                                   context=self.context)
        return payment_method.name

    def _get_lines(self):
        """
        Returns a list of lines to display in the report, grouped and ordered by employee and currency.
        Each line contains the employee name, identification number, bank data, and total of the JIs matching the criteria.
        Employees = LOCAL Staff using the Payment Method selected.
        JIs = per employee, posted, unreconciled, with a posting date in the period selected if any, booked on an account
        having the account type "Payables" or "Receivables" (=> internal types are ignored), no matter the journal used.
        """
        res = []
        employee_obj = self.pool.get('hr.employee')
        account_obj = self.pool.get('account.account')
        aml_obj = self.pool.get('account.move.line')
        employee_ids = employee_obj.search(self.cr, self.uid, [('employee_type', '=', 'local'),
                                                               ('payment_method_id', '=', self.payment_method_id)],
                                           order='name', context=self.context)
        for employee in employee_obj.browse(self.cr, self.uid, employee_ids,
                                            fields_to_fetch=['name', 'identification_id', 'bank_name', 'bank_account_number'],
                                            context=self.context):
            account_ids = account_obj.search(self.cr, self.uid,
                                             [('user_type_code', 'in', ['receivables', 'payables'])],
                                             order='NO_ORDER', context=self.context)
            dom = [('move_state', '=', 'posted'),
                   ('reconcile_id', '=', False),
                   ('employee_id', '=', employee.id),
                   ('account_id', 'in', account_ids)]
            if self.period_id:
                dom.append(('period_id', '=', self.period_id))
            aml_ids = aml_obj.search(self.cr, self.uid, dom, order='currency_id', context=self.context)
            curr = {}
            for aml in aml_obj.browse(self.cr, self.uid, aml_ids, fields_to_fetch=['amount_currency', 'currency_id'],
                                      context=self.context):
                if aml.currency_id:
                    if aml.currency_id.name not in curr:
                        curr[aml.currency_id.name] = 0.0
                    curr[aml.currency_id.name] += aml.amount_currency or 0.0
            for c in curr:
                employee_dict = {
                    'employee_name': employee.name,
                    'employee_id': employee.identification_id or '',
                    'bank_name': employee.bank_name or '',
                    'bank_account_number': employee.bank_account_number or '',
                    'net_to_pay': curr[c],
                    'currency': c,
                }
                res.append(employee_dict)
        return res

    def set_context(self, objects, data, ids, report_type=None):
        """
        Retrieves the Payment method & period selected
        """
        self.context = data.get('context', {})
        self.payment_method_id = data.get('payment_method_id')
        self.period_id = data.get('period_id', False)
        return super(hr_payment_order_report, self).set_context(objects, data, ids, report_type)


report_sxw.report_sxw('report.hr.payment.order.report', 'hr.payroll.msf',
                      'addons/msf_homere_interface/report/payment_order_report.rml', parser=hr_payment_order_report,
                      header='internal')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
