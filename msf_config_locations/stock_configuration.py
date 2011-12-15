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
        'location_usage': fields.selection([('stock', 'Stock'), ('cu', 'Consumption Unit'), ('eprep', 'EPREP')],
                                          string='Location usage'),
        'location_type': fields.selection([('in', 'Internal'), ('out', 'External')], string='Location type'),
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
            if wizard.location_usage in ('stock', 'eprep') or (wizard.location_type == 'in' and wizard.location_usage == 'cu'):
                # Check if 'Configurable locations' location is active − If not, activate it !
                location_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_internal_client_view')
                if not location_id:
                    raise osv.except_osv(_('Error'), _('Location \'Configurable locations\' not found in the instance or is not activated !'))
                
                if not location_obj.browse(cr, uid, location_id, context=context).active:
                    location_obj.write(cr, uid, [location_id[1]], {'active': True}, context=context)
                
                if wizard.location_usage in ('stock', 'eprep'):
                    if wizard.location_usage == 'stock':
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
                elif wizard.location_usage == 'cu':
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
            elif wizard.location_type == 'out' and wizard.location_usage == 'cu':
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
                                      'optional_loc': True,
                                      }, context=context)
        
        return_view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_location_tree')
        
        if return_view_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'stock.location',
                    'domain': [('location_id','=',False)],
                    'view_type': 'tree',
                    'target': 'crush',
                    'view_id': [return_view_id[1]],
                    }
        else:
            return {'type': 'ir.actions.act_window'}
    
stock_location_configuration_wizard()


