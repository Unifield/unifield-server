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

from tools.translate import _
from report import report_sxw
from common_report_header import common_report_header
import pooler

class partner_balance(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        super(partner_balance, self).__init__(cr, uid, name, context=context)
        self.account_ids = []
        self.IB_DATE_TO = ''
        self.IB_JOURNAL_REQUEST = ''
        self.result_lines = False
        self.partner_account_used_for_ib = []
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit,
            'sum_litige': self._sum_litige,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_filter': self._get_filter,
            'get_account': self._get_account,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_partners':self._get_partners,
            'get_target_move': self._get_target_move,
            'get_accounts': self._get_accounts,
        })

    def set_context(self, objects, data, ids, report_type=None):
        self.display_partner = data['form'].get('display_partner', 'non-zero_balance')
        obj_move = self.pool.get('account.move.line')
        obj_journal = self.pool.get('account.journal')
        obj_fy = self.pool.get('account.fiscalyear')
        self.query = obj_move._query_get(self.cr, self.uid, obj='l', context=data['form'].get('used_context', {}))
        self.result_selection = data['form'].get('result_selection')
        self.target_move = data['form'].get('target_move', 'all')
        self.instance_ids = data['form'].get('instance_ids', False)
        self.account_ids = data['form'].get('account_ids', False)
        self.initial_balance = data['form'].get('initial_balance', False)
        self.fiscalyear_id = data['form'].get('fiscalyear_id', False)
        if self.fiscalyear_id:
            fy = obj_fy.read(self.cr, self.uid, [self.fiscalyear_id], ['date_start'],
                             context=data['form'].get('used_context', {}))

        # if "Initial Balance" and FY are selected, store data for the IB calculation whatever the dates or periods selected
        if self.initial_balance and self.fiscalyear_id:
            self.IB_DATE_TO = "AND l.date < '%s'" % fy[0].get('date_start')
            # all journals by default
            journal_ids = data['form'].get('journal_ids',
                                           obj_journal.search(self.cr, self.uid, [], order='NO_ORDER',
                                                              context=data.get('context', {})))
            if len(journal_ids) == 1:
                self.IB_JOURNAL_REQUEST = "AND l.journal_id = %s" % journal_ids[0]
            else:
                self.IB_JOURNAL_REQUEST = "AND l.journal_id IN %s" % (tuple(journal_ids),)

        self.PARTNER_REQUEST = 'AND l.partner_id IS NOT NULL'
        if data['form'].get('partner_ids', False):  # some partners are specifically selected
            partner_ids = data['form']['partner_ids']
            if len(partner_ids) == 1:
                self.PARTNER_REQUEST = 'AND p.id = %s' % partner_ids[0]
            else:
                self.PARTNER_REQUEST = 'AND p.id IN %s' % (tuple(partner_ids),)
        elif data['form'].get('only_active_partners'):  # check if we should include only active partners
            self.PARTNER_REQUEST = "AND p.active = 't'"

        if (self.result_selection == 'customer' ):
            self.ACCOUNT_TYPE = ('receivable',)
        elif (self.result_selection == 'supplier'):
            self.ACCOUNT_TYPE = ('payable',)
        else:
            self.ACCOUNT_TYPE = ('payable', 'receivable')

        self.move_state = ['draft', 'posted']
        if self.target_move == 'posted':
            self.move_state = ['posted']

        # UFTP-312: Permit to exclude tax accounts from the report
        self.exclude_tax = data['form'].get('tax', False)
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

        self.RECONCILE_REQUEST = ''
        if not data['form'].get('include_reconciled_entries', True):
            self.RECONCILE_REQUEST = 'AND l.reconcile_id IS NULL'  # include only non-reconciled entries

        # get the account list (if some accounts have been specifically selected use them directly)
        if not self.account_ids:
            self.cr.execute("SELECT a.id "
                "FROM account_account a "
                "LEFT JOIN account_account_type t "
                    "ON (a.user_type = t.id) "
                    "WHERE a.type IN %s "
                    " " + self.TAX_REQUEST + " "
                    "AND a.active", (self.ACCOUNT_TYPE,))
            self.account_ids = [a for (a,) in self.cr.fetchall()]
        res = super(partner_balance, self).set_context(objects, data, ids, report_type=report_type)
        common_report_header._set_context(self, data)
        return res

    def _get_initial_balance(self, partner_id, account_id):
        """
        Returns the initial balance for the partner and account in parameter as: [(debit, credit, balance)]
        """
        if not partner_id or not account_id:
            return [(0.0, 0.0, 0.0)]
        self.cr.execute(
            "SELECT COALESCE(SUM(l.debit),0.0), COALESCE(SUM(l.credit),0.0), COALESCE(sum(debit-credit), 0.0) "
            "FROM account_move_line AS l,  "
            "account_move AS am "
            "WHERE l.partner_id = %s "
            "AND am.id = l.move_id "
            "AND am.state IN %s "
            "AND account_id = %s"
            " " + self.RECONCILE_REQUEST + " "
            " " + self.IB_JOURNAL_REQUEST + " "
            " " + self.IB_DATE_TO + " ",
            (partner_id, tuple(self.move_state), account_id))
        # store the tuple (partner, account) where an IB has been calculated
        self.partner_account_used_for_ib.append((partner_id, account_id))
        return self.cr.fetchall()

    def lines(self):
        if self.result_lines:
            return self.result_lines
        full_account = []
        self.cr.execute(
            "SELECT p.id as partner_id, ac.id as account_id, p.ref, l.account_id, ac.name AS account_name, "
            "ac.code AS code, p.name, COALESCE(sum(debit), 0) AS debit, COALESCE(sum(credit), 0) AS credit, "
                    "CASE WHEN sum(debit) > sum(credit) " \
                        "THEN sum(debit) - sum(credit) " \
                        "ELSE 0 " \
                    "END AS sdebit, " \
                    "CASE WHEN sum(debit) < sum(credit) " \
                        "THEN sum(credit) - sum(debit) " \
                        "ELSE 0 " \
                    "END AS scredit, " \
                    "(SELECT sum(debit-credit) " \
                        "FROM account_move_line l " \
                        "WHERE partner_id = p.id " \
                            "AND " + self.query + " " \
                            "AND blocked = TRUE " \
                    ") AS enlitige " \
            "FROM account_move_line l INNER JOIN res_partner p ON (l.partner_id=p.id) "
            "JOIN account_account ac ON (l.account_id = ac.id)" \
            "JOIN account_move am ON (am.id = l.move_id)" \
            "WHERE ac.id IN %s " \
            "AND am.state IN %s " \
            "AND " + self.query + "" \
            " " + self.PARTNER_REQUEST + " "
            " " + self.RECONCILE_REQUEST + " "
            " " + self.INSTANCE_REQUEST + " "
            "GROUP BY p.id, p.ref, p.name, l.account_id, ac.name, ac.code, ac.id "
            "ORDER BY l.account_id,p.name",
            (tuple(self.account_ids), tuple(self.move_state)))
        res = self.cr.dictfetchall()

        if self.display_partner == 'non-zero_balance':
            full_account = [r for r in res if r['sdebit'] > 0 or r['scredit'] > 0]
        else:
            full_account = [r for r in res]

        for rec in full_account:
            if not rec.get('name', False):
                rec.update({'name': _('Unknown Partner')})

        full_account_ib = []
        for fa in full_account:
            # add the initial balance for each "account + partner"
            ib = [(0.0, 0.0, 0.0)]
            if self.initial_balance:
                partner_id = fa.get('partner_id', False)
                account_id = fa.get('account_id', False)
                ib = self._get_initial_balance(partner_id, account_id)
            fa['initial_balance'] = ib
            full_account_ib.append(fa)

        ## We will now compute Total
        self.result_lines = subtotal_row = self._add_subtotal(full_account_ib)
        return subtotal_row

    def _add_subtotal(self, cleanarray):
        i = 0
        completearray = []
        tot_debit = 0.0
        tot_credit = 0.0
        tot_scredit = 0.0
        tot_sdebit = 0.0
        tot_ib_credit = 0.0
        tot_ib_debit = 0.0
        tot_enlitige = 0.0
        for r in cleanarray:
            # For the first element we always add the line
            # type = 1 is the line is the first of the account
            # type = 2 is an other line of the account
            if i==0:
                # We add the first as the header
                #
                ##
                new_header = {}
                new_header['ref'] = ''
                new_header['name'] = r['account_name']
                new_header['code'] = r['code']
                new_header['debit'] = r['debit']
                new_header['credit'] = r['credit']
                new_header['scredit'] = tot_scredit
                new_header['sdebit'] = tot_sdebit
                new_header['initial_balance'] = []
                # Initial Balance values are stored in a tuple in the following order: (debit, credit, balance)
                new_header['initial_balance'].append((tot_ib_debit, tot_ib_credit, r['initial_balance'][0][0] - r['initial_balance'][0][1]))
                new_header['enlitige'] = tot_enlitige
                new_header['balance'] = r['debit'] - r['credit']
                new_header['type'] = 3
                ##
                completearray.append(new_header)
                #
                r['type'] = 1
                r['balance'] = float(r['sdebit']) - float(r['scredit'])
                r['initial_balance'][0] = (r['initial_balance'][0][0], r['initial_balance'][0][1], float(r['initial_balance'][0][0]) - float(r['initial_balance'][0][1]))

                completearray.append(r)
                #
                tot_debit = r['debit']
                tot_credit = r['credit']
                tot_scredit = r['scredit']
                tot_sdebit = r['sdebit']
                tot_ib_debit = r['initial_balance'][0][0]
                tot_ib_credit = r['initial_balance'][0][1]
                tot_enlitige = (r['enlitige'] or 0.0)
                #
            else:
                if cleanarray[i]['account_id'] <> cleanarray[i-1]['account_id']:

                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['initial_balance'] = []
                    new_header['initial_balance'].append((tot_ib_debit, tot_ib_credit, float(tot_ib_debit) - float(tot_ib_credit)))
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)
                    new_header['type'] = 3
                    # we reset the counter
                    tot_debit = r['debit']
                    tot_credit = r['credit']
                    tot_scredit = r['scredit']
                    tot_sdebit = r['sdebit']
                    tot_ib_debit = r['initial_balance'][0][0]
                    tot_ib_credit = r['initial_balance'][0][1]
                    tot_enlitige = (r['enlitige'] or 0.0)
                    #
                    ##
                    new_header = {}
                    new_header['ref'] = ''
                    new_header['name'] = r['account_name']
                    new_header['code'] = r['code']
                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['initial_balance'] = []
                    new_header['initial_balance'].append((tot_ib_debit, tot_ib_credit, float(tot_ib_debit) - float(tot_ib_credit)))
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)
                    new_header['type'] = 3
                    ##get_fiscalyear
                    ##

                    completearray.append(new_header)
                    ##
                    #
                    r['type'] = 1
                    #
                    r['balance'] = float(r['sdebit']) - float(r['scredit'])
                    r['initial_balance'][0] = (r['initial_balance'][0][0], r['initial_balance'][0][1], float(r['initial_balance'][0][0]) - float(r['initial_balance'][0][1]))

                    completearray.append(r)

                if cleanarray[i]['account_id'] == cleanarray[i-1]['account_id']:
                    # we reset the counter

                    new_header['type'] = 3

                    tot_debit = tot_debit + r['debit']
                    tot_credit = tot_credit + r['credit']
                    tot_scredit = tot_scredit + r['scredit']
                    tot_sdebit = tot_sdebit + r['sdebit']
                    tot_ib_debit = tot_ib_debit + r['initial_balance'][0][0]
                    tot_ib_credit = tot_ib_credit + r['initial_balance'][0][1]
                    tot_enlitige = tot_enlitige + (r['enlitige'] or 0.0)

                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['initial_balance'] = []
                    new_header['initial_balance'].append((tot_ib_debit, tot_ib_credit, float(tot_ib_debit) - float(tot_ib_credit)))
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)

                    #
                    r['type'] = 2
                    #
                    r['balance'] = float(r['sdebit']) - float(r['scredit'])
                    r['initial_balance'][0] = (r['initial_balance'][0][0], r['initial_balance'][0][1], float(r['initial_balance'][0][0]) - float(r['initial_balance'][0][1]))
                    #

                    completearray.append(r)

            i = i + 1
        return completearray

    def _sum_debit(self):
        if not self.ids:
            return 0.0
        temp_res = 0.0
        init_res = 0.0
        # calculate the Initial Balance ONLY for partner-account associations having IB lines displayed in the report
        if self.initial_balance:
            self.lines()  # to get the correct values for self.partner_account_used_for_ib
            for partner_account in self.partner_account_used_for_ib:
                self.cr.execute(
                        "SELECT sum(debit) "
                        "FROM account_move_line AS l "
                        "INNER JOIN account_move AS am ON am.id = l.move_id "
                        "INNER JOIN res_partner AS p ON l.partner_id = p.id "
                        "AND am.state IN %s "
                        " " + self.RECONCILE_REQUEST + " "
                        " AND p.id = %s "
                        " AND l.account_id = %s "
                        " " + self.IB_DATE_TO + " "
                        " " + self.INSTANCE_REQUEST + " "
                        " " + self.IB_JOURNAL_REQUEST + " ",
                        (tuple(self.move_state), partner_account[0], partner_account[1]))
                contemp = self.cr.fetchone()
                if contemp != None:
                    init_res += float(contemp[0] or 0.0)

        self.cr.execute(
                "SELECT sum(debit) " \
                "FROM account_move_line AS l "
                "INNER JOIN account_move AS am ON am.id = l.move_id "
                "INNER JOIN res_partner AS p ON l.partner_id = p.id "
                "WHERE l.account_id IN %s"  \
                    "AND am.state IN %s" \
                    "AND " + self.query + " "
                    " " + self.PARTNER_REQUEST + " "
                    " " + self.RECONCILE_REQUEST + " "
                    " " + self.INSTANCE_REQUEST + " ",
                    (tuple(self.account_ids), tuple(self.move_state)))
        temp_res = float(self.cr.fetchone()[0] or 0.0)
        return temp_res + init_res

    def _sum_credit(self):
        if not self.ids:
            return 0.0
        temp_res = 0.0
        init_res = 0.0
        # calculate the Initial Balance ONLY for partner-account associations having IB lines displayed in the report
        if self.initial_balance:
            self.lines()  # to get the correct values for self.partner_account_used_for_ib
            for partner_account in self.partner_account_used_for_ib:
                self.cr.execute(
                        "SELECT sum(credit) "
                        "FROM account_move_line AS l "
                        "INNER JOIN account_move AS am ON am.id = l.move_id "
                        "INNER JOIN res_partner AS p ON l.partner_id = p.id "
                        "AND am.state IN %s "
                        " " + self.RECONCILE_REQUEST + " "
                        " AND p.id = %s "
                        " AND l.account_id = %s "
                        " " + self.IB_DATE_TO + " "
                        " " + self.INSTANCE_REQUEST + " "
                        " " + self.IB_JOURNAL_REQUEST + " ",
                        (tuple(self.move_state), partner_account[0], partner_account[1]))
                contemp = self.cr.fetchone()
                if contemp != None:
                    init_res += float(contemp[0] or 0.0)

        self.cr.execute(
                "SELECT sum(credit) " \
                "FROM account_move_line AS l INNER JOIN res_partner p ON l.partner_id = p.id "
                "JOIN account_move am ON (am.id = l.move_id)" \
                "WHERE l.account_id IN %s" \
                    "AND am.state IN %s" \
                    "AND " + self.query + ""
                    " " + self.PARTNER_REQUEST + " "
                    " " + self.RECONCILE_REQUEST + " "
                    " " + self.INSTANCE_REQUEST + " ",
                    (tuple(self.account_ids), tuple(self.move_state)))
        temp_res = float(self.cr.fetchone()[0] or 0.0)
        return temp_res + init_res

    def _sum_litige(self):
        #gives the total of move lines with blocked boolean set to TRUE for the report selection
        if not self.ids:
            return 0.0
        temp_res = 0.0
        self.cr.execute(
                "SELECT sum(debit-credit) " \
                "FROM account_move_line AS l INNER JOIN res_partner p ON l.partner_id = p.id "
                "JOIN account_move am ON (am.id = l.move_id)" \
                "WHERE l.account_id IN %s" \
                    "AND am.state IN %s" \
                    "AND " + self.query + " " \
                    " " + self.PARTNER_REQUEST + " "
                    " " + self.RECONCILE_REQUEST + " "
                    " " + self.INSTANCE_REQUEST + " "
                    "AND l.blocked=TRUE ",
                    (tuple(self.account_ids), tuple(self.move_state), ))
        temp_res = float(self.cr.fetchone()[0] or 0.0)
        return temp_res

    def _get_partners(self):
        cr, uid = self.cr, self.uid
        context = self.localcontext # all of it?

        if self.result_selection == 'customer':
            return _('Receivable Accounts')
        elif self.result_selection == 'supplier':
            return _('Payable Accounts')
        elif self.result_selection == 'customer_supplier':
            return _('Receivable and Payable Accounts')
        return ''

    def _get_journal(self, data, instance_ids=False):
        """
        If all journals have been selected: display "All Journals" instead of listing all of them
        """
        if data.get('form', False) and data['form'].get('all_journals', False):
            return [_('All Journals')]
        return super(partner_balance, self)._get_journal(data, instance_ids)

report_sxw.report_sxw('report.account.partner.balance', 'res.partner', 'account/report/account_partner_balance.rml',parser=partner_balance, header="internal")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
