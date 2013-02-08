# -*- coding: utf-8 -*-
##############################################################################
#
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

import tools
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time
import logging

from mx import DateTime

# warning messages
SHORT_SHELF_LIFE_MESS = 'Product with Short Shelf Life, check the accuracy of the order quantity, frequency and mode of transport.'


class sale_order_line(osv.osv):
    '''
    override to add message at sale order creation and update
    '''
    _inherit = 'sale.order.line'
    
    def _kc_dg(self, cr, uid, ids, name, arg, context=None):
        '''
        return 'KC' if cold chain or 'DG' if dangerous goods
        '''
        result = {}
        for id in ids:
            result[id] = ''
            
        for sol in self.browse(cr, uid, ids, context=context):
            if sol.product_id:
                if sol.product_id.heat_sensitive_item:
                    result[sol.id] = 'KC'
                elif sol.product_id.dangerous_goods:
                    result[sol.id] = 'DG'
        
        return result
        
    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='KC/DG', type='char'),}
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        '''
        if the product is short shelf life we display a warning
        '''
        # call to super
        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id, lang, update_tax, date_order, packaging, fiscal_position, flag)
        
        # if the product is short shelf life, display a warning
        if product:
            prod_obj = self.pool.get('product.product')
            if prod_obj.browse(cr, uid, product).short_shelf_life:
                warning = {
                            'title': 'Short Shelf Life product',
                            'message': _(SHORT_SHELF_LIFE_MESS)
                            }
                result.update(warning=warning)
            
        return result
    
sale_order_line()


class sale_order(osv.osv):
    '''
    add message when so is written, i.e when we add new so lines
    '''
    _inherit = 'sale.order'
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        display message if contains short shelf life
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.order_line:
                # log the message
                if line.product_id.short_shelf_life:
                    # log the message
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
        
        return super(sale_order, self).write(cr, uid, ids, vals, context=context)
    
sale_order()


class purchase_order_line(osv.osv):
    '''
    override to add message at purchase order creation and update
    '''
    _inherit = 'purchase.order.line'
    
    def _kc_dg(self, cr, uid, ids, name, arg, context=None):
        '''
        return 'KC' if cold chain or 'DG' if dangerous goods
        '''
        result = {}
        for id in ids:
            result[id] = ''
            
        for pol in self.browse(cr, uid, ids, context=context):
            if pol.product_id:
                if pol.product_id.heat_sensitive_item:
                    result[pol.id] = 'KC'
                elif pol.product_id.dangerous_goods:
                    result[pol.id] = 'DG'
        
        return result
        
    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='KC/DG', type='char'),}
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        '''
        if the product is short shelf life we display a warning
        '''
        # call to super
        result = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order, fiscal_position, date_planned,
            name, price_unit, notes)
        
        # if the product is short shelf life, display a warning
        if product:
            prod_obj = self.pool.get('product.product')
            if prod_obj.browse(cr, uid, product).short_shelf_life:
                warning = {
                            'title': 'Short Shelf Life product',
                            'message': _(SHORT_SHELF_LIFE_MESS)
                            }
                result.update(warning=warning)
            
        return result
    
purchase_order_line()


class purchase_order(osv.osv):
    '''
    add message when po is written, i.e when we add new po lines
    
    no need to modify the wkf_confirm_order as the wrtie method is called during the workflow
    '''
    _inherit = 'purchase.order'
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        display message if contains short shelf life
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.order_line:
                # log the message
                if line.product_id.short_shelf_life:
                    # log the message
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
        
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)
    
purchase_order()


class stock_warehouse_orderpoint(osv.osv):
    '''
    add message
    '''
    _inherit = 'stock.warehouse.orderpoint'

    _columns = {
         'name': fields.char('Reference', size=128, required=True, select=True),
         'location_id': fields.many2one('stock.location', 'Location', required=True, ondelete="cascade", 
                                        domain="[('is_replenishment', '=', warehouse_id)]"),
    }
    
    def _check_product_uom(self, cr, uid, ids, context=None):
        '''
        Check if the UoM has the same category as the product standard UoM
        '''
        if not context:
            context = {}
            
        for rule in self.browse(cr, uid, ids, context=context):
            if rule.product_id.uom_id.category_id.id != rule.product_uom.category_id.id:
                return False
            
        return True
    
    _constraints = [
        (_check_product_uom, 'You have to select a product UOM in the same category than the purchase UOM of the product', ['product_id', 'product_uom']),
    ]
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the default values for the replenishment rule
        '''
        res = super(stock_warehouse_orderpoint, self).default_get(cr, uid, fields, context=context)
        
        company_id = res.get('company_id')
        warehouse_id = res.get('warehouse_id')
        
        if not 'company_id' in res:
            company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.automatic.supply', context=context)
            res.update({'company_id': company_id})
        
        if not 'warehouse_id' in res:
            warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', company_id)], context=context)[0]
            res.update({'warehouse_id': warehouse_id})
            
        if not 'location_id' in res:
            location_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_stock_id.id
            res.update({'location_id': location_id})
        
        return res
    
    def create(self, cr, uid, vals, context=None):
        '''
        add message
        '''
        new_id = super(stock_warehouse_orderpoint, self).create(cr, uid, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                self.log(cr, uid, new_id, _(SHORT_SHELF_LIFE_MESS))
                
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        add message
        '''
        result = super(stock_warehouse_orderpoint, self).write(cr, uid, ids, vals, context=context)
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
        
        return result
    
    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        '''
        Add domain on UoM to have only UoM on the same category of the
        product standard UoM
        '''
        product_obj = self.pool.get('product.product')
        
        res = super(stock_warehouse_orderpoint, self).onchange_product_id(cr, uid, ids, product_id, context=context)
        domain = {}

        # Get the product UoM category
        if product_id:        
            product = product_obj.browse(cr, uid, product_id, context=context)
            domain = {'product_uom': [('category_id', '=', product.uom_id.category_id.id)]}
        else:
            domain = {'product_uom': []}
            if 'value' in res:
                res['value'].update({'product_uom': False})
            else:
                res.update({'value': {'product_uom': False}})
                
        # Apply the domain in res
        if 'domain' in res:
            res['domain'].update(domain)
        else:
            res.update({'domain': domain})
            
        return res
    
    def onchange_uom(self, cr, uid, ids, product_id, uom_id, context=None):
        '''
        Check if the UoM is convertible to product standard UoM
        '''
        if uom_id and product_id:
            product_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
        
            product = product_obj.browse(cr, uid, product_id, context=context)
            uom = uom_obj.browse(cr, uid, uom_id, context=context)
        
            if product.uom_id.category_id.id != uom.category_id.id:
                raise osv.except_osv(_('Wrong Product UOM !'), _('You have to select a product UOM in the same category than the purchase UOM of the product'))
        
        return {}
        
        
