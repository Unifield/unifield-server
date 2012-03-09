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
    }
    
    def onchange_cross_docking_ok(self, cr, uid, ids, cross_docking_ok, context=None):
        """ Finds location id for changed cross_docking_ok.
        @param cross_docking_ok: Changed value of cross_docking_ok.
        @return: Dictionary of values.
        """
        obj_data = self.pool.get('ir.model.data')
        if cross_docking_ok:
            l = obj_data.get_object_reference(cr, uid, 'stock', 'stock_location_cross_docking')[1]
        elif cross_docking_ok == False:
            l = obj_data.get_object_reference(cr, uid, 'msf_profile', 'stock_location_input')[1]
        return {'value': {'location_id': l}}
    
    def test_cross_docking_ok(self, cr, uid, ids):
        """ Tests whether cross docking is True or False.
        @return: True or False
        """
        for order in self.browse(cr, uid, ids):
            return order.cross_docking_ok
purchase_order()

#class procurement_order(osv.osv):
#    '''
#    date modifications
#    '''
#    _inherit = 'procurement.order'
#    
#    def po_line_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
#        '''
#        Please copy this to your module's method also.
#        This hook belongs to the make_po method from purchase>purchase.py>procurement_order
#        
#        - allow to modify the data for purchase order line creation
#        '''
#        if context is None:
#            context = {}
#        line = super(procurement_order, self).po_line_values_hook(cr, uid, ids, context=context, *args, **kwargs)
#        procurement = kwargs['procurement']
#        # date_planned (requested date) = date_planned from procurement order (rts - prepartion lead time)
#        # confirmed_delivery_date (confirmed date) = False
#        line.update({'date_planned': procurement.date_planned, 'confirmed_delivery_date': False,})
#        return line
#    
#    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
#        '''
#        Please copy this to your module's method also.
#        This hook belongs to the make_po method from purchase>purchase.py>procurement_order
#        
#        - allow to modify the data for purchase order creation
#        '''
#        if context is None:
#            context = {}
#        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
#        line = kwargs['line']
#        procurement = kwargs['procurement']
#        # update from yml flag
#        values['from_yml_test'] = procurement.from_yml_test
#        # date_planned (requested date) = date_planned from procurement order (rts - prepartion lead time)
#        # confirmed_delivery_date (confirmed date) = False
#        # both values are taken from line 
#        values.update({'delivery_requested_date': line['date_planned'], 'delivery_confirmed_date': line['confirmed_delivery_date'],})
#        return values  
#
#procurement_order()