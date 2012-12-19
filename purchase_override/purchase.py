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
import time
from osv.orm import browse_record, browse_null
from workflow.wkf_expr import _eval_expr
import logging

from dateutil.relativedelta import relativedelta
from datetime import datetime

import decimal_precision as dp

from purchase_override import PURCHASE_ORDER_STATE_SELECTION

class purchase_order_confirm_wizard(osv.osv):
    _name = 'purchase.order.confirm.wizard'
    
    _columns = {
            'order_id': fields.many2one('purchase.order', string='Purchase Order', readonly=True),
            'errors': fields.text(string='Error message', readonly=True),
        }
    
    def validate_order(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for wiz in self.browse(cr, uid, ids, context=context):
            wf_service.trg_validate(uid, 'purchase.order', wiz.order_id.id, 'purchase_confirmed_wait', cr)
        return {'type': 'ir.actions.act_window_close'}
    
purchase_order_confirm_wizard()

class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        Remove loan_id field on new purchase.order
        '''
        if not default:
            default = {}
            
        default.update({'loan_id': False, 'merged_line_ids': False, 'origin': False, 'partner_ref': False, })
        return super(purchase_order, self).copy(cr, uid, id, default, context=context)
    
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
            if ((purchase.order_type == 'regular' and purchase.partner_id.partner_type in ('internal', 'esc')) or \
                purchase.order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']):
                res[purchase.id] = purchase.shipped_rate
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
    
    def _get_allocation_setup(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the Unifield configuration value
        '''
        res = {}
        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        
        for order in ids:
            res[order] = setup.allocation_setup
        
        return res
    
    def _get_no_line(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = True
            for line in order.order_line:
                res[order.id] = False
                break
            # better: if order.order_line: res[order.id] = False
                
        return res
    
    _columns = {
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'), 
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), 
                                        ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                        ('direct', 'Direct Purchase Order')], string='Order Type', required=True, states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'loan_id': fields.many2one('sale.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        # we increase the size of the 'details' field from 30 to 86
        'details': fields.char(size=86, string='Details', states={'cancel':[('readonly',True)], 'confirmed_wait':[('readonly',True)], 'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'invoiced': fields.function(_invoiced, method=True, string='Invoiced', type='boolean', help="It indicates that an invoice has been generated"),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'from_yml_test': fields.boolean('Only used to pass addons unit test', readonly=True, help='Never set this field to true !'),
        'date_order':fields.date(string='Creation Date', readonly=True, required=True,
                            states={'draft':[('readonly',False)],}, select=True, help="Date on which this document has been created."),
        'name': fields.char('Order Reference', size=64, required=True, select=True, readonly=True,
                            help="unique number of the purchase order,computed automatically when the purchase order is created"),
        'invoice_ids': fields.many2many('account.invoice', 'purchase_invoice_rel', 'purchase_id', 'invoice_id', 'Invoices', help="Invoices generated for a purchase order", readonly=True),
        'order_line': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft':[('readonly',False)], 'rfq_sent':[('readonly',False)], 'confirmed': [('readonly',False)]}),
        'partner_id':fields.many2one('res.partner', 'Supplier', required=True, states={'rfq_sent':[('readonly',True)], 'rfq_done':[('readonly',True)], 'rfq_updated':[('readonly',True)], 'confirmed':[('readonly',True)], 'confirmed_wait':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)],'cancel':[('readonly',True)]}, change_default=True, domain="[('id', '!=', company_id)]"),
        'partner_address_id':fields.many2one('res.partner.address', 'Address', required=True,
            states={'rfq_sent':[('readonly',True)], 'rfq_done':[('readonly',True)], 'rfq_updated':[('readonly',True)], 'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]},domain="[('partner_id', '=', partner_id)]"),
        'dest_partner_id': fields.many2one('res.partner', string='Destination partner', domain=[('partner_type', '=', 'internal')]),
        'invoice_address_id': fields.many2one('res.partner.address', string='Invoicing address', required=True, 
                                              help="The address where the invoice will be sent."),
        'invoice_method': fields.selection([('manual','Manual'),('order','From Order'),('picking','From Picking')], 'Invoicing Control', required=True, readonly=True,
            help="From Order: a draft invoice will be pre-generated based on the purchase order. The accountant " \
                "will just have to validate this invoice for control.\n" \
                "From Picking: a draft invoice will be pre-generated based on validated receptions.\n" \
                "Manual: allows you to generate suppliers invoices by chosing in the uninvoiced lines of all manual purchase orders."
        ),
        'merged_line_ids': fields.one2many('purchase.order.merged.line', 'order_id', string='Merged line'),
        'date_confirm': fields.date(string='Confirmation date'),
        'allocation_setup': fields.function(_get_allocation_setup, type='selection',
                                            selection=[('allocated', 'Allocated'),
                                                       ('unallocated', 'Unallocated'),
                                                       ('mixed', 'Mixed')], string='Allocated setup', method=True, store=False),
        'unallocation_ok': fields.boolean(string='Unallocated PO'),
        # we increase the size of the partner_ref field from 64 to 128
        'partner_ref': fields.char('Supplier Reference', size=128),
        'product_id': fields.related('order_line', 'product_id', type='many2one', relation='product.product', string='Product'),
        'no_line': fields.function(_get_no_line, method=True, type='boolean', string='No line'),
        'active': fields.boolean('Active', readonly=True),
    }
    
    _defaults = {
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': 2,
        'from_yml_test': lambda *a: False,
        'invoice_address_id': lambda obj, cr, uid, ctx: obj.pool.get('res.partner').address_get(cr, uid, obj.pool.get('res.users').browse(cr, uid, uid, ctx).company_id.partner_id.id, ['invoice'])['invoice'],
        'invoice_method': lambda *a: 'picking',
        'dest_address_id': lambda obj, cr, uid, ctx: obj.pool.get('res.partner').address_get(cr, uid, obj.pool.get('res.users').browse(cr, uid, uid, ctx).company_id.partner_id.id, ['delivery'])['delivery'],
        'no_line': lambda *a: True,
        'active': True,
        'name': lambda *a: False,
    }
    
    def _check_service(self, cr, uid, ids, vals, context=None):
        '''
        Avoid the saving of a PO with non service products on Service PO
        '''
        categ = {'transport': _('Transport'),
                 'service': _('Service')}
        
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                if vals.get('categ', order.categ) == 'transport' and line.product_id and (line.product_id.type not in ('service', 'service_recep') or not line.product_id.transport_ok):
                    raise osv.except_osv(_('Error'), _('The product [%s]%s is not a \'Transport\' product. You can purchase only \'Transport\' products on a \'Transport\' purchase order. Please remove this line.') % (line.product_id.default_code, line.product_id.name))
                    return False
                elif vals.get('categ', order.categ) == 'service' and line.product_id and line.product_id.type not in ('service', 'service_recep'):
                    raise osv.except_osv(_('Error'), _('The product [%s] %s is not a \'Service\' product. You can purchase only \'Service\' products on a \'Service\' purchase order. Please remove this line.') % (line.product_id.default_code, line.product_id.name))
                    return False
                
        return True                    

    def default_get(self, cr, uid, fields, context=None):
        '''
        Fill the unallocated_ok field according to Unifield setup
        '''
        res = super(purchase_order, self).default_get(cr, uid, fields, context=context)

        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res.update({'unallocation_ok': False, 'allocation_setup': setup.allocation_setup})
        if setup.allocation_setup == 'unallocated':
            res.update({'unallocation_ok': True})

        res.update({'name': False})

        return res


    def _check_user_company(self, cr, uid, company_id, context=None):
        '''
        Remove the possibility to make a PO to user's company
        '''
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        if company_id == user_company_id:
            raise osv.except_osv(_('Error'), _('You cannot made a purchase order to your own company !'))

        return True

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Check if the partner is correct.
        # UTP-114 demand purchase_list PO to be "from picking" as invoice_method
        '''
        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)
            
        self._check_service(cr, uid, ids, vals, context=context)
            
        if vals.get('order_type'):
            if vals.get('order_type') in ['donation_exp', 'donation_st', 'loan']:
                vals.update({'invoice_method': 'manual'})
            elif vals.get('order_type') in ['direct',]:
                vals.update({'invoice_method': 'order'})
            else:
                vals.update({'invoice_method': 'picking'})

        return super(purchase_order, self).write(cr, uid, ids, vals, context=context)
    
    def onchange_internal_type(self, cr, uid, ids, order_type, partner_id, categ, dest_partner_id=False, warehouse_id=False, delivery_requested_date=False):
        '''
        Changes the invoice method of the purchase order according to
        the choosen order type
        Changes the partner to local market if the type is Purchase List
        '''
        partner_obj = self.pool.get('res.partner')
        v = {}
        # the domain on the onchange was replace by a several fields.function that you can retrieve in the 
        # file msf_custom_settings/view/purchase_view.xml: domain="[('supplier', '=', True), ('id', '!=', company_id), ('check_partner_po', '=', order_type),  ('check_partner_rfq', '=', tender_id)]"
#        d = {'partner_id': []}
        w = {}
        local_market = None
        
        # Search the local market partner id
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj.search(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'), ('name', '=', 'res_partner_local_market')] )
        if data_id:
            local_market = data_obj.read(cr, uid, data_id, ['res_id'])[0]['res_id']
            
        if order_type == 'loan':
            setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
                
            if not setup.field_orders_ok:
                return {'value': {'order_type': 'regular'},
                        'warning': {'title': 'Error',
                                    'message': 'The Field orders feature is not activated on your system, so, you cannot create a Loan Purchase Order !'}}
        
        if order_type in ['donation_exp', 'donation_st', 'loan']:
            v['invoice_method'] = 'manual'
        elif order_type in ['direct']:
            v['invoice_method'] = 'order'
#            d['partner_id'] = [('partner_type', 'in', ['esc', 'external'])]
        elif order_type in ['in_kind', 'purchase_list']:
            v['invoice_method'] = 'picking'
#            d['partner_id'] = [('partner_type', 'in', ['esc', 'external'])]
        else:
            v['invoice_method'] = 'picking'
        
        if order_type == 'direct' and dest_partner_id:
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, dest_partner_id, ['delivery'])['delivery']
            v.update({'dest_address_id': cp_address_id})
#            d.update({'dest_address_id': [('partner_id', '=', dest_partner_id)]})
        elif order_type == 'direct':
            v.update({'dest_address_id': False})
#            d.update({'dest_address_id': [('partner_id', '=', self.pool.get('res.users').browse(cr, uid, uid).company_id.id)]})
        else:
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id, ['delivery'])['delivery']
            v.update({'dest_address_id': cp_address_id})
#            d.update({'dest_address_id': [('partner_id', '=', self.pool.get('res.users').browse(cr, uid, uid).company_id.id)]})

        if partner_id and partner_id != local_market:
            partner = partner_obj.browse(cr, uid, partner_id)
            if partner.partner_type in ('internal', 'esc') and order_type == 'regular':
                v['invoice_method'] = 'manual'
            elif partner.partner_type not in ('external', 'esc') and order_type == 'direct':
                v.update({'partner_address_id': False, 'partner_id': False, 'pricelist_id': False,})
#                d['partner_id'] = [('partner_type', 'in', ['esc', 'external'])]
                w.update({'message': 'You cannot have a Direct Purchase Order with a partner which is not external or an ESC',
                          'title': 'An error has occured !'})
        elif partner_id and partner_id == local_market and order_type != 'purchase_list':
            v['partner_id'] = None
            v['partner_address_id'] = None
            v['pricelist_id'] = None
            
        if order_type == 'purchase_list':
            if local_market:
                partner = self.pool.get('res.partner').browse(cr, uid, local_market)
                v['partner_id'] = partner.id
                if partner.address:
                    v['partner_address_id'] = partner.address[0].id
                if partner.property_product_pricelist_purchase:
                    v['pricelist_id'] = partner.property_product_pricelist_purchase.id
        elif order_type == 'direct':
            v['cross_docking_ok'] = False
        
#        return {'value': v, 'domain': d, 'warning': w}
        return {'value': v, 'warning': w}
    
    def onchange_partner_id(self, cr, uid, ids, part, *a, **b):
        '''
        Fills the Requested and Confirmed delivery dates
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        res = super(purchase_order, self).onchange_partner_id(cr, uid, ids, part, *a, **b)
        
        if part:
            partner_obj = self.pool.get('res.partner')
            partner = partner_obj.browse(cr, uid, part)
            if partner.partner_type in ('internal', 'esc'):
                res['value']['invoice_method'] = 'manual'
        
        return res
    
    # Be careful during integration, the onchange_warehouse_id method is also defined on UF-965
    def onchange_warehouse_id(self, cr, uid, ids,  warehouse_id, order_type, dest_address_id):
        '''
        Change the destination address to the destination address of the company if False
        '''
        res = super(purchase_order, self).onchange_warehouse_id(cr, uid, ids, warehouse_id)
        
        if not res.get('value', {}).get('dest_address_id') and order_type!='direct':
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id, ['delivery'])['delivery']
            if 'value' in res:
                res['value'].update({'dest_address_id': cp_address_id})
            else:
                res.update({'value': {'dest_address_id': cp_address_id}})
        if order_type == 'direct' or dest_address_id:
            if 'dest_address_id' in res.get('value', {}):
                res['value'].pop('dest_address_id')
        
        return res
    
    def on_change_dest_partner_id(self, cr, uid, ids, dest_partner_id, context=None):
        '''
        Fill automatically the destination address according to the destination partner
        '''
        v = {}
        d = {}
        
        if not context:
            context = {}
        
        company_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.id
        
        if not dest_partner_id:
            v.update({'dest_address_id': False})
            d.update({'dest_address_id': [('partner_id', '=', company_id)]})
        else:
            d.update({'dest_address_id': [('partner_id', '=', dest_partner_id)]})
        
            delivery_addr = self.pool.get('res.partner').address_get(cr, uid, dest_partner_id, ['delivery'])
            v.update({'dest_address_id': delivery_addr['delivery']})
        
        return {'value': v, 'domain': d}
    
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
            wiz = self.pool.get('purchase.order.change.currency').create(cr, uid, data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order.change.currency',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_id': wiz,
                    'target': 'new'}
            
        return True
    
    def order_line_change(self, cr, uid, ids, order_line):
        res = {'no_line': True}
        
        if order_line:
            res = {'no_line': False}
        
        return {'value': res}

    def _hook_confirm_order_message(self, cr, uid, context=None, *args, **kwargs):
        '''
        Change the logged message
        '''
        if context is None:
            context = {}
        if 'po' in kwargs:
            po = kwargs['po']
            return _("Purchase order '%s' is validated.") % (po.name,)
        else:
            return super(purchase_order, self)._hook_confirm_order_message(cr, uid, context, args, kwargs)

    def _get_destination_ok(self, cr, uid, lines, context):
        dest_ok = False
        for line in lines:
            is_inkind = False
            if line.order_id and line.order_id.order_type == 'in_kind':
                is_inkind = True
            dest_ok = line.account_4_distribution and line.account_4_distribution.destination_ids or False
            if not dest_ok:
                if is_inkind:
                    raise osv.except_osv(_('Error'), _('No destination found. An In-kind Donation expense account is probably missing for this line: %s.') % (line.name or ''))
                raise osv.except_osv(_('Error'), _('No destination found for this line: %s.') % (line.name or '',))
        return dest_ok

    def check_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Check analytic distribution validity for given PO.
        Also check that partner have a donation account (is PO is in_kind)
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Analytic distribution verification
        for po in self.browse(cr, uid, ids, context=context):
            if po.order_type and po.order_type == 'in_kind':
                if not po.partner_id.donation_payable_account:
                    raise osv.except_osv(_('Error'), _('No donation account on this partner: %s') % (po.partner_id.name or '',))
            for pol in po.order_line:
                # Forget check if we come from YAML tests
                if po.from_yml_test:
                    continue
                distrib_id = (pol.analytic_distribution_id and pol.analytic_distribution_id.id) or (po.analytic_distribution_id and po.analytic_distribution_id.id) or False
                # Raise an error if no analytic distribution found
                if not distrib_id:
                    raise osv.except_osv(_('Warning'), _('Analytic allocation is mandatory for this line: %s!') % (pol.name or '',))
                # Change distribution to be valid if needed by using those from header
                if pol.analytic_distribution_state != 'valid':
                    id_ad = self.pool.get('analytic.distribution').create(cr, uid, {})
                    for line in pol.analytic_distribution_id and pol.analytic_distribution_id.cost_center_lines or po.analytic_distribution_id.cost_center_lines:
                        # fetch compatible destinations then use on of them:
                        # - destination if compatible
                        # - else default destination of given account
                        bro_dests = self._get_destination_ok(cr, uid, [pol], context=context)
                        if line.destination_id in bro_dests:
                            bro_dest_ok = line.destination_id
                        else:
                            bro_dest_ok = pol.account_4_distribution.default_destination_id
                        # Copy cost center line to the new distribution
                        self.pool.get('cost.center.distribution.line').copy(cr, uid, line.id, {'distribution_id': id_ad, 'destination_id': bro_dest_ok.id})
                        # Write result
                        self.pool.get('purchase.order.line').write(cr, uid, [pol.id], {'analytic_distribution_id': id_ad})
        return True

    def wkf_confirm_order(self, cr, uid, ids, context=None):
        '''
        Update the confirmation date of the PO at confirmation.
        Check analytic distribution.
        '''
        for order in self.browse(cr, uid, ids, context=context):
            if order.categ in ['transport', 'service']:
                ch_res = self.onchange_categ(cr, uid, [order.id], order.categ, order.warehouse_id.id, order.cross_docking_ok, order.location_id.id, context=context)
                if ch_res.get('warning', {}).get('message', False):
                    raise osv.except_osv(_('Error'), ch_res.get('warning', {}).get('message', ''))
            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [('in_search', '=', order.partner_id.partner_type)], context=context)
            if order.pricelist_id.id not in pricelist_ids:
                raise osv.except_osv(_('Error'), _('The currency used on the order is not compatible with the supplier. Please change the currency to choose a compatible currency.'))
        res = super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'date_confirm': time.strftime('%Y-%m-%d')}, context=context)
        # CODE MOVED TO self.check_analytic_distribution()
        self.check_analytic_distribution(cr, uid, ids, context=context)
        return res

    def wkf_picking_done(self, cr, uid, ids, context=None):
        '''
        Change the shipped boolean and the state of the PO
        '''
        for order in self.browse(cr, uid, ids, context=context):
            if order.order_type == 'direct':
                self.write(cr, uid, order.id, {'state': 'approved'}, context=context)
            else:
                self.write(cr, uid, order.id, {'shipped':1,'state':'approved'}, context=context)

        return True
    
    def confirm_button(self, cr, uid, ids, context=None):
        '''
        check the supplier partner type (partner_type)
        
        confirmation is needed for internal, inter-mission and inter-section
        
        ('internal', 'Internal'), ('section', 'Inter-section'), ('intermission', 'Intermission')
        '''
        # data
        name = _("You're about to confirm a PO that is synchronized and should be consequently confirmed by the supplier (automatically at his equivalent FO confirmation). Are you sure you want to force the confirmation at your level (you won't get the supplier's update)?")
        model = 'confirm'
        step = 'default'
        question = "You're about to confirm a PO that is synchronized and should be consequently confirmed by the supplier (automatically at his equivalent FO confirmation). Are you sure you want to force the confirmation at your level (you won't get the supplier's update)?"
        clazz = 'purchase.order'
        func = '_purchase_approve'
        args = [ids]
        kwargs = {}
                
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.partner_id.partner_type in ('internal', 'section', 'intermission'):
                # open the wizard
                wiz_obj = self.pool.get('wizard')
                # open the selected wizard
                res = wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, step=step, context=dict(context, question=question,
                                                                                                        callback={'clazz': clazz,
                                                                                                                  'func': func,
                                                                                                                  'args': args,
                                                                                                                  'kwargs': kwargs}))
                return res
            
        # otherwise call function directly
        return self.purchase_approve(cr, uid, ids, context=context)
    
    def _purchase_approve(self, cr, uid, ids, context=None):
        '''
        interface for call from wizard
        
        if called from wizard without opening a new dic -> return close
        if called from wizard with new dic -> open new wizard
        
        if called from button directly, this interface is not called
        '''
        res = self.purchase_approve(cr, uid, ids, context=context)
        if not isinstance(res, dict):
            return {'type': 'ir.actions.act_window_close'}
        return res
    
    def purchase_approve(self, cr, uid, ids, context=None):
        '''
        If the PO is a DPO, check the state of the stock moves
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        wf_service = netsvc.LocalService("workflow")
        move_obj = self.pool.get('stock.move')
            
        for order in self.browse(cr, uid, ids, context=context):
            if order.categ in ['transport', 'service']:
                ch_res = self.onchange_categ(cr, uid, [order.id], order.categ, order.warehouse_id.id, order.cross_docking_ok, order.location_id.id, context=context)
                if ch_res.get('warning', {}).get('message', False):
                    raise osv.except_osv(_('Error'), ch_res.get('warning', {}).get('message', ''))
            if not order.delivery_confirmed_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            todo = []
            todo2 = []
            todo3 = []
            
            if order.order_type == 'direct':
                for line in order.order_line:
                    if line.procurement_id: todo.append(line.procurement_id.id)
                    
            if todo:
                todo2 = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', 'in', todo)], context=context)
            
            if todo2:
                sm_ids = move_obj.search(cr, uid, [('sale_line_id', 'in', todo2)], context=context)
                error_moves = []
                for move in move_obj.browse(cr, uid, sm_ids, context=context):
                    backmove_ids = self.pool.get('stock.move').search(cr, uid, [('backmove_id', '=', move.id)])
                    if move.state == 'done':
                        error_moves.append(move)
                    if backmove_ids:
                        for bmove in move_obj.browse(cr, uid, backmove_ids):
                            error_moves.append(bmove)
                        
                if error_moves:
                    errors = '''You are trying to confirm a Direct Purchase Order.
