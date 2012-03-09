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
from tools.translate import _

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    _columns = {
        'cross_docking_ok': fields.boolean('Cross docking?'),
        'stock_location_id': fields.many2one('stock.location','Location'),
    }
    
    def onchange_cross_docking_ok(self, cr, uid, ids, cross_docking_ok, context=None):
        """ Finds location id for changed cross_docking_ok.
        @param cross_docking_ok: Changed value of cross_docking_ok.
        @return: Dictionary of values.
        """
        if cross_docking_ok:
            w = self.pool.get('stock.location').search(cr, uid, [('name', '=', 'Cross docking')], context=context)
            v = {'stock_location_id': w}
        elif cross_docking_ok == False:
            v = {'stock_location_id': False}
        return {'value': v}
        return {}
    
    def test_cross_docking_ok(self, cr, uid, ids):
        """ Tests whether cross docking is True or False.
        @return: True or False
        """
        for order in self.browse(cr, uid, ids):
            return order.cross_docking_ok

#    def _hook_action_picking_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
#        '''
#        modify data for stock move creation
#        - location_dest_id is set to Cross docking
#        '''
#        if context is None:
#            context = {}
#        move_values = super(purchase_order, self)._hook_action_picking_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
#        w = self.pool.get('stock.location').search(cr, uid, [('name', '=', 'Cross docking')], context=context)
#        move_values.update({'location_dest_id': w,})
#        return move_values


#    def action_picking_create(self, cr, uid, ids, context=None):
#        '''
#        Checks if the the option Cross Docking has been chosen
#        '''
#        if context is None:
#            context = {}
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#        
#        for order in self.browse(cr, uid, ids, context=context):
#            if order.cross_docking_ok:
#                self.
#            
#        return super(purchase_order, self).action_picking_create(cr, uid, ids, context=context)
purchase_order()