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
import time
from tools.translate import _ 
import logging
from workflow.wkf_expr import _eval_expr

from sale_override import SALE_ORDER_STATE_SELECTION
from sale_override import SALE_ORDER_SPLIT_SELECTION
from sale_override import SALE_ORDER_LINE_STATE_SELECTION

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        Delete the loan_id field on the new sale.order
        - reset split flag to original value (field order flow) if not in default
        '''
        if context is None:
            context = {}
        if default is None:
            default = {}

        default.update({'loan_id': False,
                        'active': True})
        # if splitting related attributes are not set with default values, we reset their values
        if 'split_type_sale_order' not in default:
            default.update({'split_type_sale_order': 'original_sale_order'})
        if 'original_so_id_sale_order' not in default:
            default.update({'original_so_id_sale_order': False})
        return super(sale_order, self).copy(cr, uid, id, default=default, context=context)

    #@@@override sale.sale_order._invoiced
    def _invoiced(self, cr, uid, ids, name, arg, context=None):
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
    def _invoiced_search(self, cursor, user, obj, name, args, context=None):
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
    
    def _get_noinvoice(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for sale in self.browse(cr, uid, ids):
            res[sale.id] = sale.order_type != 'regular' or sale.partner_id.partner_type == 'internal'
        return res
    
    def _vals_get_sale_override(self, cr, uid, ids, fields, arg, context=None):
        '''
        get function values
        '''
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False})
                
            # state_hidden_sale_order
            result[obj.id]['state_hidden_sale_order'] = obj.state
            if obj.state == 'done' and obj.split_type_sale_order == 'original_sale_order':
                result[obj.id]['state_hidden_sale_order'] = 'split_so'
            
        return result
    
    _columns = {
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, select=True, domain="[('id', '!=', company_id2)]"),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation (for help)'), ('loan', 'Loan'),], 
                                        string='Order Type', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'loan_id': fields.many2one('purchase.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'details': fields.char(size=30, string='Details', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'invoiced': fields.function(_invoiced, method=True, string='Paid',
            fnct_search=_invoiced_search, type='boolean', help="It indicates that an invoice has been paid."),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'noinvoice': fields.function(_get_noinvoice, method=True, string="Don't create an invoice", type='boolean'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'yml_module_name': fields.char(size=1024, string='Name of the module which created the object in the yml tests', readonly=True),
        'company_id2': fields.many2one('res.company','Company',select=1),
        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'partner_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="Invoice address for current field order."),
        'partner_order_id': fields.many2one('res.partner.address', 'Ordering Contact', readonly=True, required=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="The name and address of the contact who requested the order or quotation."),
        'partner_shipping_id': fields.many2one('res.partner.address', 'Shipping Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="Shipping address for current field order."),
        'pricelist_id': fields.many2one('product.pricelist', 'Currency', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="Currency for current field order."),
        'validated_date': fields.date(string='Validated date', help='Date on which the FO was validated.'),
        'order_policy': fields.selection([
            ('prepaid', 'Payment Before Delivery'),
            ('manual', 'Shipping & Manual Invoice'),
            ('postpaid', 'Invoice On Order After Delivery'),
            ('picking', 'Invoice From The Picking'),
        ], 'Shipping Policy', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]},
            help="""The Shipping Policy is used to synchronise invoice and delivery operations.
  - The 'Pay Before delivery' choice will first generate the invoice and then generate the picking order after the payment of this invoice.
  - The 'Shipping & Manual Invoice' will create the picking order directly and wait for the user to manually click on the 'Invoice' button to generate the draft invoice.
  - The 'Invoice On Order After Delivery' choice will generate the draft invoice based on sales order after all picking lists have been finished.
  - The 'Invoice From The Picking' choice is used to create an invoice during the picking process."""),
        'split_type_sale_order': fields.selection(SALE_ORDER_SPLIT_SELECTION, required=True, readonly=True),
        'original_so_id_sale_order': fields.many2one('sale.order', 'Original Field Order', readonly=True),
        'active': fields.boolean('Active', readonly=True),
        'product_id': fields.related('order_line', 'product_id', type='many2one', relation='product.product', string='Product'),
        'state_hidden_sale_order': fields.function(_vals_get_sale_override, method=True, type='selection', selection=SALE_ORDER_STATE_SELECTION, readonly=True, string='State', multi='get_vals_sale_override',
                                                   store= {'sale.order': (lambda self, cr, uid, ids, c=None: ids, ['state', 'split_type_sale_order'], 10)}),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': lambda *a: 2,
        'from_yml_test': lambda *a: False,
        'company_id2': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
        'order_policy': lambda *a: 'picking',
        'split_type_sale_order': 'original_sale_order',
        'active': True,
    }

    def _check_own_company(self, cr, uid, company_id, context=None):
        '''
        Remove the possibility to make a SO to user's company
        '''
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        if company_id == user_company_id:
            raise osv.except_osv(_('Error'), _('You cannot made a Field order to your own company !'))

        return True
    
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if context.get('update_mode') in ['init', 'update'] and 'from_yml_test' not in vals:
            logging.getLogger('init').info('SO: set from yml test to True')
            vals['from_yml_test'] = True

        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request') and not vals.get('procurement_request'):
            self._check_own_company(cr, uid, vals['partner_id'], context=context)

        return super(sale_order, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Remove the possibility to make a SO to user's company
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request'):
                for obj in self.read(cr, uid, ids, ['procurement_request']):
                    if not obj['procurement_request']:
                        self._check_own_company(cr, uid, vals['partner_id'], context=context)

        return super(sale_order, self).write(cr, uid, ids, vals, context=context)

    def wkf_validated(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            if len(order.order_line) < 1:
                raise osv.except_osv(_('Error'), _('You cannot validate a Field order without line !'))
        self.write(cr, uid, ids, {'state': 'validated', 'validated_date': time.strftime('%Y-%m-%d')}, context=context)
        for order in self.browse(cr, uid, ids, context=context):
            self.log(cr, uid, order.id, 'The Field order \'%s\' has been validated.' % order.name, context=context)

        return True
    
    def wkf_split(self, cr, uid, ids, context=None):
        '''
        split function for sale order: original -> stock, esc, local purchase
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        line_obj = self.pool.get('sale.order.line')
        fields_tools = self.pool.get('fields.tools')
        wf_service = netsvc.LocalService("workflow")
        
        # must be original-sale-order to reach this method
        for so in self.browse(cr, uid, ids, context=context):
            # links to split Fo
            split_fo_dic = {'esc_split_sale_order': False,
                            'stock_split_sale_order': False,
                            'local_purchase_split_sale_order': False}
            # check we are allowed to be here
            if so.split_type_sale_order != 'original_sale_order':
                raise osv.except_osv(_('Error'), _('You cannot split a Fo which has already been split.'))
            # loop through lines
            for line in so.order_line:
                # check that each line must have a supplier specified
                if not line.supplier and line.type == 'make_to_order' and line.po_cft in ('po', 'dpo'):
                    raise osv.except_osv(_('Error'), _('Supplier is not defined for all Field Order lines.'))
                fo_type = False
                # get corresponding type
                if line.type == 'make_to_stock':
                    fo_type = 'stock_split_sale_order'
                elif line.supplier.partner_type == 'esc':
                    fo_type = 'esc_split_sale_order'
                else:
                    fo_type = 'local_purchase_split_sale_order'
                # do we have already a link to Fo
                if not split_fo_dic[fo_type]:
                    # try to find corresponding stock split sale order
                    so_ids = self.search(cr, uid, [('original_so_id_sale_order', '=', so.id),
                                                   ('split_type_sale_order', '=', fo_type)], context=context)
                    if so_ids:
                        # the fo already exists
                        split_fo_dic[fo_type] = so_ids[0]
                    else:
                        # we create a new Fo for the corresponding type -> COPY we empty the lines
                        # generate the name of new fo
                        selec_name = fields_tools.get_selection_name(cr, uid, self, 'split_type_sale_order', fo_type, context=context)
                        fo_name = so.name + '-' + selec_name
                        split_id = self.copy(cr, uid, so.id, {'name': fo_name,
                                                              'order_line': [],
                                                              'split_type_sale_order': fo_type,
                                                              'original_so_id_sale_order': so.id}, context=dict(context, keepDateAndDistrib=True))
                        # log the action of split
                        self.log(cr, uid, split_id, _('The %s split %s has been created.')%(selec_name, fo_name))
                        split_fo_dic[fo_type] = split_id
                # copy the line to the split Fo - the state is forced to 'draft' by default method in original add-ons
                # -> the line state is modified to sourced when the corresponding procurement is created in action_ship_proc_create
                line_obj.copy(cr, uid, line.id, {'order_id': split_fo_dic[fo_type]}, context=dict(context, keepDateAndDistrib=True))
            # the sale order is treated, we process the workflow of the new so
            for to_treat in [x for x in split_fo_dic.values() if x]:
                wf_service.trg_validate(uid, 'sale.order', to_treat, 'order_validated', cr)
                wf_service.trg_validate(uid, 'sale.order', to_treat, 'order_confirm', cr)
        
        return True
    
    def wkf_split_done(self, cr, uid, ids, context=None):
        '''
        split done function for sale order
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        sol_obj = self.pool.get('sale.order.line')
        # get all corresponding sale order lines
        sol_ids = sol_obj.search(cr, uid, [('order_id', 'in', ids)], context=context)
        # set lines state to done
        if sol_ids:
            sol_obj.write(cr, uid, sol_ids, {'state': 'done'}, context=context)
        self.write(cr, uid, ids, {'state': 'done',
                                  'active': False}, context=context)
        return True
    
    def get_po_ids_from_so_ids(self, cr, uid, ids, context=None):
        '''
        receive the list of sale order ids
        
        return the list of purchase order ids corresponding (through procurement process)
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # procurement ids list
        po_ids = []
        
        for so in self.browse(cr, uid, ids, context=context):
            for line in so.order_line:
                if line.procurement_id:
                    if line.procurement_id.purchase_id:
                        if line.procurement_id.purchase_id.id not in po_ids:
                            po_ids.append(line.procurement_id.purchase_id.id)
        
        # return the purchase order ids
        return po_ids
    
    def _hook_message_action_wait(self, cr, uid, *args, **kwargs):
        '''
        Hook the message displayed on sale order confirmation
        '''
        return _('The Field order \'%s\' has been confirmed.') % (kwargs['order'].name,)

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
                      'location_id': order.shop_id.warehouse_id.lot_input_id.id,
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
            
            message = _("Loan counterpart '%s' has been created.") % (purchase.name,)
            
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

    def _get_reason_type(self, cr, uid, order, context=None):
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
        result['price_currency_id'] = self.browse(cr, uid, ids[0], context=context).pricelist_id.currency_id.id
        
        return result
    
    def _hook_ship_create_execute_specific_code_01(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to execute specific code at position 01
        '''
        super(sale_order, self)._hook_ship_create_execute_specific_code_01(cr, uid, ids, context=context, *args, **kwargs)
        # Comment because the confirmation of the Internal Request confirmed automatically the associated procurement order
#        wf_service = netsvc.LocalService("workflow")
#        order = kwargs['order']
#        proc_id = kwargs['proc_id']
#        if order.procurement_request and order.state == 'progress':
#            wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
        
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
    
    def _hook_procurement_create_line_condition(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
             
        - allow to customize the execution condition
        '''
        line = kwargs['line']
        order = kwargs['order']
        result = super(sale_order, self)._hook_procurement_create_line_condition(cr, uid, ids, context=context, *args, **kwargs)
        
        # for new Fo split logic, we create procurement order in action_ship_create only for IR or when the sale order is shipping in exception
        # when shipping in exception, we recreate a procurement order each time action_ship_create is called... this is standard openERP
        return result and (line.order_id.procurement_request or order.state == 'shipping_except' or order.yml_module_name == 'sale')

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the sale order and all related documents to done state
        '''
        wf_service = netsvc.LocalService("workflow")

        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}
        order_lines = []
        for order in self.browse(cr, uid, ids, context=context):
            # Done picking
            for pick in order.picking_ids:
                if pick.state not in ('cancel', 'done'):
                    wf_service.trg_validate(uid, 'stock.picking', pick.id, 'manually_done', cr)

            for line in order.order_line:
                order_lines.append(line.id)
                if line.procurement_id:
                    # Closed procurement
                    wf_service.trg_validate(uid, 'procurement.order', line.procurement_id.id, 'subflow.cancel', cr)
                    wf_service.trg_validate(uid, 'procurement.order', line.procurement_id.id, 'button_check', cr)

            # Closed loan counterpart
            if order.loan_id and order.loan_id.state not in ('cancel', 'done') and not context.get('loan_id', False) == order.id:
                loan_context = context.copy()
                loan_context.update({'loan_id': order.id})
                self.pool.get('purchase.order').set_manually_done(cr, uid, order.loan_id.id, all_doc=all_doc, context=loan_context)

            # Closed invoices
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

        # Closed stock moves
        move_ids = self.pool.get('stock.move').search(cr, uid, [('sale_line_id', 'in', order_lines), ('state', 'not in', ('cancel', 'done'))], context=context)
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)

        if all_doc:
            # Detach the PO from his workflow and set the state to done
            for order_id in ids:
                wf_service.trg_delete(uid, 'sale.order', order_id, cr)
                # Search the method called when the workflow enter in last activity
                wkf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'sale', 'act_done')[1]
                activity = self.pool.get('workflow.activity').browse(cr, uid, wkf_id, context=context)
                res = _eval_expr(cr, [uid, 'sale.order', order_id], False, activity.action)

        return True
    
    def _hook_ship_create_procurement_order(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to modify the data for procurement order creation
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        line = kwargs['line']
        # call to super
        proc_data = super(sale_order, self)._hook_ship_create_procurement_order(cr, uid, ids, context=context, *args, **kwargs)
        # update proc_data for link to destination purchase order during back update of sale order
        proc_data.update({'so_back_update_dest_po_id_procurement_order': line.so_back_update_dest_po_id_sale_order_line.id})
        return proc_data
    
    def action_ship_proc_create(self, cr, uid, ids, context=None):
        '''
        process logic at ship_procurement activity level
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        wf_service = netsvc.LocalService("workflow")
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        line_obj = self.pool.get('sale.order.line')
        
        lines = []
        
        # customer code execution position 03
        self._hook_ship_create_execute_specific_code_03(cr, uid, ids, context=context)
        
        for order in self.browse(cr, uid, ids, context=context):
            # from action_wait msf_order_dates
            # deactivated
            if not order.delivery_confirmed_date and False:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            for line in order.order_line:
                if not line.confirmed_delivery_date:
                    line.write({'confirmed_delivery_date': order.delivery_confirmed_date})
                    
            # from action_wait sale_override
            if len(order.order_line) < 1:
                raise osv.except_osv(_('Error'), _('You cannot confirm a Field order without line !'))
            if order.partner_id.partner_type == 'internal' and order.order_type == 'regular':
                self.write(cr, uid, [order.id], {'order_policy': 'manual'})
                for line in order.order_line:
                    lines.append(line.id)
            elif order.order_type in ['donation_exp', 'donation_st', 'loan']:
                self.write(cr, uid, [order.id], {'order_policy': 'manual'})
                for line in order.order_line:
                    lines.append(line.id)
# COMMENTED because of SP4 WM 12: Invoice Control
#            elif not order.from_yml_test:
#                self.write(cr, uid, [order.id], {'order_policy': 'manual'})
            
            # created procurements
            proc_ids = []
            # flag to prevent the display of the sale order log message
            # if the method is called after po update, we do not display log message
            display_log = True
            for line in order.order_line:
                proc_id = False
                date_planned = datetime.now() + relativedelta(days=line.delay or 0.0)
                date_planned = (date_planned - timedelta(days=company.security_lead)).strftime('%Y-%m-%d %H:%M:%S')
                
                # these lines are valid for all types (stock and order)
                # when the line is sourced, we already get a procurement for the line
                # when the line is confirmed, the corresponding procurement order has already been processed
                # if the line is draft, either it is the first call, or we call the method again after having added a line in the procurement's po
                if line.state in ['sourced', 'confirmed', 'done']:
                    continue

                if line.product_id:
                    proc_data = {'name': line.name,
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
                                 'move_id': False, # will be completed at ship state in action_ship_create method
                                 'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                                 'company_id': order.company_id.id,
                                 }
                    proc_data = self._hook_ship_create_procurement_order(cr, uid, ids, context=context, proc_data=proc_data, line=line, order=order)
                    proc_id = self.pool.get('procurement.order').create(cr, uid, proc_data, context=context)
                    proc_ids.append(proc_id)
                    line_obj.write(cr, uid, [line.id], {'procurement_id': proc_id}, context=context)
                    # set the flag for log message
                    if line.so_back_update_dest_po_id_sale_order_line:
                        display_log = False
                
                # if the line is draft (it should be the case), we set its state to 'sourced'
                    if line.state == 'draft':
                        line_obj.write(cr, uid, [line.id], {'state': 'sourced'}, context=context)
                    
            for proc_id in proc_ids:
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                
            # the Fo is sourced we set the state
            self.write(cr, uid, [order.id], {'state': 'sourced'}, context=context)
            # display message for sourced
            if display_log:
                self.log(cr, uid, order.id, _('The split \'%s\' is sourced.')%(order.name))
        
        if lines:
            line_obj.write(cr, uid, lines, {'invoiced': 1}, context=context)
        return True
    
    def _hook_ship_create_execute_specific_code_02(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to execute specific code at position 02
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        move_obj = self.pool.get('stock.move')
        pol_obj = self.pool.get('purchase.order.line')
        proc_obj = self.pool.get('procurement.order')
        order = kwargs['order']
        line = kwargs['line']
        move_id = kwargs['move_id']
        
        # we update the procurement and the purchase orderS if we are treating a Fo which is not shipping_exception
        # Po is only treated if line is make_to_order
        # IN nor OUT are yet (or just) created, we theoretically wont have problem with backorders and co
        if order.state != 'shipping_except' and not order.procurement_request and line.procurement_id:
            # if the procurement already has a stock move linked to it (during action_confirm of procurement order), we cancel it
            if line.procurement_id.move_id:
                # use action_cancel actually, because there is not stock picking or related stock moves
                move_obj.action_cancel(cr, uid, [line.procurement_id.move_id.id], context=context)
                #move_obj.write(cr, uid, [line.procurement_id.move_id.id], {'state': 'cancel'}, context=context)
            # corresponding procurement order
            proc_obj.write(cr, uid, [line.procurement_id.id], {'move_id': move_id}, context=context)
            # corresponding purchase order, if it exists (make_to_order)
            if line.type == 'make_to_order':
                pol_update_ids = pol_obj.search(cr, uid, [('procurement_id', '=', line.procurement_id.id)], context=context)
                pol_obj.write(cr, uid, pol_update_ids, {'move_dest_id': move_id}, context=context)
                
        return True
    
    def _hook_ship_create_execute_specific_code_03(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to execute specific code at position 03
        
        update the delivery confirmed date of sale order in case of STOCK sale order
        (check split_type_sale_order == 'stock_split_sale_order')
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        fields_tools = self.pool.get('fields.tools')
        date_tools = self.pool.get('date.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        
        for order in self.browse(cr, uid, ids, context=context):
            # if the order is stock So, we update the confirmed delivery date
            if order.split_type_sale_order == 'stock_split_sale_order':
                # date values
                ship_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                # confirmed
                confirmed = datetime.today()
                confirmed = confirmed + relativedelta(days=ship_lt or 0)
                confirmed = confirmed + relativedelta(days=order.est_transport_lead_time or 0)
                confirmed = confirmed.strftime(db_date_format)
                # rts
                rts = datetime.today()
                rts = rts + relativedelta(days=ship_lt or 0)
                rts = rts.strftime(db_date_format)
                
                self.write(cr, uid, [order.id], {'delivery_confirmed_date': confirmed,
                                                 'ready_to_ship_date': rts}, context=context)
            
        return True
    
    def test_lines(self, cr, uid, ids, context=None):
        '''
        return True if all lines of type 'make_to_order' are 'confirmed'
        
        only if a product is selected
        internal requests are not taken into account (should not be the case anyway because of separate workflow)
        '''
        for order in self.browse(cr, uid, ids, context=context):
            # backward compatibility for yml tests, if test we do not wait
            if order.from_yml_test:
                continue
            for line in order.order_line:
                # the product needs to have a product selected, otherwise not procurement, and no po to trigger back the so
                if line.type == 'make_to_order' and line.state != 'confirmed' and line.product_id:
                    return False
        return True

sale_order()


class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    _columns = {'parent_line_id': fields.many2one('sale.order.line', string='Parent line'),
                'partner_id': fields.related('order_id', 'partner_id', relation="res.partner", readonly=True, type="many2one", string="Customer"),
                # this field is used when the po is modified during on order process, and the so must be modified accordingly
                # the resulting new purchase order line will be merged in specified po_id 
                'so_back_update_dest_po_id_sale_order_line': fields.many2one('purchase.order', string='Destination of new purchase order line', readonly=True),
                'state': fields.selection(SALE_ORDER_LINE_STATE_SELECTION, 'State', required=True, readonly=True,
                help='* The \'Draft\' state is set when the related sales order in draft state. \
                    \n* The \'Confirmed\' state is set when the related sales order is confirmed. \
                    \n* The \'Exception\' state is set when the related sales order is set as exception. \
                    \n* The \'Done\' state is set when the sales order line has been picked. \
                    \n* The \'Cancelled\' state is set when a user cancel the sales order related.'),

                # these 2 columns are for the sync module
                'sync_pol_db_id': fields.integer(string='PO line DB Id', required=False, readonly=True),
                'sync_sol_db_id': fields.integer(string='SO line DB Id', required=False, readonly=True),
                }

    def create(self, cr, uid, vals, context=None):
        '''
        Add the database ID of the SO line to the value sync_sol_db_id
        '''
        so_line_ids = super(sale_order_line, self).create(cr, uid, vals, context=context)

        super(sale_order_line, self).write(cr, uid, so_line_ids, {'sync_sol_db_id': so_line_ids,} , context=context)
        return so_line_ids

    def open_split_wizard(self, cr, uid, ids, context=None):
        '''
        Open the wizard to split the line
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            data = {'sale_line_id': line.id, 'original_qty': line.product_uom_qty, 'old_line_qty': line.product_uom_qty}
            wiz_id = self.pool.get('split.sale.order.line.wizard').create(cr, uid, data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'split.sale.order.line.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context}
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset link to purchase order from update of on order purchase order
        '''
        if not default:
            default = {}
        # if the po link is not in default, we set it to False
        if 'so_back_update_dest_po_id_sale_order_line' not in default:
            default.update({'so_back_update_dest_po_id_sale_order_line': False})
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)

sale_order_line()


class sale_config_picking_policy(osv.osv_memory):
    """
    Set order_policy to picking
    """
    _name = 'sale.config.picking_policy'
    _inherit = 'sale.config.picking_policy'

    _defaults = {
        'order_policy': 'picking',
    }

sale_config_picking_policy()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
