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
        'location_id': fields.many2one('stock.location', 'Destination', required=True, domain=[('usage','<>','view')], 
        help="""This location is set according to the Warehouse selected, or according to the option 'Cross docking' 
        or freely if you do not select 'Warehouse'.But if the 'Order category' is set to 'Transport' or 'Service', 
        you cannot have an other location than 'Service'"""),
    }

    _defaults = {
        'cross_docking_ok': False,
    }
    
    def onchange_internal_type(self, cr, uid, ids, order_type, partner_id, dest_partner_id=False, warehouse_id=False):
        '''
        Changes destination location
        '''
        res = super(purchase_order, self).onchange_internal_type(cr, uid, ids, order_type, partner_id, dest_partner_id, warehouse_id)
        if order_type == 'direct':
            location_id = self.onchange_cross_docking_ok(cr, uid, ids, False, warehouse_id)['value']['location_id']
        
            if 'value' in res:
                res['value'].update({'location_id': location_id})
            else:
                res.update({'value': {'location_id': location_id}})
        
        return res

    def onchange_cross_docking_ok(self, cr, uid, ids, cross_docking_ok, warehouse_id, context=None):
        """ Finds location id for changed cross_docking_ok.
        @param cross_docking_ok: Changed value of cross_docking_ok.
        @return: Dictionary of values.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        if cross_docking_ok:
            l = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        else:
            warehouse_obj = self.pool.get('stock.warehouse')
            if not warehouse_id:
                warehouse_ids = warehouse_obj.search(cr, uid, [], limit=1)
                if not warehouse_ids:
                    return {'warning': {'title': _('Error !'), 'message': _('No Warehouse defined !')}, 'value': {'location_id': False}}
                warehouse_id = warehouse_ids[0]
            l = warehouse_obj.read(cr, uid, [warehouse_id], ['lot_input_id'])[0]['lot_input_id'][0]
        return {'value': {'location_id': l}}
    
    def onchange_location_id(self, cr, uid, ids, location_id, categ, context=None):
        """ If location_id == cross docking we tick the box "cross docking".
        @param location_id: Changed value of location_id.
        @return: Dictionary of values.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        res['value'] = {}
        obj_data = self.pool.get('ir.model.data')
        if location_id == self.pool.get('stock.location').get_cross_docking_location(cr, uid) and categ not in ['service', 'transport']:
            cross_docking_ok = True
        elif location_id != self.pool.get('stock.location').get_cross_docking_location(cr, uid):
            cross_docking_ok = False
        elif location_id != self.pool.get('stock.location').get_service_location(cr, uid) and categ in ['service', 'transport']:
            return {'warning': {'title': _('Error !'), 'message': _("""
            If the 'Order Category' is 'Service' or 'Transport', you cannot have an other location than 'Service'
            """)}, 'value': {'location_id': self.pool.get('stock.location').get_service_location(cr, uid)}}
        res['value']['cross_docking_ok'] = cross_docking_ok
        return res
    
    def onchange_warehouse_id(self, cr, uid, ids,  warehouse_id, order_type, dest_address_id):
        """ Set cross_docking_ok to False when we change warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        res = super(purchase_order, self).onchange_warehouse_id(cr, uid, ids,  warehouse_id, order_type, dest_address_id)
        if warehouse_id:
            res['value'].update({'cross_docking_ok': False})
        return res
    
    
    def onchange_categ(self, cr, uid, ids, categ, warehouse_id, cross_docking_ok, location_id, context=None):
        """ Sets cross_docking to False if the categ is service or transport.
        @param categ: Changed value of categ.
        @return: Dictionary of values.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        warehouse_obj = self.pool.get('stock.warehouse')
        value = {}
        service_loc = self.pool.get('stock.location').get_service_location(cr, uid)
        cross_loc = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        if categ in ['service', 'transport']:
            value = {'location_id': service_loc, 'cross_docking_ok': False}
        elif cross_docking_ok:
            value = {'location_id': cross_loc}
        elif location_id in (service_loc, cross_loc):
            if warehouse_id:
                value = {'location_id': warehouse_obj.read(cr, uid, [warehouse_id], ['lot_input_id'])[0]['lot_input_id'][0]}
            else:
                value = {'location_id': False}
        return {'value': value}

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if 'order_type' in vals and vals['order_type'] == 'direct':
            vals.update({'cross_docking_ok': False})
        if 'categ' in vals and vals['categ'] in ['service', 'transport']:
            vals.update({'cross_docking_ok': False, 'location_id': self.pool.get('stock.location').get_service_location(cr, uid)})
        if 'cross_docking_ok' in vals and vals['cross_docking_ok']:
            vals.update({'location_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})

        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        obj_data = self.pool.get('ir.model.data')
        if vals.get('order_type') == 'direct':
            vals.update({'cross_docking_ok': False})
        if 'categ' in vals and vals['categ'] in ['service', 'transport']:
            vals.update({'cross_docking_ok': False, 'location_id': self.pool.get('stock.location').get_service_location(cr, uid)})
        if vals.get('cross_docking_ok'):
            vals.update({'location_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})
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
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        for purchase in self.browse(cr, uid, ids, context=context):
            if purchase.cross_docking_ok and purchase.location_id.id != cross_docking_location:
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
            values.update({'cross_docking_ok': True, 'location_id' : self.pool.get('stock.location').get_cross_docking_location(cr, uid)})
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
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
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
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        for pick in pick_obj.browse(cr,uid,ids,context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1 :
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr,uid,[move_ids],context=context):
                        # Don't change done stock moves
                        if move.state != 'done':
                            move_obj.write(cr, uid, [move_ids], {'location_id': cross_docking_location, 'move_cross_docking_ok': True}, context=context)
                self.write(cr, uid, ids, {'cross_docking_ok': True}, context=context)
            else :
                raise osv.except_osv(_('Warning !'), _('Please, enter some stock moves before changing the source location to CROSS DOCKING'))
        # we check availability : cancel then check
        self.cancel_assign(cr, uid, ids)
        self.action_assign(cr, uid, ids)
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
        for pick in pick_obj.browse(cr,uid,ids,context=context):
            move_lines = pick.move_lines
            if len(move_lines) >= 1 :
                for move in move_lines:
                    move_ids = move.id
                    for move in move_obj.browse(cr,uid,[move_ids],context=context):
                        if move.state != 'done':
                            if move.product_id.type == 'consu':
                                if pick.type == 'out':
                                    id_loc_s = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking','stock_location_cross_docking')
                                else:
                                    id_loc_s = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock','stock_location_non_stockable')
                                move_obj.write(cr, uid, [move_ids], {'location_id': id_loc_s[1], 'move_cross_docking_ok': False}, context=context)
                            else:
                                move_obj.write(cr, uid, [move_ids], {'location_id': pick.warehouse_id.lot_stock_id.id, 'move_cross_docking_ok': False}, context=context)
                self.write(cr, uid, ids, {'cross_docking_ok': False}, context=context)
            else :
                raise osv.except_osv(_('Warning !'), _('Please, enter some stock moves before changing the source location to STOCK'))
        # we check availability : cancel then check
        self.cancel_assign(cr, uid, ids)
        self.action_assign(cr, uid, ids)
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
       
        # take ids of the wizard from the context. 
        # NB: the wizard_ids is created in delivery_mechanism>delivery_mecanism.py> in the method "_stock_picking_action_process_hook"
        wiz_ids = context.get('wizard_ids')
        res = {}
        if not wiz_ids:
            return res

# ------ referring to locations 'cross docking' and 'stock' ------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)
        stock_location_input = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
# ----------------------------------------------------------------------------------------------------------------
        partial_picking_obj = self.pool.get('stock.partial.picking')
        
        # We browse over the wizard (stock.partial.picking)
        for var in partial_picking_obj.browse(cr, uid, wiz_ids, context=context):
            """For incoming shipment """
            # we check the dest_type for INCOMING shipment (and not the source_type which is reserved for OUTGOING shipment)
            if var.dest_type == 'to_cross_docking':
                # below, "source_type" is only used for the outgoing shipment. We set it to "None" because by default it is "default"and we do not want that info on INCOMING shipment
                var.source_type = None
                product_id = values['product_id']
                product_type = self.pool.get('product.product').read(cr, uid, product_id, ['type'], context=context)['type']
                if product_type not in ('service_recep', 'service'):
                    # treat moves towards CROSS DOCKING if NOT SERVICE
                    values.update({'location_dest_id': cross_docking_location})
            elif var.dest_type == 'to_stock' :
                var.source_type = None
                # below, "source_type" is only used for the outgoing shipment. We set it to "None" because by default it is "default"and we do not want that info on INCOMING shipment
                product_id = values['product_id']
                product_type = self.pool.get('product.product').read(cr, uid, product_id, ['type'], context=context)['type']
                if product_type not in ('service_recep', 'service'):
                    # treat moves towards STOCK if NOT SERVICE
                    values.update({'location_dest_id': stock_location_input})
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
            default_data.update({'location_dest_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})
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
        cross_docking_location = self.pool.get('stock.location').get_cross_docking_location(cr, uid)

        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state != 'done': 
                todo.append(move.id)
        ret = True
        if todo:
            ret = self.write(cr, uid, todo, {'location_id': cross_docking_location, 'move_cross_docking_ok': True}, context=context)

            # below we cancel availability to recheck it
            stock_picking_id = self.read(cr, uid, todo, ['picking_id'], context=context)[0]['picking_id'][0]
            # we cancel availability
            self.pool.get('stock.picking').cancel_assign(cr, uid, [stock_picking_id])
            # we recheck availability
            self.pool.get('stock.picking').action_assign(cr, uid, [stock_picking_id])
        return ret

    def button_stock (self, cr, uid, ids, context=None):
        """
        for each stock move we enable to change the source location to stock
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        
        todo = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state != 'done':
                if move.product_id.type == 'consu':
                    if move.picking_id.type == 'out':
                        id_loc_s = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking','stock_location_cross_docking')
                    else:
                        id_loc_s = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock','stock_location_non_stockable')
                    self.write(cr, uid, move.id, {'location_id': id_loc_s[1], 'move_cross_docking_ok': False}, context=context)
                else:
                    self.write(cr, uid, move.id, {'location_id': move.picking_id.warehouse_id.lot_stock_id.id, 'move_cross_docking_ok': False}, context=context)
                todo.append(move.id)

        if todo:
            # below we cancel availability to recheck it
            stock_picking_id = self.read(cr, uid, todo, ['picking_id'], context=context)[0]['picking_id'][0]
            # we cancel availability
            self.pool.get('stock.picking').cancel_assign(cr, uid, [stock_picking_id])
            # we recheck availability
            self.pool.get('stock.picking').action_assign(cr, uid, [stock_picking_id])
        return True

stock_move()
