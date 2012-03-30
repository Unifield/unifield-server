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
import logging
import tools
from os import path

class purchase_order(osv.osv):
    '''
    Enables the option cross docking
    '''
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'cross_docking_ok': fields.boolean('Cross docking'),
    }

    _defaults = {
        'cross_docking_ok': False,
    }

    def onchange_cross_docking_ok(self, cr, uid, ids, cross_docking_ok, context=None):
        """ Finds location id for changed cross_docking_ok.
        @param cross_docking_ok: Changed value of cross_docking_ok.
        @return: Dictionary of values.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        if cross_docking_ok:
            l = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        elif cross_docking_ok == False:
            l = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        return {'value': {'location_id': l}}

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        if vals.get('cross_docking_ok'):
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1],})
        elif vals.get('cross_docking_ok') == False:
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1], })
        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context={}):
        obj_data = self.pool.get('ir.model.data')
        if vals.get('cross_docking_ok'):
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1],})
        elif vals.get('cross_docking_ok') == False:
            vals.update({'location_id': obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1], })
        return super(purchase_order, self).create(cr, uid, vals, context=context)
    
    def _check_cross_docking(self, cr, uid, ids, context=None):
        """
        Check that if you select cross docking, you do not have an other location than cross docking
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
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
        if isinstance(ids, (int, long)):
            ids = [ids]
        sol_obj = self.pool.get('sale.order.line')
        obj_data = self.pool.get('ir.model.data')
        procurement = kwargs['procurement']
        
        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        ids = sol_obj.search(cr, uid, [('procurement_id', '=', procurement.id)], context=context)
        if len(ids):
            values.update({'cross_docking_ok': True, 'location_id' : obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1],})
        return values  

procurement_order()

