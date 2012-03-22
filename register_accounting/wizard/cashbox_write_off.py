#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
        'choice' : fields.selection( [('writeoff', 'Accept write-off and close register'), ('reopen', 'Re-open Register')], \
            string="Decision about CashBox", required=True),
        'account_id': fields.many2one('account.account', string="Write-off Account"),
        'amount': fields.float(string="CashBox difference", digits=(16, 2), readonly=True),
    }

    def default_get(self, cr, uid, fields=None, context={}):
        """
        Return the difference between balance_end and balance_end_cash from the cashbox and diplay it in the wizard.
        """
        res = super(cashbox_write_off, self).default_get(cr, uid, fields, context=context)
        # Have we got any cashbox id ?
        if 'active_id' in context:
            # search values
            cashbox_id = context.get('active_id')
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, cashbox_id)
            amount = cashbox.balance_end - cashbox.balance_end_cash
            res.update({'amount': amount})
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Define elements for two case:
         - when raising an error : give a wizard with some information
         - other case : give the normal wizard
        """
        res = {}
        res = super(cashbox_write_off, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if 'active_id' in context:
            # search values
            cashbox_id = context.get('active_id')
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, cashbox_id)
            if cashbox.state not in ['partial_close', 'confirm']:
                raise osv.except_osv(_('Warning'), _("Please use 'Close CashBox' button before."))
        return res

    def action_confirm_choice(self, cr, uid, ids, context={}):
        """
        Do what the user wants, but not coffee ! Just this : 
        - re-open the cashbox
        - do a write-off
        """
        id = context.get('active_id', False)
        if not id:
            raise osv.except_osv(_('Warning'), _('You cannot decide about Cash Discrepancy without selecting any CashBox!'))
        else:
            # search cashbox object
            cashbox = self.pool.get('account.bank.statement').browse(cr, uid, id)
            cstate = cashbox.state
            # What about cashbox state ?
            if cstate not in ['partial_close', 'confirm']:
                raise osv.except_osv(_('Warning'), _('You cannot do anything as long as the "Close CashBox" button has not been used.'))
            # look at user choice
            choice = self.browse(cr,uid,ids)[0].choice
            if choice == 'reopen':
                if cstate not in ['partial_close']:
                    raise osv.except_osv(_('Warning'), _('You cannot re-open a Closed Register.'))
                # re-open case
                cashbox.write({'state': 'open'})
                return { 'type': 'ir.actions.act_window_close', 'res_id': id}
            elif choice == 'writeoff':
                # writing-off case
                if cstate != 'partial_close':
                    raise osv.except_osv(_('Warning'), _('This option is only useful for CashBox with cash discrepancy!'))
                    return False
                else:
                    account_id = self.browse(cr, uid, ids)[0].account_id.id
                    if account_id:
                        # Prepare some values
                        acc_mov_obj = self.pool.get('account.move')
                        move_line_obj = self.pool.get('account.move.line')
                        journal_id = cashbox.journal_id.id
                        curr_date = time.strftime('%Y-%m-%d')
                        date = cashbox.period_id.date_stop
                        period_id = cashbox.period_id.id
                        cash_period = cashbox.period_id.date_start
                        desc_period = time.strftime('%Y%m', time.strptime(cash_period, '%Y-%m-%d'))
                        # description = register period (YYYYMM) + "-" + register code + " " + "Write-off"
                        description = "" + desc_period[:6] + "-" + cashbox.name + " " + "Write-off"
                        cash_difference = cashbox.balance_end - cashbox.balance_end_cash
                        account_debit_id = cashbox.journal_id.default_debit_account_id.id
                        account_credit_id = cashbox.journal_id.default_credit_account_id.id
                        currency_id = cashbox.currency.id
                        analytic_account_id = False
                        # search analytic account used for FX gain/loss
                        search_ids = self.pool.get('account.analytic.account').search(cr, uid, [('for_fx_gain_loss', '=', True)])
                        if not search_ids:
                            raise osv.except_osv(_('Warning'), _('No FX gain/loss analytic account defined!'))
                        # create an analytic distribution
                        distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context={})
                        # add a cost center for analytic distribution
                        distrib_line_vals = {
                            'distribution_id': distrib_id,
                            'currency_id': cashbox.company_id.currency_id.id,
                            'analytic_id': search_ids[0],
                            'percentage': 100.0,
                            'date': date,
                            'source_date': date,
                        }
                        cc_id = self.pool.get('cost.center.distribution.line').create(cr, uid, distrib_line_vals, context=context)
                        # add a funding pool line for analytic distribution
                        try:
                            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                        except ValueError:
                            fp_id = 0
                        if not fp_id:
                            raise osv.except_osv(_('Error'), _('No analytic account named "MSF Private Fund" found!'))
                        distrib_line_vals.update({'analytic_id': fp_id, 'cost_center_id': search_ids[0]})
                        self.pool.get('funding.pool.distribution.line').create(cr, uid, distrib_line_vals, context=context)
                        # create an account move (a journal entry)
                        move_vals = {
                            'journal_id': journal_id,
                            'period_id': period_id,
                            'date': date,
                            'name': description,
                        }
                        move_id = acc_mov_obj.create(cr, uid, move_vals, context=context)
                        # create attached account move lines
                        # first for the bank account
                        # make a verification that no other currency is choose
                        # if another currency is applied on the journal, then we do a calculation of the new amount
                        amount = False
                        if currency_id != cashbox.company_id.currency_id.id:
                            res_currency_obj = self.pool.get('res.currency')
                            amount = res_currency_obj.compute(cr, uid, currency_id, cashbox.company_id.currency_id.id, cash_difference, context=context)
                        if cash_difference > 0:
                            # the cash difference is positive that's why we do a move from credit (for bank)
                            #+ and the opposite for the writeoff
                            bank_account_id = account_credit_id
                            bank_debit = 0.0
                            bank_credit = abs(cash_difference)
                            if amount:
                                bank_credit = abs(amount) # if another currency
                        else:
                            bank_account_id = account_debit_id
                            bank_debit = abs(cash_difference)
                            if amount:
                                bank_debit = abs(amount) # if another currency
                            bank_credit = 0.0
                        # move lines are the opposite of bank for the writeoff
                        writeoff_debit = bank_credit
                        writeoff_credit = bank_debit
                        # create the bank account move line
                        bank_move_line_vals = {
                            'name': description,
                            'date': date,
                            'move_id': move_id,
                            'account_id': bank_account_id,
                            'credit': bank_credit,
                            'debit': bank_debit,
                            'statement_id': cashbox.id,
                            'journal_id': journal_id,
                            'period_id': period_id,
                            'currency_id': currency_id,
                            'analytic_account_id': analytic_account_id
                        }
                        # add an amount currency if the currency is different from company currency
                        if amount and bank_credit > 0:
                            bank_amount = -abs(cash_difference)
                            bank_move_line_vals.update({'amount_currency': bank_amount})
                        elif amount and bank_debit > 0:
                            bank_amount = abs(cash_difference)
                            bank_move_line_vals.update({'amount_currency': bank_amount})
                        bank_move_line_id = move_line_obj.create(cr, uid, bank_move_line_vals, context = context)
                        # then for the writeoff account
                        writeoff_move_line_vals = {
                            'name': description,
                            'date': date,
                            'move_id': move_id,
                            'account_id': account_id,
                            'credit': writeoff_credit,
                            'debit': writeoff_debit,
                            'statement_id': cashbox.id,
                            'journal_id': journal_id,
                            'period_id': period_id,
                            'currency_id': currency_id,
                            'analytic_account_id': analytic_account_id,
                            'analytic_distribution_id': distrib_id,
                        }
                        # add an amount currency if the currency is different from company currency
                        if amount:
                            writeoff_move_line_vals.update({'amount_currency': -bank_amount})
                        writeoff_move_line_id = move_line_obj.create(cr, uid, writeoff_move_line_vals, context = context)
                        # Make the write-off in posted state
                        res_move_id = acc_mov_obj.write(cr, uid, [move_id], {'state': 'posted'}, context=context)
                        # Change cashbox state into "Closed"
                        cashbox.write({'state': 'confirm', 'closing_date': curr_date})
                    else:
                        raise osv.except_osv(_('Warning'), _('Please select an account to do a write-off!'))
                return { 'type': 'ir.actions.act_window_close', 'res_id': id}
            else:
                raise osv.except_osv(_('Warning'), _('An error has occured !'))
        return { 'type': 'ir.actions.act_window_close', 'res_id': id}

cashbox_write_off()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
