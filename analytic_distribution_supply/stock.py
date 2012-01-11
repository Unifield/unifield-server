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

    def _invoice_line_hook(self, cr, uid, move_line, invoice_line_id):
        """
        Create a link between invoice_line and purchase_order_line. This piece of information is available on move_line.order_line_id
        """
        if invoice_line_id and move_line:
            self.pool.get('account.invoice.line').write(cr, uid, [invoice_line_id], 
                {'order_line_id': move_line.purchase_line_id and move_line.purchase_line_id.id or False})
        return super(stock_picking, self)._invoice_line_hook(cr, uid, move_line, invoice_line_id)

    def _invoice_hook(self, cr, uid, picking, invoice_id):
        """
        Create a link between invoice and purchase_order.
        Copy analytic distribution from purchase order to invoice (or from commitment voucher if exists)
        """
        if invoice_id and picking:
            po_id = picking.purchase_id and picking.purchase_id.id or False
            if po_id:
                self.pool.get('purchase.order').write(cr, uid, [po_id], {'invoice_ids': [(4, invoice_id)]})
            # Copy analytic distribution from purchase order or commitment voucher (if exists)
            self.pool.get('account.invoice').fetch_analytic_distribution(cr, uid, [invoice_id])
        return super(stock_picking, self)._invoice_hook(cr, uid, picking, invoice_id)

stock_picking()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
