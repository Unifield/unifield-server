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
from order_types import ORDER_PRIORITY, ORDER_CATEGORY

class stock_move(osv.osv):
    _name= 'stock.move'
    _inherit = 'stock.move'
    
    def _get_order_information(self, cr, uid, ids, fields_name, arg, context={}):
        '''
        Returns information about the order linked to the stock move
        '''
        res = {}
        
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = False
            if move.purchase_line_id and move.purchase_line_id.id:
                order = move.purchase_line_id.order_id
            elif move.sale_line_id and move.sale_line_id.id:
                order = move.sale_line_id.order_id
                
            if order:
                res[move.id] = {}
                if 'order_priority' in fields_name:
                    res[move.id]['order_priority'] = order.priority
                if 'order_category' in fields_name:
                    res[move.id]['order_category'] = order.categ
                if 'order_type' in fields_name:
                    res[move.id]['order_type'] = order.internal_type
        
        return res
    
    _columns = {
        'order_priority': fields.function(_get_order_information, method=True, string='Priority', type='selection', 
                                          selection=ORDER_PRIORITY, multi='move_order'),
        'order_category': fields.function(_get_order_information, method=True, string='Category', type='selection', 
                                          selection=ORDER_CATEGORY, multi='move_order'),
        'order_type': fields.function(_get_order_information, method=True, string='Order Type', type='selection', 
                                      selection=[('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                                 ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                                 ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                                 ('direct', 'Direct Purchase Order')], multi='move_order'),
    }
    
stock_move()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: