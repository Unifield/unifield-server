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
import decimal_precision as dp
import math
import re
import time


#----------------------------------------------------------
# Assets
#----------------------------------------------------------
class product_asset_type(osv.osv):
    _name = "product.asset.type"
    _description = "Specify the type of asset at product level"

    _columns = {
                'name': fields.char('Name', size=64, required=True),
    }
    
product_asset_type()



class product_asset(osv.osv):
    _name = "product.asset"
    _description = "A specific asset of a product"
    
    
    def view_init(self, cr , uid , fields_list, context=None):
        #print 'product asset'
        pass
    
    
    def _getRelatedProductFields(self, cr, uid, productId):
        '''
        get related fields from product
        '''
        result = {}
        # if no product, return empty dic
        if not productId:
            return result
        
        # fetch the product
        product = self.pool.get('product.product').browse(cr, uid, productId)
        
        result.update({
                       'asset_type_id': product.asset_type_id.id,
                       'prod_int_code': product.default_code,
                       'prod_int_name': product.name,
                     })
        
        return result
        
    
    
    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to force readonly fields to be saved to db
        on data update
        '''
        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, user, productId))
        
        # save the data to db
        return super(product_asset, self).write(cr, user, ids, vals, context)
    
    
    def create(self, cr, user, vals, context=None):
        '''
        override create method to force readonly fields to be saved to db
        on data creation
        '''
        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, user, productId))
        
        # save the data to db
        return super(product_asset, self).create(cr, user, vals, context)
        
        
    
    def _compute_product(self, cr, uid, ids, context=None):
        '''
        origininally used for fields.function test
        
        not used presently
        '''
        assets = self.browse(cr, uid, ids)
        
        result = {}
        
        for asset in assets:
            pass
            
            
            
    def onChangeProductId(self, cr, uid, ids, productId):
        '''
        
        '''
        result = {}
        
        # no product selected
        if not productId:
            return result
        
        result.update({'value': self._getRelatedProductFields(cr, uid, productId)
                       })
        
        return result
            
    
    _columns = {
                'product_id': fields.many2one('product.product', 'Product', domain="[('subtype','=','asset')]", required=True, ondelete='cascade'),
                'event_ids': fields.one2many('product.asset.event', 'asset_id', 'Events'),
                'asset_code': fields.char('Asset Code', size=64, required=True),
                'name': fields.char('Asset Name', size=128),
                'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', readonly=True), # from product
                # HQ reference
                'hq_local_ref': fields.char('Local Reference', size=128),
                'hq_asset_name': fields.char('Asset Name', size=128),
                'hq_serial_nb': fields.char('Serial Number', size=128, required=True),
                'hq_brand': fields.char('Brand', size=128, required=True),
                'hq_type': fields.char('Type', size=128, required=True),
                'hq_model': fields.char('Model', size=128, required=True),
                # MSF codification
                # TODO or fields.reference or fields.related ?
                #'codif_prod_int_code': fields.function(_compute_product, arg={'test':'test', 'field':product_id}, method=True, string='Product Internal Code',
                #                                       store={'product.product': (lambda self, cr, uid, ids, c={}: '', ['code'], 10),},
                #                                       multi='product'),
                'prod_int_code': fields.char('Product Internal Code', size=128, readonly=True), # from product
                'prod_int_name': fields.char('Product Internal Name', size=128, readonly=True), # from product
                'prod_nomenc_code': fields.char('Product Nomenclature Code', size=128),
                # traceability
                'trac_orig_req_ref': fields.char('Original Requested Reference (Project PO)', size=128),
                'trac_orig_mission_code': fields.char('Original Mission Code', size=128, required=True),
                'trac_sourc_ref': fields.char('Sourcing Reference', size=128, required=True),
                'trac_arriv_date': fields.date('Arrival Date', required=True),
                'trac_receipt_place': fields.char('Receipt Place', size=128, required=True),
                # Invoice
                'invo_num': fields.char('Invoice Number', size=128, required=True),
                'invo_date': fields.date('Invoice Date', required=True),
                'invo_val_curr': fields.char('Value and Corresponding Currency', size=128, required=True),
                'invo_supplier': fields.char('Supplier', size=128),
                'invo_donator_code': fields.char('Donator Code', size=128),
    }
    
    _defaults = {
        'trac_arriv_date': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
product_asset()

    
class product_asset_event(osv.osv):
    _name = "product.asset.event"
    _description = "Event for asset follow up"
    
    stateSelection = [
        ('inUse', 'In Use'),
        ('stock', 'Stock'),
        ('repair', 'Repair'),
    ]
    
    eventTypeSelection = [
        ('reception', 'Reception'),
        ('startUse', 'Start Use'),
        ('repairing', 'Repairing'),
        ('endUse', 'End Use'),
        ('obsolete', 'Obsolete'),
        ('loaning', 'Loaning'),
        ('transfer', 'Transfer (internal)'),
        ('donation', 'Donation (external)'),
        ('other', 'Other'),
    ]
    
    def _getRelatedAssetFields(self, cr, uid, assetId):
        '''
        get related fields from product
        '''
        result = {}
        # if no asset, return empty dic
        if not assetId:
            return result
        
        # newly selected asset object        
        asset = self.pool.get('product.asset').browse(cr, uid, assetId)
        
        result.update({
                       'asset_code': asset.asset_code,
                       'asset_type_id': asset.asset_type_id.id,
                       'prod_int_code': asset.prod_int_code,
                       'prod_int_name': asset.prod_int_name,
                       'hq_brand': asset.hq_brand,
                       'hq_model': asset.hq_model,
                    })
        
        return result
    
    
    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to force readonly fields to be saved to db
        on data update
        '''
        # fetch the asset
        assetId = vals['asset_id']
        # add readonly fields to vals
        vals.update(self._getRelatedAssetFields(cr, user, assetId))
        
        # save the data to db
        return super(product_asset_event, self).write(cr, user, ids, vals, context)
    
    
    def create(self, cr, user, vals, context=None):
        '''
        override create method to force readonly fields to be saved to db
        on data creation
        '''
        # fetch the asset
        assetId = vals['asset_id']
        # add readonly fields to vals
        vals.update(self._getRelatedAssetFields(cr, user, assetId))
        
        # save the data to db
        return super(product_asset_event, self).create(cr, user, vals, context)
    
    
    def onChangeAssetId(self, cr, uid, ids, assetId):
        
        result = {}
        
        # no asset selected
        if not assetId:
            return result
        
        result.update({'value': self._getRelatedAssetFields(cr, uid, assetId)})
        
        return result
        
    
    _columns = {
                'asset_id': fields.many2one('product.asset', 'Asset', required=True, ondelete='cascade'),
                'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', readonly=True), # from asset
                'date': fields.date('Date', required=True),
                'name': fields.char('Event Name', size=128),
                'asset_code': fields.char('Asset Code', size=128, readonly=True), # from asset
                'prod_int_code': fields.char('Product Internal Code', size=128, readonly=True), # from asset
                'prod_int_name': fields.char('Product Internal Name', size=128, readonly=True), # from asset
                'hq_brand': fields.char('Brand', size=128, readonly=True), # from asset
                'hq_model': fields.char('Model', size=128, readonly=True), # from asset
                'location': fields.char('Location', size=128),
                'proj_code': fields.char('Project Code', size=128),
                'event_type': fields.selection(eventTypeSelection, 'Event Type', required=True), # TODO many2one or selection ?
                'remark': fields.char('Remark', size=128),
                'state': fields.selection(stateSelection, 'Current Status', required=True), # TODO many2one or selection ?
    }
    
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'event_type': lambda *a: 'reception',
        'state': lambda *a: 'inUse',
    }
    
product_asset_event()


#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):
    
    _inherit = "product.template"
    _description = "Product Template"
    
    _columns = {
        'subtype': fields.selection([('single','Single Item'),('kit', 'Kit'),('asset','Asset')], 'Product SubType', required=True, help="Will change the way procurements are processed."),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type'),
    }

    _defaults = {
        'subtype': lambda *a: 'single',
    }

product_template()

class product_product(osv.osv):
    
    _inherit = "product.product"
    _description = "Product"
    
    _columns = {
        'asset_ids': fields.one2many('product.asset', 'product_id', 'Assets')
    }

    _defaults = {
    }

product_product()


#----------------------------------------------------------
# Stock moves
#----------------------------------------------------------
class stock_move(osv.osv):

    _inherit = "stock.move"
    _description = "Stock Move"
    
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, address_id=False):
        '''
        override to clear asset_id
        '''
        result = super(stock_move, self).onchange_product_id(cr, uid, ids, prod_id, loc_id,
                            loc_dest_id, address_id)
        
        if 'value' not in result:
            result['value'] = {}
            
        result['value'].update({'asset_id': False})
        
        return result
    
    
    _columns = {
        'asset_id': fields.many2one('product.asset', 'Asset')
    }
    
    
stock_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
