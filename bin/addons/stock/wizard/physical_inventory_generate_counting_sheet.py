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

class physical_inventory_generate_counting_sheet(osv.osv_memory):
    _name = "physical.inventory.generate.counting.sheet"
    _description = "Generate counting sheet from selected products"

    _columns = {
        'inventory_id': fields.many2one('physical.inventory', _('Inventory'), readonly=True),
        'prefill_bn': fields.boolean(_('Prefill Batch Numbers')),
        'prefill_ed': fields.boolean(_('Prefill Expiry Dates')),
    }

    _defaults = {
        'prefill_bn': True,
        'prefill_ed': True
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

        # Get location, products selected, and existing inventory lines
        inventory_id = read_single(self._name, wizard_id, "inventory_id")
        inventory = read_many("physical.inventory", [inventory_id], ['location_id',
                                                                     'counting_line_ids',
                                                                     'product_ids'])[0]

        # Get relevant info for products to be able to create the inventory
        # lines
        location_id = inventory["location_id"][0]
        product_ids = inventory["product_ids"]

        bn_and_eds = self.get_BN_and_ED_for_products_at_location(cr, uid, location_id, product_ids, context=context)

        # Prepare the inventory lines to be created

        inventory_counting_lines_to_create = []
        for product_id in product_ids:
            bn_and_eds_for_this_product = bn_and_eds[product_id]
            # If no bn / ed related to this product, create a single inventory
            # line
            if len(bn_and_eds_for_this_product) == 0:
                values = { "line_no": len(inventory_counting_lines_to_create) + 1,
                           "inventory_id": inventory_id,
                           "product_id": product_id,
                           "batch_number": False,
                           "expiry_date": False
                         }
                inventory_counting_lines_to_create.append(values)
            # Otherwise, create an inventory line for this product ~and~ for
            # each BN/ED
            else:
                for bn_and_ed in bn_and_eds_for_this_product:
                    values = { "line_no": len(inventory_counting_lines_to_create) + 1,
                               "inventory_id": inventory_id,
                               "product_id": product_id,
                               "batch_number": bn_and_ed[0] if prefill_bn else False,
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


    def get_BN_and_ED_for_products_at_location(self, cr, uid, location_id, product_ids, context=None):
        context = context if context else {}
        def read_many(model, ids, columns):
            return self.pool.get(model).read(cr, uid, ids, columns, context=context)

        # Get the moves at location, related to these products
        moves_at_location = self.get_moves_at_location(cr, uid, location_id, context=context)

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

            batch_number = move["prodlot_id"][1] if isinstance(move["prodlot_id"], tuple) else False
            expired_date = move["expired_date"]

            # Dirty hack to ignore/hide internal batch numbers ("MSFBN")
            if batch_number and batch_number.startswith("MSFBN"):
                batch_number = False

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

physical_inventory_generate_counting_sheet()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
