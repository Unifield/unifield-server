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
from osv import osv, fields
from lxml import etree

class sale_order_rw(osv.osv):
    _inherit = "sale.order"

    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(sale_order_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type,so_po_common.REMOTE_WAREHOUSE)

sale_order_rw()

class purchase_order_rw(osv.osv):
    _inherit = "purchase.order"

    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(purchase_order_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type,so_po_common.REMOTE_WAREHOUSE)
    
purchase_order_rw()

class tender_rw(osv.osv):
    _inherit = 'tender'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(tender_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.REMOTE_WAREHOUSE)
    
tender_rw()
    
class real_average_consumption_rw(osv.osv):
    _name = 'real.average.consumption'
    _inherit = 'real.average.consumption'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(real_average_consumption_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.CENTRAL_PLATFORM)
    
real_average_consumption_rw()

'''
The following 4 objects must have no new nor duplicate buttons in the view in Remote Wareshouse instances
'''

class stock_warehouse_orderpoint_rw(osv.osv):
    _inherit = 'stock.warehouse.orderpoint'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(stock_warehouse_orderpoint_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.REMOTE_WAREHOUSE)
    
stock_warehouse_orderpoint_rw()

class threshold_value_rw(osv.osv):
    _inherit = 'threshold.value'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(threshold_value_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.REMOTE_WAREHOUSE)
    
threshold_value_rw()

class stock_warehouse_order_cycle_rw(osv.osv):
    _inherit = 'stock.warehouse.order.cycle'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(stock_warehouse_order_cycle_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.REMOTE_WAREHOUSE)
    
stock_warehouse_order_cycle_rw()

class stock_warehouse_automatic_supply_rw(osv.osv):
    _inherit = 'stock.warehouse.automatic.supply'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(stock_warehouse_automatic_supply_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.REMOTE_WAREHOUSE)
    
stock_warehouse_automatic_supply_rw()


#US-702: remove buttons in some more views
class stock_inventory_rw(osv.osv):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(stock_inventory_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.CENTRAL_PLATFORM)
    
stock_inventory_rw()

class initial_stock_inventory_rw(osv.osv):
    _name = 'initial.stock.inventory'
    _inherit = 'initial.stock.inventory'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(initial_stock_inventory_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.CENTRAL_PLATFORM)
    
initial_stock_inventory_rw()

class res_partner_rw(osv.osv):
    _name = 'res.partner'
    _inherit = 'res.partner'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(res_partner_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.REMOTE_WAREHOUSE)
    
res_partner_rw()


class stock_picking_out_rw(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(stock_picking_out_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        
        if view_type in ['tree','form'] and 'out' in res['name']:
            return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.CENTRAL_PLATFORM)
        return res
    
stock_picking_out_rw()

class pack_type_rw(osv.osv):
    _name = 'pack.type'
    _inherit = 'pack.type'
    
    # Do not show the button new, duplicate in the tree and form view
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        so_po_common = self.pool.get('so.po.common')
        res = super(pack_type_rw, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar,submenu=False)
        return so_po_common.rw_view_remove_buttons(cr, uid, res, view_type, so_po_common.CENTRAL_PLATFORM)
    
pack_type_rw()



