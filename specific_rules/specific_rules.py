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

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta, relativedelta
from osv import osv, fields
from osv.orm import browse_record, browse_null
from tools.translate import _

import decimal_precision as dp
import netsvc
import pooler
import time

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
                            'message': SHORT_SHELF_LIFE_MESS
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
                    self.log(cr, uid, obj.id, SHORT_SHELF_LIFE_MESS)
        
        return super(sale_order, self).write(cr, uid, ids, vals, context=context)
    
sale_order()


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
                    self.log(cr, uid, obj.id, SHORT_SHELF_LIFE_MESS)
        
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)
    
purchase_order()


class stock_warehouse_orderpoint(osv.osv):
    '''
    add message
    '''
    _inherit = 'stock.warehouse.orderpoint'
    
    def create(self, cr, uid, vals, context=None):
        '''
        add message
        '''
        new_id = super(stock_warehouse_orderpoint, self).create(cr, uid, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                self.log(cr, uid, new_id, SHORT_SHELF_LIFE_MESS)
                
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        add message
        '''
        result = super(stock_warehouse_orderpoint, self).write(cr, uid, ids, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, SHORT_SHELF_LIFE_MESS)
        
        return result
        
stock_warehouse_orderpoint()


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
                self.log(cr, uid, new_id, SHORT_SHELF_LIFE_MESS)
                
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        add message
        '''
        result = super(stock_warehouse_automatic_supply, self).write(cr, uid, ids, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, SHORT_SHELF_LIFE_MESS)
        
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
                self.log(cr, uid, new_id, SHORT_SHELF_LIFE_MESS)
                
        return new_id
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        add message
        '''
        if context is None:
            context = {}
            
        result = super(stock_warehouse_order_cycle, self).write(cr, uid, ids, vals, context=context)
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, SHORT_SHELF_LIFE_MESS)
        
        return result
    
stock_warehouse_order_cycle()


class stock_move(osv.osv):
    '''
    add kc/dg
    '''
    _inherit = 'stock.move'

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
        
    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='KC/DG', type='char'),}

stock_move()


class stock_production_lot(osv.osv):
    '''
    productin lot modifications
    '''
    _inherit = 'stock.production.lot'
    
    def product_id_change(self, cr, uid, ids, product_id, context=None):
        '''
        complete the life_date attribute
        '''
        product_obj = self.pool.get('product.product')
        values = {}
        if product_id:
            duration = product_obj.browse(cr, uid, product_id, context=context).life_time
            date = datetime.today() + relativedelta(months=duration)
            values.update(life_date=date.strftime('%Y-%m-%d'))
            
        return {'value':values}
    
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

        name = 'Production Lot'
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
        sequence = self.create_sequence(cr, uid, vals, context=context)
        vals.update({'sequence_id': sequence})
        
        return super(stock_production_lot, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        update the sequence for the version management
        '''
        revision_obj = self.pool.get('stock.production.lot.revision')
        
        for lot in self.browse(cr, uid, ids, context=context):
           # create revision object for each lot
           version_number = lot.sequence_id.get_id(test='id', context=context)
           values = {'name': 'Auto Revision Logging',
                     'description': 'The production lot has been modified, this revision log has been created automatically.',
                     'date': time.strftime('%Y-%m-%d'),
                     'indice': version_number,
                     'author_id': uid,
                     'lot_id': lot.id,}
           revision_obj.create(cr, uid, values, context=context)
        
        return super(stock_production_lot, self).write(cr, uid, ids, vals, context=context)
    
    def remove_flag(self, flag, list):
        '''
        if we do not remove the flag, we fall into an infinite loop
        '''
        i = 0
        to_del = []
        for arg in list:
            if arg[0] == flag:
                to_del.append(i)
            i+=1
        for i in to_del:
            list.pop(i)
        
        return True
    
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
        self.remove_flag('check_type', args)
            
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
    
    _columns = {'check_type': fields.function(_get_false, fnct_search=search_check_type, string='Check Type', type="boolean", readonly=True, method=True),
                'type': fields.selection([('internal', 'Internal'), ('standard', 'Standard'),], string="Type"),
                'expiry_date': fields.date('Expiry Date'),
                'name': fields.char('Batch Number', size=1024, required=True, help="Unique production lot, will be displayed as: PREFIX/SERIAL [INT_REF]"),
                'date': fields.datetime('Auto Creation Date', required=True),
                'sequence_id': fields.many2one('ir.sequence', 'Lot Sequence', required=True,),}
    
    _defaults = {'type': 'standard',}
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Batch Number must be unique !'),
    ]
    
    def search(self, cr, uid, args=[], offset=0, limit=None, order=None, context={}, count=False):
        '''
        search function of production lot
        '''
        result = super(stock_production_lot, self).search(cr, uid, args, offset, limit, order, context, count)
        
        return result
    
stock_production_lot()

class stock_production_lot_revision(osv.osv):
    _inherit = 'stock.production.lot.revision'
    
    _order = 'indice desc'
    
stock_production_lot_revision()
