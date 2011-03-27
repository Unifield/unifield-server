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

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from osv import osv, fields
import netsvc
import pooler
from tools.translate import _
import decimal_precision as dp
from osv.orm import browse_record, browse_null

import product_nomenclature as pn

#
# PO
#
class purchase_order_line(osv.osv):
    '''
    1. add new fields :
       - nomenclature_code : contains the corresponding code
       - nomenclature_description : contains the corresponding description
    '''
    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        overriden on_change function
        '''
        result = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order, fiscal_position, date_planned,
            name, price_unit, notes)
        
        
        # change nomenclature_description to correspond to the product
        # for now simply clear nomenclature if a product has been selected
        if product:
            result['value'].update({'nomenclature_description':False})
        
        return result
    
    
    def create(self, cr, uid, vals, context=None):
        '''
        override create. don't save filtering data
        '''
        # recreate description because in readonly
        if vals['product_id']:
            vals.update({'nomenclature_description':False})
        else:
            sale = self.pool.get('sale.order.line')
            sale._setNomenclatureInfo(cr, uid, vals, context)
        
        # clear nomenclature filter values
        self.pool.get('product.product')._resetNomenclatureFields(vals)
        
        return super(purchase_order_line, self).create(cr, uid, vals, context=context)
    
    
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write. don't save filtering data
        '''
        # recreate description because in readonly
        if vals['product_id']:
            vals.update({'nomenclature_description':False})
        else:
            sale = self.pool.get('sale.order.line')
            sale._setNomenclatureInfo(cr, uid, vals, context)
            
        # clear nomenclature filter values
        self.pool.get('product.product')._resetNomenclatureFields(vals)
            
        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)
    
    
    def nomenChange(self, cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                    nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        direct call to sale processes
        '''
        sale = self.pool.get('sale.order.line')
        return sale.nomenChange(cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                                nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
    
    
    def codeChange(self, cr, uid, id, fieldNumber, code, nomenclatureType,
                   nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        direct call to sale processes
        '''
        sale = self.pool.get('sale.order.line')
        return sale.codeChange(cr, uid, id, fieldNumber, code, nomenclatureType,
                   nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
    
    
    # PO/SO - IDENTICAL
    _columns = {
        'nomenclature_code': fields.char('Nomenclature code', size=128),
        'nomenclature_description': fields.char('Nomenclature', size=128),
        
        
        
        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Leaf'),
        # codes
        'nomen_c_manda_0': fields.char('C1', size=32),
        'nomen_c_manda_1': fields.char('C2', size=32),
        'nomen_c_manda_2': fields.char('C3', size=32),
        'nomen_c_manda_3': fields.char('C4', size=32),
        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),
        # codes
        'nomen_c_sub_0': fields.char('C5', size=128),
        'nomen_c_sub_1': fields.char('C6', size=128),
        'nomen_c_sub_2': fields.char('C7', size=128),
        'nomen_c_sub_3': fields.char('C8', size=128),
        'nomen_c_sub_4': fields.char('C9', size=128),
        'nomen_c_sub_5': fields.char('C10', size=128),
    }
    ### END OF COPY
    
    _defaults = {
    }
    
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'


purchase_order_line()

#
# SO
#
class sale_order_line(osv.osv):
    '''
    1. add new fields :
       - nomenclature_code : contains the corresponding code
       - nomenclature_description : contains the corresponding description
    ''' 
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        overriden on_change function
        '''
        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id,
            lang, update_tax, date_order, packaging, fiscal_position, flag)
        
        # change nomenclature_description to correspond to the product
        # for now simply clear nomenclature if a product has been selected
        if product:
            result['value'].update({'nomenclature_description':False})
        
        return result
        
    
    def create(self, cr, uid, vals, context=None):
        '''
        override create. don't save filtering data
        '''
        # recreate description because in readonly
        if vals['product_id']:
            vals.update({'nomenclature_description':False})
        else:
            self._setNomenclatureInfo(cr, uid, vals, context)
        
        # clear nomenclature filter values
        self.pool.get('product.product')._resetNomenclatureFields(vals)
        
        return super(sale_order_line, self).create(cr, uid, vals, context=context)
    
    
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write. don't save filtering data
        '''
        # recreate description because in readonly
        if vals['product_id']:
            vals.update({'nomenclature_description':False})
        else:
            self._setNomenclatureInfo(cr, uid, vals, context)
            
        # clear nomenclature filter values
        self.pool.get('product.product')._resetNomenclatureFields(vals)
            
        return super(sale_order_line, self).write(cr, uid, ids, vals, context=context)
    
    
    
    def _setNomenclatureInfo(self, cr, uid, values, context=None):
        '''
        set nomenclature_description
        '''
        assert values, 'No values, error on function call'
        
        constants = self.pool.get('product.nomenclature')._returnConstants()
        
        # the last selected level
        mandaDesc = ''
        levels = constants['levels']
        ids = filter(lambda x: values['nomen_manda_%i'%x], range(levels))
        if len(ids) > 0:
            id = values['nomen_manda_%i'%max(ids)]
            mandaDesc = self.pool.get('product.nomenclature').name_get(cr, uid, [id], context)[0][1]
            
        description = [mandaDesc]
        
        # add optional names
        sublevels = constants['sublevels']
        ids = filter(lambda x: values['nomen_sub_%i'%x], range(sublevels))
        ids = map(lambda x: values['nomen_sub_%i'%x], ids)
        subNomenclatures = self.pool.get('product.nomenclature').browse(cr, uid, ids, context)
        
        for n in subNomenclatures:
            description.append(n.name)

        values.update({'nomenclature_description': ':'.join(description)})
    
    
    def _productDomain(self, cr, uid, id, context=None):
        '''
        product the dynamic product's domain
        '''
        # all values are updated from 'result' in context
        # loop through these values
        # if the value is not False, create a new domain rule
        assert context, 'No context, error on function call'
        
        # check and create domain dictionary
        if 'domain' in context['result']:
            domain = context['result']['domain']
        else:
            domain = {}
            context['result']['domain'] = domain
        
        # empty product domain list
        productList = []    
        domain.update({'product_id': productList})
        
        
        values = context['result']['value']
        for k,v in values.items():
            if v:
                newRule = (k, '=', v)
                productList.append(newRule)
    
    
    
    def nomenChange(self, cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                    nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        first call the standard product_nomenclature process
        secondly complete dynamic domain
        '''
        assert context, 'No context, error on function call'
        
        product = self.pool.get('product.product')
        product.nomenChange(cr, uid, id, fieldNumber, nomenclatureId, nomenclatureType,
                            nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
        self._productDomain(cr, uid, id, context)
        self._setNomenclatureInfo(cr, uid, context['result']['value'], context)
        
        result = context['result']
        return result
        
    
    
    def codeChange(self, cr, uid, id, fieldNumber, code, nomenclatureType,
                   nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None, *optionalList):
        '''
        first call the standard product_nomenclature process
        secondly complete dynamic domain
        '''
        assert context, 'No context, error on function call'
        
        
        product = self.pool.get('product.product')
        product.codeChange(cr, uid, id, fieldNumber, code, nomenclatureType,
                           nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context, *optionalList)
        self._productDomain(cr, uid, id, context)
        self._setNomenclatureInfo(cr, uid, context['result']['value'], context)
        
        result = context['result']
        return result
        
         
    # PO/SO - IDENTICAL
    _columns = {
        'nomenclature_code': fields.char('Nomenclature code', size=128),
        'nomenclature_description': fields.char('Nomenclature', size=128),
        
        
        
        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Leaf'),
        # codes
        'nomen_c_manda_0': fields.char('C1', size=32),
        'nomen_c_manda_1': fields.char('C2', size=32),
        'nomen_c_manda_2': fields.char('C3', size=32),
        'nomen_c_manda_3': fields.char('C4', size=32),
        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),
        # codes
        'nomen_c_sub_0': fields.char('C5', size=128),
        'nomen_c_sub_1': fields.char('C6', size=128),
        'nomen_c_sub_2': fields.char('C7', size=128),
        'nomen_c_sub_3': fields.char('C8', size=128),
        'nomen_c_sub_4': fields.char('C9', size=128),
        'nomen_c_sub_5': fields.char('C10', size=128),
    }
    ### END OF COPY
    
    _defaults = {
    }
    
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line'
    

sale_order_line()


