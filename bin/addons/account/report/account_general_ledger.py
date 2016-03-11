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
        used_context = data['form'].get('used_context',{})
        self.query = obj_move._query_get(self.cr, self.uid, obj='l', context=used_context)
        ctx2 = data['form'].get('used_context',{}).copy()
        #ctx2.update({'initial_bal': True})
        ctx2.update({'period0': 1, 'show_period_0': 1, 'state_agnostic': 1, })
        if 'chart_account_id' in ctx2:
            del ctx2['chart_account_id']  # US-822: IB period 0 journals entries
        if 'journal_ids' in ctx2:
            del ctx2['journal_ids']  # US-822: IB period 0 journals entries
        self.init_query = obj_move._query_get(self.cr, self.uid, obj='l', context=ctx2)
        self.init_balance = data['form']['initial_balance']
        self.display_account = data['form']['display_account']
        self.target_move = data['form'].get('target_move', 'all')
        self.account_report_types = self._get_data_form(data, 'account_type')
        if self.account_report_types:
            # convert wizard selection to account.account.type 'report_type'
            if self.account_report_types == 'pl':
                self.account_report_types = [ 'income', 'expense', ]
            elif self.account_report_types == 'bl':
                self.account_report_types = [ 'asset', 'liability', ]
            else:  # all
                self.account_report_types = False

        # settings regarding report mode
        # default general ledger mode
        self.show_move_lines = True
        self.title = _('General Ledger')
        if 'report_mode' in data['form']:
            if data['form']['report_mode'] == 'tb':
                # trial balance mode
                self.show_move_lines = False
                self.title = _('Trial Balance')

        self.account_ids = self._get_data_form(data, 'account_ids')

        # US-334/6: Only account 10100 and 10200 must never be displayed in \
        # details when you tick "Unreconciled" because they are the only \
        # account not reconciliable.
        a_obj = self.pool.get('account.account')
        self.unreconciled_filter = self._get_data_form(data, 'unreconciled', False)
        if self.unreconciled_filter:
            self.unreconciliable_accounts = a_obj.search(self.cr, self.uid, [
                    ('reconcile', '=', False),
                    ('type', '=', 'liquidity'),
                ], context=self.context)
        else:
            self.unreconciliable_accounts = []

        self.context['state'] = data['form']['target_move']

        if 'instance_ids' in data['form']:
            self.context['instance_ids'] = data['form']['instance_ids']
        if (data['model'] == 'ir.ui.menu'):
            new_ids = [data['form']['chart_account_id']]
            objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids, context=self.context)
        
        # output currency
        self.output_currency_id = 'output_currency' in data['form'] \
            and data['form']['output_currency']
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

        # UF-1714 accounts 8*, 9* are not displayed:
        # have to deduce 8/9 balance amounts to MSF account view (root account)
        deduce_accounts_index = [ '8', '9', ]
        self._deduce_accounts_data = {
            'debit': 0., 'credit': 0., 'balance': 0.,
        }
        if deduce_accounts_index:
            # compute to deduce amount without any journals filtering
            # (by default ikd entries filtered and typically in 8/9 accounts)
            deduce_accounts_ctx = used_context.copy()
            if 'journal_ids' in deduce_accounts_ctx:
                del deduce_accounts_ctx['journal_ids']

            a_ids = a_obj.search(self.cr, self.uid,
                [('code', 'in', [ c for c in deduce_accounts_index ])],
                context=deduce_accounts_ctx)
            if a_ids:
                for account in a_obj.browse(self.cr, self.uid, a_ids,
                    context=deduce_accounts_ctx):
                    self._deduce_accounts_data['debit'] += account.debit
                    self._deduce_accounts_data['credit'] += account.credit
                    self._deduce_accounts_data['balance'] += \
                        account.debit - account.credit

        if self.account_ids:
            # add parent(s) of filtered accounts
            self.account_ids += self.pool.get('account.account')._get_parent_of(
                    self.cr, self.uid, self.account_ids)
        
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
            'get_journals_str': self._get_journals_str,
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
            'get_currencies_account_subtotals': \
                self.get_currencies_account_subtotals,
            'get_display_info': self._get_display_info,
            'get_show_move_lines': self.get_show_move_lines,
            'get_ccy_label': self.get_ccy_label,
            'get_title': self._get_title,
            'get_initial_balance': self._get_initial_balance,
        })
        
        # company currency
        self.uid = uid
        self.currency_id = False
        self.currency_name = ''
        self.instance_id = False
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            self.currency_id = user[0].company_id.currency_id.id
            self.currency_name = user[0].company_id.currency_id and user[0].company_id.currency_id.name or ''
            if user[0].company_id.instance_id:
                self.instance_id = user[0].company_id.instance_id.id
        if not self.currency_id:
            raise osv.except_osv(_('Error !'), _('Company has no default currency'))

        self.context = context

    def _sum_currency_amount_account(self, account):
        reconcile_pattern = self.unreconciled_filter and \
            " AND reconcile_id is null" or ''

        sql = 'SELECT sum(l.amount_currency) AS tot_currency \
            FROM account_move_line l \
            WHERE l.account_id = %s AND %s' + reconcile_pattern
        self.cr.execute(sql % (account.id, self.query, ))
        sum_currency = self.cr.fetchone()[0] or 0.0

        return sum_currency

    def _get_journals_str(self, data):
        if 'all_journals' in data['form']:
            return _('All Journals')
        return ', '.join(self._get_journal(data))

    def get_currencies(self, account=False, include_with_ib=False):
        res = []

        sql = """
            SELECT DISTINCT(l.currency_id)
            FROM account_move_line AS l
            WHERE %s
        """ % (self.query)
        if account:
            sql += " and l.account_id=%d" % (account.id, )
        self.cr.execute(sql)
        rows = self.cr.fetchall() or []

        if include_with_ib and self.init_balance:
            sql = """
                SELECT DISTINCT(l.currency_id)
                FROM account_move_line AS l
            WHERE %s
            """ % (self.init_query)
            if account:
                sql += " and l.account_id=%d" % (account.id, )
            self.cr.execute(sql)
            ib_rows = self.cr.fetchall() or []
            if ib_rows:
                rows += ib_rows
                rows = list(set(rows))

        if rows:
            rc_obj = self.pool.get('res.currency')
            ordered_ids = rc_obj.search(self.cr, self.uid, [
                ('id', 'in', [ r[0] for r in rows ]),
            ], order='name')
            res = rc_obj.browse(self.cr, self.uid, ordered_ids)

        return res

    def get_currencies_account_subtotals(self, account):
        ccy_brs = self.get_currencies(account=account, include_with_ib=True)
        res = []

        if ccy_brs:
            for ccy in ccy_brs:
                line = {
                    'account_code': account and account.code or '',
                    'ccy_name': ccy.name or ccy.code or '',
                    'debit': self._sum_debit_account(account, ccy=ccy,
                        booking=True, is_sub_total=True),
                    'credit': self._sum_credit_account(account, ccy=ccy,
                        booking=True, is_sub_total=True),
                    'bal': self._sum_balance_account(account, ccy=ccy,
                        booking=True, is_sub_total=True),
                }
                # append the line if amount (and compute functional bal)
                if line['debit'] or line['credit'] or line['bal']:
                    line['bal_func'] = self._sum_balance_account(account,
                        ccy=ccy, booking=False, is_sub_total=True),
                    res.append(line)
        return res

    def get_children_accounts(self, account, ccy=False):
        res = []
        currency_obj = self.pool.get('res.currency')
        account_obj = self.pool.get('account.account')

        # force the context to financial_report=True
        # this make possible not to consider the accounts that are marked (or
        # their parents) as display_in_reports=False
        context = {'financial_report': True}
        ids_acc = account_obj._get_children_and_consol(self.cr,
                self.uid, account.id, context=context)
        currency = account.currency_id and account.currency_id or account.company_id.currency_id
        for child_account in self.pool.get('account.account').browse(self.cr, self.uid, ids_acc, context=self.context):
            if self.account_report_types:
                # filter by B/S P&L report type
                if child_account.user_type \
                    and child_account.user_type.report_type \
                    and child_account.user_type.report_type \
                        not in self.account_report_types:
                    continue
            if self.unreconciled_filter:
                if child_account.id in self.unreconciliable_accounts:
                    # unreconciliable filter:
                    # do not display unreciliable account
                    continue
            if self.account_ids and child_account.id not in self.account_ids:
                    continue  # filtered account

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

        return res or [account]

    def lines(self, account, initial_balance_mode=False):
        res = []
        if not self.show_move_lines and not initial_balance_mode:
            # trial balance: do not show lines except initial_balance_mode ones
            return res

        if not initial_balance_mode:
            move_state_in = "('posted')" if self.target_move == 'posted' \
                else "('draft', 'posted')"

            # First compute all counterpart strings for every move_id where this account appear.
            # Currently, the counterpart info is used only in landscape mode
            # => desactivated since US-334
            '''
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
            del counterpart_res'''
            # Then select all account_move_line of this account

            if self.sortby == 'sort_journal_partner':
                sql_sort='j.code, p.name, l.move_id'
            else:
                sql_sort='l.date, l.move_id'
            sql = """
                SELECT l.id AS lid, l.date AS ldate, j.code AS lcode, l.currency_id,
                l.amount_currency,l.ref AS lref, l.name AS lname,
                COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit,
                COALESCE(l.debit_currency,0) as debit_currency,
                COALESCE(l.credit_currency,0) as credit_currency,
                l.period_id AS lperiod_id, l.partner_id AS lpartner_id,
                m.name AS move_name, m.id AS mmove_id,per.code as period_code,
                c.symbol AS currency_code,
                i.id AS invoice_id, i.type AS invoice_type,
                i.number AS invoice_number,
                p.name AS partner_name, c.name as currency_name
                FROM account_move_line l
                JOIN account_move m on (l.move_id=m.id)
                LEFT JOIN res_currency c on (l.currency_id=c.id)
                LEFT JOIN res_partner p on (l.partner_id=p.id)
                LEFT JOIN account_invoice i on (m.id =i.move_id)
                LEFT JOIN account_period per on (per.id=l.period_id)
                LEFT JOIN account_account ac on (ac.id=l.account_id)
                JOIN account_journal j on (l.journal_id=j.id)
                WHERE %s AND m.state IN %s AND l.account_id = %%s{{reconcile}} ORDER by %s
            """ %(self.query, move_state_in, sql_sort)
            sql = sql.replace('{{reconcile}}',
                    self.unreconciled_filter and \
                        " AND reconcile_id is null and ac.reconcile ='t'" or '')
            self.cr.execute(sql, (account.id, ))
            res = self.cr.dictfetchall()
        else:
            if self.init_balance:
                # US-822: move lines for period 0 IB journal
                sql_sort = 'l.move_id'
                sql = """
                    SELECT l.id AS lid, l.date AS ldate, j.code AS lcode, l.currency_id,
                    l.amount_currency,l.ref AS lref, l.name AS lname,
                    COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit,
                    COALESCE(l.debit_currency,0) as debit_currency,
                    COALESCE(l.credit_currency,0) as credit_currency,
                    l.period_id AS lperiod_id, '' AS lpartner_id,
                    m.name AS move_name, m.id AS mmove_id,
                    per.code as period_code, c.symbol AS currency_code,
                    '' AS invoice_id, '' invoice_type,
                    '' AS invoice_number,
                    '' AS partner_name, c.name as currency_name
                    FROM account_move_line l
                    JOIN account_move m on (l.move_id=m.id)
                    LEFT JOIN res_currency c on (l.currency_id=c.id)
                    LEFT JOIN res_partner p on (l.partner_id=p.id)
                    LEFT JOIN account_period per on (per.id=l.period_id)
                    LEFT JOIN account_account ac on (ac.id=l.account_id)
                        JOIN account_journal j on (l.journal_id=j.id)
                    WHERE %s AND l.account_id = %%s and per.number = 0 ORDER by %s
                """ % (self.init_query, sql_sort, )
                self.cr.execute(sql, (account.id, ))
                res = self.cr.dictfetchall()

        if res:
            account_sum = 0.0
            for l in res:
                l['move'] = l['move_name'] != '/' and l['move_name'] or ('*'+str(l['mmove_id']))
                l['partner'] = l['partner_name'] or ''
                account_sum += l['debit'] - l['credit']
                l['progress'] = account_sum
                # counter part desactivated since us 354
                # l['line_corresp'] = l['mmove_id'] == '' and ' ' or counterpart_accounts[l['mmove_id']].replace(', ',',')
                # Modification of amount Currency
                if l['credit'] > 0:
                    if l['amount_currency'] != None:
                        l['amount_currency'] = abs(l['amount_currency']) * -1
                if l['amount_currency'] != None:
                    self.tot_currency = self.tot_currency + l['amount_currency']
        return res

    def __sum_amount_account_check_view(self, account, field, ccy=False):
        """
        :return : (is_view, amount, )
        """
        def compute_initial_balance():
            # drill child accounts entries (always fonctional ccy)
            aa_obj = self.pool.get('account.account')
            account_ids = aa_obj._get_children_and_consol(self.cr, self.uid,
                [account.id])
            if not account_ids:
                return 0.

            move_state = [ 'posted', ] if self.target_move == 'posted' \
                else [ 'draft', 'posted', ]
            if field == 'balance':
                sum_expr = '(sum(l.debit) - sum(l.credit))'
            else:
                sum_expr = 'sum(l.{field})'.replace('{field}', field)
            sql = 'SELECT {sum}' \
                ' FROM account_move_line l' \
                ' JOIN account_move am ON am.id = l.move_id' \
                ' LEFT JOIN account_period per ON per.id = l.period_id' \
                ' WHERE per.number = 0' \
                ' AND am.state in %s AND l.account_id in %s'
            sql = sql.replace('{sum}', sum_expr)
            self.cr.execute(sql, (tuple(move_state), tuple(account_ids), ))

            return self.cr.fetchone()[0] or 0.

        if account.type == 'view':
            account._context.update({'financial_report':True})
            amount = getattr(account, field)
            if not account.parent_id:
                # MSF CoA root: deduce balance of not displayed accounts
                if field in self._deduce_accounts_data:
                    amount = amount - self._deduce_accounts_data[field]
            if not ccy and self.init_balance:
                # all views: include the optional initial balance of IB period 0
                # entries
                amount += compute_initial_balance()
            return True, self._currency_conv(amount)

        return False, 0.

    def __sum_amount_account(self, account, move_state, mode,
            ccy=False, booking=False, initial_balance=False):
        if mode == 'debit':
            field = 'sum(debit{booking})'
        elif mode == 'credit':
            field = 'sum(credit{booking})'
        elif mode == 'balance':
            field = '(sum(debit{booking}) - sum(credit{booking}))'
        else:
            raise osv.except_osv(_('Error'), _('Mode not supported'))

        if ccy:
            ccy_pattern = " AND l.currency_id = %d" % (ccy.id, )
        else:
            ccy_pattern = ""
        reconcile_pattern = self.unreconciled_filter and \
            " AND reconcile_id is null" or ''

        sql = 'SELECT {field} \
            FROM account_move_line l \
            JOIN account_move am ON (am.id = l.move_id) \
            WHERE (l.account_id = %s) \
            AND (am.state IN %s) \
            AND ' + self.query + ' ' + ccy_pattern + reconcile_pattern
        sql = sql.replace('{field}', field).replace(
            '{booking}', '_currency' if booking else '')

        self.cr.execute(sql, (account.id, tuple(move_state), ))
        res = self.cr.fetchone()[0] or 0.0

        if initial_balance:
            # US-822 include inital balance at ccy subtotal line level
            sql = 'SELECT {field} \
            FROM account_move_line l \
            JOIN account_move am ON (am.id = l.move_id) \
            LEFT JOIN account_period per ON (per.id = l.period_id) \
            WHERE (l.account_id = %s) and per.number = 0 \
            AND ' + self.init_query + ' ' + ccy_pattern
            sql = sql.replace('{field}', field).replace(
            '{booking}', '_currency' if booking else '')
            self.cr.execute(sql, (account.id, ))
            res += self.cr.fetchone()[0] or 0.0

        return res

    def _sum_debit_account(self, account, ccy=False, booking=False,
        is_sub_total=False):
        """
        :param ccy: filter ccy entries
        :param booking: not applicable for view accounts (used for account total lines
        by ccy)
        :param is_sub_total: is a sub total line ? (per ccy)
        """
        is_view, amount = self.__sum_amount_account_check_view(account,
            'debit', ccy=ccy)
        if is_view:
            return amount

        move_state = [ 'posted', ] if self.target_move == 'posted' \
            else [ 'draft', 'posted', ]

        initial_balance = False
        if self.init_balance:
            if booking:
                initial_balance = is_sub_total and ccy or False
            else:
                initial_balance = not is_sub_total
        amount = self.__sum_amount_account(account, move_state, 'debit',
            ccy=ccy, booking=booking, initial_balance=initial_balance)
        return self._currency_conv(amount)

    def _sum_credit_account(self, account, ccy=False, booking=False,
        is_sub_total=False):
        """
        :param ccy: filter ccy entries
        :param booking: not applicable for view accounts (used for account total lines
        by ccy)
        :param is_sub_total: is a sub total line ? (per ccy)
        """
        is_view, amount = self.__sum_amount_account_check_view(account,
            'credit', ccy=ccy)
        if is_view:
            return amount

        move_state = [ 'posted', ] if self.target_move == 'posted' \
            else [ 'draft', 'posted', ]

        initial_balance = False
        if self.init_balance:
            if booking:
                initial_balance = is_sub_total and ccy or False
            else:
                initial_balance = not is_sub_total
        amount = self.__sum_amount_account(account, move_state, 'credit',
            ccy=ccy, booking=booking, initial_balance=initial_balance)
        return self._currency_conv(amount)

    def _sum_balance_account(self, account, ccy=False, booking=False,
        is_sub_total=False):
        """
        :param ccy: filter ccy entries
        :param booking: not applicable for view accounts (used for account total lines
        by ccy)
        :param is_sub_total: is a sub total line ? (per ccy)
        """
        is_view, amount = self.__sum_amount_account_check_view(account,
            'balance', ccy=ccy)
        if is_view:
            return amount

        if ccy:
            ccy_pattern = " AND l.currency_id = %d" % (ccy.id, )
        else:
            ccy_pattern = ""

        move_state = [ 'posted', ] if self.target_move == 'posted' \
            else [ 'draft', 'posted', ]

        # add initial balance if ticked in wizard and booking subtotal
        # amount or any functional amount
        initial_balance = self.init_balance and (
            (booking and is_sub_total and ccy) or True) or False
        amount = self.__sum_amount_account(account, move_state, 'balance',
            ccy=ccy, booking=booking, initial_balance=initial_balance)
        return self._currency_conv(amount)

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
        return self.output_currency_code or self.currency_name
        
    def _get_filter_info(self, data):
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
            if data['form']['filter'] in ('filter_date', 'filter_date_doc', ):
                line = _('Posting') if data['form']['filter'] == 'filter_date' else _('Document')
                line += " %s " % (_('Date'), )
                line += self.formatLang(self._get_start_date(data), date=True) + ' - ' + self.formatLang(self._get_end_date(data), date=True)
            elif data['form']['filter'] == 'filter_period':
                line = self.get_start_period(data) + ' - ' + self.get_end_period(data)
            if line:
                infos.append(line)

        return infos and ", \n".join(infos) or ''
        
    def _get_line_debit(self, line, booking=False):
        return self.__get_line_amount(line, 'debit', booking=booking)
        
    def _get_line_credit(self, line, booking=False):
        return self.__get_line_amount(line, 'credit', booking=booking)
        
    def _get_line_balance(self, line, booking=False):
        return self._currency_conv(
            self.__get_line_amount(line, 'debit', booking=booking, conv=False) \
            - self.__get_line_amount(line, 'credit', booking=booking, conv=False)
        )

    def __get_line_amount(self, line, key, booking=False, conv=True):
        if booking:
            key += '_currency'
        return (self._currency_conv(line[key]) if conv else line[key]) or 0.
        
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
            return 0.
        if not self._is_company_currency():
            amount = self.pool.get('res.currency').compute(self.cr, self.uid,
                self.currency_id, self.output_currency_id, amount)
        if not amount or abs(amount) < 0.001:
            amount = 0.
        return amount
        
    def _get_prop_instances(self, data):
        instances = []
        if data.get('form', False):
            if data['form'].get('instance_ids', False):
                self.cr.execute('select code from msf_instance where id IN %s',
                    (tuple(data['form']['instance_ids']),))
            else:
                self.cr.execute('select code from msf_instance',
                    (tuple(data['form']['instance_ids']),))
            instances = [x for x, in self.cr.fetchall()]
        return ', '.join(instances)

    # internal filter functions
    def _get_data_form(self, data, key, default=False):
        if not 'form' in data or not key in data['form']:
            return default
        return data['form'].get(key, default)

    def _get_display_info(self, data):
        info_data = []
        yes_str = _('Yes')
        no_str = _('No')
        all_str = _('All')

        # account type
        ac = all_str
        if data['form'].get('account_type'):
            if data['form'].get('account_type') == 'pl':
                ac = _('Profit & Loss')
            elif data['form'].get('account_type') == 'bl':
                ac = _('Balance Sheet')
        info_data.append((_('Account Type'), ac, ))

        # reconciled account
        info_data.append((_('Unreconciled'),
            self.unreconciled_filter and yes_str or no_str, ))

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

    def get_show_move_lines(self):
        return self.show_move_lines

    def get_ccy_label(self, short_version=False):
        return short_version and _('CUR') or _('Currency')

    def _get_title(self):
        if hasattr(self, 'title'):
            return self.title or ''
        return ''

    def _get_initial_balance(self):
        return self.init_balance
                                            
#report_sxw.report_sxw('report.account.general.ledger', 'account.account', 'addons/account/report/account_general_ledger.rml', parser=general_ledger, header='internal')
report_sxw.report_sxw('report.account.general.ledger_landscape', 'account.account', 'addons/account/report/account_general_ledger_landscape.rml', parser=general_ledger, header='internal landscape')
report_sxw.report_sxw('report.account.general.ledger_landscape_tb', 'account.account', 'addons/account/report/account_general_ledger_landscape.rml', parser=general_ledger, header='internal landscape')


class general_ledger_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(general_ledger_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        #ids = getIds(self, cr, uid, ids, context)
        a = super(general_ledger_xls, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')

general_ledger_xls('report.account.general.ledger_xls', 'account.account', 'addons/account/report/account_general_ledger_xls.mako', parser=general_ledger, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
