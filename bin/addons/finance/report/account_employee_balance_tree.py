# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2022 TeMPO Consulting
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

from tools.translate import _
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import pooler


class account_employee_balance_tree(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(account_employee_balance_tree, self).__init__(cr, uid, name, context=context)
        self.aebt_obj = self.pool.get('account.employee.balance.tree')
        self.uid = uid
        self.has_data = True
        self.localcontext.update({
            # header
            'get_account': self._get_account,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journals_str': self._get_journals_str,
            'get_filter': self._get_filter,
            'get_filter_info': self._get_filter_info,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_target_move': self._get_target_move,
            'get_prop_instances_str': self._get_prop_instances_str,
            'get_type_of_accounts': self._get_type_of_accounts,
            'get_accounts_str': self._get_accounts_str,
            'get_reconcile_selection': self._get_reconcile_selection,
            'get_display_employees_selection': self._get_display_employees_selection,
            'get_employee_type': self._get_employee_type,
            'get_payment_methods': self._get_payment_methods,

            # data
            'get_employees': self._get_employees,
            'get_employee_account_move_lines': self._get_employee_account_move_lines,
            'get_lines_per_currency': self._get_lines_per_currency,
            'get_employees_total_debit_credit_balance': self._get_employees_total_debit_credit_balance,
            'get_has_data': self._get_has_data,
        })

    def set_context(self, objects, data, ids, report_type=None):
        self.display_employee = data['form'].get('display_employee', 'non-zero_balance')
        self.result_selection = data['form'].get('result_selection')
        self.target_move = data['form'].get('target_move', 'all')
        return super(account_employee_balance_tree, self).set_context(objects, data, ids, report_type=report_type)

    def _get_employee_type(self, data):
        """
        Returns the String to display in the "Employee Type" section of the report header
        """
        emp_type = _('All')
        # if specific employees are selected don't display emp type
        if data['form'].get('employee_ids', False):
            emp_type = '-'
        else:
            emp = data['form'].get('employee_type', False)
            if emp == 'local':
                emp_type = _('Local Staff')
            if emp == 'ex':
                emp_type = _('Expatriate Staff')
        return emp_type

    def _get_payment_methods(self, data):
        """
        Returns the String to display in the "Payment Method" section of the report header
        """
        pay_method = _('All')
        # if specific employees are selected don't display payment method
        if data['form'].get('employee_ids', False):
            pay_method = '-'
        else:
            method = data['form'].get('payment_method')
            if method != 'blank':
                return method
        return pay_method

    def _get_type_of_accounts(self):
        if self.result_selection == 'customer':
            return _('Receivable Accounts')
        elif self.result_selection == 'supplier':
            return _('Payable Accounts')
        elif self.result_selection == 'customer_supplier':
            return _('Receivable and Payable Accounts')
        return ''

    def _get_has_data(self):
        """
        Returns True if there is data to display in the report
        """
        return bool(self.has_data)

    def _get_employees(self, data):
        """ return a list of 1 or 2 elements each element containing browse objects
        only [payable] or only [receivable] or [payable, receivable]
        """
        res = []
        objects = self.aebt_obj.get_employee_data(self.cr, self.uid, data)
        if objects:
            res.append(objects)
        self.has_data = len(res)
        return res

    def _get_reconcile_selection(self, data):
        """
        Returns "Yes" if "Reconciled: Yes" is selected in the wizard
        """
        selection = _('All')
        if data['form'].get('reconciled', '') == 'yes':
            selection = _('Yes')
        elif data['form'].get('reconciled', '') == 'no':
            selection = _('No')
        return selection

    def _get_display_employees_selection(self, data):
        """
        Returns the String to display in the "Display Employees" section of the report header
        """
        selection = ''
        display_employee = data['form'].get('display_employee', '')
        if display_employee == 'all':
            selection = _('All Employees')
        elif display_employee == 'with_movements':
            selection = _('With movements')
        elif display_employee == 'non-zero_balance':
            selection = _('With balance is not equal to 0')
        return selection

    def _get_employee_account_move_lines(self, employee_id, data):
        return self.aebt_obj.get_employee_account_move_lines_data(self.cr, self.uid, employee_id, data)

    def _get_lines_per_currency(self, employee_id, data, account_code):
        return self.aebt_obj.get_lines_per_currency(self.cr, self.uid, employee_id, data, account_code)

    def _get_employees_total_debit_credit_balance(self, data):
        return self.aebt_obj.get_employees_total_debit_credit_balance(self.cr, self.uid, data)

    def _get_filter_info(self, data):
        """ get filter info
        _get_filter, _get_start_date, _get_end_date,
        get_start_period, get_end_period
        are from common_report_header
        """
        res = ''
        f = self._get_filter(data)
        if not f:
            return res

        if f == _('No Filter'):
            res = f
        elif f == _('Date'):
            res = self.formatLang(self._get_start_date(data), date=True) + ' - ' + self.formatLang(self._get_end_date(data), date=True)
        elif f == _('Periods'):
            res = self.get_start_period(data) + ' - ' + self.get_end_period(data)
        return res

    def _get_start_date(self, data):
        if data.get('form', False) and data['form'].get('date_from', False):
            return data['form']['date_from']
        return ''

    def _get_target_move(self, data):
        if data.get('form', False) and data['form'].get('target_move', False):
            if data['form']['target_move'] == 'all':
                return _('All Entries')
            return _('All Posted Entries')
        return ''

    def _get_end_date(self, data):
        if data.get('form', False) and data['form'].get('date_to', False):
            return data['form']['date_to']
        return ''

    def get_start_period(self, data):
        if data.get('form', False) and data['form'].get('period_from', False):
            return self.pool.get('account.period').browse(self.cr,self.uid,data['form']['period_from']).name
        return ''

    def get_end_period(self, data):
        if data.get('form', False) and data['form'].get('period_to', False):
            return self.pool.get('account.period').browse(self.cr, self.uid, data['form']['period_to']).name
        return ''

    def _get_account(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).name
        return ''

    def _get_accounts(self, data):
        """
        Returns:
        - "All Accounts" if no specific account is selected
        - or the codes of all accounts selected
        """
        account_ids = data.get('form', False) and data['form'].get('account_ids', False)
        if account_ids:
            account_obj = pooler.get_pool(self.cr.dbname).get('account.account')
            return [i.code for i in account_obj.browse(self.cr, self.uid, account_ids,
                                                       fields_to_fetch=['code'], context=data.get('context', {}))]
        return [_('All Accounts')]

    def _get_accounts_str(self, data):
        """
        Returns the list of accounts as a String (cut if > 300 characters)
        """
        data_tools_obj = self.pool.get('data.tools')
        return data_tools_obj.truncate_list(self._get_accounts(data))

    def _get_filter(self, data):
        if data.get('form', False) and data['form'].get('filter', False):
            if data['form']['filter'] == 'filter_date':
                return _('Date')
            elif data['form']['filter'] == 'filter_period':
                return _('Periods')
        return _('No Filter')

    def _get_fiscalyear(self, data):
        if data.get('form', False) and data['form'].get('fiscalyear_id', False):
            return self.pool.get('account.fiscalyear').browse(self.cr, self.uid, data['form']['fiscalyear_id']).name
        return ''

    def _get_company(self, data):
        if data.get('form', False) and data['form'].get('chart_account_id', False):
            return self.pool.get.get('account.account').browse(self.cr, self.uid, data['form']['chart_account_id']).company_id.name
        return ''

    def _get_journal(self, data):
        """
        Returns the codes of the journals selected (or "All Journals")
        """
        if data.get('form', False) and 'all_journals' in data['form']:
            return [_('All Journals')]
        codes = []
        if data.get('form', False) and data['form'].get('journal_ids', False):
            self.cr.execute('select distinct(code) from account_journal where id IN %s', (tuple(data['form']['journal_ids']),))
            codes = [x for x, in self.cr.fetchall()]
        return codes

    def _get_journals_str(self, data):
        """
        Returns the list of journals as a String (cut if > 300 characters)
        """
        data_tools_obj = self.pool.get('data.tools')
        return data_tools_obj.truncate_list(self._get_journal(data))

    def _get_prop_instances(self, data):
        """
        Returns the codes of the instances selected (or "All Instances")
        """
        if data.get('form', False) and data['form'].get('instance_ids', False):
            self.cr.execute('select code from msf_instance where id IN %s',(tuple(data['form']['instance_ids']),))
            return [lt or '' for lt, in self.cr.fetchall()]
        return [_('All Instances')]

    def _get_prop_instances_str(self, data, pdf=False):
        """
        Returns the list of instances as a String (cut if > 300 characters)
        """
        display_limit = 300
        if pdf:
            # in the PDF version instances are listed one below the other and instance names are cut if > 20 characters
            instances_str = ',\n'.join([(len(inst) <= 20) and inst or ("%s%s" % (inst[:17], '...'))
                                        for inst in self._get_prop_instances(data)])
            if len(instances_str) > display_limit:
                instances_str = "%s%s" % (instances_str[:display_limit-3], '...')
        else:
            # otherwise instances are simply separated by a comma
            data_tools_obj = self.pool.get('data.tools')
            instances_str = data_tools_obj.truncate_list(self._get_prop_instances(data), limit=display_limit)
        return instances_str


class account_employee_balance_tree_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_employee_balance_tree_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(account_employee_balance_tree_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')


# XLS report
account_employee_balance_tree_xls('report.account.employee.balance.tree_xls', 'account.employee.balance.tree',
                                  'finance/report/account_employee_balance_tree_xls.mako',
                                  parser=account_employee_balance_tree, header='internal')
# PDF report
report_sxw.report_sxw('report.account.employee.balance', 'hr.employee', 'account/report/account_employee_balance.rml',
                      parser=account_employee_balance_tree, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
