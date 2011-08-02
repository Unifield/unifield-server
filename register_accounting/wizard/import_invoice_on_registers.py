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

class wizard_import_invoice_lines(osv.osv_memory):
    """
    Selected invoice that will be imported in the register after wizard termination.
    Note : some account_move will be also written in order to make these lines in a temp post state.
    """
    _name = 'wizard.import.invoice.lines'
    _description = 'Lines from invoice to be imported'
    _columns = {
        'partner_id': fields.many2one('res.partner', string='Partner', readonly=True),
        'ref': fields.char('Ref.', size=64, readonly=True),
        'number': fields.char('Number', size=64, readonly=True),
        'supplier_ref': fields.char('Supplier Inv. Ref.', size=64, readonly=True),
        'account_id': fields.many2one('account.account', string="Account", readonly=True),
        'date_maturity': fields.date('Due Date', readonly=True),
        'date': fields.date('Effective Date', readonly=False, required=True),
        'amount': fields.integer('Amount', readonly=False, required=True),
        'amount_to_pay': fields.integer('Amount to pay', readonly=True),
        'amount_currency': fields.integer('Amount currency', readonly=True),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True),
        'line_id': fields.many2one('account.move.line', string="Invoice", required=True),
        'wizard_id': fields.many2one('wizard.import.invoice', string='wizard'),
    }

wizard_import_invoice_lines()

class wizard_import_invoice(osv.osv_memory):
    """
    A wizard that permit to select some invoice in order to add them to the register.
    It's possible to do partial payment on several invoices.
    """
    _name = 'wizard.import.invoice'
    _description = 'Invoices to be imported'

    _columns = {
        'line_id': fields.many2one('account.move.line', string='Invoice', required=False),
        'invoice_lines_ids': fields.one2many('wizard.import.invoice.lines', 'wizard_id', string='', required=True),
        'statement_id': fields.many2one('account.bank.statement', string='Register', required=True, help="Register that we come from."),
    }

    def _get_date_in_period(self, cr, uid, date=None, period_id=None, context={}):
        """
        Permit to return a date included in period :
         - if given date is included in period, return the given date
         - else return the date_stop of given period
        """
        if not context:
            context={}
        if not date or not period_id:
            return False
        period = self.pool.get('account.period').browse(cr, uid, period_id, context=context)
        if date < period.date_start or date > period.date_stop:
            return period.date_stop
        return date

    def action_add_invoice(self, cr, uid, ids, context={}):
        """
        Add selected invoice into invoice_lines_ids tree
        """
        wizard = self.browse(cr, uid, ids[0], context=context)
        vals = {}
        new_lines = []
        # Take all registered lines
        display_lines = [x['line_id']['id'] for x in wizard.invoice_lines_ids]
        if display_lines:
            # Add these lines 
            new_lines.append(wizard.invoice_lines_ids)
        period_id = wizard.statement_id.period_id.id
        if not wizard.line_id: 
            return False
        if wizard.line_id.id in display_lines or wizard.line_id.from_import_invoice == True:
            raise osv.except_osv(_('Warning'), _('This invoice has already been added. Please choose another invoice.'))
        line = wizard.line_id
        vals = {
            'line_id': line.id or None,
            'partner_id': line.partner_id.id or None,
            'ref': line.ref or None,
            'number': line.invoice.number or None,
            'supplier_ref': line.invoice.name or None,
            'account_id': line.account_id.id or None,
            'date_maturity': line.date_maturity or None,
            'date': self._get_date_in_period(cr, uid, line.date, period_id, context=context),
            'amount': line.amount_to_pay or None, # By default, amount_to_pay
            'amount_to_pay': line.amount_to_pay or None,
            'amount_currency': line.amount_currency or None,
            'currency_id': line.currency_id.id or None,
            'wizard_id': wizard.id or None,
        }
        new_line = (0, 0, vals)
        new_lines.append(new_line)
        # Write change on wizard in order to:
        # - add new lines
        # - clear invoice field
        self.write(cr, uid, ids, {'invoice_lines_ids': new_lines, 'line_id': None}, context=context)
        # Refresh wizard to display changes
        return {
         'type': 'ir.actions.act_window',
         'res_model': 'wizard.import.invoice',
         'view_type': 'form',
         'view_mode': 'form',
         'res_id': ids[0],
         'context': context,
         'target': 'new',
        }

    def action_confirm(self, cr, uid, ids, context={}):
        """
        Take all given lines and do Journal Entries (account_move) for each partner_id
        """
        # TODO: REFACTORING (create more functions)
        # FIXME:
        # - verify amount regarding foreign currency !!!
        wizard = self.browse(cr, uid, ids[0], context=context)
        # Order lines by partner_id
        ordered_lines = {}
        for line in wizard.invoice_lines_ids:
            # FIXME: Verify that all lines have positive amount AND an amount that doesn't be superior to amount_to_pay
            if not line.partner_id.id in ordered_lines:
                ordered_lines[line.partner_id.id] = [line.id]
            elif line.id not in ordered_lines[line.partner_id.id]:
                ordered_lines[line.partner_id.id].append(line.id)

        # Prepare some values
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        absl_obj = self.pool.get('account.bank.statement.line')
        st = wizard.statement_id
        st_id = st.id
        journal_id = st.journal_id.id
        period_id = st.period_id.id

        # For each partner, do an account_move with all lines => lines merge
        for partner in ordered_lines:
            move_vals = {}
            move_line_vals = {}
            register_vals = {}
            # Lines for this partner
            lines = self.pool.get('wizard.import.invoice.lines').browse(cr, uid, ordered_lines[partner])
            first_line = move_line_obj.browse(cr, uid, [lines[0].line_id.id], context=context)[0] or None
            # Take some information about the first line
