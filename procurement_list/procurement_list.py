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

import time
import netsvc

from osv import osv
from osv import fields
from tools.translate import _

class procurement_list(osv.osv):
    _name = 'procurement.list'
    _description = 'Procurement list'

    _columns = {
        'name': fields.char(size=64, string='Ref.', required=True, readonly=True, 
                            states={'draft': [('readonly', False)]}),
        'requestor': fields.char(size=20, string='Requestor',),
        'order_date': fields.date(string='Order date', required=True),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'origin': fields.char(size=64, string='Origin'),
        'state': fields.selection([('draft', 'Draft'),('done', 'Done'), ('cancel', 'Cancel')], 
                                   string='State', readonly=True),
        'line_ids': fields.one2many('procurement.list.line', 'list_id', string='Lines', readonly=True,
                                    states={'draft': [('readonly', False)]}),
        'notes': fields.text(string='Notes'),
        'supplier_ids': fields.many2many('res.partner', 'procurement_list_supplier_rel',
                                         'list_id', 'supplier_id', string='Suppliers',
                                         domain="[('supplier', '=', True)]",
                                         states={'done': [('readonly', True)]}),
        'order_ids': fields.many2many('purchase.order', 'procurement_list_order_rel',
                                      'list_id', 'order_id', string='Orders', readonly=True),
    }

    _defaults = {
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'procurement.list'),
        'state': lambda *a: 'draft',
        'order_date': lambda *a: time.strftime('%Y-%m-%d'),
    }
    
    def copy(self, cr, uid, ids, default={}, context={}):
        '''
        Increments the sequence for the new list
        '''        
        default['name'] = self.pool.get('ir.sequence').get(cr, uid, 'procurement.list')
        default['order_ids'] = []
        
        res = super(procurement_list, self).copy(cr, uid, ids, default, context=context)
        
        return res

    def cancel(self, cr, uid, ids, context={}):
        '''
        Sets the procurement list to the 'Cancel' state
        '''
        self.write(cr, uid, ids, {'state': 'cancel'})

        return True

    def create_rfq(self, cr, uid, ids, context={}):
        ''' 
        Create a RfQ per supplier with all products
        '''
        purchase_obj = self.pool.get('purchase.order')
        line_obj = self.pool.get('purchase.order.line')

        order_ids = []

        for list in self.browse(cr, uid, ids, context=context):
            # Returns an error message if no suppliers or no products
            if not list.supplier_ids or len(list.supplier_ids) == 0:
                raise osv.except_osv(_('Error'), _('No supplier defined for this list !'))
            if not list.line_ids or len(list.line_ids) == 0:
                raise osv.except_osv(_('Error'), _('No line defined for this list !'))

            location_id = self._get_location(cr, uid, list.warehouse_id)
            # Creates a RfQ for each supplier...
            for supplier in list.supplier_ids:
                po_id = purchase_obj.create(cr, uid, {'partner_id': supplier.id,
                                                      'partner_address_id': supplier.address_get().get('default'),
                                                      'pricelist_id': supplier.property_product_pricelist.id,
                                                      'origin': list.name,
                                                      'location_id': location_id})
                order_ids.append(po_id)

                # ... with all lines...
                for line in list.line_ids:
                    # ... which aren't from stock
                    if not line.from_stock:
                        line_obj.create(cr, uid, {'product_uom': line.product_uom_id.id,
                                                  'product_id': line.product_id.id,
                                                  'order_id': po_id,
                                                  'price_unit': 0.00,
                                                  'date_planned': list.order_date,
                                                  'product_qty': line.product_qty,
                                                  'procurement_line_id': line.id,
                                                  'name': line.product_id.name,})
                    self.pool.get('procurement.list.line').write(cr, uid, line.id, {'latest': 'RfQ In Progress'})

        self.write(cr, uid, ids, {'state': 'done', 'order_ids': [(6, 0, order_ids)]})

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', order_ids)]}

    def reset(self, cr, uid, ids, context={}):
        '''
        Sets the procurement list to the 'Draft' state
        '''
        self.write(cr, uid, ids, {'state': 'draft'})

        return True

    def _get_location(self, cr, uid, warehouse=None):
        '''
        Returns the default input location for product
        '''
        if warehouse:
            return warehouse.lot_input_id.id
        warehouse_obj = self.pool.get('stock.warehouse')
        warehouse_id = warehouse_obj.search(cr, uid, [])[0]
        return warehouse_obj.browse(cr, uid, warehouse_id).lot_input_id.id

procurement_list()


class procurement_list_line(osv.osv):
    _name = 'procurement.list.line'
    _description = 'Procurement line'
    _rec_name = 'product_id'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'product_qty': fields.float(digits=(16,4), string='Quantity', required=True),
        'comment': fields.char(size=128, string='Comment'),
        'from_stock': fields.boolean(string='From stock ?'),
        'latest': fields.char(size=64, string='Latest document', readonly=True),
        'list_id': fields.many2one('procurement.list', string='List', required=True, ondelete='cascade'),
    }
    
    _defaults = {
        'latest': lambda *a: '',
    }
    
    def copy_data(self, cr, uid, id, default={}, context={}):
        '''
        Initializes the 'latest' fields to an empty field
        '''
        default['latest'] = ''
        
        res = super(procurement_list_line, self).copy_data(cr, uid, id, default, context=context)
        
        return res

    def product_id_change(self, cr, uid, ids, product_id, context={}):
        '''
        Fills automatically the product_uom_id field on the line when the 
        product was changed.
        '''
        product_obj = self.pool.get('product.product')

        v = {}
        if not product_id:
            v.update({'product_uom_id': False})
        else:
            product = product_obj.browse(cr, uid, product_id, context=context)
            v.update({'product_uom_id': product.uom_id.id})

        return {'value': v}

procurement_list_line()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'
    
    _columns = {
        'procurement_line_id': fields.many2one('procurement.list.line', string='Procurement Line', readonly=True, ondelete='set null'),
    }
    
    def action_confirm(self, cr, uid, ids, context={}):
        '''
        Changes the status of the procurement line
        '''
        proc_line_obj = self.pool.get('procurement.list.line')
        for line in self.browse(cr, uid, ids):
            if line.procurement_line_id and line.procurement_line_id.id:
                proc_line_obj.write(cr, uid, [line.procurement_line_id.id], {'latest': line.order_id.name})
        
        return super(purchase_order_line, self).action_confirm(cr, uid, ids, context=context)
    
purchase_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

