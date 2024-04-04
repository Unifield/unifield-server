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
from .common_report_header import common_report_header
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from datetime import datetime
from dateutil.relativedelta import relativedelta
from osv import osv
from tools.translate import _

from vertical_integration import report as reportvi

class account_liquidity_balance(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        self.liquidity_sql = reportvi.hq_report_ocb.liquidity_sql  # same SQL request as in OCB VI
        self.period_id = False
        self.date_from = False
        self.date_to = False
        self.instance_ids = False
        self.period_title = False
        self.context = {}
        super(account_liquidity_balance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_register_data': self._get_register_data,
        })

    def _filter_journal_status(self, reg_data):
        """
        Applies the following changes to the reg_data:
        - adds the journal status
        """
        journal_obj = self.pool.get('account.journal')
        new_reg_data = []
        for reg in reg_data:
            journal_active = journal_obj.read(self.cr, self.uid, reg['id'], ['is_active'])['is_active']
            reg['journal_status'] = journal_active and _('Active') or _('Inactive')
            new_reg_data.append(reg)
        return new_reg_data

    def _get_register_data(self):
        """
        Returns a list of dicts, each containing the data of the liquidity registers for the selected period and instances
        For Cash & Bank registers the calculation is the one used in OCB VI.
        For Cheque Registers:
            - starting: balance at end of N-1 of entries which are either not reconciled, or reconciled with at least
                one entry belonging to the same period or later
            - calculated/Movements: always 0.00
            - closing: balance at end of N of entries which are either not reconciled, or reconciled with at least
                one entry belonging to a later period
        """
        res = []
        reg_obj = self.pool.get('account.bank.statement')
        period_obj = self.pool.get('account.period')
        date_from = date_to = False
        if self.date_from and self.date_to:
            date_from = self.date_from
            date_to = self.date_to
        elif self.period_id:
            period = period_obj.browse(self.cr, self.uid, self.period_id, context=self.context,
                                       fields_to_fetch=['date_start', 'date_stop'])
            date_from = period.date_start
            date_to = period.date_stop
        if not date_from or not date_to:
            raise osv.except_osv(_('Error'), _('Start date and/or End date missing.'))
        period_title = self.period_title or ''
        # Cash and Bank registers
        reg_types = ('cash', 'bank')
        params = (period_title, date_from, date_to, reg_types, date_from, reg_types, date_from, date_to, reg_types, date_to, tuple(self.instance_ids))
        self.cr.execute(self.liquidity_sql, params)
        cash_bank_res = self.cr.dictfetchall()
        cash_bank_res = self._filter_journal_status(cash_bank_res)
        cash_bank_res = reportvi.hq_report_ocb.postprocess_liquidity_balances(self, self.cr, self.uid, cash_bank_res,
                                                                              encode=False, context=self.context)
        res.extend(cash_bank_res)
        # Cheque registers
        # Chq Starting Balance
        chq_starting_bal_sql = """
            SELECT DISTINCT (aml.id)
            FROM account_move_line aml 
            LEFT JOIN account_journal j ON aml.journal_id = j.id 
            WHERE j.type = 'cheque'
            AND aml.date < %s
            AND j.instance_id IN %s
            AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id);
        """
        self.cr.execute(chq_starting_bal_sql, (date_from, tuple(self.instance_ids)))
        chq_starting_bal_ids = [x for x, in self.cr.fetchall()]
        # get the day before the beginning date (cf the beginning date itself should be included in the Pending Chq computation)
        date_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        beginning_date = (date_from_dt + relativedelta(days=-1)).strftime('%Y-%m-%d')
        pending_chq_starting_bal_ids = reg_obj.get_pending_cheque_ids(self.cr, self.uid, [], [], beginning_date,
                                                                      aml_ids=chq_starting_bal_ids, context=self.context)
        # Chq Closing Balance
        chq_closing_bal_sql = """
            SELECT DISTINCT (aml.id)
            FROM account_move_line aml 
            LEFT JOIN account_journal j ON aml.journal_id = j.id 
            WHERE j.type = 'cheque'
            AND aml.date <= %s
            AND j.instance_id IN %s
            AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id);
        """
        self.cr.execute(chq_closing_bal_sql, (date_to, tuple(self.instance_ids)))
        chq_closing_bal_ids = [x for x, in self.cr.fetchall()]
        pending_chq_closing_bal_ids = reg_obj.get_pending_cheque_ids(self.cr, self.uid, [], [], date_to,
                                                                     aml_ids=chq_closing_bal_ids, context=self.context)
        cheque_sql = """
                    SELECT i.code AS instance, j.code, j.id, %s AS period, req.opening, req.calculated, req.closing, 
                    c.name AS currency
                    FROM res_currency c,
                    (
                        SELECT journal_id, account_id, SUM(col1) AS opening, SUM(col2) AS calculated, SUM(col3) AS closing
                        FROM (
                            (
                                SELECT journal_id, account_id, ROUND(SUM(amount_currency), 2) as col1, 0.00 as col2, 0.00 as col3
                                FROM account_move_line
                                WHERE id IN %s
                                GROUP BY journal_id, account_id
                            )
                        UNION
                            (
                                SELECT journal_id, account_id, 0.00 as col1, 0.00 as col2, ROUND(SUM(amount_currency), 2) as col3
                                FROM account_move_line
                                WHERE id IN %s
                                GROUP BY journal_id, account_id
                            )
                        ) AS ssreq
                        GROUP BY journal_id, account_id
                        ORDER BY journal_id, account_id
                    ) AS req, account_journal j, msf_instance i
                    WHERE req.journal_id = j.id
                    AND j.instance_id = i.id
                    AND j.currency = c.id
                    AND j.instance_id IN %s;
                    """
        # ensure not to have empty arrays to avoid crash at query execution...
        pending_chq_starting_bal_ids = pending_chq_starting_bal_ids or [-1]
        pending_chq_closing_bal_ids = pending_chq_closing_bal_ids or [-1]
        cheque_params = (period_title, tuple(pending_chq_starting_bal_ids), tuple(pending_chq_closing_bal_ids), tuple(self.instance_ids))
        self.cr.execute(cheque_sql, cheque_params)
        cheque_res = self.cr.dictfetchall()
        cheque_res = self._filter_journal_status(cheque_res)
        cheque_res = reportvi.hq_report_ocb.postprocess_liquidity_balances(self, self.cr, self.uid, cheque_res, encode=False, context=self.context)
        res.extend(cheque_res)
        # sort result by instance code and by journal code
        sorted_res = sorted(res, key=lambda k: (k['instance'], k['code']))
        return sorted_res

    def set_context(self, objects, data, ids, report_type=None):
        # get the selection made by the user
        self.period_id = data['form'].get('period_id', False)
        self.date_from = data['form'].get('date_from', False)
        self.date_to = data['form'].get('date_to', False)
        self.instance_ids = data['form'].get('instance_ids', False)
        self.period_title = data['form'].get('period_title', False)
        self.context = data.get('context', {})
        return super(account_liquidity_balance, self).set_context(objects, data, ids, report_type)

SpreadsheetReport('report.account.liquidity.balance', 'account.bank.statement',
                  'addons/account/report/account_liquidity_balance.mako', parser=account_liquidity_balance)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
