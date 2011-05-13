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
from tools.translate import _

class procurement_request(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    _columns = {
        'requestor': fields.char(size=128, string='Requestor'),
        'procurement_request': fields.boolean(string='Procurement Request', readonly=True),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'origin': fields.char(size=64, string='Origin'),
        'notes': fields.text(string='Notes'),
        
        # Remove readonly parameter from sale.order class
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=False, change_default=True, select=True),
        'partner_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=False, states={'draft': [('readonly', False)]}, help="Invoice address for current sales order."),
        'partner_order_id': fields.many2one('res.partner.address', 'Ordering Contact', readonly=True, required=False, states={'draft': [('readonly', False)]}, help="The name and address of the contact who requested the order or quotation."),
        'partner_shipping_id': fields.many2one('res.partner.address', 'Shipping Address', readonly=True, required=False, states={'draft': [('readonly', False)]}, help="Shipping address for current sales order."),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=False, readonly=True, states={'draft': [('readonly', False)]}, help="Pricelist for current sales order."),
        'state': fields.selection([
            ('procurement', 'Internal Supply Requirement'),
            ('proc_progress', 'In Progress'),
            ('proc_cancel', 'Cancelled'),
            ('proc_done', 'Done'),
            ('draft', 'Quotation'),
            ('waiting_date', 'Waiting Schedule'),
            ('manual', 'Manual In Progress'),
            ('progress', 'In Progress'),
            ('shipping_except', 'Shipping Exception'),
            ('invoice_except', 'Invoice Exception'),
            ('done', 'Done'),
            ('cancel', 'Cancelled')
            ], 'Order State', readonly=True, help="Gives the state of the quotation or sales order. \nThe exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'.", select=True),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context: context.get('procurement_request', False) and obj.pool.get('ir.sequence').get(cr, uid, 'procurement.request') or obj.pool.get('ir.sequence').get(cr, uid, 'sale.order'),
        'procurement_request': lambda obj, cr, uid, context: context.get('procurement_request', False),
        'state': lambda self, cr, uid, c: c.get('procurement_request', False) and 'procurement' or 'draft',
    }
    
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
            
        seq_obj = self.pool.get('ir.sequence')
        order = self.browse(cr, uid, id)
        name = (order.procurement_request or context.get('procurement.request', False)) and seq_obj.get(cr, uid, 'procurement.request') or seq_obj.get(cr, uid, 'sale.order')
        proc = order.procurement_request or context.get('procurement.request', False)
            
        default.update({
            'state': 'draft',
            'shipped': False,
            'invoice_ids': [],
            'picking_ids': [],
            'date_confirm': False,
            'name': name,
            'procurement_request': proc,
        })
        
        return super(sale_order, self).copy(cr, uid, id, default, context=context)
    
procurement_request()

class procurement_request_line(osv.osv):
    _name = 'sale.order.line'
    _inherit= 'sale.order.line'
    
    _columns = {
        'procurement_request': fields.boolean(string='Procurement Request', readonly=True),
        'supplier_id': fields.many2one('res.partner', string='Supplier'),
        'latest': fields.char(size=64, string='Latest documents', readonly=True),
    }
    
    _defaults = {
        'procurement_request': lambda self, cr, uid, c: c.get('procurement_request', False),
    }
    
    def requested_product_id_change(self, cr, uid, ids, product_id, context={}):
        '''
        Fills automatically the product_uom_id field on the line when the 
        product was changed.
        '''
        product_obj = self.pool.get('product.product')

        v = {}
        if not product_id:
            v.update({'product_uom': False, 'supplier_id': False})
        else:
            product = product_obj.browse(cr, uid, product_id, context=context)
            v.update({'product_uom': product.uom_id.id, 'supplier_id': product.seller_id.id})

        return {'value': v}
    
procurement_request_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: