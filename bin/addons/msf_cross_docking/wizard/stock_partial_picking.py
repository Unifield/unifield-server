
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF
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
# xml parser
from lxml import etree

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
            ('default', 'Other Types'), ], string="Destination Type", readonly=False, help=
            """
            The default value is the one set on each stock move line.
            """),
        'source_type': fields.selection([
            ('from_cross_docking', 'From Cross Docking'),
            ('from_stock', 'From stock'),
            ('default', 'Default'), ], string="Source Type", readonly=False),
        'direct_incoming': fields.boolean(string='Direct to Stock ?'),
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
        pick_obj = self.pool.get('stock.picking')
        res = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
        obj_ids = context.get('active_ids', [])
        if not obj_ids:
            return res

        if context.get('active_ids', []):
            if 'dest_type' in fields:
                for pick in pick_obj.browse(cr, uid, obj_ids, context=context):
                    if not pick.backorder_id:
                        if pick.purchase_id.cross_docking_ok:
                            res.update({'dest_type': 'to_cross_docking'})
                        elif pick.purchase_id.cross_docking_ok == False:
                        # take care: if pick.purchase_id.cross_docking_ok is None we shouldn't be here but in the next else block
                        # pick.purchase_id.cross_docking_ok is None if pick.purchase_id is empty
                            res.update({'dest_type': 'to_stock'})
                        else:
                            res.update({'dest_type': 'default'})
                    else:
                        if pick.cd_from_bo:
                            res.update({'dest_type': 'to_cross_docking'})
                        elif pick.cd_from_bo == False:
                            res.update({'dest_type': 'to_stock'})
                        else:
                            res.update({'dest_type': 'default'})
            
            if 'source_type' in fields:
                res.update({'source_type': 'default'})

        res.update({'direct_incoming': True})

        return res

    def onchange_dest_type(self, cr, uid, ids, dest_type, context=None):
        """ Raise a message if the user change a default dest type (cross docking or IN stock).
        @param dest_type: Changed value of dest_type.
        @return: Dictionary of values.
        """
        if context is None:
            context = {}
        res = {}
        result = {'value': {}}

        obj_ids = context.get('active_ids', [])
        if not obj_ids:
            return res
        pick_obj = self.pool.get('stock.picking')
        for pick in pick_obj.browse(cr, uid, obj_ids, context=context):
            if pick.purchase_id and dest_type != 'to_cross_docking'and pick.purchase_id.cross_docking_ok:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _("""You want to receive the IN on an other location than
                                         Cross Docking but "Cross docking" was checked.""")}
            elif pick.purchase_id and dest_type == 'to_cross_docking'and not pick.purchase_id.cross_docking_ok:
                    # display warning
                    result['warning'] = {'title': _('Error'),
                                         'message': _('You want to receive the IN on Cross Docking but "Cross docking" was not checked.')}

        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)

        if dest_type == 'to_cross_docking' and setup.allocation_setup == 'unallocated':
            result['value'].update({'dest_type': 'default'})
            result['warning'] = {'title': _('Error'),
                                 'message': _("""The Allocated stocks setup is set to Unallocated.
                                 In this configuration, you cannot made moves from/to Cross-docking locations.""")}
        return result

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add the field 'dest_type' for the wizard 'incoming shipment' and 'delivery orders'
        '''
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_id = context.get('active_ids')
        if picking_id:
            picking_id = picking_id[0]
            data = picking_obj.read(cr, uid, [picking_id], ['type'], context=context)
            picking_type = data[0]['type']
            # for both type, we add a field before the cancel button
            new_field_txt = False
            new_field_txt2 = False
            # define the new field according to picking type
            if picking_type == 'in':
                # replace line '<group col="2" colspan="2">' for 'incoming_shipment' only to select the 'stock location' destination
                new_field_txt = '<field name="dest_type" invisible="0" on_change="onchange_dest_type(dest_type,context)" required="0"/>'
                new_field_txt2 = '<field name="direct_incoming" attrs="{\'invisible\': [(\'dest_type\', \'not in\', [\'default\', \'to_stock\'])]}" />'
            elif picking_type == 'out':
                # replace line '<group col="2" colspan="2">' for 'delivery orders' only to select the 'stock location' source
                new_field_txt = '<field name="source_type" invisible="1" required="0"/>'
            # if a new field has been defined, we resize the group tag, and add the new field before cancel button
            if new_field_txt:
                # modify the group size
                # load the xml tree
                root = etree.fromstring(result['arch'])
                # xpath of fields to be modified
                list_xpath = ['//group[@col="2" and @colspan="2"]']
                group_field = False
                for xpath in list_xpath:
                    fields = root.xpath(xpath)
                    if not fields:
                        raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                    for field in fields:
                        group_field = field
                        field.set('col', '4')
                        field.set('colspan', '4')
                        if new_field_txt2:
                            field.set('col', '8')
                            list_button_xpath = ['//button[@special="cancel" or @name="do_incoming_shipment"]']
                            for bxpath in list_button_xpath:
                                buttons = root.xpath(bxpath)
                                if not buttons:
                                    raise osv.except_osv(_('Warning !'), _('Element %s not found.')%bxpath)
                                for button in buttons:
                                    button.set('colspan', '2')

                # find the cancel button
                list_xpath = ['//button[@special="cancel"]']
                fields = False
                for xpath in list_xpath:
                    fields = root.xpath(xpath)
                    if not fields:
                        raise osv.except_osv(_('Warning !'), _('Element %s not found.')%xpath)
                # cancel button index
                cancel_index = list(group_field).index(fields[0])
                # generate xml tree
                if new_field_txt2:
                    new_field2 = etree.fromstring(new_field_txt2)
                    group_field.insert(cancel_index, new_field2)
                new_field = etree.fromstring(new_field_txt)
                # insert new field at the place of cancel button
                group_field.insert(cancel_index, new_field)
                result['arch'] = etree.tostring(root)

        return result

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
        res = {}
        if not wiz_ids:
            return res
        partial_picking_obj = self.pool.get('stock.partial.picking')
        pick_obj = self.pool.get('stock.picking')

# ------ referring to locations 'cross docking' and 'stock'-------------------------------------------------------
        obj_data = self.pool.get('ir.model.data')
        cross_docking_location = obj_data.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        stock_location_output = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_output')[1]
# ----------------------------------------------------------------------------------------------------------------

        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)

        for var in partial_picking_obj.browse(cr, uid, wiz_ids, context=context):
            if var.source_type == 'from_cross_docking':
                if setup.allocation_setup == 'unallocated':
                    raise osv.except_osv(_('Error'), _("""You cannot made moves from/to Cross-docking locations when
                    the Allocated stocks configuration is set to \'Unallocated\'."""))
                # below, "dest_type" is only used for the incoming shipment. We set it to "None" because
                #by default it is "default"and we do not want that info on outgoing shipment
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    partial_datas['move%s' % (move.move_id.id)].update({'location_id': cross_docking_location})
            elif var.source_type == 'from_stock':
                var.dest_type = None
                for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
                    partial_datas['move%s' % (move.move_id.id)].update({'location_id': stock_location_output})
            elif var.source_type is not None:
                var.dest_type = None
        return partial_datas

stock_partial_picking()
