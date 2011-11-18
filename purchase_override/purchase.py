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
from tools.translate import _
import netsvc

from mx.DateTime import *

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def copy(self, cr, uid, id, default, context={}):
        '''
        Remove loan_id field on new purchase.order
        '''
        return super(purchase_order, self).copy(cr, uid, id, default={'loan_id': False}, context=context)
    
    # @@@purchase.purchase_order._invoiced
    def _invoiced(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            invoiced = False
            if purchase.invoiced_rate == 100.00:
                invoiced = True
            res[purchase.id] = invoiced
        return res
    # @@@end
    
    # @@@purchase.purchase_order._shipped_rate
    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            if purchase.state != 'draft' and ((purchase.order_type == 'regular' and purchase.partner_id.partner_type == 'internal') or \
                purchase.order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']):
                res[purchase.id] = 100.0
            else:
                tot = 0.0
                for invoice in purchase.invoice_ids:
                    if invoice.state not in ('draft','cancel'):
                        tot += invoice.amount_untaxed
                if purchase.amount_untaxed:
                    res[purchase.id] = min(100.0, tot * 100.0 / (purchase.amount_untaxed))
                else:
                    res[purchase.id] = 0.0
        return res
    # @@@end
    
    _columns = {
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                        ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                        ('direct', 'Direct Purchase Order')], string='Order Type', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'loan_id': fields.many2one('sale.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'details': fields.char(size=30, string='Details', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'invoiced': fields.function(_invoiced, method=True, string='Invoiced & Paid', type='boolean', help="It indicates that an invoice has been paid"),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': 2,
    }
    
    def onchange_internal_type(self, cr, uid, ids, order_type, partner_id):
        '''
        Changes the invoice method of the purchase order according to
        the choosen order type
        Changes the partner to local market if the type is Purchase List
        '''
        partner_obj = self.pool.get('res.partner')
        v = {}
        local_market = None
        
        # Search the local market partner id
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj.search(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'), ('name', '=', 'res_partner_local_market')] )
        if data_id:
            local_market = data_obj.read(cr, uid, data_id, ['res_id'])[0]['res_id']
        
        if order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']:
            v['invoice_method'] = 'manual'

        if partner_id and partner_id != local_market:
            partner = partner_obj.browse(cr, uid, partner_id)
            if partner.partner_type == 'internal' and order_type == 'regular':
                v['invoice_method'] = 'manual'
        elif partner_id and partner_id == local_market and order_type != 'purchase_list':
            v['partner_id'] = None
            v['dest_address_id'] = None
            v['partner_address_id'] = None
            v['pricelist_id'] = None
            
        if order_type == 'purchase_list':
            if local_market:
                partner = self.pool.get('res.partner').browse(cr, uid, local_market)
                v['partner_id'] = partner.id
                if partner.address:
                    v['dest_address_id'] = partner.address[0].id
                    v['partner_address_id'] = partner.address[0].id
                if partner.property_product_pricelist_purchase:
                    v['pricelist_id'] = partner.property_product_pricelist_purchase.id
        
        return {'value': v}
    
    def onchange_partner_id(self, cr, uid, ids, part):
        '''
        Fills the Requested and Confirmed delivery dates
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)
        
        if part:
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.browse(cr, uid, part)
            if partner.partner_type == 'internal':
                res['value']['invoice_method'] = 'manual'
        
        return res
    
    def wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        Checks if the invoice should be create from the purchase order
        or not
        '''
        line_obj = self.pool.get('purchase.order.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for order in self.browse(cr, uid, ids):
            if order.partner_id.partner_type == 'internal' and order.order_type == 'regular' or \
                         order.order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']:
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
                line_obj.write(cr, uid, [x.id for x in order.order_line], {'invoiced': 1})
            
        return super(purchase_order, self).wkf_approve_order(cr, uid, ids, context=context)
    
    def action_sale_order_create(self, cr, uid, ids, context={}):
        '''
        Create a sale order as counterpart for the loan.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        sale_shop = self.pool.get('sale.shop')
        partner_obj = self.pool.get('res.partner')
            
        for order in self.browse(cr, uid, ids):
            loan_duration = Parser.DateFromString(order.minimum_planned_date) + RelativeDateTime(months=+order.loan_duration)
            order_id = sale_obj.create(cr, uid, {'shop_id': sale_shop.search(cr, uid, [])[0],
                                                 'partner_id': order.partner_id.id,
                                                 'partner_order_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['contact'])['contact'],
                                                 'partner_invoice_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['invoice'])['invoice'],
                                                 'partner_shipping_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['delivery'])['delivery'],
                                                 'pricelist_id': order.partner_id.property_product_pricelist.id,
                                                 'loan_id': order.id,
                                                 'loan_duration': order.loan_duration,
                                                 'origin': order.name,
                                                 'order_type': 'loan',
                                                 'delivery_requested_date': loan_duration.strftime('%Y-%m-%d'),
                                                 'categ': order.categ,
                                                 'priority': order.priority,})
            for line in order.order_line:
                sale_line_obj.create(cr, uid, {'product_id': line.product_id and line.product_id.id or False,
                                               'product_uom': line.product_uom.id,
                                               'order_id': order_id,
                                               'price_unit': line.price_unit,
                                               'product_uom_qty': line.product_qty,
                                               'date_planned': loan_duration.strftime('%Y-%m-%d'),
                                               'delay': 60.0,
                                               'name': line.name,
                                               'type': line.product_id.procure_method})
            self.write(cr, uid, [order.id], {'loan_id': order_id})
            
            sale = sale_obj.browse(cr, uid, order_id)
            
            message = _("Loan counterpart '%s' was created.") % (sale.name,)
            
            sale_obj.log(cr, uid, order_id, message)
        
        return order_id
    
    def has_stockable_product(self,cr, uid, ids, *args):
        '''
        Override the has_stockable_product to return False
        when the order_type of the order is 'direct'
        '''
        # TODO: See with Synchro team which object the system will should create
        # to have an Incoming Movement in the destination instance
        for order in self.browse(cr, uid, ids):
            if order.order_type != 'direct':
                return super(purchase_order, self).has_stockable_product(cr, uid, ids, args)
        
        return False
    
    def action_invoice_create(self, cr, uid, ids, *args):
        '''
        Override this method to check the purchase_list box on invoice
        when the invoice comes from a purchase list
        '''
        invoice_id = super(purchase_order, self).action_invoice_create(cr, uid, ids, args)
        invoice_obj = self.pool.get('account.invoice')
        
        for order in self.browse(cr, uid, ids):
            if order.order_type == 'purchase_list':
                invoice_obj.write(cr, uid, [invoice_id], {'purchase_list': 1})
        
        return invoice_id
    
    # @@@override@purchase.purchase.order.action_picking_create
    def action_picking_create(self,cr, uid, ids, context={}, *args):
        picking_id = False
        for order in self.browse(cr, uid, ids):
            loc_id = order.partner_id.property_stock_supplier.id
            istate = 'none'
            reason_type_id = False
            if order.invoice_method=='picking':
                istate = '2binvoiced'
                
            pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.in')
            picking_values = {
                'name': pick_name,
                'origin': order.name+((order.origin and (':'+order.origin)) or ''),
                'type': 'in',
                'address_id': order.dest_address_id.id or order.partner_address_id.id,
                'invoice_state': istate,
                'purchase_id': order.id,
                'company_id': order.company_id.id,
                'move_lines' : [],
            }
            
            if order.order_type in ('regular', 'purchase_list', 'direct'):
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
            if order.order_type == 'loan':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
            if order.order_type == 'donation_st':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
            if order.order_type == 'donation_exp':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
            if order.order_type == 'in_kind':
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_in_kind_donation')[1]
                
            if reason_type_id:
                picking_values.update({'reason_type_id': reason_type_id})
            
            picking_id = self.pool.get('stock.picking').create(cr, uid, picking_values, context=context)
            todo_moves = []
            for order_line in order.order_line:
                if not order_line.product_id:
                    continue
                if order_line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    dest = order.location_id.id
                    move_values = {
                        'name': order.name + ': ' +(order_line.name or ''),
                        'product_id': order_line.product_id.id,
                        'product_qty': order_line.product_qty,
                        'product_uos_qty': order_line.product_qty,
                        'product_uom': order_line.product_uom.id,
                        'product_uos': order_line.product_uom.id,
                        'date': order_line.date_planned,
                        'date_expected': order_line.date_planned,
                        'location_id': loc_id,
                        'location_dest_id': dest,
                        'picking_id': picking_id,
                        'move_dest_id': order_line.move_dest_id.id,
                        'state': 'draft',
                        'purchase_line_id': order_line.id,
                        'company_id': order.company_id.id,
                        'price_unit': order_line.price_unit
                    }
                    
                    if reason_type_id:
                        move_values.update({'reason_type_id': reason_type_id})
                    
                    move = self.pool.get('stock.move').create(cr, uid, move_values, context=context)
                    if order_line.move_dest_id:
                        self.pool.get('stock.move').write(cr, uid, [order_line.move_dest_id.id], {'location_id':order.location_id.id})
                    todo_moves.append(move)
            self.pool.get('stock.move').action_confirm(cr, uid, todo_moves)
            self.pool.get('stock.move').force_assign(cr, uid, todo_moves)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
        # @@@end
    
purchase_order()

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'
    
    _columns = {
        'purchase_list': fields.boolean(string='Purchase List ?', help='Check this box if the invoice comes from a purchase list', readonly=True, states={'draft':[('readonly',False)]}),
    }
    
account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
