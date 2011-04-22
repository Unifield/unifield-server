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

    def copy(self, cr, uid, id, default, context={}):
        '''
        Delete the loan_id field on the new sale.order
        '''
        return super(sale_order, self).copy(cr, uid, id, default={'loan_id': False}, context=context)
    
    #@@@override sale.sale_order._invoiced
    def _invoiced(self, cr, uid, ids, name, arg, context={}):
        '''
        Return True is the sale order is an uninvoiced order
        '''
        partner_obj = self.pool.get('res.partner')
        res = {}
        
        for sale in self.browse(cr, uid, ids):
            partner = partner_obj.browse(cr, uid, [sale.partner_id.id])[0]
            if sale.order_type != 'regular' or (partner and partner.partner_type == 'internal'):
                res[sale.id] = True
            else:
                res[sale.id] = True
                for invoice in sale.invoice_ids:
                    if invoice.state != 'paid':
                        res[sale.id] = False
                        break
                if not sale.invoice_ids:
                    res[sale.id] = False
        return res
    #@@@end
    
    #@@@override sale.sale_order._invoiced_search
    def _invoiced_search(self, cursor, user, obj, name, args, context={}):
        if not len(args):
            return []
        clause = ''
        sale_clause = ''
        no_invoiced = False
        for arg in args:
            if arg[1] == '=':
                if arg[2]:
                    clause += 'AND inv.state = \'paid\''
                else:
                    clause += 'AND inv.state != \'cancel\' AND sale.state != \'cancel\'  AND inv.state <> \'paid\'  AND rel.order_id = sale.id '
                    sale_clause = ',  sale_order AS sale '
                    no_invoiced = True

        cursor.execute('SELECT rel.order_id ' \
                'FROM sale_order_invoice_rel AS rel, account_invoice AS inv '+ sale_clause + \
                'WHERE rel.invoice_id = inv.id ' + clause)
        res = cursor.fetchall()
        if no_invoiced:
            cursor.execute('SELECT sale.id ' \
                    'FROM sale_order AS sale ' \
                    'WHERE sale.id NOT IN ' \
                        '(SELECT rel.order_id ' \
                        'FROM sale_order_invoice_rel AS rel) and sale.state != \'cancel\'')
            res.extend(cursor.fetchall())
        if not res:
            return [('id', '=', 0)]
        return [('id', 'in', [x[0] for x in res])]
    #@@@end
    
    #@@@override sale.sale_order._invoiced_rate
    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for sale in self.browse(cursor, user, ids, context=context):
            if sale.invoiced:
                res[sale.id] = 100.0
                continue
            tot = 0.0
            for invoice in sale.invoice_ids:
                if invoice.state not in ('draft', 'cancel'):
                    tot += invoice.amount_untaxed
            if tot:
                res[sale.id] = min(100.0, tot * 100.0 / (sale.amount_untaxed or 1.00))
            else:
                res[sale.id] = 0.0
        return res
    #@@@end
    
    def _get_noinvoice(self, cr, uid, ids, name, arg, context={}):
        res = {}
        for sale in self.browse(cr, uid, ids):
            res[sale.id] = sale.order_type != 'regular' or sale.partner_id.partner_type == 'internal'
        return res
    
    _columns = {
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation (for help)'), ('loan', 'Loan'),], 
                                        string='Order Type', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'loan_id': fields.many2one('purchase.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True, states={'draft': [('readonly', False)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'details': fields.char(size=30, string='Details', readonly=True, states={'draft': [('readonly', False)]}),
        'invoiced': fields.function(_invoiced, method=True, string='Paid',
            fnct_search=_invoiced_search, type='boolean', help="It indicates that an invoice has been paid."),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'noinvoice': fields.function(_get_noinvoice, method=True, string="Don't create an invoice", type='boolean'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', readonly=True, states={'draft': [('readonly', False)]}),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'mixed',
        'loan_duration': lambda *a: 2,
    }
    

    
    def action_wait(self, cr, uid, ids, *args):
        '''
        Checks if the invoice should be create from the sale order
        or not
        '''
        line_obj = self.pool.get('sale.order.line')
        lines = []
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for order in self.browse(cr, uid, ids):
            if order.partner_id.partner_type == 'internal' and order.order_type == 'regular':
                self.write(cr, uid, [order.id], {'order_policy': 'manual'})
                for line in order.order_line:
                    lines.append(line.id)
            elif order.order_type in ['donation_exp', 'donation_st', 'loan']:
                self.write(cr, uid, [order.id], {'order_policy': 'manual'})
                for line in order.order_line:
                    lines.append(line.id)
                    
        line_obj.write(cr, uid, lines, {'invoiced': 1})
            
        return super(sale_order, self).action_wait(cr, uid, ids, args)

    def action_ship_create(self, cr, uid, ids, *args, **kwargs):
        model_obj = self.pool.get('ir.model.data')
        loss_ids = model_obj.search(cr, uid, [('module', '=', 'stock_inventory_type'),
                                              ('model', '=', 'stock.adjustment.type'),
                                              ('name', '=', 'adjustment_type_loss')])
        kwargs['loss_id'] = model_obj.read(cr, uid, loss_ids, ['res_id'])[0]['res_id']
        return super(sale_order, self).action_ship_create(cr, uid, ids, *args, **kwargs)

    def _hook_ship_create_stock_move(self, cr, uid, ids, move_data, order_line, *args, **kwargs):
        if order_line.order_id.order_type == 'donation_exp' and kwargs.get('loss_id'):
            move_data['type_id'] = kwargs['loss_id']
        return super(sale_order, self)._hook_ship_create_stock_move(cr, uid, ids, move_data, order_line, *args, **kwargs)
    
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
                                                 'loan_duration': order.loan_duration,
                                                 'origin': order.name,
                                                 'order_type': 'loan',
                                                 'delivery_requested_date': (today() + RelativeDateTime(months=+order.loan_duration)).strftime('%Y-%m-%d'),
                                                 'categ': order.categ,
                                                 'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                                                 'priority': order.priority,})
            for line in order.order_line:
                purchase_line_obj.create(cr, uid, {'product_id': line.product_id and line.product_id.id or False,
                                                   'product_uom': line.product_uom.id,
                                                   'order_id': order_id,
                                                   'price_unit': line.price_unit,
                                                   'product_qty': line.product_uom_qty,
                                                   'date_planned': (today() + RelativeDateTime(months=+order.loan_duration)).strftime('%Y-%m-%d'),
                                                   'name': line.name,})
            self.write(cr, uid, [order.id], {'loan_id': order_id})
            
            purchase = purchase_obj.browse(cr, uid, order_id)
            
            message = _("Loan counterpart '%s' is created.") % (purchase.name,)
            
            purchase_obj.log(cr, uid, order_id, message)
        
        return order_id
    
    def has_stockable_products(self, cr, uid, ids, *args):
        '''
        Override the has_stockable_product to return False
        when the internal_type of the order is 'direct'
        '''
        for order in self.browse(cr, uid, ids):
            if order.order_type != 'direct':
                return super(sale_order, self).has_stockable_product(cr, uid, ids, args)
        
        return False
    
    #@@@override sale.sale_order.action_invoice_end
    def action_invoice_end(self, cr, uid, ids, context=None):
        ''' 
        Modified to set lines invoiced when order_type is not regular
        '''
        for order in self.browse(cr, uid, ids, context=context):
            #
            # Update the sale order lines state (and invoiced flag).
            #
            for line in order.order_line:
                vals = {}
                #
                # Check if the line is invoiced (has asociated invoice
                # lines from non-cancelled invoices).
                #
                invoiced = order.noinvoice
                if not invoiced:
                    for iline in line.invoice_lines:
                        if iline.invoice_id and iline.invoice_id.state != 'cancel':
                            invoiced = True
                            break
                if line.invoiced != invoiced:
                    vals['invoiced'] = invoiced
                # If the line was in exception state, now it gets confirmed.
                if line.state == 'exception':
                    vals['state'] = 'confirmed'
                # Update the line (only when needed).
                if vals:
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], vals, context=context)
            #
            # Update the sales order state.
            #
            if order.state == 'invoice_except':
                self.write(cr, uid, [order.id], {'state': 'progress'}, context=context)
        return True
        #@@@end

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
