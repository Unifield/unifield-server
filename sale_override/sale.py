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

import decimal_precision as dp

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

        # if the copy comes from the button duplicate
        if context.get('from_button'):
            default.update({'is_a_counterpart': False})
        
        if 'loan_id' not in default:
            default.update({'loan_id': False})

        default.update({'order_policy': 'picking',
                        'active': True})

        if not context.get('keepClientOrder', False):
            default.update({'client_order_ref': False})
                    
        # if splitting related attributes are not set with default values, we reset their values
        if 'split_type_sale_order' not in default:
            default.update({'split_type_sale_order': 'original_sale_order'})
        if 'original_so_id_sale_order' not in default:
            default.update({'original_so_id_sale_order': False})
        if 'fo_to_resource' not in default:
            default.update({'fo_to_resource': False})
        if 'parent_order_name' not in default:
            default.update({'parent_order_name': False})
        return super(sale_order, self).copy(cr, uid, id, default=default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        Check if the status of the unlinked FO is allowed for unlink.
        Statuses allowed : draft / cancel
        '''
        for order in self.read(cr, uid, ids, ['state', 'procurement_request'], context=context):
            if order['state'] not in ('draft', 'cancel'):
                type = order['procurement_request'] and _('Internal Request') or _('Field order')
                raise osv.except_osv(_('Error'), _('Only Draft and Canceled %s can be deleted.') % type)
        return super(sale_order, self).unlink(cr, uid, ids, context=context)

    def action_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'delivery_confirmed_date': time.strftime('%Y-%m-%d')}, context=context)
        return super(sale_order, self).action_cancel(cr, uid, ids, context=context)

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
            for line in sale.order_line:
                if line.invoiced:
                    for invoice_line in line.invoice_lines:
                        if invoice_line.invoice_id.state not in ('draft', 'cancel'):
                            tot += invoice_line.price_subtotal
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
    
    def _get_no_line(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = True
            for line in order.order_line:
                res[order.id] = False
                break
            # better: if order.order_line: res[order.id] = False
                
        return res

    def _get_manually_corrected(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = False
            for line in order.order_line:
                if line.manually_corrected:
                    res[order.id] = True
                    break

        return res

    _columns = {
        # we increase the size of client_order_ref field from 64 to 128
        'client_order_ref': fields.char('Customer Reference', size=128),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, select=True),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'),], 
                                        string='Order Type', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'loan_id': fields.many2one('purchase.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        # we increase the size of the 'details' field from 30 to 86
        'details': fields.char(size=86, string='Details', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
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
        'invoice_quantity': fields.selection([('order', 'Ordered Quantities'), ('procurement', 'Shipped Quantities')], 'Invoice on', help="The sale order will automatically create the invoice proposition (draft invoice). Ordered and delivered quantities may not be the same. You have to choose if you want your invoice based on ordered or shipped quantities. If the product is a service, shipped quantities means hours spent on the associated tasks.", required=True, readonly=True),
        'order_policy': fields.selection([
            ('prepaid', 'Payment Before Delivery'),
            ('manual', 'Shipping & Manual Invoice'),
            ('postpaid', 'Invoice On Order After Delivery'),
            ('picking', 'Invoice From The Picking'),
        ], 'Shipping Policy', required=True, readonly=True,
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
        'no_line': fields.function(_get_no_line, method=True, type='boolean', string='No line'),
        'manually_corrected': fields.function(_get_manually_corrected, method=True, type='boolean', string='Manually corrected'),
        'is_a_counterpart': fields.boolean('Counterpart?', help="This field is only for indicating that the order is a counterpart"),
        'fo_created_by_po_sync': fields.boolean('FO created by PO after SYNC', readonly=True),
        'fo_to_resource': fields.boolean(string='FO created to resource FO in exception', readonly=True),
        'parent_order_name': fields.char(size=64, string='Parent order name', help='In case of this FO is created to re-source a need, this field contains the name of the initial FO (before split).'),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'invoice_quantity': lambda *a: 'procurement',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': lambda *a: 2,
        'from_yml_test': lambda *a: False,
        'company_id2': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
        'order_policy': lambda *a: 'picking',
        'split_type_sale_order': 'original_sale_order',
        'active': True,
        'no_line': lambda *a: True,
    }

    def _check_own_company(self, cr, uid, company_id, context=None):
        '''
        Remove the possibility to make a SO to user's company
        '''
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        if company_id == user_company_id:
            raise osv.except_osv(_('Error'), _('You cannot made a Field order to your own company !'))

        return True

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check restriction on products
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('sale.order.line')
        res = True

        for order in self.browse(cr, uid, ids, context=context):
            res = res and line_obj._check_restriction_line(cr, uid, [x.id for x in order.order_line], context=context)

        return res
    
    def onchange_partner_id(self, cr, uid, ids, part=False, order_type=False, *a, **b):
        '''
        Set the intl_customer_ok field if the partner is an ESC or an international partner
        '''
        res = super(sale_order, self).onchange_partner_id(cr, uid, ids, part)

        if part and order_type:
            res2 = self.onchange_order_type(cr, uid, ids, order_type, part)
            if res2.get('value'):
                if res.get('value'):
                    res['value'].update(res2['value'])
                else:
                    res.update({'value': res2['value']})
        
            # Check the restrction of product in lines
            if ids:
                product_obj = self.pool.get('product.product')
                for order in self.browse(cr, uid, ids):
                    for line in order.order_line:
                        if line.product_id:
                            res, test = product_obj._on_change_restriction_error(cr, uid, line.product_id.id, field_name='partner_id', values=res, vals={'partner_id': part, 'obj_type': 'sale.order'})
                            if test:
                                res.setdefault('value', {}).update({'partner_order_id': False, 'partner_shipping_id': False, 'partner_invoice_id': False})
                                return res

        return res

    def onchange_categ(self, cr, uid, ids, categ, context=None):
        '''
        Check if the list of products is valid for this new category
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        message = {}
        if ids and categ in ['service', 'transport']:
            # Avoid selection of non-service producs on Service FO
            category = categ=='service' and 'service_recep' or 'transport'
            transport_cat = ''
            if category == 'transport':
                transport_cat = 'OR p.transport_ok = False'
            cr.execute('''SELECT p.default_code AS default_code, t.name AS name
                          FROM sale_order_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN sale_order fo ON l.order_id = fo.id
                          WHERE (t.type != 'service_recep' %s) AND fo.id in (%s) LIMIT 1''' % (transport_cat, ','.join(str(x) for x in ids)))
            res = cr.fetchall()
            if res:
                cat_name = categ=='service' and 'Service' or 'Transport'
                message.update({'title': _('Warning'),
                                'message': _('The product [%s] %s is not a \'%s\' product. You can sale only \'%s\' products on a \'%s\' field order. Please remove this line before saving.') % (res[0][0], res[0][1], cat_name, cat_name, cat_name)})

        return {'warning': message}

    def _check_service(self, cr, uid, ids, vals, context=None):
        '''
        Avoid the saving of a FO with a non service products on Service FO
        '''
        categ = {'transport': _('Transport'),
                 'service': _('Service')}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        if context.get('import_in_progress'):
            return True

        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                if vals.get('categ', order.categ) == 'transport' and line.product_id and (line.product_id.type not in ('service', 'service_recep') or not line.product_id.transport_ok):
                    raise osv.except_osv(_('Error'), _('The product [%s] %s is not a \'Transport\' product. You can sale only \'Transport\' products on a \'Transport\' field order. Please remove this line.') % (line.product_id.default_code, line.product_id.name))
                    return False
                elif vals.get('categ', order.categ) == 'service' and line.product_id and line.product_id.type not in ('service', 'service_recep'):
                    raise osv.except_osv(_('Error'), _('The product [%s] %s is not a \'Service\' product. You can sale only \'Service\' products on a \'Service\' field order. Please remove this line.') % (line.product_id.default_code, line.product_id.name))
                    return False

        return True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if context.get('update_mode') in ['init', 'update'] and 'from_yml_test' not in vals:
            logging.getLogger('init').info('SO: set from yml test to True')
            vals['from_yml_test'] = True

        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request') and not vals.get('procurement_request'):
            self._check_own_company(cr, uid, vals['partner_id'], context=context)

        if 'partner_id' in vals and vals.get('yml_module_name') != 'sale':
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'])
            if vals.get('order_type', 'regular') != 'regular' or (vals.get('order_type', 'regular') == 'regular' and partner.partner_type == 'internal'):
                vals['order_policy'] = 'manual'
            else:
                vals['order_policy'] = 'picking'
        elif vals.get('yml_module_name') == 'vals':
            if not vals.get('order_policy'):
                vals['order_policy'] = 'picking'
            if not vals.get('invoice_quantity'):
                vals['invoice_quantity'] = 'order'

        res = super(sale_order, self).create(cr, uid, vals, context)
        self._check_service(cr, uid, [res], vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Remove the possibility to make a SO to user's company
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request'):
                for obj in self.read(cr, uid, ids, ['procurement_request']):
                    if not obj['procurement_request']:
                        self._check_own_company(cr, uid, vals['partner_id'], context=context)

        for order in self.browse(cr, uid, ids, context=context):
            if order.yml_module_name == 'sale':
                continue
            partner = self.pool.get('res.partner').browse(cr, uid, vals.get('partner_id', order.partner_id.id))
            if vals.get('order_type', order.order_type) != 'regular' or (vals.get('order_type', order.order_type) == 'regular' and partner.partner_type == 'internal'):
                vals['order_policy'] = 'manual'
            else:
                vals['order_policy'] = 'picking'

        self._check_service(cr, uid, ids, vals, context=context)

        res = super(sale_order, self).write(cr, uid, ids, vals, context=context)

        return res

    def ask_resource_lines(self, cr, uid, ids, context=None):
        '''
        Launch the wizard to re-source lines
        '''
        # Objects
        wiz_obj = self.pool.get('sale.order.cancelation.wizard')

        # Variables
        wf_service = netsvc.LocalService("workflow")

        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for order in self.browse(cr, uid, ids, context=context):
            if order.state == 'validated' and len(order.order_line) > 0:
                wiz_id = wiz_obj.create(cr, uid, {'order_id': order.id}, context=context)
                return {'type': 'ir.actions.act_window',
                        'res_model': 'sale.order.cancelation.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': wiz_id,
                        'context': context}

            wf_service.trg_validate(uid, 'sale.order', order.id, 'cancel', cr)

        return True
    
    def change_currency(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to change the currency and update lines
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for order in self.browse(cr, uid, ids, context=context):
            data = {'order_id': order.id,
                    'partner_id': order.partner_id.id,
                    'partner_type': order.partner_id.partner_type,
                    'new_pricelist_id': order.pricelist_id.id,
                    'currency_rate': 1.00,
                    'old_pricelist_id': order.pricelist_id.id}
            wiz = self.pool.get('sale.order.change.currency').create(cr, uid, data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'sale.order.change.currency',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': wiz,
                    'target': 'new'}
            
        return True

    def wkf_validated(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            if order.order_type == 'loan':
                line_ids = []
                for l in order.order_line:
                    line_ids.append(l.id)
                self.pool.get('sale.order.line').write(cr, uid, line_ids, {'type': 'make_to_stock'}, context=context)


            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [('in_search', '=', order.partner_id.partner_type)], context=context)
            if order.pricelist_id.id not in pricelist_ids:
                raise osv.except_osv(_('Error'), _('The currency used on the order is not compatible with the supplier. Please change the currency to choose a compatible currency.'))
            if len(order.order_line) < 1:
                raise osv.except_osv(_('Error'), _('You cannot validate a Field order without line !'))
        self.write(cr, uid, ids, {'state': 'validated', 'validated_date': time.strftime('%Y-%m-%d')}, context=context)
        for order in self.browse(cr, uid, ids, context=context):
            if not order.procurement_request:
                self.log(cr, uid, order.id, 'The Field order \'%s\' has been validated.' % order.name, context=context)
            else:
                self.log(cr, uid, order.id, 'The Internal Request \'%s\' has been validated.' % order.name, context=context)

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
            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [('in_search', '=', so.partner_id.partner_type)], context=context)
            if so.pricelist_id.id not in pricelist_ids:
                raise osv.except_osv(_('Error'), _('The currency used on the order is not compatible with the supplier. Please change the currency to choose a compatible currency.'))
            # links to split Fo
            split_fo_dic = {'esc_split_sale_order': False,
                            'stock_split_sale_order': False,
                            'local_purchase_split_sale_order': False}
            # check we are allowed to be here
            if so.split_type_sale_order != 'original_sale_order':
                raise osv.except_osv(_('Error'), _('You cannot split a Fo which has already been split.'))
            # loop through lines
            created_line = []
            for line in so.order_line:
                # check that each line must have a supplier specified
                if  line.type == 'make_to_order':
                    if not line.product_id:
                        raise osv.except_osv(_('Warning'), _("""You can't confirm a Sale Order that contains
                        lines with procurement method 'On Order' and without product. Please check the line %s
                        """) % line.line_number)
                    if not line.supplier and line.po_cft in ('po', 'dpo'):
                        raise osv.except_osv(_('Error'), _("""Supplier is not defined for all Field Order lines. 
                        Please check the line %s
                        """) % line.line_number)
                fo_type = False
                # get corresponding type
                if line.type == 'make_to_stock':
                    fo_type = 'stock_split_sale_order'
                elif line.supplier.partner_type == 'esc':
                    fo_type = 'esc_split_sale_order'
                else:
                    # default value is local purchase - same value if no supplier is defined (tender)
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
                                                              'loan_id': so.loan_id and so.loan_id.id or False,
                                                              'delivery_requested_date': so.delivery_requested_date,
                                                              'split_type_sale_order': fo_type,
                                                              'ready_to_ship_date': line.order_id.ready_to_ship_date,
                                                              'original_so_id_sale_order': so.id}, context=dict(context, keepDateAndDistrib=True, keepClientOrder=True))
                        # log the action of split
                        self.log(cr, uid, split_id, _('The %s split %s has been created.')%(selec_name, fo_name))
                        split_fo_dic[fo_type] = split_id
                        # For loans, change the subflow
                        if fo_type == 'stock_split_sale_order':
                            po_ids = self.pool.get('purchase.order').search(cr, uid, [('loan_id', '=', so.id)], context=context)
                            netsvc.LocalService("workflow").trg_change_subflow(uid, 'purchase.order', po_ids, 'sale.order', [so.id], split_id, cr)
                # copy the line to the split Fo - the state is forced to 'draft' by default method in original add-ons
                # -> the line state is modified to sourced when the corresponding procurement is created in action_ship_proc_create
                new_context = dict(context, keepDateAndDistrib=True, keepLineNumber=True, no_store_function=True)
                new_line_id = line_obj.copy(cr, uid, line.id, {'order_id': split_fo_dic[fo_type],
                                                 'original_line_id': line.id}, context=dict(context, keepDateAndDistrib=True, keepLineNumber=True, no_store_function=['sale.order.line']))
                created_line.append(new_line_id)

            line_obj._call_store_function(cr, uid, created_line, keys=None, result=None, bypass=False, context=context)
            # the sale order is treated, we process the workflow of the new so
            for to_treat in [x for x in split_fo_dic.values() if x]:
                wf_service.trg_validate(uid, 'sale.order', to_treat, 'order_validated', cr)
                wf_service.trg_validate(uid, 'sale.order', to_treat, 'order_confirm', cr)
        return True

    def get_original_name(self, cr, uid, order, context=None):
        '''
        Returns the name of the first original FO
        '''
        if order.original_so_id_sale_order:
            return self.get_original_name(cr, uid, order.original_so_id_sale_order, context=context)
        elif order.parent_order_name:
            return order.parent_order_name

        return order.name

    def create_resource_order(self, cr, uid, order, context=None):
        '''
        Create a new FO to re-source the needs.
        '''
        context = context or {}

        # Get the name of the original FO
        old_order_name = order.name
#        order_name = '/'.join(x for x in order.name.split('/')[0:-1])

        order_ids = self.search(cr, uid, [('active', 'in', ('t', 'f')), ('fo_to_resource', '=', True), ('parent_order_name', '=', old_order_name)], context=dict(context, procurement_request=True))
        for old_order in self.read(cr, uid, order_ids, ['name', 'state'], context=context):
            if old_order['state'] == 'draft':
                return old_order['id']

        tmp_kco = context.get('keepClientOrder')
        context['keepClientOrder'] = True
        order_id = self.copy(cr, uid, order.id, {'order_line': [], 
                                                 'state': 'draft', 
                                                 'parent_order_name': old_order_name, 
                                                 'fo_to_resource': True}, context=context)
        context['keepClientOrder'] = tmp_kco

        order_name = self.read(cr, uid, order_id, ['name'], context=context)['name']

        self.log(cr, uid, order_id, _('The Field order %s has been created to re-source the canceled needs') % order_name, context=dict(context, procurement_request=order.procurement_request))

        return order_id

    def sale_except_correction(self, cr, uid, ids, context=None):
        '''
        Remove the link between a Field order and the canceled procurement orders
        '''
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                if line.procurement_id and line.procurement_id.state == 'cancel':
                    if line.procurement_id.procure_method == 'make_to_stock' and line.procurement_id.move_id:
                        # TODO: Make a diff with UoM
                        diff = line.product_uom_qty - (line.product_uom_qty - line.procurement_id.move_id.product_qty)
                        resource_id = self.pool.get('sale.order').create_resource_order(cr, uid, line.order_id.original_so_id_sale_order, context=context)
                        self.pool.get('sale.order.line').add_resource_line(cr, uid, line, resource_id, diff, context=context)
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'state': 'cancel',
                                                                                'manually_corrected': True,
                                                                                'procurement_id': False}, context=context)
            if (order.order_policy == 'manual'):
                self.write(cr, uid, [order.id], {'state': 'manual'})
            else:
                self.write(cr, uid, [order.id], {'state': 'progress'})

        return
    
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
            # UTP-392: don't create a PO if it is created by sync ofr the loan
            if order.is_a_counterpart or (order.order_type == 'loan' and order.fo_created_by_po_sync):
                return

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
                      'is_a_counterpart': True,
                      }
            context['is_a_counterpart'] = True
            order_id = purchase_obj.create(cr, uid, values, context=context)
            for line in order.order_line:
                purchase_line_obj.create(cr, uid, {'product_id': line.product_id and line.product_id.id or False,
                                                   'product_uom': line.product_uom.id,
                                                   'order_id': order_id,
                                                   'price_unit': line.price_unit,
                                                   'product_qty': line.product_uom_qty,
                                                   'date_planned': (today() + RelativeDateTime(months=+order.loan_duration)).strftime('%Y-%m-%d'),
                                                   'name': line.name,}, context)
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
    
    def order_line_change(self, cr, uid, ids, order_line):
        res = {'no_line': True}
        
        if order_line:
            res = {'no_line': False}
        
        return {'value': res}
    
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
        obj_data = self.pool.get('ir.model.data')

        result = super(sale_order, self)._hook_ship_create_stock_move(cr, uid, ids, context=context, *args, **kwargs)
        result['reason_type_id'] = self._get_reason_type(cr, uid, kwargs['order'], context)
        result['price_currency_id'] = self.browse(cr, uid, ids[0], context=context).pricelist_id.currency_id.id

        line = kwargs['line']
        if line.order_id.procurement_request and line.order_id.location_requestor_id.usage == 'customer' and not line.product_id and line.comment:
            result['product_id'] = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        
        return result
    
    def _hook_ship_create_execute_specific_code_01(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
        
        - allow to execute specific code at position 01
        '''
        super(sale_order, self)._hook_ship_create_execute_specific_code_01(cr, uid, ids, context=context, *args, **kwargs)
        # DE-Comment because the confirmation of the Internal Request DOES NOT confirmed automatically the associated procurement order
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
        if line.order_id.manually_corrected:
            return False
        if line.order_id.procurement_request:
            # Create OUT lines for MTO lines with an external CU as requestor location 
            if line.type == 'make_to_order' and line.order_id.location_requestor_id.usage != 'customer':
                result = False
            elif line.type == 'make_to_order' and line.order_id.location_requestor_id.usage == 'customer':
                result = True
        # result = result and not line.order_id.procurement_request => the proc request can have pick and move
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
        
        # for new Fo split logic, we create procurement order in action_ship_create only for IR
        return result and (line.order_id.procurement_request or order.yml_module_name == 'sale')

    def _hook_ship_create_product_id(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
             
        - allow to modifiy product especially for internal request which type is "make_to_order"
        '''
        obj_data = self.pool.get('ir.model.data')
        result = super(sale_order, self)._hook_ship_create_product_id(cr, uid, ids, context=context, *args, **kwargs)
        line = kwargs['line']
        if line.product_id:
            result = line.product_id.id
        elif line.order_id.procurement_request and not line.product_id and line.comment:
            result = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        return result
    
    def _hook_ship_create_uom_id(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py
             
        - allow to modifiy uom especially for internal request which type is "make_to_order"
        '''
        obj_data = self.pool.get('ir.model.data')
        result = super(sale_order, self)._hook_ship_create_uom_id(cr, uid, ids, context=context, *args, **kwargs)
        line = kwargs['line']
        if line.product_id:
            result = line.product_uom.id
        elif line.order_id.procurement_request and not line.product_id and line.comment:
            # do we need to have one product data per uom?
            result = obj_data.get_object_reference(cr, uid, 'product', 'cat0')[1]
        return result

    def _hook_execute_action_assign(self, cr, uid, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to add more actions when the picking is confirmed
        '''
        picking_id = kwargs['pick_id']
        res = super(sale_order, self)._hook_execute_action_assign(cr, uid, *args, **kwargs)
        return self.pool.get('stock.picking').action_assign(cr, uid, [picking_id])

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
        procurement_ids = []
        proc_move_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            # Done picking
            for pick in order.picking_ids:
                if pick.state not in ('cancel', 'done'):
                    wf_service.trg_validate(uid, 'stock.picking', pick.id, 'manually_done', cr)

            for line in order.order_line:
                order_lines.append(line.id)
                if line.procurement_id:
                    procurement_ids.append(line.procurement_id.id)
                    if line.procurement_id.move_id:
                        proc_move_ids.append(line.procurement_id.move_id.id)

            # Closed loan counterpart
            if order.loan_id and order.loan_id.state not in ('cancel', 'done') and not context.get('loan_id', False) == order.id:
                loan_context = context.copy()
                loan_context.update({'loan_id': order.id})
                self.pool.get('purchase.order').set_manually_done(cr, uid, order.loan_id.id, all_doc=all_doc, context=loan_context)

            # Closed invoices
            #invoice_error_ids = []
            #for invoice in order.invoice_ids:
            #    if invoice.state == 'draft':
            #        wf_service.trg_validate(uid, 'account.invoice', invoice.id, 'invoice_cancel', cr)
            #    elif invoice.state not in ('cancel', 'done'):
            #        invoice_error_ids.append(invoice.id)

            #if invoice_error_ids:
            #    invoices_ref = ' / '.join(x.number for x in self.pool.get('account.invoice').browse(cr, uid, invoice_error_ids, context=context))
            #    raise osv.except_osv(_('Error'), _('The state of the following invoices cannot be updated automatically. Please cancel them manually or d    iscuss with the accounting team to solve the problem. Invoices references : %s') % invoices_ref)

        # Closed stock moves
        move_ids = self.pool.get('stock.move').search(cr, uid, [('sale_line_id', 'in', order_lines), ('state', 'not in', ('cancel', 'done'))], context=context)
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)
        self.pool.get('stock.move').set_manually_done(cr, uid, proc_move_ids, all_doc=all_doc, context=context)

        for procurement in procurement_ids:
            # Closed procurement
            wf_service.trg_validate(uid, 'procurement.order', procurement, 'subflow.cancel', cr)
            wf_service.trg_validate(uid, 'procurement.order', procurement, 'button_check', cr)


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
        # update proc_data for link to destination purchase order and purchase order line (for line number) during back update of sale order
        proc_data.update({'so_back_update_dest_po_id_procurement_order': line.so_back_update_dest_po_id_sale_order_line.id,
                          'so_back_update_dest_pol_id_procurement_order': line.so_back_update_dest_pol_id_sale_order_line.id,
                          'sale_id': line.order_id.id,})
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
            # Put a default delivery confirmed date
            if not order.delivery_confirmed_date:
                self.write(cr, uid, [order.id], {'delivery_confirmed_date': time.strftime('%Y-%m-%d')}, context=context)
            # for all lines, if the confirmed date is not filled, we copy the header value
            for line in order.order_line:
                if not line.confirmed_delivery_date:
                    line.write({'confirmed_delivery_date': order.delivery_confirmed_date})
                    
            # from action_wait sale_override
            if len(order.order_line) < 1:
                raise osv.except_osv(_('Error'), _('You cannot confirm a Field order without line !'))
            if order.yml_module_name != 'sale':
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
            proc_to_check = []
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
                    if line.so_back_update_dest_po_id_sale_order_line or line.created_by_po:
                        display_log = False

                    if line.created_by_po:
                        proc_to_check.append(proc_id)

                    if line.created_by_po_line:
                        self.pool.get('purchase.order.line').write(cr, uid, [line.created_by_po_line.id], {'procurement_id': proc_id}, context=context)
                
                # if the line is draft (it should be the case), we set its state to 'sourced'
                    if line.state == 'draft':
                        line_obj.write(cr, uid, [line.id], {'state': 'sourced'}, context=context)
                    
            for proc_id in proc_ids:
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)

            for proc_id in proc_to_check:
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
                self.pool.get('procurement.order').write(cr, uid, [proc_id], {'state': 'running'}, context=context)
                
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
            cancel_move_id = False
            # if the procurement already has a stock move linked to it (during action_confirm of procurement order), we cancel it
            # UF-1155 : Divided the cancel of the move in two times to avoid the cancelation of the field order
            if line.procurement_id.move_id:
                cancel_move_id = line.procurement_id.move_id.id
            
            # update corresponding procurement order with the new stock move
            proc_obj.write(cr, uid, [line.procurement_id.id], {'move_id': move_id}, context=context)

            if cancel_move_id:
                # use action_cancel actually, because there is not stock picking or related stock moves
                move_obj.action_cancel(cr, uid, [line.procurement_id.move_id.id], context=context)
                #move_obj.write(cr, uid, [line.procurement_id.move_id.id], {'state': 'cancel'}, context=context)
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
                if line.product_id and line.type == 'make_to_order' and line.state != 'confirmed' and (not line.procurement_id or line.procurement_id.state != 'cancel'):
                    return False
        return True

