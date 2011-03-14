#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Author: Tempo Consulting (<http://www.tempo-consulting.fr/>), MSF
#    Developer: Olivier DOSSMANN
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

from osv import osv
from osv import fields
import time
from tools.translate import _

class cashbox_write_off(osv.osv_memory):
    _name = 'cashbox.write.off'

    _columns = {
        'choice' : fields.selection( (('writeoff', 'Accepting write-off and close CashBox'), ('reopen', 'Re-open CashBox')), \
            string="Decision about CashBox", required=True),
        'account_id': fields.many2one('account.account', string="Write-off Account"),
        'amount': fields.float(string="CashBox difference", digits=(16, 2), readonly=True),
    }

    def default_get(self, cr, uid, fields=None, context={}):
        """
        Return the difference between balance_end and balance_end_cash from the cashbox and diplay it in the wizard.
        """
        res = {}
        # Have we got any cashbox id ?
        if 'active_id' in context:
            # search values
            cashbox_id = context.get('active_id')
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, cashbox_id)
            amount = cashbox.balance_end - cashbox.balance_end_cash
            res.update({'amount': amount})
        return res

    def action_confirm_choice(self, cr, uid, ids, context={}):
        """
        Do what the user wants, but not coffee ! Just this : 
        - re-open the cashbox
        - do a write-off
        """
        id = context.get('active_id', False)
        if not id:
            raise osv.except_osv('Warning', 'You cannot decide about Cash Discrepancy without selecting any CashBox!')
        else:
            # search cashbox object
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, id)
            cstate = cashbox.state
            # What about cashbox state ?
            if cstate not in ['partial_close', 'confirm']:
                raise osv.except_osv('Warning', 'You cannot do anything as long as the CashBox has been closed!')
            # look at user choice
            choice = self.browse(cr,uid,ids)[0].choice
            if choice == 'reopen':
                # re-open case
                cashbox.write({'state': 'open'})
                return { 'type': 'ir.actions.act_window_close', 'res_id': id}
            elif choice == 'writeoff':
                # writing-off case
                if cstate != 'partial_close':
                    raise osv.except_osv('Warning', 'This option is only useful for CashBox with cash discrepancy!')
                    return False
                else:
                    account_id = self.browse(cr, uid, ids)[0].account_id.id
                    if account_id:
                        # Prepare some values
                        acc_mov_obj = self.pool.get('account.move')
                        move_line_obj = self.pool.get('account.move.line')
                        journal_id = cashbox.journal_id.id
                        period_id = cashbox.period_id.id
                        curr_date = time.strftime('%Y-%m-%d')
                        move_name = "writeoff" + "/" + curr_date
                        cash_difference = cashbox.balance_end - cashbox.balance_end_cash
                        account_debit_id = cashbox.journal_id.default_debit_account_id.id
                        account_credit_id = cashbox.journal_id.default_credit_account_id.id
                        currency_id = cashbox.currency.id
                        analytic_account_id = cashbox.journal_id.analytic_journal_id.id
                        # create an account move (a journal entry)
                        move_vals = {
                            'journal_id': journal_id,
                            'period_id': period_id,
                            'date': curr_date,
                            'name': move_name,
                        }
                        move_id = acc_mov_obj.create(cr, uid, move_vals, context=context)
                        # create attached account move lines
                        # first for the bank account
                        description = "writeoff" + '/' + curr_date
                        if cash_difference > 0:
                            # the cash difference is positive that's why we do a move from credit (for bank)
                            #+ and the opposite for the writeoff
                            bank_account_id = account_credit_id
                            bank_debit = 0.0
                            bank_credit = abs(cash_difference)
                        else:
                            bank_account_id = account_debit_id
                            bank_debit = abs(cash_difference)
                            bank_credit = 0.0
                        # move lines are the opposite of bank for the writeoff
                        writeoff_debit = bank_credit
                        writeoff_credit = bank_debit
                        # creating the bank account move line
                        bank_move_line_vals = {
                            'name': description,
                            'date': curr_date,
                            'move_id': move_id,
                            'account_id': bank_account_id,
                            'credit': bank_credit,
                            'debit': bank_debit,
                            'statement_id': id,
                            'journal_id': journal_id,
                            'period_id': period_id,
                            'currency_id': currency_id,
                            'analytic_account_id': analytic_account_id
                        }
                        bank_move_line_id = move_line_obj.create(cr, uid, bank_move_line_vals, context = context)
                        # then for the writeoff account
                        writeoff_move_line_vals = {
                            'name': description,
                            'date': curr_date,
                            'move_id': move_id,
                            'account_id': account_id,
                            'credit': writeoff_credit,
                            'debit': writeoff_debit,
                            'statement_id': id,
                            'journal_id': journal_id,
                            'period_id': period_id,
                            'currency_id': currency_id,
                            'analytic_account_id': analytic_account_id
                        }
                        writeoff_move_line_id = move_line_obj.create(cr, uid, writeoff_move_line_vals, context = context)
                        # Change cashbox state into "Closed"
                        cashbox.write({'state': 'confirm'})
                    else:
                        raise osv.except_osv(_('Warning'), _('Please select an account to do a write-off!'))
                return { 'type': 'ir.actions.act_window_close', 'res_id': id}
            else:
                raise osv.except_osv('Warning', 'An error has occured !')
        return { 'type': 'ir.actions.act_window_close', 'res_id': id}

cashbox_write_off()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
