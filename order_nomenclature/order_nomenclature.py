# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
       - nomenclature_id : contains the nomenclature id
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
        
        # comment is cleared
        result['value'].update({'comment':False})
        
        # change nomenclature_description to correspond to the product
        # for now simply clear nomenclature if a product has been selected
        if product:
            result['value'].update({'nomenclature_description':False})
            # product has been selected, nomenclatures are readonly and empty
            self.pool.get('product.product')._resetNomenclatureFields(result['value'])
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            # name is the name of the product
            result['value'].update({'name':productObj.name})
            result['value'].update({'default_code':productObj.default_code})
            result['value'].update({'default_name':productObj.name})
        else:
            result['value'].update({'default_code':False})
            result['value'].update({'default_name':False})
        
        return result
    
    def product_uom_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        override product_uom_change to avoid the reset of Comment when the UOM is changed
        '''
        # call to super
        result = super(purchase_order_line, self).product_uom_change(cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order, fiscal_position, date_planned,
            name, price_unit, notes)
        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']
            
        return result
    
    def product_qty_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False, state=False, old_unit_price=False, fake_id=False, context=None):
        '''
        interface product_id_change to avoid the reset of Comment field when the qty is changed
        '''
        result = self.product_id_on_change(cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order, fiscal_position, date_planned,
            name, price_unit, notes, state, old_unit_price, fake_id, context=context)
        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']
        
        return result
    
    def _relatedFields(self, cr, uid, vals, context=None):
        '''
        related fields for create and write
        '''
        # recreate description because in readonly
        if ('product_id' in vals) and (vals['product_id']):
            # no nomenclature description
            vals.update({'nomenclature_description':False})
            # update the name (comment) of order line
            # the 'name' is no more the get_name from product, but instead
            # the name of product
            productObj = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
            vals.update({'name':productObj.name})
            vals.update({'default_code':productObj.default_code})
            vals.update({'default_name':productObj.name})
            # erase the nomenclature - readonly
            self.pool.get('product.product')._resetNomenclatureFields(vals)
        elif ('product_id' in vals) and (not vals['product_id']):
            sale = self.pool.get('sale.order.line')
            sale._setNomenclatureInfo(cr, uid, vals, context)
            # erase default code
            vals.update({'default_code':False})
            vals.update({'default_name':False})
            
            if 'comment' in vals:
                vals.update({'name':vals['comment']})
        # clear nomenclature filter values
        #self.pool.get('product.product')._resetNomenclatureFields(vals)
    
    def create(self, cr, uid, vals, context=None):
        '''
        override create. don't save filtering data
        '''
        self._relatedFields(cr, uid, vals, context)
        
        return super(purchase_order_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write. don't save filtering data
        '''
        self._relatedFields(cr, uid, vals, context)
            
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
        'nomenclature_code': fields.char('Nomenclature code', size=1024),
        'comment': fields.char('Comment', size=1024),
        'default_code': fields.char('Product Reference', size=1024),
        'default_name': fields.char('Product Name', size=1024),
        'name': fields.char('Comment', size=1024, required=True),
        
        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),

        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),

        # concatenation of nomenclature in a visible way
        'nomenclature_description': fields.char('Nomenclature', size=1024),
    }
    ### END OF COPY
    
    _defaults = {
    }
    
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)

    def get_sub_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_sub_nomen(cr, uid, self, id, field)

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('sale.order.line').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)

    def onChangeSubNom(self, cr, uid, id, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, nomen_sub_0, nomen_sub_1, nomen_sub_2, nomen_sub_3, nomen_sub_4, nomen_sub_5, context=None):
        return self.pool.get('sale.order.line').onChangeSubNom(cr, uid, id, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, nomen_sub_0, nomen_sub_1, nomen_sub_2, nomen_sub_3, nomen_sub_4, nomen_sub_5, context)
purchase_order_line()

