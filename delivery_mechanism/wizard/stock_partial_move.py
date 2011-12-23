# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from osv import fields, osv
from tools.translate import _
import time


class stock_partial_move_memory_out(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    
    _columns = {'force_complete' : fields.boolean(string='Force'),
                }
    _defaults = {'force_complete': False,}
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        remove force_complete if not incoming
        
        temporary hack
        because problem: attrs does not work : <field name="force_complete" attrs="{'readonly': [('type_check', '!=', 'in')]}" />
        '''
        res = super(stock_partial_move_memory_out, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        picking_obj = self.pool.get('stock.picking')
        picking_id = context.get('active_ids')
        if picking_id:
            picking_id = picking_id[0]
            picking_type = picking_obj.browse(cr, uid, picking_id, context=context).type
            if picking_type != 'in':
                arch = res['arch']
                arch = arch.replace('<field name="force_complete"/>', '')
                res['arch'] = arch
        return res
    
stock_partial_move_memory_out()


class stock_partial_move_memory_in(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    _name = "stock.move.memory.in"
    
stock_partial_move_memory_in()

