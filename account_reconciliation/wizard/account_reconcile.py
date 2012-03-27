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
        'state': fields.selection([('total', 'Full Reconciliation'), ('partial', 'Partial Reconciliation'), 
            ('total_change', 'Full Reconciliation with change'), ('partial_change', 'Partial Reconciliation with change')], string="State", 
            required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'total',
    }

    def default_get(self, cr, uid, fields, context=None):
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

    def trans_rec_get(self, cr, uid, ids, context=None):
        """
        Change default method:
        - take debit_currency and credit_currency instead of debit and credit (this is to pay attention to Booking Currency)
        - add some values:
          - state: if write off is 0.0, then 'total' else 'partial'
        - verify that lines come from a transfer account or not
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        account_move_line_obj = self.pool.get('account.move.line')
        credit = debit = fcredit = fdebit = 0
        state = 'partial'
        account_id = False
        count = 0
        # Browse all lines
        prev_acc_id = None
        prev_third_party = None
        transfer = False
        transfer_with_change = False
        # Transfer verification
        operator = 'in'
        if len(context['active_ids']) == 1:
            operator = '='
        search_ids = account_move_line_obj.search(cr, uid, [('account_id.type_for_register', 'in', ['transfer_same', 'transfer']), 
            ('id', operator, context['active_ids'])], context=context)
        if len(context['active_ids']) == len(search_ids):
            if len(context['active_ids']) == 2:
                elements = account_move_line_obj.browse(cr, uid, context['active_ids'], context)
                first_line = elements[0]
                second_line = elements[1]
                if first_line.journal_id and first_line.transfer_journal_id and second_line.journal_id and second_line.transfer_journal_id:
                    # Cross check on third parties
                    if first_line.journal_id.id == second_line.transfer_journal_id.id and second_line.journal_id.id == first_line.transfer_journal_id.id:
                        transfer = True
                    # Cross check on amounts for transfer_with_change verification
                    if first_line.is_transfer_with_change and second_line.is_transfer_with_change:
                        if abs(first_line.transfer_amount) == abs(second_line.amount_currency) and abs(first_line.amount_currency) == abs(second_line.transfer_amount):
                            transfer_with_change = True
                        else:
                            raise osv.except_osv(_('Warning'), _("Cannot reconcile entries : Cross check between initial and converted amount fails."))
        if transfer_with_change:
            # For transfer with change, we need to do a total reconciliation!
            state = 'total_change'
        for line in account_move_line_obj.browse(cr, uid, context['active_ids'], context=context):
            # prepare some values
            account_id = line.account_id.id
            # some verifications
            if not line.account_id.reconcile:
                raise osv.except_osv(_('Warning'), _('This account is not reconciliable: %s') % (line.account_id.code,))
            # verification that there's only one account for each line
            if not prev_acc_id:
                prev_acc_id = account_id
            if prev_acc_id != account_id:
                raise osv.except_osv(_('Error'), _('An account is different from others: %s') % (line.account_id.code,))
            # verification that there's only one 3rd party
            # The 3rd party verification is desactivated in case of transfer with change
            if not transfer:
                third_party = {
                        'partner_id': line.partner_id and line.partner_id.id or False, 
                        'employee_id': line.employee_id and line.employee_id.id or False, 
                        'register_id': line.register_id and line.register_id.id or False, 
                        'transfer_journal_id': line.transfer_journal_id and line.transfer_journal_id.id or False}
                if not prev_third_party:
                    prev_third_party = third_party
                if prev_third_party != third_party:
                    raise osv.except_osv(_('Error'), _('Cannot reconcile entries : Cross check between Journal Code and Third Party failed.'))
            # process necessary elements
            if not line.reconcile_id and not line.reconcile_id.id:
                count += 1
                credit += line.credit_currency
                debit += line.debit_currency
                if transfer_with_change:
                    fcredit += line.credit
                    fdebit += line.debit
        # Adapt state value
        if (debit - credit) == 0.0:
            state = 'total'
        if transfer_with_change:
            debit = fdebit
            credit = fcredit
            if (fdebit - fcredit) == 0.0:
                state = 'total_change'
        return {'trans_nbr': count, 'account_id': account_id, 'credit': credit, 'debit': debit, 'writeoff': debit - credit, 'state': state}

    def total_reconcile(self, cr, uid, ids, context=None):
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
        to_reconcile = context['active_ids']
        self.pool.get('account.move.line').reconcile(cr, uid, to_reconcile, 'manual', False, False, False, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def partial_reconcile(self, cr, uid, ids, context=None):
        """
        Do a partial reconciliation
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Do partial reconciliation
        self.pool.get('account.move.line').reconcile_partial(cr, uid, context['active_ids'], 'manual', context=context)
        return {'type': 'ir.actions.act_window_close'}

account_move_line_reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
