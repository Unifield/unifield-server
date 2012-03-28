# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2012 MSF, TeMPO Consulting, Smile.
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

class create_picking(osv.osv_memory):
    _inherit = "create.picking"
    """
        Add the option cross docking for incoming shipment from "picking ticket"
    """

    _columns = {
        'source_type': fields.selection([
            ('from_cross_docking', 'From Cross Docking'),
            ('from_stock', 'From stock'),
            ('default', 'Default'),], string="Source Type", readonly=False, help="Change the delivery process. At the end, it will simply change the source location of the delivery. \"Default\" do not change anything"),
    }

#    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
#        '''
#        generates the xml view by adding the cross docking option
#        '''
#        res = super(create_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
#        # integrity check
#        assert context, 'No context defined'
#        # call super
#        result = super(create_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
#        # working objects
#        pick_obj = self.pool.get('stock.picking')
#        picking_ids = context.get('active_ids', False)
#        assert 'step' in context, 'No step defined in context'
#        step = context['step']
#
#        if not picking_ids:
#            # not called through an action (e.g. buildbot), return the default.
#            return result
#        
#        # get picking subtype
#        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
#            picking_subtype = pick.subtype
#        if picking_subtype == 'picking':
#            if step in ['create', 'validate', 'returnproducts']:
#                res['arch'] = res['arch'].replace(
#                    '<group col="4" colspan="2">',
#                    '<group col="6" colspan="4"><field name="source_type" invisible="0" required="0"/>')
#                return res

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
        res = super(create_picking, self).default_get(cr, uid, fields, context=context)
        obj_ids = context.get('active_ids', [])
        if not obj_ids:
            return res
        
        if context.get('active_ids', []):
            active_id = context.get('active_ids')[0]
            if 'source_type' in fields:
                res.update({'source_type':'default'})
        return res

    def do_create_picking_first_hook(self, cr, uid, context=None, *args, **kwargs):
        # call to super
        partial_datas = super(create_picking, self).do_create_picking_first_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        move = kwargs.get('move')
        if context is None:
            context = {}
        picking_ids = context.get('active_ids', False)
        wiz_ids = context.get('wizard_ids')
        if not wiz_ids:
            return res
        create_picking_obj = self.pool.get('create.picking')
        pick_obj = self.pool.get('stock.picking')

 # ------ referring to locations 'cross docking' and 'stock'-------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        stock_location_output = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_output')[1]
 # ----------------------------------------------------------------------------------------------------------------

        for var in create_picking_obj.browse(cr, uid, wiz_ids, context=context):
            if var.source_type == 'from_cross_docking' :
                # below, "dest_type" is only used for the incoming shipment. We set it to "None" because by default it is "default"and we do not want that info on outgoing shipment
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    dic1 = partial_datas[pick.id]
                    dic2 = dic1[move.move_id.id]
                    for move in dic2:
                        move.update({'location_id':cross_docking_location,})
            elif var.source_type == 'from_stock' :
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    dic1 = partial_datas[pick.id]
                    dic2 = dic1[move.move_id.id]
                    for move in dic2:
                        move.update({'location_id':stock_location_output,})
            elif var.source_type != None :
                var.dest_type = None
        return partial_datas

    def do_validate_picking_first_hook(self, cr, uid, context=None, *args, **kwargs):
        # call to super
        partial_datas = super(create_picking, self).do_validate_picking_first_hook(cr, uid, context, *args, **kwargs)
        assert partial_datas, 'partial_datas missing'
        move = kwargs.get('move')
        if context is None:
            context = {}
        picking_ids = context.get('active_ids', False)
        wiz_ids = context.get('wizard_ids')
        if not wiz_ids:
            return res
        create_picking_obj = self.pool.get('create.picking')
        pick_obj = self.pool.get('stock.picking')

 # ------ referring to locations 'cross docking' and 'stock'-------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        stock_location_output = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_output')[1]
 # ----------------------------------------------------------------------------------------------------------------

        for var in create_picking_obj.browse(cr, uid, wiz_ids, context=context):
            if var.source_type == 'from_cross_docking' :
                # below, "dest_type" is only used for the incoming shipment. We set it to "None" because by default it is "default"and we do not want that info on outgoing shipment
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    dic1 = partial_datas[pick.id]
                    dic2 = dic1[move.move_id.id]
                    for move in dic2:
                        move.update({'location_id':cross_docking_location,})
            elif var.source_type == 'from_stock' :
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    dic1 = partial_datas[pick.id]
                    dic2 = dic1[move.move_id.id]
                    for move in dic2:
                        move.update({'location_id':stock_location_output,})
            elif var.source_type != None :
                var.dest_type = None
        return partial_datas

create_picking()