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
import decimal_precision as dp
import time 
from ..register_tools import _get_date_in_period

class wizard_import_invoice_lines(osv.osv_memory):
    """
    Selected invoice that will be imported in the register after wizard termination.
    Note : some account_move will be also written in order to make these lines in a temp post state.
    """
    _name = 'wizard.import.invoice.lines'
    _description = 'Lines from invoice to be imported'

    def _get_num_inv(self, cr, uid, ids, *args, **kw):
        res = {}
        for obj in self.read(cr, uid, ids, ['line_ids']):
            res[obj['id']] = obj['line_ids'] and len(obj['line_ids']) or 0
        return res

    _columns = {
        'partner_id': fields.many2one('res.partner', string='Partner', readonly=True),
        'ref': fields.char('Ref.', size=64, readonly=True),
        'account_id': fields.many2one('account.account', string="Account", readonly=True),
        'date': fields.date('Posting Date', readonly=False, required=True),
        'amount': fields.float('Amount', readonly=False, required=True, digits_compute=dp.get_precision('Account')),
        'amount_to_pay': fields.float('Amount to pay', readonly=True, digits_compute=dp.get_precision('Account')),
        'amount_currency': fields.float('Amount currency', readonly=True, digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', string="Currency", readonly=True),
        'line_ids': fields.many2many('account.move.line', 'account_move_immport_rel', 'move_id', 'line_id', 'Invoices'),
        'number_invoices': fields.function(_get_num_inv, type='integer', string='Invoices', method=True),
        'wizard_id': fields.many2one('wizard.import.invoice', string='wizard'),
        'cheque_number': fields.char(string="Cheque Number", size=120, readonly=False, required=False),
    }
    def write(self, cr, uid, ids, vals, context={}):
        if isinstance(ids, (long, int)):
            ids = [ids]
        if 'amount' in vals:
            for l in self.read(cr, uid, ids, ['amount_to_pay']):
                if vals['amount'] > l['amount_to_pay']:
                    raise osv.except_osv(_('Warning'), _("Amount %s can't be greatest than 'Amount to pay': %s")%(vals['amount'], l['amount_to_pay']))

        return super(wizard_import_invoice_lines, self).write(cr, uid, ids, vals, context)

wizard_import_invoice_lines()

class wizard_import_invoice(osv.osv_memory):
    """
    A wizard that permit to select some invoice in order to add them to the register.
    It's possible to do partial payment on several invoices.
    """
    _name = 'wizard.import.invoice'
    _description = 'Invoices to be imported'

    _columns = {
        'line_ids': fields.many2many('account.move.line', 'account_move_line_relation', 'move_id', 'line_id', 'Invoices'),
        'invoice_lines_ids': fields.one2many('wizard.import.invoice.lines', 'wizard_id', string='', required=True),
        'statement_id': fields.many2one('account.bank.statement', string='Register', required=True, help="Register that we come from."),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True, help="Help to filter invoices regarding currency."),
        'date': fields.date('Date'),
        'state': fields.selection( (('draft', 'Draft'), ('open', 'Open')), string="State", required=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
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

    def single_import(self, cr, uid, ids, context={}):
        return self.group_import(cr, uid, ids, context, group=False)

    def group_import(self, cr, uid, ids, context={}, group=True):
        wizard = self.browse(cr, uid, ids[0], context=context)
        if not wizard.line_ids:
            raise osv.except_osv(_('Warning'), _('Please add invoice lines'))
        
        already = []
        for line in wizard.invoice_lines_ids:
            for inv in line.line_ids:
                already.append(inv.id)

        ordered_lines = {}
        for line in wizard.line_ids:
            if line.id in already:
                raise osv.except_osv(_('Warning'), _('This invoice: %s %s has already been added. Please choose another invoice.')%(line.name, line.amount_currency))
            if group:
                key = "%s-%s-%s"%(line.amount_currency < 0 and "-" or "+", line.partner_id.id, line.account_id.id)
            else:
                key = line.id

            if not key in ordered_lines:
                ordered_lines[key] = [line]
            elif line not in ordered_lines[key]:
                ordered_lines[key].append(line)
        
        # For each partner, do an account_move with all lines => lines merge
        new_lines = []
        for key in ordered_lines:
            # Prepare some values
            total = 0.0
            amount_cur = 0

            for line in ordered_lines[key]:
                total += line.amount_currency
                amount_cur += line.amount_residual_import_inv
            
            # Create register line
            new_lines.append({
                'line_ids': [(6, 0, [x.id for x in ordered_lines[key]])],
                'partner_id': ordered_lines[key][0].partner_id.id or None,
                'ref': 'Imported Invoice',
                'account_id': ordered_lines[key][0].account_id.id or None,
                'date': wizard.date or time.strftime('%Y-%m-%d'),
                'amount': abs(amount_cur),
                'amount_to_pay': amount_cur,
                'amount_currency': total,
                'currency_id': ordered_lines[key][0].currency_id.id,
            })
        self.write(cr, uid, [wizard.id], {'state': 'open', 'line_ids': [(6, 0, [])], 'invoice_lines_ids': [(0, 0, x) for x in new_lines]})
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

        # For each partner, do an account_move with all lines => lines merge
        for line in wizard.invoice_lines_ids:
            if cheque and not line.cheque_number:
                raise osv.except_osv(_('Warning'), _('Please add a cheque number to red lines.'))

            # Create register line
            register_vals = {
                'name': line.ref,
                'date': line.date,
                'statement_id': st_id,
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id,
                'amount': line.amount_currency < 0 and -line.amount or line.amount,
                'imported_invoice_line_ids': [(4, x.id) for x in line.line_ids],
            }
            # if we come from cheque, add a column for that
            if cheque:
                register_vals.update({'cheque_number': line.cheque_number})
            
            absl_id = absl_obj.create(cr, uid, register_vals, context=context)
            
            # Temp post the register line
            res = absl_obj.posting(cr, uid, [absl_id], 'temp', context=context)

            # Add id of register line in the exit of this function
            st_line_ids.append(absl_id)
        
        if not len(st_line_ids):
            raise osv.except_osv(_('Warning'), _('No line created!'))
        # Close Wizard
        # st_line_ids could be necessary for some tests
        return { 'type': 'ir.actions.act_window_close', 'st_line_ids': st_line_ids}

wizard_import_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
