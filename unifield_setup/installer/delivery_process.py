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
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        setup_obj = self.pool.get('unifield.setup.configuration')
        
        res = super(delivery_process_setup, self).default_get(cr, uid, fields, context=context)
        
        setup_ids = setup_obj.search(cr, uid, [], context=context)
        if not setup_ids:
            setup_ids = [setup_obj.create(cr, uid, {}, context=context)]
            
        setup_id = setup_obj.browse(cr, uid, setup_ids[0], context=context)
        
        res['delivery_process'] = setup_id.delivery_process
        
        return res
        
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        data_obj = self.pool.get('ir.model.data')
        
        setup_ids = setup_obj.search(cr, uid, [], context=context)
        if not setup_ids:
            setup_ids = [setup_obj.create(cr, uid, {}, context=context)]
            
        # Get all menu ids concerned by this modification
        picking_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_picking_ticket')[1]
        pre_packing_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_ppl')[1]
        pack_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_pack_type_tree')[1]
        packing_menu_id = data_obj.get_object_reference(cr, uid, 'msf_outgoing', 'menu_action_shipment')[1]
        
        menu_ids = [picking_menu_id, 
                    pre_packing_menu_id, 
                    pack_menu_id, 
                    packing_menu_id]
            
        if payload.delivery_process == 'simple':
            # In simple configuration, remove the menu entries
            self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': False}, context=context)
        else:
            # In complex configuration, added the menu entries
            self.pool.get('ir.ui.menu').write(cr, uid, menu_ids, {'active': True}, context=context)
    
        setup_obj.write(cr, uid, setup_ids, {'delivery_process': payload.delivery_process}, context=context)

        
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