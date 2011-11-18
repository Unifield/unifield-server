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
from tools.translate import _
import time

class account_move_line_reconcile(osv.osv_memory):
    _inherit = 'account.move.line.reconcile'
    _name = 'account.move.line.reconcile'

    _columns = {
        'state': fields.selection([('total', 'Full Reconciliation'), ('partial', 'Partial Reconciliation')], string="State", 
            required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'total',
    }

    def _get_addendum_line_account_id(self, cr, uid, ids, context={}):
        """
        Give addendum line account id.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Retrieve 6308 account
        account_id = self.pool.get('account.account').search(cr, uid, [('code', '=', '6308')], context=context, limit=1)
        return account_id and account_id[0] or False

    def default_get(self, cr, uid, fields, context={}):
        """
        Add state field in res
        """
        # Some verifications
        if not context:
            context = {}
        # Default value
        res = super(account_move_line_reconcile, self).default_get(cr, uid, fields, context=context)
        # Retrieve some value
        data = self.trans_rec_get(cr, uid, context['active_ids'], context=context)
        # Update res with state value
        if 'state' in fields and 'state' in data:
            res.update({'state': data['state']})
        return res

    def trans_rec_get(self, cr, uid, ids, context={}):
        """
        Change default method:
        - take debit_currency and credit_currency instead of debit and credit (this is to pay attention to Booking Currency)
        - add some values:
          - state: if write off is 0.0, then 'total' else 'partial'
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        account_move_line_obj = self.pool.get('account.move.line')
        credit = debit = 0
        state = 'partial'
        account_id = False
        count = 0
        # Browse all lines
        prev_acc_id = None
        prev_third_party = None
        for line in account_move_line_obj.browse(cr, uid, context['active_ids'], context=context):
            # prepare some values
            account_id = line.account_id.id
            # some verifications
            if not line.account_id.reconcile:
                raise osv.except_osv(_('Warning'), _('This account is not reconciliable: %s' % line.account_id.code))
            # verification that there's only one account for each line
            if not prev_acc_id:
                prev_acc_id = account_id
            if prev_acc_id != account_id:
                raise osv.except_osv(_('Error'), _('An account is different from others: %s' % line.account_id.code))
            # verification that there's only one 3rd party
            # FIXME: This 3rd party verification should be desactivated in case of transfer with change
            if not prev_third_party:
                prev_third_party = line.partner_txt
            if prev_third_party != line.partner_txt:
                raise osv.except_osv(_('Error'), _('A third party is different from others: %s' % line.partner_txt))
            # process necessary elements
            if not line.reconcile_id and not line.reconcile_id.id:
                count += 1
                credit += line.credit_currency
                debit += line.debit_currency
            # FIXME: Do currency verification and change wizard state regarding currency: In case of transfer with change then state is 
            #+ 'total_change' or 'partial_change'
        # Adapt state value
        if (debit - credit) == 0.0:
            state = 'total'
        return {'trans_nbr': count, 'account_id': account_id, 'credit': credit, 'debit': debit, 'writeoff': debit - credit, 'state': state}

    def total_reconcile(self, cr, uid, ids, context={}):
        """
        Do a total reconciliation for given active_ids in context.
        Add another line to reconcile if some gain/loss of rate recalculation.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        addendum_line = False
        to_reconcile = context['active_ids']
        ml_obj = self.pool.get('account.move.line')
        # Verify that balance in fonctional currency (debit/credit ) is correct, otherwise activate addendum_line
        total = ml_obj._accounting_balance(cr, uid, context['active_ids'], context=context)[0]
        if total != 0.0:
            addendum_line = True
        # Search first line for some values
        first_line = ml_obj.browse(cr, uid, [context['active_ids'][0]], context=context)[0]
        # Retrieve some values
        account_id = first_line.account_id and first_line.account_id.id or False
        # those for third party for an example
        partner_id = first_line.partner_id and first_line.partner_id.id or False
        employee_id = first_line.employee_id and first_line.employee_id.id or False
        register_id = first_line.register_id and first_line.register_id.id or False
        if addendum_line:
            # Get default account for addendum_line
            addendum_line_account_id = self._get_addendum_line_account_id(cr, uid, ids, context=context)
            # Prepare some values
            date = time.strftime('%Y-%m-%d')
            j_obj = self.pool.get('account.journal')
            # Search Miscellaneous Transactions journal
            j_ids = j_obj.search(cr, uid, [('type', '=', 'general'), ('code', '=', 'MT'), ('name', '=', 'Miscellaneous Transactions')], context=context)
            if not j_ids:
                raise osv.except_osv(_('Error'), ('No Miscellaneous Transactions journal found!'))
            journal_id = j_ids[0]
            # Search attached period
            period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)], context=context, 
                limit=1, order='date_start, name')
            if not period_ids:
                raise osv.except_osv(_('Error'), _('No attached period found or current period not open!'))
            period_id = period_ids[0]
            # Create a new move
            move_id = self.pool.get('account.move').create(cr, uid,{'journal_id': journal_id, 'period_id': period_id, 'date': date}, 
                context=context)
            # Create default vals for the new two move lines
            vals = {
                'move_id': move_id,
                'date': date,
                'journal_id': journal_id,
                'period_id': period_id,
                'partner_id': partner_id,
                'employee_id': employee_id,
                'register_id': register_id,
                'credit': 0.0,
                'debit': 0.0,
                'name': 'Realised loss/gain',
            }
            # Note that if total == 0.0 we are not in this loop (normal reconciliation)
            # If total inferior to 0, some amount is missing @debit for partner
            partner_db = partner_cr = addendum_db = addendum_cr = None
            if total < 0.0:
                # data for partner line
                partner_db = addendum_cr = abs(total)
            # Conversely some amount is missing @credit for partner
            else:
                partner_cr = addendum_db = abs(total)
            # Create partner line
            vals.update({'account_id': account_id, 'debit_currency': partner_db or 0.0, 'credit_currency': partner_cr or 0.0})
            partner_line_id = ml_obj.create(cr, uid, vals, context=context)
            # Create addendum_line
            vals.update({'account_id': addendum_line_account_id, 'debit_currency': addendum_db or 0.0, 'credit_currency': addendum_cr or 0.0})
            addendum_line_id = ml_obj.create(cr, uid, vals, context=context)
            # Validate move
            self.pool.get('account.move').post(cr, uid, [move_id], context=context)
            # Add partner_line to do total reconciliation
            to_reconcile.append(partner_line_id)
        # Do reconciliation
        ml_obj.reconcile(cr, uid, to_reconcile, 'manual', False, False, False, context=context)
        return {'type': 'ir.actions.act_window_close'}


    def partial_reconcile(self, cr, uid, ids, context={}):
        """
        Do a partial reconciliation
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Do partial reconciliation
        account_move_line_obj.reconcile_partial(cr, uid, context['active_ids'], 'manual', context=context)
        return {'type': 'ir.actions.act_window_close'}

account_move_line_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
