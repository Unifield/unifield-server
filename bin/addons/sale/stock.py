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


stock_picking()

