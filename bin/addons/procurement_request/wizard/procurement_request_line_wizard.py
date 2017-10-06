# -*- coding: utf-8 -*-
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

from osv import osv
from osv import fields
from tools.translate import _


class procurement_request_line_wizard(osv.osv_memory):
    _name = 'procurement.request.line.wizard'
    _description = 'Original Data Internal Request line'

    _columns = {
        'id': fields.integer('id'),
        'product_id': fields.many2one('product.product', 'Current Product'),
        # 'original_product': fields.many2one('product.product', 'Original Product'),
        'product_uom_qty': fields.float('Current Qty'),
        'original_qty': fields.float('Original Qty'),
        'price_unit': fields.float('Current Price'),
        'original_price': fields.float('Original Price'),
        'product_uom': fields.many2one('product.uom', 'Current UOM'),
        'original_uom': fields.many2one('product.uom', 'Original UOM'),
        'modification_comment': fields.char('Modification Comment', size=1024),
    }


procurement_request_line_wizard()