At Direct Purchase Order confirmation, the system tries to change the state of concerning OUT moves but for this DPO, the system has detected 
stock moves which are already processed : '''
                    for m in error_moves:
                        errors = '%s \n %s' % (errors, '''
        * Picking : %s - Product : [%s] %s - Product Qty. : %s %s \n''' % (m.picking_id.name, m.product_id.default_code, m.product_id.name, m.product_qty, m.product_uom.name))
                        
                    errors = '%s \n %s' % (errors, 'This warning is only for informational purpose. The stock moves already processed will not be modified by this confirmation.')
                        
                    wiz_id = self.pool.get('purchase.order.confirm.wizard').create(cr, uid, {'order_id': order.id,
                                                                                             'errors': errors})
                    return {'type': 'ir.actions.act_window',
                            'res_model': 'purchase.order.confirm.wizard',
                            'res_id': wiz_id,
                            'view_type': 'form',
                            'view_mode': 'form',
                            'target': 'new'}
            
            # If no errors, validate the DPO
            wf_service.trg_validate(uid, 'purchase.order', order.id, 'purchase_confirmed_wait', cr)
            
        return True
    
    def get_so_ids_from_po_ids(self, cr, uid, ids, context=None):
        '''
        receive the list of purchase order ids
        
        return the list of sale order ids corresponding (through procurement process)
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        sol_obj = self.pool.get('sale.order.line')
        # sale order list
        so_ids = []
        
        # get the sale order lines
        sol_ids = self.get_sol_ids_from_po_ids(cr, uid, ids, context=context)
        if sol_ids:
            # list of dictionaries for each sale order line
            datas = sol_obj.read(cr, uid, sol_ids, ['order_id'], context=context)
            # we retrieve the list of sale order ids
            for data in datas:
                if data['order_id'] and data['order_id'][0] not in so_ids:
                    so_ids.append(data['order_id'][0])
        return so_ids
    
    def get_sol_ids_from_po_ids(self, cr, uid, ids, context=None):
        '''
        receive the list of purchase order ids
        
        return the list of sale order line ids corresponding (through procurement process)
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        sol_obj = self.pool.get('sale.order.line')
        # procurement ids list
        proc_ids = []
        # sale order lines list
        sol_ids = []
        
        for po in self.browse(cr, uid, ids, context=context):
            for line in po.order_line:
                if line.procurement_id:
                    proc_ids.append(line.procurement_id.id)
        # get the corresponding sale order line list
        if proc_ids:
            sol_ids = sol_obj.search(cr, uid, [('procurement_id', 'in', proc_ids)], context=context)
        return sol_ids
    
    def common_code_from_wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        delivery confirmed date at po level is mandatory
        update corresponding date at line level if needed.
        Check analytic distribution
        '''
        # objects
        ana_obj = self.pool.get('analytic.distribution')
        
        # Check analytic distribution
        self.check_analytic_distribution(cr, uid, ids, context=context)
        for po in self.browse(cr, uid, ids, context=context):
            # CODE MOVED TO self.check_analytic_distribution()
            # msf_order_date checks
            if not po.delivery_confirmed_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            for line in po.order_line:
                if not line.confirmed_delivery_date:
                    line.write({'confirmed_delivery_date': po.delivery_confirmed_date,}, context=context)
        # MOVE code for COMMITMENT into wkf_approve_order
        return True
    
    def wkf_confirm_wait_order(self, cr, uid, ids, context=None):
        """
        Checks:
        1/ if all purchase line could take an analytic distribution
        2/ if a commitment voucher should be created after PO approbation
        
        _> originally in purchase.py from analytic_distribution_supply
        
        Checks if the Delivery Confirmed Date has been filled
        
        _> originally in order_dates.py from msf_order_date
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        sol_obj = self.pool.get('sale.order.line')
        
        # code from wkf_approve_order
        self.common_code_from_wkf_approve_order(cr, uid, ids, context=context)
        # set the state of purchase order to confirmed_wait
        self.write(cr, uid, ids, {'state': 'confirmed_wait'}, context=context)
        # sale order lines with modified state
        sol_ids = self.get_sol_ids_from_po_ids(cr, uid, ids, context=context)
        if sol_ids:
            sol_obj.write(cr, uid, sol_ids, {'state': 'confirmed'}, context=context)
        
        # !!BEWARE!! we must update the So lines before any writing to So objects
        for po in self.browse(cr, uid, ids, context=context): 
            # hook for corresponding Fo update
            self._hook_confirm_order_update_corresponding_so(cr, uid, ids, context=context, po=po)
        
        return True
    
    def compute_confirmed_delivery_date(self, cr, uid, ids, confirmed, prep_lt, ship_lt, est_transport_lead_time, db_date_format, context=None):
        '''
        compute the confirmed date
        
        confirmed must be string
        return string corresponding to database format
        '''
        assert type(confirmed) == str
        confirmed = datetime.strptime(confirmed, db_date_format)
        confirmed = confirmed + relativedelta(days=prep_lt or 0)
        confirmed = confirmed + relativedelta(days=ship_lt or 0)
        confirmed = confirmed + relativedelta(days=est_transport_lead_time or 0)
        confirmed = confirmed.strftime(db_date_format)
        
        return confirmed
    
    def _hook_confirm_order_update_corresponding_so(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Add a hook to update correspondingn so
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        po = kwargs['po']
        pol_obj = self.pool.get('purchase.order.line')
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        
        # update corresponding fo if exist
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        if so_ids:
            # date values
            ship_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
            prep_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)
            
            for line in po.order_line:
                # get the corresponding so line
                sol_ids = pol_obj.get_sol_ids_from_pol_ids(cr, uid, [line.id], context=context)
                if sol_ids:
                    # get so_id
                    data = sol_obj.read(cr, uid, sol_ids, ['order_id'], context=context)
                    order_id = data[0]['order_id'][0]
                    # get est_transport_lead_time of corresponding so
                    data = so_obj.read(cr, uid, order_id, ['est_transport_lead_time'], context=context)
                    est_transport_lead_time = data['est_transport_lead_time']
                    
                    line_confirmed = False
                    # compute confirmed date for line
                    if line.confirmed_delivery_date:
                        line_confirmed = self.compute_confirmed_delivery_date(cr, uid, ids, line.confirmed_delivery_date,
                                                                              prep_lt, ship_lt, est_transport_lead_time,
                                                                              db_date_format, context=context)
                    # we update the corresponding sale order line
                    sol = sol_obj.browse(cr, uid, sol_ids[0], context=context)
                    # do not update Internal Requests
                    if sol.order_id.procurement_request:
                        continue
                    # {sol: pol}
                    # compute the price_unit value - we need to specify the date
                    date_context = {'date': po.date_order}
                    # convert from currency of pol to currency of sol
                    price_unit_converted = self.pool.get('res.currency').compute(cr, uid, line.currency_id.id,
                                                                                 sol.currency_id.id, line.price_unit or 0.0,
                                                                                 round=False, context=date_context)
                    fields_dic = {'product_id': line.product_id and line.product_id.id or False,
                                  'name': line.name,
                                  'default_name': line.default_name,
                                  'default_code': line.default_code,
                                  'product_uom_qty': line.product_qty,
                                  'product_uom': line.product_uom and line.product_uom.id or False,
                                  'product_uos_qty': line.product_qty,
                                  'product_uos': line.product_uom and line.product_uom.id or False,
                                  'price_unit': price_unit_converted,
                                  'nomenclature_description': line.nomenclature_description,
                                  'nomenclature_code': line.nomenclature_code,
                                  'comment': line.comment,
                                  'nomen_manda_0': line.nomen_manda_0 and line.nomen_manda_0.id or False,
                                  'nomen_manda_1': line.nomen_manda_1 and line.nomen_manda_1.id or False,
                                  'nomen_manda_2': line.nomen_manda_2 and line.nomen_manda_2.id or False,
                                  'nomen_manda_3': line.nomen_manda_3 and line.nomen_manda_3.id or False,
                                  'nomen_sub_0': line.nomen_sub_0 and line.nomen_sub_0.id or False,
                                  'nomen_sub_1': line.nomen_sub_1 and line.nomen_sub_1.id or False,
                                  'nomen_sub_2': line.nomen_sub_2 and line.nomen_sub_2.id or False,
                                  'nomen_sub_3': line.nomen_sub_3 and line.nomen_sub_3.id or False,
                                  'nomen_sub_4': line.nomen_sub_4 and line.nomen_sub_4.id or False,
                                  'nomen_sub_5': line.nomen_sub_5 and line.nomen_sub_5.id or False,
                                  'confirmed_delivery_date': line_confirmed,
                                  }
                    # write the line
                    sol_obj.write(cr, uid, sol_ids, fields_dic, context=context)
            
            # compute so dates -- only if we get a confirmed value, because rts is mandatory on So side
            # update after lines update, as so write triggers So workflow, and we dont want the Out document
            # to be created with old So datas
            if po.delivery_confirmed_date:
                for so in so_obj.browse(cr, uid, so_ids, context=context):
                    # Fo rts = Po confirmed date + prep_lt
                    delivery_confirmed_date = datetime.strptime(po.delivery_confirmed_date, db_date_format)
                    so_rts = delivery_confirmed_date + relativedelta(days=prep_lt or 0)
                    so_rts = so_rts.strftime(db_date_format)
                
                    # Fo confirmed date = confirmed date + prep_lt + ship_lt + transport_lt
                    so_confirmed = self.compute_confirmed_delivery_date(cr, uid, ids, po.delivery_confirmed_date,
                                                                        prep_lt, ship_lt, so.est_transport_lead_time,
                                                                        db_date_format, context=context)
                    # write data to so
                    so_obj.write(cr, uid, [so.id], {'delivery_confirmed_date': so_confirmed,
                                                   'ready_to_ship_date': so_rts}, context=context)
            
        return True

    def check_if_product(self, cr, uid, ids, context=None):
        """
        Check if all line have a product before confirming the Purchase Order
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for po in self.browse(cr, uid, ids, context=context):
            if po.order_line:
                for line in po.order_line:
                    if not line.product_id:
                        raise osv.except_osv(_('Error !'), _('You should have a product on all Purchase Order lines to be able to confirm the Purchase Order.') )
        return True

    def all_po_confirmed(self, cr, uid, ids, context=None):
        '''
        condition for the po to leave the act_confirmed_wait state
        
        if the po is from scratch (no procurement), or from replenishment mechanism (procurement but no sale order line)
        the method will return True and therefore the po workflow is not blocked
        
        only 'make_to_order' sale order lines are checked, we dont care on state of 'make_to_stock' sale order line
        _> anyway, thanks to Fo split, make_to_stock and make_to_order so lines are separated in different sale orders
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # objects
        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        
        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)
        # if we have sol_ids, we are treating a po which is make_to_order from sale order
        if all_so_ids:
            # we retrieve the list of ids of all sale order line if type 'make_to_order' with state != 'confirmed'
            # with product_id (if no product id, no procurement, no po, so should not be taken into account)
            # in case of grouped po, multiple Fo depend on this po, all Po of these Fo need to be completed
            # and all Fo will be confirmed together. Because IN of grouped Po need corresponding OUT document of all Fo
            # internal request are automatically 'confirmed'
            # not take done into account, because IR could be done as they are confirmed before the Po are all done
            # see video in uf-1050 for detail
            all_sol_not_confirmed_ids = sol_obj.search(cr, uid, [('order_id', 'in', all_so_ids),
                                                                 ('type', '=', 'make_to_order'),
                                                                 ('product_id', '!=', False),
                                                                 ('state', 'not in', ['confirmed', 'done'])], context=context)
            # if any lines exist, we return False
            if all_sol_not_confirmed_ids:
                return False
            
        return True
    
    def wkf_confirm_trigger(self, cr, uid, ids, context=None):
        '''
        trigger corresponding so then po
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        proc_obj = self.pool.get('procurement.order')
        wf_service = netsvc.LocalService("workflow")
        
        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po first level
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)
        # from all so, list all corresponding po second level
        all_po_for_all_so_ids = so_obj.get_po_ids_from_so_ids(cr, uid, all_so_ids, context=context)
        
        # we trigger all the corresponding sale order -> test_lines is called on these so
        for so_id in all_so_ids:
            wf_service.trg_write(uid, 'sale.order', so_id, cr)
            
        # we trigger pos of all sale orders -> all_po_confirm is called on these po
        for po_id in all_po_for_all_so_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)
        
        return True
    
    def wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        Checks if the invoice should be create from the purchase order
        or not
        If the PO is a DPO, set all related OUT stock move to 'done' state
        '''
        line_obj = self.pool.get('purchase.order.line')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        # duplicated code with wkf_confirm_wait_order because of backward compatibility issue with yml tests for dates,
        # which doesnt execute wkf_confirm_wait_order (null value in column "date_expected" violates not-null constraint for stock.move otherwise)
        # msf_order_date checks
        self.common_code_from_wkf_approve_order(cr, uid, ids, context=context)

        for order in self.browse(cr, uid, ids):
            # Create commitments for each PO only if po is "from picking"
            # UTP-114: No Commitment Voucher on PO that are 'purchase_list'!
            if order.invoice_method in ['picking', 'order'] and not order.from_yml_test and order.order_type not in ['in_kind', 'purchase_list'] and order.partner_id.partner_type != 'intermission':
                self.action_create_commitment(cr, uid, [order.id], order.partner_id and order.partner_id.partner_type, context=context)
            # Don't accept the confirmation of regular PO with 0.00 unit price lines
            if order.order_type == 'regular':
                line_error = []
                for line in order.order_line:
                    if line.price_unit == 0.00:
                        line_error.append(line.line_number)

                if len(line_error) > 0:
                    errors = ' / '.join(str(x) for x in line_error)
                    raise osv.except_osv(_('Error !'), _('You cannot have a purchase order line with a 0.00 Unit Price. Lines in exception : %s') % errors)

            todo = []
            todo2 = []
            todo3 = []
            if order.partner_id.partner_type in ('internal', 'esc') and order.order_type == 'regular' or \
                         order.order_type in ['donation_exp', 'donation_st', 'loan']:
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
                line_obj.write(cr, uid, [x.id for x in order.order_line], {'invoiced': 1})

            message = _("Purchase order '%s' is confirmed.") % (order.name,)
            self.log(cr, uid, order.id, message)
            
            if order.order_type == 'direct':
                self.write(cr, uid, [order.id], {'invoice_method': 'order'}, context=context)
                for line in order.order_line:
                    if line.procurement_id: todo.append(line.procurement_id.id)
                    
            if todo:
                todo2 = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', 'in', todo)], context=context)
            
            if todo2:
                sm_ids = move_obj.search(cr, uid, [('sale_line_id', 'in', todo2)], context=context)
                self.pool.get('stock.move').action_confirm(cr, uid, sm_ids, context=context)
                stock_location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
                for move in move_obj.browse(cr, uid, sm_ids, context=context):
                    # Search if this move has been processed
                    backmove_ids = self.pool.get('stock.move').search(cr, uid, [('backmove_id', '=', move.id)])
                    if move.state != 'done' and not backmove_ids and not move.backmove_id:
                        move_obj.write(cr, uid, sm_ids, {'dpo_id': order.id, 'state': 'done',
                                                         'location_id': stock_location_id,
                                                         'location_dest_id': stock_location_id, 
                                                         'date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
                        wf_service.trg_trigger(uid, 'stock.move', move.id, cr)
                        if move.picking_id: 
                            all_move_closed = True
                            # Check if the picking should be updated
                            if move.picking_id.subtype == 'picking':
                                for m in move.picking_id.move_lines:
                                    if m.id not in sm_ids and m.state != 'done':
                                        all_move_closed = False
                            # If all stock moves of the picking is done, trigger the workflow
                            if all_move_closed:
                                todo3.append(move.picking_id.id)
                
            if todo3:
                for pick_id in todo3:
                    wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
                    wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
            
        return super(purchase_order, self).wkf_approve_order(cr, uid, ids, context=context)
    
    def action_sale_order_create(self, cr, uid, ids, context=None):
        '''
        Create a sale order as counterpart for the loan.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
            
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        sale_shop = self.pool.get('sale.shop')
        partner_obj = self.pool.get('res.partner')
            
        for order in self.browse(cr, uid, ids):
            loan_duration = Parser.DateFromString(order.minimum_planned_date) + RelativeDateTime(months=+order.loan_duration)
            # from yml test is updated according to order value
            values = {'shop_id': sale_shop.search(cr, uid, [])[0],
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
                      'priority': order.priority,
                      'from_yml_test': order.from_yml_test,
                      }
            order_id = sale_obj.create(cr, uid, values, context=context)
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
            
            message = _("Loan counterpart '%s' has been created.") % (sale.name,)
            
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
        when the invoice comes from a purchase list.
        Change journal to an inkind journal if we comes from a In-kind Donation PO
        '''
        invoice_id = super(purchase_order, self).action_invoice_create(cr, uid, ids, args)
        invoice_obj = self.pool.get('account.invoice')
        inkind_journal_ids = self.pool.get('account.journal').search(cr, uid, [
                    ("type", "=", "inkind"),
                    ('is_current_instance', '=', True)
                ])

        for order in self.browse(cr, uid, ids):
            if order.order_type == 'purchase_list':
                invoice_obj.write(cr, uid, [invoice_id], {'purchase_list': 1})
            elif order.order_type == 'in_kind':
                if not inkind_journal_ids:
                    raise osv.except_osv(_('Error'), _('No In-kind Donation journal found!'))
                invoice_obj.write(cr, uid, [invoice_id], {'journal_id': inkind_journal_ids[0], 'is_inkind_donation': True})

        return invoice_id
    
    def _hook_action_picking_create_modify_out_source_loc_check(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_picking_create method from purchase>purchase.py>purchase_order class
        
        - allow to choose whether or not the source location of the corresponding outgoing stock move should
        match the destination location of incoming stock move
        '''
        order_line = kwargs['order_line']
        # by default, we change the destination stock move if the destination stock move exists
        return order_line.move_dest_id
    
    def _hook_action_picking_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        modify data for stock move creation
        '''
        move_values = kwargs['move_values']
        return move_values
    
    # @@@override@purchase.purchase.order.action_picking_create
    def action_picking_create(self,cr, uid, ids, context=None, *args):
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
                'partner_id2': order.partner_id.id,
                'address_id': order.partner_address_id.id or False,
                'invoice_state': istate,
                'purchase_id': order.id,
                'company_id': order.company_id.id,
                'move_lines' : [],
            }

            if order.order_type in ('regular', 'purchase_list', 'direct') and order.partner_id.partner_type in ('internal', 'intermission', 'section', 'esc'):
                reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1]
            elif order.order_type in ('regular', 'purchase_list', 'direct'):
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
                # Reload the data of the line because if the line comes from an ISR and it's a duplicate line,
                # the move_dest_id field has been changed by the _hook_action_picking_create_modify_out_source_loc_check method
                order_line = self.pool.get('purchase.order.line').browse(cr, uid, order_line.id, context=context)
                if not order_line.product_id:
                    continue
                dest = order.location_id.id
                # service with reception are directed to Service Location
                if order_line.product_id.type == 'service_recep' and not order.cross_docking_ok:
                    dest = self.pool.get('stock.location').get_service_location(cr, uid)
                        
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
                    'price_currency_id': order.pricelist_id.currency_id.id,
                    'price_unit': order_line.price_unit
                }
                # hook for stock move values modification
                move_values = self._hook_action_picking_create_stock_picking(cr, uid, ids, context=context, move_values=move_values, order_line=order_line,)
                
                if reason_type_id:
                    move_values.update({'reason_type_id': reason_type_id})
                
                move = self.pool.get('stock.move').create(cr, uid, move_values, context=context)
                if self._hook_action_picking_create_modify_out_source_loc_check(cr, uid, ids, context=context, order_line=order_line, move_id=move):
                    self.pool.get('stock.move').write(cr, uid, [order_line.move_dest_id.id], {'location_id':order.location_id.id})
                todo_moves.append(move)
            self.pool.get('stock.move').action_confirm(cr, uid, todo_moves)
            self.pool.get('stock.move').force_assign(cr, uid, todo_moves)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
        # @@@end

    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests
        # UTP-114 demands purchase_list PO to be 'from picking'.
        """
        if not context:
            context = {}

        if context.get('update_mode') in ['init', 'update'] and 'from_yml_test' not in vals:
            logging.getLogger('init').info('PO: set from yml test to True')
            vals['from_yml_test'] = True
            
        if vals.get('order_type'):
            if vals.get('order_type') in ['donation_exp', 'donation_st', 'loan']:
                vals.update({'invoice_method': 'manual'})
            elif vals.get('order_type') in ['direct']:
                vals.update({'invoice_method': 'order'})
            else:
                vals.update({'invoice_method': 'picking'})
            
        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)
            
        res = super(purchase_order, self).create(cr, uid, vals, context=context)
        self._check_service(cr, uid, [res], vals, context=context)
    
        return res

    def wkf_action_cancel_po(self, cr, uid, ids, context=None):
        """
        Cancel activity in workflow.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.write(cr, uid, ids, {'state':'cancel'}, context=context)

    def action_done(self, cr, uid, ids, context=None):
        """
        Done activity in workflow.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for order in self.browse(cr, uid, ids, context=context):
            vals = {'state': 'done'}
            if order.order_type == 'direct':
                vals.update({'shipped': 1})
            self.write(cr, uid, order.id, vals, context=context)
        return True

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the PO to done state
        '''
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        order_lines = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                order_lines.append(line.id)

            # Done picking
            for pick in order.picking_ids:
                if pick.state not in ('cancel', 'done'):
                    wf_service.trg_validate(uid, 'stock.picking', pick.id, 'manually_done', cr)

            # Done loan counterpart
            if order.loan_id and order.loan_id.state not in ('cancel', 'done') and not context.get('loan_id', False) == order.id:
                loan_context = context.copy()
                loan_context.update({'loan_id': order.id})
                self.pool.get('sale.order').set_manually_done(cr, uid, order.loan_id.id, all_doc=all_doc, context=loan_context)

            # Done invoices
            #invoice_error_ids = []
            #for invoice in order.invoice_ids:
            #    if invoice.state == 'draft':
            #        wf_service.trg_validate(uid, 'account.invoice', invoice.id, 'invoice_cancel', cr)
            #    elif invoice.state not in ('cancel', 'done'):
            #        invoice_error_ids.append(invoice.id)
