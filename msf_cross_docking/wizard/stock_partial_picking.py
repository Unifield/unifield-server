
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

from osv import fields, osv
from tools.translate import _
import time

class stock_partial_picking(osv.osv_memory):
    """
    Enables to choose the location for IN (selection of destination for incoming shipment) 
    and OUT (selection of the source for delivery orders and picking ticket)
    """
    _inherit = "stock.partial.picking"

    _columns = {
        'dest_type': fields.selection([
            ('to_cross_docking', 'To Cross Docking'),
            ('to_stock', 'To Stock'),
            ('default', 'Other Types'),], string="Destination Type", readonly=False, help="The default value is the one set on each stock move line."),
        'source_type': fields.selection([
            ('from_cross_docking', 'From Cross Docking'),
            ('from_stock', 'From stock'),
            ('default', 'Default'),
            ], string="Source Type", readonly=False),

     }

    def default_get(self, cr, uid, fields, context=None):
        """ To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}
        res = {}
        obj_data = self.pool.get('ir.model.data')
        pick_obj = self.pool.get('stock.picking')
        res = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
        obj_ids = context.get('active_ids', [])
        if not obj_ids:
            return res
        
        if context.get('active_ids', []):
            active_id = context.get('active_ids')[0]
            if 'dest_type' in fields:
                for pick in pick_obj.browse(cr, uid, obj_ids, context=context):
                    if pick.purchase_id.cross_docking_ok == True:
                       res.update({'dest_type':'to_cross_docking'})
                    elif pick.purchase_id.cross_docking_ok == False:
                        res.update({'dest_type':'to_stock'})
                    else:
                        res.update({'dest_type':'default'})
            if 'source_type' in fields:
                res.update({'source_type':'default'})
        return res

    def onchange_dest_type(self, cr, uid, ids, dest_type, context=None):
        """ Raise a message if the user change a default dest type (cross docking or IN stock).
        @param dest_type: Changed value of dest_type.
        @return: Dictionary of values.
        """
        if context is None:
            context = {}
        res = {}
        result = {'value':{}}
        
        obj_ids = context.get('active_ids', [])
        if not obj_ids:
            return res
        obj_data = self.pool.get('ir.model.data')
        pick_obj = self.pool.get('stock.picking')
        for pick in pick_obj.browse(cr, uid, obj_ids, context=context):
            if pick.purchase_id and dest_type != 'to_cross_docking'and pick.purchase_id.cross_docking_ok :
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('You want to receive the IN on an other location than Cross Docking but "Cross docking" was checked.')}
            elif pick.purchase_id and dest_type == 'to_cross_docking'and not pick.purchase_id.cross_docking_ok :
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('You want to receive the IN on Cross Docking but "Cross docking" was not checked.')}
            return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add the field 'dest_type' for the wizard 'incoming shipment' and 'delivery orders'
        '''
        res = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_id = context.get('active_ids')
        if picking_id:
            picking_id = picking_id[0]
            data = picking_obj.read(cr, uid, [picking_id], ['type'], context=context)
            picking_type = data[0]['type']
            if picking_type == 'in':
                # replace line '<group col="2" colspan="2">' for 'incoming_shipment' only to select the 'stock location' destination
                res['arch'] = res['arch'].replace(
                '<group col="2" colspan="2">',
                '<group col="4" colspan="4"><field name="dest_type" invisible="0" on_change="onchange_dest_type(dest_type,context)" required="0"/>')
            elif picking_type == 'out':
                # replace line '<group col="2" colspan="2">' for 'delivery orders' only to select the 'stock location' source
                res['arch'] = res['arch'].replace(
                '<group col="2" colspan="2">',
                '<group col="4" colspan="4"><field name="source_type" invisible="1" required="0"/>')
        return res
    
    def do_partial_hook(self, cr, uid, context=None, *args, **kwargs):
        '''
        ON OUTGOING SHIPMENT
        This hook to "do_partial" comes from stock_override>wizard>stock_partial_picking.py
        It aims to update the source location (location_id) of stock picking according to the Source that the user chooses.
        To update the stock_move values of the stock_picking object, we need to write an other hook in the stock_picking object.
        Have a look in cross_docking>cross_docking.py> the method "_do_partial_hook" on the stock_picking object
        '''

        # call to super
        partial_datas = super(stock_partial_picking, self).do_partial_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        move = kwargs.get('move')
        if context is None:
            context = {}
        picking_ids = context.get('active_ids', False)
        wiz_ids = context.get('wizard_ids')
        if not wiz_ids:
            return res
        partial_picking_obj = self.pool.get('stock.partial.picking')
        pick_obj = self.pool.get('stock.picking')

 # ------ referring to locations 'cross docking' and 'stock'-------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]
        stock_location_output = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_output')[1]
 # ----------------------------------------------------------------------------------------------------------------

        for var in partial_picking_obj.browse(cr, uid, wiz_ids, context=context):
            if var.source_type == 'from_cross_docking' :
                # below, "dest_type" is only used for the incoming shipment. We set it to "None" because by default it is "default"and we do not want that info on outgoing shipment
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    partial_datas['move%s' % (move.move_id.id)].update({
                                                    'location_id':cross_docking_location,
                                                    })
            elif var.source_type == 'from_stock' :
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    partial_datas['move%s' % (move.move_id.id)].update({
                                                'location_id' : stock_location_output,
                                                })
            elif var.source_type != None:
                var.dest_type = None
        return partial_datas

stock_partial_picking()