class stock_picking(osv.osv):
    '''
    do_partial(=function which is originally called from delivery_mechanism) modification 
    for the selection of the LOCATION for IN (incoming shipment) and OUT (delivery orders)
    '''
    _inherit = 'stock.picking'

    def init(self, cr):
        """
        Load msf_cross_docking_data.xml before self
        """
        if hasattr(super(stock_picking, self), 'init'):
            super(stock_picking, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        logging.getLogger('init').info('HOOK: module msf_cross_docking: loading data/msf_msf_cross_docking_data.xml')
        pathname = path.join('msf_cross_docking', 'data/msf_cross_docking_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'msf_cross_docking', file, {}, mode='init', noupdate=False)

    _columns = {
        'cross_docking_ok': fields.boolean('Cross docking'),
    }
    
    '''
    do_partial(=function which is originally called from delivery_mechanism) modification 
    for the selection of the LOCATION for IN (incoming shipment) and OUT (delivery orders)
    '''
    _inherit = 'stock.picking'

    def write(self, cr, uid, ids, vals, context=None):
        """
        Here we check if all stock move are in stock or in cross docking
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        for pick in pick_obj.browse(cr,uid,ids,context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1 :
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr,uid,[move_ids],context=context):
                        move_cross_docking_ok_value = move_obj.read(cr, uid, [move_ids], ['move_cross_docking_ok'], context=context)
                        if move.move_cross_docking_ok == True:
                            vals.update({'cross_docking_ok': True,})
                        elif move.move_cross_docking_ok == False:
                            vals.update({'cross_docking_ok': False,})
        return super(stock_picking, self).write(cr, uid, ids, vals, context=context)

    def button_cross_docking_all (self, cr, uid, ids, context=None):
        """
        set all stock moves with the source location to 'cross docking'
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        for pick in pick_obj.browse(cr,uid,ids,context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1 :
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr,uid,[move_ids],context=context):
                        move_obj.write(cr, uid, [move_ids], {'location_id': cross_docking_location, 'move_cross_docking_ok': True}, context=context)
                self.write(cr, uid, ids, {'cross_docking_ok': True}, context=context)
            else :
                raise osv.except_osv(_('Warning !'), _('Please, enter some stock moves before changing the source location to CROSS DOCKING'))
        return False

    def button_stock_all (self, cr, uid, ids, context=None):
        """
        set all stock move with the source location to 'stock'
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        stock_location_output = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        for pick in pick_obj.browse(cr,uid,ids,context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1 :
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr,uid,[move_ids],context=context):
                        move_obj.write(cr, uid, [move_ids], {'location_id': stock_location_output, 'move_cross_docking_ok': False}, context=context)
                self.write(cr, uid, ids, {'cross_docking_ok': False}, context=context)
            else :
                raise osv.except_osv(_('Warning !'), _('Please, enter some stock moves before changing the source location to STOCK'))
        return False

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
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        
        # take ids of the wizard from the context. 
        # NB: the wizard_ids is created in delivery_mechanism>delivery_mecanism.py> in the method "_stock_picking_action_process_hook"
        wiz_ids = context.get('wizard_ids')
        if not wiz_ids:
            return res
        # this will help to take ids of the stock moves (see below : move_ids)
        assert 'partial_datas' in context, 'partial datas not present in context'
        partial_datas = context['partial_datas']

# ------ referring to locations 'cross docking' and 'stock'-------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        stock_location_input = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
# ----------------------------------------------------------------------------------------------------------------
        move_obj = self.pool.get('stock.move')
        partial_picking_obj = self.pool.get('stock.partial.picking')
        stock_picking_obj = self.pool.get('stock.picking')
        
        # We browse over the wizard (stock.partial.picking)
        for var in partial_picking_obj.browse(cr, uid, wiz_ids, context=context):
            """For incoming shipment """
            # we check the dest_type for INCOMING shipment (and not the source_type which is reserved for OUTGOING shipment)
            if var.dest_type == 'to_cross_docking' :
                # below, "source_type" is only used for the outgoing shipment. We set it to "None" because by default it is "default"and we do not want that info on INCOMING shipment
                var.source_type = None
                for pick in stock_picking_obj.browse(cr, uid, ids, context=context):
                    # treat moves towards CROSS DOCKING
                    move_ids = partial_datas[pick.id].keys()
                    for move in move_obj.browse(cr, uid, move_ids, context=context):
                        values.update({'location_dest_id':cross_docking_location,})
            elif var.dest_type == 'to_stock' :
                var.source_type = None
                for pick in stock_picking_obj.browse(cr, uid, ids, context=context):
                    # treat moves towards STOCK
                    move_ids = partial_datas[pick.id].keys()
                    for move in move_obj.browse(cr, uid, move_ids, context=context):
                        values.update({'location_dest_id':stock_location_input,})
        return values
    
    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data of the current object, which is stock.picking.
        The defaults data are taken from the _do_partial_hook which is on the stock_partial_picking
        osv_memory object used for the wizard of deliveries.
        For outgoing shipment 
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'
        
        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        # location_id is equivalent to the source location: does it exist when we go through the "_do_partial_hook" in the msf_cross_docking> stock_partial_piking> "do_partial_hook"
        location_id = partial_datas.get('move%s'%(move.id), False).get('location_id')
        if location_id:
            defaults.update({'location_id': location_id})
        
        return defaults
    
stock_picking()

class stock_move(osv.osv):
    _inherit = 'stock.move'
    """
    The field below 'move_cross_docking_ok' is used solely for the view using attrs. I has been named especially 
    'MOVE_cross_docking_ok' for not being in conflict with the other 'cross_docking_ok' in the stock.picking object 
    which also uses attrs according to the value of cross_docking_ok'.
    """
    _columns = {
        'move_cross_docking_ok': fields.boolean('Cross docking'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object:
        If cross docking is checked on the purchase order, we set "cross docking" to the destination location
        else we keep the default values i.e. "Input"
        """
        default_data = super(stock_move, self).default_get(cr, uid, fields, context=context)
        if context is None:
            context = {}
        purchase_id = context.get('purchase_id', [])
        if not purchase_id:
            return default_data
        
        obj_data = self.pool.get('ir.model.data')
        purchase_browse = self.pool.get('purchase.order').browse(cr, uid, purchase_id, context=context)
        # If the purchase order linked has the option cross docking then the new created stock move should have the destination location to cross docking
        if purchase_browse.cross_docking_ok:
            default_data.update({'location_dest_id' : obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1],})
        return default_data
    
    def button_cross_docking (self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to cross docking
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        return self.write(cr, uid, ids, {'location_id': cross_docking_location, 'move_cross_docking_ok': True}, context=context)

    def button_stock (self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to stock
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        stock_location_output = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        return self.write(cr, uid, ids, {'location_id': stock_location_output, 'move_cross_docking_ok': False}, context=context)
    
stock_move()