stock_warehouse_orderpoint()


class product_uom(osv.osv):
    _name = 'product.uom'
    _inherit = 'product.uom'
    
    def _get_uom_by_product(self, cr, uid, ids, field_name, args, context=None):
        return {}
    
    def _search_uom_by_product(self, cr, uid, obj, name, args, context=None):
        dom = []
        
        for arg in args:
            if arg[0] == 'uom_by_product' and arg[1] != '=':
                raise osv.except_osv(_('Error'), _('Bad comparison operator in domain'))
            elif arg[0] == 'uom_by_product':
                product_id = arg[2]
                if product_id:
                    if isinstance(product_id, (int, long)):
                        product_id = [product_id]
                    product = self.pool.get('product.product').browse(cr, uid, product_id[0], context=context)
                    dom.append(('category_id', '=', product.uom_id.category_id.id))
                
        return dom

    _columns = {
        'uom_by_product': fields.function(_get_uom_by_product, fnct_search=_search_uom_by_product, string='UoM by Product', 
                                          help='Field used to filter the UoM for a specific product'),
    }
    
product_uom()


class stock_warehouse_automatic_supply(osv.osv):
    '''
    add message
    '''
    _inherit = 'stock.warehouse.automatic.supply'
    
    def create(self, cr, uid, vals, context=None):
        '''
        add message
        '''
        new_id = super(stock_warehouse_automatic_supply, self).create(cr, uid, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                self.log(cr, uid, new_id, _(SHORT_SHELF_LIFE_MESS))
                
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        add message
        '''
        result = super(stock_warehouse_automatic_supply, self).write(cr, uid, ids, vals, context=context)
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
        
        return result
    
stock_warehouse_automatic_supply()


class stock_warehouse_order_cycle(osv.osv):
    '''
    add message
    '''
    _inherit = 'stock.warehouse.order.cycle'
    
    def create(self, cr, uid, vals, context=None):
        '''
        add message
        '''
        new_id = super(stock_warehouse_order_cycle, self).create(cr, uid, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                self.log(cr, uid, new_id, _(SHORT_SHELF_LIFE_MESS))
                
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        add message
        '''
        if context is None:
            context = {}
            
        result = super(stock_warehouse_order_cycle, self).write(cr, uid, ids, vals, context=context)
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
        
        return result
    
stock_warehouse_order_cycle()


class stock_picking(osv.osv):
    '''
    modify hook function
    '''
    _inherit = 'stock.picking'
    
    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'
        
        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assetId = partial_datas.get('move%s'%(move.id), {}).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})
        
        return defaults
    
    _columns = {}
    
stock_picking()


class stock_move(osv.osv):
    '''
    add kc/dg
    '''
    _inherit = 'stock.move'
    
    def create(self, cr, uid, vals, context=None):
        '''
        complete info normally generated by javascript on_change function
        '''
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)

            if vals.get('picking_id') and product.type == 'consu' and vals.get('location_dest_id') != id_cross:
                pick_bro = self.pool.get('stock.picking').browse(cr, uid, vals.get('picking_id'))
                id_nonstock = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')
                if vals.get('sale_line_id'):
                    id_pack = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')
                    if pick_bro.type == 'out':
                        vals.update(location_id=id_cross)
                    else:
                        vals.update(location_id=id_nonstock[1])
                    vals.update(location_dest_id=id_pack[1])
                else:
                    if pick_bro.type != 'out':
                        vals.update(location_dest_id=id_nonstock[1])

            if product.batch_management:
                vals.update(hidden_batch_management_mandatory=True)
            elif product.perishable:
                vals.update(hidden_perishable_mandatory=True)
            else:
                vals.update(hidden_batch_management_mandatory=False,
                            hidden_perishable_mandatory=False,
                            )
        # call super
        result = super(stock_move, self).create(cr, uid, vals, context=context)
        return result
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        complete info normally generated by javascript on_change function
        '''
        id_cross = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        prod_obj = self.pool.get('product.product')

        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)

            if vals.get('picking_id') and product.type == 'consu' and vals.get('location_dest_id') != id_cross:
                pick_bro = self.pool.get('stock.picking').browse(cr, uid, vals.get('picking_id'))
                id_nonstock = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')
                if vals.get('sale_line_id'):
                    id_pack = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_location_packing')
                    if pick_bro.type == 'out':
                        vals.update(location_id=id_cross)
                    else:
                        vals.update(location_id=id_nonstock[1])
                    vals.update(location_dest_id=id_pack[1])
                else:
                    if pick_bro.type != 'out':
                        vals.update(location_dest_id=id_nonstock[1])

            if product.batch_management:
                vals.update(hidden_batch_management_mandatory=True)
            elif product.perishable:
                vals.update(hidden_perishable_mandatory=True)
            else:
                vals.update(hidden_batch_management_mandatory=False,
                            hidden_perishable_mandatory=False,
                            )
        # call super
        result = super(stock_move, self).write(cr, uid, ids, vals, context=context)
        return result

    def _kc_dg(self, cr, uid, ids, name, arg, context=None):
        '''
        return 'KC' if cold chain or 'DG' if dangerous goods
        '''
        result = {}
        for id in ids:
            result[id] = ''
            
        for move in self.browse(cr, uid, ids, context=context):
            if move.product_id:
                if move.product_id.heat_sensitive_item:
                    result[move.id] = 'KC'
                elif move.product_id.dangerous_goods:
                    result[move.id] = 'DG'
        
        return result
    
    def _check_batch_management(self, cr, uid, ids, context=None):
        """
        check for batch management
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done' and move.location_id.id != move.location_dest_id.id:
                if move.product_id.batch_management:
                    if not move.prodlot_id and move.product_qty:
                        raise osv.except_osv(_('Error!'),  _('You must assign a Batch Number for this product (Batch Number Mandatory).'))
        return True
    
    def _check_perishable(self, cr, uid, ids, context=None):
        """
        check for perishable
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done' and move.location_id.id != move.location_dest_id.id:
                if move.product_id.perishable:
                    if not move.prodlot_id and move.product_qty:
                        raise osv.except_osv(_('Error!'),  _('You must assign an Expiry Date for this product (Expiry Date Mandatory).'))
        return True
    
    def _check_prodlot_need(self, cr, uid, ids, context=None):
        """
        If the move has a prodlot but does not need one, return False.
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.prodlot_id:
                if not move.product_id.perishable and not move.product_id.batch_management:
                    raise osv.except_osv(_('Error!'),  _('The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory.'))
        return True
    
    def _check_prodlot_need_batch_management(self, cr, uid, ids, context=None):
        """
        If the product is batch management while the selected prodlot is 'internal'.
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.prodlot_id:
                if move.prodlot_id.type == 'internal' and move.product_id.batch_management:
                    raise osv.except_osv(_('Error!'),  _('The selected product is Batch Number Mandatory while the selected Batch number corresponds to Expiry Date Mandatory.'))
        return True
    
    def _check_prodlot_need_perishable(self, cr, uid, ids, context=None):
        """
        If the product is perishable ONLY while the selected prodlot is 'standard'.
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.prodlot_id:
                if move.prodlot_id.type == 'standard' and not move.product_id.batch_management and move.product_id.perishable:
                    raise osv.except_osv(_('Error!'),  _('The selected product is Expiry Date Mandatory while the selected Batch number corresponds to Batch Number Mandatory.'))
        return True
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False, loc_dest_id=False, address_id=False, parent_type=False, purchase_line_id=False, out=False,):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = super(stock_move, self).onchange_product_id(cr, uid, ids, prod_id, loc_id,
                                                             loc_dest_id, address_id)

        # product changes, prodlot is always cleared
        result.setdefault('value', {})['prodlot_id'] = False
        # reset the hidden flag
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        if prod_id:
            product = self.pool.get('product.product').browse(cr, uid, prod_id)

            if product.batch_management:
                result.setdefault('value', {})['hidden_batch_management_mandatory'] = True
                result['warning'] = {'title': _('Info'),
                                     'message': _('The selected product is Batch Management.')}

            elif product.perishable:
                result.setdefault('value', {})['hidden_perishable_mandatory'] = True
                result['warning'] = {'title': _('Info'),
                                     'message': _('The selected product is Perishable.')}
        # quantities are set to False
        result.setdefault('value', {}).update({'product_qty': 0.00,
                                               'product_uos_qty': 0.00,
                                               })
            
        return result
    
    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        function for KC/SSL/DG/NP products
        '''
        # objects
        kit_obj = self.pool.get('composition.kit')
        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False})
        
        for obj in self.browse(cr, uid, ids, context=context):
            # keep cool
            if obj.product_id.heat_sensitive_item:
                result[obj.id]['kc_check'] = True
            # ssl
            if obj.product_id.short_shelf_life:
                result[obj.id]['ssl_check'] = True
            # dangerous goods
            if obj.product_id.dangerous_goods:
                result[obj.id]['dg_check'] = True
            # narcotic
            if obj.product_id.narcotic:
                result[obj.id]['np_check'] = True
            # lot management
            if obj.product_id.batch_management:
                result[obj.id]['lot_check'] = True
            # expiry date management
            if obj.product_id.perishable:
                result[obj.id]['exp_check'] = True
            # contains a kit and allow the creation of a new composition LIst
            # will be false if the kit is batch management and a composition list already uses this batch number
            # only one composition list can  use a given batch number for a given product
            if obj.product_id.type == 'product' and obj.product_id.subtype == 'kit':
                if obj.prodlot_id:
                    # search if composition list already use this batch number
                    kit_ids = kit_obj.search(cr, uid, [('composition_lot_id', '=', obj.prodlot_id.id)], context=context)
                    if not kit_ids:
                        result[obj.id]['kit_check'] = True
                else:
                    # not batch management, we can create as many composition list as we want
                    result[obj.id]['kit_check'] = True
            
        return result
    
    def _check_tracking(self, cr, uid, ids, context=None):
        """ Checks if production lot is assigned to stock move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if not move.prodlot_id and move.product_qty and \
               (move.state == 'done' and \
               ( \
                   (move.product_id.track_production and move.location_id.usage == 'production') or \
                   (move.product_id.track_production and move.location_dest_id.usage == 'production') or \
                   (move.product_id.track_incoming and move.location_id.usage == 'supplier') or \
                   (move.product_id.track_outgoing and move.location_dest_id.usage == 'customer') \
               )):
                raise osv.except_osv(_('Error!'),  _('You must assign a batch number for this product.'))
        return True
            
    _columns = {
        'kc_dg': fields.function(_kc_dg, method=True, string='KC/DG', type='char'),
        # if prodlot needs to be mandatory, add 'required': ['|', ('hidden_batch_management_mandatory','=',True), ('hidden_perishable_mandatory','=',True)] in attrs
        'hidden_batch_management_mandatory': fields.boolean(string='Hidden Flag for Batch Management product',),
        'hidden_perishable_mandatory': fields.boolean(string='Hidden Flag for Perishable product',),
        'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
        'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
        'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
        'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
        'lot_check': fields.function(_get_checks_all, method=True, string='B.Num', type='boolean', readonly=True, multi="m"),
        'exp_check': fields.function(_get_checks_all, method=True, string='Exp', type='boolean', readonly=True, multi="m"),
        'kit_check': fields.function(_get_checks_all, method=True, string='Kit', type='boolean', readonly=True, multi="m"),
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch', states={'done': [('readonly', True)]}, help="Batch number is used to put a serial number on the production", select=True),
    }
    
    _constraints = [(_check_batch_management,
                     'You must assign a Batch Number for this product (Batch Number Mandatory).',
                     ['prodlot_id']),
                    (_check_perishable,
                     'You must assign an Expiry Date for this product (Expiry Date Mandatory).',
                     ['prodlot_id']),
                    (_check_prodlot_need,
                     'The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory.',
                     ['prodlot_id']),
                    (_check_prodlot_need_batch_management,
                     'The selected product is Batch Number Mandatory while the selected Batch number corresponds to Expiry Date Mandatory.',
                     ['prodlot_id']),
                    (_check_prodlot_need_perishable,
                     'The selected product is Expiry Date Mandatory while the selected Batch number corresponds to Batch Number Mandatory.',
                     ['prodlot_id']),
                     (_check_tracking,
                      'You must assign a batch number for this product.',
                      ['prodlot_id']),
                    ]

stock_move()


class stock_production_lot(osv.osv):
    '''
    productin lot modifications
    '''
    _inherit = 'stock.production.lot'
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Correct fields in order to have those from account_statement_from_invoice_lines (in case where account_statement_from_invoice is used)
        """
        if context is None:
            context = {}
        
        # warehouse wizards or inventory screen
        if view_type == 'tree' and ((context.get('expiry_date_check', False) and not context.get('batch_number_check', False)) or context.get('hidden_perishable_mandatory', False)):
            view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'specific_rules', 'view_production_lot_expiry_date_tree')
            if view:
                view_id = view[1]
        result = super(stock_production_lot, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        increase the batch number
        create a new sequence
        '''
        if default is None:
            default = {}
            
        # original reference
        lot_name = self.read(cr, uid, id, ['name'])['name']
        default.update(name='%s (copy)'%lot_name, date=time.strftime('%Y-%m-%d'))
        
        return super(stock_production_lot, self).copy(cr, uid, id, default, context=context)
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        clear the revisions
        '''
        if default is None:
            default = {}
        default.update(revisions=[])
        return super(stock_production_lot, self).copy_data(cr, uid, id, default, context=context)
    
    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Batch number'
        code = 'stock.production.lot'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)
    
    def create(self, cr, uid, vals, context=None):
        '''
        create the sequence for the version management
        '''
        if context is None:
            context = {}
            
        sequence = self.create_sequence(cr, uid, vals, context=context)
        vals.update({'sequence_id': sequence,})
        
        if context.get('update_mode') in ['init', 'update']:
            if not vals.get('life_date'):
                # default value to today
                vals.update(life_date=time.strftime('%Y-%m-%d'))
        
        return super(stock_production_lot, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        update the sequence for the version management
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        revision_obj = self.pool.get('stock.production.lot.revision')
        
        for lot in self.browse(cr, uid, ids, context=context):
           # create revision object for each lot
           version_number = lot.sequence_id.get_id(test='id', context=context)
           values = {'name': 'Auto Revision Logging',
                     'description': 'The batch number has been modified, this revision log has been created automatically.',
                     'date': time.strftime('%Y-%m-%d'),
                     'indice': version_number,
                     'author_id': uid,
                     'lot_id': lot.id,}
           revision_obj.create(cr, uid, values, context=context)
        
        return super(stock_production_lot, self).write(cr, uid, ids, vals, context=context)
    
    def remove_flag(self, flag, _list):
        '''
        if we do not remove the flag, we fall into an infinite loop
        '''
        args2 = []
        for arg in _list:
            if arg[0] != flag:
                args2.append(arg)
        return args2
    
    def search_check_type(self, cr, uid, obj, name, args, context=None):
        '''
        modify the query to take the type of prodlot into account according to product's attributes
        'Batch Number mandatory' and 'Expiry Date Mandatory'
        
        if batch management: display only 'standard' lot
        if expiry and not batch management: display only 'internal' lot
        else: display normally
        '''
        product_obj = self.pool.get('product.product')
        product_id = context.get('product_id', False)
        
        # remove flag avoid infinite loop
        args = self.remove_flag('check_type', args)
            
        if not product_id:
            return args
        
        # check the product
        product = product_obj.browse(cr, uid, product_id, context=context)

        if product.batch_management:
            # standard lots
            args.append(('type', '=', 'standard'))
        elif product.perishable:
            # internal lots
            args.append(('type', '=', 'internal'))
            
        return args
    
    def _get_false(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return false for each id
        '''
        if isinstance(ids,(long, int)):
           ids = [ids]
        
        result = {}
        for id in ids:
          result[id] = False
        return result

    def _stock_search_virtual(self, cr, uid, obj, name, args, context=None):
        """ Searches Ids of products
        @return: Ids of locations
        """
        if context is None:
            context = {}
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
        else:
            locations = context['location_id'] and [context['location_id']] or []
        
        ids = [('id', 'in', [])]
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots_virtual
                where
                    location_id IN %s group by prodlot_id
                having  sum(qty) '''+ str(args[0][1]) + str(args[0][2]),(tuple(locations),))
            res = cr.fetchall()
            ids = [('id', 'in', map(lambda x: x[0], res))]
        return ids
    
    def _stock_search(self, cr, uid, obj, name, args, context=None):
        '''
        call super method, as fields.function does not work with inheritance
        '''
        return super(stock_production_lot, self)._stock_search(cr, uid, obj, name, args, context=context)

    def _get_stock_virtual(self, cr, uid, ids, field_name, arg, context=None):
        """ Gets stock of products for locations
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        # when the location_id = False results now in showing stock for all internal locations
        # *previously*, was showing the location of no location (= 0.0 for all prodlot)
        if 'location_id' not in context or not context['location_id']:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
        else:
            locations = context['location_id'] and [context['location_id']] or []

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}.fromkeys(ids, 0.0)
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(qty)
                from
                    stock_report_prodlots_virtual
                where
                    location_id IN %s and prodlot_id IN %s group by prodlot_id''',(tuple(locations),tuple(ids),))
            res.update(dict(cr.fetchall()))

        return res
    
    def _get_stock(self, cr, uid, ids, field_name, arg, context=None):
        '''
        call super method, as fields.function does not work with inheritance
        '''
        return super(stock_production_lot, self)._get_stock(cr, uid, ids, field_name, arg, context=context)
    
    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        function for KC/SSL/DG/NP products
        '''
        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False})
            
        for obj in self.browse(cr, uid, ids, context=context):
            # keep cool
            if obj.product_id.heat_sensitive_item:
                result[obj.id]['kc_check'] = True
            # ssl
            if obj.product_id.short_shelf_life:
                result[obj.id]['ssl_check'] = True
            # dangerous goods
            if obj.product_id.dangerous_goods:
                result[obj.id]['dg_check'] = True
            # narcotic
            if obj.product_id.narcotic:
                result[obj.id]['np_check'] = True
            # lot management
            if obj.product_id.batch_management:
                result[obj.id]['lot_check'] = True
            # expiry date management
            if obj.product_id.perishable:
                result[obj.id]['exp_check'] = True
            
        return result

    def _check_batch_type_integrity(self, cr, uid, ids, context=None):
        '''
        Check if the type of the batch is consistent with the product attributes
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.type == 'standard' and not obj.product_id.batch_management:
                return False

        return True

    def _check_perishable_type_integrity(self, cr, uid, ids, context=None):
        '''
        Check if the type of the batch is consistent with the product attributes
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.type == 'internal' and (obj.product_id.batch_management or not obj.product_id.perishable):
                return False

        return True

    def _get_delete_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns if the batch is deletable
        '''
        res = {}
        for batch_id in ids:
            res[batch_id] = True
            move_ids = self.pool.get('stock.move').search(cr, uid, [('prodlot_id', '=', batch_id)], context=context)
            if move_ids:
                res[batch_id] = False

        return res
    
    _columns = {'check_type': fields.function(_get_false, fnct_search=search_check_type, string='Check Type', type="boolean", readonly=True, method=True),
                # readonly is True, the user is only allowed to create standard lots - internal lots are system-created
                'type': fields.selection([('standard', 'Standard'),('internal', 'Internal'),], string="Type", readonly=True),
                #'expiry_date': fields.date('Expiry Date'),
                'name': fields.char('Batch Number', size=1024, required=True, help="Unique batch number, will be displayed as: PREFIX/SERIAL [INT_REF]"),
                'date': fields.datetime('Auto Creation Date', required=True),
                'sequence_id': fields.many2one('ir.sequence', 'Batch Sequence', required=True,),
                'stock_virtual': fields.function(_get_stock_virtual, method=True, type="float", string="Available Stock", select=True,
                                                 help="Current available quantity of products with this Batch Numbre Number in company warehouses",
                                                 digits_compute=dp.get_precision('Product UoM'), readonly=True,
                                                 fnct_search=_stock_search_virtual,),
                'stock_available': fields.function(_get_stock, fnct_search=_stock_search, method=True, type="float", string="Real Stock", select=True,
                                                   help="Current real quantity of products with this Batch Number in company warehouses",
                                                   digits_compute=dp.get_precision('Product UoM')),
                'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
                'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
                'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
                'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
                'lot_check': fields.function(_get_checks_all, method=True, string='B.Num', type='boolean', readonly=True, multi="m"),
                'exp_check': fields.function(_get_checks_all, method=True, string='Exp', type='boolean', readonly=True, multi="m"),
                'delete_ok': fields.function(_get_delete_ok, method=True, string='Possible deletion ?', type='boolean', readonly=True),
                }
    
    _defaults = {'type': 'standard',
                 'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'stock.production.lot', context=c),
                 'name': False,
                 'life_date': False,
                 }
    
    _sql_constraints = [('name_uniq', 'unique (product_id,name)', 'For a given product, the batch number must be unique.'),
                        ]

    _constraints = [(_check_batch_type_integrity,
                    'You can\'t create a standard batch number for a product which is not batch mandatory. If the product is perishable, the system will create automatically an internal batch number on reception/inventory.',
                    ['Type', 'Product']),
                    (_check_perishable_type_integrity,
                    'You can\'t create an internal Batch Number for a product which is batch managed or which is not perishable. If the product is batch managed, please create a standard batch number.',
                    ['Type', 'Product']),
                ]

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        search function of production lot
        '''
        result = super(stock_production_lot, self).search(cr, uid, args=args, offset=offset, limit=limit, order=order, context=context, count=count)
        
        return result
    
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if context is None:
            context = {}

        reads = self.read(cr, uid, ids, ['name', 'prefix', 'ref', 'life_date'], context)
        res = []
# TODO replace by _get_format in uf-651
        if context.get('with_expiry'):
            user_obj = self.pool.get('res.users')
            lang_obj = self.pool.get('res.lang')
            user_lang = user_obj.read(cr, uid, uid, ['context_lang'], context=context)['context_lang']
            lang_id = lang_obj.search(cr, uid, [('code','=',user_lang)])
            date_format = lang_id and lang_obj.read(cr, uid, lang_id[0], ['date_format'], context=context)['date_format'] or '%m/%d/%Y'

        for record in reads:
            if context.get('with_expiry') and record['life_date']:
                name = '%s - %s'%(record['name'], DateTime.strptime(record['life_date'],'%Y-%m-%d').strftime(date_format).decode('utf-8'))
            else:
                name = record['name']
            res.append((record['id'], name))
        return res

    def unlink(self, cr, uid, ids, context=None):
        '''
        Remove the batch
        '''
        for batch in self.browse(cr, uid, ids, context=context):
            if not batch.delete_ok:
                raise osv.except_osv(_('Error'), _('You cannot remove a batch number which has stock !'))

        return super(stock_production_lot, self).unlink(cr, uid, batch.id, context=context)


stock_production_lot()


class stock_location(osv.osv):
    '''
    override stock location to add:
    - stock_real
    - stock_virtual
    '''
    _inherit = 'stock.location'
    
    def replace_field_key(self, fieldsDic, search, replace):
        '''
        will replace 'stock_real' by 'stock_real_specific'
        and 'stock_virtual' by 'stock_virtual_specific'
        
        and return a new dictionary
        '''
        return dict((replace if key == search else key, (self.replace_field_key(value, search, replace) if isinstance(value, dict) else value)) for key, value in fieldsDic.items())
    
    def _product_value_specific_rules(self, cr, uid, ids, field_names, arg, context=None):
        '''
        add two fields for custom stock computation, if no product selected, both stock are set to 0.0
        '''
        if context is None:
            context = {}
        # initialize data
        result = {}
        for id in ids:
            result[id] = {}
            for f in field_names:
                result[id].update({f: False,})
        # if product is set to False, it does not make sense to return a stock value, return False for each location
        if 'product_id' in context and not context['product_id']:
            return result
        
        result = super(stock_location, self)._product_value(cr, uid, ids, ['stock_real', 'stock_virtual'], arg, context=context)
        # replace stock real
        result = self.replace_field_key(result, 'stock_real', 'stock_real_specific')
        # replace stock virtual
        result = self.replace_field_key(result, 'stock_virtual', 'stock_virtual_specific')
        return result
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        display the modified stock values (stock_real_specific, stock_virtual_specific) if needed
        """
        if context is None:
            context = {}
        # warehouse wizards or inventory screen
        if view_type == 'tree' and context.get('specific_rules_tree_view', False):
            view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'specific_rules', 'view_location_tree2')
            if view:
                view_id = view[1]
        result = super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return result
    
    _columns = {'stock_real_specific': fields.function(_product_value_specific_rules, method=True, type='float', string='Real Stock', multi="get_vals_specific_rules"),
                'stock_virtual_specific': fields.function(_product_value_specific_rules, method=True, type='float', string='Virtual Stock', multi="get_vals_specific_rules"),
                }
    
