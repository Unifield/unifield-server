# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

from osv import osv
from osv import fields
from tools.translate import _

class purchase_order(osv.osv):
    '''
    Enables the option cross docking
    '''
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'cross_docking_ok': fields.boolean('Cross docking?'),
    }

    _defaults = {
        'cross_docking_ok': False,
    }

    def onchange_cross_docking_ok(self, cr, uid, ids, cross_docking_ok, context=None):
        """ Finds location id for changed cross_docking_ok.
        @param cross_docking_ok: Changed value of cross_docking_ok.
        @return: Dictionary of values.
        """
        obj_data = self.pool.get('ir.model.data')
        if cross_docking_ok:
            l = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]
        elif cross_docking_ok == False:
            l = obj_data.get_object_reference(cr, uid, 'msf_profile', 'stock_location_input')[1]
        return {'value': {'location_id': l}}

    def write(self, cr, uid, ids, vals, context=None):
        obj_data = self.pool.get('ir.model.data')
        if vals.get('cross_docking_ok'):
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1],})
        elif vals.get('cross_docking_ok') == False:
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'msf_profile', 'stock_location_input')[1], })
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context={}):
        obj_data = self.pool.get('ir.model.data')
        if vals.get('cross_docking_ok'):
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1],})
        elif vals.get('cross_docking_ok') == False:
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'msf_profile', 'stock_location_input')[1], })
        id = super(purchase_order, self).create(cr, uid, vals, context=context)
        return id
    
purchase_order()

class procurement_order(osv.osv):
    '''
    We modify location_id in purchase order created from sale order (type = make_to_order) 
    to set 'cross docking'
    '''
    _inherit = 'procurement.order'
    
    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the make_po method from purchase>purchase.py>procurement_order
        
        - allow to modify the data for purchase order creation
        '''
        if context is None:
            context = {}
        sol_obj = self.pool.get('sale.order.line')
        obj_data = self.pool.get('ir.model.data')
        procurement = kwargs['procurement']
        
        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        ids = sol_obj.search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        if len(ids):
            values.update({'cross_docking_ok': True, 'location_id' : obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1],})
        return values  

procurement_order()

class stock_picking(osv.osv):
    '''
    do_partial modification
    '''
    _inherit = 'stock.picking'
    
#    def choose_cross_docking(self, cr, uid, ids, context=None):
#        res = []
#        if context is None:
#            context = {}
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#        obj_data = self.pool.get('ir.model.data')
#        for var in self.pool.get('stock.move').browse(cr, uid, ids, context=context):
#            if var.location_dest_id.id != obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]:
#                res = 'location_dest_id' == obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]
#        return res
#
#    def do_not_choose_cross_docking(self, cr, uid, ids, context=None):
#        res = []
#        if context is None:
#            context = {}
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#        obj_data = self.pool.get('ir.model.data')
#        
#        move_line = self.pool.get('stock.move').browse(cr, uid, ids, context=context)
#        for var in move_line.location_dest_id.id:
#            if var == obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]:
#                res = self.write(cr, uid, [move'location_dest_id': obj_data.get_object_reference(cr, uid, 'msf_profile', 'stock_location_input')[1]), context=context)
#        return res
    
    def _stock_picking_action_process_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_process method from stock>stock.py>stock_picking
        - allow to modify the data for wizard display
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = super(stock_picking, self)._stock_picking_action_process_hook(cr, uid, ids, context=context, *args, **kwargs)
        wizard_obj = self.pool.get('wizard')
        res = wizard_obj.open_wizard(cr, uid, ids, type='update', context=dict(context,
                                                                               wizard_ids=[res['res_id']],
                                                                               wizard_name=res['name'],
                                                                               model=res['res_model'],
                                                                               step='default'))
        return res
stock_picking()