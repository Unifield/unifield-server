#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF, Smile. All Rights Reserved
#    All Rigts Reserved
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

class kit_creation(osv.osv):
    _inherit = 'kit.creation'
    _name = 'kit.creation'
    
    def action_cancel(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        kit = self.browse(cr, uid, ids, context=context)[0]
        move_obj = self.pool.get('stock.move')
        composition_kit = self.pool.get('composition.kit')
        stock_picking = self.pool.get('stock.picking')
        move_ids = []
        
        if kit.kit_ids_kit_creation:
            for line in kit.kit_ids_kit_creation:
                kit_ids_kit_creation = line.id
                composition_kit.write(cr, uid, [kit_ids_kit_creation], {'state': 'cancel'}, context=context)
            
        if kit.internal_picking_id_kit_creation:
            internal_picking_id_kit_creation = kit.internal_picking_id_kit_creation.id
            stock_picking.write(cr, uid, [internal_picking_id_kit_creation], {'state': 'cancel'}, context=context)
            
        if kit.consumed_ids_kit_creation:
            move_ids = [x.id for x in kit.consumed_ids_kit_creation]
            move_obj.action_cancel(cr, uid, move_ids, context=context)
            # we set original_from_process_stock_move to False, so lines can be deleted when canceled
            move_obj.write(cr, uid, move_ids, {'original_from_process_stock_move': False}, context=context)
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

kit_creation()