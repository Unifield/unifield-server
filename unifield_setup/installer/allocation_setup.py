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
                                              string='Allocated stocks', required=True),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        '''
        Display the default value for delivery process
        '''
        setup_obj = self.pool.get('unifield.setup.configuration')
        
        res = super(allocation_stock_setup, self).default_get(cr, uid, fields, context=context)
        
        setup_ids = setup_obj.search(cr, uid, [], context=context)
        if not setup_ids:
            setup_id = setup_obj.create(cr, uid, {}, context=context)
        else:
            setup_id = setup_obj.browse(cr, uid, setup_ids[0], context=context)
        
        res['allocation_setup'] = setup_id.allocation_setup
        
        return res
        
    
    def execute(self, cr, uid, ids, context=None):
        '''
        Fill the delivery process field in company
        '''
        assert len(ids) == 1, "We should only get one object from the form"
        payload = self.browse(cr, uid, ids[0], context=context)
        
        setup_obj = self.pool.get('unifield.setup.configuration')
        data_obj = self.pool.get('ir.model.data')
        loc_obj = self.pool.get('stock.location')
        
        setup_ids = setup_obj.search(cr, uid, [], context=context)
        if not setup_ids:
            setup_ids = [setup_obj.create(cr, uid, {}, context=context)]
            
        # Get all menu ids concerned by this modification
        med_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]
        un_med_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_unalloc_medical')[1]
        log_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_logistic')[1]
        un_log_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_unalloc_logistic')[1]
        cross_docking_loc_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        
        if payload.allocation_setup == 'allocated':
            # Inactive unallocated locations
            loc_obj.write(cr, uid, [un_med_loc_id,
                                    un_log_loc_id], {'active': False}, context=context)
            # Active allocated locations
            loc_obj.write(cr, uid, [cross_docking_loc_id,
                                    med_loc_id,
                                    log_loc_id,], {'active': True}, context=context)            
        elif payload.allocation_setup == 'unallocated':
            # Inactive allocated locations
            loc_obj.write(cr, uid, [cross_docking_loc_id,
                                    med_loc_id,
                                    log_loc_id,], {'active': False}, context=context)
            # Active unallocated locations
            loc_obj.write(cr, uid, [un_med_loc_id,
                                    un_log_loc_id], {'active': True}, context=context)
        else:
            # Active all locations
            loc_obj.write(cr, uid, [cross_docking_loc_id,
                                    med_loc_id,
                                    un_med_loc_id,
                                    log_loc_id,
                                    un_log_loc_id], {'active': True}, context=context)
    
        setup_obj.write(cr, uid, setup_ids, {'allocation_setup': payload.allocation_setup}, context=context)
        
allocation_stock_setup()