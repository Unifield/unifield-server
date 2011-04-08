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
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from mx.DateTime import *
from tools.translate import _ 

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    _columns = {
        'internal_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation (for help)'), ('loan', 'Loan'),], 
                                        string='Order Type', required=True),
        'loan_id': fields.many2one('purchase.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority'),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True),
        'details': fields.char(size=30, string='Details'),
    }
    
    _defaults = {
        'internal_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'mixed',
    }
    
    def action_wait(self, cr, uid, ids, *args):
        '''
        Checks if the invoice should be create from the sale order
        or not
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for order in self.browse(cr, uid, ids):
            if order.partner_id.partner_type == 'internal' and order.internal_type == 'regular':
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
            elif order.internal_type in ['donation_exp', 'donation_st', 'loan']:
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
            
        return super(sale_order, self).action_wait(cr, uid, ids, args)

    # @@@override@sale.sale.order.action_ship_create
    def action_ship_create(self, cr, uid, ids, *args):
        wf_service = netsvc.LocalService("workflow")
        picking_id = False
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        model_obj = self.pool.get('ir.model.data')
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        loss_ids = model_obj.search(cr, uid, [('module', '=', 'stock_inventory_type'),
                                              ('model', '=', 'stock.adjustment.type'),
                                              ('name', '=', 'adjustment_type_loss')])
        loss_id = model_obj.read(cr, uid, loss_ids, ['res_id'])[0]['res_id']
        
        for order in self.browse(cr, uid, ids, context={}):
            proc_ids = []
            output_id = order.shop_id.warehouse_id.lot_output_id.id
            picking_id = False
            for line in order.order_line:
                proc_id = False
                date_planned = datetime.now() + relativedelta(days=line.delay or 0.0)
                date_planned = (date_planned - timedelta(days=company.security_lead)).strftime('%Y-%m-%d %H:%M:%S')

                if line.state == 'done':
                    continue
                move_id = False
                if line.product_id and line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    location_id = order.shop_id.warehouse_id.lot_stock_id.id
                    if not picking_id:
                        pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.out')
                        picking_id = self.pool.get('stock.picking').create(cr, uid, {
                            'name': pick_name,
                            'origin': order.name,
                            'type': 'out',
                            'state': 'auto',
                            'move_type': order.picking_policy,
                            'sale_id': order.id,
                            'address_id': order.partner_shipping_id.id,
                            'note': order.note,
                            'invoice_state': (order.order_policy=='picking' and '2binvoiced') or 'none',
                            'company_id': order.company_id.id,
                        })
                    move_id = self.pool.get('stock.move').create(cr, uid, {
                        'name': line.name[:64],
                        'type_id': order.internal_type == 'donation_exp' and loss_id or False,
                        'picking_id': picking_id,
                        'product_id': line.product_id.id,
                        'date': date_planned,
                        'date_expected': date_planned,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'product_packaging': line.product_packaging.id,
                        'address_id': line.address_allotment_id.id or order.partner_shipping_id.id,
                        'location_id': location_id,
                        'location_dest_id': output_id,
                        'sale_line_id': line.id,
                        'tracking_id': False,
                        'state': 'draft',
                        #'state': 'waiting',
                        'note': line.notes,
                        'company_id': order.company_id.id,
                    })

                if line.product_id:
                    proc_id = self.pool.get('procurement.order').create(cr, uid, {
                        'name': line.name,
                        'origin': order.name,
                        'date_planned': date_planned,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                                or line.product_uom_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'move_id': move_id,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                        'company_id': order.company_id.id,
                    })
                    proc_ids.append(proc_id)
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'procurement_id': proc_id})
                    if order.state == 'shipping_except':
                        for pick in order.picking_ids:
                            for move in pick.move_lines:
                                if move.state == 'cancel':
                                    mov_ids = move_obj.search(cr, uid, [('state', '=', 'cancel'),('sale_line_id', '=', line.id),('picking_id', '=', pick.id)])
                                    if mov_ids:
                                        for mov in move_obj.browse(cr, uid, mov_ids):
                                            move_obj.write(cr, uid, [move_id], {'product_qty': mov.product_qty, 'product_uos_qty': mov.product_uos_qty})
                                            proc_obj.write(cr, uid, [proc_id], {'product_qty': mov.product_qty, 'product_uos_qty': mov.product_uos_qty})

            val = {}

            if picking_id:
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            for proc_id in proc_ids:
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)

            if order.state == 'shipping_except':
                val['state'] = 'progress'
                val['shipped'] = False

                if (order.order_policy == 'manual'):
                    for line in order.order_line:
                        if (not line.invoiced) and (line.state not in ('cancel', 'draft')):
                            val['state'] = 'manual'
                            break
            self.write(cr, uid, [order.id], val)
        return True
    # @@@end
    
    def action_purchase_order_create(self, cr, uid, ids, context={}):
        '''
        Create a purchase order as counterpart for the loan.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
            
        for order in self.browse(cr, uid, ids):
            two_months = today() + RelativeDateTime(months=+2)
            order_id = purchase_obj.create(cr, uid, {'partner_id': order.partner_id.id,
                                                 'partner_address_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['contact'])['contact'],
                                                 'pricelist_id': order.partner_id.property_product_pricelist_purchase.id,
                                                 'loan_id': order.id,
                                                 'origin': order.name,
                                                 'internal_type': 'loan',
                                                 'delivery_requested_date': two_months.strftime('%Y-%m-%d'),
                                                 'categ': order.categ,
                                                 'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                                                 'priority': order.priority,})
            for line in order.order_line:
                purchase_line_obj.create(cr, uid, {'product_id': line.product_id and line.product_id.id or False,
                                                   'product_uom': line.product_uom.id,
                                                   'order_id': order_id,
                                                   'price_unit': line.price_unit,
                                                   'product_qty': line.product_uom_qty,
                                                   'date_planned': two_months.strftime('%Y-%m-%d'),
                                                   'name': line.name,})
            self.write(cr, uid, [order.id], {'loan_id': order_id})
            
            purchase = purchase_obj.browse(cr, uid, order_id)
            
            message = _("Loan counterpart '%s' is created.") % (purchase.name,)
            
            self.log(cr, uid, order.id, message)
        
        return order_id
    
    def has_stockable_products(self, cr, uid, ids, *args):
        '''
        Override the has_stockable_product to return False
        when the internal_type of the order is 'direct'
        '''
        for order in self.browse(cr, uid, ids):
            if order.internal_type != 'direct':
                return super(sale_order, self).has_stockable_product(cr, uid, ids, args)
        
        return False
    
#    def shipping_policy_change(self, cr, uid, ids, order_policy, internal_type=False, partner_id=False, field=False, context={}):
#        '''
#        Display a message if the error tries to associate an internal type with an incompatible
#        order policy
#        '''
#        qty = False
#        partner = False
#        error = False
#        message = {}
#        res = {}
#        
#        # Get super values
#        res2 = super(sale_order, self).shipping_policy_change(cr, uid, ids, order_policy, context=context)
#        if res2 and 'value' in res2 and 'invoice_quantity' in res2['value']:
#            qty = res2['value']['invoice_quantity']
#        
#        # Get partne information
#        if partner_id:
#            partner= self.pool.get('res.partner').browse(cr, uid, [partner_id])[0]
#        
#        # Tests
#        if order_policy != 'manual':
#            if internal_type == 'regular' and partner and partner.partner_type == 'internal':
#                message = {'title': _('Error'),
#                           'message': _('You cannot define an automatic invoicing policy with an internal partner for a regular order !')}
#                error = True
#            elif internal_type != 'regular':
#                message = {'title': _('Error'), 
#                           'message': _('You cannot define an automatic invoicing policy for a non-regular order !')}
#                error = True
#        
#        # Displaying
#        if error and field and field == 'internal_type':
#            res = {'value': {'internal_type': 'regular'},
#                   'warning': message,}
#        elif error and field and field == 'order_policy':
#            res = {'value': {'order_policy': 'manual'},
#                   'warning': message}
#        if qty and 'value' in res:
#            res['value'].update({'invoice_quantity': qty})
#        elif qty:
#            res = {'value': {'invoice_quantity': qty}}
#            
#        return res
    
sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: