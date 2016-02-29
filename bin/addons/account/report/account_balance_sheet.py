# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

import time

import pooler
from report import report_sxw
from account.report import account_profit_loss
from common_report_header import common_report_header
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _

class report_balancesheet_horizontal(report_sxw.rml_parse, common_report_header):
    def __init__(self, cr, uid, name, context=None):
        super(report_balancesheet_horizontal, self).__init__(cr, uid, name, context=context)
        self.obj_pl = account_profit_loss.report_pl_account_horizontal(cr, uid, name, context=context)
        self.result_sum_dr = 0.0
        self.result_sum_cr = 0.0
        self.result = {}
        self.res_bl = {}
        self.result_temp = []
        self.localcontext.update({
            'time': time,
            'get_lines': self.get_lines,
            'get_lines_another': self.get_lines_another,
            'get_company': self._get_company,
            'get_currency': self._get_currency,
            'sum_dr': self.sum_dr,
            'sum_cr': self.sum_cr,
            'get_data':self.get_data,
            'get_pl_balance':self.get_pl_balance,
            'get_fiscalyear': self._get_fiscalyear,
            'get_account': self._get_account,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_sortby': self._get_sortby,
            'get_filter': self._get_filter,
            'get_journal': self._get_journal,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_company':self._get_company,
            'get_target_move': self._get_target_move,
            'get_display_info': self.get_display_info,
            'get_filter_name': self._get_filter,
            'get_filter_info': self.get_filter_info,
            'get_prop_instances': self.get_prop_instances,
        })
        self.context = context

    def set_context(self, objects, data, ids, report_type=None):
        new_ids = ids
        if (data['model'] == 'ir.ui.menu'):
            new_ids = 'chart_account_id' in data['form'] and [data['form']['chart_account_id']] or []
            objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids)
            lang_dict = self.pool.get('res.users').read(self.cr,self.uid,self.uid,['context_lang'])
            data['lang'] = lang_dict.get('context_lang') or False
        res = super(report_balancesheet_horizontal, self).set_context(objects, data, new_ids, report_type=report_type)
        common_report_header._set_context(self, data)
        return res

    def sum_dr(self):
        if self.res_bl['type'] == _('Net Profit'):
            self.result_sum_dr += self.res_bl['balance']*-1
        '''if self._deduce_accounts_data and self._deduce_accounts_data['debit']:
            if self.result_sum_dr < 0:
                self.result_sum_dr += self._deduce_accounts_data['debit']
            else:
                self.result_sum_dr -= self._deduce_accounts_data['debit']'''
        return self.result_sum_dr

    def sum_cr(self):
        if self.res_bl['type'] == _('Net Loss'):
            self.result_sum_cr += self.res_bl['balance']
        '''if self._deduce_accounts_data and self._deduce_accounts_data['credit']:
            if self.result_sum_cr < 0:
                self.result_sum_cr += self._deduce_accounts_data['credit']
            else:
                self.result_sum_cr -= self._deduce_accounts_data['credit']'''
        return self.result_sum_cr

    def get_pl_balance(self):
        return self.res_bl

    def get_data(self,data):
        cr, uid = self.cr, self.uid
        db_pool = pooler.get_pool(self.cr.dbname)

        #Getting Profit or Loss Balance from profit and Loss report
        self.obj_pl.get_data(data)
        self.res_bl = self.obj_pl.final_result()

        account_pool = db_pool.get('account.account')
        currency_pool = db_pool.get('res.currency')

        types = [
            'liability',
            'asset'
        ]

        # set context
        ctx = self.context.copy()
        ctx['fiscalyear'] = data['form'].get('fiscalyear_id', False)
        if data['form']['filter'] == 'filter_period':
            ctx['periods'] = data['form'].get('periods', False)
        elif data['form']['filter'] == 'filter_date':
            ctx['date_from'] = data['form'].get('date_from', False)
            ctx['date_to'] =  data['form'].get('date_to', False)
        ctx['state'] = data['form'].get('target_move', 'all')
        if 'instance_ids' in data['form']:
            ctx['instance_ids'] = data['form']['instance_ids']

        cal_list = {}
        pl_dict = {}
        account_dict = {}
        account_id = data['form'].get('chart_account_id', False)
        account_ids = account_pool._get_children_and_consol(cr, uid, account_id, context=ctx)
        accounts = account_pool.browse(cr, uid, account_ids, context=ctx)
        
        # US-227/6: accounts 8*, 9* are not displayed:
        '''self._deduce_accounts_data = { 'debit': 0., 'credit': 0., }'''

        if not self.res_bl:
            self.res_bl['type'] = _('Net Profit')
            self.res_bl['balance'] = 0.0

        if self.res_bl['type'] == _('Net Profit'):
            self.res_bl['type'] = _('Net Profit')
        else:
            self.res_bl['type'] = _('Net Loss')
        pl_dict  = {
            'code': self.res_bl['type'],
            'name': self.res_bl['type'],
            'level': False,
            'balance':self.res_bl['balance'],
        }
        for typ in types:
            accounts_temp = []
            for account in accounts:
                """ before US-227/1
                PAY ATTENTION TO KEEP THIS COMMENTED AS OCA NEED TO DISCUSS
                IF ALL THE WORK IS DONE COA SETTINGS LEVEL VS
                US-227/1, breakdown in asset/liability below
                if (account.user_type.report_type) and (account.user_type.report_type == typ):
                    account_dict = {
                        'id': account.id,
                        'code': account.code,
                        'name': account.name,
                        'level': account.level,
                        'balance':account.balance,
                    }"""
                # US-227/1 starts from here
                """
                B/S report : display account Internal Type
                 - Liquidity, Receivable under Assets (left side)
                 - and account Internal type Payable under Liabilities (right side)
                For the Regular internal type, some will be under Asset and some others under Liabilities
                    - Regular/Cash, Regular/Asset, Regular/Stock are under Assets
                    - Regular/Debt, Regular Equity are under Liabilities

                Note US-227/7.1
                - if account is linked to account type tax and is a Receivable internal type, display it in the Assets column
                - if account is linked to account type tax and is a Payable internal type, display it in the Liability column
                is already included in the following US-227/1 1st condition:
                    display account Internal Type Liquidity, Receivable under Assets (left side)and account Internal type Payable under Liabilities (right side)
                """
                register_account = False

                if typ == 'asset':
                    # US-227/1, breakdown in asset:
                    # - Internal Type Liquidity,
                    # - Internal Type Receivable,
                    # - Regular/Cash, Regular/Asset, Regular/Stock
                    register_account = \
                        account.type in ('liquidity', 'receivable', ) or \
                        (account.type == 'other' \
                            and account.user_type.code in (
                                'cash',
                                'asset',
                                'stock',
                                )) or False
                elif  typ == 'liability':
                    # US-227/1, breakdown in liability:
                    # - Internal type Payable
                    # - Regular/Debt, Regular/Equity
                    register_account = \
                        account.type == 'payable' or \
                        (account.type == 'other' \
                            and account.user_type.code in (
                                'debt',
                                'equity',
                                )) or False
                if register_account:
                    account_dict = {
                        'id': account.id,
                        'code': account.code,
                        'name': account.name,
                        'level': account.level,
                        'balance':account.balance,
                    } # US-227/1 ends here
                    currency = account.currency_id and account.currency_id or account.company_id.currency_id
                    if typ == 'liability' and account.type <> 'view' and (account.debit <> account.credit):
                        self.result_sum_dr += account.balance
                        '''if account.code.startswith('8') \
                            or account.code.startswith('9'):
                                # US-227/6: accounts 8*, 9* are not displayed
                                self._deduce_accounts_data['debit'] += account.balance
                                continue'''
                    if typ == 'asset' and account.type <> 'view' and (account.debit <> account.credit):
                        self.result_sum_cr += account.balance
                        '''if account.code.startswith('8') \
                            or account.code.startswith('9'):
                                # US-227/6: accounts 8*, 9* are not displayed
                                self._deduce_accounts_data['credit'] += account.balance
                                continue'''
                    '''if account.code.startswith('8') \
                        or account.code.startswith('9'):
                            # US-227/6: accounts 8*, 9* are not displayed
                            continue'''
                    if data['form']['display_account'] == 'bal_movement':
                        if (not currency_pool.is_zero(self.cr, self.uid, currency, account.credit)) or (not currency_pool.is_zero(self.cr, self.uid, currency, account.debit)) or (not currency_pool.is_zero(self.cr, self.uid, currency, account.balance)):
                            accounts_temp.append(account_dict)
                    elif data['form']['display_account'] == 'bal_solde':
                        if not currency_pool.is_zero(self.cr, self.uid, currency, account.balance):
                            accounts_temp.append(account_dict)
                    else:
                        accounts_temp.append(account_dict)
                    if account.id == data['form']['reserve_account_id']:
                        pl_dict['level'] = account['level'] + 1
                        accounts_temp.append(pl_dict)

            self.result[typ] = accounts_temp
            cal_list[typ]=self.result[typ]

        if cal_list:
            temp = {}
            for i in range(0,max(len(cal_list['liability']),len(cal_list['asset']))):
                if i < len(cal_list['liability']) and i < len(cal_list['asset']):
                    temp={
                          'code': cal_list['liability'][i]['code'],
                          'name': cal_list['liability'][i]['name'],
                          'level': cal_list['liability'][i]['level'],
                          'balance':cal_list['liability'][i]['balance'],
                          'code1': cal_list['asset'][i]['code'],
                          'name1': cal_list['asset'][i]['name'],
                          'level1': cal_list['asset'][i]['level'],
                          'balance1':cal_list['asset'][i]['balance'],
                          }
                    self.result_temp.append(temp)
                else:
                    if i < len(cal_list['asset']):
                        temp={
                              'code': '',
                              'name': '',
                              'level': False,
                              'balance':False,
                              'code1': cal_list['asset'][i]['code'],
                              'name1': cal_list['asset'][i]['name'],
                              'level1': cal_list['asset'][i]['level'],
                              'balance1':cal_list['asset'][i]['balance'],
                          }
                        self.result_temp.append(temp)
                    if  i < len(cal_list['liability']):
                        temp={
                              'code': cal_list['liability'][i]['code'],
                              'name': cal_list['liability'][i]['name'],
                              'level': cal_list['liability'][i]['level'],
                              'balance':cal_list['liability'][i]['balance'],
                              'code1': '',
                              'name1': '',
                              'level1': False,
                              'balance1':False,
                          }
                        self.result_temp.append(temp)
        return None

    def get_lines(self):
        return self.result_temp

    def get_lines_another(self, group):
        return self.result.get(group, [])

    def get_display_info(self, data):
        info_data = []
        yes_str = _('Yes')
        no_str = _('No')
        all_str = _('All')

        display_account = all_str
        if 'display_account' in data['form']:
            if data['form']['display_account'] == 'bal_all':
                display_account = _('All')
            elif data['form']['display_account'] == 'bal_movement':
                display_account = _('With movements')
            else:
                display_account = _('With balance is not equal to 0')
        info_data.append((_('Accounts'), display_account, ))

        res = [ "%s: %s" % (label, val, ) for label, val in info_data ]
        return ', \n'.join(res)

    def get_filter_info(self, data):
        """ get filter info
        _get_filter, _get_start_date, _get_end_date,
        get_start_period, get_end_period
        are from common_report_header
        """
        if not data.get('form', False):
            return ''
        infos = []

        # date/period
        if data.get('form', False) and data['form'].get('filter', False):
            line = ''
            if data['form']['filter'] in ('filter_date', ):
                line = _('Posting')
                line += " %s " % (_('Date'), )
                line += self.formatLang(self._get_start_date(data), date=True) + ' - ' + self.formatLang(self._get_end_date(data), date=True)
            elif data['form']['filter'] == 'filter_period':
                line = self.get_start_period(data) + ' - ' + self.get_end_period(data)
            if line:
                infos.append(line)
        return infos and ", \n".join(infos) or _('No Filter')

    def get_prop_instances(self, data):
        instances = []
        if data.get('form', False):
            if data['form'].get('instance_ids', False):
                self.cr.execute('select code from msf_instance where id IN %s',
                    (tuple(data['form']['instance_ids']),))
            else:
                self.cr.execute('select code from msf_instance')
            instances = [x for x, in self.cr.fetchall()]
        return ', '.join(instances)

report_sxw.report_sxw('report.account.balancesheet.horizontal', 'account.account',
    'addons/account/report/account_balance_sheet_horizontal.rml',parser=report_balancesheet_horizontal,
    header='internal landscape')

report_sxw.report_sxw('report.account.balancesheet', 'account.account',
    'addons/account/report/account_balance_sheet.rml',parser=report_balancesheet_horizontal,
    header='internal')


class balance_sheet_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
        header='external', store=False):
        super(balance_sheet_xls, self).__init__(name, table, rml=rml,
            parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        #ids = getIds(self, cr, uid, ids, context)
        a = super(balance_sheet_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

balance_sheet_xls('report.account.balance.sheet_xls', 'account.account',
    'addons/account/report/account_balance_sheet_xls.mako',
    parser=report_balancesheet_horizontal, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
