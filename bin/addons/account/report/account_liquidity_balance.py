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
from common_report_header import common_report_header
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport

from vertical_integration import report as reportvi

class account_liquidity_balance(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        self.liquidity_sql = reportvi.hq_report_ocb.liquidity_sql  # same SQL request as in OCB VI
        self.period_id = False
        self.instance_ids = False
        self.year = False
        self.month = False
        super(account_liquidity_balance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_register_data': self._get_register_data,
        })

    def _get_register_data(self):
        """
        Returns a list of dicts, each containing the data of the liquidity registers for the selected period and instances
        For Cash & Bank registers the calculation is the one used in OCB VI.
        For Cheque Registers:
            - opening: balance at end of N-1 of entries which are not reconciled within period N-1 or before
            - calculated: always 0.00
            - closing: balance at end of N of entries which are not reconciled within period N or before
        """
        res = []
        period = self.pool.get('account.period').browse(self.cr, self.uid, self.period_id, context=self.context,
                                                        fields_to_fetch=['date_start', 'date_stop'])
        period_yyyymm = "{0}{1}".format(self.year, self.month)
        # Cash and Bank registers
        reg_types = ('cash', 'bank')
        params = (tuple([period_yyyymm]), reg_types, period.date_start, reg_types, period.id, reg_types,
                  period.date_stop, tuple(self.instance_ids))
        self.cr.execute(self.liquidity_sql, params)
        cash_bank_res = self.cr.dictfetchall()
        res.extend(cash_bank_res)
        # Cheque registers
        cheque_sql = """
                    SELECT i.code AS instance, j.code, j.name, %s AS period, req.opening, req.calculated, req.closing, 
                    c.name AS currency
                    FROM res_currency c,
                    (
                        SELECT journal_id, account_id, SUM(col1) AS opening, SUM(col2) AS calculated, SUM(col3) AS closing
                        FROM (
                            (
                                SELECT aml.journal_id AS journal_id, aml.account_id AS account_id, 
                                ROUND(SUM(amount_currency), 2) as col1, 0.00 as col2, 0.00 as col3
                                FROM account_move_line AS aml 
                                LEFT JOIN account_journal j ON aml.journal_id = j.id 
                                WHERE j.type = 'cheque'
                                AND aml.date < %s
                                AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id)
                                AND ((reconcile_id IS NULL AND reconcile_partial_id IS NULL) OR reconcile_date >= %s)
                                GROUP BY aml.journal_id, aml.account_id
                            )
                        UNION
                            (
                                SELECT aml.journal_id AS journal_id, aml.account_id AS account_id, 0.00 as col1, 
                                0.00 as col2, ROUND(SUM(amount_currency), 2) as col3
                                FROM account_move_line AS aml 
                                LEFT JOIN account_journal j ON aml.journal_id = j.id 
                                WHERE j.type = 'cheque'
                                AND aml.date <= %s
                                AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id)
                                AND ((reconcile_id IS NULL AND reconcile_partial_id IS NULL) OR reconcile_date > %s)
                                GROUP BY aml.journal_id, aml.account_id
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
        cheque_params = (tuple([period_yyyymm]), period.date_start, period.date_start, period.date_stop,
                         period.date_stop, tuple(self.instance_ids))
        self.cr.execute(cheque_sql, cheque_params)
        cheque_res = self.cr.dictfetchall()
        res.extend(cheque_res)
        return res

    def set_context(self, objects, data, ids, report_type=None):
        # get the selection made by the user
        self.period_id = data['form'].get('period_id', False)
        self.instance_ids = data['form'].get('instance_ids', False)
        self.year = data['form'].get('year', False)
        self.month = data['form'].get('month', False)
        self.context = data.get('context', {})
        return super(account_liquidity_balance, self).set_context(objects, data, ids, report_type)

SpreadsheetReport('report.account.liquidity.balance', 'account.bank.statement',
                  'addons/account/report/account_liquidity_balance.mako', parser=account_liquidity_balance)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