stock_location()


class stock_production_lot_revision(osv.osv):
    _inherit = 'stock.production.lot.revision'
    _order = 'indice desc'
    
stock_production_lot_revision()


class stock_inventory(osv.osv):
    '''
    override the action_confirm to create the production lot if needed
    '''
    _inherit = 'stock.inventory'

    def _check_line_data(self, cr, uid, ids, context=None):
        for inv in self.browse(cr, uid, ids, context=context):
            if inv.state not in ('draft', 'cancel'):
                for line in inv.inventory_line_id:
                    if line.product_qty != 0.00 and not line.location_id:
                        return False

        return True

    def copy(self, cr, uid, inventory_id, defaults, context=None):
        '''
        Set the creation date of the document to the current date
        '''
        if not defaults:
            defaults = {}

        defaults.update({'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'move_ids': False})
        return super(stock_inventory, self).copy(cr, uid, inventory_id, defaults, context=context)
        
    _columns = {
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }

    _constraints = [
        (_check_line_data, "You must define a stock location for each line", ['state']),
    ]
    
    def onChangeSearchNomenclature(self, cr, uid, ids, position, n_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, n_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        line_obj = self.pool.get('stock.inventory.line')
        product_obj = self.pool.get('product.product')
        
        if context is None:
            context = {}

        discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
            
        for inv in self.browse(cr, uid, ids, context=context):
            product_ids = []

            nom = False
            field = False
            # Get all products for the defined nomenclature
            if inv.nomen_manda_3:
                nom = inv.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif inv.nomen_manda_2:
                nom = inv.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif inv.nomen_manda_1:
                nom = inv.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif inv.nomen_manda_0:
                nom = inv.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if inv.sublist_id:
                for line in inv.sublist_id.product_ids:
                    product_ids.append(line.name.id)
                    
            for product in product_obj.browse(cr, uid, product_ids, context=context):
                # Check if the product is not already in the list
                if product.type not in ('consu', 'service', 'service_recep') and\
                   not line_obj.search(cr, uid, [('inventory_id', '=', inv.id), 
                                                 ('product_id', '=', product.id),
                                                 ('product_uom', '=', product.uom_id.id)], context=context):
                    line_obj.create(cr, uid, {'inventory_id': inv.id,
                                              'product_id': product.id,
                                              'reason_type_id': discrepancy_id,
                                              'product_uom': product.uom_id.id}, context=context)
        
        return True

    def get_nomen(self, cr, uid, ids, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, ids, field, context={'withnum': 1})

    def _hook_dont_move(self, cr, uid, *args, **kwargs):
        res = super(stock_inventory, self)._hook_dont_move(cr, uid, *args, **kwargs)
        if 'line' in kwargs:
            return res and not kwargs['line'].dont_move

        return res
    
    def action_confirm(self, cr, uid, ids, context=None):
        '''
        if the line is perishable without prodlot, we create the prodlot
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        product_obj = self.pool.get('product.product')
        # treat the needed production lot
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.inventory_line_id:
                if self._name == 'initial.stock.inventory' and line.product_qty == 0.00:
                    line.write({'dont_move': True})
                    continue
                if line.hidden_perishable_mandatory and not line.expiry_date:
                    raise osv.except_osv(_('Error'), _('The product %s is perishable but the line with this product has no expiry date') % product_obj.name_get(cr, uid, [line.product_id.id])[0][1])
                if line.hidden_batch_management_mandatory and not line.prod_lot_id:
                    raise osv.except_osv(_('Error'), _('The product %s is batch mandatory but the line with this product has no batch') % product_obj.name_get(cr, uid, [line.product_id.id])[0][1])
                # if perishable product
                if line.hidden_perishable_mandatory and not line.hidden_batch_management_mandatory:
                    # integrity test
                    assert line.product_id.perishable, 'product is not perishable but line is'
                    assert line.expiry_date, 'expiry date is not set'
                    # if no production lot, we create a new one
                    if not line.prod_lot_id:
                        # double check to find the corresponding prodlot
                        prodlot_ids = prodlot_obj.search(cr, uid, [('life_date', '=', line.expiry_date),
                                                                   ('type', '=', 'internal'),
                                                                   ('product_id', '=', line.product_id.id)], context=context)
                        # no prodlot, create a new one
                        if not prodlot_ids:
                            vals = {'product_id': line.product_id.id,
                                    'life_date': line.expiry_date,
                                    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'),
                                    'type': 'internal',
                                    }
                            prodlot_id = prodlot_obj.create(cr, uid, vals, context=context)
                        else:
                            prodlot_id = prodlot_ids[0]
                        # update the line
                        line.write({'prod_lot_id': prodlot_id,},)
        
        # super function after production lot creation - production lot are therefore taken into account at stock move creation
        result = super(stock_inventory, self).action_confirm(cr, uid, ids, context=context)      
        return result
                        
stock_inventory()


class stock_inventory_line(osv.osv):
    '''
    add mandatory or readonly behavior to prodlot
    '''
    _inherit = 'stock.inventory.line'
    
    def common_on_change(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False, result=None):
        '''
        commmon qty computation
        '''
        if result is None:
            result = {}
        if not product:
            return result
        product_obj = self.pool.get('product.product').browse(cr, uid, product)
        product_uom = product_obj.uom_id.id
        if uom:
            uom_obj = self.pool.get('product.uom').browse(cr, uid, uom)
            if uom_obj.category_id.id == product_obj.uom_id.category_id.id:
                product_uom = uom
        #uom = uom or product_obj.uom_id.id
        stock_context = {'uom': product_uom, 'to_date': to_date,
                         'prodlot_id':prod_lot_id,}
        if location_id:
            # if a location is specified, we do not list the children locations, otherwise yes
            stock_context.update({'compute_child': False,})
        amount = self.pool.get('stock.location')._product_get(cr, uid, location_id, [product], stock_context)[product]
        result.setdefault('value', {}).update({'product_qty': amount, 'product_uom': product_uom})
        return result
    
    def change_lot(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        # reset expiry date or fill it
        if prod_lot_id:
            result['value'].update(expiry_date=prodlot_obj.browse(cr, uid, prod_lot_id).life_date)
        else:
            result['value'].update(expiry_date=False)
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product, prod_lot_id, uom, to_date, result=result)
        return result
    
    def change_expiry(self, cr, uid, id, expiry_date, product_id, type_check, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        
        if expiry_date and product_id:
            prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                    ('type', '=', 'internal'),
                                                    ('product_id', '=', product_id)], context=context)
            if not prod_ids:
                if type_check == 'in':
                    # the corresponding production lot will be created afterwards
                    result['warning'] = {'title': _('Info'),
                                     'message': _('The selected Expiry Date does not exist in the system. It will be created during validation process.')}
                    # clear prod lot
                    result['value'].update(prod_lot_id=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(expiry_date=False, prod_lot_id=False)
            else:
                # return first prodlot
                result['value'].update(prod_lot_id=prod_ids[0])
        else:
            # clear expiry date, we clear production lot
            result['value'].update(prod_lot_id=False,
                                   expiry_date=False,
                                   )
        return result
    
    def on_change_location_id(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        """ Changes UoM and name if product_id changes.
        @param location_id: Location id
        @param product: Changed product_id
        @param uom: UoM product
        @return:  Dictionary of changed values
        """
        result = {}
        if not product:
            # do nothing
            result.setdefault('value', {}).update({'product_qty': 0.0,})
            return result
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product, prod_lot_id, uom, to_date, result=result)
        return result
    
    def on_change_product_id_specific_rules(self, cr, uid, ids, location_id, product, prod_lot_id, uom=False, to_date=False,):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = super(stock_inventory_line, self).on_change_product_id(cr, uid, ids, location_id, product, uom, to_date)
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['prod_lot_id'] = False
        result.setdefault('value', {})['expiry_date'] = False
        # reset the hidden flags
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        if product:
            product_obj = self.pool.get('product.product').browse(cr, uid, product)
            if product_obj.batch_management:
                result.setdefault('value', {})['hidden_batch_management_mandatory'] = True
            elif product_obj.perishable:
                result.setdefault('value', {})['hidden_perishable_mandatory'] = True
            # if not product, result is 0.0 by super
            # compute qty
            result = self.common_on_change(cr, uid, ids, location_id, product, prod_lot_id, uom, to_date, result=result)
        return result
    
    def create(self, cr, uid, vals, context=None):
        '''
        complete info normally generated by javascript on_change function
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if product.batch_management:
                vals.update(hidden_batch_management_mandatory=True)
            elif product.perishable:
                vals.update(hidden_perishable_mandatory=True)
            else:
                vals.update(hidden_batch_management_mandatory=False,
                            hidden_perishable_mandatory=False,
                            )
        # complete expiry date from production lot - needed if not created from GUI
        prodlot_obj = self.pool.get('stock.production.lot')
        if vals.get('prod_lot_id', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prod_lot_id'), context=context).life_date)
        # call super
        result = super(stock_inventory_line, self).create(cr, uid, vals, context=context)
        return result
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        complete info normally generated by javascript on_change function
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            # complete hidden flags - needed if not created from GUI
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if product.batch_management:
                vals.update(hidden_batch_management_mandatory=True)
            elif product.perishable:
                vals.update(hidden_perishable_mandatory=True)
            else:
                vals.update(hidden_batch_management_mandatory=False,
                            hidden_perishable_mandatory=False,
                            )
        # complete expiry date from production lot - needed if not created from GUI
        prodlot_obj = self.pool.get('stock.production.lot')
        if vals.get('prod_lot_id', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prod_lot_id'), context=context).life_date)
        
        # call super
        result = super(stock_inventory_line, self).write(cr, uid, ids, vals, context=context)
        return result
    
    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        function for KC/SSL/DG/NP products
        '''
        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False,})
            
        for obj in self.browse(cr, uid, ids, context=context):
            # keep cool
            if obj.product_id.heat_sensitive_item:
                result[obj.id]['kc_check'] = True
            # ssl
            if obj.product_id.short_shelf_life:
                result[obj.id]['ssl_check'] = True
            # dangerous goods
            if obj.product_id.dangerous_goods:
                result[obj.id]['dg_check'] = True
            # narcotic
            if obj.product_id.narcotic:
                result[obj.id]['np_check'] = True
            # lot management
            if obj.product_id.batch_management:
                result[obj.id]['lot_check'] = True
            # expiry date management
            if obj.product_id.perishable:
                result[obj.id]['exp_check'] = True

            # has a problem
            # Line will be displayed in red if it's not correct
            result[obj.id]['has_problem'] = False
            if not obj.location_id \
               or not self._check_perishable(cr, uid, [obj.id]) \
               or not self._check_batch_management(cr, uid, [obj.id]):
                   result[obj.id]['has_problem'] = True
            
        return result
    
    def _check_batch_management(self, cr, uid, ids, context=None):
        '''
        check for batch management
        '''
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.inventory_id.state not in ('draft', 'cancel') and obj.product_id.batch_management:
                if not obj.prod_lot_id or obj.prod_lot_id.type != 'standard':
                    return False
        return True
    
    def _check_perishable(self, cr, uid, ids, context=None):
        """
        check for perishable ONLY
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.inventory_id.state not in ('draft', 'cancel') and obj.product_id.perishable and not obj.product_id.batch_management:
                if (not obj.prod_lot_id and not obj.expiry_date) or (obj.prod_lot_id and obj.prod_lot_id.type != 'internal'):
                    return False
        return True
    
    def _check_prodlot_need(self, cr, uid, ids, context=None):
        """
        If the inv line has a prodlot but does not need one, return False.
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.prod_lot_id:
                if not obj.product_id.perishable and not obj.product_id.batch_management:
                    return False
        return True
    
    _columns = {
        'hidden_perishable_mandatory': fields.boolean(string='Hidden Flag for Perishable product',),
        'hidden_batch_management_mandatory': fields.boolean(string='Hidden Flag for Batch Management product',),
        # Remove the 'required' attribute on location_id to allow the possiblity to fill lines with list or nomenclature
        # The required attribute is True on the XML view
        'location_id': fields.many2one('stock.location', 'Location'),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Batch', domain="[('product_id','=',product_id)]"),
        'expiry_date': fields.date(string='Expiry Date'),
        'type_check': fields.char(string='Type Check', size=1024,),
        'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
        'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
        'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
        'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
        'lot_check': fields.function(_get_checks_all, method=True, string='B.Num', type='boolean', readonly=True, multi="m"),
        'exp_check': fields.function(_get_checks_all, method=True, string='Exp', type='boolean', readonly=True, multi="m"),
        'has_problem': fields.function(_get_checks_all, method=True, string='Has problem', type='boolean', readonly=True, multi="m"),
        'dont_move': fields.boolean(string='Don\'t create stock.move for this line'),
    }
    
    _defaults = {# in is used, meaning a new prod lot will be created if the specified expiry date does not exist
                 'type_check': 'in',
                 'dont_move': lambda *a: False,
                 }
    
    _constraints = [(_check_batch_management,
                     'You must assign a Batch Number which corresponds to Batch Number Mandatory Products.',
                     ['prod_lot_id']),
                    (_check_perishable,
                     'You must assign a Batch Numbre which corresponds to Expiry Date Mandatory Products.',
                     ['prod_lot_id']),
                    (_check_prodlot_need,
                     'The selected product is neither Batch Number Mandatory nor Expiry Date Mandatory',
                     ['prod_lot_id']),
                    ]

stock_inventory_line()

class report_stock_inventory(osv.osv):
    '''
    UF-565: add group by expired_date
    '''
    _inherit = "report.stock.inventory"
    
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_stock_inventory')
        cr.execute("""
CREATE OR REPLACE view report_stock_inventory AS (
    (SELECT
        min(m.id) as id, m.date as date,
        m.expired_date as expired_date,
        m.address_id as partner_id, m.location_id as location_id,
        m.product_id as product_id, pt.categ_id as product_categ_id, l.usage as location_type,
        m.company_id,
        m.state as state, m.prodlot_id as prodlot_id,
        coalesce(sum(-pt.standard_price * m.product_qty)::decimal, 0.0) as value,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(-m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum(-m.product_qty * pu.factor)::decimal, 0.0) END as product_qty
    FROM
        stock_move m
            LEFT JOIN stock_picking p ON (m.picking_id=p.id)
            LEFT JOIN product_product pp ON (m.product_id=pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                LEFT JOIN product_uom pu ON (pt.uom_id=pu.id)
            LEFT JOIN product_uom u ON (m.product_uom=u.id)
            LEFT JOIN stock_location l ON (m.location_id=l.id)
    GROUP BY
        m.id, m.product_id, m.product_uom, pt.categ_id, m.address_id, m.location_id,  m.location_dest_id,
        m.prodlot_id, m.expired_date, m.date, m.state, l.usage, m.company_id,pt.uom_id
) UNION ALL (
    SELECT
        -m.id as id, m.date as date,
        m.expired_date as expired_date,
        m.address_id as partner_id, m.location_dest_id as location_id,
        m.product_id as product_id, pt.categ_id as product_categ_id, l.usage as location_type,
        m.company_id,
        m.state as state, m.prodlot_id as prodlot_id,
        coalesce(sum(pt.standard_price * m.product_qty )::decimal, 0.0) as value,
        CASE when pt.uom_id = m.product_uom
        THEN
        coalesce(sum(m.product_qty)::decimal, 0.0)
        ELSE
        coalesce(sum(m.product_qty * pu.factor)::decimal, 0.0) END as product_qty
    FROM
        stock_move m
            LEFT JOIN stock_picking p ON (m.picking_id=p.id)
            LEFT JOIN product_product pp ON (m.product_id=pp.id)
                LEFT JOIN product_template pt ON (pp.product_tmpl_id=pt.id)
                LEFT JOIN product_uom pu ON (pt.uom_id=pu.id)
            LEFT JOIN product_uom u ON (m.product_uom=u.id)
            LEFT JOIN stock_location l ON (m.location_dest_id=l.id)
    GROUP BY
        m.id, m.product_id, m.product_uom, pt.categ_id, m.address_id, m.location_id, m.location_dest_id,
        m.prodlot_id, m.expired_date, m.date, m.state, l.usage, m.company_id,pt.uom_id
    )
);
        """)
    
    _columns = {
        'prodlot_id': fields.many2one('stock.production.lot', 'Batch', readonly=True),
        'expired_date': fields.date(string='Expiry Date',),
    }
   
    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        if context is None:
            context = {}
        if fields is None:
            fields = []
        context['with_expiry'] = 1
        return super(report_stock_inventory, self).read(cr, uid, ids, fields, context, load)
    
    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
        '''
        UF-1546: This method is to remove the lines that have quantity = 0 from the list view
        '''
        res = super(report_stock_inventory, self).read_group(cr, uid, domain, fields, groupby, offset, limit, context, orderby)
        if self._name == 'report.stock.inventory' and res:
             return [data for data in res if data.get('product_qty', 10) != 0.0]
        return res
    
report_stock_inventory()

class product_product(osv.osv):
    _inherit = 'product.product'
    def open_stock_by_location(self, cr, uid, ids, context=None):
        name = 'Stock by Location'
        if context is None:
            context = {}
        if ids:
            prod = self.pool.get('product.product').read(cr, uid, ids[0], ['name', 'code'])
            name = "%s: [%s] %s"%(name, prod['code'], prod['name'])
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'view_location_tree_tree')[1] 

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.location',
            'view_type': 'tree',
            'view_id': [view_id],
            'domain': [('location_id','=',False)],
            'view_mode': 'tree',
            'context': {'product_id': context.get('active_id') , 'compute_child': False},
            'target': 'current',
        }

product_product()
