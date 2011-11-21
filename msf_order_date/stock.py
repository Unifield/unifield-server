#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'


    # @@@override stock>stock.py>stock_picking>do_partial
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        '''
        Write the shipment date on accoding order
        '''
        res = super(stock_picking, self).do_partial(cr, uid, ids, partial_datas, context=context)

        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')

        for picking in self.browse(cr, uid, ids, context=context):
            if picking.purchase_id:
                po_obj.write(cr, uid, [picking.purchase_id.id], {'shipment_date': picking.date_done})
            if picking.sale_id:
                so_obj.write(cr, uid, [picking.sale_id.id], {'shipment_date': picking.date_done})

        return res


stock_picking()