#
#            if invoice_error_ids:
#                invoices_ref = ' / '.join(x.number for x in self.pool.get('account.invoice').browse(cr, uid, invoice_error_ids, context=context))
#                raise osv.except_osv(_('Error'), _('The state of the following invoices cannot be updated automatically. Please cancel them manually or discuss with the accounting team to solve the problem.' \
#                                'Invoices references : %s') % invoices_ref)

        # Done stock moves
        move_ids = self.pool.get('stock.move').search(cr, uid, [('purchase_line_id', 'in', order_lines), ('state', 'not in', ('cancel', 'done'))], context=context)
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)

        # Cancel all procurement ordes which have generated one of these PO
        proc_ids = self.pool.get('procurement.order').search(cr, uid, [('purchase_id', 'in', ids)], context=context)
        for proc in self.pool.get('procurement.order').browse(cr, uid, proc_ids, context=context):
            self.pool.get('stock.move').write(cr, uid, [proc.move_id.id], {'state': 'cancel'}, context=context)
            wf_service.trg_validate(uid, 'procurement.order', proc.id, 'subflow.cancel', cr)

        if all_doc:
            # Detach the PO from his workflow and set the state to done
            for order_id in self.browse(cr, uid, ids, context=context):
                if order_id.rfq_ok and order_id.state == 'draft':
                    wf_service.trg_validate(uid, 'purchase.order', order_id.id, 'purchase_cancel', cr)
                elif order_id.tender_id:
                    raise osv.except_osv(_('Error'), _('You cannot \'Close\' a Request for Quotation attached to a tender. Please make the tender %s to \'Closed\' before !') % order_id.tender_id.name)
                else:
                    wf_service.trg_delete(uid, 'purchase.order', order_id.id, cr)
                    # Search the method called when the workflow enter in last activity
                    wkf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'act_done')[1]
                    activity = self.pool.get('workflow.activity').browse(cr, uid, wkf_id, context=context)
                    res = _eval_expr(cr, [uid, 'purchase.order', order_id.id], False, activity.action)

        return True
    
    def _hook_order_infos(self, cr, uid, *args, **kwargs):
        '''
        Hook to change the values of the PO
        '''
        order_infos = super(purchase_order, self)._hook_order_infos(cr, uid, *args, **kwargs)
        order_id = kwargs['order_id']
        
        fields = ['invoice_method', 'minimum_planned_date', 'order_type',
                  'categ', 'priority', 'internal_type', 'arrival_date',
                  'transport_type', 'shipment_date', 'ready_to_ship_date',
                  'cross_docking_ok', 'delivery_confirmed_date',
                  'est_transport_lead_time', 'transport_mode', 'location_id',
                  'dest_address_id', 'incoterm_id']
        

        delivery_requested_date = getattr(order_id, 'delivery_requested_date')
        if not order_infos.get('delivery_requested_date') or delivery_requested_date < order_infos['delivery_requested_date']:
            order_infos['delivery_requested_date'] = delivery_requested_date
        
        
        for field in fields:
            field_val = getattr(order_id, field)
            if isinstance(field_val, browse_record):
                field_val = field_val.id
            elif isinstance(field_val, browse_null):
                field_val = False
            elif isinstance(field_val, list):
                field_val = ((6, 0, tuple([v.id for v in field_val])),)
            order_infos[field] = field_val
            
        return order_infos
    
    def _hook_o_line_value(self, cr, uid, *args, **kwargs):
        o_line = super(purchase_order, self)._hook_o_line_value(cr, uid, *args, **kwargs)
        order_line = kwargs['order_line']
        
        # Copy all fields except order_id and analytic_distribution_id
        fields = ['product_uom', 'price_unit', 'move_dest_id', 'product_qty', 'partner_id',
                  'confirmed_delivery_date', 'nomenclature_description', 'default_code', 
                  'nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3',
                  'nomenclature_code', 'name', 'default_name', 'comment', 'date_planned',
                  'to_correct_ok', 'text_error', 
                  'nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4', 
                  'nomen_sub_5', 'procurement_id', 'change_price_manually', 'old_price_unit',
                  'origin', 'account_analytic_id', 'product_id', 'company_id', 'notes', 'taxes_id']
        
        for field in fields:
            field_val = getattr(order_line, field)
            if isinstance(field_val, browse_record):
                field_val = field_val.id
            elif isinstance(field_val, browse_null):
                field_val = False
            elif isinstance(field_val, list):
                field_val = ((6, 0, tuple([v.id for v in field_val])),)
            o_line[field] = field_val
            
        
        # Set the analytic distribution 
        distrib_id = False
        if order_line.analytic_distribution_id:
            distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, order_line.analytic_distribution_id.id)
        elif order_line.order_id.analytic_distribution_id:
            distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, order_line.order_id.analytic_distribution_id.id)
            
        o_line['analytic_distribution_id'] = distrib_id
        
        return o_line
    
