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


class supplier_catalogue(osv.osv):
    _name = 'supplier.catalogue'
    _description = 'Supplier catalogue'
    
    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'partner_id': fields.many2one('res.partner', string='Partner', required=True,
                                      domain=[('supplier', '=', True)]),
        'period_from': fields.date(string='From', required=True,
                                   help='Starting date of the catalogue.'),
        'period_to': fields.date(string='To', required=True,
                                 help='End date of the catalogue'),
        'currency_id': fields.many2one('res.currency', string='Currency', required=True,
                                       help='Currency used in this catalogue.'),
        'comment': fields.text(string='Comment'),
        'line_ids': fields.one2many('supplier.catalogue.line', 'catalogue_id', string='Lines'),
    }
    
    _defaults = {
        # By default, use the currency of the user
        'currency_id': lambda obj, cr, uid, ctx: obj.pool.get('res.users').browse(cr, uid, uid, context=ctx).company_id.currency_id.id,
    }
    
    def _check_period(self, cr, uid, ids):
        '''
        Check if the To date is older than the From date
        '''
        for catalogue in self.browse(cr, uid, ids):
            if catalogue.period_to < catalogue.period_from:
                return False
        return True
    
    _constraints = [(_check_period, 'The \'To\' date mustn\'t be younger than the \'From\' date !', ['period_from', 'period_to'])]
    
supplier_catalogue()

class supplier_catalogue_line(osv.osv):
    _name = 'supplier.catalogue.line'
    _description = 'Supplier catalogue line'
    _rec_name = 'product_id'
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'min_qty': fields.integer(string='Min. Qty', required=True,
                                  help='Minimal order quantity to get this unit price.'),
        'uom_id': fields.many2one('product.uom', string='Product UoM', required=True,
                                  help='UoM of the product used to get this unit price.'),
        'unit_price': fields.float(digits=(16,2), string='Unit Price', required=True),
        'rounding': fields.integer(string='Rounding', 
                                   help='The ordered quantity must be a multiple of this rounding value.'),
        'comment': fields.char(size=256, string='Comment'),
    }
    
supplier_catalogue_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: