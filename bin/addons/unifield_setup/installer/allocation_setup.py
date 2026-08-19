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
    }

    _defaults = {
        'allocation_setup': lambda *a: 'mixed',
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Display the default value for delivery process
        '''
        setup_id = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res = super(allocation_stock_setup, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        res['allocation_setup'] = setup_id.allocation_setup
        res['unallocated_ok'] = setup_id.unallocated_ok and 'yes' or 'no'

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
            # Inactive unallocated locations
            loc_obj.write(cr, uid, unallocated_ids, {'active': False}, context=context)
            # Active allocated locations
            loc_obj.write(cr, uid, allocated_ids, {'active': True}, context=context)
        elif payload.allocation_setup == 'unallocated':
            # Inactive allocated locations
            loc_obj.write(cr, uid, allocated_ids, {'active': False}, context=context)
            # Active unallocated locations
            loc_obj.write(cr, uid, unallocated_ids, {'active': True}, context=context)
        else:
            # Active all locations
            loc_obj.write(cr, uid, all_loc_ids, {'active': True}, context=context)

        setup_obj.write(cr, uid, [setup_id.id], {'allocation_setup': payload.allocation_setup,
                                                 'unallocated_ok': payload.allocation_setup in ['unallocated', 'mixed']}, context=context)

allocation_stock_setup()
