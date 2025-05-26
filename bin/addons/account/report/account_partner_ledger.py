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

import time
import re
from report import report_sxw
from .common_report_header import common_report_header
import pooler
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _

class third_party_ledger(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        super(third_party_ledger, self).__init__(cr, uid, name, context=context)
        self.fctal_totals = {}  # to store the totals in functional currency
        self.subtotals = {}  # to store the subtotals per booking currency
        self.accounts_to_display = {}
        self.report_lines = {}
        self.debit_balances = {}
        self.credit_balances = {}
        self.current_partner_number = 0
        self.localcontext.update({
            'partners_to_display': self._partners_to_display,
            'time': time,
            'lines': self.lines,
            'sum_debit_partner': self._sum_debit_partner,
            'sum_credit_partner': self._sum_credit_partner,
            'get_currency': self._get_currency,
            'comma_me': self.comma_me,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_account': self._get_account,
            'get_filter': self._get_filter,
            'get_start_date': self._get_start_date,
            'get_end_date': self._get_end_date,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journals_str': self._get_journals_str,
            'get_partners':self._get_partners,
            'get_target_move': self._get_target_move,
            'get_reconcile_selection': self._get_reconcile_selection,
            'get_display_partners_selection': self._get_display_partners_selection,
            'get_instances_str': self._get_instances_str,
            'get_accounts_str': self._get_accounts_str,
            'format_entry_label': self._format_entry_label,
            'get_accounts_to_display': self._get_accounts_to_display,
            'get_fctal_totals': self._get_fctal_totals,
            'get_subtotals': self._get_subtotals,
            'nb_partners': lambda partners: len(self._partners_to_display(partners)),
            'update_current_partner_number': self._update_current_partner_number,
            'get_current_partner_number': lambda: self.current_partner_number,
        })

    def set_context(self, objects, data, ids, report_type=None):
        obj_move = self.pool.get('account.move.line')
        obj_partner = self.pool.get('res.partner')
        obj_fy = self.pool.get('account.fiscalyear')
        used_context = data['form'].get('used_context', {})
        self.reconciled = data['form'].get('reconciled', False)
        self.result_selection = data['form'].get('result_selection', 'customer_supplier')
        self.target_move = data['form'].get('target_move', 'all')
        self.period_id = data['form'].get('period_from', False)
        self.date_from = data['form'].get('date_from', False)
        self.exclude_tax = data['form'].get('tax', False)
        self.instance_ids = data['form'].get('instance_ids', False)
        self.account_ids = data['form'].get('account_ids', False)
        self.display_partner = data['form'].get('display_partner', '')
        self.fiscalyear_id = data['form'].get('fiscalyear_id', False)
        if self.fiscalyear_id:
            fy = obj_fy.read(self.cr, self.uid, [self.fiscalyear_id], ['date_start'], context=used_context)
        else:
            # by default all FY taken into account
            used_context.update({'all_fiscalyear': True})
        self.query = obj_move._query_get(self.cr, self.uid, obj='l', context=used_context)

        #+ To have right partner balance, we have to take all next lines after a specific date.
        #+ To do that, we need to make requests regarding a date. So first we take date_from
        #+  then period_from (if no date_from)
        #+  finally fisalyear_id (if no period)
        #+ If no date, the report is wrong.
        pool = pooler.get_pool(self.cr.dbname)
        self.DATE_FROM = ''
        if self.fiscalyear_id or self.period_id or self.date_from:
            if self.date_from:
                self.DATE_FROM = "AND l.date >= '%s'" % self.date_from
            elif self.period_id:
                period_obj = pool.get('account.period')
                period = period_obj.read(self.cr, self.uid, [self.period_id], ['date_start'])
                self.DATE_FROM = "AND l.date >= '%s'" % period[0].get('date_start')
            elif self.fiscalyear_id:
                self.DATE_FROM = "AND l.date >= '%s'" % fy[0].get('date_start')

        # UFTP-312: Exclude tax if user ask it
        self.TAX_REQUEST = ''
        if self.exclude_tax is True:
            self.TAX_REQUEST = "AND t.code != 'tax'"

        # Create the part of the request concerning instances
        if not self.instance_ids:
            # select all instances by default
            self.instance_ids = self.pool.get('msf.instance').search(self.cr, self.uid, [], order='NO_ORDER')
        if len(self.instance_ids) == 1:
            self.INSTANCE_REQUEST = "AND l.instance_id = %s" % self.instance_ids[0]
        else:
            self.INSTANCE_REQUEST = "AND l.instance_id IN %s" % (tuple(self.instance_ids),)

        if self.result_selection == 'supplier':
            self.ACCOUNT_TYPE = ['payable']
        elif self.result_selection == 'customer':
            self.ACCOUNT_TYPE = ['receivable']
        else:
            self.ACCOUNT_TYPE = ['payable','receivable']

        # get the account list (if some accounts have been specifically selected use them directly)
        if not self.account_ids:
            self.cr.execute(
                "SELECT a.id " \
                "FROM account_account a " \
                "LEFT JOIN account_account_type t " \
                "ON (a.user_type=t.id) " \
                'WHERE a.type IN %s' \
                " " + self.TAX_REQUEST + " " \
                "AND a.active", (tuple(self.ACCOUNT_TYPE), ))
            self.account_ids = [a for (a,) in self.cr.fetchall()]
        if data['form'].get('partner_ids', False):
            new_ids = data['form']['partner_ids']  # some partners are specifically selected
        else:
            partner_to_use = []
            # check if we should display all partners or only active ones
            active_selection = data['form'].get('only_active_partners') and ('t',) or ('t', 'f')
            self.cr.execute(
                "SELECT id as partner_id, name "
                "FROM res_partner "
                "WHERE active IN %s "
                "AND name != 'To be defined'"
                "ORDER BY name;",
                (active_selection,))
            res = self.cr.dictfetchall()
            for res_line in res:
                partner_to_use.append(res_line['partner_id'])
            new_ids = partner_to_use
        self.partner_ids = new_ids
        objects = obj_partner.browse(self.cr, self.uid, new_ids)
        res = super(third_party_ledger, self).set_context(objects, data, new_ids, report_type)
        common_report_header._set_context(self, data)
        if data['model'] == 'ir.ui.menu':
            # US-324: use of user LG instead of each partner in the report
            lang_dict = self.pool.get('res.users').read(self.cr,self.uid,self.uid,['context_lang'])
            data['lang'] = lang_dict.get('context_lang') or False

        return res

    def comma_me(self, amount):
        if type(amount) is float:
            amount = str('%.2f'%amount)
        else:
            amount = str(amount)
        if (amount == '0'):
            return ' '
        orig = amount
        new = re.sub(r"^(-?\d+)(\d{3})", r"\g<1>'\g<2>", amount)
        if orig == new:
            return new
        else:
            return self.comma_me(new)

    def _format_entry_label(self, label, index):
        """
        Formats the entry label:
        adds a line break every (index) character
        """
        x = 0
        parts = []
        while x < len(label):
            parts.append(label[x:x+index])
            x += index
        return "\n".join(parts)

    def _get_accounts_to_display(self, partner):
        """
        Returns the list of account codes to be displayed for the partner in parameter
        """
        if self.accounts_to_display:
            return self.accounts_to_display.get(partner.id, [])
        move_state = ['draft', 'posted']
        if self.target_move == 'posted':
            move_state = ['posted']
        if self.reconciled == 'yes':
            reconcile_tag = "AND l.reconcile_id IS NOT NULL"
        elif self.reconciled == 'no':
            reconcile_tag = "AND l.reconcile_id IS NULL AND acc.reconcile='t'"  # reconcilable entries not reconciled
        else:  # 'empty'
            reconcile_tag = " "
        self.cr.execute(
            "SELECT l.partner_id, acc.code "
            "FROM account_move_line l "
            "LEFT JOIN account_journal j ON l.journal_id = j.id "
            "LEFT JOIN account_account acc ON l.account_id = acc.id "
            "LEFT JOIN res_currency c ON l.currency_id = c.id "
            "LEFT JOIN account_move m ON m.id = l.move_id "
            "WHERE "
            " l.account_id IN %s AND " + self.query + " "
            "AND m.state IN %s "
            " " + reconcile_tag + " "
            " " + self.DATE_FROM + " "
            " " + self.INSTANCE_REQUEST + " "
            "GROUP BY l.partner_id, acc.code ORDER BY acc.code;",
            (tuple(self.account_ids), tuple(move_state)))
        for x in self.cr.fetchall():
            self.accounts_to_display.setdefault(x[0], []).append(x[1])
        return self.accounts_to_display.get(partner.id, [])

    def lines(self, partner, account_code):
        if partner.id in self.report_lines and account_code in self.report_lines[partner.id]:
            return self.report_lines[partner.id][account_code]
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']

        if self.reconciled == 'yes':
            RECONCILE_TAG = "AND l.reconcile_id IS NOT NULL"
        elif self.reconciled == 'no':
            RECONCILE_TAG = "AND l.reconcile_id IS NULL AND acc.reconcile='t'"  # reconcilable entries not reconciled
        else:  # 'empty'
            RECONCILE_TAG = " "
        self.cr.execute(
            "SELECT l.id, l.date, j.code, acc.code as a_code, acc.name as a_name, l.ref, m.name as move_name, l.name, "
            "COALESCE(l.debit_currency, 0) as debit, COALESCE(l.credit_currency, 0) as credit, "
            "COALESCE(l.debit, 0) AS debit_functional, COALESCE(l.credit, 0) AS credit_functional, "
            "l.debit - l.credit as total_functional, l.amount_currency, l.currency_id, c.name AS currency_code, "
            "l.reconcile_txt "
            "FROM account_move_line l " \
            "LEFT JOIN account_journal j " \
            "ON (l.journal_id = j.id) " \
            "LEFT JOIN account_account acc " \
            "ON (l.account_id = acc.id) " \
            "LEFT JOIN res_currency c ON (l.currency_id=c.id)" \
            "LEFT JOIN account_move m ON (m.id=l.move_id)" \
            "WHERE l.partner_id = %s " \
            "AND l.account_id = (SELECT id FROM account_account WHERE code = %s LIMIT 1) "
            "AND " + self.query + " " \
            "AND m.state IN %s " \
            " " + RECONCILE_TAG + " "\
            " " + self.DATE_FROM + " "\
            " " + self.INSTANCE_REQUEST + " "
            "ORDER BY l.date;",
            (partner.id, account_code, tuple(move_state)))
        if partner.id not in self.report_lines:
            self.report_lines[partner.id] = {}
        self.report_lines[partner.id][account_code] = self.cr.dictfetchall()
        # initialize totals in functional currency
        if partner.id not in self.fctal_totals:
            self.fctal_totals[partner.id] = {}
        if account_code not in self.fctal_totals[partner.id]:
            self.fctal_totals[partner.id][account_code] = {
                'debit_functional': 0.0,
                'credit_functional': 0.0,
                'total_functional': 0.0,
            }
        # initialize subtotals in booking currency
        if partner.id not in self.subtotals:
            self.subtotals[partner.id] = {}
        if account_code not in self.subtotals[partner.id]:
            self.subtotals[partner.id][account_code] = {}
        # fill in fctal_totals/subtotals
        for line in self.report_lines[partner.id][account_code]:
            self.fctal_totals[partner.id][account_code]['debit_functional'] += line['debit_functional'] or 0.0
            self.fctal_totals[partner.id][account_code]['credit_functional'] += line['credit_functional'] or 0.0
            self.fctal_totals[partner.id][account_code]['total_functional'] += line['total_functional'] or 0.0
            if line['currency_code'] not in self.subtotals[partner.id][account_code]:
                self.subtotals[partner.id][account_code][line['currency_code']] = {
                    'debit': 0.0,
                    'credit': 0.0,
                    'amount_currency': 0.0,
                    'total_functional': 0.0,
                }
            self.subtotals[partner.id][account_code][line['currency_code']]['debit'] += line['debit'] or 0.0
            self.subtotals[partner.id][account_code][line['currency_code']]['credit'] += line['credit'] or 0.0
            self.subtotals[partner.id][account_code][line['currency_code']]['amount_currency'] += line['amount_currency'] or 0.0
            self.subtotals[partner.id][account_code][line['currency_code']]['total_functional'] += line['total_functional'] or 0.0
        return self.report_lines[partner.id][account_code]

    def _get_subtotals(self, partner, account_code):
        """
        Returns a dictionary with key = currency code, and value = dict. of the subtotals values for the
        partner/account_code, i.e. {'credit': xxx, 'debit': xxx, 'amount_currency': xxx, 'total_functional': xxx}
        """
        if partner.id not in self.subtotals or account_code not in self.subtotals[partner.id]:
            self.lines(partner, account_code)  # fills in the self.subtotals dictionary
        return self.subtotals[partner.id][account_code]

    def _get_fctal_totals(self, partner, account_code):
        """
        Returns a dictionary with the total values in functional currency for the partner/code in param:
        {'credit_functional': xxx, 'debit_functional': xxx, 'total_functional': xxx}
        """
        if partner.id not in self.fctal_totals or account_code not in self.fctal_totals[partner.id]:
            self.lines(partner, account_code)  # fills in the self.fctal_totals dictionary
        return self.fctal_totals[partner.id][account_code]

    def _update_current_partner_number(self):
        """
        Increments the current partner number and always returns True (used for the display in rml template)
        """
        self.current_partner_number += 1
        return True

    def _sum_debit_partner(self, partner):
        if partner.id in self.debit_balances:
            # compute the result only once per partner
            return self.debit_balances[partner.id]
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']

        result_tmp = 0.0
        if self.reconciled == 'yes':
            RECONCILE_TAG = "AND l.reconcile_id IS NOT NULL"
        elif self.reconciled == 'no':
            RECONCILE_TAG = "AND l.reconcile_id IS NULL AND acc.reconcile='t'"  # reconcilable entries not reconciled
        else:  # 'empty'
            RECONCILE_TAG = " "

        self.cr.execute(
            "SELECT sum(debit) " \
            "FROM account_move_line AS l, " \
            "account_move AS m, "
            "account_account AS acc "
            "WHERE l.partner_id = %s " \
            "AND m.id = l.move_id " \
            "AND l.account_id = acc.id "
            "AND m.state IN %s "
            "AND account_id IN %s" \
            " " + RECONCILE_TAG + " " \
            " " + self.DATE_FROM + " " \
            " " + self.INSTANCE_REQUEST + " "
            "AND " + self.query + " ",
            (partner.id, tuple(move_state), tuple(self.account_ids),))

        contemp = self.cr.fetchone()
        if contemp != None:
            result_tmp = contemp[0] or 0.0
        else:
            result_tmp = result_tmp + 0.0
        self.debit_balances[partner.id] = result_tmp
        return result_tmp

    def _sum_credit_partner(self, partner):
        if partner.id in self.credit_balances:
            # compute the result only once per partner
            return self.credit_balances[partner.id]
        move_state = ['draft','posted']
        if self.target_move == 'posted':
            move_state = ['posted']

        result_tmp = 0.0
        if self.reconciled == 'yes':
            RECONCILE_TAG = "AND l.reconcile_id IS NOT NULL"
        elif self.reconciled == 'no':
            RECONCILE_TAG = "AND l.reconcile_id IS NULL AND acc.reconcile='t'"  # reconcilable entries not reconciled
        else:  # 'empty'
            RECONCILE_TAG = " "

        self.cr.execute(
            "SELECT sum(credit) " \
            "FROM account_move_line AS l, " \
            "account_move AS m, "
            "account_account AS acc "
            "WHERE l.partner_id=%s " \
            "AND m.id = l.move_id " \
            "AND l.account_id = acc.id "
            "AND m.state IN %s "
            "AND account_id IN %s" \
            " " + RECONCILE_TAG + " " \
            " " + self.DATE_FROM + " " \
            " " + self.INSTANCE_REQUEST + " "\
            "AND " + self.query + " ",
            (partner.id, tuple(move_state), tuple(self.account_ids),))

        contemp = self.cr.fetchone()
        if contemp != None:
            result_tmp = contemp[0] or 0.0
        else:
            result_tmp = result_tmp + 0.0
        self.credit_balances[partner.id] = result_tmp
        return result_tmp

    def _partners_to_display(self, partners):
        """
        Returns the partners to be displayed in the report as a list of res.partner browse records
        """
        to_display = partners
        if self.display_partner == 'non-zero_balance':
            for p in partners:
                # fill in the dictionaries self.debit_balances and self.credit_balances
                self._sum_debit_partner(p)
                self._sum_credit_partner(p)
            to_display = [p for p in partners if abs(self.debit_balances[p.id] - self.credit_balances[p.id]) > 10**-3]
        elif self.display_partner == 'with_movements':
            for p in partners:
                for account_code in self._get_accounts_to_display(p):
                    # fill in the dictionary self.report_lines
                    self.lines(p, account_code)
            to_display = [p for p in partners if p.id in self.report_lines and self.report_lines[p.id]]
        return to_display

    def _get_partners(self):
        if self.result_selection == 'customer':
            return _('Receivable Accounts')
        elif self.result_selection == 'supplier':
            return _('Payable Accounts')
        elif self.result_selection == 'customer_supplier':
            return _('Receivable and Payable Accounts')
        return ''

    def _get_reconcile_selection(self):
        """
        Returns "Yes" if "Reconciled: Yes" is selected in the wizard
        """
        selection = _('All')
        if self.reconciled == 'yes':
            selection = _('Yes')
        elif self.reconciled == 'no':
            selection = _('No')
        return selection

    def _get_display_partners_selection(self):
        """
        Returns the String to display in the "Display Partners" section of the report header
        """
        selection = '-'
        if self.display_partner == 'all':
            selection = _('All Partners')
        elif self.display_partner == 'with_movements':
            selection = _('With movements')
        elif self.display_partner == 'non-zero_balance':
            selection = _('With balance is not equal to 0')
        return selection

    def _sum_currency_amount_account(self, account, form):
        self._set_get_account_currency_code(account.id)
        self.cr.execute("SELECT sum(aml.amount_currency) FROM account_move_line as aml,res_currency as rc WHERE aml.currency_id = rc.id AND aml.account_id= %s ", (account.id,))
        total = self.cr.fetchone()
        if self.account_currency:
            return_field = str(total[0]) + self.account_currency
            return return_field
        else:
            currency_total = self.tot_currency = 0.0
            return currency_total

    def _get_journal(self, data, instance_ids=False):
        """
        If all journals have been selected: display "All Journals" instead of listing all of them
        """
        journal_ids = data.get('form', False) and data['form'].get('journal_ids', False)
        if journal_ids:
            journal_obj = pooler.get_pool(self.cr.dbname).get('account.journal')
            nb_journals = journal_obj.search(self.cr, self.uid, [], order='NO_ORDER', count=True, context=data.get('context', {}))
            if len(journal_ids) == nb_journals:
                return [_('All Journals')]
        instance_ids = instance_ids or data.get('form', False) and data['form'].get('instance_ids', False)
        journal_list = super(third_party_ledger, self)._get_journal(data, instance_ids)
        return set(journal_list)  # exclude duplications

    def _get_journals_str(self, data):
        """
        Returns the list of journals as a String (cut if > 300 characters)
        """
        data_tools_obj = self.pool.get('data.tools')
        return data_tools_obj.truncate_list(self._get_journal(data))

    def _get_instances_str(self, data):
        """
        Returns the list of instances as a String (cut if > 300 characters)
        """
        data_tools_obj = self.pool.get('data.tools')
        return data_tools_obj.truncate_list(self._get_instances_from_data(data))

    def _get_accounts_str(self, data):
        """
        Returns the list of accounts as a String (cut if > 300 characters)
        """
        data_tools_obj = self.pool.get('data.tools')
        return data_tools_obj.truncate_list(self._get_accounts(data))

# PDF report with one partner per page
report_sxw.report_sxw('report.account.third_party_ledger', 'res.partner',
                      'addons/account/report/account_partner_ledger.rml',parser=third_party_ledger,
                      header='internal landscape')
# PDF report with partners displayed one after another
report_sxw.report_sxw('report.account.third_party_ledger_other', 'res.partner',
                      'addons/account/report/account_partner_ledger_other.rml',parser=third_party_ledger,
                      header='internal landscape')
# XLS report
SpreadsheetReport('report.account.third_party_ledger_xls', 'res.partner',
                  'addons/account/report/account_partner_ledger.mako', parser=third_party_ledger)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
