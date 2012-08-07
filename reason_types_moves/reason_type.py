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

from osv import osv, fields

from tools.translate import _

import logging
from os import path
import math
import re
import tools

class stock_reason_type(osv.osv):
    _name = 'stock.reason.type'
    _description = 'Reason Types Moves'
    
    def init(self, cr):
        """
        Load reason_type_data.xml brefore product
        """
        if hasattr(super(stock_reason_type, self), 'init'):
            super(stock_reason_type, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'reason_types_moves')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']

        if demo:
            logging.getLogger('init').info('HOOK: module reason_types_moves: loading reason_type_data.xml')
            pathname = path.join('reason_types_moves', 'reason_type_data.xml')
            file = tools.file_open(pathname)
            tools.convert_xml_import(cr, 'reason_types_moves', file, {}, mode='init', noupdate=False)
    
    def return_level(self, cr, uid, type, level=0):
        if type.parent_id:
            level += 1
            self.return_level(cr, uid, type.parent_id, level)
        
        return level
    
    def _get_level(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the level of the reason type
        '''
        res = {}
        
        for type in self.browse(cr, uid, ids, context=context):
            res[type.id] = self.return_level(cr, uid, type)
        
        return res
    
    def _get_inventory(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns if the type will be present in inventory line
        '''
        res = {}
        
        for type in self.browse(cr, uid, ids, context=context):
            tmp_type = type
            while tmp_type.parent_id:
                tmp_type = tmp_type.parent_id
            res[type.id] = tmp_type.inventory_ok
            
        return res
    
    def _search_inventory(self, cr, uid, obj, name, args, context=None):
        '''
        Returns the ids of all reason type which are displayed in inventory line
        '''
        res = []
        
        for arg in args:
            if arg[0] == 'is_inventory' and arg[1] == '=' and arg[2] in (True, 1, 'True', 'true', '1'):
                inv_ids = self.search(cr, uid, [('inventory_ok', '=', True)], context=context)
                res_ids = inv_ids
                while inv_ids:
                    inv_ids = self.search(cr, uid, [('parent_id', 'in', inv_ids)], context=context)
                    res_ids.extend(inv_ids)
                res = [('id', 'in', res_ids)] 
                    
        return res
                
    
    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            name = record.name
            code = record.code
            if record.parent_id:
                name = record.parent_id.name + ' / ' + name
                code = str(record.parent_id.code) + '.' + str(code)
            res.append((record.id, '%s %s' % (code, name)))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'code': fields.integer(string='Code', required=True),
        'complete_name': fields.function(_name_get_fnc, method=True, type="char", string='Name'),
        'parent_id': fields.many2one('stock.reason.type', string='Parent reason'),
        'level': fields.function(_get_level, method=True, type='integer', string='Level', readonly=True),
        'inventory_ok': fields.boolean(string='Inventory type', help='If checked, this reason type will be available in inventory line'),
        'is_inventory': fields.function(_get_inventory, fnct_search=_search_inventory, 
                                        method=True, type='boolean', string='Inventory type', 
                                        readonly=True, help='If checked, this reason type will be available in inventory line'),
        'incoming_ok': fields.boolean(string='Available for incoming shipment ?'),
        'internal_ok': fields.boolean(string='Available for internal picking ?'),
        'outgoing_ok': fields.boolean(string='Available for outgoing movements ?'),
    }
    
stock_reason_type()

class stock_inventory_line(osv.osv):
    _name = 'stock.inventory.line'
    _inherit = 'stock.inventory.line'

    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Adjustment type', required=True),
        'comment': fields.char(size=128, string='Comment'),
    }
    
    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['reason_type_id']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for stock.picking')
                vals.update(self.pool.get('stock.picking')._get_default_reason(cr, uid, context))
        return super(stock_inventory_line, self).create(cr, uid, vals, context)

stock_inventory_line()

class stock_inventory(osv.osv):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'

    # @@@override@ stock.stock_inventory._inventory_line_hook()
    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        """ Creates a stock move from an inventory line
        @param inventory_line:
        @param move_vals:
        @return:
        """
        location_obj = self.pool.get('stock.location')

        # Copy the comment
        move_vals.update({
            'comment': inventory_line.comment,
            'reason_type_id': inventory_line.reason_type_id.id,
            'not_chained': True,
        })

        return super(stock_inventory, self)._inventory_line_hook(cr, uid, inventory_line, move_vals) 
        # @@@end

stock_inventory()


