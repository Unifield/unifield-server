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
        assetId = partial_datas.get('move%s'%(move.id), False).get('asset_id')
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
        create function clears prodlot if not (batch_number_check or expiry_date_check)
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if not(product.batch_management or product.perishable):
                vals.update(prodlot_id=False)
        
        result = super(stock_move, self).create(cr, uid, vals, context=context)
        return result
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        write function clears prodlot if not (batch_number_check or expiry_date_check)
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if not(product.batch_management or product.perishable):
                vals.update(prodlot_id=False)
        
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
        get values
        '''
        result = {}
        for id in ids:
            result[id] = {'batch_number_check': False,
                          'expiry_date_check': False,
                          }
            
        for move in self.browse(cr, uid, ids, context=context):
            if move.product_id:
                result[move.id] = {'batch_number_check': move.product_id.batch_management,
                                   'expiry_date_check': move.product_id.perishable,
                                   }
            
        return result
    
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False, loc_dest_id=False, address_id=False):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = super(stock_move, self).onchange_product_id(cr, uid, ids, prod_id, loc_id,
                                                             loc_dest_id, address_id)
        
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['prodlot_id'] = False
        # reset the hidden flag
        result.setdefault('value', {})['hidden_prod_mandatory'] = False
        if prod_id:
            product = self.pool.get('product.product').browse(cr, uid, prod_id)
            if product.batch_management:
                result.setdefault('value', {})['hidden_prod_mandatory'] = True
                result['warning'] = {'title': _('Warning'),
                                     'message': _('The selected product is Batch Management.')}
            
            elif product.perishable:
                result.setdefault('value', {})['hidden_prod_mandatory'] = True
                result['warning'] = {'title': _('Warning'),
                                     'message': _('The selected product is Perishable.')}
            
        return result
    
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
            
        return result
        
    _columns = {'kc_dg': fields.function(_kc_dg, method=True, string='KC/DG', type='char'),
                'batch_number_check': fields.function(_get_checks_batch, method=True, string='Batch Number Check', type='boolean', readonly=True, multi='vals_get',),
                'expiry_date_check': fields.function(_get_checks_batch, method=True, string='Expiry Date Check', type='boolean', readonly=True, multi='vals_get',),
                # if prodlot needs to be mandatory, add 'required': [('hidden_prod_mandatory','=',True)] in attrs
                'hidden_prod_mandatory': fields.boolean(string='Hidden Flag for Prod lot and expired date',),
                'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
                'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
                'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
                'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
                }
    
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
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Correct fields in order to have those from account_statement_from_invoice_lines (in case where account_statement_from_invoice is used)
        """
        if context is None:
            context = {}
        # warehouse wizards or inventory screen
        if view_type == 'tree' and ((context.get('expiry_date_check', False) and not context.get('batch_number_check', False)) or context.get('hidden_perishable_mandatory')):
            view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'specific_rules', 'view_production_lot_expiry_date_tree')
            if view:
                view_id = view[1]
        result = super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return result
    
    def copy(self, cr, uid, id, default=None, context=None):
        '''
        increase the batch number
        create a new sequence
        '''
        if default is None:
            default = {}
        
        default.update(name='new code', date=time.strftime('%Y-%m-%d'))
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
        if isinstance(ids, (int, long)):
            ids = [ids]
        
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
                                                   digits_compute=dp.get_precision('Product UoM'), readonly=True,),
                'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
                'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
                'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
                'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
                }
    
    _defaults = {'type': 'standard',
                 'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'stock.production.lot', context=c),
                 'name': 'new code',
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


class stock_inventory(osv.osv):
    '''
    override the action_confirm to create the production lot if needed
    '''
    _inherit = 'stock.inventory'
    
    def action_confirm(self, cr, uid, ids, context=None):
        '''
        if the line is perishable without prodlot, we create the prodlot
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        # treat the needed production lot
        for obj in self.browse(cr, uid, ids, context=context):
            for line in obj.inventory_line_id:
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
    
    def change_lot(self, cr, uid, id, prod_lot_id, context=None):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        
        if prod_lot_id:
            result['value'].update(expiry_date=prodlot_obj.browse(cr, uid, prod_lot_id, context).life_date)
        else:
            result['value'].update(expiry_date=False)
        
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
            
        return result
    
    _columns = {'hidden_perishable_mandatory': fields.boolean(string='Hidden Flag for Perishable product',),
                'hidden_batch_management_mandatory': fields.boolean(string='Hidden Flag for Batch Management product',),
                'expiry_date': fields.date(string='Expiry Date'),
                'type_check': fields.char(string='Type Check', size=1024,),
                'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
                'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
                'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
                'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
                }
    
    _defaults = {# in is used, meaning a new prod lot will be created if the specified expiry date does not exist
                 'type_check': 'in',
                 }
    
    def on_change_product_id(self, cr, uid, ids, location_id, product, uom=False, to_date=False):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = super(stock_inventory_line, self).on_change_product_id(cr, uid, ids, location_id, product, uom, to_date)
        
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['prod_lot_id'] = False
        result.setdefault('value', {})['expiry_date'] = False
        # reset the flags
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        if product:
            product_obj = self.pool.get('product.product').browse(cr, uid, product)
            if product_obj.batch_management:
                result.setdefault('value', {})['hidden_batch_management_mandatory'] = True
            elif product_obj.perishable:
                result.setdefault('value', {})['hidden_perishable_mandatory'] = True
            
        return result
    
    def create(self, cr, uid, vals, context=None):
        '''
        create function clears prodlot if not (batch_number_check or expiry_date_check)
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if not(product.batch_management or product.perishable):
                vals.update(prod_lot_id=False)
                
        prodlot_obj = self.pool.get('stock.production.lot')
        if vals.get('prod_lot_id', False) and not vals.get('expiry_date', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prod_lot_id'), context=context).life_date)
        
        result = super(stock_inventory_line, self).create(cr, uid, vals, context=context)
        return result
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        write function clears prodlot if not (batch_number_check or expiry_date_check)
        '''
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id', False):
            product = prod_obj.browse(cr, uid, vals.get('product_id'), context=context)
            if not(product.batch_management or product.perishable):
                vals.update(prod_lot_id=False)
                
        prodlot_obj = self.pool.get('stock.production.lot')
        if vals.get('prod_lot_id', False) and not vals.get('expiry_date', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prod_lot_id'), context=context).life_date)
        
        result = super(stock_inventory_line, self).write(cr, uid, ids, vals, context=context)
        return result

stock_inventory_line()
