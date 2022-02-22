# -*- coding: utf-8 -*-

from osv import fields, osv
from tools.translate import _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import itertools
assert _


class physical_inventory_generate_counting_sheet(osv.osv_memory):
    _name = "physical.inventory.generate.counting.sheet"
    _description = "Generate counting sheet from selected products"

    _columns = {
        'inventory_id': fields.many2one('physical.inventory', 'Inventory', readonly=True),
        'prefill_bn': fields.boolean('Prefill Batch Numbers'),
        'prefill_ed': fields.boolean('Prefill Expiry Dates'),
        'only_with_stock_level': fields.boolean('Only count lines with stock different than 0'),
        'only_with_pos_move': fields.boolean('Only count lines with stock & moves different than 0'),
        'recent_moves_months': fields.char('Recent Moves', size=256),
    }

    _defaults = {
        'prefill_bn': True,
        'prefill_ed': True,
        'only_with_stock_level': False,
        'only_with_pos_move': False,
        'recent_moves_months': False,
    }

    def create(self, cr, user, vals, context=None):

        context = context if context else {}

        assert 'inventory_id' in vals

        return super(physical_inventory_generate_counting_sheet, self).create(cr, user, vals, context=context)

    def onchange_prefill_bn(self, cr, uid, ids, prefill_bn, only_with_stock_level):
        if not prefill_bn and not only_with_stock_level:
            return {'value': {'only_with_pos_move': False}}
        else:
            return True

    def onchange_prefill_ed(self, cr, uid, ids, prefill_ed, only_with_stock_level):
        if not prefill_ed and not only_with_stock_level:
            return {'value': {'only_with_pos_move': False}}
        else:
            return True

    def onchange_only_with_stock_level(self, cr, uid, ids, only_with_stock_level, only_with_pos_move):
        if only_with_stock_level and only_with_pos_move:
            return {'value': {'only_with_pos_move': False}}
        else:
            return True

    def onchange_only_with_pos_move(self, cr, uid, ids, only_with_pos_move, only_with_stock_level):
        if only_with_pos_move and only_with_stock_level:
            return {'value': {'only_with_stock_level': False}}
        else:
            return True

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

        # Get the options
        wiz_data = read_many(self._name, wizard_id, ['prefill_bn', 'prefill_ed', 'only_with_stock_level',
                                                     'only_with_pos_move'])

        # Get location, products selected, and existing inventory lines
        inventory_id = read_single(self._name, wizard_id, "inventory_id")
        inventory = read_many("physical.inventory", [inventory_id], ['location_id',
                                                                     'counting_line_ids',
                                                                     'product_ids', 'max_filter_months'])[0]

        # Get relevant info for products to be able to create the inventory
        # lines
        location_id = inventory["location_id"][0]
        product_ids = inventory["product_ids"]

        # Get the month used if "Only count lines with stock & moves different than 0" has been selected
        months = 0
        if  wiz_data['only_with_pos_move']:
            months = inventory['max_filter_months']

        # Prepare the inventory lines to be created
        inventory_counting_lines_to_create = []
        if not wiz_data['prefill_bn'] and not wiz_data['prefill_ed']:
            prods = self.pool.get('product.product').browse(cr, uid, product_ids, fields_to_fetch=['batch_management', 'perishable'], context=context)
            for prod in prods:
                if prod.batch_management or prod.perishable:
                    for x in itertools.repeat(None, 3):
                        values = {
                            "line_no": len(inventory_counting_lines_to_create) + 1,
                            "inventory_id": inventory_id,
                            "product_id": prod.id,
                            "batch_number": False,
                            "expiry_date": False
                        }
                        inventory_counting_lines_to_create.append(values)
                elif not wiz_data['only_with_stock_level'] or (wiz_data['only_with_stock_level'] and self.not_zero_stock_on_location(cr, uid, location_id, prod.id, False, False, context=context)):
                    values = {
                        "line_no": len(inventory_counting_lines_to_create) + 1,
                        "inventory_id": inventory_id,
                        "product_id": prod.id,
                        "batch_number": False,
                        "expiry_date": False
                    }
                    inventory_counting_lines_to_create.append(values)
        else:
            bn_and_eds = self.get_BN_and_ED_for_products_at_location(cr, uid, location_id, product_ids, context=context)

            for key in sorted(list(bn_and_eds.keys()), key=lambda x: x[1]):
                product_id = key[0]
                bn_and_eds_for_this_product = bn_and_eds[key]
                # If no bn / ed related to this product, create a single inventory
                # line
                if bn_and_eds_for_this_product == (False, False, False):
                    if wiz_data['only_with_stock_level'] and not self.not_zero_stock_on_location(cr, uid, location_id, product_id, False, False, context=context):
                        continue
                    else:
                        values = {
                            "line_no": len(inventory_counting_lines_to_create) + 1,
                            "inventory_id": inventory_id,
                            "product_id": product_id,
                            "batch_number": False,
                            "expiry_date": False
                        }
                        inventory_counting_lines_to_create.append(values)
                elif not bn_and_eds_for_this_product:
                    # BN/ED product with no stock move in this location
                    if not wiz_data['only_with_stock_level'] and not wiz_data['only_with_pos_move']:
                        values = {
                            "line_no": len(inventory_counting_lines_to_create) + 1,
                            "inventory_id": inventory_id,
                            "product_id": product_id,
                            "batch_number": False,
                            "expiry_date": False
                        }
                        inventory_counting_lines_to_create.append(values)
                else:
                    # Otherwise, create an inventory line for this product ~and~ for
                    # each BN/ED
                    for bn_and_ed in sorted(bn_and_eds_for_this_product, key=lambda x: x[1] or x[0]):
                        if (wiz_data['only_with_stock_level'] and not self.not_zero_stock_on_location(cr, uid, location_id, product_id, bn_and_ed[2], False, context=context)) or\
                                (wiz_data['only_with_pos_move'] and not self.not_zero_stock_on_location(cr, uid, location_id, product_id, bn_and_ed[2], months, context=context)):
                            continue
                        else:
                            values = {
                                "line_no": len(inventory_counting_lines_to_create) + 1,
                                "inventory_id": inventory_id,
                                "product_id": product_id,
                                "batch_number": bn_and_ed[0] if wiz_data['prefill_bn'] else False,
                                "expiry_date": bn_and_ed[1] if wiz_data['prefill_ed'] else False
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

    def get_BN_and_ED_for_products_at_location(self, cr, uid, location_id, product_ids, context=None):
        if context is None:
            context = {}

        prod_info = {}
        move_obj = self.pool.get('stock.move')
        prod_obj = self.pool.get('product.product')

        BN_and_ED = {}
        default_code_dict = {}
        for prod in prod_obj.read(cr, uid, product_ids, ['batch_management', 'perishable', 'default_code'], context=context):
            default_code_dict[prod['id']] = prod['default_code']
            key = (prod['id'], prod['default_code'])
            if not prod['batch_management'] and not prod['perishable']:
                BN_and_ED[key] = (False, False, False)
            else:
                prod_info[prod['id']] = prod
                BN_and_ED[key] = set()

        domain = ['&', '&', '|',
                  ('location_id', 'in', [location_id]),
                  ('location_dest_id', 'in', [location_id]),
                  ('state', '=', 'done'),
                  ('product_id', 'in', list(prod_info.keys())),
                  ('prodlot_id', '!=', False),
                  ('product_qty', '!=', 0),
                  ]

        move_ids = move_obj.search(cr, uid, domain, context=context)

        for move in move_obj.browse(cr, uid, move_ids, fields_to_fetch=['product_id', 'prodlot_id', 'expired_date'], context=context):
            product_id = move.product_id.id

            if move.prodlot_id and move.prodlot_id.type == 'internal':
                if prod_info.get(product_id, {}).get('batch_management'):
                    # old move when product was ED only, now it's BN so ignore the move
                    continue
                batch_number = False
            else:
                if not prod_info.get(product_id, {}).get('batch_management'):
                    # old move when this product was BN, now it's ED only so ignore this stock move
                    continue
                batch_number = move.prodlot_id.name

            key = (product_id, default_code_dict.get(product_id))
            BN_and_ED[key].add((batch_number, move.expired_date, move.prodlot_id.id))

        return BN_and_ED

    def not_zero_stock_on_location(self, cr, uid, location_id, product_id, prodlot_id, months, context=False):
        '''
        Check if the product's stock on the inventory's location is != 0
        '''
        if not context:
            context = {}

        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')

        domain = [('product_id', '=', product_id), ('prodlot_id', '=', prodlot_id), ('state', '=', 'done'),
                  '|', ('location_id', '=', location_id), ('location_dest_id', '=', location_id)]

        max_date = False
        if months:
            max_date =  (datetime.today() + relativedelta(months=-months)).strftime('%Y-%m-%d 00:00:00')

        move_ids = move_obj.search(cr, uid, domain, context=context)

        product_qty = 0.00
        used_fields = ['location_id', 'location_dest_id', 'product_id', 'product_qty', 'product_uom', 'date']
        last_move = False
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
            if not last_move or move.date > last_move:
                last_move = move.date

        if product_qty == 0:
            if max_date and last_move >= max_date:
                return True

            return False

        return True


physical_inventory_generate_counting_sheet()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
