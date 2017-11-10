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
        'inventory_id': fields.many2one('physical.inventory', 'Inventory', readonly=True),
        'fill_bn_and_ed': fields.boolean('Prefill Batch Numbers and Expiry Date'),
    }

    def create(self, cr, user, vals, context=None):

        context = {} if context else context

        assert 'inventory_id' in vals

        return super(physical_inventory_generate_counting_sheet, self).create(cr, user, vals, context=context)


    def get_BN_and_ED_for_products(self, cr, uid, location_id, product_ids, context=None):
        context = {} if context else context
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

            BN_and_ED[product_id].add((move["prodlot_id"][0],
                                       move["expired_date"]))

#    def refresh_products(self, cr, uid, wizard_ids, context=None):
#        context = {} if context else context
#
#        def read_single(model, id_, column):
#            return self.pool.get(model).read(cr, uid, [id_], [column], context=context)[0][column]
#
#        def read_many(model, ids, columns):
#            return self.pool.get(model).read(cr, uid, ids, columns, context=context)
#
#        # Get this wizard...
#        assert len(wizard_ids) == 1
#        wizard_id = wizard_ids[0]
#
#        inventory_id = read_single(self._name, wizard_id, "inventory_id")
#
#        # Get the selected options
#        w = read_many(self._name, [wizard_id], ['inventory_id',
#                                                'full_inventory',
#                                                'recent_moves_months_fullinvo',
#                                                'first_filter',
#                                                'recent_moves_months',
#                                                'second_filter',
#                                                'kc',
#                                                'cs',
#                                                'dg',
#                                                'product_list',
#                                                'nomen_manda_0',
#                                                'nomen_manda_1',
#                                                'nomen_manda_2',
#                                                'nomen_manda_3'])[0]
#
#        # Find the location of the inventory
#        location_id = read_single('physical.inventory', w["inventory_id"], "location_id")[0]

physical_inventory_generate_counting_sheet()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