class stock_fill_inventory(osv.osv_memory):
    _name = 'stock.fill.inventory'
    _inherit = 'stock.fill.inventory'
    
    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True, domain=[('is_inventory', '=', True)]),
    }
    
    def _hook_fill_datas(self, cr, uid, *args, **kwargs):
        '''
        Hook to add data values in fill inventory line data
        '''
        res = super(stock_fill_inventory, self)._hook_fill_datas(cr, uid, *args, **kwargs)
        if kwargs.get('fill_inventory'):
            res.update({'reason_type_id': kwargs['fill_inventory'].reason_type_id.id})
        
        # Fix unit tests on stock
        if kwargs.get('context'):
            context = kwargs['context']
            if context.get('update_mode') in ['init', 'update']:
                required = ['reason_type_id']
                has_required = False
                for req in required:
                    if  req in res and res.get('req'):
                        has_required = True
                        break
                    if not has_required:
                        logging.getLogger('init').info('Loading default values for stock.picking')
                        res.update(self.pool.get('stock.picking')._get_default_reason(cr, uid, context))

        return res
    
stock_fill_inventory() 



class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
        
    def _get_default_reason(self, cr, uid, context=None):
        res = {}
        toget = [('reason_type_id', 'reason_type_external_supply')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', xml_id)
            res[field] = nom[1]
        return res
    
    def onchange_move(self, cr, uid, ids, context=None):
        res = {}
        if ids:
            for pick in self.browse(cr, uid, ids, context=context):
                res.update({'reason_type_id': pick.reason_type_id.id})

        return {'value': res}

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Take into account all stock_picking with reason_type_id is a children
        '''
        reason_obj = self.pool.get('stock.reason.type')

        new_args = []

        for arg in args:
            if arg[0] == 'reason_type_id' and arg[1] in ('=', 'in'):
                new_arg = (arg[0], 'child_of', arg[2])
            else:
                new_arg = arg
            new_args.append(new_arg)

        return super(stock_picking, self).search(cr, uid, new_args, offset=offset, limit=limit, order=order, context=context, count=False)
    
    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['reason_type_id']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for stock.picking')
                vals.update(self._get_default_reason(cr, uid, context))
        return super(stock_picking, self).create(cr, uid, vals, context)
    
    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True),
    }
    
stock_picking()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'
    
    def hook__create_chained_picking(self, cr, uid, pick_values, picking):
        if not 'reason_type_id' in pick_values:
            pick_values.update({'reason_type_id': picking.reason_type_id.id})
            
        return pick_values
    
    def _get_default_reason(self, cr, uid, context=None):
        res = {}
        toget = [('reason_type_id', 'reason_type_external_supply')]

        for field, xml_id in toget:
            nom = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', xml_id)
            res[field] = nom[1]
        return res
    
    def create(self, cr, uid, vals, context=None):
        '''
        Set default values for datas.xml and tests.yml
        '''
        if not context:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            required = ['reason_type_id']
            has_required = False
            for req in required:
                if  req in vals:
                    has_required = True
                    break
            if not has_required:
                logging.getLogger('init').info('Loading default values for stock.picking')
                vals.update(self._get_default_reason(cr, uid, context))

        if 'location_dest_id' in vals:
            dest_id = self.pool.get('stock.location').browse(cr, uid, vals['location_dest_id'], context=context)
            if dest_id.usage == 'inventory':
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            if dest_id.scrap_location:
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
                
        # Change the reason type of the picking if it is not the same
        if vals.get('picking_id'):
            pick_id = self.pool.get('stock.picking').browse(cr, uid, vals['picking_id'], context=context)
            if pick_id.reason_type_id.id != vals['reason_type_id']:
                other_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
                self.pool.get('stock.picking').write(cr, uid, vals['picking_id'], {'reason_type_id': other_type_id}, context=context)

        return super(stock_move, self).create(cr, uid, vals, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        '''
        Set default values if the reason type has changed
        '''
        if 'location_dest_id' in vals:
            dest_id = self.pool.get('stock.location').browse(cr, uid, vals['location_dest_id'], context=context)
            if dest_id.usage == 'inventory':
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            if dest_id.scrap_location:
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
                
        # Change the reason type of the picking if it is not the same
        if 'reason_type_id' in vals:
            for pick_id in self.browse(cr, uid, ids, context=context):
                if pick_id.picking_id and pick_id.picking_id.reason_type_id.id != vals['reason_type_id']:
                    other_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_other')[1]
                    self.pool.get('stock.picking').write(cr, uid, pick_id.picking_id.id, {'reason_type_id': other_type_id}, context=context)

        return super(stock_move, self).write(cr, uid, ids, vals, context=context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Take into account all stock_picking with reason_type_id is a children
        '''
        reason_obj = self.pool.get('stock.reason.type')

        new_args = []

        for arg in args:
            if arg[0] == 'reason_type_id' and arg[1] in ('=', 'in'):
                new_arg = (arg[0], 'child_of', arg[2])
            else:
                new_arg = arg
            new_args.append(new_arg)

        return super(stock_move, self).search(cr, uid, new_args, offset=offset, limit=limit, order=order, context=context, count=False)
    
    def _get_product_type(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = move.product_id.type
        
        return res
    
    _columns = {
        'reason_type_id': fields.many2one('stock.reason.type', string='Reason type', required=True),
        'comment': fields.char(size=128, string='Comment'),
        'product_type': fields.function(_get_product_type, method=True, type='char', string='Product type', store=False),
        'not_chained': fields.boolean(string='Not chained', help='If checked, the chaining move will not be run.'),
    }
    
    _defaults = {
        'reason_type_id': lambda obj, cr, uid, context={}: context.get('reason_type_id', False) and context.get('reason_type_id') or False,
        'not_chained': lambda *a: False,
    }

    def location_dest_change(self, cr, uid, ids, location_dest_id, context=None):
        '''
        Tries to define a reason type for the move according to the destination location
        '''
        vals = {}

        if location_dest_id:
            dest_id = self.pool.get('stock.location').browse(cr, uid, location_dest_id, context=context)
            if dest_id.usage == 'inventory':
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            if dest_id.scrap_location:
                vals['reason_type_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]


        return {'value': vals}
    
    def _hook_dest(self, cr, uid, *args, **kwargs):
        move = kwargs['m']
        res = super(stock_move, self)._hook_dest(cr, uid, *args, **kwargs)
        return res and not move.not_chained
    
stock_move()


class stock_return_picking(osv.osv_memory):
    _name = 'stock.return.picking'
    _inherit = 'stock.return.picking'

    def _hook_default_return_data(self, cr, uid, ids, context=None, 
                                  *args, **kwargs):
        '''
        Hook to allow user to modify the value for the stock move copy method
        '''
        if context is None:
            context = {}
        default_value = super(stock_return_picking, self).\
                        _hook_default_return_data(cr, uid, ids, 
                                      context=context, 
                                      default_value=kwargs['default_value'])

        reason_type_id = self.pool.get('ir.model.data').\
                         get_object_reference(cr, uid, 'reason_types_moves', 
                                          'reason_type_return_from_unit')[1]

        default_value.update({'reason_type_id': reason_type_id})

        return default_value

stock_return_picking()

class stock_location(osv.osv):
    _name = 'stock.location'
    _inherit = 'stock.location'
    
    def _get_replenishment(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for loc in ids:
            res[loc] = True
        return res

    def _get_st_out(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = False
        return res
    
    def _src_replenishment(self, cr, uid, obj, name, args, context=None):
        res = []
        for arg in args:
            if arg[0] == 'is_replenishment':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error !'), _('Bad operator !'))
                elif arg[2] and isinstance(arg[2], (int, long)):
                    warehouse_id = arg[2]
                    stock_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_stock_id.id
                    res.append(('location_id', 'child_of', stock_id))
                    res.append(('location_category', '=', 'stock'))
                    res.append(('quarantine_location', '=', False))
        return res
        
    def _src_st_out(self, cr, uid, obj, name, args, context=None):
        '''
        Returns location allowed for Standard out
        '''
        res = [('usage', '!=', 'view')]
        loc_obj = self.pool.get('stock.location')
        for arg in args:
            if arg[0] == 'standard_out_ok':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error !'), _('Bad operator !'))
                if arg[2] == 'dest':
                    virtual_loc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_locations_virtual')[1]
                    virtual_loc_ids = loc_obj.search(cr, uid, [('location_id', 'child_of', virtual_loc_id)], context=context)
                    
                    customer_loc_ids = loc_obj.search(cr, uid, [('usage', '=', 'customer')], context=context)
                    output_loc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_output')[1]
                    
                    loc_ids = virtual_loc_ids
                    loc_ids.extend(customer_loc_ids)
                    loc_ids.append(output_loc_id)
                    res.append(('id', 'in', loc_ids))
                elif arg[2] == 'src':
                    warehouse_ids = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)
                    output_loc_ids = []
                    input_loc_ids = []
                    output_ids = []
                    input_ids = []
                    for w in self.pool.get('stock.warehouse').browse(cr, uid, warehouse_ids, context=context):
                        output_ids.append(w.lot_output_id.id)
                        input_ids.append(w.lot_input_id.id)
                        
                    for loc_id in output_ids:
                        output_loc_ids.extend(self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', loc_id)], context=context))
                    for loc_id in input_ids:
                        input_loc_ids.extend(self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', loc_id)], context=context))
                    
                    res.append(('quarantine_location', '=', False))
                    res.append(('usage', '=', 'internal'))
                    res.append(('cross_docking_location_ok', '=', False))
                    res.append(('id', 'not in', output_loc_ids))
                    res.append(('id', 'not in', input_loc_ids))
                    
        return res
                    
    _columns = {
        'is_replenishment': fields.function(_get_replenishment, fnct_search=_src_replenishment, type='boolean',
                                            method=True, string='Is replenishment ?', store=False,
                                            help='Is True, the location could be used in replenishment rules'),
        'standard_out_ok': fields.function(_get_st_out, fnct_search=_src_st_out, method=True, type='boolean', string='St. Out', store=False),
    }
    
stock_location()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
