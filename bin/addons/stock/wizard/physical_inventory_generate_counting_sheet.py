# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _
import time
assert _

class physical_inventory_generate_counting_sheet(osv.osv_memory):
    _name = "physical.inventory.generate.counting.sheet"
    _description = "Generate counting sheet from selected products"

    _columns = {
        'inventory_id': fields.many2one('physical.inventory', 'Inventory', readonly=True),
        'prefill_bn': fields.boolean('Prefill Batch Numbers'),
        'prefill_ed': fields.boolean('Prefill Expiry Dates'),
        'only_with_stock_level': fields.boolean('Only count lines with stock different than 0'),
    }

    _defaults = {
        'prefill_bn': True,
        'prefill_ed': True,
        'only_with_stock_level': False,
    }

    def create(self, cr, user, vals, context=None):

        context = context if context else {}

        assert 'inventory_id' in vals

        return super(physical_inventory_generate_counting_sheet, self).create(cr, user, vals, context=context)


    def generate_counting_sheet(self, cr, uid, wizard_ids, context=None):
        context = context if context else {}
        def read_single(model, id_, column):
            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
        def write(model, id_, vals):
            return self.pool.get(model).write(cr, uid, [id_], vals, context=context)

        # Get this wizard...
        assert len(wizard_ids) == 1
        wizard_id = wizard_ids[0]

        # Get the selected option
        prefill_bn = read_single(self._name, wizard_id, 'prefill_bn')
        prefill_ed = read_single(self._name, wizard_id, 'prefill_ed')
        only_with_stock_level = read_single(self._name, wizard_id, 'only_with_stock_level')

        # Get location, products selected, and existing inventory lines
        inventory_id = read_single(self._name, wizard_id, "inventory_id")
        inventory = read_many("physical.inventory", [inventory_id], ['location_id',
                                                                     'counting_line_ids',
                                                                     'product_ids'])[0]

        # Get relevant info for products to be able to create the inventory
        # lines
        location_id = inventory["location_id"][0]
        product_ids = inventory["product_ids"]

        bn_and_eds = self.get_BN_and_ED_for_products_at_location(cr, uid, location_id, product_ids, only_with_stock_level, context=context)

        # Prepare the inventory lines to be created

        inventory_counting_lines_to_create = []
        current_prodlot_id = False
        for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
            bn_and_eds_for_this_product = bn_and_eds[product.id]
            # If no bn / ed related to this product, create a single inventory
            # line
            if not product.batch_management and not product.perishable:
                if only_with_stock_level and not self.not_zero_stock_on_location(cr, uid, location_id, product.id,
                                                                                 current_prodlot_id, context=context):
                    continue
                else:
                    values = {
                        "line_no": len(inventory_counting_lines_to_create) + 1,
                        "inventory_id": inventory_id,
                        "product_id": product.id,
                        "batch_number": False,
                        "expiry_date": False
                    }
                    inventory_counting_lines_to_create.append(values)
            # Otherwise, create an inventory line for this product ~and~ for
            # each BN/ED
            else:
                for bn_and_ed in bn_and_eds_for_this_product:
                    current_prodlot = bn_and_ed[0] if prefill_bn else False
                    current_prodlot_id = self.pool.get('stock.production.lot').search(cr, uid, [('name', '=', current_prodlot)],
                                                                                      context=context)[0] if prefill_bn else False
                    if only_with_stock_level and not self.not_zero_stock_on_location(cr, uid, location_id, product.id,
                                                                                     current_prodlot_id, context=context):
                        continue
                    else:
                        values = {
                            "line_no": len(inventory_counting_lines_to_create) + 1,
                            "inventory_id": inventory_id,
                            "product_id": product.id,
                            "batch_number": current_prodlot,
                            "expiry_date":  bn_and_ed[1] if prefill_ed else False
                        }
                        inventory_counting_lines_to_create.append(values)

        # Get the existing inventory counting lines (to be cleared)

        existing_inventory_counting_lines = inventory["counting_line_ids"]

        # Prepare the actual create/remove for inventory lines
        # 2 is the code for removal/deletion, 0 is for addition/creation

        delete_existing_inventory_counting_lines = [ (2,line_id) for line_id in existing_inventory_counting_lines ]

        create_inventory_counting_lines = [ (0,0,line_values) for line_values in inventory_counting_lines_to_create ]

        todo = []
        todo.extend(delete_existing_inventory_counting_lines)
        todo.extend(create_inventory_counting_lines)

        # Do the actual write
        # TODO : Test if Draft state here
        write("physical.inventory", inventory_id, {'counting_line_ids': todo,
                                                   'state': 'counting'})

        return {'type': 'ir.actions.act_window_close'}

    def get_BN_and_ED_for_products_at_location(self, cr, uid, location_id, product_ids, only_with_stock_level, context=None):
        context = context if context else {}
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        # Add location to the copied context
        ctx = context.copy()
        ctx['location'] = location_id
        ctx['compute_child'] = True

        # Get the moves at location, related to these products
        moves_at_location = self.get_moves_at_location(cr, uid, location_id, context=ctx)

        moves_at_location_for_products = [ m for m in moves_at_location
                                           if m["product_id"][0] in product_ids ]

        # Get the production lot associated to these moves
        moves_at_location_for_products = read_many("stock.move",
                                                   moves_at_location_for_products,
                                                   ["product_id",
                                                    "prodlot_id",
                                                    "expired_date"])

        # Init a dict with an empty set for each products
        BN_and_ED = { product_id:set() for product_id in product_ids }

        for move in moves_at_location_for_products:

            product_id = move["product_id"][0]
            product_qty = self.pool.get('product.product').browse(cr, uid, product_id, fields_to_fetch=['qty_available'],
                                                                  context=ctx).qty_available

            batch_number = move["prodlot_id"][1] if isinstance(move["prodlot_id"], tuple) else False
            expired_date = move["expired_date"]

            # Dirty hack to ignore/hide internal batch numbers ("MSFBN")
            if batch_number and batch_number.startswith("MSFBN"):
                batch_number = False

            if not only_with_stock_level or (only_with_stock_level and product_qty != 0):
                BN_and_ED[product_id].add((batch_number, expired_date))

        return BN_and_ED

    # FIXME : this is copy/pasta from the other wizard ...
    # Should be factorized, probably in physical inventory, or stock somewhere.
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

    def not_zero_stock_on_location(self, cr, uid, location_id, product_id, prodlot_id, context=False):
        '''
        Check if the product's stock on the inventory's location is != 0
        '''
        if not context:
            context = {}

        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        not_zero = True

        domain = [('product_id', '=', product_id), ('prodlot_id', '=', prodlot_id), ('state', '=', 'done'),
                  '|', ('location_id', '=', location_id), ('location_dest_id', '=', location_id)]
        move_ids = move_obj.search(cr, uid, domain, context=context)

        product_qty = 0.00
        used_fields = ['location_id', 'location_dest_id', 'product_id', 'product_qty', 'product_uom']
        for move in move_obj.browse(cr, uid, move_ids, fields_to_fetch=used_fields, context=context):
            # If the move is from the same location as destination
            if move.location_dest_id.id == move.location_id.id or move.product_qty == 0.00:
                continue

            if move.product_uom.id != move.product_id.uom_id.id:
                to_unit = move.product_id.uom_id.id
                qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, to_unit)
            else:
                qty = move.product_qty

            if move.location_dest_id.id == location_id:  # IN qty
                product_qty += qty
            elif move.location_id.id == location_id:  # OUT qty
                product_qty -= qty

        if product_qty == 0:
            not_zero = False

        return not_zero


physical_inventory_generate_counting_sheet()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
