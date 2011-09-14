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
    
    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for id in ids:
            result[id] = {'batch_number_check': False, 'expiry_date_check': False, 'type_check': False}
            
        for out in self.browse(cr, uid, ids, context=context):
            if out.product_id:
                result[out.id]['batch_number_check'] = out.product_id.batch_management
                result[out.id]['expiry_date_check'] = out.product_id.perishable
            result[out.id]['type_check'] = out.move_id.type
            
        return result
    
    def change_lot(self, cr, uid, id, prodlot_id, context=None):
        '''
        prod lot changes, update the expiry date
        '''
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        
        if prodlot_id:
            result['value'].update(expiry_date=prodlot_obj.browse(cr, uid, prodlot_id, context).life_date)
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
