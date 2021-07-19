# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import osv, fields

class stock_move(osv.osv):
    _inherit = 'stock.move'

    def _create_chained_picking(self, cr, uid, pick_name, picking, ptype, move, context=None):
        res = super(stock_move, self)._create_chained_picking(cr, uid, pick_name, picking, ptype, move, context=context)
        if picking.sale_id:
            self.pool.get('stock.picking').write(cr, uid, [res], {'sale_id': picking.sale_id.id})
        return res
stock_move()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
        'sale_id': fields.many2one('sale.order', 'Sales Order', ondelete='set null', select=True),
    }
    _defaults = {
        'sale_id': False
    }

    def get_currency_id(self, cursor, user, picking):
        if picking.sale_id:
            return picking.sale_id.pricelist_id.currency_id.id
        else:
            return super(stock_picking, self).get_currency_id(cursor, user, picking)

    def _get_payment_term(self, cursor, user, picking):
        if picking.sale_id and picking.sale_id.payment_term:
            return picking.sale_id.payment_term.id
        return super(stock_picking, self)._get_payment_term(cursor, user, picking)

    def _get_address_invoice(self, cursor, user, picking):
        res = {}
        if picking.sale_id:
            res['contact'] = picking.sale_id.partner_order_id.id
            res['invoice'] = picking.sale_id.partner_invoice_id.id
            return res
        return super(stock_picking, self)._get_address_invoice(cursor, user, picking)

    def _get_comment_invoice(self, cursor, user, picking):
        if picking.note or (picking.sale_id and picking.sale_id.note):
            return picking.note or picking.sale_id.note
        return super(stock_picking, self)._get_comment_invoice(cursor, user, picking)

    def _invoice_hook(self, cursor, user, picking, invoice_id):
        sale_obj = self.pool.get('sale.order')
        if picking.sale_id:
            sale_obj.write(cursor, user, [picking.sale_id.id], {
                'invoice_ids': [(4, invoice_id)],
            })
        return super(stock_picking, self)._invoice_hook(cursor, user, picking, invoice_id)


stock_picking()

