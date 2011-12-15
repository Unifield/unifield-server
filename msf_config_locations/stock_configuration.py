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

class stock_location(osv.osv):
    '''
    Change the order and parent_order field.
    '''
    _name = "stock.location"
    _inherit = 'stock.location'
    _parent_order = 'posz'
    _order = 'posz'
    
stock_location()


class stock_location_configuration_wizard(osv.osv_memory):
    _name = 'stock.location.configuration.wizard'
    
    _columns = {
        'location_name': fields.char(size=64, string='Location name', required=True),
        'location_type': fields.selection([('stock', 'Stock'), ('cu', 'Consumption Unit'), ('eprep', 'EPREP')],
                                          string='Location usage'),
        'location_in_out': fields.selection([('in', 'Internal'), ('out', 'Partner')], string='Location type'),
    }

    def confirm_creation(self, cr, uid, ids, context={}):
        res = False
        data_obj = self.pool.get('ir.model.data')
        location_obj = self.pool.get('stock.location')
        parent_location_id = False
        location_category = False
        location_usage = False
        location_name = False
        chained_location_type = 'none'
        chained_auto_packing = 'manual'
        chained_picking_type = 'internal'
        chained_location_id = False
        
        for wizard in self.browse(cr, uid, ids, context=context):
            location_name = wizard.location_name
            # Check if all parent locations are activated in the system
            if wizard.location_type in ('stock', 'eprep') or (wizard.location_in_out == 'in' and wizard.location_type == 'cu'):
                # Check if 'Configurable locations' location is active − If not, activate it !
                location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_internal_client_view')
                if not location_id:
                    raise osv.except_osv(_('Error'), _('Location \'Configurable locations\' not found in the instance or is not activated !'))
                
                if not location_obj.browse(cr, uid, location_id, context=context).active:
                    location_obj.write(cr, uid, [location_id[1]], {'active': True}, context=context)
                
                if wizard.location_type in ('stock', 'eprep'):
                    if wizard.location_type == 'stock':
                        location_category = 'stock'
                        location_usage = 'internal'
                    else:
                        location_stock_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')
                        if not location_stock_id:
                            raise osv.except_osv(_('Error'), _('Location \'Stock\' not found in the instance or is not activated !'))
                        location_category = 'eprep'
                        location_usage = 'internal'
                        chained_location_type = 'fixed'
                        chained_auto_packing = 'manual'
                        chained_picking_type = 'internal'
                        chained_location_id = location_stock_id[1]
                    # Check if 'Intermediate Stocks' is active − If note activate it !
                    parent_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')
                
                    if not parent_location_id:
                        raise osv.except_osv(_('Error'), _('Location \'Intermediate Stocks\' not found in the instance or is not activated !'))
                    
                    parent_location_id = parent_location_id[1]
                    
                    if not location_obj.browse(cr, uid, parent_location_id, context=context).active:
                        location_obj.write(cr, uid, [parent_location_id], {'active': True}, context=context)
                elif wizard.location_type == 'cu':
                    location_category = 'consumption_unit'
                    location_usage = 'internal'
                    # Check if 'Internal Consumption Units' is active − If note activate it !
                    parent_location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_consumption_units_view')
                    
                    parent_location_id = parent_location_id[1]
                
                    if not parent_location_id:
                        raise osv.except_osv(_('Error'), _('Location \'Internal Consumption Units\' not found in the instance or is not activated !'))
                    
                    if not location_obj.browse(cr, uid, parent_location_id, context=context).active:
                        location_obj.write(cr, uid, [parent_location_id], {'active': True}, context=context)
                else:
                    raise osv.except_osv(_('Error'), _('The type of the new location is not correct ! Please check the parameters and retry.'))
            elif wizard.location_in_out == 'out' and wizard.location_type == 'cu':
                location_category = 'consumption_unit'
                location_usage = 'customer'
                chained_picking_type = 'out'
                # Check if 'MSF Customer' location is active − If not, activate it !
                parent_location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')
                if not parent_location_id:
                    raise osv.except_osv(_('Error'), _('Location \'MSF Customer\' not found in the instance or is not activated !'))
                                    
                parent_location_id = parent_location_id[1]
                    
                if not location_obj.browse(cr, uid, parent_location_id, context=context).active:
                    location_obj.write(cr, uid, [parent_location_id], {'active': True}, context=context)
            else:
                raise osv.except_osv(_('Error'), _('The type of the new location is not correct ! Please check the parameters and retry.'))
        
        if not parent_location_id or not location_category or not location_usage:
            raise osv.except_osv(_('Error'), _('Parent stock location not found for the new location !'))
        
        # Create the new location
        location_obj.create(cr, uid, {'name': location_name,
                                      'location_id': parent_location_id,
                                      'location_category': location_category,
                                      'usage': location_usage,
                                      'chained_location_type': chained_location_type,
                                      'chained_auto_packing': chained_auto_packing,
                                      'chained_picking_type': chained_picking_type,
                                      'chained_location_id': chained_location_id,
                                      }, context=context)
        
        return_view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_location_tree')
        
        if return_view_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'stock.location',
                    'domain': [('location_id','=',False)],
                    'view_type': 'tree',
                    'view_id': [return_view_id[1]],
                    }
        else:
            return {'type': 'ir.actions.act_window'}
    
stock_location_configuration_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: