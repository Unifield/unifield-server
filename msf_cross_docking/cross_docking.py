# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF, Smile
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
    
    def _check_cross_docking(self, cr, uid, ids, context=None):
        """
        Check that if you select cross docking, you do not have an other location than cross docking
        """
        if context is None:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]
        for p in self.browse(cr, uid, ids, context=context):
            if p.cross_docking_ok and p.location_id.id != cross_docking_location:
                raise osv.except_osv(_('Warning !'), _('If you tick the box \"cross docking\", you cannot have an other location than \"Cross docking\"'))
            else:
                return True

    _constraints = [
        (_check_cross_docking, 'If you tick the box \"cross docking\", you cannot have an other location than \"Cross docking\"', ['location_id']),
    ]

purchase_order()

class procurement_order(osv.osv):

    _inherit = 'procurement.order'
    
    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        When you run the scheduler and you have a sale order line with type = make_to_order,
        we modify the location_id to set 'cross docking' of the purchase order created in mirror
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
    do_partial modification for the selection of the LOCATION for incoming shipments
    '''
    _inherit = 'stock.picking'
    
    def _do_incoming_shipment_first_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        This hook refers to delivery_mechanism>delivery_mechanism.py>_do_incoming_shipment.
        It updates the location_dest_id (to cross docking or to stock) 
        of selected stock moves when the linked 'incoming shipment' is validated
        -> only related to 'in' type stock.picking
        '''
        values = super(stock_picking, self)._do_incoming_shipment_first_hook(cr, uid, ids, context=context, *args, **kwargs)
        assert values is not None, 'missing values'

        if context is None:
            context = {}
        res = {}
        
        # take ids of the wizard
        wiz_ids = context.get('wizard_ids')
        if not wiz_ids:
            return res
        # this will help to take ids of the stock moves (see below : move_ids)
        assert 'partial_datas' in context, 'partial datas not present in context'
        partial_datas = context['partial_datas']

# ------ referring to locations 'cross docking' and 'stock'-------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]
        stock_location_input = obj_data.get_object_reference(cr, uid, 'msf_profile', 'stock_location_input')[1]
# ----------------------------------------------------------------------------------------------------------------
        move_obj = self.pool.get('stock.move')
        partial_picking_obj = self.pool.get('stock.partial.picking')
        stock_picking_obj = self.pool.get('stock.picking')
        
        for var in partial_picking_obj.browse(cr, uid, wiz_ids, context=context):
            if var.process_type == 'to_cross_docking':
                for pick in stock_picking_obj.browse(cr, uid, ids, context=context):
                    # treat moves towards CROSS DOCKING
                    move_ids = partial_datas[pick.id].keys()
                    for move in move_obj.browse(cr, uid, move_ids, context=context):
                        values.update({'location_dest_id':cross_docking_location,})
            elif var.process_type == 'to_stock':
                for pick in stock_picking_obj.browse(cr, uid, ids, context=context):
                    # treat moves towards STOCK
                    move_ids = partial_datas[pick.id].keys()
                    for move in move_obj.browse(cr, uid, move_ids, context=context):
                        values.update({'location_dest_id':stock_location_input,})
        return values
    
stock_picking()