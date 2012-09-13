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


class allocation_stock_setup(osv.osv_memory):
    _name = 'allocation.stock.setup'
    _inherit = 'res.config'
    
    _columns = {
        'allocation_setup': fields.selection([('allocated', 'Allocated'),
                                              ('unallocated', 'Unallocated'),
                                              ('mixed', 'Mixed')], 
                                              # UF-1261 : As long as the Unallocated stock are not developped, user shouldn't be able to change this option
                                              readonly=True,
                                              string='Allocated stocks', required=True),
        'unallocated_ok': fields.selection([('yes', 'Yes'), ('no', 'No')], string='System will use unallocated moves on finance side ?', readonly=True),
        'error_ok': fields.boolean(string='Error'),
        'error_msg': fields.text(string='Error', readonly=True),
        'error_po_ok': fields.boolean(string='Error'),
        'error_cross_ok': fields.boolean(string='Error'),
        'error_central_ok': fields.boolean(string='Error'),
        'error_location_ok': fields.boolean(string='Error'),
        'error_po_ids': fields.many2many('purchase.order', 'allocated_purchase_order_config_rel',
                                         'wizard_id', 'order_id', string='PO'),
        'error_sm_cross_ids': fields.many2many('stock.picking', 'allocated_stock_picking_config_rel',
                                               'wizard_id', 'picking_id', string='Picking'),
        'error_sm_central_ids': fields.many2many('stock.picking', 'allocated_stock_picking_central_config_rel',
                                               'wizard_id', 'picking_id', string='Picking'),
        'error_location_ids': fields.many2many('stock.location', 'allocated_stock_location_config_rel',
                                               'wizard_id', 'location_id', string='Location'),
    }
    
    _defaults = {
        'error_msg': lambda *a: '''You have some documents which block the possibility to change the Allocated stocks configuration to Unallocated.
These documents can be some Cross-docking purchase orders not done, stock moves to/from a cross-docking or central stock location.
To change the Allocated stocks configuration, locations which will be inactivated should be empty.
        
Please click on the below buttons to see the different blocking documents.''',
        'allocation_setup': lambda *a: 'mixed',
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(allocation_stock_setup, self).default_get(cr, uid, fields, context=context)
        res['allocation_setup'] = setup_id.allocation_setup
        res['unallocated_ok'] = setup_id.unallocated_ok and 'yes' or 'no'
        
        return res
    
    def allocation_on_change(self, cr, uid, ids, allocation_setup='allocated', context=None):
        if allocation_setup in ('mixed', 'unallocated'):
            return {'value': {'unallocated_ok': 'yes'}}
        
        return {'value': {'unallocated_ok': 'no'}}    
        
    def _get_allocated_mvmt(self, cr, uid, type='unallocated'):
        '''
        Search if unallocated PO and moves not done exist
        '''
        data_obj = self.pool.get('ir.model.data')
        po_ids = self.pool.get('purchase.order').search(cr, uid, [('cross_docking_ok', '=', True), ('state', 'not in', ['cancel', 'done'])])
        
        picking_cross_ids = []
        cross_loc_ids = []
        if type != 'unallocated':
            cross_loc_ids = self.pool.get('stock.location').search(cr, uid, [('cross_docking_location_ok', '=', True)])
            move_ids = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ['cancel', 'done']),
                                                                    '|', 
                                                                    ('location_id', 'in', cross_loc_ids),
                                                                    ('location_dest_id', 'in', cross_loc_ids)])
            
            move_ids.extend(self.pool.get('stock.move').search(cr, uid, [('move_cross_docking_ok', '=', True)]))
            
            for move in self.pool.get('stock.move').browse(cr, uid, move_ids):
                picking_cross_ids.append(move.picking_id.id)
                
            picking_cross_ids.extend(self.pool.get('stock.picking').search(cr, uid, [('cross_docking_ok', '=', True)]))
        
        med_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]
        log_loc_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
        if type != 'unallocated':    
            med_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_unalloc_medical')[1]
            log_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_unalloc_logistic')[1]
        med_loc_ids = self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', med_loc_id)])
        log_loc_ids = self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', log_loc_id)])
        
        central_loc_ids = med_loc_ids + log_loc_ids
        move_ids = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ['cancel', 'done']),
                                                                '|', 
                                                                ('location_id', 'in', central_loc_ids),
                                                                ('location_dest_id', 'in', central_loc_ids)])
        picking_central_ids = []
        for move in self.pool.get('stock.move').browse(cr, uid, move_ids):
            picking_central_ids.append(move.picking_id.id)
        
        
        all_location_ids = cross_loc_ids + central_loc_ids
        nok_location_ids = []
        for location_id in all_location_ids:
            product_qty = self.pool.get('stock.location')._product_virtual_get(cr, uid, location_id)
            for product in product_qty:
                if product_qty[product]:
                    nok_location_ids.append(location_id)
                    continue
        
        return po_ids, picking_cross_ids, picking_central_ids, nok_location_ids
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        
        setup_id = setup_obj.get_config(cr, uid)
            
        # Get all locations concerned by this modification
        med_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]
        log_loc_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
        
        med_loc_ids = loc_obj.search(cr, uid, [('location_id', 'child_of', med_loc_id), ('active', 'in', ['t', 'f'])])
        log_loc_ids = loc_obj.search(cr, uid, [('location_id', 'child_of', log_loc_id), ('active', 'in', ['t', 'f'])])
        cross_docking_loc_ids = loc_obj.search(cr, uid, [('cross_docking_location_ok', '=', True), ('active', 'in', ['t', 'f'])])
        
        unallocated_ids = loc_obj.search(cr, uid, [('central_location_ok', '=', True), ('active', 'in', ['t', 'f'])])
        allocated_ids = cross_docking_loc_ids + med_loc_ids + log_loc_ids
        all_loc_ids = unallocated_ids + allocated_ids
        
        if payload.allocation_setup == 'allocated':
            po_ids, picking_cross_ids, picking_central_ids, nok_location_ids = self._get_allocated_mvmt(cr, uid, 'allocated')
            if po_ids or picking_cross_ids or picking_central_ids or nok_location_ids:
                self.write(cr, uid, [payload.id], {'allocation_setup': 'allocated',
                                                   'error_ok': True,
                                                   'error_po_ok': po_ids and True or False,
                                                   'error_cross_ok': picking_cross_ids and True or False,
                                                   'error_central_ok': picking_central_ids and True or False,
                                                   'error_location_ok': nok_location_ids and True or False,
                                                   'error_po_ids': [(6,0,po_ids)],
                                                   'error_sm_cross_ids': [(6,0,picking_cross_ids)],
                                                   'error_sm_central_ids': [(6,0,picking_central_ids)],
                                                   'error_location_ids': [(6,0,nok_location_ids)],})
                todo_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'unifield_setup', 'allocation_stock_setup_todo')[1]
                self.pool.get('ir.actions.todo').write(cr, uid, [todo_id], {'state': 'open'})
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'unifield_setup', 'view_allocation_stock_setup')[1]
                return {
                        'res_id': payload.id,
                        'view_mode': 'form',
                        'view_type': 'form',
                        'view_id': [view_id],
                        'res_model': 'allocation.stock.setup',
                        'type': 'ir.actions.act_window',
                        'target': 'new',}
            # Inactive unallocated locations
            loc_obj.write(cr, uid, unallocated_ids, {'active': False}, context=context)
            # Active allocated locations
            loc_obj.write(cr, uid, allocated_ids, {'active': True}, context=context)            
        elif payload.allocation_setup == 'unallocated':
            po_ids, picking_cross_ids, picking_central_ids, nok_location_ids = self._get_allocated_mvmt(cr, uid, 'unallocated')
            if po_ids or picking_cross_ids or picking_central_ids or nok_location_ids:
                self.write(cr, uid, [payload.id], {'allocation_setup': 'unallocated',
                                                   'error_ok': True,
                                                   'error_po_ok': po_ids and True or False,
                                                   'error_cross_ok': picking_cross_ids and True or False,
                                                   'error_central_ok': picking_central_ids and True or False,
                                                   'error_location_ok': nok_location_ids and True or False,
                                                   'error_po_ids': [(6,0,po_ids)],
                                                   'error_sm_cross_ids': [(6,0,picking_cross_ids)],
                                                   'error_sm_central_ids': [(6,0,picking_central_ids)],
                                                   'error_location_ids': [(6,0,nok_location_ids)],})
                todo_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'unifield_setup', 'allocation_stock_setup_todo')[1]
                self.pool.get('ir.actions.todo').write(cr, uid, [todo_id], {'state': 'open'})
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'unifield_setup', 'view_allocation_stock_setup')[1]
                return {
                        'res_id': payload.id,
                        'view_mode': 'form',
                        'view_type': 'form',
                        'view_id': [view_id],
                        'res_model': 'allocation.stock.setup',
                        'type': 'ir.actions.act_window',
                        'target': 'new',}
            # Inactive allocated locations
            loc_obj.write(cr, uid, allocated_ids, {'active': False}, context=context)
            # Active unallocated locations
            loc_obj.write(cr, uid, unallocated_ids, {'active': True}, context=context)
        else:
            # Active all locations
            loc_obj.write(cr, uid, all_loc_ids, {'active': True}, context=context)
    
        setup_obj.write(cr, uid, [setup_id.id], {'allocation_setup': payload.allocation_setup, 
                                             'unallocated_ok': payload.allocation_setup in ['unallocated', 'mixed']}, context=context)
        
    def go_to_po(self, cr, uid, ids, context=None):
        payload = self.browse(cr, uid, ids[0])
        po_ids = []
        for po in payload.error_po_ids:
            po_ids.append(po.id)
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'nodestroy': True,
                'domain': [('id', 'in', po_ids)],
                'target': 'current'}
        
    def go_to_cross(self, cr, uid, ids, context=None):
        payload = self.browse(cr, uid, ids[0])
        pick_ids = []
        for pick in payload.error_sm_cross_ids:
            pick_ids.append(pick.id)
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'nodestroy': True,
                'domain': [('id', 'in', pick_ids)],
                'target': 'current'}
        
    def go_to_central(self, cr, uid, ids, context=None):
        payload = self.browse(cr, uid, ids[0])
        pick_ids = []
        for pick in payload.error_sm_central_ids:
            pick_ids.append(pick.id)
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_type': 'form',
                'nodestroy': True,
                'view_mode': 'tree,form',
                'domain': [('id', 'in', pick_ids)],
                'target': 'current'}
        
    def go_to_location(self, cr, uid, ids, context=None):
        payload = self.browse(cr, uid, ids[0])
        loc_ids = []
        for loc in payload.error_location_ids:
            loc_ids.append(loc.id)
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.location',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'nodestroy': True,
                'domain': [('id', 'in', loc_ids)],
                'target': 'current'}
        
allocation_stock_setup()
