#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'


    def _invoice_hook(self, cr, uid, picking, invoice_id):
        """
        Create a link between invoice and purchase_order.
        Copy analytic distribution from purchase order to invoice (or from commitment voucher if exists)
        """
        if invoice_id and picking:
            po_id = picking.purchase_id and picking.purchase_id.id or False
            so_id = picking.sale_id and picking.sale_id.id or False
            if po_id:
                self.pool.get('purchase.order').write(cr, uid, [po_id], {'invoice_ids': [(4, invoice_id)]})
            if so_id:
                self.pool.get('sale.order').write(cr, uid, [so_id], {'invoice_ids': [(4, invoice_id)]})
            # Copy analytic distribution from purchase order or commitment voucher (if exists) or sale order
            self.pool.get('account.invoice').fetch_analytic_distribution(cr, uid, [invoice_id])
        return super(stock_picking, self)._invoice_hook(cr, uid, picking, invoice_id)

# action_invoice_create method have been removed because of impossibility to retrieve DESTINATION from SO.

stock_picking()

class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'

    def action_cancel(self, cr, uid, ids, context=None):
        """
        Update commitment voucher line for the given moves
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Browse all elements
        for move in self.browse(cr, uid, ids, context=context):
            # Fetch all necessary elements
            qty = move.product_uos_qty or move.product_qty or 0.0
            picking = move.picking_id or False
            if not picking or not move.purchase_line_id or picking.type !='in':
                # If no picking then no PO have generated this stock move
                continue
            # fetch invoice type in order to retrieve price unit
            inv_type = self.pool.get('stock.picking')._get_invoice_type(picking) or 'out_invoice'
            price_unit = self.pool.get('stock.picking')._get_price_unit_invoice(cr, uid, move, inv_type)
            if not price_unit:
                # If no price_unit, so no impact on commitments because no price unit have been taken for commitment calculation
                continue
            # update all commitment voucher lines
            for cl in move.purchase_line_id.commitment_line_ids:
                new_amount = cl.amount - (qty * price_unit)
                if new_amount < 0.0:
                    new_amount = 0.0
                self.pool.get('account.commitment.line').write(cr, uid, [cl.id], {'amount': new_amount}, context=context)
        return super(stock_move, self).action_cancel(cr, uid, ids, context=context)

stock_move()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
