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

class substitute(osv.osv_memory):
    '''
    substitute wizard
    '''
    _name = "substitute"
    
    _columns = {'kit_id': fields.many2one('composition.kit', string='Substitute Items from Composition List', readonly=True),
                'destination_location_id': fields.many2one('stock.location', string='Destination Location', domain=[('usage', '=', 'internal')], required=True),
                'composition_item_ids': fields.many2many('composition.item', 'substitute_items_rel', 'wizard_id', 'item_id', string='Items to replace'),
                'replacement_item_ids': fields.one2many('substitute.item', 'wizard_id', string='Replacement items'),
                }
    
    _defaults = {'kit_id': lambda s, cr, uid, c: c.get('kit_id', False),}

substitute()


class substitute_item(osv.osv_memory):
    '''
    substitute items
    '''
    _name = 'substitute.item'
    
    def common_on_change(self, cr, uid, ids, location_id, product_id, prodlot_id, uom_id=False, result=None, context=None):
        '''
        commmon qty computation
        '''
        if context is None:
            context = {}
        if result is None:
            result = {}
        if not product_id or not location_id:
            result.update({'qty_substitute_item': 0.0})
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
        if res:
            if prodlot_id:
                # if a lot is specified, we take this specific qty info
                qty = res[location_id][prodlot_id]['total']
            else:
                # otherwise we take total according to the location
                qty = res[location_id]['total']
            # update the result
            result.setdefault('value', {}).update({'qty_substitute_item': qty, 'uom_id_substitute_item': uom_id})
        else:
            result.setdefault('value', {}).update({'qty_substitute_item': 0.0})
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
                    result['value'].update(lot_substitute_item=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(exp_substitute_item=False, lot_substitute_item=False)
            else:
                # return first prodlot
                prodlot_id = prod_ids[0]
                result['value'].update(lot_substitute_item=prodlot_id)
        else:
            # clear expiry date, we clear production lot
            result['value'].update(lot_substitute_item=False,
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
        result.setdefault('value', {})['lot_substitute_item'] = False
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
            if product_obj.batch_management:
                result.setdefault('value', {})['hidden_batch_management_mandatory'] = True
            elif product_obj.perishable:
                result.setdefault('value', {})['hidden_perishable_mandatory'] = True
        # compute qty
        result = self.common_on_change(cr, uid, ids, location_id, product_id, prodlot_id, uom_id, result=result, context=context)
        return result
    
    _columns = {'wizard_id': fields.many2one('substitute', string='Substitute wizard'),
                'location_id_substitute_item': fields.many2one('stock.location', string='Source Location', required=True, domain=[('usage', '=', 'internal')]),
                'module_substitute_item': fields.char(string='Module', size=1024),
                'product_id_substitute_item': fields.many2one('product.product', string='Product', required=True),
                'qty_substitute_item': fields.float(string='Qty', digits_compute=dp.get_precision('Product UoM'), required=True),
                'uom_id_substitute_item': fields.many2one('product.uom', string='UoM', required=True),
                'lot_substitute_item': fields.many2one('stock.production.lot', string='Batch Nb'),
                'exp_substitute_item': fields.date(string='Expiry Date'),
                'hidden_perishable_mandatory': fields.boolean(string='Hidden Flag for Perishable product',),
                'hidden_batch_management_mandatory': fields.boolean(string='Hidden Flag for Batch Management product',),
                'type_check': fields.char(string='Type Check', size=1024,),
                'hidden_perishable_mandatory': fields.boolean(string='Hidden Flag for Perishable product',),
                'hidden_batch_management_mandatory': fields.boolean(string='Hidden Flag for Batch Management product',),
                }
    
    _defaults = {# in is used, meaning a new prod lot will be created if the specified expiry date does not exist
                 'type_check': 'out',
                 }
    
substitute_item()
