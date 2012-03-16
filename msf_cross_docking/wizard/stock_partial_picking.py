
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
    Enables to choose the location of incoming shipment
    """
    _inherit = "stock.partial.picking"

    _columns = {
        'process_type': fields.selection([
            ('to_cross_docking', 'To Cross Docking'),
            ('to_stock', 'To Stock')], string="Process Type", required=True, readonly=False),
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
            if 'process_type' in fields:
                for pick in pick_obj.browse(cr, uid, obj_ids, context=context):
                    if pick.purchase_id.cross_docking_ok == True:
                       res.update({'process_type':'to_cross_docking'})
                    elif pick.purchase_id.cross_docking_ok == False:
                        res.update({'process_type':'to_stock'})
        return res

    def onchange_process_type(self, cr, uid, ids, process_type, context=None):
        """ Raise a message if the user change a default process type (cross docking or IN stock).
        @param process_type: Changed value of process_type.
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
            if process_type != 'to_cross_docking'and pick.purchase_id.cross_docking_ok :
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('You want to receive the IN on an other location than Cross Docking but "Cross docking" was checked.')}
            elif process_type == 'to_cross_docking'and not pick.purchase_id.cross_docking_ok :
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('You want to receive the IN on Cross Docking but "Cross docking" was not checked.')}
            return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add the field 'process_type' for the wizard 'incoming shipment' only
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
                '<group col="4" colspan="4"><field name="process_type" invisible="0" on_change="onchange_process_type(process_type,context)"/>')
        return res

stock_partial_picking()
