#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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


class stock_adjustment_type(osv.osv):
    _name = 'stock.adjustment.type'
    _description = 'Inventory/Move Adjustment Types'

    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
    }

stock_adjustment_type()


class stock_inventory_line(osv.osv):
    _name = 'stock.inventory.line'
    _inherit = 'stock.inventory.line'

    _columns = {
        'type_id': fields.many2one('stock.adjustment.type', string='Adjustment type'),
        'comment': fields.char(size=128, string='Comment'),
    }

stock_inventory_line()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'

    _columns = {
        'type_id': fields.many2one('stock.adjustment.type', string='Adjustment type', readonly=True),
        'comment': fields.char(size=128, string='Comment'),
    }

stock_move()


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
        
        type_id = inventory_line.type_id and inventory_line.type_id.id or False
        
        # Copy the comment
        move_vals.update({
            'comment': inventory_line.comment,
        })
        
        location = location_obj.browse(cr, uid, move_vals['location_dest_id'])
        
        if type_id:
            move_vals.update({
                'type_id': type_id,
            })
            
        if location.usage == 'inventory':
            reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
            move_vals.update({
                'reason_type_id': reason_type_id,
            })
            
        if location.scrap_location:
            reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1]
            move_vals.update({
                'reason_type_id': reason_type_id,
            })
            
        if inventory_line.type_id and type_id == self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_inventory_type', 'adjustment_type_expired')[1]:
            reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_expiry')[1]
            move_vals.update({
                'reason_type_id': reason_type_id,
            })
            
        if inventory_line.location_id.id == move_vals.get('location_dest_id'):
            reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
            move_vals.update({
                'reason_type_id': reason_type_id,
            })
        
        return super(stock_inventory, self)._inventory_line_hook(cr, uid, inventory_line, move_vals) 
        # @@@end

stock_inventory()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

