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

class account_invoice_line(osv.osv):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

    def copy(self, cr, uid, id, default=None, context=None):
        if not context:
            context = {}
        if not default:
            default = {}

        new_id = super(account_invoice_line, self).copy(cr, uid, id, default, context)

        if 'split_it' in context:
            purchase_lines_obj = self.pool.get('purchase.order.line')
            sale_lines_obj = self.pool.get('sale.order.line')

            if purchase_lines_obj:
                purchase_line_ids = purchase_lines_obj.search(cr, uid, [('invoice_lines', 'in', [id])])
                if purchase_line_ids:
                    purchase_lines_obj.write(cr, uid, purchase_line_ids, {'invoice_lines': [(4, new_id)]})

            if sale_lines_obj:
                sale_lines_ids =  sale_lines_obj.search(cr, uid, [('invoice_lines', 'in', [id])])
                if sale_lines_ids:
                    sale_lines_obj.write(cr, uid,  sale_lines_ids, {'invoice_lines': [(4, new_id)]})
        
        return new_id

account_invoice_line()


class account_invoice(osv.osv):
    _name = 'account.invoice'
    _description = 'Account invoice'

    _inherit = 'account.invoice'

    def copy(self, cr, uid, id, default=None, context=None):
        if not context:
            context = {}
        if not default:
            default = {}

        if 'register_line_ids' not in default:
            default['register_line_ids'] = []

        new_id = super(account_invoice, self).copy(cr, uid, id, default, context)

        if 'split_it' in context:
            purchase_obj = self.pool.get('purchase.order')
            sale_obj = self.pool.get('sale.order')

            if purchase_obj:
                # attach new invoice to PO
                purchase_ids = purchase_obj.search(cr, uid, [('invoice_ids', 'in', [id])], context=context)
                if purchase_ids:
                    purchase_obj.write(cr, uid, purchase_ids, {'invoice_ids': [(4, new_id)]}, context=context)
            if sale_obj:
                # attach new invoice to SO
                sale_ids = sale_obj.search(cr, uid, [('invoice_ids', 'in', [id])], context=context)
                if sale_ids:
                    sale_obj.write(cr, uid, sale_ids, {'invoice_ids': [(4, new_id)]}, context=context)

        return new_id

    def button_split_invoice(self, cr, uid, ids, context=None):
        """
        Launch the split invoice wizard to split an invoice in two elements.
        """
        # Some verifications
        if not context:
            context={}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some value
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        inv_lines_obj = self.pool.get('account.invoice.line')
        # Creating wizard
        wizard_id = self.pool.get('wizard.split.invoice').create(cr, uid, {'invoice_id': ids[0]}, context=context)
        # Add invoices_lines into the wizard
        invoice_line_ids = self.pool.get('account.invoice.line').search(cr, uid, [('invoice_id', '=', ids[0])], context=context)
        # Some other verifications
        if not len(invoice_line_ids):
            raise osv.except_osv(_('Error'), _('No invoice line in this invoice or not enough elements'))
        for invl in inv_lines_obj.browse(cr, uid, invoice_line_ids, context=context):
            wiz_lines_obj.create(cr, uid, {'invoice_line_id': invl.id, 'product_id': invl.product_id.id, 'quantity': invl.quantity, 
                'price_unit': invl.price_unit, 'description': invl.name, 'wizard_id': wizard_id}, context=context)
        # Return wizard
        if wizard_id:
            return {
                'name': "Split Invoice",
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.split.invoice',
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': [wizard_id],
                'context':
                {
                    'active_id': ids[0],
                    'active_ids': ids,
                    'wizard_id': wizard_id,
                }
            }
        return False

account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
