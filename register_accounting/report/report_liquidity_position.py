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


class report_liquidity_position2(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(report_liquidity_position2, self).__init__(cr, uid, name,
                                                         context=context)
        self.res = 0
        self.cal = 0
        self.registers = {}
        self.funcCur = ''
        self.iter = []
        self.period_id = context.get('period_id', None)
        self.devices = {}
        self.cal_bal_subtotal = 0
        self.reg_bal_subtotal = 0
        self.cal_bal_total = 0
        self.reg_bal_total = 0
        self.localcontext.update({
            'getRegister': self.getRegister,
            'getConvert': self.getConvert,
            'getRes': self.getRes,
            'getCal': self.getCal,
            'getRegister2': self.getRegister2,
            'getFuncCur': self.getFuncCur,
            'getCurTot': self.getCurTot,
            'getFormula': self.getFormula,
            'getDevices': self.getDevices,
            'addAndprintCalBal': self.addAndprintCalBal,
            'addAndprintRegBal': self.addAndprintRegBal,
            'getSubtotalRegBal': self.getSubtotalRegBal,
            'getSubtotalCalBal': self.getSubtotalCalBal,
            'resetSubtotalBal': self.resetSubtotalBal,
            'getTotalRegBal': self.getTotalRegBal,
            'getTotalCalBal': self.getTotalCalBal,
            'addAndprintRegBal': self.addAndprintRegBal,
            'addAndprintRegBal': self.addAndprintRegBal,
        })
        return

    def getFormula(self):
        formul = ''
        iters = self.iter[1:]
        temp = self.iter[1:]
        tour = 1
        for _ in temp:
            tour += 1
            nb = 0
            for x in iters:
                nb += x + 2
            rang = nb + 2
            formul += '+R[-'+str(rang)+']C'
            iters = self.iter[tour:]
        return formul

    def getFuncCur(self,bro_ac):
        self.funcCur = bro_ac.journal_id and bro_ac.journal_id.company_id and bro_ac.journal_id.company_id.currency_id.name or ''
        return bro_ac.journal_id and bro_ac.journal_id.company_id and bro_ac.journal_id.company_id.currency_id.name or ''

    def getCurTot(self):
        return self.funcCur

    def getRes(self):
        temp = self.res
        self.res = 0
        return temp

    def getCal(self):
        temp = self.cal
        self.cal = 0
        return temp

    def getRegister2(self):
        return self.registers

    def getDevices(self):
        return self.devices

    def getRegister(self):
        ids = []
        pool = pooler.get_pool(self.cr.dbname)

        if self.period_id is None:
            sql_register_ids = """
                SELECT abs.id 
                FROM account_bank_statement abs
                LEFT JOIN account_journal aj ON abs.journal_id = aj.id
                WHERE aj.type != 'cheque' 
                AND abs.state != 'draft'
                AND abs.period_number = (SELECT max(abs2.period_number) 
                                           FROM account_bank_statement abs2
                                           LEFT JOIN account_journal aj2 ON abs2.journal_id = aj2.id
                                           WHERE aj2.type != 'cheque' AND abs2.state != 'draft'
                                           AND abs2.instance_id = abs.instance_id
                                           AND abs2.journal_id = abs.journal_id)
            """
        else:
            sql_register_ids = """
                SELECT abs.id 
                FROM account_bank_statement abs
                LEFT JOIN account_journal aj ON abs.journal_id = aj.id
                WHERE aj.type != 'cheque' 
                AND abs.state != 'draft'
                AND abs.period_number = """ + str(self.period_id)

        self.cr.execute(sql_register_ids)
        register_ids = [x[0] for x in self.cr.fetchall()]

        registers = {}
        devices = {}

        for register in pool.get('account.bank.statement').browse(self.cr, self.uid, register_ids):
            ids.append(register)
            if registers.has_key(register.instance_id.id):
                registers[register.instance_id.id] += [register]
            else:
                registers[register.instance_id.id] = [register]

            # US_336: parse uniques devices
            device_name = register.journal_id.currency.name
            current_instance = register.instance_id.id
            calc_bal = register.msf_calculated_balance
            reg_bal = 0
            if register.journal_id.type == 'cash':
                reg_bal = register.balance_end_cash
            elif register.journal_id.type == 'bank':
                reg_bal = register.balance_end_real

            if current_instance not in devices:
                devices[current_instance] = {}
            if device_name not in devices[current_instance]:
                devices[current_instance][device_name] = {'calc_bal': 0,
                                                        'reg_bal': 0}
            devices[current_instance][device_name]['calc_bal'] += calc_bal
            devices[current_instance][device_name]['reg_bal'] += reg_bal

        self.registers = registers
        self.devices = devices
        for x in registers:
            self.iter.append(len(registers[x]))

        return registers

    def getConvert(self,cur,func_cur,amount,option):
        conv = self.pool.get('res.currency').compute(self.cr, self.uid, cur.id, func_cur.id, amount or 0.0, round=True,)

        if option == 'cal':
            self.cal += 1
        elif option == 'reg':
            self.res += 1

        return float(conv)

    def addAndprintCalBal(self, balance):
        self.cal_bal_subtotal += balance
        self.cal_bal_total += balance
        return balance

    def addAndprintRegBal(self, balance):
        self.reg_bal_subtotal += balance
        self.reg_bal_total += balance
        return balance

    def getSubtotalRegBal(self):
        return self.reg_bal_subtotal

    def getSubtotalCalBal(self):
        return self.cal_bal_subtotal

    def resetSubtotalBal(self):
        self.cal_bal_subtotal = 0
        self.reg_bal_subtotal = 0

    def getTotalRegBal(self):
        return self.reg_bal_total

    def getTotalCalBal(self):
        return self.cal_bal_total

SpreadsheetReport('report.liquidity.position.2','account.bank.statement','addons/register_accounting/report/liquidity_position_xls.mako', parser=report_liquidity_position2)
report_sxw.report_sxw('report.liquidity.position.3', 'account.bank.statement', 'addons/register_accounting/report/liquidity_position_pdf.rml', parser=report_liquidity_position2)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
