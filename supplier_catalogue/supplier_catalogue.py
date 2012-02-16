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

from mx.DateTime import DateFrom, now
from datetime import date

class supplier_catalogue(osv.osv):
    _name = 'supplier.catalogue'
    _description = 'Supplier catalogue'        
    
    def _get_active(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Return True if today is into the period of the catalogue
        '''
        res = {}
        
        for catalogue in self.browse(cr, uid, ids, context=context):
            date_from = DateFrom(catalogue.period_from)
            date_to = DateFrom(catalogue.period_to)
            res[catalogue.id] = date_from < now() < date_to 
        
        return res
    
    def _search_active(self, cr, uid, obj, name, args, context={}):
        '''
        Returns all active catalogue
        '''
        ids = []
        
        for arg in args:
            if arg[0] == 'current' and arg[1] == '=':
                ids = self.search(cr, uid, [('period_from', '<', date.today()), 
                                            ('period_to', '>', date.today())], context=context)
                return [('id', 'in', ids)]
            elif arg[0] == 'current' and arg[1] == '!=':
                ids = self.search(cr, uid, ['|', ('period_from', '>', date.today()), 
                                                 ('period_to', '<', date.today())], context=context)
                return [('id', 'in', ids)]
        
        return ids
    
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
        'current': fields.function(_get_active, fnct_search=_search_active, method=True, string='Active', type='boolean', store=False, 
                                   readonly=True, help='Indicate if the catalogue is currently active.'),
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
    
    def create(self, cr, uid, vals, context={}):
        '''
        Create a pricelist line on product supplier information tab
        '''
        return super(supplier_catalogue_line, self).create(cr, uid, vals, context={})
    
    def write(self, cr, uid, ids, vals, context={}):
        '''
        Update the pricelist line on product supplier information tab
        '''
        return super(supplier_catalogue_line, self).write(cr, uid, ids, vals, context={})
    
    def unlink(self, cr, uid, id, context={}):
        '''
        Remove the pricelist line on product supplier information tab
        If the product supplier information has no line, remove it
        '''
        return super(supplier_catalogue_line, self).unlink(cr, uid, id, context=context)
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'min_qty': fields.float(digits=(16,2), string='Min. Qty', required=True,
                                  help='Minimal order quantity to get this unit price.'),
        'uom_id': fields.many2one('product.uom', string='Product UoM', required=True,
                                  help='UoM of the product used to get this unit price.'),
        'unit_price': fields.float(digits=(16,2), string='Unit Price', required=True),
        'rounding': fields.float(digits=(16,2), string='Rounding', 
                                   help='The ordered quantity must be a multiple of this rounding value.'),
        'comment': fields.char(size=64, string='Comment'),
        'supplier_info_id': fields.many2one('product.supplierinfo', string='Linked Supplier Info'),
        'partner_info_id': fields.many2one('pricelist.partnerinfo', string='Linked Supplier Info line'),
    }
    
    def product_change(self, cr, uid, ids, product_id, context={}):
        '''
        When the product change, fill automatically the uom_id field of the
        catalogue line.
        @param product_id: ID of the selected product or False
        '''
        v = {'uom_id': False}
        
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v.update({'uom_id': product.uom_id.id})
        
        return {'value': v}
    
supplier_catalogue_line()


class product_supplierinfo(osv.osv):
    _name = 'product.supplierinfo'
    _inherit = 'product.supplierinfo'
    
    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Associated catalogue', ondelete='cascade'),
    }
    
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