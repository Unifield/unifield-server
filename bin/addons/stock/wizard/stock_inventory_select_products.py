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

from osv import fields, osv
from tools.translate import _

# This will be a tuple ((1,"1 months" ), (2, "2 months"), ...)
MOVED_IN_LAST_X_MONTHS = tuple([ (i, "%s months" % str(i)) for i in range(1,13) ])

class stock_inventory_select_products(osv.osv_memory):
    _name = "stock.inventory.select.products"
    _description = "Select product to consider for inventory, using filters"

    _columns = {

        'inventory_id': fields.many2one('stock.inventory', 'Inventory', readonly=True),
        'full_inventory': fields.boolean('Full Inventory'),

        # If this is a full inventory, we'll add products in stock at that
        # location + products with recent moves at that location
        'recent_moves_months_fullinvo': fields.selection(MOVED_IN_LAST_X_MONTHS, "Moved in the last", select=True),

        # For partial inventories :

        # First filter is to select products either in stock, or with recent
        # moves at that location
        'first_filter': fields.selection((('in_stock', "Products currently in stock at location"),
                                          ('recent_movements', "Products with recent movement at location")),
                                          "First filter", select=True),
        'recent_moves_months': fields.selection(MOVED_IN_LAST_X_MONTHS, "Moved in the last", select=True),


        # Second filter is to select a family / product list / 'special care' products
        'second_filter': fields.selection((('all',         "All"),
                                           ('family',      "All from a family"),
                                           ('productlist', "All from a product list"),
                                           ('specialcare', "KC/CS/DG")),
                                           "Second filter", select=True),
        'kc': fields.boolean('Keep cool items'),
        'cs': fields.boolean('Controlled substances'),
        'dg': fields.boolean('Dangerous goods'),
        'product_list': fields.many2one('product.list', 'Product List', select=True),
        'family':       fields.many2one('product.list', 'Family',       select=True),

        # Finally, we want to give the user some feedback about what's going
        # to be imported
        'products_preview': fields.many2many('product.product', 'products_preview_rel', 'product_id', 'stock_inventory_select_products_id',  string="Products preview", readonly=True),
    }

    def create(self, cr, user, vals, context=None):

        context = context is None and {} or context

        assert 'inventory_id' in vals
        assert 'full_inventory' in vals

        return super(stock_inventory_select_products, self).create(cr, user, vals, context=context)




stock_inventory_select_products()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