#
# SO
#
class sale_order_line(osv.osv):
    '''
    1. add new fields :
       - nomenclature_id : contains the nomenclature id
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
        
        # comment is cleared
        result['value'].update({'comment':False})
        
        # change nomenclature_description to correspond to the product
        # for now simply clear nomenclature if a product has been selected
        if product:
            result['value'].update({'nomenclature_description':False})
            # product has been selected, nomenclatures are readonly and empty
            self.pool.get('product.product')._resetNomenclatureFields(result['value'])
            productObj = self.pool.get('product.product').browse(cr, uid, product)
            # name is the name of the product
            result['value'].update({'name':productObj.name})
            result['value'].update({'default_code':productObj.default_code})
            result['value'].update({'default_name':productObj.name})
        else:
            result['value'].update({'default_code':False})
            result['value'].update({'default_name':False})
        
        return result
    
    def product_uom_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False):
        '''
        override product_uom_change to avoid the reset of Comment when the UOM is changed
        '''
        # call to super
        result = super(sale_order_line, self).product_uom_change(cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id, lang, update_tax, date_order)
        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']
            
        return result
    
    def product_qty_change(self, cr, uid, ids, pricelist, product, qty=0,
        uom=False, qty_uos=0, uos=False, name='', partner_id=False,
        lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        interface product_id_change to avoid the reset of Comment field when the qty is changed 
        '''
        result = self.product_id_change(cr, uid, ids, pricelist, product, qty,
                                        uom, qty_uos, uos, name, partner_id,
                                        lang, update_tax, date_order, packaging, fiscal_position, flag)
        # drop modification to name attribute
        if 'name' in result['value']:
            del result['value']['name']
        # drop modification to comment attribute
        if 'comment' in result['value']:
            del result['value']['comment']
            
        return result
    
    def product_packaging_change(self, cr, uid, ids, pricelist, product, qty=0,
        uom=False, qty_uos=0, uos=False, name='', partner_id=False,
        lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        interface product_id_change to avoid the reset of Comment field when the qty is changed 
        '''
        result = self.product_qty_change(cr, uid, ids, pricelist, product, qty,
                                        uom, qty_uos, uos, name, partner_id,
                                        lang, update_tax, date_order, packaging, fiscal_position, flag)
        
        return result
    
    def _relatedFields(self, cr, uid, vals, context=None):
        '''
        related fields for create and write
        '''
        # recreate description because in readonly
        if ('product_id' in vals) and (vals['product_id']):
            # no nomenclature description
            vals.update({'nomenclature_description':False})
            # update the name (comment) of order line
            # the 'name' is no more the get_name from product, but instead
            # the name of product
            productObj = self.pool.get('product.product').browse(cr, uid, vals['product_id'])
            vals.update({'name':productObj.name})
            vals.update({'default_code':productObj.default_code})
            vals.update({'default_name':productObj.name})
            # erase the nomenclature - readonly
            self.pool.get('product.product')._resetNomenclatureFields(vals)
        elif ('product_id' in vals) and (not vals['product_id']):
            self._setNomenclatureInfo(cr, uid, vals, context)
            # erase default code
            vals.update({'default_code':False})
            vals.update({'default_name':False})
                        
            if 'comment' in vals:
                vals.update({'name':vals['comment']})
        # clear nomenclature filter values
        #self.pool.get('product.product')._resetNomenclatureFields(vals)
        
    def create(self, cr, uid, vals, context=None):
        '''
        override create. don't save filtering data
        '''
        self._relatedFields(cr, uid, vals, context)
        
        return super(sale_order_line, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        override write. don't save filtering data
        '''
        self._relatedFields(cr, uid, vals, context)
            
        return super(sale_order_line, self).write(cr, uid, ids, vals, context=context)
    
    def _setNomenclatureInfo(self, cr, uid, values, context=None):
        '''
        set nomenclature_description
        '''
        if not values:
            return {}
        
        constants = self.pool.get('product.nomenclature')._returnConstants()
        
        # the last selected level
        mandaDesc = ''
        levels = constants['levels']
        ids = filter(lambda x: ('nomen_manda_%i'%x in values) and (values['nomen_manda_%i'%x]), range(levels))
        if len(ids) > 0:
            id = values['nomen_manda_%i'%max(ids)]
            mandaDesc = self.pool.get('product.nomenclature').name_get(cr, uid, [id], context)[0][1]
            
        description = [mandaDesc]
        
        # add optional names
        sublevels = constants['sublevels']
        ids = filter(lambda x: ('nomen_sub_%i'%x in values) and (values['nomen_sub_%i'%x]), range(sublevels))
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
        #self._productDomain(cr, uid, id, context)
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
        #self._productDomain(cr, uid, id, context)
        self._setNomenclatureInfo(cr, uid, context['result']['value'], context)
        
        result = context['result']
        return result
        
    # PO/SO - IDENTICAL
    _columns = {
        'nomenclature_code': fields.char('Nomenclature code', size=1024),
        'comment': fields.char('Comment', size=1024),
        'default_code': fields.char('Product Reference', size=1024),
        'default_name': fields.char('Product Name', size=1024),
        'name': fields.char('Comment', size=1024, required=True, select=True, readonly=True, states={'draft': [('readonly', False)]}),
        
        ### EXACT COPY-PASTE FROM product_nomenclature -> product_template
        # mandatory nomenclature levels -> not mandatory on screen here
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),

        # optional nomenclature levels
        'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
        'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
        'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
        'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
        'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
        'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),

        # concatenation of nomenclature in a visible way
        'nomenclature_description': fields.char('Nomenclature', size=1024),
    }
    ### END OF COPY
    
    _defaults = {
    }
    
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line'
    
    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field)

    def get_sub_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_sub_nomen(cr, uid, self, id, field)

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=False, context=None):
        ret = self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)
        newval = {}
        for i in range(0, 4):
            if 'nomen_manda_%s'%i not in ret.get('value',{}):
                newval['nomen_manda_%s'%i] = eval('nomen_manda_%s'%i)
        self._setNomenclatureInfo(cr, uid, newval)
        if 'value' not in ret:
            ret['value'] = {}
        ret['value']['nomenclature_description'] = newval.get('nomenclature_description')
        return ret

    def onChangeSubNom(self, cr, uid, id, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, nomen_sub_0, nomen_sub_1, nomen_sub_2, nomen_sub_3, nomen_sub_4, nomen_sub_5, context=None):
        newval = {}
        for i in range(0, 6):
            if i < 4:
                newval['nomen_manda_%s'%i] = eval('nomen_manda_%s'%i)
            newval['nomen_sub_%s'%i] = eval('nomen_sub_%s'%i)
        self._setNomenclatureInfo(cr, uid, newval)
        ret = {'value': {}}
        ret['value']['nomenclature_description'] = newval.get('nomenclature_description')
        return ret


    
sale_order_line()
