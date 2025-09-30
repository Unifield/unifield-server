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
        self.currency_id = False
        self.fx_table_id = False
        self.sub_totals = False
        self.general_total = False
        self.context = {}
        super(account_liquidity_balance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_register_data': self._get_register_data,
            'get_subtotals' : self._get_subtotals,
            'get_general_total': self._get_general_total,
        })

    def _filter_journal_status(self, reg_data, date_from):
        """
        Applies the following changes to the reg_data:
        - adds the journal status
        - removes the lines for which the journal is inactive only if the Starting Balance, the Movements, and the Closing Balance are all 0.00
        """
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        last_open_reg_period = False
        new_reg_data = []
        for reg in reg_data:
            j_info = journal_obj.read(self.cr, self.uid, reg['id'], ['is_active', 'inactivation_date',
                                                                     'last_period_with_open_register_id'])
            if j_info and j_info['last_period_with_open_register_id']:
                last_open_reg_period = period_obj.browse(self.cr, self.uid, j_info['last_period_with_open_register_id'][0],
                                                 fields_to_fetch=['date_start', 'date_stop'], context=self.context)
            if (last_open_reg_period and last_open_reg_period.date_stop and last_open_reg_period.date_stop >= date_from) and \
                    (j_info['is_active'] or (j_info and j_info['inactivation_date'] and j_info['inactivation_date'] >= date_from) or\
                    reg['opening'] or reg['calculated'] or reg['closing']):
                # US-14182 Display the value of the status of the journal at the selected period
                if j_info['inactivation_date'] and j_info['inactivation_date'] > date_from:
                    reg['journal_status'] = _('Active')
                elif j_info['inactivation_date'] and j_info['inactivation_date'] < date_from:
                    reg['journal_status'] = _('Inactive')
                else:
                    reg['journal_status'] = j_info['is_active'] and _('Active') or _('Inactive')
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
        curr_rates = {}
        table_curr_rates = {}
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

        currency_id = self.currency_id
        if self.fx_table_id:
            # When the fx_table is used, the display currencies are mandatory and restricted to only those present in that fx_table,
            # so we can use the following simple query
            self.cr.execute("WITH fxtable_rate AS ("
                            "   (SELECT rcr.rate, rcr.name "
                            "    FROM res_currency curr, res_currency_rate rcr "
                            "    WHERE "
                            "       curr.currency_table_id = %s AND "
                            "       rcr.currency_id = %s AND"
                            "       rcr.name <= %s ORDER BY rcr.name desc LIMIT 1) "
                            "UNION "
                            "   (SELECT rcr.rate, rcr.name "
                            "    FROM res_currency curr, res_currency_rate rcr "
                            "    WHERE "
                            "       curr.currency_table_id = %s AND "
                            "       rcr.currency_id = %s AND"
                            "       rcr.name > %s AND "
                            "       rcr.name <= %s ORDER BY rcr.name asc LIMIT 1)) "
                            "SELECT rate FROM fxtable_rate ORDER BY name asc LIMIT 1 ",
                            (self.fx_table_id, self.currency_id, date_to, self.fx_table_id, self.currency_id, date_to, datetime.today().strftime('%Y-%m-%d')))

        elif self.currency_id and not self.fx_table_id:
            self.cr.execute(
                "SELECT currency_id, name, rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1",
                (currency_id, date_to))
        if self.currency_id:
            display_currency_rate = self.cr.dictfetchall()[0]

        period_title = self.period_title or ''
        # Cash and Bank registers
        reg_types = ('cash', 'bank')
        params = {
            'period_title': period_title,
            'j_type': reg_types,
            'date_from': date_from,
            'date_to': date_to,
            'instance_ids': tuple(self.instance_ids),
        }
        self.cr.execute(self.liquidity_sql, params)
        cash_bank_res = self.cr.dictfetchall()
        cash_bank_res = self._filter_journal_status(cash_bank_res, date_from)
        cash_bank_res = reportvi.hq_report_ocb.postprocess_liquidity_balances(self, self.cr, self.uid, cash_bank_res, context=self.context)
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
                    SELECT i.code AS instance, j.code, j.id, %(period_title)s AS period, req.opening, req.calculated, req.closing, 
                    c.name AS currency
                    FROM res_currency c,
                    (
                        SELECT journal_id, account_id, SUM(col1) AS opening, SUM(col2) AS calculated, SUM(col3) AS closing
                        FROM (
                            (
                            -- coo: export chq register empty
                                SELECT j.id AS journal_id, j.default_debit_account_id  AS account_id, 0 as col1, 0 as col2, 0 as col3
                                FROM account_bank_statement st, account_journal j, account_period p
                                WHERE
                                    st.journal_id = j.id
                                    AND st.period_id = p.id
                                    AND j.type = 'cheque'
                                    AND p.date_start >= %(date_from)s
                                    AND p.date_stop <= %(date_to)s
                                GROUP BY j.id, j.default_debit_account_id
                            )
                        UNION
                            (
                            -- hq: list cheque journal if a register has been created for the period selected
                                SELECT j.id AS journal_id, j.default_debit_account_id AS account_id, 0.00 as col1, 0.00 as col2, 0.00 as col3
                                FROM account_journal j, account_period p
                                WHERE
                                    j.type = 'cheque' AND
                                    j.last_period_with_open_register_id = p.id AND
                                    cast(date_trunc('month', j.create_date) as date) <= %(date_to)s AND
                                    p.date_stop >= %(date_from)s
                                GROUP BY j.id, j.default_debit_account_id
                            )
                        UNION
                            (
                                SELECT journal_id, account_id, ROUND(SUM(amount_currency), 2) as col1, 0.00 as col2, 0.00 as col3
                                FROM account_move_line
                                WHERE id IN %(pending_chq_starting_bal_ids)s
                                GROUP BY journal_id, account_id
                            )
                        UNION
                            (
                                SELECT journal_id, account_id, 0.00 as col1, 0.00 as col2, ROUND(SUM(amount_currency), 2) as col3
                                FROM account_move_line
                                WHERE id IN %(pending_chq_closing_bal_ids)s
                                GROUP BY journal_id, account_id
                            )
                        ) AS ssreq
                        GROUP BY journal_id, account_id
                        ORDER BY journal_id, account_id
                    ) AS req, account_journal j, msf_instance i
                    WHERE req.journal_id = j.id
                    AND j.instance_id = i.id
                    AND j.currency = c.id
                    AND j.instance_id IN %(instance_ids)s;
                    """
        # ensure not to have empty arrays to avoid crash at query execution...
        pending_chq_starting_bal_ids = pending_chq_starting_bal_ids or [-1]
        pending_chq_closing_bal_ids = pending_chq_closing_bal_ids or [-1]
        # cheque_params = (period_title, date_from, date_to, date_from, date_to, tuple(pending_chq_starting_bal_ids), tuple(pending_chq_closing_bal_ids), tuple(self.instance_ids))
        cheque_params = {
            'period_title': period_title,
            'date_from': date_from,
            'date_to': date_to,
            'pending_chq_starting_bal_ids': tuple(pending_chq_starting_bal_ids),
            'pending_chq_closing_bal_ids': tuple(pending_chq_closing_bal_ids),
            'instance_ids': tuple(self.instance_ids),
        }
        self.cr.execute(cheque_sql, cheque_params)
        cheque_res = self.cr.dictfetchall()
        cheque_res = self._filter_journal_status(cheque_res, date_from)
        cheque_res = reportvi.hq_report_ocb.postprocess_liquidity_balances(self, self.cr, self.uid, cheque_res, context=self.context)
        res.extend(cheque_res)
        # sort result by instance code and by journal code
        sorted_res = sorted(res, key=lambda k: (k['instance'], k['code']))
        # sum closing balances by booking currencies
        sub_totals = {}
        for i, register in enumerate(sorted_res):
            # Get the rate of current register currency
            if self.currency_id:
                register_currency_rate = False
                if self.fx_table_id:
                    if not table_curr_rates.get(self.fx_table_id, {}).get(register['currency'], False):
                        self.cr.execute(
                            "WITH fxtable_rate AS ("
                            "   (SELECT rcr.rate, rcr.name "
                            "    FROM res_currency curr, res_currency_rate rcr "
                            "    WHERE "
                            "       curr.name = %s AND "
                            "       curr.currency_table_id = %s AND "
                            "       rcr.currency_id = curr.id AND"
                            "       rcr.name <= %s ORDER BY rcr.name desc LIMIT 1) "
                            "UNION "
                            "   (SELECT rcr.rate, rcr.name "
                            "    FROM res_currency curr, res_currency_rate rcr "
                            "    WHERE "
                            "       curr.name = %s AND "
                            "       curr.currency_table_id = %s AND "
                            "       rcr.currency_id = curr.id AND"
                            "       rcr.name > %s AND "
                            "       rcr.name <= %s ORDER BY rcr.name asc LIMIT 1)) "
                            "SELECT rate FROM fxtable_rate ORDER BY name asc LIMIT 1 ",
                            (register['currency'], self.fx_table_id, date_to, register['currency'], self.fx_table_id, date_to,
                             datetime.today().strftime('%Y-%m-%d')))
                    else:
                        register_currency_rate = table_curr_rates.get(self.fx_table_id, {}).get(register['currency'], False)
                elif not curr_rates.get(register['currency'], False):
                    self.cr.execute(
                        "SELECT rcr.rate "
                        "FROM res_currency curr, res_currency_rate rcr "
                        "WHERE "
                        "   curr.name = %s AND "
                        "   curr.currency_table_id is Null AND"
                        "   rcr.currency_id = curr.id AND "
                        "   rcr.name <= %s ORDER BY rcr.name desc LIMIT 1",
                        (register['currency'], date_to))
                else:
                    register_currency_rate = curr_rates.get(register['currency'], False)
                if not register_currency_rate:
                    try:
                        register_currency_rate = self.cr.dictfetchall()
                        register_currency_rate = register_currency_rate[0]['rate']
                    except:
                        raise osv.except_osv(_('Error'), _('Could not find the rate of the display currency at date %s or in the currency table.') % (date_to))

                sorted_res[i].update({'output_value': register['closing'] / register_currency_rate * display_currency_rate['rate']})
                # Store currency rate in a cache to reduce query calls
                if self.fx_table_id:
                    if not table_curr_rates.get(self.fx_table_id, False):
                        table_curr_rates[self.fx_table_id] = {}
                    if not table_curr_rates[self.fx_table_id].get(register['currency'], False):
                        table_curr_rates[self.fx_table_id][register['currency']] = register_currency_rate
                else:
                    if not curr_rates.get(register['currency'], False):
                        curr_rates[register['currency']] = register_currency_rate

            if register['currency'] in sub_totals:
                sub_totals[register['currency']] ['closings'] += register['closing']
                if self.currency_id:
                    sub_totals[register['currency']]['output_value'] += register['output_value']
            else:
                sub_totals[register['currency']] = {}
                sub_totals[register['currency']]['closings'] = register['closing']
                if self.currency_id:
                    sub_totals[register['currency']]['output_value'] = register['output_value']
        self.sub_totals = sub_totals
        if self.currency_id:
            self.general_total = sum([subtotal.get('output_value') for subtotal in sub_totals.values()])

        return sorted_res

    def _get_subtotals(self):
        # Default dict with 7 key-value pairs to fix the error when a register is empty
        # With 7 being the number of cells in the subtotals part of the pdf liquidity balance report
        default_subtotals = {'':{} for key in range(7)}
        return self.sub_totals or default_subtotals

    def _get_general_total(self):
        return self.general_total


    def set_context(self, objects, data, ids, report_type=None):
        # get the selection made by the user
        self.period_id = data['form'].get('period_id', False)
        self.date_from = data['form'].get('date_from', False)
        self.date_to = data['form'].get('date_to', False)
        self.instance_ids = data['form'].get('instance_ids', False)
        self.period_title = data['form'].get('period_title', False)
        self.currency_id = data['form'].get('currency_id', False)
        self.fx_table_id = data['form'].get('fx_table_id', False)
        self.context = data.get('context', {})
        return super(account_liquidity_balance, self).set_context(objects, data, ids, report_type)

# XLS Report
SpreadsheetReport('report.account.liquidity.balance', 'account.bank.statement',
                  'addons/account/report/account_liquidity_balance.mako', parser=account_liquidity_balance)
# PDF report
report_sxw.report_sxw('report.account.liquidity.balance.pdf', 'account.bank.statement',
                      'addons/account/report/account_liquidity_balance.rml',parser=account_liquidity_balance,
                      header='internal landscape')
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
