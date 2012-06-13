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
from tools.misc import flatten

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    def _is_corrigible(self, cr, uid, ids, name, args, context=None):
        """
        Return True for all element that correspond to some criteria:
         - The entry state is posted
         - The account is not payable or receivable
         - Item have not been corrected
         - Item have not been reversed
         - Item come from a reconciliation that have set 'is_addendum_line' to True
         - The account is not the default credit/debit account of the attached statement (register)
         - All items attached to the entry have no reconcile_id on reconciliable account
         - The line doesn't come from a write-off
        """
        if context is None:
            context = {}
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = True
            # False if move is posted
            if ml.move_id.state != 'posted':
                res[ml.id] = False
            # False if account is payable or receivable
            if ml.account_id.type in ['payable', 'receivable']:
                res[ml.id] = False
            # False if account is tax
            if ml.account_id.user_type.code in ['tax']:
                res[ml.id] = False
            # False if line have been corrected
            if ml.corrected:
                res[ml.id] = False
            # False if line is a reversal
            if ml.reversal:
                res[ml.id] = False
            # False if this line is an addendum line
            if ml.is_addendum_line:
                res[ml.id] = False
            # False if line account and statement default debit/credit account are similar
            if ml.statement_id:
                accounts = []
                accounts.append(ml.statement_id.journal_id.default_debit_account_id and ml.statement_id.journal_id.default_debit_account_id.id)
                accounts.append(ml.statement_id.journal_id.default_credit_account_id and ml.statement_id.journal_id.default_credit_account_id.id)
                if ml.account_id.id in accounts:
                    res[ml.id] = False
            # False if one of move line account is reconciliable and reconciled
            for aml in ml.move_id.line_id:
                if aml.account_id.reconcile and (aml.reconcile_id or aml.reconcile_partial_id):
                    res[aml.id] = False
            # False if this line come from a write-off
            if ml.is_write_off:
                res[ml.id] = False
        return res

    _columns = {
        'corrected': fields.boolean(string="Corrected?", readonly=True, 
            help="If true, this line has been corrected by an accounting correction wizard"),
        'corrected_line_id': fields.many2one('account.move.line', string="Corrected Line", readonly=True, 
            help="Line that have been corrected by this one."),
        'reversal': fields.boolean(string="Reversal?", readonly=True, 
            help="If true, this line is a reversal of another (This was done via a correction wizard)."),
        'reversal_line_id': fields.many2one('account.move.line', string="Reversal Line", readonly=True, 
            help="Line that have been reversed by this one."),
        'have_an_historic': fields.boolean(string="Display historic?", readonly=True, 
            help="If true, this implies that this line have historical correction(s)."),
        'is_corrigible': fields.function(_is_corrigible, method=True, string="Is corrigible?", type='boolean', 
            readonly=True, help="This informs system if this item is corrigible. Criteria: the entry state should be posted, account should not be payable or \
receivable, item have not been corrected, item have not been reversed and account is not the default one of the linked register (statement).", 
            store=False),
        'corrected_st_line_id': fields.many2one('account.bank.statement.line', string="Corrected register line", readonly=True, 
            help="This register line is those which have been corrected last."),
    }

    _defaults = {
        'corrected': lambda *a: False,
        'reversal': lambda *a: False,
        'have_an_historic': lambda *a: False,
        'is_corrigible': lambda *a: True,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Copy a move line with draft state. Do not create a new analytic_distribution from line if we come from a correction.
        """
        if default is None:
            default = {}
        if 'omit_analytic_distribution' in context and context.get('omit_analytic_distribution') is True:
            default.update({
                'analytic_distribution_id': False,
            })
        default.update({
            'state': 'draft',
            'have_an_historic': False,
            'corrected': False,
            'reversal': False,
        })
        return super(account_move_line, self).copy(cr, uid, id, default, context=context)

    def get_corrections_history(self, cr, uid, ids, context=None):
        """
        Give for each line their history by using "corrected_line_id" field to browse lines
        Return something like that: 
            {id1: [line_id, another_line_id], id2: [a_line_id, other_line_id]}
        """
        # Verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        move_obj = self.pool.get('account.move')
        # Browse all given lines
        for ml in self.browse(cr, uid, ids, context=context):
            upstream_line_ids = []
            downstream_line_ids = []
            # Get upstream move lines
            line = ml
            while line != None:
                if line:
                    # Add line to result
                    upstream_line_ids.append(line.id)
                    # Add reversal line to result
                    reversal_ids = self.search(cr, uid, [('move_id', '=', line.move_id.id), ('reversal', '=', True)], context=context)
                    if reversal_ids:
                        upstream_line_ids.append(reversal_ids)
                if line.corrected_line_id:
                    line = line.corrected_line_id
                else:
                    line = None
            # Get downstream move lines
            sline_ids = [ml.id]
            while sline_ids != None:
                operator = 'in'
                if len(sline_ids) == 1:
                    operator = '='
                search_ids = self.search(cr, uid, [('corrected_line_id', operator, sline_ids)], context=context)
                if search_ids:
                    # Add line to result
                    downstream_line_ids.append(search_ids)
                    # Add reversal line to result
                    for dl in self.browse(cr, uid, search_ids, context=context):
                        reversal_ids = self.search(cr, uid, [('move_id', '=', dl.move_id.id), ('reversal', '=', True)], context=context)
                        downstream_line_ids.append(reversal_ids)
                    sline_ids = search_ids
                else:
                    sline_ids = None
            # Add search result to res
            res[str(ml.id)] = list(set(flatten(upstream_line_ids) + flatten(downstream_line_ids))) # downstream_line_ids needs to be simplify with flatten
        return res

    def get_first_corrected_line(self, cr, uid, ids, context=None):
        """
        For each move line, give the first line from which all corrections have been done.
        Example:
         - line 1 exists.
         - line 1 was corrected by line 3.
         - line 5 correct line 3.
         - line 8 correct line 5.
         - get_first_corrected_line of line 8 should give line 1.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            upstream_line_ids = []
            # Get upstream move lines
            line = ml
            corrected_line_id = ml.corrected_line_id and ml.corrected_line_id
            while corrected_line_id != False:
                line = line.corrected_line_id or False
                if not line:
                    corrected_line_id = False
                    continue
                corrected_line_id = line.corrected_line_id and line.corrected_line_id.id or False
            res[str(ml.id)] = False
            if line:
                res[str(ml.id)] = line.id
        return res

    def button_do_accounting_corrections(self, cr, uid, ids, context=None):
        """
        Launch accounting correction wizard to do reverse or correction on selected move line.
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
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

    def button_open_corrections(self, cr, uid, ids, context=None):
        """
        Open all corrections linked to the given one
        """
        # Verification
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        domain_ids = []
        # Search ids to be open
        res_ids = self.get_corrections_history(cr, uid, ids, context=context)
        # For each ids, add elements to the domain
        for el in res_ids:
            domain_ids.append(res_ids[el])
        # If no result, just display selected ids
        if not domain_ids:
            domain_ids = ids
        # Create domain
        domain = [('id', 'in', flatten(domain_ids))]#, ('reversal', '=', False)]
        # Update context
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Display the result
        return {
            'name': "History Move Line",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'target': 'new',
            'view_type': 'form',
            'view_mode': 'tree',
            'context': context,
            'domain': domain,
        }
        return True

    def reverse(self, cr, uid, ids, date=None, context=None):
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
            name = self.join_without_redundancy(ml.name, 'REV')
            amt = -1 * ml.amount_currency
            vals.update({
                'debit': ml.credit,
                'credit': ml.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'reversal_line_id': ml.id,
                'account_id': ml.account_id.id,
                'source_date': ml.date,
                'reversal': True,
            })
            self.write(cr, uid, [rev_line_id], vals, context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [ml.id], {'corrected': True, 'have_an_historic': True,}, context=context)
            # Add this line to succeded lines
            success_move_line_ids.append(ml.id)
        return success_move_line_ids

    def reverse_move(self, cr, uid, ids, date=None, context=None):
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
        success_move_ids = []
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
            # Search move line that have to be corrected.
            # NB: this is useful when you correct a move line twice and do a reverse on it. It should be reverse the complementary move line of the first move line
            # and reverse the last correction line.
            # This is just a little bit more complicated than reverse a move.
            to_reverse = []
            # 1/ add move line from this move that have not been reversed to the "to_reverse"
            # 2/ search first move line of each move lines
            # 3/ add complementary line of first move_line to the "to_reverse"
            valid = []
            # Search valid lines into current move
            for line in m.line_id:
                if not line.reversal:
                    valid.append(line)
            # Search first line for each valid lines
            for line in valid:
                first_line_id = self.get_first_corrected_line(cr, uid, line.id, context=context).get(str(line.id), False)
                # add line_id to line to be reversed
                to_reverse.append(line.id)
                if first_line_id:
                    # Get first line move
                    first_line = self.browse(cr, uid, [first_line_id], context=context)[0]
                    for ml in first_line.move_id.line_id:
                        # Add lines that come not from valid lines
                        if ml.id != first_line_id:
                            to_reverse.append(ml.id)
            # Browse all move lines and change information
            for ml in self.browse(cr, uid, to_reverse, context=context):
                amt = -1 * ml.amount_currency
                name = self.join_without_redundancy(ml.name, 'REV')
                vals = {}
                # omit analytic_distribution if exists on first move line
                context.update({'omit_analytic_distribution': False})
                new_distrib_id = False
                if ml.analytic_distribution_id:
                    context.update({'omit_analytic_distribution': True})
                    ana_obj = self.pool.get('analytic.distribution')
                    # create a new distribution
                    new_distrib_id = ana_obj.copy(cr, uid, ml.analytic_distribution_id.id, {}, context=context)
                    # update amount on new distribution
                    ana_obj.update_distribution_line_amount(cr, uid, new_distrib_id, (-1 * (ml.debit - ml.credit)), context=context)
                new_line_id = self.copy(cr, uid, ml.id, {'move_id': new_move_id}, context=context)
                vals.update({
                    'name': name,
                    'debit': ml.credit,
                    'credit': ml.debit,
                    'amount_currency': amt,
                    'reversal_line_id': ml.id,
                    'source_date': ml.date,
                    'reversal': True,
                })
                # Add distribution if new one
                if new_distrib_id:
                    vals.update({'analytic_distribution_id': new_distrib_id})
                self.write(cr, uid, [new_line_id], vals, context=context)
                # Flag this line as corrected
                self.write(cr, uid, [ml.id], {'corrected': True, 'have_an_historic': True,}, context=context)
                # Only add line ID that appear in IDS (success move lines)
                if ml.id in ids:
                    success_move_line_ids.append(ml.id)
            # Hard post the move
            move_obj.post(cr, uid, [new_move_id], context=context)
            success_move_ids.append(new_move_id)
        return success_move_line_ids, success_move_ids

    def update_account_on_st_line(self, cr, uid, ids, account_id=None, context=None):
        """
        Update the account from the statement line attached if different
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not account_id:
            raise osv.except_osv(_('Error'), _('No account_id given. update_account_on_st_line() could not works.'))
        # Prepare some values
        absl_obj = self.pool.get('account.bank.statement.line')
        # Update lines
        for ml in self.browse(cr, uid, ids, context=context):
            # in order to update hard posted line (that's forbidden!), we use a tip: add from_correction in context
            context.update({'from_correction': True})
            # Search lines that are correction of this one (in order to add some fields)
            corrected_line_ids = self.search(cr, uid, [('corrected_line_id', '=', ml.id)], context=context)
            # Case where this move line have a link to some statement lines
            if ml.statement_id and ml.move_id.statement_line_ids:
                for st_line in ml.move_id.statement_line_ids:
                    absl_obj.write(cr, uid, [st_line.id], {'account_id': account_id}, context=context)
                    # we informs new move line that it have correct a statement line
                    self.write(cr, uid, corrected_line_ids, {'corrected_st_line_id': st_line.id}, context=context)
            # if not, this move line should have a direct link to a register line
            elif ml.statement_id and ml.corrected_st_line_id:
                absl_obj.write(cr, uid, [ml.corrected_st_line_id.id], {'account_id': account_id}, context=context)
        return True

    def correct_account(self, cr, uid, ids, date=None, new_account_id=None, corrected_distrib=None, context=None):
        """
        Correct given account_move_line by only changing account
        """
        # Verification
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not date:
            date = strftime('%Y-%m-%d')
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
            context.update({'omit_analytic_distribution': True})
            # Copy the line
            rev_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            correction_line_id = self.copy(cr, uid, ml.id, vals, context=context)
            # Do the reverse
            name = self.join_without_redundancy(ml.name, 'REV')
            amt = -1 * ml.amount_currency
            vals.update({
                'debit': ml.credit,
                'credit': ml.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'reversal_line_id': ml.id,
                'account_id': ml.account_id.id,
                'source_date': ml.date,
                'reversal': True,
            })
            self.write(cr, uid, [rev_line_id], vals, context=context)
            # Do the correction line
            name = self.join_without_redundancy(ml.name, 'COR')
            cor_vals = {
                'name': name,
                'journal_id': j_corr_ids[0],
                'corrected_line_id': ml.id,
                'account_id': new_account_id,
                'ref': ml.ref,
                'source_date': ml.date,
                'have_an_historic': True,
            }
            self.write(cr, uid, [correction_line_id], cor_vals, context=context)
            # Do process on analytic distribution: 
            # 1/ copy old distribution_id on new correction line
            # 2/ copy old distribution_id on reversed line
            if ml.analytic_distribution_id:
                # correction line
                change_distrib = {}
                if corrected_distrib:
                    change_distrib = corrected_distrib
                new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, ml.analytic_distribution_id.id, change_distrib, context=context)
                if new_distrib_id:
                    self.write(cr, uid, [correction_line_id], {'analytic_distribution_id': new_distrib_id,}, context=context)
                # reversed line
                new_rev_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, ml.analytic_distribution_id.id, {}, context=context)
                if new_rev_distrib_id:
                    self.write(cr, uid, [rev_line_id], {'analytic_distribution_id': new_rev_distrib_id,}, context=context)
            # Update register line if exists
            if ml.statement_id:
                self.update_account_on_st_line(cr, uid, [ml.id], new_account_id, context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [ml.id], {'corrected': True, 'have_an_historic': True,}, context=context)
            # Post the move
            move_obj.post(cr, uid, [move_id], context=context)
            # Copy old journal attached to old distribution. Copy those from first line
            if ml.analytic_distribution_id:
                cl = self.browse(cr, uid, [correction_line_id], context=context)[0]
                cl_journal = ml.journal_id.analytic_journal_id.id
                first_line_id = self.get_first_corrected_line(cr, uid, ml.id, context=context).get(str(ml.id), False)
                if first_line_id:
                    first_line = self.browse(cr, uid, [first_line_id], context=context)[0]
                    cl_journal = first_line.journal_id and first_line.journal_id.analytic_journal_id and first_line.journal_id.analytic_journal_id.id or cl_journal
                self.pool.get('account.analytic.line').write(cr, uid, [x.id for x in cl.analytic_distribution_id.analytic_lines], {'journal_id': cl_journal}, context=context)
            # Add this line to succeded lines
            success_move_line_ids.append(ml.id)
        return success_move_line_ids

    def correct_partner_id(self, cr, uid, ids, date=None, partner_id=None, context=None):
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
            date = strftime('%Y-%m-%d')
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
                'source_date': ml.date,
            }
            # Copy the line
            rev_line_id = self.copy(cr, uid, move_line.id, vals, context=context)
            correction_line_id = self.copy(cr, uid, move_line.id, vals, context=context)
            # Do the reverse
            name = self.join_without_redundancy(move_line.name, 'REV')
            amt = -1 * move_line.amount_currency
            vals.update({
                'debit': move_line.credit,
                'credit': move_line.debit,
                'amount_currency': amt,
                'journal_id': j_corr_ids[0],
                'name': name,
                'reversal_line_id': move_line.id,
                'account_id': move_line.account_id.id,
            })
            self.write(cr, uid, [rev_line_id], vals, context=context)
            # Do the correction line
            name = self.join_without_redundancy(move_line.name, 'COR')
            self.write(cr, uid, [correction_line_id], {'name': name, 'journal_id': j_corr_ids[0], 'corrected_line_id': move_line.id,
                'account_id': account_id, 'partner_id': partner_id, 'have_an_historic': True,}, context=context)
            # Inform old line that it have been corrected
            self.write(cr, uid, [move_line.id], {'corrected': True, 'have_an_historic': True,}, context=context)
            # Post the move
            move_obj.post(cr, uid, [move_id], context=context)
            # Reconcile the line with its reversal
            self.reconcile_partial(cr, uid, [line.id, rev_line_id], context=context)
            # Add this line to succeded lines
            success_move_line_ids.append(move_line.id)
        return success_move_line_ids

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
