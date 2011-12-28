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
import time
import netsvc
from reconciliation_tools import _get_addendum_line_account_id
from tools.translate import _

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _name = 'account.move.line'

    def reconcile_partial(self, cr, uid, ids, type='auto', context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        # @@@override@account.account_move_line.py
        move_rec_obj = self.pool.get('account.move.reconcile')
        merges = []
        unmerge = []
        total = 0.0
        merges_rec = []
        company_list = []
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning !'), _('To reconcile the entries company should be the same for all entries'))
            company_list.append(line.company_id.id)

        for line in self.browse(cr, uid, ids, context=context):
            company_currency_id = line.company_id.currency_id
            if line.reconcile_id:
                raise osv.except_osv(_('Warning'), _('Already Reconciled!'))
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    if not line2.reconcile_id:
                        if line2.id not in merges:
                            merges.append(line2.id)
                        # Next line have been modified from debit/credit to debit_currency/credit_currency
                        total += (line2.debit_currency or 0.0) - (line2.credit_currency or 0.0)
                merges_rec.append(line.reconcile_partial_id.id)
            else:
                unmerge.append(line.id)
                total += (line.debit_currency or 0.0) - (line.credit_currency or 0.0)
        if self.pool.get('res.currency').is_zero(cr, uid, company_currency_id, total):
            res = self.reconcile(cr, uid, merges+unmerge, context=context)
            return res
        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_partial_ids': map(lambda x: (4,x,False), merges+unmerge)
        })
        move_rec_obj.reconcile_partial_check(cr, uid, [r_id] + merges_rec, context=context)
        # @@@end
        return True

    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
        """
        WARNING: This method has been taken from account module from OpenERP
        """
        # @@@override@account.account_move_line.py
        account_obj = self.pool.get('account.account')
        move_obj = self.pool.get('account.move')
        move_rec_obj = self.pool.get('account.move.reconcile')
        partner_obj = self.pool.get('res.partner')
        currency_obj = self.pool.get('res.currency')
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = func_debit = func_credit = currency = 0.0
        currency_id = account_id = partner_id = employee_id = register_id = functional_currency_id = False
        if context is None:
            context = {}
        company_list = []
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning !'), _('To reconcile the entries company should be the same for all entries'))
            company_list.append(line.company_id.id)
        for line in unrec_lines:
            if line.state <> 'valid':
                raise osv.except_osv(_('Error'),
                        _('Entry "%s" is not valid !') % line.name)
            credit += line['credit_currency']
            debit += line['debit_currency']
            func_debit += line['debit']
            func_credit += line['credit']
            currency += line['amount_currency'] or 0.0
            currency_id = line['currency_id']['id']
            functional_currency_id = line['functional_currency_id']['id']
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
            employee_id = (line['employee_id'] and line['employee_id']['id']) or False
            register_id = (line['register_id'] and line['register_id']['id']) or False
        func_balance = func_debit - func_credit

        # Ifdate_p in context => take this date
        if context.has_key('date_p') and context['date_p']:
            date=context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        cr.execute('SELECT account_id, reconcile_id '\
                   'FROM account_move_line '\
                   'WHERE id IN %s '\
                   'GROUP BY account_id,reconcile_id',
                   (tuple(ids), ))
        r = cr.fetchall()
        #TODO: move this check to a constraint in the account_move_reconcile object
        if (len(r) != 1) and not context.get('fy_closing', False):
            raise osv.except_osv(_('Error'), _('Entries are not of the same account or already reconciled ! '))
        if not unrec_lines:
            raise osv.except_osv(_('Error'), _('Entry is already reconciled'))
        account = account_obj.browse(cr, uid, account_id, context=context)
        if not context.get('fy_closing', False) and not account.reconcile:
            raise osv.except_osv(_('Error'), _('The account is not defined to be reconciled !'))
        if r[0][1] != None:
            raise osv.except_osv(_('Error'), _('Some entries are already reconciled !'))
        
        ############################################################
        ### Addendum line verification and creation if necessary ###
        ############################################################
        if func_balance != 0.0:
            # Get default account for addendum_line
            addendum_line_account_id = _get_addendum_line_account_id(self, cr, uid, ids, context=context)
            # Prepare some values
            date = time.strftime('%Y-%m-%d')
            j_obj = self.pool.get('account.journal')
            # Search Miscellaneous Transactions journal
            j_ids = j_obj.search(cr, uid, [('type', '=', 'cur_adj')], order='id', context=context)
            if not j_ids:
                raise osv.except_osv(_('Error'), _('No Currency Adjustement journal found!'))
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
                'source_date': date,
                'journal_id': journal_id,
                'period_id': period_id,
                'partner_id': partner_id,
                'employee_id': employee_id,
                'register_id': register_id,
                'credit': 0.0,
                'debit': 0.0,
                'name': 'Realised loss/gain',
                'is_addendum_line': True,
                'currency_id': currency_id,
                'functional_currency_id': functional_currency_id,
            }
            # Note that if func_balance == 0.0 we are not in this loop (normal reconciliation)
            # If func_balance inferior to 0, some amount is missing @debit for partner
            partner_db = partner_cr = addendum_db = addendum_cr = None
            if func_balance < 0.0:
                # data for partner line
                partner_db = addendum_cr = abs(func_balance)
            # Conversely some amount is missing @credit for partner
            else:
                partner_cr = addendum_db = abs(func_balance)
            # Create partner line
            vals.update({'account_id': account_id, 'debit': partner_db or 0.0, 'credit': partner_cr or 0.0,})
            partner_line_id = self.create(cr, uid, vals, context=context)
            # Create addendum_line
            vals.update({'account_id': addendum_line_account_id, 'debit': addendum_db or 0.0, 'credit': addendum_cr or 0.0,})
            addendum_line_id = self.create(cr, uid, vals, context=context)
            # Validate move
            self.pool.get('account.move').post(cr, uid, [move_id], context=context)
            # Add partner_line to do total reconciliation
            ids.append(partner_line_id)
        ############################################################

        r_id = move_rec_obj.create(cr, uid, {
            'type': type,
            'line_id': map(lambda x: (4, x, False), ids),
            'line_partial_ids': map(lambda x: (3, x, False), ids)
        })
        wf_service = netsvc.LocalService("workflow")
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        for id in ids:
            wf_service.trg_trigger(uid, 'account.move.line', id, cr)

        if lines and lines[0]:
            partner_id = lines[0].partner_id and lines[0].partner_id.id or False
            if partner_id and context and context.get('stop_reconcile', False):
                partner_obj.write(cr, uid, [partner_id], {'last_reconciliation_date': time.strftime('%Y-%m-%d %H:%M:%S')})
        # @@@end
        return r_id

    def _remove_move_reconcile(self, cr, uid, move_ids=[], context={}):
        """
        Delete reconciliation object from given move lines ids (move_ids)
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(move_ids, (int, long)):
            move_ids = [move_ids]
        # Retrieve all addendum lines
        # First search all reconciliation ids to find ALL move lines (some could be not selected but unreconciled after
        reconcile_ids = [x.reconcile_id and x.reconcile_id.id for x in self.browse(cr, uid, move_ids, context=context)]
        # Search all account move line for this reconcile_ids
        operator = 'in'
        if len(reconcile_ids) == 1:
            operator = '='
        ml_ids = self.search(cr, uid, [('reconcile_id', operator, reconcile_ids)])
        # Search addendum line to delete
        to_delete = []
        for line in self.browse(cr, uid, ml_ids, context=context):
            if line.is_addendum_line:
                to_delete.append(line.move_id and line.move_id.id)
        # Retrieve default behaviour
        res = super(account_move_line, self)._remove_move_reconcile(cr, uid, move_ids, context=context)
        # If success, verify that no addendum line exists
        if res and to_delete:
            # Delete doublons
            to_delete = list(set(to_delete))
            # First cancel moves
            self.pool.get('account.move').button_cancel(cr, uid, to_delete, context=context)
            # Then delete moves
            self.pool.get('account.move').unlink(cr, uid, to_delete, context=context)
        return res

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
