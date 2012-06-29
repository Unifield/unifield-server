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

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _name = 'stock.picking'

    def _hook_log_picking_modify_message(self, cr, uid, ids, context=None, message='', pick=False):
        '''
        Possibility to change the message: we want to have only Picking report in the right panel
        '''
        context.update({'picking_screen': True}, {'from_so':True})
        return super(stock_picking, self)._hook_log_picking_modify_message(cr, uid, ids, context=context, message=message, pick=pick)

    def button_remove_line(self, cr, uid, ids, context=None):
        '''
        Remove stock_picking line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        self.unlink(cr, uid, ids, context=context)
        return True

    def _vals_get_sale(self, cr, uid, ids, fields, arg, context=None):
        '''
        get function values
        '''
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False,})
            if obj.sale_id :
                result[obj.id]['sale_id'] = obj.sale_id
        return result

    _columns={
        'sale_id_hidden': fields.function(_vals_get_sale, method=True, type='many2one', relation='sale.order', string='Sale', store=False),
    }

stock_picking()

