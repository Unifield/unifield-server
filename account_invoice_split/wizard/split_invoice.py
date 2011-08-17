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

class wizard_split_invoice_lines(osv.osv_memory):
    _name = 'wizard.split.invoice.lines'
    _description = 'Split Invoice lines'

    _columns = {
        'invoice_line_id': fields.many2one('account.invoice.line', string='Invoice Line', readonly=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'quantity': fields.float(string='Qty', required=True, readonly=False),
        'price_unit': fields.float(string='Unit price', required=True),
        'description': fields.char(string='Description', size=255),
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
        # FIXME: verify that all lines are completed (quantity required)
        # FIXME:
        # - create new lines for those which doesn't have any invoice_line_id (for the new invoice)
        # - if line exists, then correct it with the difference in account_invoice_line
        # - create a new invoice in draft, with copy ?

        # Prepare some values
        wizard = self.browse(cr, uid, ids[0], context=context)
        invoice_ids = [] # created invoices
        invoice_origin_id = wizard.invoice_id.id
        inv_obj = self.pool.get('account.invoice')
        invl_obj = self.pool.get('account.invoice.line')
        wiz_lines_obj = self.pool.get('wizard.split.invoice.lines')
        # Create a copy of invoice
        new_inv_id = inv_obj.copy(cr, uid, invoice_origin_id, {}, context=context)
        if not new_inv_id:
            raise osv.except_osv(_('Error'), _('The creation of a new invoice failed.'))
        # Delete new lines
        invl_ids = invl_obj.search(cr, uid, [('invoice_id', '=', new_inv_id)], context=context)
        invl_obj.unlink(cr, uid, invl_ids, context=context)
        # Create new ones
        wiz_line_ids = wiz_lines_obj.search(cr, uid, [('wizard_id', '=', wizard.id)])
        for wiz_line in wiz_lines_obj.browse(cr, uid, wiz_line_ids, context=context):
            print wiz_line.product_id.name
        raise osv.except_osv('error', 'programmed error')
        return { 'type' : 'ir.actions.act_window_close', 'active_id' : wizard.invoice_id.id, 'invoice_ids': invoice_ids}

wizard_split_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
