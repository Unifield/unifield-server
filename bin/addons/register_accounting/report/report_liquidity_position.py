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


class report_liquidity_position3(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_liquidity_position3, self).__init__(cr, uid, name,
                                                         context=context)
        self.period_id = context.get('period_id', None)
        self.registers = {}
        self.func_currency = {}
        self.func_currency_id = 0
        self.total_func_calculated_balance = 0
        self.total_func_register_balance = 0

        self.localcontext.update({
            'getRegistersByType': self.getRegistersByType,
            'getPeriod': self.getPeriod,
            'getFuncCurrency': self.getFuncCurrency,
            'getFuncCurrencyId': self.getFuncCurrencyId,
            'getTotalCalc': self.getTotalCalc,
            'getTotalReg': self.getTotalReg,
            'getReg': self.getRegisters,
            'getConvert': self.getConvert,
            'getOpeningBalance': self.getOpeningBalance,
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

    def getFuncCurrencyId(self):
        return self.func_currency_id

    def getPeriod(self):
        return self.pool.get('account.period').browse(self.cr, self.uid, self.period_id, context={'lang': self.localcontext.get('lang')})

    def getConvert(self, cur_id, func_cur_id, amount):
        cur_ovj = self.pool.get('res.currency')
        conv = cur_ovj.compute(self.cr, self.uid, cur_id,
                               func_cur_id, amount or 0.0, round=True)
        return float(conv)

    def getRegistersByType(self):
        reg_types = {}
        total_func_calculated_balance = 0
        total_func_register_balance = 0

        pool = pooler.get_pool(self.cr.dbname)
        reg_obj = pool.get('account.bank.statement')
        args = [('period_id', '=', self.period_id)]
        reg_ids = reg_obj.search(self.cr, self.uid, args)
        regs = reg_obj.browse(self.cr, self.uid, reg_ids, context={'lang': self.localcontext.get('lang')})

        self.func_currency = regs[0].journal_id.company_id.currency_id.name
        self.func_currency_id = regs[0].journal_id.company_id.currency_id.id
        for reg in regs:

            journal = reg.journal_id
            currency = journal.currency

            # For Now, check are ignored
            if journal.type == 'cheque':
                continue

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
            func_calc_bal = self.getConvert(currency.id,
                                            journal.company_id.currency_id.id,
                                            calc_bal)
            if reg.journal_id.type == 'bank':
                reg_bal = reg.balance_end_real

            elif reg.journal_id.type == 'cash':
                reg_bal = reg.balance_end_cash

            func_reg_bal = self.getConvert(currency.id,
                                           journal.company_id.currency_id.id,
                                           reg_bal)

            # Add register to list
            reg_types[journal.type]['registers'].append({
                'instance': reg.instance_id.name,
                'journal_code': journal.code,
                'journal_name': journal.name,
                # for the state, get the value from the selection field ("Closed" instead of "confirm", etc.):
                'state': reg.state and dict(reg_obj._columns['state'].selection).get(reg.state) or '',
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

            # Add totals functionnal amounts
            total_func_calculated_balance += func_calc_bal
            total_func_register_balance += func_reg_bal
            self.registers = reg_types

        self.total_func_calculated_balance = total_func_calculated_balance
        self.total_func_register_balance = total_func_register_balance
        return reg_types

    def getOpeningBalance(self, reg_type, cur):
        '''
        Returns the TOTAL of opening balance for the register type and the currency in parameters
        '''
        reg_data = self.getRegisters()[reg_type]['registers']
        return sum([line['opening_balance'] or 0.0 for line in reg_data if line['currency'] == cur])


SpreadsheetReport('report.liquidity.position.2', 'account.bank.statement', 'addons/register_accounting/report/liquidity_position_xls.mako', parser=report_liquidity_position3)
report_sxw.report_sxw('report.liquidity.position.pdf', 'account.bank.statement', 'addons/register_accounting/report/liquidity_position_pdf.rml', header=False, parser=report_liquidity_position3)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
