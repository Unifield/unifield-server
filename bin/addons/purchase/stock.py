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

#
# Inherit of picking to add the link to the PO
#
class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
        'purchase_id': fields.many2one('purchase.order', 'Purchase Order',
                                       ondelete='set null', select=True),
    }
    _defaults = {
        'purchase_id': False,
    }

    def get_currency_id(self, cursor, user, picking):
        if picking.purchase_id:
            return picking.purchase_id.pricelist_id.currency_id.id
        else:
            return super(stock_picking, self).get_currency_id(cursor, user, picking)

    def _invoice_hook(self, cursor, user, picking, invoice_id):
        purchase_obj = self.pool.get('purchase.order')
        if picking.purchase_id:
            purchase_obj.write(cursor, user, [picking.purchase_id.id], {'invoice_id': invoice_id,})
        return super(stock_picking, self)._invoice_hook(cursor, user, picking, invoice_id)

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

