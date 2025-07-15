# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _
assert _
from datetime import datetime
from dateutil.relativedelta import relativedelta

# This will be a tuple ((1,"1 months" ), (2, "2 months"), ...)
MOVED_IN_LAST_X_MONTHS_FULL_INV = tuple([("%s" % i, _("%s months") % str(i)) for i in range(0, 13)])
MOVED_IN_LAST_X_MONTHS = tuple([(i, _("%s months") % str(i)) for i in range(1, 13)])


class physical_inventory_select_products(osv.osv_memory):
    _name = "physical.inventory.select.products"
    _description = "Select product to consider for inventory, using filters"

    _columns = {

        'inventory_id': fields.many2one('physical.inventory', 'Inventory', readonly=True),
        'full_inventory': fields.boolean('Full Inventory'),

        # If this is a full inventory, we'll add products in stock at that
        # location + products with recent moves at that location
        'recent_moves_months_fullinvo': fields.selection(MOVED_IN_LAST_X_MONTHS_FULL_INV, "Moved in the last", select=True),

        # For partial inventories :

        # First filter is to select products either in stock, or with recent
        # moves at that location
        'first_filter': fields.selection((('in_stock', "Products currently in stock at location"),
                                          ('recent_movements', "Products with recent movement at location")),
                                         "First filter", select=True),
        'recent_moves_months': fields.selection(MOVED_IN_LAST_X_MONTHS, "Moved in the last", select=True),

        # Second filter is to select a family / product list / 'special care' products
        'second_filter': fields.selection((('all', "All"),
                                           ('family', "All from a family"),
                                           ('productlist', "All from a product list"),
                                           ('specialcare', "CC/CS/DG")),
                                          "Second filter", select=True),
        'kc': fields.boolean('Cold chain items'),
        'cs': fields.boolean('Controlled substances'),
        'dg': fields.boolean('Dangerous goods'),
        'product_list': fields.many2one('product.list', 'Product List', select=True),

        # mandatory nomenclature levels
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', readonly=False, select=1),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', readonly=False, select=1),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', readonly=False, select=1),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', readonly=False, select=1),

        # Finally, we want to give the user some feedback about what's going
        # to be imported
        'products_preview': fields.many2many('product.product', 'products_preview_rel', 'product_id',
                                             'physical_inventory_select_products_id', string="Products preview",
                                             readonly=True),
    }

    def create(self, cr, user, vals, context=None):

        context = context if context else {}

        assert 'inventory_id' in vals
        assert 'full_inventory' in vals

        return super(physical_inventory_select_products, self).create(cr, user, vals, context=context)

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

        context = context if context else {}

        return self.pool.get('product.product') \
            .onChangeSearchNomenclature(cr, uid, id, position, type,
                                        nomen_manda_0,
                                        nomen_manda_1,
                                        nomen_manda_2,
                                        nomen_manda_3,
                                        num=num,
                                        prod_code=False,
                                        international_status=False,
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
        context = context if context else {}

        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]

        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        # Get this wizard...
        assert len(wizard_ids) == 1
        wizard_id = wizard_ids[0]

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
        location_id = read_single('physical.inventory', w["inventory_id"], "location_id")[0]

        # Full inventory case
        if w["full_inventory"]:

            # Get products in stock at that location, or recently moved
            products_in_stock = self.get_products_in_stock_at_location(cr, uid, location_id, context=context)
            products_recently_moved = set()
            if w['recent_moves_months_fullinvo'] != '0':
                products_recently_moved = self.get_products_with_recent_moves_at_location(cr, uid, location_id,
                                                                                          w['recent_moves_months_fullinvo'],
                                                                                          context=context)
            products = products_in_stock.union(products_recently_moved)

            # Show them in the preview
            self.update_product_preview(cr, uid, wizard_id, products, context=context)

        # Partial inventory case
        else:

            # Handle the first filter
            if w["first_filter"] == "in_stock":
                products = self.get_products_in_stock_at_location(cr, uid, location_id, context=context)
            elif w["first_filter"] == "recent_movements":
                products = self.get_products_with_recent_moves_at_location(cr, uid, location_id,
                                                                           w['recent_moves_months'], context=context)
            else:
                # Does not happens
                pass

            # Handle the second filter
            if w['second_filter'] == 'productlist':
                product_list_id = read_single(self._name, wizard_id, "product_list")
                products = self.filter_products_with_product_list(cr, uid, products, product_list_id, context=context)

            elif w['second_filter'] == 'specialcare':
                special_care_criterias = [c for c in ['kc', 'cs', 'dg'] if w[c]]
                products = self.filter_products_with_special_care(cr, uid, products, special_care_criterias,
                                                                  context=context)

            elif w['second_filter'] == 'family':
                nomenclature = {name: w[name] for name in ['nomen_manda_0',
                                                           'nomen_manda_1',
                                                           'nomen_manda_2',
                                                           'nomen_manda_3'
                                                           ] if w[name]}
                products = self.filter_products_with_nomenclature(cr, uid, products, nomenclature, context=context)

            else:
                # Nothing to do, keep all the products found with first filter
                pass

            # Show them in the preview
            self.update_product_preview(cr, uid, wizard_id, products, context=context)
        return {}


    def update_product_preview(self, cr, uid, wizard_id, product_ids, context=None):
        context = context if context else {}

        assert isinstance(wizard_id, int)
        assert isinstance(product_ids, list) or isinstance(product_ids, set)

        # '6' is the code for 'replace all'
        vals = {"products_preview": [(6, 0, list(product_ids))]}

        self.write(cr, uid, [wizard_id], vals, context=context)

    def get_moves_at_location(self, cr, uid, location_id, context=None):
        context = context if context else {}

        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        assert isinstance(location_id, int)

        # Get all the moves for in/out of that location
        from_or_to_location = ['&', '|',
                               ('location_id', 'in', [location_id]),
                               ('location_dest_id', 'in', [location_id]),
                               ('state', '=', 'done')]

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
        context = context if context else {}

        assert isinstance(location_id, int)

        moves_at_location = self.get_moves_at_location(cr, uid, location_id, context=None)

        # Init stock at 0 for products
        stocks = {}
        for product_id in set([m["product_id"][0] for m in moves_at_location]):
            stocks[product_id] = 0.0

        # Sum all lines
        for move in moves_at_location:

            product_id = move["product_id"][0]
            product_qty = move["product_qty"]

            move_out = (move["location_id"][0] == location_id)
            move_in = (move["location_dest_id"][0] == location_id)

            if move_in:
                stocks[product_id] += product_qty
            elif move_out:
                stocks[product_id] -= product_qty
            else:
                # This shouldnt happen
                pass

        # Keep only products for which stock != 0 (including negative ones)
        products_in_stock = set([p_id
                                 for p_id, stock in list(stocks.items())
                                 if stock != 0.0])

        return products_in_stock

    def get_products_with_recent_moves_at_location(self, cr, uid, location_id, recent_moves_months, context=None):
        context = context if context else {}

        if isinstance(recent_moves_months, str):
            recent_moves_months = int(recent_moves_months)
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

    def filter_products_with_special_care(self, cr, uid, product_ids, special_care_criterias, context=None):
        context = context if context else {}

        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        assert isinstance(special_care_criterias, list)
        assert isinstance(product_ids, list) or isinstance(product_ids, set)

        domain_filter = [('id', 'in', list(product_ids))]

        # To convert wizard option to column name in product.product
        special_care_column_name = {'kc': 'is_kc',
                                    'cs': 'is_cs',
                                    'dg': 'is_dg'}

        # Add special care criterias to the domain
        for criteria in special_care_criterias:
            column_name = special_care_column_name[criteria]
            domain_filter = ['&'] + domain_filter + [(column_name, '=', True)]

        # Perform the search/fitlering
        products_filtered = search('product.product', domain_filter)

        return products_filtered

    def filter_products_with_nomenclature(self, cr, uid, product_ids, nomenclature, context=None):
        context = context if context else {}

        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        assert isinstance(nomenclature, dict)
        assert isinstance(product_ids, list) or isinstance(product_ids, set)

        domain_filter = [('id', 'in', list(product_ids))]

        # Add nomenclature to the domain
        for name, value in list(nomenclature.items()):
            domain_filter = ['&'] + domain_filter + [(name, '=', value)]

        # Perform the search/fitlering
        products_filtered = search('product.product', domain_filter)

        return products_filtered

    def filter_products_with_product_list(self, cr, uid, product_ids, product_list_id, context=None):
        context = context if context else {}

        def search(model, domain):
            return self.pool.get(model).search(cr, uid, domain, context=context)

        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        # Get all the product ids in the list
        product_lines_in_list = search('product.list.line',
                                       [('list_id', '=', product_list_id)])

        product_ids_in_list = read_many('product.list.line',
                                        product_lines_in_list,
                                        ['name'])

        product_ids_in_list = set([l['name'][0] for l in product_ids_in_list])

        # Now use these products in list to filter the products in input
        product_ids_in_list = product_ids_in_list.intersection(product_ids)

        return product_ids_in_list

    #
    # When clicking 'Add product'
    #
    def add_products(self, cr, uid, wizard_ids, context=None):
        context = context if context else {}

        # Get this wizard...
        assert len(wizard_ids) == 1
        wizard_id = wizard_ids[0]

        self.refresh_products(cr, uid, [wizard_id], context=context)
        self.update_products_in_inventory(cr, uid, wizard_id, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def update_products_in_inventory(self, cr, uid, wizard_id, context=None):
        context = context if context else {}

        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]

        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        def write(model, id_, vals):
            return self.pool.get(model).write(cr, uid, [id_], vals, context=context)

        assert isinstance(wizard_id, int)

        wiz_data = read_many(self._name, wizard_id, ["inventory_id", "products_preview", "first_filter", "recent_moves_months", "recent_moves_months_fullinvo", "full_inventory"])
        inventory_id = wiz_data["inventory_id"]
        product_ids = wiz_data["products_preview"]

        # Redo a search to force order according to default order
        inventory_data= self.pool.get('physical.inventory').read(cr, uid, inventory_id, ['product_ids', 'max_filter_months', 'multiple_filter_months'], context=context)
        product_ids = inventory_data['product_ids'] + product_ids
        product_ids = self.pool.get("product.product").search(cr, uid, [("id", 'in', product_ids)], context=context)

        # '6' is the code for 'replace all'
        vals = {'product_ids': [(6, 0, product_ids)], 'products_added': True}

        # Check if 'recent_movements' has been used
        if wiz_data['products_preview'] and (wiz_data['first_filter'] == 'recent_movements' or wiz_data['full_inventory'] and wiz_data['recent_moves_months_fullinvo']):
            if wiz_data['full_inventory']:
                nb_months = int(wiz_data['recent_moves_months_fullinvo'])
            else:
                nb_months = wiz_data['recent_moves_months']
            if nb_months > inventory_data['max_filter_months']:
                vals['max_filter_months'] = nb_months
            if not inventory_data['multiple_filter_months'] and inventory_data['max_filter_months'] != -1  and nb_months != inventory_data['max_filter_months']:
                vals['multiple_filter_months'] = True

        write('physical.inventory', inventory_id, vals)


physical_inventory_select_products()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
