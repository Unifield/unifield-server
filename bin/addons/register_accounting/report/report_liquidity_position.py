# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import pooler
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


class report_liquidity_position3(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_liquidity_position3, self).__init__(cr, uid, name,
                                                         context=context)
        self.period_id = context.get('period_id', None)
        self.registers = {}
        self.func_currency = {}
        self.pending_cheques = {}
        self.revaluation_lines = {}
        self.func_currency_id = 0
        self.total_func_calculated_balance = 0
        self.total_func_register_balance = 0
        self.grand_total_reg_currency = {}

        self.localcontext.update({
            'getRegistersByType': self.getRegistersByType,
            'getPeriod': self.getPeriod,
            'getFuncCurrency': self.getFuncCurrency,
            'getTotalCalc': self.getTotalCalc,
            'getTotalReg': self.getTotalReg,
            'getReg': self.getRegisters,
            'getConvert': self.getConvert,
            'getOpeningBalance': self.getOpeningBalance,
            'getPendingCheques': self.getPendingCheques,
            'getSortedJournals': self.getSortedJournals,
            'getGrandTotalRegCurrency': self.getGrandTotalRegCurrency,
            'getRevaluationLines': self.getRevaluationLines,
        })
        return

    def getTotalReg(self):
        return self.total_func_register_balance

    def getTotalCalc(self):
        return self.total_func_calculated_balance

    def getRegisters(self):
        return self.registers

    def getFuncCurrency(self):
        return self.func_currency

    def getPeriod(self):
        return self.pool.get('account.period').browse(self.cr, self.uid, self.period_id, context={'lang': self.localcontext.get('lang')})

    def getConvert(self, cur_id, amount, report_period=None):
        '''
        Returns the amount converted from the currency whose id is in parameter into the functional currency
        '''
        currency = self.pool.get('res.currency').browse(self.cr, self.uid, cur_id)
        rate = 1
        # get the correct exchange rate according to the report period
        if not report_period:
            report_period = self.getPeriod()
        self.cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s "
                        "ORDER BY name DESC LIMIT 1;", (cur_id, report_period.date_stop))
        if self.cr.rowcount != 0:
            rate = self.cr.fetchone()[0]
        converted_amount = amount / rate
        rounding = currency.rounding or False
        if rounding:
            converted_amount = round(converted_amount / rounding) * rounding
        return converted_amount

    def getSortedJournals(self):
        """
        Returns the list of the ids of the Cheque Journals to display sorted in alphabetical order of code
        """
        journal_obj = self.pool.get('account.journal')
        journals = journal_obj.browse(self.cr, self.uid, list(self.getPendingCheques()['registers'].keys()), fields_to_fetch=['code'])
        return [journal.id for journal in sorted(journals, key=lambda j: j.code)]

    def getRegistersByType(self):
        reg_types = {}
        total_func_calculated_balance = 0
        total_func_register_balance = 0

        pool = pooler.get_pool(self.cr.dbname)
        reg_obj = pool.get('account.bank.statement')
        journal_obj = pool.get('account.journal')
        # bank and cash journals (for cheques, see getPendingCheques)
        journal_ids = journal_obj.search(self.cr, self.uid, [('type', 'in', ['bank', 'cash'])], order='NO_ORDER')
        args = [('period_id', '=', self.period_id), ('journal_id', 'in', journal_ids)]
        reg_ids = reg_obj.search(self.cr, self.uid, args, order='journal_id')
        regs = reg_obj.browse(self.cr, self.uid, reg_ids, context={'lang': self.localcontext.get('lang')})

        func_curr = self.pool.get('res.users').browse(self.cr, self.uid, self.uid, fields_to_fetch=['company_id']).company_id.currency_id
        self.func_currency = func_curr.name
        self.func_currency_id = func_curr.id
        for reg in regs:
            journal = reg.journal_id
            currency = journal.currency

            # ##############
            # INITIALISATION
            # ##############

            # Create register type
            if journal.type not in reg_types:
                reg_types[journal.type] = {
                    'registers': [],
                    'currency_amounts': {},
                    'func_amount_calculated': 0,
                    'func_amount_balanced': 0
                }
            # Create currency values
            if currency.name not in reg_types[journal.type]['currency_amounts']:
                reg_types[journal.type]['currency_amounts'][currency.name] = {
                    'amount_calculated': 0,
                    'amount_balanced': 0,
                    'id': currency.id
                }

            # ###########
            # Calculation
            # ###########

            # Calcul amounts
            reg_bal = 0
            calc_bal = reg.msf_calculated_balance
            func_calc_bal = self.getConvert(currency.id, calc_bal)
            if reg.journal_id.type == 'bank':
                reg_bal = reg.balance_end_real

            elif reg.journal_id.type == 'cash':
                reg_bal = reg.balance_end_cash

            func_reg_bal = self.getConvert(currency.id, reg_bal)

            # Add register to list
            reg_types[journal.type]['registers'].append({
                'instance': reg.instance_id.name,
                'journal_code': journal.code,
                'journal_name': journal.name,
                'state': reg.state and self.getSel(reg, 'state') or '',
                'calculated_balance': calc_bal,
                'register_balance': reg_bal,
                'opening_balance': reg.balance_start,
                'currency': journal.currency.name,
                'func_calculated_balance': func_calc_bal,
                'func_register_balance': func_reg_bal
            })

            # Add register types amounts
            reg_types[journal.type]['func_amount_calculated'] += func_calc_bal
            reg_types[journal.type]['func_amount_balanced'] += func_reg_bal

            # Add currency amounts
            reg_types[reg.journal_id.type]['currency_amounts'][currency.name]['amount_calculated'] += calc_bal
            reg_types[reg.journal_id.type]['currency_amounts'][currency.name]['amount_balanced'] += reg_bal

            # Add the amount in register currency to the Grand Total for all register types
            if currency.name not in self.grand_total_reg_currency:
                self.grand_total_reg_currency[currency.name] = 0
            self.grand_total_reg_currency[currency.name] += calc_bal

            # Add totals functionnal amounts
            total_func_calculated_balance += func_calc_bal
            total_func_register_balance += func_reg_bal
            self.registers = reg_types

        self.total_func_calculated_balance = total_func_calculated_balance
        self.total_func_register_balance = total_func_register_balance
        return reg_types

    def getOpeningBalance(self, reg_type, cur):
        '''
        Returns the TOTAL of starting balance for the register type and the currency in parameters
        '''
        reg_data = self.getRegisters()[reg_type]['registers']
        return sum([line['opening_balance'] or 0.0 for line in reg_data if line['currency'] == cur])

    def getRegisterState(self, reg, report_period_id=None):
        '''
        Returns the register state (String) for the period of the report.
        If the register doesn't exist for this period, returns 'Not Created'.
        '''
        pool = pooler.get_pool(self.cr.dbname)
        reg_obj = pool.get('account.bank.statement')
        if not report_period_id:
            report_period_id = self.period_id
        reg_for_selected_period_id = reg_obj.search(self.cr, self.uid, [('journal_id', '=', reg.journal_id.id),
                                                                        ('period_id', '=', report_period_id)])
        if reg_for_selected_period_id:
            reg_for_selected_period = reg_obj.browse(self.cr, self.uid, reg_for_selected_period_id)[0]
            state = reg_for_selected_period.state and self.getSel(reg_for_selected_period, 'state') or ''
        else:
            state = _('Not Created')
        return state

    def getRevaluationLines(self):
        """
        Returns a dict with key = currency, and value = dict of the data to display for the revaluation entries in this currency.
        Entries taken into account are: booked in the Revaluation journal of the current instance, on the accounts used
        for Cheque Registers, with a Posting date in the selected period or before, and not fully reconciled.
        """
        if not self.revaluation_lines:
            pool = pooler.get_pool(self.cr.dbname)
            journal_obj = pool.get('account.journal')
            aml_obj = pool.get('account.move.line')
            journal_ids = journal_obj.search(self.cr, self.uid, [('type', '=', 'revaluation'),
                                                                 ('is_current_instance', '=', True)], order='NO_ORDER')
            aml_domain = [('journal_id', 'in', journal_ids),
                          ('date', '<=', self.getPeriod().date_stop),
                          ('reconcile_id', '=', False)]
            cheque_journal_ids = journal_obj.search(self.cr, self.uid, [('type', '=', 'cheque'),
                                                                        ('is_current_instance', '=', True)], limit=1)
            if cheque_journal_ids:
                cheque_journal = journal_obj.browse(self.cr, self.uid, cheque_journal_ids[0],
                                                    fields_to_fetch=['default_debit_account_id', 'default_credit_account_id'])
                account_ids = [cheque_journal.default_debit_account_id.id, cheque_journal.default_credit_account_id.id]
                aml_domain.append(('account_id', 'in', account_ids))
            aml_ids = aml_obj.search(self.cr, self.uid, aml_domain, order='NO_ORDER')
            revaluation_lines = {}
            fields_list = ['currency_id', 'journal_id', 'debit_currency', 'credit_currency', 'debit', 'credit']
            for aml in aml_obj.browse(self.cr, self.uid, aml_ids, fields_to_fetch=fields_list):
                curr = aml.currency_id and aml.currency_id.name or ''
                if curr not in revaluation_lines:
                    revaluation_lines[curr] = {}
                    # initialize amounts
                    revaluation_lines[curr]['booking_amount'] = 0.0
                    revaluation_lines[curr]['functional_amount'] = 0.0
                    # same Prop. instance and journal for all entries
                    revaluation_lines[curr]['prop_instance'] = aml.journal_id.instance_id.name
                    revaluation_lines[curr]['journal_code'] = aml.journal_id.code
                    revaluation_lines[curr]['journal_name'] = aml.journal_id.name
                revaluation_lines[curr]['booking_amount'] += (aml.debit_currency or 0.0) - (aml.credit_currency or 0.0)
                revaluation_lines[curr]['functional_amount'] += (aml.debit or 0.0) - (aml.credit or 0.0)
            self.revaluation_lines = revaluation_lines
        return self.revaluation_lines

    def _update_totals_with_revaluation_lines(self, pending_cheques):
        """
        Adds the revaluation lines values to:
        - Pending Cheques subtotals per currency
        - Total Cheque
        - Grand Total Register per currency
        """
        for rev_cur in self.getRevaluationLines():
            rev_fctal = self.getRevaluationLines()[rev_cur]['functional_amount'] or 0.0
            rev_booking = self.getRevaluationLines()[rev_cur]['booking_amount'] or 0.0
            if rev_cur not in pending_cheques['currency_amounts']:
                pending_cheques['currency_amounts'][rev_cur] = {
                    'total_amount_reg_currency': 0.0,
                    'total_amount_func_currency': 0.0,
                }
            pending_cheques['currency_amounts'][rev_cur]['total_amount_reg_currency'] += rev_booking
            pending_cheques['currency_amounts'][rev_cur]['total_amount_func_currency'] += rev_fctal
            pending_cheques['total_cheque'] += rev_fctal
            if rev_cur not in self.grand_total_reg_currency:
                self.grand_total_reg_currency[rev_cur] = 0.0
            self.grand_total_reg_currency[rev_cur] += rev_booking

    def getPendingCheques(self):
        '''
        Get the pending cheques data from the selected period AND the previous ones. Gives:
        - one entry per journal: the pending cheques amounts are all added (the period displayed only indicates if
        the register has been closed).
        - the total amounts per currency in register and functional currency
        - the global total in functional currency
        '''
        if self.pending_cheques:
            return self.pending_cheques
        pending_cheques = {
            'registers': {},
            'currency_amounts': {},
            'total_cheque': 0.0,
        }
        pool = pooler.get_pool(self.cr.dbname)
        reg_obj = pool.get('account.bank.statement')
        aml_obj = pool.get('account.move.line')
        journal_obj = pool.get('account.journal')
        period_obj = pool.get('account.period')

        # get the cheque registers for the selected period and previous ones IF the one of the selected period exists
        journal_ids = []
        for j_id in journal_obj.search(self.cr, self.uid, [('type', '=', 'cheque')], order='NO_ORDER'):
            if reg_obj.search_exist(self.cr, self.uid, [('journal_id', '=', j_id), ('period_id', '=', self.period_id)]):
                journal_ids.append(j_id)
        period_ids = period_obj.search(self.cr, self.uid,
                                       [('date_start', '<=', self.getPeriod().date_start)])
        reg_ids = reg_obj.search(self.cr, self.uid, [('journal_id', 'in', journal_ids),
                                                     ('period_id', 'in', period_ids)])
        regs = reg_obj.browse(self.cr, self.uid, reg_ids, context={'lang': self.localcontext.get('lang')})

        for reg in regs:
            # Search register lines
            journal = reg.journal_id
            account_ids = [journal.default_debit_account_id.id, journal.default_credit_account_id.id]
            # include in the report only the JIs that are either not reconciled,
            # or reconciled (totally or partially) with at least one entry belonging to a later period
            aml_ids = reg_obj.get_pending_cheque_ids(self.cr, self.uid, [reg.id], account_ids, self.getPeriod().date_stop)
            lines = aml_obj.browse(self.cr, self.uid, aml_ids)

            # Get the amounts in booking and functional currency
            amount_reg_currency = sum([line.debit_currency - line.credit_currency or 0.0 for line in lines])
            amount_func_currency = sum([line.debit - line.credit or 0.0 for line in lines])

            # either create a new entry for this journal, or if it already exists (= there are pending cheques in several
            # periods for this journal) add the amounts to the previous total
            if journal.id not in pending_cheques['registers']:
                pending_cheques['registers'][journal.id] = {
                    'instance': reg.instance_id.name,
                    'journal_code': journal.code,
                    'journal_name': journal.name,
                    'state': self.getRegisterState(reg),
                    'bank_journal_code': journal.bank_journal_id.code,
                    'bank_journal_name': journal.bank_journal_id.name,
                    'amount_reg_currency': amount_reg_currency,
                    'reg_currency': journal.currency.name,
                    'amount_func_currency': amount_func_currency,
                }
            else:
                pending_cheques['registers'][journal.id]['amount_reg_currency'] += amount_reg_currency
                pending_cheques['registers'][journal.id]['amount_func_currency'] += amount_func_currency

            # Add amounts to get the total amounts per currency
            if journal.currency.name not in pending_cheques['currency_amounts']:
                pending_cheques['currency_amounts'][journal.currency.name] = {
                    'total_amount_reg_currency': 0,
                    'total_amount_func_currency': 0
                }
            pending_cheques['currency_amounts'][journal.currency.name]['total_amount_reg_currency'] += amount_reg_currency
            pending_cheques['currency_amounts'][journal.currency.name]['total_amount_func_currency'] += amount_func_currency

            # Add the amount in register currency to the Grand Total for all register types
            # (note that it is technically possible to have pending cheques in a currency for which
            # no bank register is open yet for the period)
            if journal.currency.name not in self.grand_total_reg_currency:
                self.grand_total_reg_currency[journal.currency.name] = 0
            self.grand_total_reg_currency[journal.currency.name] += amount_reg_currency

            # Add amount to get the "global" Total for all currencies (in functional currency)
            pending_cheques['total_cheque'] += amount_func_currency
        self._update_totals_with_revaluation_lines(pending_cheques)
        self.pending_cheques = pending_cheques
        return pending_cheques

    def getGrandTotalRegCurrency(self):
        return self.grand_total_reg_currency


SpreadsheetReport('report.liquidity.position.2', 'account.bank.statement', 'addons/register_accounting/report/liquidity_position_xls.mako', parser=report_liquidity_position3)
report_sxw.report_sxw('report.liquidity.position.pdf', 'account.bank.statement', 'addons/register_accounting/report/liquidity_position_pdf.rml', header=False, parser=report_liquidity_position3)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
