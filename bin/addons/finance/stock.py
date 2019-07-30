#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _

class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    def _invoice_line_hook(self, cr, uid, move_line, invoice_line_id, account_id):
        """
        BE CAREFUL : For FO with PICK/PACK/SHIP, the invoice is not created on picking but on shipment
        """
        res = super(stock_picking, self)._invoice_line_hook(cr, uid, move_line, invoice_line_id, account_id)

        # Modify the product UoM and the quantity of line according to move attributes
        values = {'uos_id': move_line.product_uom.id,
                  'quantity': move_line.product_qty}

        price_unit = False
        if move_line.price_unit:
            price_unit = move_line.price_unit

        # UTP-220: As now the price can be changed when making the reception, the system still needs to keep the PO price in the invoice!
        # UF-2211: The price unit needs to be adapted to the UoM: so it needs to be retrieved from the move line, and not the po_line in another UoM
        # Finance may decide to change later, but for instance, this is not agreed by Finance. Check UTP-220 for further info
        if move_line.picking_id:
            inv_type = self._get_invoice_type(move_line.picking_id)
            price_unit = self._get_price_unit_invoice(cr, uid, move_line, inv_type)

        if price_unit:
            values.update({'price_unit': price_unit})

        self.pool.get('account.invoice.line').write(cr, uid, [invoice_line_id], values)

        if move_line.picking_id and move_line.picking_id.purchase_id and move_line.picking_id.purchase_id.order_type == 'in_kind':
            order_line = move_line.purchase_line_id or False
            account_id = (order_line.product_id and order_line.product_id.donation_expense_account and order_line.product_id.donation_expense_account.id) \
                or (order_line.product_id.categ_id and order_line.product_id.categ_id.donation_expense_account and order_line.product_id.categ_id.donation_expense_account.id) \
                or False
            if not account_id:
                raise osv.except_osv(_('Error'), _('No donation expense account defined for this PO Line: %s') % (order_line.name or '',))
            self.pool.get('account.invoice.line').write(cr, uid, [invoice_line_id], {'account_id': account_id,})
        # Delete invoice lines that come from a picking from scratch that have an intermission/section partner  and which reason type is different from deliver partner
        # first fetch some values
        try:
            rt_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_deliver_partner')[1]
        except ValueError:
            rt_id = False
        # then test move_line
        if move_line.picking_id and move_line.picking_id.type == 'out' and move_line.reason_type_id.id != rt_id:
            if move_line.picking_id and not move_line.picking_id.purchase_id and not move_line.picking_id.sale_id and move_line.picking_id.partner_id.partner_type in ['intermission', 'section']:
                self.pool.get('account.invoice.line').unlink(cr, uid, [invoice_line_id])
        return res


stock_picking()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
