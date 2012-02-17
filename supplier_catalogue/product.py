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

from tools.translate import _

class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'
    
    def unlink(self, cr, uid, info_id, context={}):
        '''
        Disallow the possibility to remove a supplier info if 
        it's linked to a catalogue
        '''
        info = self.browse(cr, uid, info_id, context=context)
        if info.catalogue_id:
            raise osv.except_osv(_('Error'), _('You cannot remove a supplier information which is linked' \
                                               'to a supplier catalogue line ! Please remove the corresponding' \
                                               'supplier catalogue line to remove this supplier information.'))
        
        return super(product_supplierinfo, self).unlink(cr, uid, info_id, context=context)
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Associated catalogue', ondelete='cascade'),
        'min_qty': fields.float('Minimal Quantity', required=False, help="The minimal quantity to purchase to this supplier, expressed in the supplier Product UoM if not empty, in the default unit of measure of the product otherwise."),
    }
    
product_supplierinfo()


class pricelist_partnerinfo(osv.osv):
    _name = 'pricelist.partnerinfo'
    _inherit = 'pricelist.partnerinfo'
    
    def unlink(self, cr, uid, info_id, context={}):
        '''
        Disallow the possibility to remove a supplier pricelist 
        if it's linked to a catalogue line
        '''
        info = self.browse(cr, uid, info_id, context=context)
        if info.catalogue_id:
            raise osv.except_osv(_('Error'), _('You cannot remove a supplier pricelist line which is linked' \
                                               'to a supplier catalogue line ! Please remove the corresponding' \
                                               'supplier catalogue line to remove this supplier information.'))
        
        return super(pricelist_partnerinfo, self).unlink(cr, uid, info_id, context=context)
    
    _columns = {
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'rounding': fields.float(digits=(16,2), string='Rounding', 
                                 help='The ordered quantity must be a multiple of this rounding value.'),
    }
    
pricelist_partnerinfo()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _get_partner_price(self, cr, uid, product_ids, partner_id, product_qty, currency_id,
                                          order_date, product_uom_id, context={}):
        '''
        Search the good partner price line for products
        '''
        res = {}
        one_product = False
        partner_price = self.pool.get('pricelist.partnerinfo')
        
        if not context:
            context = {}
            
        if isinstance(product_ids, (int, long)):
            one_product = True
            product_ids = [product_ids]
            
        for product_id in product_ids:
            # Search the good line for the price
            res[product_id] = partner_price.search(cr, uid, [('suppinfo_id.partner_id', '=', partner_id),
                                                             ('suppinfo_id.product_id', '=', product_id),
                                                             ('min_quantity', '<=', product_qty),
                                                             ('uom_id', '=', product_uom_id),
                                                             ('currency_id', '=', currency_id),
                                                             ('valid_till', '>', order_date)],
                                                   order='min_quantity desc', limit=1, context=context)[0]
            
        return one_product and res[0] or res
    
product_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: