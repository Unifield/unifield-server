# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv


class product_template(osv.osv):
    """
    override to add new seller_info_id : default seller but supplierinfo object
    """
    _name = 'product.template'
    _inherit = 'product.template'

    def _calc_seller(self, cr, uid, ids, fields, arg, context=None):
        result = super(product_template, self)._calc_seller(cr, uid, ids, fields, arg, context)

        for product in self.browse(cr, uid, ids, context=context):
            if product.seller_ids:
                partner_list = sorted([(partner_id.sequence, partner_id) for partner_id in product.seller_ids if partner_id and partner_id.sequence])
                main_supplier = partner_list and partner_list[0] and partner_list[0][1] or False
                result[product.id]['seller_info_id'] = main_supplier and main_supplier.id or False
        return result

    _inherit = "product.template"
    _description = "Product Template"

    _columns = {
        'seller_info_id': fields.function(
            _calc_seller,
            method=True,
            type='many2one',
            relation='product.supplierinfo',
            string='Main Supplier Info',
            help="Main Supplier who has highest priority in Supplier List - Info object.",
            multi="seller_id",
        ),
    }

product_template()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
