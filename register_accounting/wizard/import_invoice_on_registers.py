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
from ..register_tools import _get_date_in_period

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
        'cheque_number': fields.char(string="Cheque Number", size=120, readonly=False, required=False),
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
        'currency_id': fields.many2one('res.currency', string="Currency", required=True, help="Help to filter invoices regarding currency.")
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Correct fields in order to have "cheque number" when we come from a cheque register.
        """
        if context is None:
            context = {}
        view_name = 'import_invoice_on_registers_lines'
        if context.get('from_cheque', False):
            view_name = 'import_invoice_on_registers_lines_cheque'
        view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'register_accounting', view_name)
        if view:
            view_id = view[1]
        result = super(wizard_import_invoice, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return result

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
        if wizard.line_id.id in display_lines:
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
            'date': _get_date_in_period(cr, uid, line.date, period_id, context=context),
            'amount': line.amount_currency or None, # By default, amount_to_pay
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

        # Prepare some values
        move_line_obj = self.pool.get('account.move.line')
        absl_obj = self.pool.get('account.bank.statement.line')
        st = wizard.statement_id
        st_id = st.id
        journal_id = st.journal_id.id
        period_id = st.period_id.id
        cheque = False
        if st.journal_id.type == 'cheque':
            cheque = True
        st_line_ids = []

        # Order lines by partner_id
        ordered_lines = {}
        for line in wizard.invoice_lines_ids:
            # FIXME: Verify that all lines have positive amount AND an amount that doesn't be superior to amount_to_pay
            if not line.partner_id.id in ordered_lines:
                ordered_lines[line.partner_id.id] = [line.id]
            elif line.id not in ordered_lines[line.partner_id.id]:
                ordered_lines[line.partner_id.id].append(line.id)
            # We come from a cheque register ? So what about cheque_number field ?
            if cheque and line.cheque_number is False:
                raise osv.except_osv(_('Warning'), _('Please complete "Cheque Number" field(s) before wizard validation.'))

        # For each partner, do an account_move with all lines => lines merge
        for partner in ordered_lines:
            register_vals = {}
            cheque_numbers = []
            # Lines for this partner
            lines = self.pool.get('wizard.import.invoice.lines').browse(cr, uid, ordered_lines[partner])
            first_line = move_line_obj.browse(cr, uid, [lines[0].line_id.id], context=context)[0] or None

            # Prepare some values
            currency_id = first_line.currency_id and first_line.currency_id.id or False
            curr_date = strftime('%Y-%m-%d')
            
            # Prepare some values
            total = 0.0
            for line in lines:
                res = self.pool.get('wizard.import.invoice.lines').read(cr, uid, line.id, ['amount', 'cheque_number'])
                if 'amount' in res:
                    total += res.get('amount')
                if cheque and 'cheque_number' in res:
                    cheque_numbers.append(res.get('cheque_number'))
            
            # Create register line
            register_vals = {
                'name': 'Imported invoices',
                'date': _get_date_in_period(cr, uid, curr_date, period_id, context=context),
                'statement_id': st_id,
                'account_id': first_line.account_id.id,
                'partner_id': first_line.partner_id.id,
                'amount': total,
            }
            # if we come from cheque, add a column for that
            if cheque:
                register_vals.update({'cheque_number': '-'.join(cheque_numbers)[:120]})
            # add ids of imported_invoice_lines
            register_vals.update({'imported_invoice_line_ids': [(4, x.line_id.id) for x in lines]})
            # create the register line
            absl_id = absl_obj.create(cr, uid, register_vals, context=context)
            
            # Temp post the register line
            res = absl_obj.posting(cr, uid, [absl_id], 'temp', context=context)

            # Add id of register line in the exit of this function
            st_line_ids.append(absl_id)
        
        # Close Wizard
        # st_line_ids could be necessary for some tests
        return { 'type': 'ir.actions.act_window_close', 'st_line_ids': st_line_ids}

wizard_import_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
