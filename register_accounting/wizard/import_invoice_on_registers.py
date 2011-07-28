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
        'date': fields.date('Effective Date', readonly=True),
        'amount': fields.integer('Amount', readonly=False),
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
    }

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
        if wizard.line_id and wizard.line_id.id not in display_lines:
            line = wizard.line_id
            vals = {
                'line_id': line.id or None,
                'partner_id': line.partner_id.id or None,
                'ref': line.ref or None,
                'number': line.invoice.number or None,
                'supplier_ref': line.invoice.name or None,
                'account_id': line.account_id.id or None,
                'date_maturity': line.date_maturity or None,
                'date': line.date or None,
                'amount': line.amount_to_pay or None, # By default, amount_to_pay
                'amount_to_pay': line.amount_to_pay or None,
                'amount_currency': line.amount_currency or None,
                'currency_id': line.currency_id.id or None,
                'wizard_id': wizard.id or None,
            }
            new_line = (0, 0, vals)
            new_lines.append(new_line)
        elif wizard.line_id.id in display_lines:
            raise osv.except_osv(_('Warning'), _('This invoice has already been added. Please choose another invoice.'))
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
        # FIXME:
        # - for each lines of each parnter do an account_move_line and attach it to the account_move for this partner_id
        # - do a register line for each partner_id
        wizard = self.browse(cr, uid, ids[0], context=context)
        # Order lines by partner_id
        ordered_lines = {}
        for line in wizard.invoice_lines_ids:
            if not line.partner_id.id in ordered_lines:
                ordered_lines[line.partner_id.id] = [line.id]
            elif line.id not in ordered_lines[line.partner_id.id]:
                ordered_lines[line.partner_id.id].append(line.id)
        # Prepare some values
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        # For each partner, do an account_move with all lines => lines merge
        for partner in ordered_lines:
            move_vals = {}
            move_line_vals = {}
            # FIXME:p
            # - create one line with amount
            # - create the compensation line with a total amount of all lines' amount

            # Lines for this partner
            lines = self.pool.get('wizard.import.invoice.lines').browse(cr, uid, ordered_lines[partner])
            first_line = move_line_obj.browse(cr, uid, [lines[0].line_id.id], context=context)[0] or None
            # Take some information about the first line
            journal_id = first_line.journal_id and first_line.journal_id.id or False
            period_id = first_line.period_id and first_line.period_id.id or False
            curr_date = strftime('%Y-%m-%d')
            # Create a move : begin
            move_name = "Invoice payment"
            # prepare a move
            move_vals = {
                'journal_id': journal_id, # invoice.journal_id.id
                'period_id': period_id,
                'date': curr_date,
                'name': move_name,
            }
            # create the move : end
            move_id = move_obj.create(cr, uid, move_vals, context=context)

        # Close Wizard
        return { 'type': 'ir.actions.act_window_close', }

wizard_import_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
