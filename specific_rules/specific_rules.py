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
        
        product_obj = self.pool.get('product.product')
        product_id = vals.get('product_id', False)
        if product_id:
            if product_obj.browse(cr, uid, product_id, context=context).short_shelf_life:
                for obj in self.browse(cr, uid, ids, context=context):
                    self.log(cr, uid, obj.id, _(SHORT_SHELF_LIFE_MESS))
        
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
                self.log(cr, uid, new_id, _(SHORT_SHELF_LIFE_MESS))
                
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
        assetId = partial_datas.get('move%s'%(move.id), False).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})
        
        return defaults


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
    
    def _check_batch_management(self, cr, uid, ids, context=None):
        """
        check for batch management
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                if move.product_id.batch_management:
                    if not move.prodlot_id:
                        return False
        return True
    
    def _check_perishable(self, cr, uid, ids, context=None):
        """
        check for perishable
        @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                if move.product_id.perishable:
                    if not move.prodlot_id:
                        return False
        return True
    
    def _get_checks_batch(self, cr, uid, ids, name, arg, context=None):
        '''
        todo should be merged with 'multi'
        '''
        result = {}
        for id in ids:
            result[id] = False
            
        for move in self.browse(cr, uid, ids, context=context):
            if move.product_id:
                result[move.id] = move.product_id.batch_management
            
        return result
        
    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='KC/DG', type='char'),
                'batch_number_check': fields.function(_get_checks_batch, method=True, string='Batch Number Check', type='boolean', readonly=True),}
    _constraints = [
                    (_check_batch_management,
                     'You must assign a Batch Number for this product (Batch Number Mandatory)',
                     ['prodlot_id']),
                    (_check_perishable,
                     'You must assign an Expiry Date for this product (Expiry Date Mandatory)',
                     ['prodlot_id'])]

stock_move()


class stock_production_lot(osv.osv):
    '''
    productin lot modifications
    '''
    _inherit = 'stock.production.lot'
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        increase the batch number
        create a new sequence
        '''
        if default is None:
            default = {}
        
        default.update(name='', date=time.strftime('%Y-%m-%d'))
        return super(stock_production_lot, self).copy(cr, uid, id, default, context=context)
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        clear the revisions
        '''
        if default is None:
            default = {}
        default.update(revisions=[])
        return super(stock_production_lot, self).copy_data(cr, uid, id, default, context=context)
    
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
        vals.update({'sequence_id': sequence,})
        
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
    
    def _get_stock(self, cr, uid, ids, field_name, arg, context=None):
        """ Gets stock of products for locations
        @return: Dictionary of values
        """
        if context is None:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        product_obj = self.pool.get('product.product')
            
        result = {}
        for id in ids:
            result[id] = 0.0
        
        for lot in self.browse(cr, uid, ids, context=context):
            # because the lot_id changes we have to loop one lot id at a time
            c = context.copy()
            # if you remove the coma after done, it will no longer work properly
            c.update({'what': ('in', 'out'),
                      'prodlot_id': lot.id,
                      #'to_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                      #'warehouse': warehouse_id,
                      #'uom': product_uom_id
                      })
            
            if field_name == 'stock_available':
                # available stock
                c.update(states=('confirmed','waiting','assigned','done'))
            elif field_name == 'stock_real':
                # real stock
                c.update(states=('done',))
            else:
                assert False, 'This line should not be reached: field_name: %s'%field_name
            
            qty = product_obj.get_product_available(cr, uid, [lot.product_id.id], context=c)
            overall_qty = sum(qty.values())
            result[lot.id] = overall_qty
        
        return result
    
    _columns = {'check_type': fields.function(_get_false, fnct_search=search_check_type, string='Check Type', type="boolean", readonly=True, method=True),
                'type': fields.selection([('standard', 'Standard'),('internal', 'Internal'),], string="Type"),
                #'expiry_date': fields.date('Expiry Date'),
                'name': fields.char('Batch Number', size=1024, required=True, help="Unique production lot, will be displayed as: PREFIX/SERIAL [INT_REF]"),
                'date': fields.datetime('Auto Creation Date', required=True),
                'sequence_id': fields.many2one('ir.sequence', 'Lot Sequence', required=True,),
                'stock_available': fields.function(_get_stock, method=True, type="float", string="Available", select=True,
                                                   help="Current quantity of products with this Production Lot Number available in company warehouses",
                                                   digits_compute=dp.get_precision('Product UoM'), readonly=True,),
                'stock_real': fields.function(_get_stock, method=True, type="float", string="Real", select=True,
                                                   help="Current quantity of products with this Production Lot Number available in company warehouses",
                                                   digits_compute=dp.get_precision('Product UoM'), readonly=True,),}
    
    _defaults = {'type': 'standard',
                 'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'stock.production.lot', context=c),
                 'name': '',
                 'life_date':time.strftime('%Y-%m-%d')}
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Batch Number must be unique !'),
    ]
    
    def search(self, cr, uid, args=[], offset=0, limit=None, order=None, context={}, count=False):
        '''
        search function of production lot
        '''
        result = super(stock_production_lot, self).search(cr, uid, args, offset, limit, order, context, count)
        
        return result
    
    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'prefix', 'ref'], context)
        res = []
        for record in reads:
            name = record['name']
            res.append((record['id'], name))
        return res
    
stock_production_lot()

class stock_production_lot_revision(osv.osv):
    _inherit = 'stock.production.lot.revision'
    _order = 'indice desc'
    
stock_production_lot_revision()
