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

class wizard_split_invoice_lines(osv.osv_memory):
    _name = 'wizard.split.invoice.lines'
    _description = 'Split Invoice lines'

    _columns = {
        'invoice_line_id': fields.many2one('account.invoice.line', string='Invoice Line', readonly=True),
        'product_id': fields.many2one('product.product', string='Product', required=True, readonly=True),
        'quantity': fields.float(string='Qty', required=True, readonly=False),
        'price_unit': fields.float(string='Unit price', required=True, readonly=True),
        'description': fields.char(string='Description', size=255, readonly=True),
        'wizard_id': fields.many2one('wizard.split.invoice', string='Wizard', readonly=True, required=True),
    }

wizard_split_invoice_lines()

class wizard_split_invoice(osv.osv_memory):
    _name = 'wizard.split.invoice'
    _description = 'Split Invoice'

    _columns = {
        'invoice_id': fields.many2one('account.invoice', string='Invoice Origin', help='Invoice we come from'),
        'invoice_line_ids': fields.one2many('wizard.split.invoice.lines', 'wizard_id', string='Invoice lines'),
    }

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Validate changes and split invoice regarding given lines
        """
        # Prepare some values
        if context is None:
            context = {}
        context.update({'from_split': True})

        wizard = self.browse(cr, uid, ids[0], context=context)
        invoice_ids = [] # created invoices
        invoice_origin_id = wizard.invoice_id.id
        inv_obj = self.pool.get('account.invoice')
        invl_obj = self.pool.get('account.invoice.line')
        wiz_line_obj = self.pool.get('wizard.split.invoice.lines')

        # Test lines
        if not wizard.invoice_line_ids:
            return { 'type' : 'ir.actions.act_window_close', 'active_id' : wizard.invoice_id.id, 'invoice_ids': invoice_ids}

        # Some verifications
        line_to_modify = []
        for wiz_line in wizard.invoice_line_ids:
            # Quantity
            initial_qty = wiz_line.invoice_line_id and wiz_line.invoice_line_id.quantity or 0.0
            if wiz_line.quantity <= 10**-3:
                raise osv.except_osv(_('Warning'), _('%s: Quantity should be positive!') % wiz_line.description)
            if abs(wiz_line.quantity - initial_qty) > 10**-3 and wiz_line.quantity > initial_qty:
                raise osv.except_osv(_('Warning'), _('%s: Quantity should be inferior or equal to initial quantity!') % wiz_line.description)
            # Price unit
            if wiz_line.price_unit <= 10**-3:
                # US-8295 Note that this check is kept on purpose on Donations even if they can have lines with amount zero. The only way to
                # use the split feature with those lines is to remove them from the Split wizard in order to send them to the second invoice.
                raise osv.except_osv(_('Warning'), _('%s: Unit price should be positive!') % wiz_line.description)
            # We add line if its quantity have changed or that another line have been deleted from original invoice
            #+ (so that the number of original invoice are more than invoice line in the current wizard)
            if abs(wiz_line.quantity - initial_qty) > 10**-3 or len(wizard.invoice_id.invoice_line) > len(wizard.invoice_line_ids):
                line_to_modify.append(wiz_line.id)
        if not len(line_to_modify):
            raise osv.except_osv(_('Error'), _('No line were modified. No split done.'))
        # Create a copy of invoice
        new_inv_id = inv_obj.copy(cr, uid, invoice_origin_id, {'invoice_line': []}, context=context)
        invoice_ids.append(new_inv_id)
        if not new_inv_id:
            raise osv.except_osv(_('Error'), _('The creation of a new invoice failed.'))

        inv_lines = wizard.invoice_id and wizard.invoice_id.invoice_line or []
        inv_lines_in_wiz = [wiz_line.invoice_line_id.id for wiz_line in wizard.invoice_line_ids]
        for inv_line in inv_lines:
            if inv_line.id not in inv_lines_in_wiz:
                # UC1: the line has been deleted in the wizard: add it in the new invoice, and then remove it from the original one
                new_data = {'invoice_id': new_inv_id}
                if inv_line.original_invoice_line_id:
                    new_data.update({'original_invoice_line_id': inv_line.original_invoice_line_id.id, 'original_line_qty': inv_line.original_line_qty})
                invl_obj.copy(cr, uid, inv_line.id, new_data, context=context)
                invl_obj.unlink(cr, uid, [inv_line.id], context=context)
            else:
                wiz_line_ids = wiz_line_obj.search(cr, uid,
                                                   [('invoice_line_id', '=', inv_line.id),
                                                    ('wizard_id', '=', wizard.id)],  # in case the wiz. is used several times on the same line
                                                   limit=1, context=context)
                if wiz_line_ids:
                    wiz_line_id = wiz_line_ids[0]
                    wiz_line_qty = wiz_line_obj.browse(cr, uid, wiz_line_id, fields_to_fetch=['quantity'], context=context).quantity or 0.0
                    diff_qty = (inv_line.quantity or 0.0) - wiz_line_qty
                    if abs(diff_qty) > 10**-3:  # UC2: line unchanged in the wizard: nothing to do, i.e. keep it in the original invoice
                        # UC3: quantity has been modified: write the new qty in the original inv., and create a line for the diff in the new one
                        original_data = {'quantity': wiz_line_qty}
                        new_data = {'invoice_id': new_inv_id, 'quantity': diff_qty}
                        if inv_line.original_invoice_line_id:
                            original_data.update({'original_invoice_line_id': inv_line.original_invoice_line_id.id, 'original_line_qty': wiz_line_qty})
                            new_data.update({'original_invoice_line_id': inv_line.original_invoice_line_id.id, 'original_line_qty': diff_qty})
                        invl_obj.write(cr, uid, [inv_line.id], original_data, context=context)
                        invl_obj.copy(cr, uid, inv_line.id, new_data, context=context)

        # Calculate total for invoices
        invoice_ids.append(wizard.invoice_id.id)
        for invoice in inv_obj.browse(cr, uid, invoice_ids, context=context):
            inv_obj.write(cr, uid, [invoice.id] + [invoice_origin_id], {'check_total': invoice.amount_total}, context=context)

        return { 'type' : 'ir.actions.act_window_close', 'active_id' : new_inv_id, 'invoice_ids': invoice_ids}


wizard_split_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
