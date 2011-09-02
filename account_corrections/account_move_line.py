#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from time import strftime

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    _columns = {
        'corrected': fields.boolean(string="Corrected", readonly=True, help="If true, this line has been corrected by an accounting correction wizard"),
        'corrected_line_id': fields.many2one('account.move.line', string="Corrected Line", readonly=True, 
            help="Line that have been corrected by this line."),
    }

    _defaults = {
        'corrected': lambda *a: False,
    }

    def copy(self, cr, uid, id, defaults={}, context={}):
        """
        Copy a move line
        """
        defaults.update({
            'state': 'draft',
        })
        return super(account_move_line, self).copy(cr, uid, id, defaults, context=context)

    def button_do_accounting_corrections(self, cr, uid, ids, context={}):
        """
        Launch accounting correction wizard to do reverse or correction on selected move line.
        """
        # Verification
        if not context:
            context={}
        # Retrieve some values
        wiz_obj = self.pool.get('wizard.journal.items.corrections')
        # Create wizard
        wizard = wiz_obj.create(cr, uid, {'move_line_id': ids[0]}, context=context)
        # Change wizard state in order to change date requirement on wizard
        wiz_obj.write(cr, uid, [wizard], {'state': 'open'}, context=context)
        return {
            'name': "Accounting Corrections Wizard",
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.journal.items.corrections',
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': [wizard],
            'context':
            {
                'active_id': ids[0],
                'active_ids': ids,
            }
        }

    def button_open_corrections(self, cr, uid, ids, context={}):
        """
        Open all corrections linked to the given one
        """
        return True

    def reverse(self, cr, uid, ids, date=None, context={}):
        """
        Reverse given lines by creating a new Journal Entry (account_move) and write in the reversal line.
        Reversal lines have some information:
         - name begin with REV
         - debit and credit are reversed
         - amount_currency is the opposite
         - date is those from given date or current date by default
         - period is those that correspond to the given date
         - line is written in the first 'correction' type journal found
        NB : return the succeeded move lines
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            date = strftime('%Y-%m-%d')
        # Prepare some values
        success_move_line_ids = []
        move_obj = self.pool.get('account.move')
        j_obj = self.pool.get('account.journal')
        j_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        # Search correction journal
        j_corr_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        if not j_corr_ids:
            raise osv.except_osv(_('Error'), ('No correction journal found!'))
        # Search attached period
        period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)], context=context, 
            limit=1, order='date_start, name')
        # Browse move line
        for ml in self.browse(cr, uid, ids, context=context):
            # Abort process if this move line was corrected before
            if ml.corrected:
                continue
            
            # FIXME: Verify that this line doesn't come from a register (statement_id) => update register line
            
            # Create a new move
            move_id = move_obj.create(cr, uid,{'journal_id': j_corr_ids[0], 'period_id': period_ids[0], 'date': date}, context=context)
            # Prepare default value for new line
            vals = {
                'move_id': move_id,
                'date': date,
                'journal_id': j_corr_ids[0],
                'period_id': period_ids[0],
            }
            # Copy the line
            rev_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            # Do the reverse
            name = 'REV' + ' ' + ml.name
            amt = -1 * ml.amount_currency
            vals.update({
                'debit': ml.credit,
                'credit': ml.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'corrected_line_id': ml.id,
                'account_id': ml.account_id.id,
            })
            self.write(cr, uid, [rev_line_id], vals, context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [ml.id], {'corrected': True}, context=context)
            # Add this line to succeded lines
            success_move_line_ids.append(ml.id)
        return success_move_line_ids

    def reverse_move(self, cr, uid, ids, date=None, context={}):
        """
        Reverse the move from lines
        Return succeeded move lines (not complementary move lines)
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            date = strftime('%Y-%m-%d')
        # Prepare some values
        success_move_line_ids = []
        move_obj = self.pool.get('account.move')
        j_obj = self.pool.get('account.journal')
        j_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        # Search correction journal
        j_corr_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        if not j_corr_ids:
            raise osv.except_osv(_('Error'), ('No correction journal found!'))
        # Search attached period
        period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)], context=context, 
            limit=1, order='date_start, name')
        # Sort ids
        move_lines = self.browse(cr, uid, ids, context=context)
        tmp_move_ids = [x.move_id.id for x in move_lines if x.move_id]
        # Delete double and sort it
        move_ids = sorted(list(set(tmp_move_ids)))
        # Browse moves
        for m in move_obj.browse(cr, uid, move_ids, context=context):
            # Verify this move could be reversed
            corrigible = True
            for ml in m.line_id:
                if ml.corrected:
                    corrigible = False
            if not corrigible:
                continue
            
            # FIXME: verify that no lines come from a statement_id => should be corrected if necessary
            
            # Create a new move
            new_move_id = move_obj.create(cr, uid,{'journal_id': j_corr_ids[0], 'period_id': period_ids[0], 'date': date}, context=context)
            # Browse all move lines and change information
            for ml in self.browse(cr, uid, [x.id for x in m.line_id], context=context):
                amt = -1 * ml.amount_currency
                name = 'REV' + ' ' + ml.name
                new_line_id = self.copy(cr, uid, ml.id, {'move_id': new_move_id}, context=context)
                self.write(cr, uid, [new_line_id], {'name': name, 'debit': ml.credit, 'credit': ml.debit, 'amount_currency': amt, 
                    'corrected_line_id': ml.id}, context=context)
                # Flag this line as corrected
                self.write(cr, uid, [ml.id], {'corrected': True}, context=context)
                if ml.id in ids:
                    success_move_line_ids.append(ml.id)
            # Hard post the move
            move_obj.post(cr, uid, [new_move_id], context=context)
        return success_move_line_ids

    def correct_account(self, cr, uid, ids, date=None, new_account_id=None, context={}):
        """
        Correct given account_move_line by only changin account
        """
        # Verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            date = strftime('%Y-%d-%m')
        if not new_account_id:
            raise osv.except_osv(_('Error'), _('No new account_id given!'))
        # Prepare some values
        move_obj = self.pool.get('account.move')
        j_obj = self.pool.get('account.journal')
        success_move_line_ids = []
        # Search correction journal
        j_corr_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        if not j_corr_ids:
            raise osv.except_osv(_('Error'), ('No correction journal found!'))
        # Search attached period
        period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)], 
            context=context, limit=1, order='date_start, name')
        # Browse all given move line for correct them
        for ml in self.browse(cr, uid, ids, context=context):
            # Abort process if this move line was corrected before
            if ml.corrected:
                continue
            # Create a new move
            move_id = move_obj.create(cr, uid,{'journal_id': j_corr_ids[0], 'period_id': period_ids[0], 'date': date}, context=context)
            # Prepare default value for new line
            vals = {
                'move_id': move_id,
                'date': date,
                'journal_id': j_corr_ids[0],
                'period_id': period_ids[0],
            }
            # Copy the line
            rev_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            correction_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            # Do the reverse
            name = 'REV' + ' ' + ml.name
            amt = -1 * ml.amount_currency
            vals.update({
                'debit': ml.credit,
                'credit': ml.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'corrected_line_id': ml.id,
                'account_id': ml.account_id.id,
            })
            self.write(cr, uid, [rev_line_id], vals, context=context)
            # Do the correction line
            name = 'COR' + ' ' + ml.name
            self.write(cr, uid, [correction_line_id], {'name': name, 'journal_id': j_corr_ids[0], 'corrected_line_id': ml.id,
                'account_id': new_account_id,}, context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [ml.id], {'corrected': True}, context=context)
            # Post the move
            move_obj.post(cr, uid, [move_id], context=context)
            # Add this line to succeded lines
            success_move_line_ids.append(ml.id)
        return success_move_line_ids

    def correct_partner_id(self, cr, uid, ids, date=None, partner_id=None, context={}):
        """
        Correct given entries in order to change its partner_id:
         - do a reverse line for partner line
         - do a correction line for new partner
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            date = strftime('%Y-%d-%m')
        if not partner_id:
            raise osv.except_osv(_('Error'), _('No new partner_id given!'))
        # Prepare some values
        j_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        success_move_line_ids = []
        # Search correction journal
        j_corr_ids = j_obj.search(cr, uid, [('type', '=', 'correction')], context=context)
        if not j_corr_ids:
            raise osv.except_osv(_('Error'), ('No correction journal found!'))
        # Search attached period
        period_ids = self.pool.get('account.period').search(cr, uid, [('date_start', '<=', date), ('date_stop', '>=', date)], 
            context=context, limit=1, order='date_start, name')
        # Correct all given move lines
        for ml in self.browse(cr, uid, ids, context=context):
            # Search the move line (in the move) to be changed (account that have a payable OR a receivable account)
            move_line = None
            for line in ml.move_id.line_id:
                if line.account_id.type == 'payable' or line.account_id.type == 'receivable':
                    move_line = line
                    break
            # If no move line found or move line has been corrected, continue process
            if not move_line or move_line.corrected:
                continue
            # Create a new move
            move_id = move_obj.create(cr, uid,{'journal_id': j_corr_ids[0], 'period_id': period_ids[0], 'date': date}, context=context)
            # Search the new attached account_id
            partner_type = 'res.partner,%s' % partner_id
            account_vals = self.pool.get('account.bank.statement.line').onchange_partner_type(cr, uid, [], partner_type, move_line.credit, 
                move_line.debit, context=context)
            if not 'value' in account_vals and not account_vals.get('value').get('account_id', False):
                raise osv.except_osv(_('Error'), _('No account found for this partner!'))
            account_id = account_vals.get('value').get('account_id')
            # Prepare default value for new line
            vals = {
                'move_id': move_id,
                'date': date,
                'journal_id': j_corr_ids[0],
                'period_id': period_ids[0],
            }
            # Copy the line
            rev_line_id = self.copy(cr, uid, move_line.id, vals, context=context)
            correction_line_id = self.copy(cr, uid, move_line.id, vals, context=context)
            # Do the reverse
            name = 'REV' + ' ' + move_line.name
            amt = -1 * move_line.amount_currency
            vals.update({
                'debit': move_line.credit,
                'credit': move_line.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'corrected_line_id': move_line.id,
                'account_id': move_line.account_id.id,
            })
            self.write(cr, uid, [rev_line_id], vals, context=context)
            # Do the correction line
            name = 'COR' + ' ' + move_line.name
            self.write(cr, uid, [correction_line_id], {'name': name, 'journal_id': j_corr_ids[0], 'corrected_line_id': move_line.id,
                'account_id': account_id, 'partner_id': partner_id}, context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [move_line.id], {'corrected': True}, context=context)
            # Post the move
            move_obj.post(cr, uid, [move_id], context=context)
            # Reconcile the line with its reversal
            self.reconcile_partial(cr, uid, [line.id, rev_line_id], context=context)
            # Add this line to succeded lines
            success_move_line_ids.append(move_line.id)
        return success_move_line_ids

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