#            journal_id = first_line.journal_id and first_line.journal_id.id or False
#            period_id = first_line.period_id and first_line.period_id.id or False
            currency_id = first_line.currency_id and first_line.currency_id.id or False
            curr_date = strftime('%Y-%m-%d')
            # Create a move : begin
            move_name = "Inv. Pay." # TODO: What should be displayed ?
            # prepare a move
            move_vals = {
                'journal_id': journal_id, # invoice.journal_id.id
                'period_id': period_id,
                'date': self._get_date_in_period(cr, uid, curr_date, period_id, context=context),
                'name': move_name,
            }
            # create the move : end
            move_id = move_obj.create(cr, uid, move_vals, context=context)
            # create on move_line for each line for this partner
            for line in lines:
                # Prepare some value
                # FIXME: do debit or credit regarding payable/receivable
                aml_vals = {
                    'name': line.number,
                    'date': self._get_date_in_period(cr, uid, line.date, period_id, context=context),
                    'move_id': move_id,
                    'partner_id': line.partner_id and line.partner_id.id or False,
                    'account_id': line.account_id and line.account_id.id,
                    'credit': line.line_id.debit,
                    'debit': line.line_id.credit,
                    'statement_id': st_id,
                    'journal_id': line.line_id.journal_id.id,
                    'period_id': period_id,
                    'currency_id': currency_id,
                }
                # Create move line
                aml_id = move_line_obj.create(cr, uid, aml_vals, context=context)
                # Inform system that invoices are linked to an import.
                move_line_obj.browse(cr, uid, line.line_id.invoice)
                move_line_obj.write(cr, uid, line.line_id.id, {'from_import_invoice': True}, context=context)
                
                # FIXME: Change amount_to_pay of this invoice (amount_to_pay - amount)
            # Write compensation line
            # FIXME: make a balance of account_move and do the compensation line with payable or receivable account
            compensation_amount = move_obj._compute_balance(cr, uid, move_id, context=context)
            compensation_debit = 0.0
            compensation_credit = compensation_amount
            compensation_account_id = journal_id and st.journal_id.default_credit_account_id.id
            if compensation_amount < 0:
                compensation_debit = abs(compensation_amount)
                compensation_account_id = journal_id and st.journal_id.default_debit_account_id.id
            compensation_vals = {
                    'name': 'Total of invoices',
                    'date': self._get_date_in_period(cr, uid, curr_date, period_id, context=context),
                    'move_id': move_id,
                    'partner_id': line.partner_id and line.partner_id.id or False,
                    'account_id': compensation_account_id,
                    'credit': compensation_credit,
                    'debit': compensation_debit,
                    'statement_id': st_id,
                    'journal_id': journal_id,
                    'period_id': period_id,
                    'currency_id': currency_id,
            }
            compensation_id = move_line_obj.create(cr, uid, compensation_vals, context=context)
            
            # Create register line
            register_vals = {
                'name': 'Imported invoices',
                'date': self._get_date_in_period(cr, uid, curr_date, period_id, context=context),
                'statement_id': st_id,
                'account_id': first_line.account_id.id,
                'partner_id': first_line.partner_id.id,
                'amount': compensation_debit - compensation_credit or 0.0,
                'move_ids': [(4, move_id, False)], # create a link between the register line and the account_move_line
                'from_import_invoice': True,
            }
            absl_obj.create(cr, uid, register_vals, context=context)
            

        # Close Wizard
        return { 'type': 'ir.actions.act_window_close', }

wizard_import_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
