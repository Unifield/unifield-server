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
from .common_report_header import common_report_header
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from osv import osv
from tools.translate import _


class general_ledger(report_sxw.rml_parse, common_report_header):
    _name = 'report.account.general.ledger'

    def set_context(self, objects, data, ids, report_type=None):
        new_ids = ids
        obj_move = self.pool.get('account.move.line')

        # local context AND move line _query_get call
        self.sortby = data['form'].get('sortby', 'sort_date')
        used_context = data['form'].get('used_context',{})
        if data.get('context', False):
            used_context['lang'] = data['context'].get('lang', 'en_MF')
        if not data['form'].get('fiscalyear_id', False):
            used_context['all_fiscalyear'] = True
            used_context['report_cross_fy'] = True
            data['form']['initial_balance'] = False  # IB not applicable
        used_context['rev_journal_ids'] = self._get_data_form(data, 'rev_journal_ids', default=False)
        self.query = obj_move._query_get(self.cr, self.uid, obj='l',
                                         context=used_context)

        # IB entries query
        self.init_balance = data['form']['initial_balance']
        if self.init_balance:
            ib_local_context = data['form'].get('used_context',{}).copy()
            if 'chart_account_id' in ib_local_context:
                del ib_local_context['chart_account_id']  # US-822: IB period 0 journals entries
            if 'journal_ids' in ib_local_context:
                del ib_local_context['journal_ids']  # US-822: IB period 0 journals entries

            ib_local_context.update({
                'period0': 1,
                'show_period_0': 1,
                'state_agnostic': 1,
            })
            # US-1197/4: IB entries for yearly closing always in 1th Jan
            # => get rid of regular period/dates filters for _query_get
            # => if self.init_balance is True, note that filtering is OK
            # validated at wizard report level
            ib_local_context.update({
                'date_from': False,
                'date_to': False,
                'date_fromto_docdate': False,
                'period_from': False,
                'period_to': False,
                'periods': False,
            })
            self.init_query = obj_move._query_get(self.cr, self.uid, obj='l',
                                                  context=ib_local_context)
        else:
            self.init_query = False

        # form params

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

        # default general ledger mode else trial balance
        self.show_move_lines = True
        self.title = _('General Ledger')
        if 'report_mode' in data['form']:
            if data['form']['report_mode'] == 'tb':
                # trial balance mode
                self.show_move_lines = False
                self.title = _('Trial Balance')

        self.account_ids = self._get_data_form(data, 'account_ids') or []
        # reverse the selection in case "Exclude account selection" has been ticked
        self.exclude_all_acc = False  # note: in case all accounts are selected and excluded, the report behaves as if no acc. had been selected
        if self.account_ids and self._get_data_form(data, 'rev_account_ids', default=False):
            rev_account_sql = """
                SELECT id
                FROM account_account
                WHERE type != 'view' AND id NOT IN %s;
            """
            self.cr.execute(rev_account_sql, (tuple(self.account_ids),))
            self.account_ids = [x[0] for x in self.cr.fetchall()]
            if not self.account_ids:
                self.exclude_all_acc = True
        # US-533 reconciled filter:
        # decision matrix
        # http://jira.unifield.org/browse/US-533?focusedCommentId=50246&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-50246
        reconcile_date = self._get_data_form(data, 'reconcile_date', False)
        reconciled = self._get_data_form(data, 'reconciled', 'empty')
        self.reconciled_filter = ''
        if reconciled == 'empty':
            # no reconcile criteria: get rid of reconcile date filter
            if reconcile_date:
                del data['form']['reconcile_date']
                reconcile_date = False
        elif reconciled == 'no':
            # reconcile 'No' filter: become reconciled since (day+1)
            # or not reconciled (cases 6/9 of Jira comment matrix)
            not_reconciled = "l.reconcile_id is null AND a.reconcile='t'"
            if reconcile_date:
                self.reconciled_filter = \
                    " AND (l.reconcile_date > '%s' or (%s))" % (
                        reconcile_date, not_reconciled, )
            else:
                self.reconciled_filter = " AND %s" % (not_reconciled, )
        elif reconciled == 'yes':
            self.reconciled_filter = " AND l.reconcile_id is not null"
            if reconcile_date:
                self.reconciled_filter += " AND l.reconcile_date <= '%s'" % (
                    reconcile_date, )

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
            if self.init_balance:
                if not self.init_query:
                    self.init_query = instance_ids_in
                else:
                    self.init_query += ' AND ' + instance_ids_in
        # selected instance ids display / filtering in journal:
        # - mission if no instance selected (<=> no instance filter in query)
        # - user selected instances
        self.selected_instance_ids = self.instance_ids or \
            self._get_instances(get_code=False, mission_filter=True) or []

        res = super(general_ledger, self).set_context(objects, data, new_ids, report_type=report_type)
        common_report_header._set_context(self, data)
        if self.account_ids:
            # add parent(s) of filtered accounts
            self.account_ids += self.pool.get('account.account')._get_parent_of(
                self.cr, self.uid, self.account_ids)

        # "Open Items at" filter
        if data['form'].get('open_items'):
            aml_ids = obj_move.search(self.cr, self.uid, [('open_items', '=', data['form']['open_items'])],
                                      order='NO_ORDER', context=self.context) or [0]
            self.query += " AND l.id in(%s) " % (",".join(map(str, aml_ids)))

        query = self.query
        if self.reconciled_filter:
            query += self.reconciled_filter
        if self.target_move == 'posted':
            query += " AND am.state = 'posted' "
        else:
            query += " AND am.state in ('draft', 'posted') "

        self._drill = self.pool.get("account.drill").build_tree(self.cr,
                                                                self.uid, query, self.init_query,
                                                                include_accounts=self.account_ids,
                                                                account_report_types=self.account_report_types,
                                                                with_balance_only=self.display_account == 'bal_solde',
                                                                reconcile_filter=self.reconciled_filter,
                                                                context=used_context)

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
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_journals_str': self._get_journals_str,
            'get_account': self._get_account,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_filter': self._get_filter,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_target_move': self._get_target_move,
            'get_output_currency_code': self._get_output_currency_code,
            'get_filter_info': self._get_filter_info,
            'get_line_debit': self._get_line_debit,
            'get_line_credit': self._get_line_credit,
            'get_line_balance': self._get_line_balance,
            'currency_conv': self._currency_conv,
            'get_prop_instances': self._get_prop_instances_str,
            'get_display_info': self._get_display_info,
            'get_open_items_selection': self._get_open_items_selection,
            'get_show_move_lines': self.get_show_move_lines,
            'get_ccy_label': self.get_ccy_label,
            'get_title': self._get_title,
            'get_initial_balance': self._get_initial_balance,
            'get_tree_nodes': self._get_tree_nodes,
            'show_node_in_report': self._show_node_in_report,
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
        self._drill = None

    def _get_tree_nodes(self, account):
        res = []
        node = self._drill.next_node()
        while node:
            res.append(node)
            node = self._drill.next_node()
        return res

    def _show_node_in_report(self, node):
        node.displayed = True
        if node.parent is None:
            return node.displayed  # always show root account MSF

        if node.is_zero \
                and (self.account_ids
                     or self.account_report_types
                     or self.reconciled_filter
                     or self.display_account == 'bal_movement'):
            # hide zero amounts for above filters on
            # no movements <=> no amount
            node.displayed = False

        if node.displayed \
                and node.is_zero_bal and self.display_account == 'bal_solde':
            # to filter zero balance
            node.displayed = False

        return node.displayed

    def lines(self, node, initial_balance_mode=False):
        """ display final account node entries (JIs)"""
        res = []
        #if not node.is_move_level:
        #    return res

        if not self.show_move_lines and not initial_balance_mode:
            # trial balance: do not show lines except initial_balance_mode ones
            return res
        if self.display_account == 'bal_solde' and node.is_zero_bal:
            # balance filter: do not display JIs of a zero balance account
            return res
        if self.display_account == 'bal_movement' and node.is_zero:
            # - do not display with no movement
            return res
        account = node.obj

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

            if self.sortby == 'sort_third_party':
                sql_sort = 'l.partner_txt NULLS first, l.move_id'
            elif self.sortby == 'sort_currency':
                sql_sort = 'c.name, l.move_id'
            elif self.sortby == 'sort_reconcile':
                sql_sort = 'l.reconcile_txt NULLS first, l.move_id'
            else:  # sort_date by default
                sql_sort = 'l.date, l.move_id'
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
                p.name AS partner_name, c.name as currency_name, l.partner_txt as third_party, l.reconcile_txt
                FROM account_move_line l
                JOIN account_move m on (l.move_id=m.id)
                LEFT JOIN res_currency c on (l.currency_id=c.id)
                LEFT JOIN res_partner p on (l.partner_id=p.id)
                LEFT JOIN account_invoice i on (m.id =i.move_id)
                LEFT JOIN account_period per on (per.id=l.period_id)
                JOIN account_journal j on (l.journal_id=j.id)
                JOIN account_account a on (a.id=l.account_id)
                WHERE %s AND m.state IN %s AND l.account_id = %%s{{reconcile}} ORDER by %s
            """ %(self.query, move_state_in, sql_sort)
            sql = sql.replace('{{reconcile}}', self.reconciled_filter)
            self.cr.execute(sql, (account.id, ))
            res = self.cr.dictfetchall()
        else:
            if self.init_balance:
                # US-822: move lines for period 0 IB journal
                sql_sort = 'l.move_id'
                if self.sortby == 'sort_currency':  # also sort by currency in case the related option is selected
                    sql_sort = 'c.name, l.move_id'
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
                    '' AS partner_name, c.name as currency_name, l.reconcile_txt
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

    def _get_account(self, data):
        if data['model'] == 'account.account':
            return self.pool.get('account.account').browse(self.cr, self.uid, data['form']['id'], context=self.context).company_id.name
        return super(general_ledger ,self)._get_account(data)

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

        # reconcile / reconcile date
        reconciled = self._get_data_form(data, 'reconciled')
        if reconciled and reconciled != 'empty':
            dt = self._get_data_form(data, 'reconcile_date')
            if dt:
                dt = ' ' + self.formatLang(dt, date=True)
            infos.append(_("Reconcile %s%s") % (reconciled.title(), dt or '', ))

        return infos and ", \n".join(infos) or _('No Filter')

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

    def _get_prop_instances_str(self):
        data_tools_obj = self.pool.get('data.tools')
        inst_list = [ i.code \
                      for i in self.pool.get('msf.instance').browse(self.cr, self.uid, self.selected_instance_ids) \
                      if i.code ]
        return data_tools_obj.truncate_list(inst_list)

    def _get_journals_str(self, data):
        data_tools_obj = self.pool.get('data.tools')
        prefix = self._get_data_form(data, 'rev_journal_ids', default=False) and _("Excluded Journals: ") or ""
        if 'all_journals' in data['form']:
            ret = _('All Journals')
        else:
            journal_list = list(set(self._get_journal(data, instance_ids=self.selected_instance_ids)))
            ret = data_tools_obj.truncate_list(journal_list, limit=300-len(prefix))
        return "%s%s" % (prefix, ret)

    # internal filter functions
    def _get_data_form(self, data, key, default=False):
        if not 'form' in data or not key in data['form']:
            return default
        return data['form'].get(key, default)

    def _get_display_info(self, data):
        data_tools_obj = self.pool.get('data.tools')
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
                          self.reconciled_filter and yes_str or no_str, ))

        display_account = all_str
        if 'display_account' in data['form']:
            if data['form']['display_account'] == 'bal_all':
                display_account = _('All')
            elif data['form']['display_account'] == 'bal_movement':
                display_account = _('With movements')
            else:
                display_account = _('With balance is not equal to 0')
        info_data.append((_('Accounts'), display_account, ))

        account_ids = list(set(self._get_data_form(data, 'account_ids')))
        if account_ids and not self.exclude_all_acc:
            # US-1197/2: display filtered accounts
            account_obj = self.pool.get('account.account')
            if self._get_data_form(data, 'rev_account_ids', default=False):
                account_label = _('Excluded Accounts')
            else:
                account_label = _('Selected Accounts')
            info_data.append((account_label, ', '.join(
                [ a.code for a in account_obj.browse(
                  self.cr, self.uid, account_ids) \
                  if a.type != 'view' ], )))

        res = [ "%s: %s" % (label, val, ) for label, val in info_data ]
        return data_tools_obj.truncate_list(res, separator=', \n')

    def _get_open_items_selection(self, data):
        """
        Returns the name of the period selected in the filter "Open Items at" if any
        """
        period_obj = self.pool.get('account.period')
        if data.get('form', {}).get('open_items'):
            return period_obj.read(self.cr, self.uid, data['form']['open_items'], ['name'], context=self.context)['name']
        return ''

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
