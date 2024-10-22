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

from osv import osv
from osv import fields

import decimal_precision as dp


class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'

    def _get_manu_price_dates(self, cr, uid, ids, fields, arg, context=None):
        if not context:
            context = {}
        ret = {}
        for prod in self.browse(cr, uid, ids):
            ret[prod.id] = {}
            ret[prod.id]['check_manufacturer'] = prod.manufacturer_id and True or False
            ret[prod.id]['get_first_price'] = prod.pricelist_ids and prod.pricelist_ids[0].price or False
            ret[prod.id]['get_first_currency'] = prod.pricelist_ids and prod.pricelist_ids[0].currency_id and prod.pricelist_ids[0].currency_id.id or False
            ret[prod.id]['get_till_date'] = False
            ret[prod.id]['get_from_date'] = False
            min_qty = False
            if prod.pricelist_ids:
                for price in prod.pricelist_ids:
                    if min_qty is False or price.min_order_qty < min_qty:
                        if price.valid_till:
                            ret[prod.id]['get_till_date'] = price.valid_till
                        if price.valid_from:
                            ret[prod.id]['get_from_date'] = price.valid_from
                        min_qty = price.min_order_qty
        return ret

    _columns = {
        'manufacturer_id': fields.many2one('res.partner', string='Manufacturer', domain=[('manufacturer', '=', 1)]),
        'second_manufacturer_id': fields.many2one('res.partner', string='Second Manufacturer', domain=[('manufacturer', '=', 1)]),
        'third_manufacturer_id': fields.many2one('res.partner', string='Third Manufacturer', domain=[('manufacturer', '=', 1)]),
        'company_id': fields.many2one('res.company','Company',select=1),
        'check_manufacturer': fields.function(_get_manu_price_dates, method=True, type="boolean", string="Manufacturer", multi="compt_f"),
        'get_first_price': fields.function(_get_manu_price_dates, method=True, type="float", string="Indicative Price", digits_compute=dp.get_precision('Purchase Price Computation'), multi="compt_f"),
        'get_first_currency': fields.function(_get_manu_price_dates, method=True, type="many2one", relation="res.currency", string="Currency", multi="compt_f"),
        'get_till_date': fields.function(_get_manu_price_dates, method=True, type="date", string="Valid till date", multi="compt_f"),
        'get_from_date': fields.function(_get_manu_price_dates, method=True, type="date", string="Valid from date", multi="compt_f"),
        'active': fields.boolean('Active', help="If the active field is set to False, it allows to hide the the supplier info without removing it."),
    }
    
    _defaults = {
        'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
        'active': True,
    }


product_supplierinfo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

