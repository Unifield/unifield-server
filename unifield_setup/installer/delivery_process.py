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


class delivery_process_setup(osv.osv_memory):
    _name = 'delivery.process.setup'
    _inherit = 'res.config'
    
    _columns = {
        'delivery_process': fields.selection([('simple', 'Simple OUT'), ('complex', 'PICK/PACK/SHIP')], string='Delivery process', required=True),
    }
    
    def _check_not_done_picking(self, cr, uid):
        shipment_ids = self.pool.get('shipment').search(cr, uid, [('state', 'not in', ['delivered', 'cancel', 'done'])])
        picking_ids = self.pool.get('stock.picking').search(cr, uid, [('subtype', '!=', 'standard'), ('state', 'not in', ['cancel', 'done'])])
        
        return (picking_ids or shipment_ids) and True or False
    
    def delivery_process_on_change(self, cr, uid, ids, process, context=None):
        res = {}
        
        if process == 'simple':
            if self._check_not_done_picking(cr, uid):
                res.update({'warning': {'title': 'Warning',
                                        'message': '''You have some Picking Tickets, Packing Lists or Shipments not done or cancelled. 
So, you cannot choose 'Simple OUT' as Delivery process while these documents are not done/cancelled !'''}})
        
        return res
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(delivery_process_setup, self).default_get(cr, uid, fields, context=context)
        res['delivery_process'] = setup_id.delivery_process
        
        return res
        
    def change_wh_board(self, cr, uid, type='simple', context=None):
        '''
        Update the WH dashboard according to Delivery process choice
        '''
        module_obj = self.pool.get('ir.module.module')
        data_obj = self.pool.get('ir.model.data')

        # In simple configuration, only display OUT on WH dashboard
        module_name = 'useability_dashboard_and_menu'
        view_xml_id = 'board_warehouse_form_default'

        if type == 'simple':
            view_xml_id = 'board_warehouse_form_default_only_out'

        module_ok = module_obj.search(cr, uid, [('name', '=', module_name), ('state', '=', 'installed')], context=context)
        if module_ok:
            try:
                wh_action_id = data_obj.get_object_reference(cr, uid, module_name, 'open_board_warehouse_unifield')[1]
                wh_view_id = data_obj.get_object_reference(cr, uid, module_name, view_xml_id)[1]
                # Update the action
                self.pool.get('ir.actions.act_window').write(cr, uid, [wh_action_id], {'view_id': wh_view_id}, context=context)
            except ValueError:
                pass

        return True

    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        data_obj = self.pool.get('ir.model.data')
        
        setup_id = setup_obj.get_config(cr, uid)
            
        # Get all menu ids concerned by this modification
        picking_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_picking_ticket')[1]
        pre_packing_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_ppl')[1]
        pack_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_pack_type_tree')[1]
        packing_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_shipment')[1]
#        preparation_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_pt_ppl')[1]
        
        menu_ids = [picking_menu_id, 
                    pre_packing_menu_id, 
                    pack_menu_id,
#                    preparation_menu_id,
                    packing_menu_id]
            
        if payload.delivery_process == 'simple':
            if self._check_not_done_picking(cr, uid):
                raise osv.except_osv(_('Error'), _('''You have some Picking Tickets, Packing Lists or Shipments not done or cancelled. 
So, you cannot choose 'Simple OUT' as Delivery process while these documents are not done/cancelled !'''))
            # In simple configuration, remove the menu entries
            self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': False}, context=context)
        else:
            # In complex configuration, added the menu entries
            self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': True}, context=context)
        
        # Update the WH dashboard view
        self.change_wh_board(cr, uid, type=payload.delivery_process, context=context)
    
        setup_obj.write(cr, uid, [setup_id.id], {'delivery_process': payload.delivery_process}, context=context)

        
delivery_process_setup()


class ir_ui_menu(osv.osv):
    _name = 'ir.ui.menu'
    _inherit = 'ir.ui.menu'
    
    _columns = {
        'active': fields.boolean(string='Active'),
    }
    
    _defaults = {
        'active': lambda *a: True,
    }
    
ir_ui_menu() 
