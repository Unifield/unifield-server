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

    def button_confirm(self, cr, uid, ids, context={}):
        """
        Validate changes and split invoice regarding given lines
        """
        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        invoice_ids = [] # created invoices
        invoice_origin_id = wizard.invoice_id.id
        inv_obj = self.pool.get('account.invoice')
        invl_obj = self.pool.get('account.invoice.line')
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        # Test lines
        wiz_line_ids = wiz_lines_obj.search(cr, uid, [('wizard_id', '=', wizard.id)])
        if not wiz_line_ids:
            return { 'type' : 'ir.actions.act_window_close', 'active_id' : wizard.invoice_id.id, 'invoice_ids': invoice_ids}
        # Some verifications
        line_to_modify = []
        for wiz_line in wiz_lines_obj.browse(cr, uid, wiz_line_ids, context=context):
            # Quantity
            if wiz_line.quantity <= 0:
                raise osv.except_osv(_('Warning'), _('%s: Quantity should be positive!') % wiz_line.description)
            if wiz_line.quantity > wiz_line.invoice_line_id.quantity:
                raise osv.except_osv(_('Warning'), _('%s: Quantity should be inferior or equal to initial quantity!') % wiz_line.description)
            # Price unit
            if wiz_line.price_unit <= 0:
                raise osv.except_osv(_('Warning'), _('%s: Unit price should be positive!') % wiz_line.description)
            if wiz_line.quantity != wiz_line.invoice_line_id.quantity:
                line_to_modify.append(wiz_line.id)
        if not len(line_to_modify):
            raise osv.except_osv(_('Error'), _('No line were modified. No split done.'))
        # Create a copy of invoice
        new_inv_id = inv_obj.copy(cr, uid, invoice_origin_id, {}, context=context)
        invoice_ids.append(new_inv_id)
        if not new_inv_id:
            raise osv.except_osv(_('Error'), _('The creation of a new invoice failed.'))
        # Delete new lines
        invl_ids = invl_obj.search(cr, uid, [('invoice_id', '=', new_inv_id)], context=context)
        invl_obj.unlink(cr, uid, invl_ids, context=context)
        # Create new ones
        for wiz_line in wiz_lines_obj.browse(cr, uid, wiz_line_ids, context=context):
            # create values for the new invoice line
            invl_vals = invl_obj.product_id_change(cr, uid, [], wiz_line.product_id.id, False, wiz_line.quantity, wiz_line.description, 
                partner_id=wizard.invoice_id.partner_id.id, price_unit=wiz_line.price_unit, context=context).get('value')
            # attach this line to the new invoice
            invl_vals.update({'invoice_id': new_inv_id, 'price_unit': wiz_line.price_unit, 'quantity': wiz_line.quantity, 
                'product_id': wiz_line.product_id.id})
            # create the new invoice line
            invl_obj.create(cr, uid, invl_vals, context=context)
            # then update old line if exists
            if wiz_line.invoice_line_id:
                qty = wiz_line.invoice_line_id.quantity - wiz_line.quantity
                # If quantity superior to 0, then write old line, if 0 then delete line
                if qty > 0:
                    invl_obj.write(cr, uid, [wiz_line.invoice_line_id.id], {'quantity': qty}, context=context)
                elif qty == 0:
                    invl_obj.unlink(cr, uid, [wiz_line.invoice_line_id.id], context=context)
        # attach new invoice to purchase order it come from
        for po in wizard.invoice_id.purchase_ids:
            inv_obj.write(cr, uid, [new_inv_id], {'purchase_ids': [(4, po.id)]}, context=context)
        return { 'type' : 'ir.actions.act_window_close', 'active_id' : new_inv_id, 'invoice_ids': invoice_ids}

wizard_split_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
