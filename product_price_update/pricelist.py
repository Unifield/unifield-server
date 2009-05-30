# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2009 Gábor Dukai
#    Parts of this module are based on product_listprice_upgrade
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields, osv
from tools.misc import debug

class product_price_update_wizard(osv.osv_memory):
    """This is the main part of the module. After filling in the form, a
    button calls action_update() to update the prices."""
    _name = 'product.price.update.wizard'

    _columns = {
        'price_type_id': fields.many2one('product.price.type', 'Price to Update', \
            required=True, change_default=True),
        'pricelist_id': fields.many2one('product.pricelist', 'Select a Pricelist', \
            required=True, domain=[('type', '=', 'internal')]),
        'categ_ids': fields.many2many('product.category', 'product_category_rel', \
            'pricewizard_ids', 'categ_ids', 'Select Product Categories', required=True),
        'upgrade': fields.boolean('Update child categories'),
    }

    _defaults = {
        'upgrade': lambda *a: 1,
    }

    def action_update(self, cr, uid, ids, context=None):
        """The recursive _update() function is called for every selected
        product category. _update() uses the selected pricelist to calculate
        the prices and the results are written to the product object."""
        pricelist_obj = self.pool.get('product.pricelist')
        cat_obj = self.pool.get('product.category')
        prod_obj = self.pool.get('product.product')

        wiz = self.browse(cr, uid, ids[0])
        done = set()
        self.updated_products = 0
        def _update(categ_id):
            if wiz.upgrade:
                child_ids = cat_obj.search(cr, uid, [('parent_id', '=', categ_id),])
                for child_id in child_ids:
                    _update(child_id)
            #if both parent and child categories are given in wiz.categ_ids, then
            #the child categories would be computed twice because of the recursion
            if categ_id not in done:
                prod_ids = prod_obj.search(cr, uid, [('categ_id', '=', categ_id),])
                for prod_id in prod_ids:
                    price = pricelist_obj.price_get(cr, uid, \
                        [wiz.pricelist_id.id], prod_id, 1)
                    prod_obj.write(cr, uid, [prod_id], {
                        wiz.price_type_id.field: price[wiz.pricelist_id.id]})
                    self.updated_products += 1
                done.add(categ_id)
        for categ_id in (br.id for br in wiz.categ_ids):
            _update(categ_id)
        return {
                "context"  : {'updated_field': wiz.price_type_id.name,
                              'updated_products': self.updated_products,},
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'product.price.update.wizard.done',
                'type': 'ir.actions.act_window',
                'target':'new',
        }


product_price_update_wizard()

class product_price_update_wizard_done(osv.osv_memory):
    """Displays the main wizard's results. This is called with the
    return statement of the main wizard and context is used to pass
    the field values."""
    _name = 'product.price.update.wizard.done'

    _columns = {
        'updated_field': fields.char('Updated price type', size=30, readonly=True),
        'updated_products': fields.float('Number of updated products', readonly=True),
    }

    _defaults = {
        'updated_field': lambda self, cr, uid, c: c['updated_field'],
        'updated_products': lambda self, cr, uid, c: c['updated_products'],
    }

product_price_update_wizard_done()