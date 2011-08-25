
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

class stock_partial_picking(osv.osv_memory):
    '''
    add message
    '''
    _inherit = "stock.partial.picking"

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add message
        '''
        if context is None:
            context = {}
        
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)
        message_in = '<label string="You receive %s products, please refer to the appropriate procedure." colspan="4" />'
        message_out = '<label string="You ship %s products, please refer to the appropriate procedure and ensure that the mean of transport is appropriate." colspan="4" />'

        if not picking_ids:
            # not called through an action (e.g. buildbot), return the default.
            return result
        
        type = False
        contains_kc = False
        contains_dg = False
        
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            type = pick.type
            for m in pick.move_lines:
                if m.product_id.heat_sensitive_item:
                    contains_kc = True
                if m.product_id.dangerous_goods:
                    contains_dg = True
            
        if contains_kc and contains_dg:
            fill = 'heat sensitive and dangerous goods'
        elif contains_kc:
            fill = 'heat sensitive'
        elif contains_dg:
            fill = 'dangerous goods'
        else:
            fill = ''
            
        message = message_out
        if type == 'in':
            message = message_in
        
        if fill:
            message = message%fill
        else:
            message = ''

        # add field in arch
        arch = result['arch']
        l = arch.split('<field name="date" invisible="1"/>')
        arch = l[0] + '<field name="date" invisible="1"/>' + message + l[1]
        result['arch'] = arch

        return result

stock_partial_picking()