sale_order()


class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    _columns = {'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Sale Price Computation'), readonly=True, states={'draft': [('readonly', False)]}),
                'parent_line_id': fields.many2one('sale.order.line', string='Parent line'),
                'partner_id': fields.related('order_id', 'partner_id', relation="res.partner", readonly=True, type="many2one", string="Customer"),
                # this field is used when the po is modified during on order process, and the so must be modified accordingly
                # the resulting new purchase order line will be merged in specified po_id 
                'so_back_update_dest_po_id_sale_order_line': fields.many2one('purchase.order', string='Destination of new purchase order line', readonly=True),
                'so_back_update_dest_pol_id_sale_order_line': fields.many2one('purchase.order.line', string='Original purchase order line', readonly=True),
                'state': fields.selection(SALE_ORDER_LINE_STATE_SELECTION, 'State', required=True, readonly=True,
                help='* The \'Draft\' state is set when the related sales order in draft state. \
                    \n* The \'Confirmed\' state is set when the related sales order is confirmed. \
                    \n* The \'Exception\' state is set when the related sales order is set as exception. \
                    \n* The \'Done\' state is set when the sales order line has been picked. \
                    \n* The \'Cancelled\' state is set when a user cancel the sales order related.'),
                
                # This field is used to identify the FO PO line between 2 instances of the sync
                'sync_order_line_db_id': fields.text(string='Sync order line DB Id', required=False, readonly=True),
                'original_line_id': fields.many2one('sale.order.line', string='Original line', help='ID of the original line before the split'),
                'manually_corrected': fields.boolean(string='FO line is manually corrected by user'),
                'created_by_po': fields.many2one('purchase.order', string='Created by PO'),
                'created_by_po_line': fields.many2one('purchase.order.line', string='Created by PO line'),
                }

    _sql_constraints = [
        ('product_qty_check', 'CHECK( product_uom_qty > 0 )', 'Product Quantity must be greater than zero.'),
    ]

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Call the user to know if the line must be re-sourced
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id and line.order_id.state != 'draft':
                return self.pool.get('sale.order.line.unlink.wizard').ask_unlink(cr, uid, ids, context=context)

        return self.ask_order_unlink(cr, uid, ids, context=context)

    def ask_order_unlink(self, cr, uid, ids, context=None):
        '''
        Call the unlink method for lines and if the FO becomes empty,
        ask the user if he wants to cancel the FO
        '''
        sale_ids = []
        res = False
        for line in self.read(cr, uid, ids, ['order_id'], context=context):
            if line['order_id'][0] not in sale_ids:
                sale_ids.append(line['order_id'][0])

        self.unlink(cr, uid, ids, context=context)

        for order in self.pool.get('sale.order').read(cr, uid, sale_ids, ['order_line'], context=context):
            if len(order['order_line']) == 0:
                res = self.pool.get('sale.order.unlink.wizard').ask_unlink(cr, uid, order['id'], context=context)

        return res

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is restriction on lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id and line.order_id.partner_id and line.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, line.product_id.id, vals={'partner_id': line.order_id.partner_id.id, 'obj_type': 'sale.order'}, context=context):
                    return False

        return True

    def update_or_cancel_line(self, cr, uid, line, qty_diff, context=None):
        '''
        Update the quantity of the IR/FO line with the qty_diff - Update also
        the quantity in procurement attached to the IR/Fo line.

        If the qty_diff is equal or larger than the line quantity, delete the
        line and its procurement.
        '''
        # Documents
        proc_obj = self.pool.get('procurement.order')
        
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(line, (int, long)):
            line = self.browse(cr, uid, line, context=context)

        order = line.order_id and line.order_id.id

        if qty_diff >= line.product_uom_qty:
            proc = line.procurement_id and line.procurement_id.id
            # Delete the line and the procurement
            self.write(cr, uid, [line.id], {'state': 'cancel'}, context=context)
            self.unlink(cr, uid, [line.id], context=context)

            if proc:
                proc_obj.write(cr, uid, [proc], {'product_qty': 0.00}, context=context)
                proc_obj.action_cancel(cr, uid, [proc])
        else:
            minus_qty = line.product_uom_qty - qty_diff
            proc = line.procurement_id and line.procurement_id.id
            # Update the line and the procurement
            self.write(cr, uid, [line.id], {'product_uom_qty': minus_qty,
                                            'product_uos_qty': minus_qty}, context=context)
            if proc:
                proc_obj.write(cr, uid, [proc], {'product_qty': minus_qty}, context=context)

        if order:
            wf_service.trg_write(uid, 'sale.order', order, cr)

        return True

    def add_resource_line(self, cr, uid, line, order_id, qty_diff, context=None):
        '''
        Add a copy of the original line (line) into the new order (order_id)
        created to resource needs.
        Update the product qty with the qty_diff in case of split or backorder moves
        before cancelation
        '''
        # Documents
        order_obj = self.pool.get('sale.order')
        ad_obj = self.pool.get('analytic.distribution')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(line, (int, long)):
            line = self.browse(cr, uid, line, context=context)
        
#        if not order_id and not line.order_id.procurement_request and line.order_id.original_so_id_sale_order:
#            order_id = order_obj.create_resource_order(cr, uid, line.order_id.original_so_id_sale_order, context=context)
#        elif not order_id and (line.order_id.procurement_request or not line.order_id.original_so_id_sale_order):
        order_id = order_obj.create_resource_order(cr, uid, line.order_id, context=context)

        if not qty_diff:
            qty_diff = line.product_uom_qty

        values = {
            'order_id': order_id,
            'product_uom_qty': qty_diff,
            'product_uos_qty': qty_diff,
            'procurement_id': False
        }
        context['keepDateAndDistrib'] = True
        if not line.analytic_distribution_id and line.order_id and line.order_id.analytic_distribution_id:
            new_distrib = ad_obj.copy(cr, uid, line.order_id.analytic_distribution_id.id, {}, context=context)
            values['analytic_distribution_id'] = new_distrib

        line_id = self.copy(cr, uid, line.id, values, context=context)

        order_name = self.pool.get('sale.order').read(cr, uid, [order_id], ['name'], context=context)[0]['name']

        if line.order_id and line.order_id.procurement_request:
            view_id = data_obj.get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'sale', 'view_order_form')[1]
        context.update({'view_id': view_id})
        self.pool.get('sale.order').log(cr, uid, order_id, _('A line was added to the Field Order %s to re-source the canceled line.')%(order_name), context=context)

        return line_id

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
        # if the po link is not in default, we set both to False (both values are closely related)
        if 'so_back_update_dest_po_id_sale_order_line' not in default:
            default.update({'so_back_update_dest_po_id_sale_order_line': False,
                            'so_back_update_dest_pol_id_sale_order_line': False,})
        default.update({'sync_order_line_db_id': False, 'manually_corrected': False})
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)

    def open_order_line_to_correct(self, cr, uid, ids, context=None):
        '''
        Open Order Line in form view
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'sale_override', 'view_order_line_to_correct_form')[1]
        view_to_return = {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order.line',
            'type': 'ir.actions.act_window',
            'res_id': ids[0],
            'target': 'new',
            'context': context,
            'view_id': [view_id],
        }
        return view_to_return

    def save_and_close(self, cr, uid, ids, context=None):
        '''
        Save and close the configuration window 
        '''
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
        obj_browse = self.browse(cr, uid, ids, context=context)
        vals={}
        message = ''
        for var in obj_browse:
            if var.product_uom.id == tbd_uom:
                message += 'You have to define a valid UOM, i.e. not "To be define".'
            if var.nomen_manda_0.id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1]:
                message += 'You have to define a valid Main Type (in tab "Nomenclature Selection"), i.e. not "To be define".'
            if var.nomen_manda_1.id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1]:
                message += 'You have to define a valid Group (in tab "Nomenclature Selection"), i.e. not "To be define".'
            if var.nomen_manda_2.id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1]:
                message += 'You have to define a valid Family (in tab "Nomenclature Selection"), i.e. not "To be define".'
        # the 3rd level is not mandatory
        if message:
            raise osv.except_osv(_('Warning !'), _(message))
        
        self.write(cr, uid, ids, vals, context=context)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')[1]
        return {'type': 'ir.actions.act_window_close',
                'res_model': 'sale.order',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': [view_id],
                }

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False):
        """
        If we select a product we change the procurement type to its own procurement method (procure_method).
        If there isn't product, the default procurement method is 'From Order' (make_to_order).
        Both remains changeable manually.
        """
        product_obj = self.pool.get('product.product')

        res = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id,
            lang, update_tax, date_order, packaging, fiscal_position, flag)

        if 'domain' in res:
            del res['domain']

        if product:
            if partner_id:
                # Test the compatibility of the product with the partner of the order
                res, test = product_obj._on_change_restriction_error(cr, uid, product, field_name='product_id', values=res, vals={'partner_id': partner_id, 'obj_type': 'sale.order'})
                if test:
                    return res

            type = product_obj.read(cr, uid, [product], 'procure_method')[0]['procure_method']
            if 'value' in res:
                res['value'].update({'type': type})
            else:
                res.update({'value':{'type': type}})
            res['value'].update({'product_uom_qty': qty, 'product_uos_qty': qty})
        elif not product:
            if 'value' in res:
                res['value'].update({'type': 'make_to_order'})
            else:
                res.update({'value':{'type': 'make_to_order'}})
            res['value'].update({'product_uom_qty': 0.00, 'product_uos_qty': 0.00})

        return res

    def default_get(self, cr, uid, fields, context=None):
        """
        Default procurement method is 'on order' if no product selected
        """
        if not context:
            context = {}

        if context.get('sale_id'):
            # Check validity of the field order. We write the order to avoid
            # the creation of a new line if one line of the order is not valid
            # according to the order category
            # Example : 
            #    1/ Create a new FO with 'Other' as Order Category
            #    2/ Add a new line with a Stockable product
            #    3/ Change the Order Category of the FO to 'Service' -> A warning message is displayed
            #    4/ Try to create a new line -> The system displays a message to avoid you to create a new line
            #       while the not valid line is not modified/deleted
            #
            #   Without the write of the order, the message displayed by the system at 4/ is displayed at the saving
            #   of the new line that is not very understandable for the user
            data = {}
            if context.get('partner_id'):
                data.update({'partner_id': context.get('partner_id')})
            if context.get('categ'):
                data.update({'categ': context.get('categ')})
            self.pool.get('sale.order').write(cr, uid, [context.get('sale_id')], data, context=context)

        default_data = super(sale_order_line, self).default_get(cr, uid, fields, context=context)
        default_data.update({'product_uom_qty': 0.00, 'product_uos_qty': 0.00})
        sale_id = context.get('sale_id', [])
        if not sale_id:
            return default_data
        else:
            default_data.update({'type': 'make_to_order'})
        return default_data

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale order line
        '''
        if not context:
            context = {}
        
        if not default:
            default = {}
            
        default.update({'sync_order_line_db_id': False, 'manually_corrected': False})
        return super(sale_order_line, self).copy(cr, uid, id, default, context)

    def create(self, cr, uid, vals, context=None):
        """
        Override create method so that the procurement method is on order if no product is selected
        If it is a procurement request, we update the cost price.
        """
        if context is None:
            context = {}
        if not vals.get('product_id') and context.get('sale_id', []):
            vals.update({'type': 'make_to_order'})
        
        # UF-1739: as we do not have product_uos_qty in PO (only in FO), we recompute here the product_uos_qty for the SYNCHRO
        qty = vals.get('product_uom_qty')
        product_id = vals.get('product_id')
        product_obj = self.pool.get('product.product')
        if product_id and qty:
            if isinstance(qty, str):
                qty = float(qty)
            vals.update({'product_uos_qty' : qty * product_obj.read(cr, uid, product_id, ['uos_coeff'])['uos_coeff']})

        # Internal request
        order_id = vals.get('order_id', False)
        if order_id and self.pool.get('sale.order').read(cr, uid, order_id,['procurement_request'], context)['procurement_request']:
            vals.update({'cost_price': vals.get('cost_price', False)})

        '''
        Add the database ID of the SO line to the value sync_order_line_db_id
        '''
            
        so_line_ids = super(sale_order_line, self).create(cr, uid, vals, context=context)
        if not vals.get('sync_order_line_db_id', False): #'sync_order_line_db_id' not in vals or vals:
            if vals.get('order_id', False):
                name = self.pool.get('sale.order').browse(cr, uid, vals.get('order_id'), context=context).name
                super(sale_order_line, self).write(cr, uid, so_line_ids, {'sync_order_line_db_id': name + "_" + str(so_line_ids), } , context=context)

        return so_line_ids

    def write(self, cr, uid, ids, vals, context=None):
        """
        Override write method so that the procurement method is on order if no product is selected.
        If it is a procurement request, we update the cost price.
        """
        if context is None:
            context = {}
        
        # UTP-392: fixed from the previous code: check if the sale order line contains the product, and not only from vals!
        product_id = vals.get('product_id')
        if not product_id:
            product_id = self.browse(cr, uid, ids, context=context)[0].product_id
        
        if not product_id and context.get('sale_id', []):
            vals.update({'type': 'make_to_order'})
        # Internal request
        order_id = vals.get('order_id', False)
        if order_id and self.pool.get('sale.order').read(cr, uid, order_id,['procurement_request'], context)['procurement_request']:
            vals.update({'cost_price': vals.get('cost_price', False)})

        res = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

        return res

sale_order_line()


class procurement_order(osv.osv):
    _inherit = 'procurement.order'

    _columns = {
        'sale_id': fields.many2one('sale.order', string='Sale'),
    }

procurement_order()


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

class sale_order_line_unlink_wizard(osv.osv_memory):
    _name = 'sale.order.line.unlink.wizard'

    _columns = {
            'order_line_id': fields.many2one('sale.order.line', 'Line to delete'),
            }

    def ask_unlink(self, cr, uid, order_line_id, context=None):
        '''
        Return the wizard
        '''
        context = context or {}

        if isinstance(order_line_id, (int, long)):
            order_line_id = [order_line_id]

        wiz_id = self.create(cr, uid, {'order_line_id': order_line_id[0]}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def close_window(self, cr, uid, ids, context=None):
        '''
        Close the pop-up and reload the FO
        '''
        return {'type': 'ir.actions.act_window_close'}

    def cancel_fo_line(self, cr, uid, ids, context=None):
        '''
        Cancel the FO line and display the FO form
        '''
        context = context or {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = False

        for wiz in self.browse(cr, uid, ids, context=context):
            res = self.pool.get('sale.order.line').ask_order_unlink(cr, uid, [wiz.order_line_id.id], context=context)
            break

        return res or {'type': 'ir.actions.act_window_close'}

    def resource_line(self, cr, uid, ids, context=None):
        '''
        Resource the FO line and display the FO form
        '''
        context = context or {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('sale.order.line').add_resource_line(cr, uid, wiz.order_line_id.id, False, wiz.order_line_id.product_uom_qty, context=context)

        return self.cancel_fo_line(cr, uid, ids, context=context)

sale_order_line_unlink_wizard()

class sale_order_unlink_wizard(osv.osv_memory):
    _name = 'sale.order.unlink.wizard'

    _columns = {
        'order_id': fields.many2one('sale.order', 'Order to delete'),
    }

    def ask_unlink(self, cr, uid, order_id, context=None):
        '''
        Return the wizard
        '''
        context = context or {}

        wiz_id = self.create(cr, uid, {'order_id': order_id}, context=context)
        context['view_id'] = False

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def close_window(self, cr, uid, ids, context=None):
        '''
        Close the pop-up and reload the FO
        '''
        return {'type': 'ir.actions.act_window_close'}

    def cancel_fo(self, cr, uid, ids, context=None):
        '''
        Cancel the FO and display the FO form
        '''
        context = context or {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            self.pool.get('sale.order').action_cancel(cr, uid, [wiz.order_id.id], context=context)

        return {'type': 'ir.actions.act_window_close'}

sale_order_unlink_wizard()


class sale_order_cancelation_wizard(osv.osv_memory):
    _name = 'sale.order.cancelation.wizard'

    _columns = {
        'order_id': fields.many2one('sale.order', 'Order to delete', required=True),
    }

    def only_cancel(self, cr, uid, ids, context=None):
        '''
        Cancel the FO w/o re-sourcing lines
        '''
        # Objects
        sale_obj = self.pool.get('sale.order')

        # Variables initialization
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [id]

        for wiz in self.browse(cr, uid, ids, context=context):
            sale_obj.action_cancel(cr, uid, [wiz.order_id.id], context=context)

        return {'type': 'ir.actions.act_window_close'}

    def resource_lines(self, cr, uid, ids, context=None):
        '''
        Cancel the FO and re-source all lines
        '''
        # Objects
        sale_obj = self.pool.get('sale.order')
        line_obj = self.pool.get('sale.order.line')

        # Variables initialization
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        for wiz in self.browse(cr, uid, ids, context=context):
            # Re-source lines
            for line in wiz.order_id.order_line:
                line_obj.add_resource_line(cr, uid, line.id, line.order_id.id, line.product_uom_qty, context=context)

            # Cancel FO
            wf_service.trg_validate(uid, 'sale.order', wiz.order_id.id, 'cancel', cr)

        return {'type': 'ir.actions.act_window_close'}

sale_order_cancelation_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
