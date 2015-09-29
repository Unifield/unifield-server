# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2005-2006 CamptoCamp
# Copyright (c) 2006-2010 OpenERP S.A
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly advised to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import time
from report import report_sxw
from common_report_header import common_report_header
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from osv import osv
from tools.translate import _


class general_ledger(report_sxw.rml_parse, common_report_header):
    _name = 'report.account.general.ledger'

    def set_context(self, objects, data, ids, report_type=None):
        new_ids = ids
        obj_move = self.pool.get('account.move.line')
        
        self.sortby = data['form'].get('sortby', 'sort_date')
        self.query = obj_move._query_get(self.cr, self.uid, obj='l', context=data['form'].get('used_context',{}))
        ctx2 = data['form'].get('used_context',{}).copy()
        ctx2.update({'initial_bal': True})
        self.init_query = obj_move._query_get(self.cr, self.uid, obj='l', context=ctx2)
        self.init_balance = data['form']['initial_balance']
        self.display_account = data['form']['display_account']
        self.target_move = data['form'].get('target_move', 'all')
        self.account_type = self._get_data_form(data, 'account_type')
        self.account_ids = self._get_data_form(data, 'account_ids')
        self.show_account_views = self._get_data_form(data,
            'display_account_view')
        self.show_move_lines = self._get_data_form(data,
            'display_details')
        self.unreconciled = self._get_data_form(data,
            'unreconciled')
        self.context['state'] = data['form']['target_move']

        if 'instance_ids' in data['form']:
            self.context['instance_ids'] = data['form']['instance_ids']
        if (data['model'] == 'ir.ui.menu'):
            new_ids = [data['form']['chart_account_id']]
            objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids, context=self.context)
        
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
                
        # proprietary instances filter
        self.instance_ids = data['form']['instance_ids'] 
        if self.instance_ids:
            # we add instance filter in clauses 'self.query/self.init_query' 
            instance_ids_in = "l.instance_id in(%s)" % (",".join(map(str, self.instance_ids)))
            if not self.query:
                self.query = instance_ids_in
            else:
                self.query += ' AND ' + instance_ids_in
            if not self.init_query:
                self.init_query = instance_ids_in
            else:
                self.init_query += ' AND ' + instance_ids_in
        
        res = super(general_ledger, self).set_context(objects, data, new_ids, report_type=report_type)
        common_report_header._set_context(self, data)

        # UF-1714
        # accounts 8*, 9* are not displayed:
        # we have to deduce debit/credit/balance amounts of MSF account view (root account)
        self._deduce_accounts = { 
            '8': {'debit': 0., 'credit': 0., 'balance': 0. },
            '9': {'debit': 0., 'credit': 0., 'balance': 0. },
        }
        a_obj = self.pool.get('account.account')
        for a_code in self._deduce_accounts:
            a_ids = a_obj.search(self.cr, self.uid, [('code', '=', a_code)])
            if a_ids:
                if isinstance(a_ids, (int, long)):
                    a_ids = [a_ids]
                account = a_obj.browse(self.cr, self.uid, a_ids, context=self.context)[0]
                if account:
                    self._deduce_accounts[a_code]['debit'] = self._sum_debit_account(account)
                    self._deduce_accounts[a_code]['credit'] = self._sum_credit_account(account)
                    self._deduce_accounts[a_code]['balance'] = self._sum_balance_account(account)
        
        return res

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        super(general_ledger, self).__init__(cr, uid, name, context=context)
        self.query = ""
        self.tot_currency = 0.0
        self.period_sql = ""
        self.sold_accounts = {}
        self.sortby = 'sort_date'
        self.localcontext.update({
            'time': time,
            'lines': self.lines,
            'sum_debit_account': self._sum_debit_account,
            'sum_credit_account': self._sum_credit_account,
            'sum_balance_account': self._sum_balance_account,
            'sum_currency_amount_account': self._sum_currency_amount_account,
            'get_children_accounts': self.get_children_accounts,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_account': self._get_account,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_filter': self._get_filter,
            'get_sortby': self._get_sortby,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_target_move': self._get_target_move,
            'get_output_currency_code': self._get_output_currency_code,
            'get_filter_info': self._get_filter_info,
            'get_line_debit': self._get_line_debit,
            'get_line_credit': self._get_line_credit,
            'get_line_balance': self._get_line_balance,
            'currency_conv': self._currency_conv,
            'get_prop_instances': self._get_prop_instances,
            'get_currencies': self.get_currencies,
        })
        
        # company currency
        self.uid = uid
        self.currency_id = False
        self.instance_id = False
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            self.currency_id = user[0].company_id.currency_id.id
            if user[0].company_id.instance_id:
                self.instance_id = user[0].company_id.instance_id.id
        if not self.currency_id:
            raise osv.except_osv(_('Error !'), _('Company has no default currency'))

        self.context = context

    def _sum_currency_amount_account(self, account):
        self.cr.execute('SELECT sum(l.amount_currency) AS tot_currency \
                FROM account_move_line l \
                WHERE l.account_id = %s AND %s' %(account.id, self.query))
        sum_currency = self.cr.fetchone()[0] or 0.0
        if self.init_balance:
            self.cr.execute('SELECT sum(l.amount_currency) AS tot_currency \
                            FROM account_move_line l \
                            WHERE l.account_id = %s AND %s '%(account.id, self.init_query))
            sum_currency += self.cr.fetchone()[0] or 0.0
        return sum_currency

    def get_currencies(self, account=False):
        res = []

        sql = """
            SELECT DISTINCT(l.currency_id)
            FROM account_move_line AS l
            WHERE %s
        """ % (self.query)
        if account:
            sql += " and l.account_id=%d" % (account.id, )
        self.cr.execute(sql)
        rows = self.cr.fetchall()
        if rows:
            rc_obj = self.pool.get('res.currency')
            ordered_ids = rc_obj.search(self.cr, self.uid, [
                ('id', 'in', [ r[0] for r in rows ]),
            ], order='name')
            res = rc_obj.browse(self.cr, self.uid, ordered_ids)

        return res

    def get_children_accounts(self, account, ccy=False):
        res = []
        currency_obj = self.pool.get('res.currency')
         
        ids_acc = self.pool.get('account.account')._get_children_and_consol(self.cr, self.uid, account.id)
        currency = account.currency_id and account.currency_id or account.company_id.currency_id
        for child_account in self.pool.get('account.account').browse(self.cr, self.uid, ids_acc, context=self.context):
            if child_account.code.startswith('8') or child_account.code.startswith('9'):
                # UF-1714: exclude accounts '8*'/'9*'
                continue
            sql = """
                SELECT count(id)
                FROM account_move_line AS l
                WHERE %s AND l.account_id = %%s
            """ % (self.query)
            if ccy:
                sql += " and l.currency_id = %d" % (ccy.id, )
            self.cr.execute(sql, (child_account.id,))
            num_entry = self.cr.fetchone()[0] or 0
            sold_account = self._sum_balance_account(child_account)
            self.sold_accounts[child_account.id] = sold_account
            if self.display_account == 'bal_movement':
                if child_account.type != 'view' and num_entry <> 0:
                    res.append(child_account)
            elif self.display_account == 'bal_solde':
                if child_account.type != 'view' and num_entry <> 0:
                    if not currency_obj.is_zero(self.cr, self.uid, currency, sold_account):
                        res.append(child_account)
            else:
                if not ccy or (ccy and num_entry > 0):
                    res.append(child_account)
        if not res:
            return [account]
        if self.account_ids:
            # filter by account
            res = [ a for a in res if a.id in self.account_ids ]
        return res

    def lines(self, account, ccy=False):
        """ Return all the account_move_line of account with their account code counterparts """
        if not self.show_move_lines:
            return []

        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted', '']
        # First compute all counterpart strings for every move_id where this account appear.
        # Currently, the counterpart info is used only in landscape mode
        sql = """
            SELECT m1.move_id,
                array_to_string(ARRAY(SELECT DISTINCT a.code
                                          FROM account_move_line m2
                                          LEFT JOIN account_account a ON (m2.account_id=a.id)
                                          WHERE m2.move_id = m1.move_id
                                          AND m2.account_id<>%%s), ', ') AS counterpart
                FROM (SELECT move_id
                        FROM account_move_line l
                        LEFT JOIN account_move am ON (am.id = l.move_id)
                        WHERE am.state IN %s and %s AND l.account_id = %%s GROUP BY move_id) m1
        """% (tuple(move_state), self.query)
        self.cr.execute(sql, (account.id, account.id))
        counterpart_res = self.cr.dictfetchall()
        counterpart_accounts = {}
        for i in counterpart_res:
            counterpart_accounts[i['move_id']] = i['counterpart']
        del counterpart_res

        # Then select all account_move_line of this account
        if self.sortby == 'sort_journal_partner':
            sql_sort='j.code, p.name, l.move_id'
        else:
            sql_sort='l.date, l.move_id'
        sql = """
            SELECT l.id AS lid, l.date AS ldate, j.code AS lcode, l.currency_id,l.amount_currency,l.ref AS lref, l.name AS lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, COALESCE(l.debit_currency,0) as debit_currency, COALESCE(l.credit_currency,0) as credit_currency, l.period_id AS lperiod_id, l.partner_id AS lpartner_id,
            m.name AS move_name, m.id AS mmove_id,per.code as period_code,
            c.symbol AS currency_code,
            i.id AS invoice_id, i.type AS invoice_type, i.number AS invoice_number,
            p.name AS partner_name
            FROM account_move_line l
            JOIN account_move m on (l.move_id=m.id)
            LEFT JOIN res_currency c on (l.currency_id=c.id)
            LEFT JOIN res_partner p on (l.partner_id=p.id)
            LEFT JOIN account_invoice i on (m.id =i.move_id)
            LEFT JOIN account_period per on (per.id=l.period_id)
            JOIN account_journal j on (l.journal_id=j.id)
            WHERE %s AND m.state IN %s AND l.account_id = %%s{ccy} ORDER by %s
        """ %(self.query, tuple(move_state), sql_sort)
        if ccy:
            ccy_pattern = " AND l.currency_id = %d" % (ccy.id, )
        else:
            ccy_pattern = ""
        sql = sql.replace('{ccy}', ccy_pattern)
        self.cr.execute(sql, (account.id,))
        res_lines = self.cr.dictfetchall()
        res_init = []
        if res_lines and self.init_balance:
            #FIXME: replace the label of lname with a string translatable
            sql = """
                SELECT 0 AS lid, '' AS ldate, '' AS lcode, COALESCE(SUM(l.amount_currency),0.0) AS amount_currency, '' AS lref, 'Initial Balance' AS lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit,COALESCE(SUM(l.debit_currency),0.0) AS debit_currency, COALESCE(SUM(l.credit_currency),0.0) AS credit_currency, '' AS lperiod_id, '' AS lpartner_id,
                '' AS move_name, '' AS mmove_id, '' AS period_code,
                '' AS currency_code,
                NULL AS currency_id,
                '' AS invoice_id, '' AS invoice_type, '' AS invoice_number,
                '' AS partner_name
                FROM account_move_line l
                LEFT JOIN account_move m on (l.move_id=m.id)
                LEFT JOIN res_currency c on (l.currency_id=c.id)
                LEFT JOIN res_partner p on (l.partner_id=p.id)
                LEFT JOIN account_invoice i on (m.id =i.move_id)
                JOIN account_journal j on (l.journal_id=j.id)
                WHERE %s AND m.state IN %s AND l.account_id = %%s
            """ %(self.init_query, tuple(move_state))
            if ccy:
                sql += ccy_pattern
            self.cr.execute(sql, (account.id,))
            res_init = self.cr.dictfetchall()
        res = res_init + res_lines
        account_sum = 0.0
        for l in res:
            l['move'] = l['move_name'] != '/' and l['move_name'] or ('*'+str(l['mmove_id']))
            l['partner'] = l['partner_name'] or ''
            account_sum += l['debit'] - l['credit']
            l['progress'] = account_sum
            l['line_corresp'] = l['mmove_id'] == '' and ' ' or counterpart_accounts[l['mmove_id']].replace(', ',',')
            # Modification of amount Currency
            if l['credit'] > 0:
                if l['amount_currency'] != None:
                    l['amount_currency'] = abs(l['amount_currency']) * -1
            if l['amount_currency'] != None:
                self.tot_currency = self.tot_currency + l['amount_currency']
        return res

    def _sum_debit_account(self, account, ccy=False):
        if ccy:
            ccy_pattern = " AND l.currency_id = %d" % (ccy.id, )
        else:
            ccy_pattern = ""

        if account.type == 'view':
            amount = account.debit
            if not account.parent_id:
                # UF-1714
                # accounts 8*, 9* are not displayed:
                # we have to deduce debit/credit/balance amounts of MSF account view (root account)
                for a_code in self._deduce_accounts:
                    amount -= self._deduce_accounts[a_code]['debit']
            return self._currency_conv(amount)
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted','']
        self.cr.execute('SELECT sum(debit) \
                FROM account_move_line l \
                JOIN account_move am ON (am.id = l.move_id) \
                WHERE (l.account_id = %s) \
                AND (am.state IN %s) \
                AND '+ self.query +' ' + ccy_pattern
                ,(account.id, tuple(move_state)))
        sum_debit = self.cr.fetchone()[0] or 0.0
        if self.init_balance:
            self.cr.execute('SELECT sum(debit) \
                    FROM account_move_line l \
                    JOIN account_move am ON (am.id = l.move_id) \
                    WHERE (l.account_id = %s) \
                    AND (am.state IN %s) \
                    AND '+ self.init_query +' ' + ccy_pattern
                    ,(account.id, tuple(move_state)))
            # Add initial balance to the result
            sum_debit += self.cr.fetchone()[0] or 0.0
        sum_debit = self._currency_conv(sum_debit)
        return sum_debit

    def _sum_credit_account(self, account, ccy=False):
        if ccy:
            ccy_pattern = " AND l.currency_id = %d" % (ccy.id, )
        else:
            ccy_pattern = ""

        if account.type == 'view':
            amount = account.credit
            if not account.parent_id:
                # UF-1714
                # accounts 8*, 9* are not displayed:
                # we have to deduce debit/credit/balance amounts of MSF account view (root account)
                for a_code in self._deduce_accounts:
                    amount -= self._deduce_accounts[a_code]['credit']
            return self._currency_conv(amount)
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted','']
        self.cr.execute('SELECT sum(credit) \
                FROM account_move_line l \
                JOIN account_move am ON (am.id = l.move_id) \
                WHERE (l.account_id = %s) \
                AND (am.state IN %s) \
                AND '+ self.query +' ' + ccy_pattern
                ,(account.id, tuple(move_state)))
        sum_credit = self.cr.fetchone()[0] or 0.0
        if self.init_balance:
            self.cr.execute('SELECT sum(credit) \
                    FROM account_move_line l \
                    JOIN account_move am ON (am.id = l.move_id) \
                    WHERE (l.account_id = %s) \
                    AND (am.state IN %s) \
                    AND '+ self.init_query +' ' + ccy_pattern
                    ,(account.id, tuple(move_state)))
            # Add initial balance to the result
            sum_credit += self.cr.fetchone()[0] or 0.0
        sum_credit = self._currency_conv(sum_credit)
        return sum_credit

    def _sum_balance_account(self, account, ccy=False):
        if ccy:
            ccy_pattern = " AND l.currency_id = %d" % (ccy.id, )
        else:
            ccy_pattern = ""

        if account.type == 'view':
            amount = account.balance
            if not account.parent_id:
                # UF-1714
                # accounts 8*, 9* are not displayed:
                # we have to deduce debit/credit/balance amounts of MSF account view (root account)
                for a_code in self._deduce_accounts:
                    amount -= self._deduce_accounts[a_code]['balance']
            return self._currency_conv(amount)
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted','']
        self.cr.execute('SELECT (sum(debit) - sum(credit)) as tot_balance \
                FROM account_move_line l \
                JOIN account_move am ON (am.id = l.move_id) \
                WHERE (l.account_id = %s) \
                AND (am.state IN %s) \
                AND '+ self.query +' ' + ccy_pattern
                ,(account.id, tuple(move_state)))
        sum_balance = self.cr.fetchone()[0] or 0.0
        if self.init_balance:
            self.cr.execute('SELECT (sum(debit) - sum(credit)) as tot_balance \
                    FROM account_move_line l \
                    JOIN account_move am ON (am.id = l.move_id) \
                    WHERE (l.account_id = %s) \
                    AND (am.state IN %s) \
                    AND '+ self.init_query +' ' + ccy_pattern
                    ,(account.id, tuple(move_state)))
            # Add initial balance to the result
            sum_balance += self.cr.fetchone()[0] or 0.0
        sum_balance = self._currency_conv(sum_balance)
        return sum_balance

    def _get_account(self, data):
        if data['model'] == 'account.account':
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['id'], context=self.context).company_id.name
        return super(general_ledger ,self)._get_account(data)

    def _get_sortby(self, data):
        if self.sortby == 'sort_date':
            return 'Date'
        elif self.sortby == 'sort_journal_partner':
            return 'Journal & Partner'
        return 'Date'
        
    def _get_output_currency_code(self, data):
        if not self.output_currency_code:
            return ''
        return self.output_currency_code
        
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
        
    def _get_line_debit(self, line):
        return self._currency_conv(line['debit'])
        
    def _get_line_credit(self, line):
        return self._currency_conv(line['credit'])
        
    def _get_line_balance(self, line):
        return self._currency_conv(line['debit'] - line['credit'])
        
    def _is_company_currency(self):
        if not self.output_currency_id or not self.currency_id \
           or self.output_currency_id == self.currency_id:
            # ouput currency == company currency
            return True
        else:
            # is other currency
            return False
        
    def _currency_conv(self, amount):
        if not amount or amount == 0.:
            return amount
        if self._is_company_currency():
            return amount
        amount = self.pool.get('res.currency').compute(self.cr, self.uid,
                                                self.currency_id,
                                                self.output_currency_id,
                                                amount)
        if not amount:
            amount = 0.
        return amount
        
    def _get_prop_instances(self, data):
        instances = []
        if data.get('form', False) \
            and data['form'].get('display_details', False):
            self.cr.execute('select code from msf_instance where id IN %s',
                (tuple(data['form']['instance_ids']),))
            instances = [x for x, in self.cr.fetchall()]
        return instances

    # internal filter functions
    def _get_data_form(self, data, key):
        return data.get('form', False) \
            and data['form'].get(key, False) or False
                                            
report_sxw.report_sxw('report.account.general.ledger', 'account.account', 'addons/account/report/account_general_ledger.rml', parser=general_ledger, header='internal')
report_sxw.report_sxw('report.account.general.ledger_landscape', 'account.account', 'addons/account/report/account_general_ledger_landscape.rml', parser=general_ledger, header='internal landscape')

report_sxw.report_sxw('report.account.general.ledger.ccy', 'account.account', 'addons/account/report/account_general_ledger_ccy.rml', parser=general_ledger, header='internal')
report_sxw.report_sxw('report.account.general.ledger.ccy_landscape', 'account.account', 'addons/account/report/account_general_ledger_ccy_landscape.rml', parser=general_ledger, header='internal landscape')


class general_ledger_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(general_ledger_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        #ids = getIds(self, cr, uid, ids, context)
        a = super(general_ledger_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
general_ledger_xls('report.account.general.ledger_xls', 'account.account', 'addons/account/report/account_general_ledger_xls.mako', parser=general_ledger, header='internal')
general_ledger_xls('report.account.general.ledger.ccy_xls', 'account.account', 'addons/account/report/account_general_ledger_ccy_xls.mako', parser=general_ledger, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
