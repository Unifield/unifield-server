# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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
import time
import netsvc
import decimal_precision as dp
from datetime import datetime, timedelta

from msf_outgoing import INTEGRITY_STATUS_SELECTION

class process_to_consume(osv.osv_memory):
    '''
    substitute wizard
    '''
    _name = "process.to.consume"
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        fill the lines with default values:
        - context contains to_consume_id, only the selected line
        - context does not contain to_consume_id, all existing to_consume lines from the kit_creation object
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        kit_creation_obj = self.pool.get('kit.creation')
        res = super(process_to_consume, self).default_get(cr, uid, fields, context=context)
        kit_creation_ids = context.get('active_ids', False)
        if not kit_creation_ids:
            return res

        result = []
        for obj in kit_creation_obj.browse(cr, uid, kit_creation_ids, context=context):
            for item in obj.to_consume_ids_kit_creation:
                values = {}
                result.append(values)
                result.append(self.__create_partial_picking_memory(m, pick_type))

        if 'product_moves_in' in fields:
            res.update({'product_moves_in': result})
        if 'product_moves_out' in fields:
            res.update({'product_moves_out': result})
        if 'date' in fields:
            res.update({'date': time.strftime('%Y-%m-%d %H:%M:%S')})
        return res
        
    _columns = {'kit_id': fields.many2one('composition.kit', string='Substitute Items from Composition List', readonly=True),
                'wizard_id': fields.integer(string='Wizard Id', readonly=True),
                'destination_location_id': fields.many2one('stock.location', string='Destination Location', domain=[('usage', '=', 'internal')], required=True),
                'composition_item_ids': fields.many2many('substitute.item.mirror', 'substitute_items_rel', 'wizard_id', 'item_id', string='Items to replace'),
                'replacement_item_ids': fields.one2many('substitute.item', 'wizard_id', string='Replacement items'),
                }
    
    def _get_default_location(self, cr, uid, context=None):
        '''
        get the default location (stock of first warehouse)
        '''
        # objects
        wh_obj = self.pool.get('stock.warehouse')
        ids = wh_obj.search(cr, uid, [], context=context)
        if ids:
            return wh_obj.browse(cr, uid, ids[0], context=context).lot_stock_id.id
        return False
    
    _defaults = {'kit_id': lambda s, cr, uid, c: c.get('kit_id', False),
                 'destination_location_id': _get_default_location,
                 }

process_to_consume()


class process_to_consume_lines(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'process.to.consume.lines'
    
    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_id_substitute_item'):
                    data = prodlot_obj.read(cr, uid, [vals.get('lot_id_substitute_item')], ['life_date'], context=context)
                    expired_date = data[0]['life_date']
                    vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, exp and lot are False
                    vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, exp and lot are set to False
                vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item, self).create(cr, uid, vals, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_id_substitute_item'):
                    data = prodlot_obj.read(cr, uid, [vals.get('lot_id_substitute_item')], ['life_date'], context=context)
                    expired_date = data[0]['life_date']
                    vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, exp and lot are False
                    vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, exp and lot are set to False
                vals.update(lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item, self).write(cr, uid, ids, vals, context=context)
    
    def common_on_change(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, result=None, context=None):
        '''
        commmon qty computation
        '''
        if context is None:
            context = {}
        if result is None:
            result = {}
        if not product_id or not location_id:
            result.setdefault('value', {}).update({'qty_substitute_item': 0.0, 'hidden_stock_available': 0.0})
            return result
        
        # objects
        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        # corresponding product object
        product_obj = prod_obj.browse(cr, uid, product_id, context=context)
        # uom from product is taken by default if needed
        uom_id = uom_id or product_obj.uom_id.id
        # we do not want the children location
        stock_context = dict(context, compute_child=False)
        # we check for the available qty (in:done, out: assigned, done)
        res = loc_obj._product_reserve_lot(cr, uid, [location_id], product_id, uom_id, context=stock_context, lock=True)
        if prodlot_id:
            # if a lot is specified, we take this specific qty info - the lot may not be available in this specific location
            qty = res[location_id].get(prodlot_id, False) and res[location_id][prodlot_id]['total'] or 0.0
        else:
            # otherwise we take total according to the location
            qty = res[location_id]['total']
        # update the result
        result.setdefault('value', {}).update({'qty_substitute_item': qty,
                                               'uom_id_substitute_item': uom_id,
                                               'hidden_stock_available': qty,
                                               })
        return result
    
    def change_lot(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        # reset expiry date or fill it
        if prodlot_id:
            result['value'].update(exp_substitute_item=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
        else:
            result['value'].update(exp_substitute_item=False)
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def change_expiry(self, cr, uid, ids, expiry_date, product_id, type_check, location_id, prodlot_id, uom_id, context=None):
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
                    result['value'].update(lot_id_substitute_item=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(exp_substitute_item=False, lot_id_substitute_item=False)
            else:
                # return first prodlot
                prodlot_id = prod_ids[0]
                result['value'].update(lot_id_substitute_item=prodlot_id)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_id_substitute_item=False,
                                   exp_substitute_item=False,
                                   )
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def on_change_location_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        """ 
        location changes
        """
        result = {}
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def on_change_product_id(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        the product changes, set the hidden flag if necessary
        '''
        result = {}
        # product changes, prodlot is always cleared
        result.setdefault('value', {})['lot_id_substitute_item'] = False
        result.setdefault('value', {})['exp_substitute_item'] = False
        # clear uom
        result.setdefault('value', {})['uom_id_substitute_item'] = False
        # reset the hidden flags
        result.setdefault('value', {})['hidden_batch_management_mandatory'] = False
        result.setdefault('value', {})['hidden_perishable_mandatory'] = False
        if product_id:
            product_obj = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            # set the default uom
            uom_id = product_obj.uom_id.id
            result.setdefault('value', {})['uom_id_substitute_item'] = uom_id
            result.setdefault('value', {})['hidden_batch_management_mandatory'] = product_obj.batch_management
            result.setdefault('value', {})['hidden_perishable_mandatory'] = product_obj.perishable
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            # batch management
            result[obj.id].update({'hidden_batch_management_mandatory': obj.product_id_substitute_item.batch_management})
            # perishable
            result[obj.id].update({'hidden_perishable_mandatory': obj.product_id_substitute_item.perishable})
        return result
    
    _columns = {'integrity_status': fields.selection(string=' ', selection=INTEGRITY_STATUS_SELECTION, readonly=True),
                'wizard_id': fields.many2one('substitute', string='Substitute wizard'),
                'location_id_substitute_item': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                'module_substitute_item': fields.char(string='Module', size=1024),
                'product_id_substitute_item': fields.many2one('product.product', string='Product', required=True),
                'qty_substitute_item': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_substitute_item': fields.many2one('product.uom', string='UoM', required=True),
                'lot_id_substitute_item': fields.many2one('stock.production.lot', string='Batch Nb'),
                'exp_substitute_item': fields.date(string='Expiry Date'),
                'type_check': fields.char(string='Type Check', size=1024,),
                'hidden_stock_available': fields.float(string='Available Stock', digits_compute=dp.get_precision('Product UoM'), invisible=True),
                # functions
                'hidden_perishable_mandatory': fields.function(_vals_get, method=True, type='boolean', string='Exp', multi='get_vals', store=False, readonly=True),
                'hidden_batch_management_mandatory': fields.function(_vals_get, method=True, type='boolean', string='B.Num', multi='get_vals', store=False, readonly=True),
                }
    
    _defaults = {# in is used, meaning a new prod lot will be created if the specified expiry date does not exist
                 'type_check': 'out',
                 'hidden_stock_available': 0.0,
                 'integrity_status': 'empty',
                 }
    
process_to_consume_lines()


class substitute_item_mirror(osv.osv_memory):
    '''
    substitute items
    memory trick to get modifiable mirror objects for kit item
    '''
    _name = 'substitute.item.mirror'
    _inherit = 'substitute.item'
    
    def create(self, cr, uid, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_mirror'):
                    prodlot_id = vals.get('lot_mirror')
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        data = prodlot_obj.read(cr, uid, [prodlot_id], ['life_date'], context=context)
                        expired_date = data[0]['life_date']
                        vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, mirror, exp and lot are False
                    vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, mirror, exp and lot are set to False
                vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item_mirror, self).create(cr, uid, vals, context=context)
        
    def write(self, cr, uid, ids, vals, context=None):
        '''
        force writing of expired_date which is readonly for batch management products
        '''
        # objects
        prod_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        if 'product_id_substitute_item' in vals:
            if vals['product_id_substitute_item']:
                product_id = vals['product_id_substitute_item']
                data = prod_obj.read(cr, uid, [product_id], ['perishable', 'batch_management'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if management and we have a lot_id, we fill the expiry date
                if management and vals.get('lot_mirror'):
                    prodlot_id = vals.get('lot_mirror')
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        data = prodlot_obj.read(cr, uid, [prodlot_id], ['life_date'], context=context)
                        expired_date = data[0]['life_date']
                        vals.update({'exp_substitute_item': expired_date})
                elif perishable:
                    # nothing special here
                    pass
                else:
                    # not perishable nor management, mirror, exp and lot are False
                    vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
            else:
                # product is False, mirror, exp and lot are set to False
                vals.update(lot_mirror=False, lot_id_substitute_item=False, exp_substitute_item=False)
        return super(substitute_item_mirror, self).write(cr, uid, ids, vals, context=context)
    
    def change_lot(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, context=None):
        '''
        prod lot changes, update the expiry date
        
        only available for batch management products
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        # reset expiry date or fill it
        if prodlot_id:
            prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                    ('type', '=', 'standard'),
                                                    ('product_id', '=', product_id)], context=context)
            if prod_ids:
                prodlot_id = prod_ids[0]
                result['value'].update(exp_substitute_item=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
        else:
            result['value'].update(exp_substitute_item=False)
        return result
    
    def change_expiry(self, cr, uid, ids, expiry_date, product_id, type_check, location_id, prodlot_id, uom_id, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        
        only available for perishable products
        '''
        # objects
        prodlot_obj = self.pool.get('stock.production.lot')
        prod_obj = self.pool.get('product.product')
        result = {'value':{}}
        
        if product_id:
            if expiry_date:
                # product management type
                data = prod_obj.read(cr, uid, [product_id], ['batch_management', 'perishable'], context=context)[0]
                management = data['batch_management']
                perishable = data['perishable']
                # if the product is batch management
                if management and prodlot_id:
                    # prodlot_id is here the name of the prodlot
                    # we check if we have a production lot, if yes, we check if it exists (the name is unique for a given product)
                    prod_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_id),
                                                            ('type', '=', 'standard'),
                                                            ('product_id', '=', product_id)], context=context)
                    # if it exists, we set the date
                    if prod_ids:
                        prodlot_id = prod_ids[0]
                        result['value'].update(exp_substitute_item=prodlot_obj.browse(cr, uid, prodlot_id, context=context).life_date)
                        
                elif perishable:
                    # if the product is perishable
                    prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                            ('type', '=', 'internal'),
                                                            ('product_id', '=', product_id)], context=context)
                    if not prod_ids:
                        if type_check == 'in':
                            # the corresponding production lot will be created afterwards
                            result['warning'] = {'title': _('Info'),
                                             'message': _('The selected Expiry Date does not exist in the system. It will be created during validation process.')}
                            # clear prod lot
                            result['value'].update(lot_mirror=False)
                        else:
                            # display warning
                            result['warning'] = {'title': _('Error'),
                                                 'message': _('The selected Expiry Date does not exist in the system.')}
                            # clear date
                            result['value'].update(exp_substitute_item=False, lot_mirror=False)
                    else:
                        # return first prodlot
                        prodlot_id = prod_ids[0]
                        # the lot is not displayed here, internal useless internal name for the user, lot is read only anyway for perishable products
                        #result['value'].update(lot_mirror=prodlot_id)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_mirror=False,
                                   exp_substitute_item=False,
                                   )
        return result
    
    _columns = {'item_id_mirror': fields.integer(string='Id of original Item', readonly=True),
                'kit_id_mirror': fields.many2one('composition.kit', string='Kit', readonly=True),
                'lot_mirror': fields.char(string='Batch Nb', size=1024),
                }
    
    _defaults = {'item_id_mirror': False,
                 'type_check': 'in',
                 }

substitute_item_mirror()
