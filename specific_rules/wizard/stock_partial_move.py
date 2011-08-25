# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
    
    def _get_checks_batch(self, cr, uid, ids, name, arg, context=None):
        '''
        todo should be merged with 'multi'
        '''
        result = {}
        for id in ids:
            result[id] = False
            
        for out in self.browse(cr, uid, ids, context=context):
            result[out.id] = out.product_id.batch_management
            
        return result
    
    def _get_checks_expiry(self, cr, uid, ids, name, arg, context=None):
        '''
        todo should be merged with 'multi'
        '''
        result = {}
        for id in ids:
            result[id] = False
            
        for out in self.browse(cr, uid, ids, context=context):
            result[out.id] = out.product_id.perishable
            
        return result
    
    _columns = {
        'batch_number_check': fields.function(_get_checks_batch, method=True, string='Batch Number Check', type='boolean', readonly=True),
        'expiry_date_check': fields.function(_get_checks_expiry, method=True, string='Expiry Date Check', type='boolean', readonly=True),
        'expiry_date': fields.date('Expiry Date'),
    }

stock_partial_move_memory_out()

    
class stock_partial_move_memory_in(osv.osv_memory):
    _inherit = "stock.move.memory.out"
    _name = "stock.move.memory.in"

stock_partial_move_memory_in()
