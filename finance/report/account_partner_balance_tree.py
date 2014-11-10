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

from tools.translate import _
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

class account_partner_balance_tree(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context=None):
        super(account_partner_balance_tree, self).__init__(cr, uid, name, context=context)
        self.apbt_obj = self.pool.get('account.partner.balance.tree')
        self.uid = uid
        self.localcontext.update({
            # header
            'get_account': self._get_account,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_filter': self._get_filter,
            'get_filter_info': self._get_filter_info,
            'get_sortby': self._get_sortby,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_target_move': self._get_target_move,
            'get_prop_instances': self._get_prop_instances,

            # data
            'get_partners': self._get_partners,
            'get_partner_account_move_lines': self._get_partner_account_move_lines,
            'get_partners_total_debit_credit_balance_by_account_type': self._get_partners_total_debit_credit_balance_by_account_type,

            # currency
            'get_output_currency_code': self._get_output_currency_code,
            'currency_conv': self._currency_conv,
        })

        # company currency
        self.currency_id = self.apbt_obj._get_company_currency(cr, uid, context=context)

    def set_context(self, objects, data, ids, report_type=None):
        self.sortby = data['form'].get('sortby', 'sort_date')

        self.display_partner = data['form'].get('display_partner', 'non-zero_balance')
        self.result_selection = data['form'].get('result_selection')
        self.target_move = data['form'].get('target_move', 'all')

        if (self.result_selection == 'customer' ):
            self.ACCOUNT_TYPE = ('receivable',)
        elif (self.result_selection == 'supplier'):
            self.ACCOUNT_TYPE = ('payable',)
        else:
            self.ACCOUNT_TYPE = ('payable', 'receivable')

        # output currency
        self.output_currency_id = data['form']['output_currency']
        self.output_currency_code = ''
        if self.output_currency_id:
            ouput_cur_r = self.pool.get('res.currency').read(self.cr,
                                            self.uid,
                                            [self.output_currency_id],
                                            ['name'])
            if ouput_cur_r and ouput_cur_r[0] and ouput_cur_r[0]['name']:
                self.output_currency_code = ouput_cur_r[0]['name']

        return super(account_partner_balance_tree, self).set_context(objects, data, ids, report_type=report_type)

    def _get_partners(self, data):
        """ return a list of 1 or 2 elements each element containing browse objects
        only [payable] or only [receivable] or [payable, receivable]
        """
        res = []
        for at in self.ACCOUNT_TYPE:
            objects = self.apbt_obj.get_partner_data(self.cr, self.uid, [at], data)
            if objects:
                res.append(objects)
        return res

    def _get_partner_account_move_lines(self, account_type, partner_id, data):
        return self.apbt_obj.get_partner_account_move_lines_data(self.cr, self.uid, account_type, partner_id, data)

    def _get_partners_total_debit_credit_balance_by_account_type(self, account_type, data):
        return self.apbt_obj.get_partners_total_debit_credit_balance_by_account_type(self.cr, self.uid, account_type, data)

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

        if f == 'No Filter':
            res = f
        elif f == 'Date':
            res = self.formatLang(self._get_start_date(data), date=True) + ' - ' + self.formatLang(self._get_end_date(data), date=True)
        elif f == 'Periods':
            res = self.get_start_period(data) + ' - ' + self.get_end_period(data)
        return res

    def _get_sortby(self, data):
        if self.sortby == 'sort_date':
            return 'Date'
        elif self.sortby == 'sort_journal_partner':
            return 'Journal & Partner'
        return 'Date'

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
        codes = []
        if data.get('form', False) and data['form'].get('journal_ids', False):
            self.cr.execute('select code from account_journal where id IN %s',(tuple(data['form']['journal_ids']),))
            codes = [x for x, in self.cr.fetchall()]
        return codes

    def _get_output_currency_code(self):
        if not self.output_currency_code:
            return ''
        return self.output_currency_code

    def _get_prop_instances(self, data):
        instances = []
        if data.get('form', False) and data['form'].get('instance_ids', False):
            self.cr.execute('select code from msf_instance where id IN %s',(tuple(data['form']['instance_ids']),))
            instances = [x for x, in self.cr.fetchall()]
        return instances

    def _currency_conv(self, amount, date):
        return self.apbt_obj._currency_conv(self.cr, self.uid, amount,
                                                self.currency_id,
                                                self.output_currency_id,
                                                date)

class account_partner_balance_tree_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(account_partner_balance_tree_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(account_partner_balance_tree_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

account_partner_balance_tree_xls('report.account.partner.balance.tree_xls', 'account.partner.balance.tree', 'finance/report/account_partner_balance_tree_xls.mako', parser=account_partner_balance_tree, header='internal')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
