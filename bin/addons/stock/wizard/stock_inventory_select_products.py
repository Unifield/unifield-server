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
from datetime import datetime
from dateutil.relativedelta import relativedelta

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

        # mandatory nomenclature levels
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', readonly=False, select=1),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group',     readonly=False, select=1),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family',    readonly=False, select=1),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root',      readonly=False, select=1),

        # Finally, we want to give the user some feedback about what's going
        # to be imported
        'products_preview': fields.many2many('product.product', 'products_preview_rel', 'product_id', 'stock_inventory_select_products_id',  string="Products preview", readonly=True),
    }


    def create(self, cr, user, vals, context=None):

        context = {} if context else context

        assert 'inventory_id' in vals
        assert 'full_inventory' in vals

        return super(stock_inventory_select_products, self).create(cr, user, vals, context=context)


    #
    # Nomenclature management
    #
    def onChangeSearchNomenclature(self, cr, uid, id, position, type,
                                   nomen_manda_0,
                                   nomen_manda_1,
                                   nomen_manda_2,
                                   nomen_manda_3,
                                   num=True,
                                   context=None):

        context = {} if context else context

        return self.pool.get('product.nomenclature') \
               .onChangeSearchNomenclature(cr, uid, id, position, type,
                                           nomen_manda_0,
                                           nomen_manda_1,
                                           nomen_manda_2,
                                           nomen_manda_3,
                                           num=num,
                                           context=context)


    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)
    #
    # END Nomenclature management
    #


    #
    # When clicking 'Refresh'
    #
    def refresh_products(self, cr, uid, wizard_ids, context=None):
        context = {} if context else context
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        # Get this wizard...
        assert len(wizard_ids) == 1
        wizard_id = wizard_ids[0]

        inventory_id = read_single(self._name, wizard_id, "inventory_id")

        # Get the selected options
        w = read_many(self._name, [wizard_id], ['inventory_id',
                                                'full_inventory',
                                                'recent_moves_months_fullinvo',
                                                'first_filter',
                                                'recent_moves_months',
                                                'second_filter',
                                                'kc',
                                                'cs',
                                                'dg',
                                                'product_list',
                                                'nomen_manda_0',
                                                'nomen_manda_1',
                                                'nomen_manda_2',
                                                'nomen_manda_3'])[0]

        # Find the location of the inventory
        location_id = read_single('stock.inventory', w["inventory_id"], "location_id")[0]

        # Full inventory case
        if w["full_inventory"]:

            # Get products in stock at that location, or recently moved
            products_in_stock = self.get_products_in_stock_at_location(cr, uid, location_id, context=context)
            products_recently_moved = self.get_products_with_recent_moves_at_location(cr, uid, location_id, w['recent_moves_months_fullinvo'], context=context)
            products = products_in_stock.union(products_recently_moved)

            # Show them in the preview
            self.update_product_preview(cr, uid, wizard_id, products, context=context)

        # Partial inventory case
        else:

            # Handle the first option
            if w["first_filter"] == "in_stock":
                products = self.get_products_in_stock_at_location(cr, uid, location_id, context=context)
            elif w["first_filter"] == "recent_movements":
                products = self.get_products_with_recent_moves_at_location(cr, uid, location_id, w['recent_moves_months'], context=context)
            else:
                # Does not happens
                pass

            # TODO - Handle the second option...

            # Show them in the preview
            self.update_product_preview(cr, uid, wizard_id, products, context=context)


    def update_product_preview(self, cr, uid, wizard_id, product_ids, context=None):
        context = {} if context else context

        assert isinstance(wizard_id, int)
        assert isinstance(product_ids, list) or isinstance(product_ids, set)

        # '6' is the code for 'replace all'
        vals = { "products_preview": [(6, 0, list(product_ids))] }

        self.write(cr, uid, [wizard_id], vals, context=context)


    def get_moves_at_location(self, cr, uid, location_id, context=None):
        context = {} if context else context
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        assert isinstance(location_id, int)


        # Get all the moves for in/out of that location
        from_or_to_location = ['&', '|',
                               ('location_id',      'in', [location_id]),
                               ('location_dest_id', 'in', [location_id]),
                               ('state',             '=', 'done'       )]

        moves_at_location_ids = search("stock.move", from_or_to_location)
        moves_at_location = read_many("stock.move",
                                      moves_at_location_ids,
                                      ["product_id",
                                       "date",
                                       "product_qty",
                                       "location_id",
                                       "location_dest_id"])

        return moves_at_location


    def get_products_in_stock_at_location(self, cr, uid, location_id, context=None):

        assert isinstance(location_id, int)

        moves_at_location = self.get_moves_at_location(cr, uid, location_id, context=None)

        # Init stock at 0 for products
        stocks = {}
        for product_id in set([ m["product_id"][0] for m in moves_at_location]):
            stocks[product_id] = 0.0

        # Sum all lines
        for move in moves_at_location:

            product_id = move["product_id"][0]
            product_qty = move["product_qty"]

            move_out = (move["location_id"][0]      == location_id)
            move_in  = (move["location_dest_id"][0] == location_id)

            if move_in:
                stocks[product_id] += product_qty
            elif move_out:
                stocks[product_id] -= product_qty
            else:
                # This shouldnt happen
                pass

        # Keep only products for which stock > 0
        products_in_stock = set([ product_id
                                  for product_id, stock in stocks.items()
                                  if stock > 0 ])

        return products_in_stock

    def get_products_with_recent_moves_at_location(self, cr, uid, location_id, recent_moves_months, context=None):

        assert isinstance(location_id, int)
        assert isinstance(recent_moves_months, int)

        moves_at_location = self.get_moves_at_location(cr, uid, location_id, context=None)

        several_months_ago = datetime.today() + relativedelta(months=-recent_moves_months)

        # Keep only the product ids related to moves during the last few months
        recently_moved_products = set()
        for move in moves_at_location:
            # Parse the move's date
            move_date = datetime.strptime(move['date'], '%Y-%m-%d %H:%M:%S')
            if move_date > several_months_ago:
                product_id = move['product_id'][0]
                recently_moved_products.add(product_id)

        return recently_moved_products

    #
    # When clicking 'Add product'
    #
    def add_products(self, cr, uid, wizard_ids, context=None):
        context = {} if context else context

        # Get this wizard...
        assert len(wizard_ids) == 1
        wizard_id = wizard_ids[0]

        self.refresh_products(cr, uid, [wizard_id], context=context)
        self.update_products_in_inventory(cr, uid, wizard_id, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def update_products_in_inventory(self, cr, uid, wizard_id, context=None):
        context = {} if context else context
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def write(model, id_, vals):
            return self.pool.get(model).write(cr, uid, [id_], vals, context=context)

        assert isinstance(wizard_id, int)

        inventory_id = read_single(self._name, wizard_id, "inventory_id")
        product_ids = read_single(self._name, wizard_id, "products_preview")

        # '4' is the code for 'add a single id'
        vals = { 'inventory_product_selection': [(4, product_id)
                                                 for product_id in product_ids] }
        write('stock.inventory', inventory_id, vals)


stock_inventory_select_products()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