class stock_remove_location_wizard(osv.osv_memory):
    _name = 'stock.remove.location.wizard'
    
    _columns = {
        'location_id': fields.many2one('stock.location', string='Location to remove'),
        'location_usage': fields.selection([('internal', 'Internal'), ('customer', 'External')], string='Location type'),
        'location_category': fields.selection([('eprep', 'EPREP'), ('stock', 'Stock'), ('consumption_unit', 'Consumption Unit')],
                                              string='Location type'),
        'error_message': fields.text(string='Information Message', readonly=True),
        'error': fields.boolean(string='Error'),
        'move_from_to': fields.boolean(string='Has a move from/to the location'),
        'not_empty': fields.boolean(string='Location not empty'),
        'has_child': fields.boolean(string='Location has children locations'),
    }
    
    def location_id_on_change(self, cr, uid, ids, location_id, context={}):
        '''
        Check if no moves to this location aren't done
        Check if there is no stock in this location
        '''
        res = {'error_message': '', 
               'move_from_to': False, 
               'not_empty': False,
               'has_child': False}
        warning = {}
        error = False
        
        if location_id:
            location = self.pool.get('stock.location').browse(cr, uid, location_id, context=context)
            # Check if no moves to this location aren't done
            move_from_to = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ('done', 'cancel')), '|', ('location_id', '=', location.id), ('location_dest_id', '=', location.id)])
            if move_from_to:
                error = True
                res['move_from_to'] = True
                res['error_message'] += '''* You have at least one move from or to the location '%s' which is not 'Done'.
Please click on the 'See moves' button to see which moves are still in progress from/to this location.''' %location.name
                res['error_message'] += '\n' + '\n'
            # Check if no stock in the location
            if location.stock_real and location.usage == 'internal':
                error = True
                res['not_empty'] = True
                res['error_message'] += '''* The location '%s' is not empty of products. 
Please click on the 'Products in location' button to see which products are still in the location.''' %location.name
                res['error_message'] += '\n' + '\n'

            # Check if the location has children locations
            if location.child_ids:
                error = True
                res['has_child'] = True
                res['error_message'] += '''* The location '%s' has children locations.
Please remove all children locations before remove it. 
Please click on the 'Children locations' button to see all children locations.''' %location.name
                res['error_message'] += '\n' + '\n'
                
        if error:
            warning.update({'title': 'Be careful !',
                            'message': 'You have a problem with this location − Please see the message in the form for more information.'})
            
        res['error'] = error
        
        return {'value': res,
                'warning': warning}
        
    def check_error(self, cr, uid, ids, context={}):
        '''
        Check if errors are always here
        '''
        for wizard in self.browse(cr, uid, ids, context=context):
            errors = self.location_id_on_change(cr, uid, ids, wizard.location_id.id, context=context)
            self.write(cr, uid, ids, errors.get('value', {}), context=context)
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.remove.location.wizard',
                'res_id': wizard.id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',}
        
    def location_usage_change(self, cr, uid, ids, usage, context={}):
        if usage and usage == 'customer':
            return {'value': {'location_category': 'consumption_unit'}} 
        
        return {}
        
    def deactivate_location(self, cr, uid, ids, context={}):
        '''
        Deactivate the selected location
        '''
        location = False
        data_obj = self.pool.get('ir.model.data')
        location_obj = self.pool.get('stock.location')
        configurable_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_internal_client_view')[1]
        intermediate_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1]
        internal_cu_loc_id = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_consumption_units_view')[1]
        
        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.error or wizard.has_child or wizard.not_empty or wizard.move_from_to:
                raise osv.except_osv(_('Error'), _('You cannot remove this location because some errors are still here !'))
            
            location = wizard.location_id
        
        # De-activate the location
        location_obj.write(cr, uid, [location.id], {'active': False}, context=context)
            
        # Check if parent location should be also de-activated
        if location.location_id.id in (intermediate_loc_id, internal_cu_loc_id):
            empty = True
            for child in location.location_id.child_ids:
                if child.active:
                    empty = False
            if empty:
                location_obj.write(cr, uid, [location.location_id.id], {'active': False}, context=context)
                
                if location.location_id.location_id.id == configurable_loc_id:
                    empty2 = True
                    for child in location.location_id.location_id.child_ids:
                        if child.active:
                            empty2 = False
                    if empty2:
                        location_obj.write(cr, uid, [location.location_id.location_id.id], {'active': False}, context=context)
            
        return_view_id = data_obj.get_object_reference(cr, uid, 'stock', 'view_location_tree')
        
        if return_view_id:
            return {'type': 'ir.actions.act_window',
                    'res_model': 'stock.location',
                    'domain': [('location_id','=',False)],
                    'view_type': 'tree',
                    'target': 'crush',
                    'view_id': [return_view_id[1]],
                    }
        else:
            return {'type': 'ir.actions.act_window'}
    
    def see_moves(self, cr, uid, ids, context={}):
        '''
        Returns all stock.picking containing a stock move not done from/to the location
        '''
        location = False
        picking_ids = []
        
        for wizard in self.browse(cr, uid, ids, context=context):
            location = wizard.location_id
            
        move_ids = self.pool.get('stock.move').search(cr, uid, [('state', 'not in', ('done', 'cancel')), '|', ('location_id', '=', location.id), ('location_dest_id', '=', location.id)])
        for move in self.pool.get('stock.move').browse(cr, uid, move_ids, context=context):
            if move.picking_id and move.picking_id.id not in picking_ids:
                picking_ids.append(move.picking_id.id)
                
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'vpicktree')[1]
        if location.usage == 'customer':
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'view_picking_out_tree')[1]
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'domain': [('id', 'in', picking_ids)],
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'tree,form',
                'target': 'current',
                }
        
    def products_in_location(self, cr, uid, ids, context={}):
        '''
        Returns a list of products in the location
        '''
        location = False
        
        for wizard in self.browse(cr, uid, ids, context=context):
            location = wizard.location_id
            
        context.update({'contact_display': 'partner', 'search_default_real':1, 
                        'search_default_location_type_internal':1,
                        'search_default_group_product':1,
                        'group_by':[], 'group_by_no_leaf':1})
        context.update({'search_default_location_id': location.id})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'report.stock.inventory',
                'view_type': 'form',
                'view_mode': 'tree',
                'domain': [('location_id', '=', location.id)],
                'context': context,
                'target': 'current'}
        
    def children_location(self, cr, uid, ids, context={}):
        '''
        Returns the list of all children locations
        '''
        location_ids = []
        location = False
        
        for wizard in self.browse(cr, uid, ids, context=context):
            location = wizard.location_id
            
        for loc in location.child_ids:
            location_ids.append(loc.id)
            
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.location',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', location_ids)],
                'target': 'current',}
    
stock_remove_location_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: