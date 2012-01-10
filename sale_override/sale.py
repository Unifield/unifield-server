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
import logging
from workflow.wkf_expr import _eval_expr

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
        partner = False
        res = {}
        
        for sale in self.browse(cr, uid, ids):
            if sale.partner_id:
                partner = partner_obj.browse(cr, uid, [sale.partner_id.id])[0]
            if sale.state != 'draft' and (sale.order_type != 'regular' or (partner and partner.partner_type == 'internal')):
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
                    clause += 'AND inv.state = \'paid\' OR (sale.state != \'draft\' AND (sale.order_type != \'regular\' OR part.partner_type = \'internal\'))'
                else:
                    clause += 'AND inv.state != \'cancel\' AND sale.state != \'cancel\'  AND inv.state <> \'paid\' AND sale.order_type = \'regular\''
                    no_invoiced = True

        cursor.execute('SELECT rel.order_id ' \
                'FROM sale_order_invoice_rel AS rel, account_invoice AS inv, sale_order AS sale, res_partner AS part '+ sale_clause + \
                'WHERE rel.invoice_id = inv.id AND rel.order_id = sale.id AND sale.partner_id = part.id ' + clause)
        res = cursor.fetchall()
        if no_invoiced:
            cursor.execute('SELECT sale.id ' \
                    'FROM sale_order AS sale, res_partner AS part ' \
                    'WHERE sale.id NOT IN ' \
                        '(SELECT rel.order_id ' \
                        'FROM sale_order_invoice_rel AS rel) and sale.state != \'cancel\'' \
                        'AND sale.partner_id = part.id ' \
                        'AND sale.order_type = \'regular\' AND part.partner_type != \'internal\'')
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
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, select=True, domain="[('id', '!=', company_id2)]"),
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
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'company_id2': fields.many2one('res.company','Company',select=1),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': lambda *a: 2,
        'from_yml_test': lambda *a: False,
        'company_id2': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
    }

    def _check_own_company(self, cr, uid, company_id, context={}):
        '''
        Remove the possibility to make a SO to user's company
        '''
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        if company_id == user_company_id:
            raise osv.except_osv(_('Error'), _('You cannot made a sale order to your own company !'))

        return True
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('update_mode') in ['init', 'update']:
            logging.getLogger('init').info('SO: set from yml test to True')
            vals['from_yml_test'] = True

        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request') and not vals.get('procurement_request'):
            self._check_own_company(cr, uid, vals['partner_id'], context=context)

        return super(sale_order, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context={}):
        '''
        Remove the possibility to make a SO to user's company
        '''
        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request'):
            self._check_own_company(cr, uid, vals['partner_id'], context=context)

        return super(sale_order, self).write(cr, uid, ids, vals, context=context)

    def wkf_validated(self, cr, uid, ids, context={}):
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        return True
    
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
            elif not order.from_yml_test:
                self.write(cr, uid, [order.id], {'order_policy': 'manual'})
    
        if lines:
            line_obj.write(cr, uid, lines, {'invoiced': 1})
            
        return super(sale_order, self).action_wait(cr, uid, ids, args)

    def action_purchase_order_create(self, cr, uid, ids, context=None):
        '''
        Create a purchase order as counterpart for the loan.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
            
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
            
        for order in self.browse(cr, uid, ids):
            two_months = today() + RelativeDateTime(months=+2)
            # from yml test is updated according to order value
            values = {'partner_id': order.partner_id.id,
                      'partner_address_id': partner_obj.address_get(cr, uid, [order.partner_id.id], ['contact'])['contact'],
                      'pricelist_id': order.partner_id.property_product_pricelist_purchase.id,
                      'loan_id': order.id,
                      'loan_duration': order.loan_duration,
                      'origin': order.name,
                      'order_type': 'loan',
                      'delivery_requested_date': (today() + RelativeDateTime(months=+order.loan_duration)).strftime('%Y-%m-%d'),
                      'categ': order.categ,
                      'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                      'priority': order.priority,
                      'from_yml_test': order.from_yml_test,
                      }
            order_id = purchase_obj.create(cr, uid, values, context=context)
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

    def _get_reason_type(self, cr, uid, order, context={}):
        r_types = {
            'regular': 'reason_type_deliver_partner', 
            'loan': 'reason_type_loan',
            'donation_st': 'reason_type_donation',
            'donation_exp': 'reason_type_donation_expiry',
        }

        if order.order_type in r_types:
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves',r_types[order.order_type])[1]

        return False
    
    def _hook_ship_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for stock picking creation
        '''
        result = super(sale_order, self)._hook_ship_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
        result['reason_type_id'] = self._get_reason_type(cr, uid, kwargs['order'], context)
        
        return result
    
    def _hook_ship_create_stock_move(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for stock move creation
        '''
        result = super(sale_order, self)._hook_ship_create_stock_move(cr, uid, ids, context=context, *args, **kwargs)
        result['reason_type_id'] = self._get_reason_type(cr, uid, kwargs['order'], context)
        
        return result
    
    def _hook_ship_create_execute_specific_code_01(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to execute specific code at position 01
        '''
        super(sale_order, self)._hook_ship_create_execute_specific_code_01(cr, uid, ids, context=context, *args, **kwargs)
        wf_service = netsvc.LocalService("workflow")
        #order = kwargs['order']
        #proc_id = kwargs['proc_id']
        #if order.procurement_request and order.state == 'progress':
        #    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
        
        return True
    
    def _hook_ship_create_line_condition(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to customize the execution condition
        '''
        line = kwargs['line']
        result = super(sale_order, self)._hook_ship_create_line_condition(cr, uid, ids, context=context, *args, **kwargs)
        result = result and not line.order_id.procurement_request
        return result


    def set_manually_done(self, cr, uid, ids, context={}):
        '''
        Set the sale order and all related documents to done state
        '''
        wf_service = netsvc.LocalService("workflow")

        if isinstance(ids, (int, long)):
            ids = [ids]

        order_lines = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                order_lines.append(line.id)
                if line.procurement_id:
                    # Done procurement
                    wf_service.trg_validate(uid, 'procurement.order', line.procurement_id.id, 'subflow.cancel', cr)
 

            # Done picking
            for pick in order.picking_ids:
                if pick.state not in ('cancel', 'done'):
                    wf_service.trg_validate(uid, 'stock.picking', pick.id, 'manually_done', cr)

            # Done loan counterpart
            if order.loan_id and order.loan_id.state not in ('cancel', 'done') and not context.get('loan_id', False) == order.id:
                loan_context = context.copy()
                loan_context.update({'loan_id': order.id})
                self.pool.get('purchase.order').set_manually_done(cr, uid, order.loan_id.id, context=loan_context)

            # Done invoices
            invoice_error_ids = []
            for invoice in order.invoice_ids:
                if invoice.state == 'draft':
                    wf_service.trg_validate(uid, 'account.invoice', invoice.id, 'invoice_cancel', cr)
                elif invoice.state not in ('cancel', 'done'):
                    invoice_error_ids.append(invoice.id)

            if invoice_error_ids:
                invoices_ref = ' / '.join(x.number for x in self.pool.get('account.invoice').browse(cr, uid, invoice_error_ids, context=context))
                raise osv.except_osv(_('Error'), _('The state of the following invoices cannot be updated automatically. Please cancel them manually or d    iscuss with the accounting team to solve the problem.' \
                            'Invoices references : %s') % invoices_ref)            

        # Done stock moves
        move_ids = self.pool.get('stock.move').search(cr, uid, [('sale_line_id', 'in', order_lines), ('state', 'not in', ('cancel', 'done'))], context=context)
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, context=context)

        # Detach the PO from his workflow and set the state to done
        for order_id in ids:
            wf_service.trg_delete(uid, 'sale.order', order_id, cr)
            # Search the method called when the workflow enter in last activity
            wkf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sale', 'act_done')[1]
            activity = self.pool.get('workflow.activity').browse(cr, uid, wkf_id, context=context)
            res = _eval_expr(cr, [uid, 'sale.order', order_id], False, activity.action)

        return True

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
