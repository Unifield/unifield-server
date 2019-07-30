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
from lxml import etree

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
        'employee_id': fields.many2one('hr.employee', string='Employee', readonly=True),
        'ref': fields.char('Ref.', size=64, readonly=True),
        'account_id': fields.many2one('account.account', string="Account", readonly=True),
        'date': fields.date('Posting Date', readonly=False, required=True),
        'document_date': fields.date('Document Date', readonly=True, required=True),
        'amount': fields.float('Amount', readonly=False, required=True, digits_compute=dp.get_precision('Account')),
        'amount_to_pay': fields.float('Amount to pay', readonly=True, digits_compute=dp.get_precision('Account')),
        'amount_currency': fields.float('Book. Amount', readonly=True, digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', string="Book. Currency", readonly=True),
        'line_ids': fields.many2many('account.move.line', 'account_move_immport_rel', 'move_id', 'line_id', 'Invoices'),
        'number_invoices': fields.function(_get_num_inv, type='integer', string='Invoices', method=True),
        'wizard_id': fields.many2one('wizard.import.invoice', string='wizard'),
        'cheque_number': fields.char(string="Cheque Number", size=120, readonly=False, required=False),
    }
    def write(self, cr, uid, ids, vals, context=None):
        """
        Check given amount:
          - should not be negative
          - should be superior to amount to pay (but absolute value)
        """
        if not ids:
            return True
        if isinstance(ids, (long, int)):
            ids = [ids]
        if context is None:
            context = {}
        msg = False

        # Amount check
        for l in self.read(cr, uid, ids, ['amount_to_pay']):
            if vals['amount'] < 0:
                msg = _('Negative amount are forbidden!')
            # if the amounts aren't equal (with a 0.001 tolerance) the paid amount shouldn't exceed the amount to pay
            elif vals['amount'] - abs(l['amount_to_pay']) > 10**-3:
                msg = _("Amount %.2f can't be greater than 'Amount to pay': %.2f") % (vals['amount'], abs(l['amount_to_pay']))
            if msg:
                # reset wrong amount
                vals = { 'amount': abs(l['amount_to_pay']) }

        res = super(wizard_import_invoice_lines, self).write(cr,uid, ids, vals, context=context)
        if msg:
            raise osv.except_osv(_('Warning'), msg)
        return res

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
        'date': fields.date('Payment posting date'),
        'document_date': fields.date('Document Date'),
        'state': fields.selection( (('draft', 'Draft'), ('open', 'Open')), string="State", required=True),
        'locked_ok': fields.boolean(u"Lock"),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'locked_ok': lambda *a: False,
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
        # UFTP-121: Add instance in the selection
        user = self.pool.get('res.users').browse(cr, uid, uid)
        instance_id = user.company_id and user.company_id.instance_id and user.company_id.instance_id.id or False
        fctx = {
            'from': 'wizard_import_invoice',
            'search_default_instance_id': instance_id,
        }
        form = etree.fromstring(result['arch'])
        fields = form.xpath("//field[@name='line_ids']")
        for field in fields:
            field.set('context', str(fctx))
        result['arch'] = etree.tostring(form)
        return result

    def single_import(self, cr, uid, ids, context=None):
        return self.group_import(cr, uid, ids, context, group=False)

    def group_import(self, cr, uid, ids, context=None, group=True):
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
                key = "%s-%s-%s"%("all", line.partner_id.id, line.account_id.id)
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
                residual = line.amount_residual_import_inv \
                    if line.amount_currency > 0 \
                    else -line.amount_residual_import_inv
                amount_cur += residual
                total += line.amount_currency

            # Search register line reference size
            ref_field_data = self.pool.get('account.bank.statement.line').fields_get(cr, uid, ['ref'])
            size = 0
            if ref_field_data and 'ref' in ref_field_data and ref_field_data.get('ref').get('size', False):
                size = ref_field_data.get('ref').get('size')
            # Create register line
            new_lines.append({
                'line_ids': [(6, 0, [x.id for x in ordered_lines[key]])],
                'partner_id': ordered_lines[key][0].partner_id.id or None,
                'employee_id': ordered_lines[key][0].employee_id.id or None,
                'ref': ' / '.join([x.ref and x.ref or '' for x in ordered_lines[key]])[:size] or False,
                'account_id': ordered_lines[key][0].account_id.id or None,
                'date': wizard.date or time.strftime('%Y-%m-%d'),
                'document_date': wizard.date or time.strftime('%Y-%m-%d'),
                'amount': abs(amount_cur),
                'amount_to_pay': amount_cur,
                'amount_currency': total,
                'currency_id': ordered_lines[key][0].currency_id.id,
            })
        self.write(cr, uid, [wizard.id], {'state': 'open', 'line_ids': [(6, 0, [])], 'invoice_lines_ids': [(0, 0, x) for x in new_lines]}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.invoice',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'context': context,
            'target': 'new',
        }

    def action_confirm(self, cr, uid, ids, context=None):
        """
        Take all given lines and do Journal Entries (account_move) for each partner_id
        """
        # Cancel the operation if it is already performed
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.locked_ok:
            return False
        # Lock the operation to avoid repeated user's actions
        self.write(cr, uid, ids, {'locked_ok': True}, context=context)
        try:
            # TODO: REFACTORING (create more functions)
            # FIXME:
            # - verify amount regarding foreign currency !!!
            wizard = self.browse(cr, uid, ids[0], context=context)

            # Prepare some values
            absl_obj = self.pool.get('account.bank.statement.line')
            st = wizard.statement_id
            st_id = st.id
            cheque = False
            if st.journal_id.type == 'cheque':
                cheque = True
            st_line_ids = []

            # For each partner, do an account_move with all lines => lines merge
            for line in wizard.invoice_lines_ids:
                if cheque and not line.cheque_number:
                    raise osv.except_osv(_('Warning'), _('Please add a cheque number to red lines.'))

                # Create register line
                partial = False
                equal_amounts = abs(abs(line.amount) - abs(line.amount_to_pay)) <= 10**-3
                if not equal_amounts and line.amount < abs(line.amount_to_pay):
                    partial = ' - ' + _('partial pymt')
                ref = line.ref
                if not ref or ref == 'false':
                    if line.line_ids and line.line_ids[0].move_id:
                        ref = line.line_ids[0].move_id.name
                register_vals = {
                    'name': '%s Imported Invoice(s)%s' % (line.number_invoices, partial or ''),
                    'ref': ref or '',
                    'date': line.date,
                    'document_date': line.document_date,
                    'statement_id': st_id,
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'employee_id': line.employee_id.id,
                    'amount': line.amount_currency < 0 and -line.amount or line.amount,
                    'imported_invoice_line_ids': [(4, x.id) for x in line.line_ids],
                }

                # if we come from cheque, add a column for that
                if cheque:
                    register_vals.update({'cheque_number': line.cheque_number})

                absl_id = absl_obj.create(cr, uid, register_vals, context=context)

                # Temp post the register line
                absl_obj.posting(cr, uid, [absl_id], 'temp', context=context)

                # Add id of register line in the exit of this function
                st_line_ids.append(absl_id)

            if not len(st_line_ids):
                raise osv.except_osv(_('Warning'), _('No line created!'))
            # Close Wizard
            # st_line_ids could be necessary for some tests
            return { 'type': 'ir.actions.act_window_close', 'st_line_ids': st_line_ids, 'o2m_refresh': 'line_ids'}
        except Exception, exc:
            # Release the lock if an error occurred during the process
            self.write(cr, uid, ids, {'locked_ok': False}, context=context)
            raise exc

wizard_import_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
