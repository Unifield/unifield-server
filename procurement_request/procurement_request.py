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
import decimal_precision as dp

class procurement_request(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Override the method to return 0.0 if the sale.order is a prcourement request
        '''
        res = {}
        new_ids = []
        
        for order in self.browse(cr, uid, ids, context=context):
            if order.procurement_request:
                res[order.id] = {}
                res[order.id]['amount_tax'] = 0.0
                res[order.id]['amount_total'] = 0.0
                res[order.id]['amount_untaxed'] = 0.0
            else:
                new_ids.append(order.id)
                
        res.update(super(procurement_request, self)._amount_all(cr, uid, new_ids, field_name, arg, context=context))
        
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Returns the procurement request search view instead of default sale order search view
        '''
        if not context:
            context = {}
        if view_type == 'search' and context.get('procurement_request') and not view_id:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_search_view')[1]

        return super(procurement_request, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
    
    #@@@ override sale.sale.order._get_order
    # Not modified method, but simply add here to fix an error on amount_total field
    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('sale.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()
    #@@@end override
    
    _columns = {
        'requestor': fields.char(size=128, string='Requestor'),
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'requested_date': fields.date(string='Requested date'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'origin': fields.char(size=64, string='Origin'),
        'notes': fields.text(string='Notes'),
        'order_ids': fields.many2many('purchase.order', 'procurement_request_order_rel',
                                      'request_id', 'order_id', string='Orders', readonly=True),
        
        # Remove readonly parameter from sale.order class
        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft': [('readonly', False)]}),
        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Untaxed Amount',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The amount without tax."),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The tax amount."),
        'amount_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The total amount."),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('waiting_date', 'Waiting Schedule'),
            ('manual', 'Confirmed'),
            ('progress', 'Confirmed'),
            ('validated', 'Validated'),
            ('shipping_except', 'Shipping Exception'),
            ('invoice_except', 'Invoice Exception'),
            ('done', 'Closed'),
            ('cancel', 'Cancelled')
            ], 'Order State', readonly=True, help="Gives the state of the quotation or sales order. \nThe exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'.", select=True),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context: not context.get('procurement_request', False) and obj.pool.get('ir.sequence').get(cr, uid, 'sale.order') or obj.pool.get('ir.sequence').get(cr, uid, 'procurement.request'),
        'procurement_request': lambda obj, cr, uid, context: context.get('procurement_request', False),
        'state': 'draft',
    }

    def create(self, cr, uid, vals, context={}):
        if not context:
            context = {}

        if context.get('procurement_request') or vals.get('procurement_request', False):
            # Get the ISR number
            if not vals.get('name', False):
                vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'procurement.request')})

            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company.partner_id.address:
                address_id = company.partner_id.address[0].id
            else:
                address_id = self.pool.get('res.partner.address').search(cr, uid, [], limit=1)[0]
            vals['partner_id'] = company.partner_id.id
            vals['partner_order_id'] = address_id
            vals['partner_invoice_id'] = address_id
            vals['partner_shipping_id'] = address_id
            vals['delivery_requested_date'] = vals.get('requested_date')
            pl = self.pool.get('product.pricelist').search(cr, uid, [], limit=1)[0]
            vals['pricelist_id'] = pl

        return super(procurement_request, self).create(cr, uid, vals, context)

    def unlink(self, cr, uid, ids, context={}):
        '''
        Changes the state of the order to allow the deletion
        '''
        line_obj = self.pool.get('sale.order.line')
        
        del_ids = []
        normal_ids = []
        
        for request in self.browse(cr, uid, ids, context=context):
            if request.procurement_request and request.state in ['draft', 'cancel']:
                del_ids.append(request.id)
            elif not request.procurement_request:
                normal_ids.append(request.id)
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Internal Request(s) which are already validated !'))
                
        if del_ids:
            osv.osv.unlink(self, cr, uid, del_ids, context=context)
                
        return super(procurement_request, self).unlink(cr, uid, normal_ids, context=context)
    
    def search(self, cr, uid, args=[], offset=0, limit=None, order=None, context={}, count=False):
        '''
        Adds automatically a domain to search only True sale orders if no procurement_request in context
        '''
        test = True
        for a in args:
            if a[0] == 'procurement_request':
                test = False
        
        if not context.get('procurement_request', False) and test:
            args.append(('procurement_request', '=', False))
            
        return super(procurement_request, self).search(cr, uid, args, offset, limit, order, context, count)
    
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
            
        seq_obj = self.pool.get('ir.sequence')
        order = self.browse(cr, uid, id)
        name = (order.procurement_request or context.get('procurement_request', False)) and seq_obj.get(cr, uid, 'procurement.request') or seq_obj.get(cr, uid, 'sale.order')
        proc = order.procurement_request or context.get('procurement_request', False)
            
        default.update({
            'shipped': False,
            'invoice_ids': [],
            'picking_ids': [],
            'date_confirm': False,
            'name': name,
            'procurement_request': proc,
        })
        
        return super(osv.osv, self).copy(cr, uid, id, default, context=context)

    def validate_procurement(self, cr, uid, ids, context={}):
        '''
        Validate the request
        '''
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True
    
    def confirm_procurement(self, cr, uid, ids, context={}):
        '''
        Confirmed the request
        '''
        self.write(cr, uid, ids, {'state': 'progress'}, context=context)
        
        return True
    
    def procurement_done(self, cr, uid, ids, context={}):
        '''
        Creates all procurement orders according to lines
        '''
        self.action_ship_create(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state': 'done'})
        
        return True
    
procurement_request()

class procurement_request_line(osv.osv):
    _name = 'sale.order.line'
    _inherit= 'sale.order.line'
    
    def _amount_line(self, cr, uid, ids, field_name, arg, context={}):
        '''
        Override the method to return 0.0 if the line is a procurement request line
        '''
        res = {}
        new_ids= []
        for line in self.browse(cr, uid, ids):
            if line.order_id.procurement_request:
                res[line.id] = 0.0
            else:
                new_ids.append(line.id)
                
        res.update(super(procurement_request_line, self)._amount_line(cr, uid, new_ids, field_name, arg, context=context))
        
        return res
    
    def create(self, cr, uid, vals, context={}):
        '''
        Adds the date_planned value
        '''
        if context is None:
            context = {}

        if not 'date_planned' in vals and context.get('procurement_request'):
            if 'date_planned' in context:
                vals.update({'date_planned': context.get('date_planned')})
            else:
                date_planned = self.pool.get('sale.order').browse(cr, uid, vals.get('order_id'), context=context).delivery_requested_date
                vals.update({'date_planned': date_planned})
                
        return super(procurement_request_line, self).create(cr, uid, vals, context=context)
    
    _columns = {
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'latest': fields.char(size=64, string='Latest documents', readonly=True),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal', digits_compute= dp.get_precision('Sale Price')),
        'my_company_id': fields.many2one('res.company','Company',select=1),
        'supplier': fields.many2one('res.partner', 'Supplier', domain="[('id', '!=', my_company_id)]"),
    }
    
    def _get_planned_date(self, cr, uid, c={}):
        if c is None:
            c = {}
        if 'procurement_request' in c:
            return c.get('date_planned', False)

        return super(procurement_request_line, self)._get_planned_date(cr, uid, c)

    _defaults = {
        'procurement_request': lambda self, cr, uid, c: c.get('procurement_request', False),
        'date_planned': _get_planned_date,
        'my_company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
    }
    
    def requested_product_id_change(self, cr, uid, ids, product_id, type, context={}):
        '''
        Fills automatically the product_uom_id field on the line when the 
        product was changed.
        '''
        product_obj = self.pool.get('product.product')

        v = {}
        if not product_id:
            v.update({'product_uom': False, 'supplier': False, 'name': ''})
        else:
            product = product_obj.browse(cr, uid, product_id, context=context)
            v.update({'product_uom': product.uom_id.id, 'name': '[%s] %s'%(product.default_code, product.name)})
            if type != 'make_to_stock':
                v.update({'supplier': product.seller_ids and product.seller_ids[0].name.id})

        return {'value': v}
    
procurement_request_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