purchase_order()


class purchase_order_line(osv.osv):
    '''
    this modification is placed before merged, because unit price of merged should be Computation as well
    '''
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'
    _columns = {'price_unit': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price Computation')),
                }
    
purchase_order_line()


class purchase_order_merged_line(osv.osv):
    '''
    A purchase order merged line is a special PO line.
    These lines give the total quantity of all normal PO lines
    which have the same product and the same quantity.
    When a new normal PO line is created, the system will check
    if this new line can be attached to other PO lines. If yes,
    the unit price of all normal PO lines with the same product and
    the same UoM will be computed from supplier catalogue and updated on lines.
    '''
    _name = 'purchase.order.merged.line'
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Merged Lines'
    _table = 'purchase_order_merged_line'

    def _get_name(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.order_line_ids:
                res[line.id] = line.product_id and line.product_id.name or line.order_line_ids[0].comment
        return res

    _columns = {
        'order_line_ids': fields.one2many('purchase.order.line', 'merged_id', string='Purchase Lines'),
        'date_planned': fields.date(string='Delivery Requested Date', required=False, select=True,
                                            help='Header level dates has to be populated by default with the possibility of manual updates'),
        'name': fields.function(_get_name, method=True, type='char', string='Name', store=False),
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Set the line number to 0
        '''
        if self._name == 'purchase.order.merged.line':
            vals.update({'line_number': 0})
        return super(purchase_order_merged_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update unit price of PO lines attached to the merged line
        '''
        if context is None:
            context = {}
        new_context = context.copy()
        new_context.update({'update_merge': True})
        # If the unit price is changing, update the price unit of all normal PO lines
        # associated to this merged PO line
        if 'price_unit' in vals:
            for merged_line in self.browse(cr, uid, ids, context=context):
                for po_line in merged_line.order_line_ids:
                    self.pool.get('purchase.order.line').write(cr, uid, [po_line.id], {'price_unit': vals['price_unit'],
                                                                                       'old_price_unit': vals['price_unit']}, context=new_context)

        return super(purchase_order_merged_line, self).write(cr, uid, ids, vals, context=context)

    def _update(self, cr, uid, id, po_line_id, product_qty, price=0.00, context=None, no_update=False):
        '''
        Update the quantity and the unit price according to the new qty
        '''
        line = self.browse(cr, uid, id, context=context)
        change_price_ok = True
        if not po_line_id:
            change_price_ok = context.get('change_price_ok', True)
        else:
            po_line = self.pool.get('purchase.order.line').browse(cr, uid, po_line_id, context=context)
            change_price_ok = po_line.change_price_ok
            if 'change_price_ok' in context:
                change_price_ok = context.get('change_price_ok')

        # If no PO line attached to this merged line, remove the merged line
        if not line.order_line_ids:
            self.unlink(cr, uid, [id], context=context)
            return False, False

        new_price = False
        new_qty = line.product_qty + product_qty
        
        if (po_line_id and not change_price_ok and not po_line.order_id.rfq_ok) or (not po_line_id and not change_price_ok):    
            # Get the catalogue unit price according to the total qty
            new_price = self.pool.get('product.pricelist').price_get(cr, uid, 
                                                              [line.order_id.pricelist_id.id],
                                                              line.product_id.id,
                                                              new_qty,
                                                              line.order_id.partner_id.id,
                                                              {'uom': line.product_uom.id,
                                                               'date': line.order_id.date_order})[line.order_id.pricelist_id.id]                                      
        
        # Update the quantity of the merged line                  
        values = {'product_qty': new_qty}
        # If a catalogue unit price exist and the unit price is not manually changed
        if new_price:
            values.update({'price_unit': new_price})
        else:
            # Keep the unit price given by the user
            values.update({'price_unit': price})
            new_price = price

        # Update the unit price and the quantity of the merged line
        if not no_update:
            self.write(cr, uid, [id], values, context=context)

        return id, new_price or False


purchase_order_merged_line()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def link_merged_line(self, cr, uid, vals, product_id, order_id, product_qty, uom_id, price_unit=0.00, context=None):
        '''
        Check if a merged line exist. If not, create a new one and attach them to the Po line
        '''
        line_obj = self.pool.get('purchase.order.merged.line')
        if product_id:
            domain = [('product_id', '=', product_id), ('order_id', '=', order_id), ('product_uom', '=', uom_id)]
            # Search if a merged line already exist for the same product, the same order and the same UoM
            merged_ids = line_obj.search(cr, uid, domain, context=context)
        else:
            merged_ids = []
        
        new_vals = vals.copy()
        # Don't include taxes on merged lines
        if 'taxes_id' in new_vals:
            new_vals.pop('taxes_id')

        if not merged_ids:
            new_vals['order_id'] = order_id
            if not new_vals.get('price_unit', False):
                new_vals['price_unit'] = price_unit
            # Create a new merged line which is the same than the normal PO line except for price unit
            vals['merged_id'] = line_obj.create(cr, uid, new_vals, context=context)
        else:
            c = context.copy()
            order = self.pool.get('purchase.order').browse(cr, uid, order_id, context=context)
            stages = self._get_stages_price(cr, uid, product_id, uom_id, order, context=context)
            if order.state != 'confirmed' and stages and not order.rfq_ok:
                c.update({'change_price_ok': False})
            # Update the associated merged line
            res_merged = line_obj._update(cr, uid, merged_ids[0], False, product_qty, price_unit, context=c, no_update=False)
            vals['merged_id'] = res_merged[0]
            # Update unit price
            vals['price_unit'] = res_merged[1]

        return vals

    def _update_merged_line(self, cr, uid, line_id, vals=None, context=None):
        '''
        Update the merged line
        '''
        merged_line_obj = self.pool.get('purchase.order.merged.line')
        
        if not vals:
            vals = {}
        tmp_vals = vals.copy()

        # If it's an update of a line
        if vals and line_id:
            line = self.browse(cr, uid, line_id, context=context)
            
            # Set default values if not pass in values
            if not 'product_uom' in vals: 
                tmp_vals.update({'product_uom': line.product_uom.id})
            if not 'product_qty' in vals: 
                tmp_vals.update({'product_qty': line.product_qty})
            
            # If the user changed the product or the UoM or both on the PO line
            if ('product_id' in vals and line.product_id.id != vals['product_id']) or ('product_uom' in vals and line.product_uom.id != vals['product_uom']):
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                merged_id = line.merged_id.id
                change_price_ok = line.change_price_ok
                c = context.copy()
                c.update({'change_price_ok': change_price_ok})
                self.write(cr, uid, line_id, {'merged_id': False}, context=context)
                res_merged = merged_line_obj._update(cr, uid, merged_id, line.id, -line.product_qty, line.price_unit, context=c)
                
                # Create or update an existing merged line with the new product
                vals = self.link_merged_line(cr, uid, tmp_vals, tmp_vals.get('product_id', line.product_id.id), line.order_id.id, tmp_vals.get('product_qty', line.product_qty), tmp_vals.get('product_uom', line.product_uom.id), tmp_vals.get('price_unit', line.price_unit), context=context)
            
            # If the quantity is changed
            elif 'product_qty' in vals and line.product_qty != vals['product_qty']:
                res_merged = merged_line_obj._update(cr, uid, line.merged_id.id, line.id, vals['product_qty']-line.product_qty, line.price_unit, context=context)
                # Update the unit price
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})
                    
            # If the price unit is changed and the product and the UoM is not modified
            if 'price_unit' in tmp_vals and (line.price_unit != tmp_vals['price_unit'] or vals['price_unit'] != tmp_vals['price_unit']) and not (line.product_id.id != vals.get('product_id', False) or line.product_uom.id != vals.get('product_uom', False)):
                # Give 0.00 to quantity because the _update should recompute the price unit with the same quantity
                res_merged = merged_line_obj._update(cr, uid, line.merged_id.id, line.id, 0.00, tmp_vals['price_unit'], context=context)
                # Update the unit price
                if res_merged and res_merged[1]:
                    vals.update({'price_unit': res_merged[1]})
        # If it's a new line
        elif not line_id:
            c = context.copy()
            vals = self.link_merged_line(cr, uid, vals, vals.get('product_id'), vals['order_id'], vals['product_qty'], vals['product_uom'], vals['price_unit'], context=c)
        # If the line is removed
        elif not vals:
            line = self.browse(cr, uid, line_id, context=context)
            # Remove the qty from the merged line
            if line.merged_id:
                merged_id = line.merged_id.id
                change_price_ok = line.change_price_ok
                c = context.copy()
                c.update({'change_price_ok': change_price_ok})
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                self.write(cr, uid, [line.id], {'merged_id': False}, context=context)
                res_merged = merged_line_obj._update(cr, uid, merged_id, line.id, -line.product_qty, line.price_unit, context=c)

        return vals

    def create(self, cr, uid, vals, context=None):
        '''
        Create or update a merged line
        '''
        if not context:
            context = {}
            
        order_id = self.pool.get('purchase.order').browse(cr, uid, vals['order_id'], context=context)
        if order_id.from_yml_test:
            vals.update({'change_price_manually': True})
            if not vals.get('product_qty', False):
                vals['product_qty'] = 1.00
                
        # If we are on a RfQ, use the last entered unit price and update other lines with this price
        if order_id.rfq_ok:
            vals.update({'change_price_manually': True})
        else:
            if vals.get('product_qty', 0.00) == 0.00:
                raise osv.except_osv(_('Error'), _('You cannot save a line with no quantity !'))
        
        order_id = vals.get('order_id')
        product_id = vals.get('product_id')
        product_uom = vals.get('product_uom')
        order = self.pool.get('purchase.order').browse(cr, uid, order_id, context=context)
        other_lines = self.search(cr, uid, [('order_id', '=', order_id), ('product_id', '=', product_id), ('product_uom', '=', product_uom)], context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)

        if (other_lines and stages and order.state != 'confirmed'):
            context.update({'change_price_ok': False})

        vals = self._update_merged_line(cr, uid, False, vals, context=dict(context, skipResequencing=True))

        vals.update({'old_price_unit': vals.get('price_unit', False)})

        # add the database Id to the sync_order_line_db_id
        po_line_id = super(purchase_order_line, self).create(cr, uid, vals, context=context)
        if not vals.get('sync_order_line_db_id', False): #'sync_order_line_db_id' not in vals or vals:
            name = self.pool.get('purchase.order').browse(cr, uid, vals.get('order_id'), context=context).name
            super(purchase_order_line, self).write(cr, uid, po_line_id, {'sync_order_line_db_id': name + "_" + str(po_line_id),}, context=context)

        return po_line_id
    
    def default_get(self, cr, uid, fields, context=None):
        if not context:
            context = {}

        if context.get('purchase_id'):
            # Check validity of the purchase order. We write the order to avoid
            # the creation of a new line if one line of the order is not valid
            # according to the order category
            # Example : 
            #    1/ Create a new PO with 'Other' as Order Category
            #    2/ Add a new line with a Stockable product
            #    3/ Change the Order Category of the PO to 'Service' -> A warning message is displayed
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
            self.pool.get('purchase.order').write(cr, uid, [context.get('purchase_id')], data, context=context)

        return super(purchase_order_line, self).default_get(cr, uid, fields, context=context)

    def copy(self, cr, uid, line_id, defaults={}, context=None):
        '''
        Remove link to merged line
        '''
        defaults.update({'merged_id': False, 'sync_order_line_db_id': False, })

        return super(purchase_order_line, self).copy(cr, uid, line_id, defaults, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}
        default.update({'sync_order_line_db_id': False})
        return super(purchase_order_line, self).copy_data(cr, uid, id, default=default, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update merged line
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]
        
#        if ids and not isinstance(ids[0], (int, long)):
#            ids = [x.id for x in ids]
            
        for line in self.browse(cr, uid, ids, context=context):
            if vals.get('product_qty', line.product_qty) == 0.00 and not line.order_id.rfq_ok:
                raise osv.except_osv(_('Error'), _('You cannot save a line with no quantity !'))
        
        if not context.get('update_merge'):
            for line in ids:
                vals = self._update_merged_line(cr, uid, line, vals, context=dict(context, skipResequencing=True))
                
        if 'price_unit' in vals:
            vals.update({'old_price_unit': vals.get('price_unit')})

        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        Update the merged line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # if the line is linked to a sale order line through procurement process,
        # the deletion is impossible
        if self.get_sol_ids_from_pol_ids(cr, uid, ids, context=context):
            raise osv.except_osv(_('Error'), _('You cannot delete a line which is linked to a Fo line.'))

        for line_id in ids:
            # we want to skip resequencing because unlink is performed on merged purchase order lines
            self._update_merged_line(cr, uid, line_id, False, context=dict(context, skipResequencing=True))

        return super(purchase_order_line, self).unlink(cr, uid, ids, context=context)

    def _get_fake_state(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['state']):
            ret[pol['id']] = pol['state']
        return ret
    
    def _get_fake_id(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['id']):
            ret[pol['id']] = pol['id']
        return ret
    
    def _get_stages_price(self, cr, uid, product_id, uom_id, order, context=None):
        '''
        Returns True if the product/supplier couple has more than 1 line
        '''
        suppinfo_ids = self.pool.get('product.supplierinfo').search(cr, uid, [('name', '=', order.partner_id.id), 
                                                                              ('product_id', '=', product_id)], context=context)
        if suppinfo_ids:
            pricelist_ids = self.pool.get('pricelist.partnerinfo').search(cr, uid, [('currency_id', '=', order.pricelist_id.currency_id.id),
                                                                                    ('suppinfo_id', 'in', suppinfo_ids),
                                                                                    ('uom_id', '=', uom_id),
                                                                                    '|', ('valid_till', '=', False),
                                                                                    ('valid_till', '>=', order.date_order)], context=context)
            if len(pricelist_ids) > 1:
                return True
        
        return False
        
    def _get_price_change_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns True if the price can be changed by the user
        '''
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = True
            stages = self._get_stages_price(cr, uid, line.product_id.id, line.product_uom.id, line.order_id, context=context)
            if line.merged_id and len(line.merged_id.order_line_ids) > 1 and line.order_id.state != 'confirmed' and stages and not line.order_id.rfq_ok:
                res[line.id] = False
                        
        return res
    
    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        multi fields function method
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        sol_obj = self.pool.get('sale.order.line')
        
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # default values
            result[obj.id] = {'order_state_purchase_order_line': False}
            # order_state_purchase_order_line
            if obj.order_id:
                result[obj.id].update({'order_state_purchase_order_line': obj.order_id.state})
            
        return result

    _columns = {
        'parent_line_id': fields.many2one('purchase.order.line', string='Parent line', ondelete='set null'),
        'merged_id': fields.many2one('purchase.order.merged.line', string='Merged line'),
        'origin': fields.char(size=64, string='Origin'),
        'change_price_ok': fields.function(_get_price_change_ok, type='boolean', method=True, string='Price changing'),
        'change_price_manually': fields.boolean(string='Update price manually'),
        # openerp bug: eval invisible in p.o use the po line state and not the po state !
        'fake_state': fields.function(_get_fake_state, type='char', method=True, string='State', help='for internal use only'),
        # openerp bug: id is not given to onchanqge call if we are into one2many view
        'fake_id':fields.function(_get_fake_id, type='integer', method=True, string='Id', help='for internal use only'),
        'old_price_unit': fields.float(string='Old price', digits_compute=dp.get_precision('Purchase Price Computation')),
        'order_state_purchase_order_line': fields.function(_vals_get, method=True, type='selection', selection=PURCHASE_ORDER_STATE_SELECTION, string='State of Po', multi='get_vals_purchase_override', store=False, readonly=True),

        # This field is used to identify the FO PO line between 2 instances of the sync
        'sync_order_line_db_id': fields.text(string='Sync order line DB Id', required=False, readonly=True),
    }

    _defaults = {
        'change_price_manually': lambda *a: False,
        'product_qty': lambda *a: 0.00,
        'price_unit': lambda *a: 0.00,
        'change_price_ok': lambda *a: True,
    }
    
    _sql_constraints = [
        ('product_qty_check', 'CHECK( product_qty > 0 )', 'Product Quantity must be greater than zero.'),
    ]
    
    def product_uom_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False):
        qty = 0.00
        res = super(purchase_order_line, self).product_uom_change(cr, uid, ids, pricelist, product, qty, uom,
                                                                  partner_id, date_order, fiscal_position, date_planned,
                                                                  name, price_unit, notes)
        if not product:
            return res
        res['value'].update({'product_qty': 0.00})
        res.update({'warning': {}})
        
        return res
    
    def product_id_on_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False, fiscal_position=False, date_planned=False,
            name=False, price_unit=False, notes=False, state=False, old_price_unit=False,
            nomen_manda_0=False, comment=False, context=None):
        all_qty = qty
        suppinfo_obj = self.pool.get('product.supplierinfo')
        partner_price = self.pool.get('pricelist.partnerinfo')

        # If the user modify a line, remove the old quantity for the total quantity
        if ids:
            for line_id in self.browse(cr, uid, ids, context=context):
                all_qty -= line_id.product_qty
        
        if product and not uom:
            uom = self.pool.get('product.product').browse(cr, uid, product).uom_po_id.id
        
        if context and context.get('purchase_id') and state == 'draft' and product:    
            domain = [('product_id', '=', product), 
                      ('product_uom', '=', uom), 
                      ('order_id', '=', context.get('purchase_id'))]
            other_lines = self.search(cr, uid, domain)
            for l in self.browse(cr, uid, other_lines):
                all_qty += l.product_qty 
        
        res = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, all_qty, uom,
                                                                 partner_id, date_order, fiscal_position, 
                                                                 date_planned, name, price_unit, notes)
        
        # Remove the warning message if the product has no staged pricelist
#        if res.get('warning'):
#            supplier_info = self.pool.get('product.supplierinfo').search(cr, uid, [('product_id', '=', product)])
#            product_pricelist = self.pool.get('pricelist.partnerinfo').search(cr, uid, [('suppinfo_id', 'in', supplier_info)])
#            if not product_pricelist:
#                res['warning'] = {}
        if res.get('warning', {}).get('title', '') == 'No valid pricelist line found !' or qty == 0.00:
            res.update({'warning': {}})
        
        func_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        if pricelist:
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist).currency_id.id
        else:
            currency_id = func_curr_id
        
        # Update the old price value        
        res['value'].update({'product_qty': qty})
        if product and not res.get('value', {}).get('price_unit', False) and all_qty != 0.00 and qty != 0.00:
            # Display a warning message if the quantity is under the minimal qty of the supplier
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist).currency_id.id
            tmpl_id = self.pool.get('product.product').read(cr, uid, product, ['product_tmpl_id'])['product_tmpl_id'][0]
            info_prices = []
            domain = [('uom_id', '=', uom),
                      ('partner_id', '=', partner_id),
                      ('product_id', '=', tmpl_id),
                      '|', ('valid_from', '<=', date_order),
                      ('valid_from', '=', False),
                      '|', ('valid_till', '>=', date_order),
                      ('valid_till', '=', False)]
            
            domain_cur = [('currency_id', '=', currency_id)]
            domain_cur.extend(domain)
            
            info_prices = partner_price.search(cr, uid, domain_cur, order='sequence asc, min_quantity asc, id desc', limit=1, context=context)
            if not info_prices:
                info_prices = partner_price.search(cr, uid, domain, order='sequence asc, min_quantity asc, id desc', limit=1, context=context)
                
            if info_prices:
                info_price = partner_price.browse(cr, uid, info_prices[0], context=context)
                info_u_price = self.pool.get('res.currency').compute(cr, uid, info_price.currency_id.id, currency_id, info_price.price, round=False, context=context)
                res['value'].update({'old_price_unit': info_u_price, 'price_unit': info_u_price})
                res.update({'warning': {'title': _('Warning'), 'message': _('The product unit price has been set ' \
                                                                                'for a minimal quantity of %s (the min quantity of the price list), '\
                                                                                'it might change at the supplier confirmation.') % info_price.min_quantity}})
                if info_price.rounding and all_qty%info_price.rounding != 0:
                    message = _('A rounding value of %s UoM has been set for ' \
                            'this product, you should than modify ' \
                            'the quantity ordered to match the supplier criteria.') % info_price.rounding
                    message = '%s \n %s' % (res.get('warning', {}).get('message', ''), message)
                    res['warning'].update({'message': message})
            else:
                old_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, res['value']['price_unit'], round=False, context=context)
                res['value'].update({'old_price_unit': old_price})
        else:
            old_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, res.get('value').get('price_unit'), round=False, context=context)
            res['value'].update({'old_price_unit': old_price})
                
        # Set the unit price with cost price if the product has no staged pricelist
        if product and qty != 0.00: 
            res['value'].update({'comment': False, 'nomen_manda_0': False, 'nomen_manda_1': False,
                                 'nomen_manda_2': False, 'nomen_manda_3': False, 'nomen_sub_0': False, 
                                 'nomen_sub_1': False, 'nomen_sub_2': False, 'nomen_sub_3': False, 
                                 'nomen_sub_4': False, 'nomen_sub_5': False})
            st_price = self.pool.get('product.product').browse(cr, uid, product).standard_price
            st_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, st_price, round=False, context=context)
        
            if res.get('value', {}).get('price_unit', False) == False and (state and state == 'draft') or not state :
                res['value'].update({'price_unit': st_price, 'old_price_unit': st_price})
            elif state and state != 'draft' and old_price_unit:
                res['value'].update({'price_unit': old_price_unit, 'old_price_unit': old_price_unit})
                
            if res['value']['price_unit'] == 0.00:
                res['value'].update({'price_unit': st_price, 'old_price_unit': st_price})
                
        elif qty == 0.00:
            res['value'].update({'price_unit': 0.00, 'old_price_unit': 0.00})
        elif not product and not comment and not nomen_manda_0:
            res['value'].update({'price_unit': 0.00, 'product_qty': 0.00, 'product_uom': False, 'old_price_unit': 0.00})
        
        return res

    def price_unit_change(self, cr, uid, ids, fake_id, price_unit, product_id, 
                          product_uom, product_qty, pricelist, partner_id, date_order, 
                          change_price_ok, state, old_price_unit, 
                          nomen_manda_0=False, comment=False, context=None):
        '''
        Display a warning message on change price unit if there are other lines with the same product and the same uom
        '''
        res = {'value': {}}

        if context is None:
            context = {}
            
        if not product_id or not product_uom or not product_qty:
            return res
        
        order_id = context.get('purchase_id', False)
        if not order_id:
            return res

        order = self.pool.get('purchase.order').browse(cr, uid, order_id, context=context)
        other_lines = self.search(cr, uid, [('id', '!=', fake_id), ('order_id', '=', order_id), ('product_id', '=', product_id), ('product_uom', '=', product_uom)], context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)
        
        if not change_price_ok or (other_lines and stages and order.state != 'confirmed' and not context.get('rfq_ok')):
            res.update({'warning': {'title': 'Error',
                                    'message': 'This product get stages prices for this supplier, you cannot change the price manually in draft state '\
                                               'as you have multiple order lines (it is possible in "validated" state.'}})
            res['value'].update({'price_unit': old_price_unit})
        else:
            res['value'].update({'old_price_unit': price_unit})

        return res
    
    def get_sol_ids_from_pol_ids(self, cr, uid, ids, context=None):
        '''
        input: purchase order line ids
        return: sale order line ids
        '''
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        # objects
        sol_obj = self.pool.get('sale.order.line')
        # procurement ids list
        proc_ids = []
        # sale order lines list
        sol_ids = []
        
        for line in self.browse(cr, uid, ids, context=context):
            if line.procurement_id:
                proc_ids.append(line.procurement_id.id)
        # get the corresponding sale order line list
        if proc_ids:
            sol_ids = sol_obj.search(cr, uid, [('procurement_id', 'in', proc_ids)], context=context)
        return sol_ids

    def open_split_wizard(self, cr, uid, ids, context=None):
        '''
        Open the wizard to split the line
        '''
        if not context:
            context = {}
 
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            data = {'purchase_line_id': line.id, 'original_qty': line.product_qty, 'old_line_qty': line.product_qty}
            wiz_id = self.pool.get('split.purchase.order.line.wizard').create(cr, uid, data, context=context)
            return {'type': 'ir.actions.act_window',
                    'res_model': 'split.purchase.order.line.wizard',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': wiz_id,
                    'context': context}


purchase_order_line()

class purchase_order_group(osv.osv_memory):
    _name = "purchase.order.group"
    _inherit = "purchase.order.group"
    _description = "Purchase Order Merge"
    
    _columns = {
        'po_value_id': fields.many2one('purchase.order', string='Template PO', help='All values in this PO will be used as default values for the merged PO'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(purchase_order_group, self).default_get(cr, uid, fields, context=context)
        if context.get('active_model','') == 'purchase.order' and len(context['active_ids']) < 2:
            raise osv.except_osv(_('Warning'),
            _('Please select multiple order to merge in the list view.'))
            
        res['po_value_id'] = context['active_ids'][-1]
        
        return res
    
    def merge_orders(self, cr, uid, ids, context=None):
        res = super(purchase_order_group, self).merge_orders(cr, uid, ids, context=context)
        res.update({'context': {'search_default_draft': 1, 'search_default_approved': 0,'search_default_create_uid':uid, 'purchase_order': True}})
        
        if 'domain' in res and eval(res['domain'])[0][2]:
            return res
        
        raise osv.except_osv(_('Error'), _('No PO merged !'))
        return {'type': 'ir.actions.act_window_close'}
    
purchase_order_group()

class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _get_purchase_type(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for id in ids:
            res[id] = True
            
        return res
    
    def _src_purchase_type(self, cr, uid, obj, name, args, context=None):
        '''
        Returns a domain according to the PO type
        '''
        res = []
        for arg in args:
            if arg[0] == 'purchase_type':
                if arg[1] != '=':
                    raise osv.except_osv(_('Error'), _('Only the \'=\' operator is allowed.'))
                # Returns all service products
                if arg[2] == 'service':
                    res.append(('type', '=', 'service_recep'))
                elif arg[2] == 'transport':
                    res.append(('transport_ok', '=', True))

        return res

    _columns = {
        'purchase_type': fields.function(_get_purchase_type, fnct_search=_src_purchase_type, type='boolean', string='Purchase type', method=True, store=False),
    }
    
product_product()

class account_invoice(osv.osv):
    _name = 'account.invoice'
    _inherit = 'account.invoice'
    
    _columns = {
        'purchase_list': fields.boolean(string='Purchase List ?', help='Check this box if the invoice comes from a purchase list', readonly=True, states={'draft':[('readonly',False)]}),
    }
    
account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
