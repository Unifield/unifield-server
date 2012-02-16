# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Associated catalogue', ondelete='cascade'),
        'min_qty': fields.float('Minimal Quantity', required=False, help="The minimal quantity to purchase to this supplier, expressed in the supplier Product UoM if not empty, in the default unit of measure of the product otherwise."),
    }
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, menu=False):
        res = super(product_supplierinfo, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, menu)
        print res['arch']
        return res
    
product_supplierinfo()


class pricelist_partnerinfo(osv.osv):
    _name = 'pricelist.partnerinfo'
    _inherit = 'pricelist.partnerinfo'
    
    _columns = {
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'rounding': fields.float(digits=(16,2), string='Rounding', 
                                 help='The ordered quantity must be a multiple of this rounding value.'),
    }
    
pricelist_partnerinfo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: