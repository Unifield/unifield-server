# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class stock_partial_move_memory_out(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    
    def create(self, cr, uid, vals, context=None):
        '''
        if a production lot is specified and the expired date is empty, fill the expired date in
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        
        if vals.get('prodlot_id', False) and not vals.get('expiry_date', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prodlot_id'), context=context).life_date)
        
        return super(stock_partial_move_memory_out, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        if a production lot is specified and the expired date is empty, fill the expired date in
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')

        if isinstance(ids, (int, long)):
            ids = [ids]
        
        if vals.get('prodlot_id', False) and not vals.get('expiry_date', False):
            vals.update(expiry_date=prodlot_obj.browse(cr, uid, vals.get('prodlot_id'), context=context).life_date)

#----------------------------------------------------------------------------------

        # UF-2213: JF: PLEASE REMOVE THE FOLLOWING BLOCK OF CODE, REASON: Now when modifying an IN line, the "cost" is also editable, so the value 
        # in this field is passed into the vals, and we don't need to convert to the relevant UOM anymore!
        

#        if vals.get('product_uom', False):
#            mem_move = self.browse(cr, uid, ids[0], context=context)
#            if mem_move.move_id.picking_id.type == 'in':
#                # UTP-220: Give the possibility to change the cost when receiving the goods, so we need to take this cost into account
#                # but if the cost is not available, then just take the cost from the PO/original move
#                cost = vals.get('cost', mem_move.cost)
#                vals['cost'] = uom_obj._compute_price(cr, uid, mem_move.product_uom.id, cost, to_uom_id=vals.get('product_uom', mem_move.product_uom.id))

#----------------------------------------------------------------------------------
        
        return super(stock_partial_move_memory_out, self).write(cr, uid, ids, vals, context=context)
    
    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        '''
        out memory moves
        compute function fields
        '''
        result = {}
        for id in ids:
            result[id] = {}
            for f in name:
                result[id].update({f: False})
            
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id:
                result[obj.id]['batch_number_check'] = obj.product_id.batch_management
                result[obj.id]['expiry_date_check'] = obj.product_id.perishable
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
            # type of picking
            result[obj.id]['type_check'] = obj.move_id.type
            # lot management
            if obj.product_id.batch_management:
                result[obj.id]['lot_check'] = True
            # expiry date management
            if obj.product_id.perishable:
                result[obj.id]['exp_check'] = True
            
        return result

    def onchange_uom_qty(self, cr, uid, ids, product_uom, quantity):
        '''
        Check the round of the qty according to the UoM
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        new_qty = self.pool.get('product.uom')._change_round_up_qty(cr, uid, product_uom, quantity, 'quantity')

        for mem_move in self.browse(cr, uid, ids):
            cost = self.pool.get('product.uom')._compute_price(cr, uid, mem_move.product_uom.id, mem_move.cost, to_uom_id=product_uom)
            new_qty.setdefault('value', {}).setdefault('cost', cost)

        return new_qty
    
    def change_lot(self, cr, uid, id, prodlot_id, qty=0.00, location_id=False, product_uom=False, context=None):
        '''
        prod lot changes, update the expiry date
        '''
        if not context:
            context = {}

        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}, 'warning': {}}

        result = self.pool.get('product.uom')._change_round_up_qty(cr, uid, product_uom, qty, 'quantity')

        qty = result.get('value', {}).get('quantity', 0.00)

        if prodlot_id:
            c = context.copy()
            if location_id:
                c.update({'location_id': location_id})
            lot = prodlot_obj.browse(cr, uid, prodlot_id, c)
            result['value'].update(expiry_date=lot.life_date)
            if qty and lot.stock_available < qty:
                result['warning'].update({'title': _('Quantity error'),
                                          'message': _('The quantity to process is larger than the available quantity in Batch %s') % lot.name})
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
                    result['value'].update(prodlot_id=False)
                else:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('The selected Expiry Date does not exist in the system.')}
                    # clear date
                    result['value'].update(expiry_date=False, prodlot_id=False)
            else:
                # return first prodlot
                result['value'].update(prodlot_id=prod_ids[0])
                
        else:
            # clear expiry date, we clear production lot
            result['value'].update(prodlot_id=False)
        
        return result
    
    _columns = {
        'batch_number_check': fields.function(_get_checks_all, method=True, string='Batch Number Check', type='boolean', readonly=True, multi="m"),
        'expiry_date_check': fields.function(_get_checks_all, method=True, string='Expiry Date Check', type='boolean', readonly=True, multi="m"),
        'type_check': fields.function(_get_checks_all, method=True, string='Picking Type Check', type='char', readonly=True, multi="m"),
        'expiry_date': fields.date('Expiry Date'),
        'kc_check': fields.function(_get_checks_all, method=True, string='KC', type='boolean', readonly=True, multi="m"),
        'ssl_check': fields.function(_get_checks_all, method=True, string='SSL', type='boolean', readonly=True, multi="m"),
        'dg_check': fields.function(_get_checks_all, method=True, string='DG', type='boolean', readonly=True, multi="m"),
        'np_check': fields.function(_get_checks_all, method=True, string='NP', type='boolean', readonly=True, multi="m"),
        'lot_check': fields.function(_get_checks_all, method=True, string='B.Num', type='boolean', readonly=True, multi="m"),
        'exp_check': fields.function(_get_checks_all, method=True, string='Exp', type='boolean', readonly=True, multi="m"),
        'location_id': fields.related('move_id', 'location_id', type='many2one', relation='stock.location', string='Source Location', readonly=True),
        'quantity_ordered': fields.float('Quantity ordered'),
        'uom_ordered': fields.many2one('product.uom', string='UoM ordered', readonly=True),
        'uom_category': fields.related('uom_ordered', 'category_id', type='many2one', relation='product.uom.categ'),
    }

stock_partial_move_memory_out()

    
class stock_partial_move_memory_in(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    _name = "stock.move.memory.in"

stock_partial_move_memory_in()


class stock_partial_move(osv.osv_memory):
    _inherit = "stock.partial.move"
    
    def __create_partial_move_memory(self, move):
        '''
        add the expiry date (expired_date is a function at stock.move level)
        '''
        move_memory = super(stock_partial_move, self).__create_partial_move_memory(move)
        assert move_memory is not None
        
        move_memory.update({'expiry_date' : move.expired_date})
        
        return move_memory
    
    def do_partial_hook(self, cr, uid, context, *args, **kwargs):
        '''
        add hook to do_partial
        
        TODO: this functionality has not been tested because the
        partial reception with buttons on stock move level is
        disabled or does not exist
        '''
        # call to super
        partial_datas = super(stock_partial_move, self).do_partial_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        
        prodlot_obj = self.pool.get('stock.production.lot')
        
        move = kwargs.get('move')
        assert move, 'move is missing'
        p_moves = kwargs.get('p_moves')
        assert p_moves, 'p_moves is missing'

        # if only expiry date mandatory, and not batch management
        if p_moves[move.id].expiry_date_check and not p_moves[move.id].batch_number_check:        
            # if no production lot
            if not p_moves[move.id].prodlot_id:
                if p_moves[move.id].expiry_date:
                    # if it's a incoming shipment
                    if p_moves[move.id].type_check == 'in':
                        # double check to find the corresponding prodlot
                        prodlot_ids = prodlot_obj.search(cr, uid, [('life_date', '=', p_moves[move.id].expiry_date),
                                                                    ('type', '=', 'internal'),
                                                                    ('product_id', '=', p_moves[move.id].product_id)], context)
                        # no prodlot, create a new one
                        if not prodlot_ids:
                            vals = {'product_id': p_moves[move.id].product_id,
                                    'life_date': p_moves[move.id].expiry_date,
                                    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'),
                                    'type': 'internal',
                                    }
                            prodlot_id = prodlot_obj.create(cr, uid, vals, context)
                        else:
                            prodlot_id = prodlot_ids[0]
                        # assign the prod lot to partial_datas
                        partial_datas['move%s' % (move.id)].update({'prodlot_id': prodlot_id,})
                    else:
                        # should not be reached thanks to UI checks
                        raise osv.except_osv(_('Error !'), _('No Batch Number with Expiry Date for Expiry Date Mandatory and not Incoming Shipment should not happen. Please hold...'))
        
        return partial_datas

stock_partial_move()
