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

from osv import osv, fields
from tools.translate import _

class stock_location(osv.osv):
    '''
    override stock location to add:
    - quarantine location (checkbox - boolean)
    - destruction location (checkbox - boolean)
    - location category (selection)
    '''
    _inherit = 'stock.location'
    
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
    
    def search_check_quarantine(self, cr, uid, obj, name, args, context=None):
        '''
        modify the query to take the type of stock move into account
        
        if type is 'out', quarantine_location must be False
        '''
        move_obj = self.pool.get('stock.move')
        move_id = context.get('move_id', False)
        
        # remove flag avoid infinite loop
        self.remove_flag('check_quarantine', args)
            
        if not move_id:
            return args
        
        # check the move
        move = move_obj.browse(cr, uid, move_id, context=context)

        if move.type == 'out':
            # out -> not from quarantine
            args.append(('quarantine_location', '=', False))
            
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
    
    _columns = {'quarantine_location': fields.boolean(string='Quarantine Location'),
                'destruction_location': fields.boolean(string='Destruction Loction'),
                'location_category': fields.selection([('stock', 'Stock'),
                                                       ('consumption_unit', 'Consumption Unit'),
                                                       ('transition', 'Transition'),
                                                       ('other', 'Other'),], string='Location Category', required=True),
                # could be used after discussion with Magali
                #'check_quarantine': fields.function(_get_false, fnct_search=search_check_quarantine, string='Check Quarantine', type="boolean", readonly=True, method=True),
                }
    _defaults = { 
       'location_category': 'stock',
    }

stock_location()


class procurement_order(osv.osv):
    _inherit = 'procurement.order'

    def _do_create_proc_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # call super
        values = super(procurement_order, self)._do_create_proc_hook(cr, uid, ids, context=context, *args, **kwargs)
        # as location, we take the input of the warehouse
        op = kwargs.get('op', False)
        assert op, 'missing op'
        # update location value
        values.update(location_id=op.warehouse_id.lot_input_id.id)
        
        return values

procurement_order()
