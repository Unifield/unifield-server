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
import time
import threading
import logging
import pooler
from mx.DateTime import Parser
from mx.DateTime import RelativeDateTime
from time import strftime
from osv.orm import browse_record, browse_null
from workflow.wkf_expr import _eval_expr

from dateutil.relativedelta import relativedelta
from datetime import datetime

import decimal_precision as dp

from purchase_override import PURCHASE_ORDER_STATE_SELECTION

class purchase_order_confirm_wizard(osv.osv):
    _name = 'purchase.order.confirm.wizard'
    _rec_name = 'order_id'

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

    def update_supplier_info(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        update the supplier info of corresponding products
        '''
        info_obj = self.pool.get('product.supplierinfo')
        pricelist_info_obj = self.pool.get('pricelist.partnerinfo')
        for rfq in self.browse(cr, uid, ids, context=context):
            for line in rfq.order_line:
                # if the price is updated and a product selected
                if line.price_unit and line.product_id:
                    # get the product
                    product = line.product_id
                    # find the corresponding suppinfo with sequence -99
                    info_99_list = info_obj.search(cr, uid, [('product_id', '=', product.product_tmpl_id.id),
                                                             ('sequence', '=', -99)],
                                                             order='NO_ORDER', context=context)

                    if info_99_list:
                        # we drop it
                        info_obj.unlink(cr, uid, info_99_list, context=context)

                    # create the new one
                    values = {'name': rfq.partner_id.id,
                              'product_name': False,
                              'product_code': False,
                              'sequence' : -99,
                              #'product_uom': line.product_uom.id,
                              #'min_qty': 0.0,
                              #'qty': function
                              'product_id' : product.product_tmpl_id.id,
                              'delay' : int(rfq.partner_id.default_delay),
                              #'pricelist_ids': created just after
                              #'company_id': default value
                              }

                    new_info_id = info_obj.create(cr, uid, values, context=context)
                    # price lists creation - 'pricelist.partnerinfo
                    values = {'suppinfo_id': new_info_id,
                              'min_quantity': 1.00,
                              'price': line.price_unit,
                              'uom_id': line.product_uom.id,
                              'currency_id': line.currency_id.id,
                              'valid_till': rfq.valid_till,
                              'purchase_order_line_id': line.id,
                              'comment': 'RfQ original quantity for price : %s' % line.product_qty,
                              }
                    pricelist_info_obj.create(cr, uid, values, context=context)

        return True

    def generate_po_from_rfq(self, cr, uid, ids, context=None):
        '''
        generate a po from the selected request for quotation
        '''
        # Objects
        line_obj = self.pool.get('purchase.order.line')

        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # update price lists
        self.update_supplier_info(cr, uid, ids, context=context)
        # copy the po with rfq_ok set to False
        data = self.read(cr, uid, ids[0], ['name', 'amount_total'], context=context)
        if not data.get('amount_total', 0.00):
            raise osv.except_osv(
                _('Error'),
                _('Generation of PO aborted because no price defined on lines.'),
            )
        new_po_id = self.copy(cr, uid, ids[0], {'name': False, 'rfq_ok': False, 'origin': data['name']}, context=dict(context,keepOrigin=True))
        # Remove lines with 0.00 as unit price
        no_price_line_ids = line_obj.search(cr, uid, [
            ('order_id', '=', new_po_id),
            ('price_unit', '=', 0.00),
        ], context=context)
        line_obj.unlink(cr, uid, no_price_line_ids, context=context)

        data = self.read(cr, uid, new_po_id, ['name'], context=context)
        # log message describing the previous action
        self.log(cr, uid, new_po_id, _('The Purchase Order %s has been generated from Request for Quotation.')%data['name'])
        # close the current po
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'purchase.order', ids[0], 'rfq_done', cr)

        return new_po_id

    def copy(self, cr, uid, p_id, default=None, context=None):
        '''
        Remove loan_id field on new purchase.order
        '''
        if not default:
            default = {}
        if context is None:
            context = {}

        # if the copy comes from the button duplicate
        if context.get('from_button'):
            default.update({'is_a_counterpart': False})
        default.update({'loan_id': False, 'merged_line_ids': False, 'partner_ref': False})
        if not context.get('keepOrigin', False):
            default.update({'origin': False})

        if not 'date_confirm' in default:
            default['date_confirm'] = False

        return super(purchase_order, self).copy(cr, uid, p_id, default, context=context)

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
        sp_obj = self.pool.get('stock.picking')
        inv_obj = self.pool.get('account.invoice')
        for purchase in self.browse(cursor, user, ids, context=context):
            if ((purchase.order_type == 'regular' and purchase.partner_id.partner_type in ('internal', 'esc')) or \
                purchase.order_type in ['donation_exp', 'donation_st', 'loan', 'in_kind']):
                res[purchase.id] = purchase.shipped_rate
            else:
                tot = 0.0
                # UTP-808: Deleted invoices amount should be taken in this process. So what we do:
                # 1/ Take all closed stock picking linked to the purchase
                # 2/ Search invoices linked to these stock picking
                # 3/ Take stock picking not linked to an invoice
                # 4/ Use these non-invoiced closed stock picking to add their amount to the "invoiced" amount
                for invoice in purchase.invoice_ids:
                    if invoice.state not in ('draft','cancel'):
                        tot += invoice.amount_untaxed
                stock_pickings = sp_obj.search(cursor, user, [('purchase_id', '=', purchase.id), ('state', '=', 'done')])
                if stock_pickings:
                    sp_ids = list(stock_pickings)
                    if isinstance(stock_pickings, (int, long)):
                        stock_pickings = [stock_pickings]
                    for sp in stock_pickings:
                        inv_ids = inv_obj.search(cursor, user, [('picking_id', '=', sp)], limit=1, order='NO_ORDER')
                        if inv_ids:
                            sp_ids.remove(sp)
                    if sp_ids:
                        for stock_picking in sp_obj.browse(cursor, user, sp_ids):
                            for line in stock_picking.move_lines:
                                tot += line.product_qty * line.price_unit
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
            if order.order_line:
                res[order.id] = False
        return res

    def _po_from_x(self, cr, uid, ids, field_names, args, context=None):
        """fields.function multi for 'po_from_ir' and 'po_from_fo' fields."""
        res = {}
        pol_obj = self.pool.get('purchase.order.line')
        sol_obj = self.pool.get('sale.order.line')
        for po_data in self.read(cr, uid, ids, ['order_line'], context=context):
            res[po_data['id']] = {'po_from_ir': False, 'po_from_fo': False}
            pol_ids = po_data.get('order_line')
            if pol_ids:
                pol_datas = pol_obj.read(
                    cr, uid, pol_ids, ['procurement_id'], context=context)
                proc_ids = [pol['procurement_id'][0]
                            for pol in pol_datas if pol.get('procurement_id')]
                if proc_ids:
                    # po_from_ir
                    sol_ids = sol_obj.search(
                        cr, uid,
                        [('procurement_id', 'in', proc_ids)],
                        limit=1, order='NO_ORDER', context=context)
                    res[po_data['id']]['po_from_ir'] = bool(sol_ids)
                    # po_from_fo
                    sol_ids = sol_obj.search(
                        cr, uid,
                        [('procurement_id', 'in', proc_ids),
                         ('order_id.procurement_request', '=', False)],
                        limit=1, order='NO_ORDER', context=context)
                    res[po_data['id']]['po_from_fo'] = bool(sol_ids)
        return res

    def _get_dest_partner_names(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        res_partner_obj = self.pool.get('res.partner')
        for po_r in self.read(cr, uid, ids, ['dest_partner_ids'], context=context):
            names = ''
            if po_r['dest_partner_ids']:
                name_tuples = res_partner_obj.name_get(cr, uid, po_r['dest_partner_ids'], context=context)
                if name_tuples:
                    names_list = [nt[1] for nt in name_tuples]
                    names = "; ".join(names_list)
            res[po_r['id']] = names
        return res

    def _get_project_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the name of the POs at project side
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for po in ids:
            res[po] = {
                'fnct_project_ref': '',
                'sourced_references': '',
            }

            so_ids = self.get_so_ids_from_po_ids(cr, uid, po, context=context)
            for so in self.pool.get('sale.order').browse(cr, uid, so_ids, context=context):
                if so.client_order_ref:
                    if res[po]['fnct_project_ref']:
                        res[po]['fnct_project_ref'] += ' - '
                    res[po]['fnct_project_ref'] += so.client_order_ref

                if res[po]['sourced_references']:
                    res[po]['sourced_references'] += ','
                res[po]['sourced_references'] += so.name

        return res

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def _get_requested_date_in_past(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for po in self.read(cr, uid, ids, ['delivery_requested_date', 'rfq_ok'], context=context):
            res[po['id']] = po['delivery_requested_date'] and not po['rfq_ok'] and po['delivery_requested_date'] < time.strftime('%Y-%m-%d') or False

        return res

    _columns = {
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                                        ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                        ('direct', 'Direct Purchase Order')], string='Order Type', required=True, states={'sourced':[('readonly',True)], 'split':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'loan_id': fields.many2one('sale.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, states={'approved':[('readonly',True)],'done':[('readonly',True)]}),
        # we increase the size of the 'details' field from 30 to 86
        'details': fields.char(size=86, string='Details', states={'sourced':[('readonly',True)], 'split':[('readonly',True)], 'cancel':[('readonly',True)], 'confirmed_wait':[('readonly',True)], 'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
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
        'partner_id':fields.many2one('res.partner', 'Supplier', required=True, states={'sourced':[('readonly',True)], 'split':[('readonly',True)], 'rfq_sent':[('readonly',True)], 'rfq_done':[('readonly',True)], 'rfq_updated':[('readonly',True)], 'confirmed':[('readonly',True)], 'confirmed_wait':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)],'cancel':[('readonly',True)]}, change_default=True, domain="[('id', '!=', company_id)]"),
        'partner_address_id':fields.many2one('res.partner.address', 'Address', required=True,
            states={'sourced':[('readonly',True)], 'split':[('readonly',True)], 'rfq_sent':[('readonly',True)], 'rfq_done':[('readonly',True)], 'rfq_updated':[('readonly',True)], 'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]},domain="[('partner_id', '=', partner_id)]"),
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
        'po_from_ir': fields.function(_po_from_x, method=True, type='boolean', string='Is PO from IR ?', multi='po_from_x'),
        'po_from_fo': fields.function(_po_from_x, method=True, type='boolean', string='Is PO from FO ?', multi='po_from_x'),
        'canceled_end': fields.boolean(string='Canceled End', readonly=True),
        'is_a_counterpart': fields.boolean('Counterpart?', help="This field is only for indicating that the order is a counterpart"),
        'po_updated_by_sync': fields.boolean('PO updated by sync', readonly=False),
        'origin': fields.text('Source Document',
                        help="Reference of the document that generated this purchase order request."),
        # UF-2267: Store also the parent PO as reference in the sourced PO
        'parent_order_name': fields.many2one('purchase.order', string='Parent PO name', help='If the PO is created from a re-source FO, this field contains the relevant original PO name'),
        'project_ref': fields.char(size=256, string='Project Ref.'),
        'message_esc': fields.text(string='ESC Message'),
        'fnct_project_ref': fields.function(_get_project_ref, method=True, string='Project Ref.',
                                            type='char', size=256, store=False, multi='so_info'),
        'dest_partner_ids': fields.many2many('res.partner', 'res_partner_purchase_order_rel', 'purchase_order_id', 'partner_id', 'Customers'),  # uf-2223
        'dest_partner_names': fields.function(_get_dest_partner_names, type='char', size=256,  string='Customers', method=True),  # uf-2223
        'split_po': fields.boolean('Created by split PO', readonly=True),
        'sourced_references': fields.function(
            _get_project_ref,
            method=True,
            string='Sourced references',
            type='text',
            store=False,
            multi='so_info',
        ),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'requested_date_in_past': fields.function(
            _get_requested_date_in_past,
            method=True,
            string='Requested date in past',
            type='boolean',
            store=False,
        ),
        'update_in_progress': fields.boolean(
            string='Update in progress',
            readonly=True,
        ),
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
        'is_a_counterpart': False,
        'parent_order_name': False,
        'canceled_end': False,
        'split_po': False,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'update_in_progress': False,
    }

    def _check_po_from_fo(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for po in self.browse(cr, uid, ids, context=context):
            if po.partner_id.partner_type == 'internal' and po.po_from_fo:
                return False
        return True

    _constraints = [
        (_check_po_from_fo, 'You cannot choose an internal supplier for this purchase order', []),
    ]

    def purchase_cancel(self, cr, uid, ids, context=None):
        '''
        Call the wizard to ask if you want to re-source the line
        '''
        line_obj = self.pool.get('purchase.order.line')
        wiz_obj = self.pool.get('purchase.order.cancel.wizard')
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj = self.pool.get('sale.order')
        data_obj = self.pool.get('ir.model.data')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('rfq_ok', False):
            view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'rfq_cancel_wizard_form_view')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'purchase_override', 'purchase_order_cancel_wizard_form_view')[1]

        so_to_cancel_ids = set()
        for po in self.browse(cr, uid, ids, context=context):
            for l in po.order_line:
                if line_obj.get_sol_ids_from_pol_ids(cr, uid, [l.id], context=context):
                    wiz_id = wiz_obj.create(cr, uid, {
                        'order_id': po.id,
                        'last_lines': wiz_obj._get_last_lines(cr, uid, po.id, context=context),
                    }, context=context)
                    return {'type': 'ir.actions.act_window',
                            'res_model': 'purchase.order.cancel.wizard',
                            'res_id': wiz_id,
                            'view_type': 'form',
                            'view_mode': 'form',
                            'view_id': [view_id],
                            'target': 'new',
                            'context': context}
                else:
                    exp_sol_ids = exp_sol_obj.search(cr, uid, [('po_id', '=', po.id)], context=context)
                    for exp in exp_sol_obj.browse(cr, uid, exp_sol_ids, context=context):
                        if not exp.order_id.order_line:
                            so_to_cancel_ids.add(exp.order_id.id)

            wf_service.trg_validate(uid, 'purchase.order', po.id, 'purchase_cancel', cr)

        # Ask user to choose what must be done on the FO/IR
        if so_to_cancel_ids:
            context.update({
                'from_po': True,
                'po_ids': list(ids),
            })
            return so_obj.open_cancel_wizard(cr, uid, set(so_to_cancel_ids), context=context)


        return True

    def unlink(self, cr, uid, ids, context=None):
        '''
        No unlink for PO linked to a FO
        '''
        if self.get_so_ids_from_po_ids(cr, uid, ids, context=context):
            raise osv.except_osv(_('Error'), _('You cannot remove a Purchase order that is linked to a Field Order or an Internal Request. Please cancel it instead.'))

        return super(purchase_order, self).unlink(cr, uid, ids, context=context)

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check restriction on products
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('purchase.order.line')
        res = True

        for order in self.browse(cr, uid, ids, context=context):
            res = res and line_obj._check_restriction_line(cr, uid, [x.id for x in order.order_line], context=context)

        return res


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

        for order in self.browse(cr, uid, ids, context=context):
            partner_type = self.pool.get('res.partner').browse(cr, uid, vals.get('partner_id', order.partner_id.id), context=context).partner_type
            if vals.get('order_type'):
                if vals.get('order_type') in ['donation_exp', 'donation_st', 'loan']:
                    vals.update({'invoice_method': 'manual'})
                elif vals.get('order_type') in ['direct',] and partner_type != 'esc':
                    vals.update({'invoice_method': 'order'})
                elif vals.get('order_type') in ['direct',] and partner_type == 'esc':
                    vals.update({'invoice_method': 'manual'})
                else:
                    vals.update({'invoice_method': 'picking'})
            # we need to update the location_id because it is readonly and so does not pass in the vals of create and write
            vals = self._get_location_id(cr, uid, vals,  warehouse_id=vals.get('warehouse_id', order.warehouse_id.id), context=context)

        res = super(purchase_order, self).write(cr, uid, ids, vals, context=context)

        # Delete expected sale order line
        if 'state' in vals and vals.get('state') not in ('draft', 'confirmed'):
            exp_sol_ids = self.pool.get('expected.sale.order.line').search(cr,
                    uid, [('po_id', 'in', ids)], order='NO_ORDER', context=context)
            self.pool.get('expected.sale.order.line').unlink(cr, uid, exp_sol_ids, context=context)

        return res

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
        elif order_type in ['in_kind', 'purchase_list']:
            v['invoice_method'] = 'picking'
        else:
            v['invoice_method'] = 'picking'

        company_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id

        if order_type == 'direct' and dest_partner_id and dest_partner_id != company_id:
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, dest_partner_id, ['delivery'])['delivery']
            v.update({'dest_address_id': cp_address_id})
        elif order_type == 'direct':
            v.update({'dest_address_id': False, 'dest_partner_id': False})
        else:
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, company_id, ['delivery'])['delivery']
            v.update({'dest_address_id': cp_address_id, 'dest_partner_id': company_id})

        if partner_id and partner_id != local_market:
            partner = partner_obj.browse(cr, uid, partner_id)
            if partner.partner_type in ('internal', 'esc') and order_type in ('regular', 'direct'):
                v['invoice_method'] = 'manual'
            elif partner.partner_type not in ('external', 'esc') and order_type == 'direct':
                v.update({'partner_address_id': False, 'partner_id': False, 'pricelist_id': False,})
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
            product_obj = self.pool.get('product.product')
            partner = partner_obj.browse(cr, uid, part)
            if ids:
                # Check the restrction of product in lines
                if ids:
                    product_obj = self.pool.get('product.product')
                    for order in self.browse(cr, uid, ids):
                        for line in order.order_line:
                            if line.product_id:
                                res, test = product_obj._on_change_restriction_error(cr, uid, line.product_id.id, field_name='partner_id', values=res, vals={'partner_id': part})
                                if test:
                                    res.setdefault('value', {}).update({'partner_address_id': False})
                                    return res
            if partner.partner_type in ('internal', 'esc'):
                res['value']['invoice_method'] = 'manual'
            elif ids and partner.partner_type == 'intermission':
                try:
                    intermission = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                        'analytic_account_project_intermission')[1]
                except ValueError:
                    intermission = 0
                cr.execute('''select po.id from purchase_order po
                    left join purchase_order_line pol on pol.order_id = po.id
                    left join cost_center_distribution_line cl1 on cl1.distribution_id = po.analytic_distribution_id
                    left join cost_center_distribution_line cl2 on cl2.distribution_id = pol.analytic_distribution_id
                    where po.id in %s and (cl1.analytic_id!=%s or cl2.analytic_id!=%s)''', (tuple(ids), intermission, intermission))
                if cr.rowcount > 0:
                    res.setdefault('warning', {})
                    msg = _('You set an intermission partner, at validation Cost Centers will be changed to intermission.')
                    if res.get('warning', {}).get('message'):
                        res['warning']['message'] += msg
                    else:
                        res['warning'] = {'title': _('Warning'), 'message': msg}
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

        if not context:
            context = {}

        if not dest_partner_id:
            v.update({'dest_address_id': False})
        else:
            delivery_addr = self.pool.get('res.partner').address_get(cr, uid, dest_partner_id, ['delivery'])
            v.update({'dest_address_id': delivery_addr['delivery']})
        return {'value': v}

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

    def _get_destination_ok(self, cr, uid, lines, context):
        dest_ok = False
        for line in lines:
            is_inkind = line.order_id and line.order_id.order_type == 'in_kind' or False
            dest_ok = line.account_4_distribution and line.account_4_distribution.destination_ids or False
            if not dest_ok:
                if is_inkind:
                    raise osv.except_osv(_('Error'), _('No destination found. An In-kind Donation account is probably missing for this line: %s.') % (line.name or ''))
                raise osv.except_osv(_('Error'), _('No destination found for this line: %s.') % (line.name or '',))
        return dest_ok

    def check_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Check analytic distribution validity for given PO.
        Also check that partner have a donation account (is PO is in_kind)
        """
        # Objects
        ad_obj = self.pool.get('analytic.distribution')
        ccdl_obj = self.pool.get('cost.center.distribution.line')
        pol_obj = self.pool.get('purchase.order.line')
        imd_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Analytic distribution verification
        for po in self.browse(cr, uid, ids, context=context):
            try:
                intermission_cc = imd_obj.get_object_reference(cr, uid, 'analytic_distribution',
                                                'analytic_account_project_intermission')[1]
            except ValueError:
                intermission_cc = 0

            if po.order_type == 'in_kind' and not po.partner_id.donation_payable_account:
                if not po.partner_id.donation_payable_account:
                    raise osv.except_osv(_('Error'), _('No donation account on this partner: %s') % (po.partner_id.name or '',))

            if po.partner_id and po.partner_id.partner_type == 'intermission':
                if not intermission_cc:
                    raise osv.except_osv(_('Error'), _('No Intermission Cost Center found!'))

            for pol in po.order_line:
                distrib = pol.analytic_distribution_id  or po.analytic_distribution_id  or False
                # Raise an error if no analytic distribution found
                if not distrib:
                    # UFTP-336: For the case of a new line added from Coordo, it's a push flow, no need to check the AD! VERY SPECIAL CASE
                    if po.order_type not in ('loan', 'donation_st', 'donation_exp', 'in_kind') and not po.push_fo:
                        raise osv.except_osv(_('Warning'), _('Analytic allocation is mandatory for this line: %s!') % (pol.name or '',))

                    # UF-2031: If no distrib accepted (for loan, donation), then do not process the distrib
                    return True
                elif pol.analytic_distribution_state != 'valid':
                    id_ad = ad_obj.create(cr, uid, {})
                    ad_lines = pol.analytic_distribution_id and pol.analytic_distribution_id.cost_center_lines or po.analytic_distribution_id.cost_center_lines
                    bro_dests = self._get_destination_ok(cr, uid, [pol], context=context)
                    for line in ad_lines:
                        # fetch compatible destinations then use on of them:
                        # - destination if compatible
                        # - else default destination of given account
                        if line.destination_id in bro_dests:
                            bro_dest_ok = line.destination_id
                        else:
                            bro_dest_ok = pol.account_4_distribution.default_destination_id
                        # Copy cost center line to the new distribution
                        ccdl_obj.copy(cr, uid, line.id, {
                            'distribution_id': id_ad,
                            'destination_id': bro_dest_ok.id,
                            'partner_type': pol.order_id.partner_id.partner_type,
                        })
                    # Write result
                    pol_obj.write(cr, uid, [pol.id], {'analytic_distribution_id': id_ad})
                else:
                    ad_lines = pol.analytic_distribution_id and pol.analytic_distribution_id.cost_center_lines or po.analytic_distribution_id.cost_center_lines
                    line_ids_to_write = [line.id for line in ad_lines if not
                            line.partner_type]
                    ccdl_obj.write(cr, uid, line_ids_to_write, {
                        'partner_type': pol.order_id.partner_id.partner_type,
                    })

        return True

    def wkf_picking_done(self, cr, uid, ids, context=None):
        '''
        Change the shipped boolean and the state of the PO
        '''
        direct_order_id_list = []
        other_id_list = []
        for order in self.browse(cr, uid, ids, context=context):
            if order.order_type == 'direct':
                direct_order_id_list.append(order.id)
            else:
                other_id_list.append(order.id)

        if direct_order_id_list:
            self.write(cr, uid, direct_order_id_list, {'state': 'approved'}, context=context)
        if other_id_list:
            self.write(cr, uid, other_id_list, {'shipped':1,'state':'approved'}, context=context)
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
        # Objects
        sale_line_obj = self.pool.get('sale.order.line')
        stock_move_obj = self.pool.get('stock.move')
        wiz_obj = self.pool.get('purchase.order.confirm.wizard')

        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        move_obj = self.pool.get('stock.move')

        for order in self.browse(cr, uid, ids, context=context):
            if not order.delivery_confirmed_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))

            if order.order_type == 'direct':
                todo = []
                todo2 = []

                for line in order.order_line:
                    if line.procurement_id: todo.append(line.procurement_id.id)

                if todo:
                    todo2 = sale_line_obj.search(cr, uid, [('procurement_id', 'in', todo)], context=context)

                if todo2:
                    sm_ids = move_obj.search(cr, uid, [('sale_line_id', 'in', todo2)], context=context)
                    error_moves = []
                    for move in move_obj.browse(cr, uid, sm_ids, context=context):
                        backmove_ids = stock_move_obj.search(cr, uid, [('backmove_id', '=', move.id)])
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

                        wiz_id = wiz_obj.create(cr, uid, {'order_id': order.id,
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

    def get_so_ids_from_po_ids(self, cr, uid, ids, context=None, sol_ids=[]):
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
        if not sol_ids:
            sol_ids = self.get_sol_ids_from_po_ids(cr, uid, ids, context=context)
        if sol_ids:
            # list of dictionaries for each sale order line
            datas = sol_obj.read(cr, uid, sol_ids, ['order_id'], context=context)
            # we retrieve the list of sale order ids
            for data in datas:
                if data['order_id'] and data['order_id'][0] not in so_ids:
                    so_ids.append(data['order_id'][0])

        for po in self.browse(cr, uid, ids, context=context):
            for line in po.order_line:
                if line.procurement_id and line.procurement_id.sale_id and line.procurement_id.sale_id.id not in so_ids:
                    so_ids.append(line.procurement_id.sale_id.id)

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

    # @@@override purchase->purchase.py>purchase_order>wkf_confirm_order
    def wkf_confirm_order(self, cr, uid, ids, context=None):
        '''
        Update the confirmation date of the PO at confirmation.
        Check analytic distribution.
        '''
        # Objects
        po_line_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        todo = []
        reset_soq = []

        for po in self.browse(cr, uid, ids, context=context):
            line_error = []
            if po.order_type == 'regular':
                cr.execute('SELECT line_number FROM purchase_order_line WHERE (price_unit*product_qty < 0.01 OR price_unit = 0.00) AND order_id = %s', (po.id,))
                line_errors = cr.dictfetchall()
                for l_id in line_errors:
                    if l_id not in line_error:
                        line_error.append(l_id['line_number'])

            if len(line_error) > 0:
                errors = ' / '.join(str(x) for x in line_error)
                raise osv.except_osv(_('Error !'), _('You cannot have a purchase order line with a 0.00 Unit Price or 0.00 Subtotal. Lines in exception : %s') % errors)

            # Check if the pricelist of the order is good according to currency of the partner
            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid,
                    [('in_search', '=', po.partner_id.partner_type)],
                    order='NO_ORDER', context=context)
            if po.pricelist_id.id not in pricelist_ids:
                raise osv.except_osv(_('Error'), _('The currency used on the order is not compatible with the supplier. Please change the currency to choose a compatible currency.'))

            if not po.split_po and not po.order_line:
                raise osv.except_osv(_('Error !'), _('You can not validate a purchase order without Purchase Order Lines.'))

            if po.order_type == 'purchase_list' and po.amount_total == 0:  # UFTP-69
                raise osv.except_osv(_('Error'), _('You can not validate a purchase list with a total amount of 0.'))

            for line in po.order_line:
                if line.state=='draft':
                    todo.append(line.id)
                if line.soq_updated:
                    reset_soq.append(line.id)

            message = _("Purchase order '%s' is validated.") % (po.name,)
            self.log(cr, uid, po.id, message)
            # hook for corresponding Fo update
            self._hook_confirm_order_update_corresponding_so(cr, uid, ids, context=context, po=po)

        po_line_obj.action_confirm(cr, uid, todo, context)
        po_line_obj.write(cr, uid, reset_soq, {'soq_updated': False,}, context=context)

        self.write(cr, uid, ids, {'state' : 'confirmed',
                                  'validator' : uid,
                                  'date_confirm': strftime('%Y-%m-%d')}, context=context)

        self.check_analytic_distribution(cr, uid, ids, context=context)

        return True

    def common_code_from_wkf_approve_order(self, cr, uid, ids, context=None):
        '''
        delivery confirmed date at po level is mandatory
        update corresponding date at line level if needed.
        Check analytic distribution
        Check that no line have a 0 price unit.
        '''
        # Objects
        po_line_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Check analytic distribution
        self.check_analytic_distribution(cr, uid, ids, context=context)
        for po in self.browse(cr, uid, ids, context=context):
            # prepare some values
            is_regular = po.order_type == 'regular' # True if order_type is regular, else False
            line_error = []
            # msf_order_date checks
            if po.state == 'approved' and not po.delivery_confirmed_date:
                raise osv.except_osv(_('Error'), _('Delivery Confirmed Date is a mandatory field.'))
            # for all lines, if the confirmed date is not filled, we copy the header value
            if is_regular:
                cr.execute('SELECT line_number FROM purchase_order_line WHERE (price_unit*product_qty < 0.01 OR price_unit = 0.00) AND order_id = %s', (po.id,))
                line_errors = cr.dictfetchall()
                for l_id in line_errors:
                    if l_id not in line_error:
                        line_error.append(l_id['line_number'])

            if len(line_error) > 0:
                errors = ' / '.join(str(x) for x in line_error)
                raise osv.except_osv(_('Error !'), _('You cannot have a purchase order line with a 0.00 Unit Price or 0.00 Subtotal. Lines in exception : %s') % errors)

            lines_to_update = po_line_obj.search(
                cr, uid,
                [('order_id', '=', po.id), ('confirmed_delivery_date', '=', False)],
                context=context)

            po_line_obj.write(cr, uid, lines_to_update, {'confirmed_delivery_date': po.delivery_confirmed_date}, context=context)
        # MOVE code for COMMITMENT into wkf_approve_order
        return True

    def create_extra_lines_on_fo(self, cr, uid, ids, context=None):
        '''
        Creates FO/IR lines according to PO extra lines
        '''
        # Objects
        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        ad_obj = self.pool.get('analytic.distribution')
        proc_obj = self.pool.get('procurement.order')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        lines = []
        sol_ids = set()
        for order in self.browse(cr, uid, ids, context=context):
            for l in order.order_line:
                link_so_id = l.link_so_id and l.link_so_id.state in ('sourced', 'progress', 'manual')
                if link_so_id and (not l.procurement_id or not l.procurement_id.sale_id):
                    lines.append(l)

        for l in lines:
            # Copy the AD
            new_distrib = False
            if l.analytic_distribution_id:
                new_distrib = ad_obj.copy(cr, uid, l.analytic_distribution_id.id, {}, context=context)
            elif not l.analytic_distribution_id and l.order_id and l.order_id.analytic_distribution_id:
                new_distrib = ad_obj.copy(cr, uid, l.order_id.analytic_distribution_id.id, {}, context=context)
            # Creates the FO lines
            tmp_sale_context = context.get('sale_id')
            # create new line in FOXXXX-Y
            context['sale_id'] = l.link_so_id.id
            vals = {'order_id': l.link_so_id.id,
                    'product_id': l.product_id.id,
                    'product_uom': l.product_uom.id,
                    'product_uom_qty': l.product_qty,
                    'price_unit': l.price_unit,
                    'procurement_id': l.procurement_id and l.procurement_id.id or False,
                    'type': 'make_to_order',
                    'supplier': l.order_id.partner_id.id,
                    'analytic_distribution_id': new_distrib,
                    'created_by_po': not l.order_id.rfq_ok and l.order_id.id or False,
                    'created_by_po_line': not l.order_id.rfq_ok and l.id or False,
                    'created_by_rfq': l.order_id.rfq_ok and l.order_id.id or False,
                    'created_by_rfq_line': l.order_id.rfq_ok and l.id or False,
                    'po_cft': l.order_id.rfq_ok and 'rfq' or 'po',
                    'sync_sourced_origin': l.instance_sync_order_ref and l.instance_sync_order_ref.name or False,
                    #'is_line_split': l.is_line_split,
                    'name': '[%s] %s' % (l.product_id.default_code, l.product_id.name)}

            new_line_id = sol_obj.create(cr, uid, vals, context=context)

            # Put the sale_id in the procurement order
            if l.procurement_id:
                proc_obj.write(cr, uid, [l.procurement_id.id], {
                    'sale_id': l.link_so_id.id,
                    'purchase_id': l.order_id.id,
                }, context=context)
            # Create new line in FOXXXX (original FO)
            if l.link_so_id.original_so_id_sale_order:
                context['sale_id'] = l.link_so_id.original_so_id_sale_order.id
                vals.update({'order_id': l.link_so_id.original_so_id_sale_order.id,
                             'state': 'done'})
                sol_id = sol_obj.create(cr, uid, vals, context=context)
                self.infolog(cr, uid, "The FO/IR line id:%s has been added from the PO line id:%s" % (
                    sol_id, l.id,
                ))
            context['sale_id'] = tmp_sale_context

            # If the order is an Internal request with External location, create a new
            # stock move on the picking ticket (if not closed)
            # Get move data and create the move
            if l.link_so_id.procurement_request and l.link_so_id.location_requestor_id.usage == 'customer' and l.product_id.type == 'product':
                # Get OUT linked to IR
                pick_to_confirm = None
                out_ids = pick_obj.search(cr, uid, [
                    ('sale_id', '=', l.link_so_id.id),
                    ('type', '=', 'out'),
                    ('state', 'in', ['draft', 'confirmed', 'assigned']),
                ], context=context)
                if not out_ids:
                    picking_data = so_obj._get_picking_data(cr, uid, l.link_so_id)
                    out_ids = [pick_obj.create(cr, uid, picking_data, context=context)]
                    pick_to_confirm = out_ids

                ir_line = sol_obj.browse(cr, uid, new_line_id, context=context)
                move_data = so_obj._get_move_data(cr, uid, l.link_so_id, ir_line, out_ids[0], context=context)
                move_obj.create(cr, uid, move_data, context=context)

                if pick_to_confirm:
                    pick_obj.action_confirm(cr, uid, pick_to_confirm, context=context)

            sol_ids.add(l.link_so_id.id)
            self.infolog(cr, uid, "The FO/IR line id:%s has been added from the PO line id:%s" % (
                new_line_id, l.id,
            ))

        if sol_ids:
            so_obj.action_ship_proc_create(cr, uid, list(sol_ids), context=context)

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
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj =  self.pool.get('sale.order')

        # Create extra lines on the linked FO/IR
        self.create_extra_lines_on_fo(cr, uid, ids, context=context)

        # code from wkf_approve_order
        self.common_code_from_wkf_approve_order(cr, uid, ids, context=context)
        # set the state of purchase order to confirmed_wait
        self.write(cr, uid, ids, {'state': 'confirmed_wait'}, context=context)
        sol_ids = self.get_sol_ids_from_po_ids(cr, uid, ids, context=context)

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context, sol_ids=sol_ids)
        # UF-2509: so_ids is a list, not an int
        exp_sol_ids = exp_sol_obj.search(cr, uid, [('order_id', 'in', so_ids)], context=context)
        # from so, list corresponding po
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        for exp_sol in exp_sol_obj.browse(cr, uid, exp_sol_ids, context=context):
            # UFTP-335: Added a check in if to avoid False value being taken
            if exp_sol.po_id and exp_sol.po_id.id not in all_po_ids:
                all_po_ids.append(exp_sol.po_id.id)
        list_po_name = ', '.join([linked_po.name for linked_po in self.browse(cr, uid, all_po_ids, context) if linked_po.id != ids[0]])
        self.log(cr, uid, ids[0], _("The order %s is in confirmed (waiting) state and will be confirmed once the related orders [%s] would have been confirmed"
                                 ) % (self.read(cr, uid, ids, ['name'])[0]['name'], list_po_name))
        # sale order lines with modified state
        if sol_ids:
            sol_obj.write(cr, uid, sol_ids, {'state': 'confirmed'}, context=context)

        # !!BEWARE!! we must update the So lines before any writing to So objects
        for po in self.browse(cr, uid, ids, context=context):
            # hook for corresponding Fo update
            context['wait_order'] = True
            self._hook_confirm_order_update_corresponding_so(cr, uid, ids, context=context, po=po, so_ids=so_ids)
            del context['wait_order']
            self.infolog(cr, uid, "The PO id:%s has been confirmed" % po.id)

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
        so_ids= kwargs.get('so_ids')
        pol_obj = self.pool.get('purchase.order.line')
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')
        socl_obj = self.pool.get('sale.order.line.cancel')
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        pick_obj = self.pool.get('stock.picking')
        uom_obj = self.pool.get('product.uom')
        ad_obj = self.pool.get('analytic.distribution')
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        wf_service = netsvc.LocalService("workflow")

        # update corresponding fo if exist
        if so_ids is None:
            so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        ctx = context.copy()
        ctx['no_store_function'] = ['sale.order.line']
        store_to_call = []
        picks_to_check = {}
        if so_ids:
            # date values
            ship_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
            prep_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)

            for line in po.order_line:
                # get the corresponding so line
                sol_ids = pol_obj.get_sol_ids_from_pol_ids(cr, uid, [line.id], context=context)
                if sol_ids:
                    store_to_call += sol_ids


                    sol = sol_obj.browse(cr, uid, sol_ids[0], context=context)
                    so = sol.order_id
                    # do not update Internal Requests with internal requestor location
                    if so and so.procurement_request and so.location_requestor_id.usage != 'customer':
                        continue

                    line_confirmed = False
                    # compute confirmed date for line
                    if line.confirmed_delivery_date:
                        line_confirmed = self.compute_confirmed_delivery_date(cr, uid, ids, line.confirmed_delivery_date,
                                                                              prep_lt, ship_lt, so.est_transport_lead_time,
                                                                              db_date_format, context=context)

                    # we update the corresponding sale order line
                    # {sol: pol}
                    # compute the price_unit value - we need to specify the date
                    date_context = {'date': po.date_order}

                    # convert from currency of pol to currency of sol
                    price_unit_converted = self.pool.get('res.currency').compute(cr, uid, line.currency_id.id,
                                                                                 sol.currency_id.id, line.price_unit or 0.0,
                                                                                 round=False, context=date_context)

                    if so.order_type == 'regular' and price_unit_converted < 0.00001:
                        price_unit_converted = 0.00001

                    line_qty = line.product_qty
                    if line.procurement_id:
                        other_po_lines = pol_obj.search(cr, uid, [
                            ('procurement_id', '=', line.procurement_id.id),
                            ('id', '!=', line.id),
                            '|', ('order_id.id', '=', line.order_id.id), ('order_id.state', 'in', ['sourced', 'approved']),
                        ], context=context)
                        for opl in pol_obj.browse(cr, uid, other_po_lines, context=context):
                            # Check if the other PO line will not be canceled
                            socl_ids = socl_obj.search(cr, uid, [
                                ('sync_order_line_db_id', '=', opl.sync_order_line_db_id),
                            ], limit=1, order='NO_ORDER', context=context)
                            if socl_ids:
                                continue

                            if opl.product_uom.id != line.product_uom.id:
                                line_qty += uom_obj._compute_qty(cr, uid, opl.product_uom.id, opl.product_qty, line.product_uom.id)
                            else:
                                line_qty += opl.product_qty

                    fields_dic = {'product_id': line.product_id and line.product_id.id or False,
                                  'name': line.name,
                                  'default_name': line.default_name,
                                  'default_code': line.default_code,
                                  'product_uom_qty': line_qty,
                                  'product_uom': line.product_uom and line.product_uom.id or False,
                                  'product_uos_qty': line_qty,
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
                                  #'is_line_split': line.is_line_split,
                                  }
                    """
                    UFTP-336: Update the analytic distribution at FO line when
                              PO is confirmed if lines are created at tender
                              or RfQ because there is no AD on FO line.
                    """
                    if sol.created_by_tender or sol.created_by_rfq:
                        new_distrib = False
                        if line.analytic_distribution_id:
                            new_distrib = ad_obj.copy(cr, uid, line.analytic_distribution_id.id, {}, context=context)
                        elif not line.analytic_distribution_id and line.order_id and line.order_id.analytic_distribution_id:
                            new_distrib = ad_obj.copy(cr, uid, line.order_id.analytic_distribution_id.id, {}, context=context)

                        fields_dic['analytic_distribution_id'] = new_distrib

                    # write the line
                    sol_obj.write(cr, uid, sol_ids, fields_dic, context=ctx)

                    if so.procurement_request and so.location_requestor_id.usage == 'customer' \
                                              and line.procurement_id.move_id \
                                              and not line.procurement_id.move_id.processed_stock_move:
                        # In case of replacement of a non-stockable product by a stockable product
                        if line.product_id.id != line.procurement_id.product_id.id and  line.procurement_id.product_id.type in ('service', 'service_recep', 'consu') and line.product_id.type == 'product':
                            # Get OUT linked to IR
                            pick_to_confirm = None
                            out_ids = []
                            if line.procurement_id.sale_id:
                                out_ids = pick_obj.search(cr, uid, [
                                    ('sale_id', '=', line.procurement_id.sale_id.id),
                                    ('type', '=', 'out'),
                                    ('state', 'in', ['draft', 'confirmed', 'assigned']),
                                ], context=context)
                            if not out_ids:
                                picking_data = so_obj._get_picking_data(cr, uid, so)
                                out_ids = [pick_obj.create(cr, uid, picking_data, context=context)]
                                pick_to_confirm = out_ids

                            move_data = so_obj._get_move_data(cr, uid, so, sol, out_ids[0], context=context)
                            new_move_id = move_obj.create(cr, uid, move_data, context=context)
                            out_move_id = line.procurement_id.move_id.id
                            proc_obj.write(cr, uid, [line.procurement_id.id], {'move_id': new_move_id}, context=context)
                            move_obj.write(cr, uid, [out_move_id], {'state': 'draft'}, context=context)
                            move_obj.unlink(cr, uid, [out_move_id], context=context)

                            if pick_to_confirm:
                                wf_service = netsvc.LocalService("workflow")
                                for pick_to_confirm_id in pick_to_confirm:
                                    wf_service.trg_validate(uid, 'stock.picking', pick_to_confirm_id, 'button_confirm', cr)
                                #pick_obj.action_confirm(cr, uid, pick_to_confirm, context=context)
                            out_move_id = move_obj.browse(cr, uid, new_move_id, context=context)
                        else:
                            out_move_id = line.procurement_id.move_id
                        # If there is a non-stockable or service product, remove the OUT
                        # stock move and update the stock move on the procurement
                        if context.get('wait_order') and line.product_id.type in ('service', 'service_recep', 'consu') and out_move_id.picking_id:
                            out_pick_id = out_move_id.picking_id.id
                            proc_obj.write(cr, uid, [line.procurement_id.id], {
                                'move_id': line.move_dest_id.id,
                            }, context=context)
                            move_obj.write(cr, uid, [out_move_id.id], {'state': 'draft'})
                            if out_pick_id:
                                picks_to_check.setdefault(out_pick_id, [])
                                picks_to_check[out_pick_id].append(out_move_id.id)
                            else:
                                move_obj.unlink(cr, uid, [out_move_id.id], context=context)

                            continue

                        minus_qty = 0.00
                        bo_moves = []   # Moves already processed
                        sp_moves = []   # Moves in same picking related to same FO/IR line
                        if out_move_id.picking_id:
                            sp_moves = move_obj.search(cr, uid, [
                                ('picking_id', '=', out_move_id.picking_id.id),
                                ('sale_line_id', '=', out_move_id.sale_line_id.id),
                                ('id', '!=', out_move_id.id),
                                ('state', 'in', ['confirmed', 'assigned']),
                            ], context=context)

                            if out_move_id.picking_id.backorder_id:
                                bo_moves = move_obj.search(cr, uid, [
                                    ('picking_id', '=', out_move_id.picking_id.backorder_id.id),
                                    ('sale_line_id', '=', out_move_id.sale_line_id.id),
                                    ('state', '=', 'done'),
                                ], context=context)

                            while bo_moves:
                                boms = move_obj.browse(cr, uid, bo_moves, context=context)
                                bo_moves = []
                                for bom in boms:
                                    if bom.product_uom.id != out_move_id.product_uom.id:
                                        minus_qty += uom_obj._compute_qty(cr, uid, bom.product_uom.id, bom.product_qty, out_move_id.product_uom.id)
                                    else:
                                        minus_qty += bom.product_qty
                                        if bom.picking_id and bom.picking_id.backorder_id:
                                            if bom.picking_id.backorder_id:
                                                bo_moves.extend(move_obj.search(cr, uid, [
                                                    ('picking_id', '=', bom.picking_id.backorder_id.id),
                                                    ('sale_line_id', '=', bom.sale_line_id.id),
                                                    ('state', '=', 'done'),
                                                ], context=context))

                        for sp_move in move_obj.browse(cr, uid, sp_moves, context=context):
                            if sp_move.product_uom.id != out_move_id.product_uom.id:
                                minus_qty += uom_obj._compute_qty(cr, uid, bom.product_uom.id, bom.product_qty, out_move_id.product_uom.id)
                            else:
                                minus_qty += sp_move.product_qty

                        if out_move_id.product_uom.id != line.product_uom.id:
                            minus_qty = uom_obj._compute_qty(cr, uid, out_move_id.product_uom.id, minus_qty, line.product_uom.id)

                        if out_move_id.state == 'assigned':
                            move_obj.cancel_assign(cr, uid, [out_move_id.id])
                        elif out_move_id.state in ('cancel', 'done'):
                            continue
                        else:
                            move_dic = {
                                'name': line.name,
                                'product_uom': line.product_uom and line.product_uom.id or False,
                                'product_uos': line.product_uom and line.product_uom.id or False,
                                'product_qty': line_qty - minus_qty,
                                'product_uos_qty': line_qty - minus_qty,
                            }
                            if line.product_id:
                                move_dic['product_id'] = line.product_id.id
                            if line.product_uom:
                                move_dic.update({
                                    'product_uom': line.product_uom.id,
                                    'product_uos': line.product_uom.id,
                                })
                            move_obj.write(cr, uid, [out_move_id.id], move_dic, context=context)

            if store_to_call:
                sol_obj._call_store_function(cr, uid, store_to_call, keys=None, bypass=False, context=context)
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
                    wf_service.trg_write(uid, 'sale.order', so.id, cr)

        for out_pick_id, out_move_ids in picks_to_check.iteritems():
            full_out = pick_obj.read(cr, uid, out_pick_id, ['move_lines'])['move_lines']
            for om_id in out_move_ids:
                if om_id in full_out:
                    full_out.remove(om_id)

            if out_pick_id and not full_out:
                pick_obj.write(cr, uid, [out_pick_id], {'state': 'draft'}, context=context)
                move_obj.unlink(cr, uid, out_move_ids)
                pick_obj.unlink(cr, uid, out_pick_id)
            else:
                move_obj.unlink(cr, uid, out_move_ids)

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

    def sourcing_document_state(self, cr, uid, ids, context=None):
        """
        Returns all documents that are in the sourcing for a given PO 
        """
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)

        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)

        all_sol_not_confirmed_ids = []
        # if we have sol_ids, we are treating a po which is make_to_order from sale order
        if all_so_ids:
            all_sol_not_confirmed_ids = sol_obj.search(cr, uid, [('order_id', 'in', all_so_ids),
                                                                 ('type', '=', 'make_to_order'),
                                                                 ('product_id', '!=', False),
                                                                 ('procurement_id.state', '!=', 'cancel'),
                                                                 ('state', 'not in', ['confirmed', 'done'])], context=context)

        return so_ids, all_po_ids, all_so_ids, all_sol_not_confirmed_ids


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
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        so_ids = so_obj.search(cr, uid, [('id', 'in', so_ids), ('procurement_request', '=', False)], context=context)
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


            # if any lines exist, we return False
            if exp_sol_obj.search(cr, uid,
                    [('order_id', 'in', all_so_ids)], limit=1,
                    order='NO_ORDER', context=context):
                return False

            if sol_obj.search(cr, uid,
                    [('order_id', 'in', all_so_ids),
                     ('type', '=', 'make_to_order'),
                     ('product_id', '!=', False),
                     ('procurement_id.state', '!=', 'cancel'),
                     ('order_id.procurement_request', '=', False),
                     ('state', 'not in', ['confirmed', 'done'])],
                    limit=1, order='NO_ORDER', context=context):
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
        so_obj = self.pool.get('sale.order')
        wf_service = netsvc.LocalService("workflow")

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po first level
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)
        # from all so, list all corresponding po second level
        all_po_for_all_so_ids = so_obj.get_po_ids_from_so_ids(cr, uid, all_so_ids, context=context)

        not_confirmed_po = self.search(cr, uid, [
            ('id', 'not in', all_po_for_all_so_ids),
            ('state', '=', 'confirmed_wait'),
        ], context=context)

        # we trigger all the corresponding sale order -> test_lines is called on these so
        for so_id in all_so_ids:
            wf_service.trg_write(uid, 'sale.order', so_id, cr)

        # we trigger pos of all sale orders -> all_po_confirm is called on these po
        for po_id in all_po_for_all_so_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        for po_id in not_confirmed_po:
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
        uf_config = self.pool.get('unifield.setup.configuration')
        wf_service = netsvc.LocalService("workflow")
        imd_obj = self.pool.get('ir.model.data')

        if isinstance(ids, (int, long)):
            ids = [ids]

        # duplicated code with wkf_confirm_wait_order because of backward compatibility issue with yml tests for dates,
        # which doesnt execute wkf_confirm_wait_order (null value in column "date_expected" violates not-null constraint for stock.move otherwise)
        # msf_order_date checks
        self.common_code_from_wkf_approve_order(cr, uid, ids, context=context)

        setup = uf_config.get_config(cr, uid)

        for order in self.browse(cr, uid, ids):
            if order.order_type == 'purchase_list' and order.amount_total == 0:  # UFTP-69
                # total amount could be set to 0 after it was Validated
                # or no lines
                # (after wkf_confirm_order total amount check)
                raise osv.except_osv(_('Error'), _('You can not confirm a purchase list with a total amount of 0.'))

            # Create commitments for each PO only if po is "from picking"
            # UTP-114: No Commitment Voucher on PO that are 'purchase_list'!
            if (order.invoice_method in ['picking', 'order'] and not order.from_yml_test and order.order_type not in ['in_kind', 'purchase_list'] and order.partner_id.partner_type != 'intermission') or (order.invoice_method == 'manual' and order.order_type == 'direct' and order.partner_id.partner_type == 'esc'):
                # UTP-827: no commitment if they are imported for ESC partners
                if not (order.partner_id.partner_type == 'esc' and setup.import_commitments):
                    # US-917: Check if any CV exists for the given PO
                    commit_obj = self.pool.get('account.commitment')
                    existingCV = commit_obj.search(cr, uid, [('purchase_id', 'in', [order.id])], context=context)
                    if not existingCV:
                        self.action_create_commitment(cr, uid, [order.id], order.partner_id and order.partner_id.partner_type, context=context)
            todo = []
            todo2 = []
            todo3 = []
            todo4 = {}
            if order.partner_id.partner_type in ('internal', 'esc') and order.order_type == 'regular' or \
                         order.order_type in ['donation_exp', 'donation_st', 'loan']:
                self.write(cr, uid, [order.id], {'invoice_method': 'manual'})
                line_obj.write(cr, uid, [x.id for x in order.order_line], {'invoiced': 1})

            message = _("Purchase order '%s' is confirmed.") % (order.name,)
            self.log(cr, uid, order.id, message)

            if order.order_type == 'direct':
                if order.partner_id.partner_type != 'esc':
                    self.write(cr, uid, [order.id], {'invoice_method': 'order'}, context=context)
                for line in order.order_line:
                    if line.procurement_id:
                        todo.append(line.procurement_id.id)
                        todo4.update({line.procurement_id.id: line.id})

            if todo:
                todo2 = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', 'in', todo)], context=context)

            if todo2:
                sm_ids = move_obj.search(cr, uid, [('sale_line_id', 'in', todo2)], context=context)
                move_obj.action_confirm(cr, uid, sm_ids, context=context)
                stock_location_id = imd_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
                cross_id = imd_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
                non_stock_id = imd_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
                for move in move_obj.browse(cr, uid, sm_ids, context=context):
                    # Reset the location_id to Stock
                    location_id = stock_location_id
                    # Search if this move has been processed
                    backmove_ids = move_obj.search(cr, uid,
                            [('backmove_id', '=', move.id)],
                            limit=1, order='NO_ORDER')
                    if move.state != 'done' and not backmove_ids and not move.backmove_id:
                        if move.product_id.type in ('service', 'service_recep'):
                            location_id = cross_id
                        elif move.product_id.type == 'consu':
                            location_id = non_stock_id
                        move_obj.write(cr, uid, [move.id], {'dpo_id': order.id,
                                                            'state': 'done',
                                                            'dpo_line_id': todo4.get(move.sale_line_id.procurement_id.id, False),
                                                            'location_id': location_id,
                                                            'location_dest_id': location_id,
                                                            'date': strftime('%Y-%m-%d %H:%M:%S')}, context=context)
                        wf_service.trg_trigger(uid, 'stock.move', move.id, cr)
                        if move.picking_id:
                            all_move_closed = True
                            # Check if the picking should be updated
                            if move.picking_id.subtype == 'picking':
                                for m in move.picking_id.move_lines:
                                    if m.id not in sm_ids and m.state != 'done':
                                        all_move_closed = False
                                        break
                            # If all stock moves of the picking is done, trigger the workflow
                            if all_move_closed:
                                todo3.append(move.picking_id.id)

            if todo3:
                for pick_id in todo3:
                    wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
                    wf_service.trg_write(uid, 'stock.picking', pick_id, cr)

        # @@@override@purchase.purchase.order.wkf_approve_order
        self.write(cr, uid, ids, {'state': 'approved', 'date_approve': strftime('%Y-%m-%d')})
        return True

    def need_counterpart(self, cr, uid, ids, context=None):
        for po in self.browse(cr, uid, ids, context=context):
            if po.order_type == 'loan' and not po.loan_id and not po.is_a_counterpart and po.partner_id.partner_type not in ('internal', 'intermission', 'section'):
                return True
        return False

    def go_to_loan_done(self, cr, uid, ids, context=None):
        for po in self.browse(cr, uid, ids, context=context):
            if po.order_type not in ('loan', 'direct') or po.loan_id or (po.order_type == 'loan' and po.partner_id.partner_type in ('internal', 'intermission', 'section')):
                return True
        return False

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
            if order.is_a_counterpart or (order.order_type == 'loan' and order.partner_id.partner_type in ('internal', 'intermission', 'section')):
                # UTP-392: This PO is created by the synchro from a Loan FO of internal/intermission partner, so do not generate the counterpart FO
                return

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
                      'is_a_counterpart': True,
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
            message = _("Loan counterpart '%s' has been created and validated. Please confirm it.") % (sale.name,)

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

    # @@@override@purchase.purchase.order.action_picking_create
    def action_picking_create(self,cr, uid, ids, context=None, *args):
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        line_obj = self.pool.get('purchase.order.line')
        sol_obj = self.pool.get('sale.order.line')
        data_obj = self.pool.get('ir.model.data')

        input_loc = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
        picking_id = False
        for order in self.browse(cr, uid, ids):
            moves_to_update = []
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
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_supply')[1]
            elif order.order_type in ('regular', 'purchase_list', 'direct'):
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1]
            if order.order_type == 'loan':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
            if order.order_type == 'donation_st':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
            if order.order_type == 'donation_exp':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
            if order.order_type == 'in_kind':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_in_kind_donation')[1]

            if reason_type_id:
                picking_values.update({'reason_type_id': reason_type_id})

            # US-917: Check if any IN exists for the given PO
            pick_obj = self.pool.get('stock.picking')
            existingIN = pick_obj.search(cr, uid, [('purchase_id', 'in', [order.id])], context=context)
            if existingIN:
                return

            picking_id = self.pool.get('stock.picking').create(cr, uid, picking_values, context=context)
            todo_moves = []
            for order_line in order.order_line:
                # Reload the data of the line because if the line comes from an ISR and it's a duplicate line,
                # the move_dest_id field has been changed by the _hook_action_picking_create_modify_out_source_loc_check method
                order_line = line_obj.browse(cr, uid, order_line.id, context=context)
                if not order_line.product_id:
                    continue
                dest = order.location_id.id
                # service with reception are directed to Service Location
                if order_line.product_id.type == 'service_recep' and not order.cross_docking_ok:
                    dest = self.pool.get('stock.location').get_service_location(cr, uid)
                else:
                    sol_ids = line_obj.get_sol_ids_from_pol_ids(cr, uid, [order_line.id], context=context)
                    for sol in sol_obj.browse(cr, uid, sol_ids, context=context):
                        if sol.order_id and sol.order_id.procurement_request:
                            if order_line.product_id.type == 'service_recep':
                                dest = self.pool.get('stock.location').get_service_location(cr, uid)
                                break
                            elif order_line.product_id.type == 'consu':
                                dest = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
                                break
                            elif sol.order_id.location_requestor_id.usage != 'customer':
                                dest = input_loc
                                break

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
                    'price_unit': order_line.price_unit,
                    'date': order_line.confirmed_delivery_date,
                    'date_expected': order_line.confirmed_delivery_date,
                    'line_number': order_line.line_number,
                }

                if reason_type_id:
                    move_values.update({'reason_type_id': reason_type_id})

                ctx = context.copy()
                ctx['bypass_store_function'] = [('stock.picking', ['dpo_incoming', 'dpo_out', 'overall_qty', 'line_state'])]
                move = move_obj.create(cr, uid, move_values, context=ctx)
                if self._hook_action_picking_create_modify_out_source_loc_check(cr, uid, ids, context=context, order_line=order_line, move_id=move):
                    moves_to_update.append(order_line.move_dest_id.id)
                todo_moves.append(move)
            # compute function fields
            if todo_moves:
                compute_store = move_obj._store_get_values(cr, uid, todo_moves, None, context)
                compute_store.sort()
                done = []
                for _, store_object, store_ids, store_fields2 in compute_store:
                    if store_fields2 in ('dpo_incoming', 'dpo_out', 'overall_qty', 'line_state') and not (store_object, store_ids, store_fields2) in done:
                        self.pool.get(store_object)._store_set_values(cr, uid, store_ids, store_fields2, context)
                        done.append((store_object, store_ids, store_fields2))
            move_obj.write(cr, uid, moves_to_update, {'location_id':order.location_id.id})
            move_obj.action_confirm(cr, uid, todo_moves)
            move_obj.force_assign(cr, uid, todo_moves)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
        # @@@end

    def _get_location_id(self, cr, uid, vals, warehouse_id=False, context=None):
        """
        Get the location_id according to the cross_docking_ok option
        Return vals
        """
        if 'cross_docking_ok' not in vals:
            return vals

        if not warehouse_id:
            warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [], context=context)[0]

        if isinstance(warehouse_id, str):
            try:
                warehouse_id = int(warehouse_id)
            except ValueError:
                raise osv.except_osv(
                        _('Error'),
                        _('The field \'warehouse_id\' is a float field but value is a string - Please contact your administrator'),
                )

        if not vals.get('cross_docking_ok', False):
            vals.update({'location_id': self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_input_id.id})
        elif vals.get('cross_docking_ok', False):
            vals.update({'location_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})

        return vals


    def create(self, cr, uid, vals, context=None):
        """
        Filled in 'from_yml_test' to True if we come from tests
        # UTP-114 demands purchase_list PO to be 'from picking'.
        """
        if not context:
            context = {}

        if vals.get('order_type'):
            if vals.get('order_type') in ['donation_exp', 'donation_st', 'loan']:
                vals.update({'invoice_method': 'manual'})
            elif vals.get('order_type') in ['direct']:
                vals.update({'invoice_method': 'order'})
                if vals.get('partner_id'):
                    if self.pool.get('res.partner').browse(cr, uid, vals.get('partner_id'), context=context).partner_type == 'esc':
                        vals.update({'invoice_method': 'manual'})
            else:
                vals.update({'invoice_method': 'picking'})

        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)
        # we need to update the location_id because it is readonly and so does not pass in the vals of create and write
        vals = self._get_location_id(cr, uid, vals, warehouse_id=vals.get('warehouse_id', False), context=context)

        res = super(purchase_order, self).create(cr, uid, vals, context=context)

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

        wf_service = netsvc.LocalService("workflow")

        line_ids = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                line_ids.append(line.id)
                if line.procurement_id and line.procurement_id.move_id:
                    self.pool.get('stock.move').write(cr, uid, line.procurement_id.move_id.id, {'state': 'cancel'}, context=context)
                    if line.procurement_id.move_id.picking_id:
                        wf_service.trg_write(uid, 'stock.picking', line.procurement_id.move_id.picking_id.id, cr)

        self.pool.get('purchase.order.line').cancel_sol(cr, uid, line_ids, context=context)
        return self.write(cr, uid, ids, {'state':'cancel'}, context=context)

    def wkf_confirm_cancel(self, cr, uid, ids, context=None):
        """
        Continue the workflow if all other POs are confirmed
        """
        wf_service = netsvc.LocalService("workflow")
        so_obj = self.pool.get('sale.order')

        # corresponding sale order
        so_ids = self.get_so_ids_from_po_ids(cr, uid, ids, context=context)
        # from so, list corresponding po first level
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)
        # from listed po, list corresponding so
        all_so_ids = self.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)
        # from all so, list all corresponding po second level
        all_po_for_all_so_ids = so_obj.get_po_ids_from_so_ids(cr, uid, all_so_ids, context=context)

        not_confirmed_po = self.search(cr, uid, [
            ('id', 'not in', all_po_for_all_so_ids),
            ('state', '=', 'confirmed_wait'),
        ], context=context)

        # we trigger all the corresponding sale order -> test_lines is called on these so
        for so_id in all_so_ids:
            wf_service.trg_write(uid, 'sale.order', so_id, cr)

        # we trigger pos of all sale orders -> all_po_confirm is called on these po
        for po_id in all_po_for_all_so_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        for po_id in not_confirmed_po:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        return True


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
        so_obj = self.pool.get('sale.order')
        move_obj = self.pool.get('stock.move')

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
                so_obj.set_manually_done(cr, uid, order.loan_id.id, all_doc=all_doc, context=loan_context)

        # Done stock moves
        move_ids = move_obj.search(cr, uid, [('purchase_line_id', 'in', order_lines), ('state', 'not in', ('cancel', 'done'))], context=context)
        move_obj.set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)

        # Cancel all procurement ordes which have generated one of these PO
        proc_ids = self.pool.get('procurement.order').search(cr, uid, [('purchase_id', 'in', ids)], context=context)
        for proc in self.pool.get('procurement.order').browse(cr, uid, proc_ids, context=context):
            if proc.move_id and proc.move_id.id:
                move_obj.write(cr, uid, [proc.move_id.id], {'state': 'cancel'}, context=context)
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
                    _eval_expr(cr, [uid, 'purchase.order', order_id.id], False, activity.action)

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

    def check_empty_po(self, cr, uid, ids, context=None):
        """
        If the PO is empty, return a wizard to ask user if he wants
        cancel the whole PO
        """
        order_wiz_obj = self.pool.get('purchase.order.cancel.wizard')
        data_obj = self.pool.get('ir.model.data')

        for po in self.browse(cr, uid, ids, context=context):
            if all(x.state in ('cancel', 'done') for x in po.order_line):
                wiz_id = order_wiz_obj.create(cr, uid, {'order_id': po.id}, context=context)
                if po.rfq_ok:
                    view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'ask_rfq_cancel_wizard_form_view')[1]
                else:
                    view_id = data_obj.get_object_reference(cr, uid, 'purchase_override', 'ask_po_cancel_wizard_form_view')[1]
                context['view_id'] = False
                return {'type': 'ir.actions.act_window',
                        'res_model': 'purchase.order.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'view_id': [view_id],
                        'res_id': wiz_id,
                        'target': 'new',
                        'context': context}

        return {'type': 'ir.actions.act_window_close'}

    def round_to_soq(self, cr, uid, ids, context=None):
        """
        Create a new thread to check for each line of the order if the quantity
        is compatible with the SoQ rounding of the supplier catalogue or
        product. If not compatible, update the quantity to match with SoQ rounding.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of sale.order to check and update
        :param context: Context of the call
        :return: True
        """
        th = threading.Thread(
            target=self._do_round_to_soq,
            args=(cr, uid, ids, context, True),
        )
        th.start()
        th.join(5.0)

        return True

    def _do_round_to_soq(self, cr, uid, ids, context=None, use_new_cursor=False):
        """
        Check for each line of the order if the quantity is compatible
        with the SoQ rounding of the supplier catalogue or product. If
        not compatible, update the quantity to match with SoQ rounding.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of sale.order to check and update
        :param context: Context of the call
        :param use_new_cursor: True if this method is called into a new thread
        :return: True
        """
        pol_obj = self.pool.get('purchase.order.line')
        uom_obj = self.pool.get('product.uom')
        sup_obj = self.pool.get('product.supplierinfo')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if use_new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()

        try:
            self.write(cr, uid, ids, {
                'update_in_progress': True,
            }, context=context)
            if use_new_cursor:
                cr.commit()

            pol_ids = pol_obj.search(cr, uid, [
                ('order_id', 'in', ids),
                ('product_id', '!=', False),
            ], context=context)

            to_update = {}
            for pol in pol_obj.browse(cr, uid, pol_ids, context=context):
                # Check only products with defined SoQ quantity
                sup_ids = sup_obj.search(cr, uid, [
                    ('name', '=', pol.order_id.partner_id.id),
                    ('product_id', '=', pol.product_id.id),
                ], context=context)
                if not sup_ids and not pol.product_id.soq_quantity:
                    continue

                # Get SoQ value
                soq = pol.product_id.soq_quantity
                soq_uom = pol.product_id.uom_id
                if sup_ids:
                    for sup in sup_obj.browse(cr, uid, sup_ids, context=context):
                        for pcl in sup.pricelist_ids:
                            if pcl.rounding and pcl.min_quantity <= pol.product_qty:
                                soq = pcl.rounding
                                soq_uom = pcl.uom_id

                if not soq:
                    continue

                # Get line quantity in SoQ UoM
                line_qty = pol.product_qty
                if pol.product_uom.id != soq_uom.id:
                    line_qty = uom_obj._compute_qty_obj(cr, uid, pol.product_uom, pol.product_qty, soq_uom, context=context)

                good_quantity = 0
                if line_qty % soq:
                    good_quantity = (line_qty - (line_qty % soq)) + soq

                if good_quantity and pol.product_uom.id != soq_uom.id:
                    good_quantity = uom_obj._compute_qty_obj(cr, uid, soq_uom, good_quantity, pol.product_uom, context=context)

                if good_quantity:
                    to_update.setdefault(good_quantity, [])
                    to_update[good_quantity].append(pol.id)

            for qty, line_ids in to_update.iteritems():
                pol_obj.write(cr, uid, line_ids, {
                    'product_qty': qty,
                    'soq_updated': True,
                }, context=context)
        except Exception as e:
            logger = logging.getLogger('purchase.order.round_to_soq')
            logger.error(e)
        finally:
            self.write(cr, uid, ids, {
                'update_in_progress': False,
            }, context=context)

        if use_new_cursor:
            cr.commit()
            cr.close()

        return True

purchase_order()


class purchase_order_line1(osv.osv):
    '''
    this modification is placed before merged, because unit price of merged should be Computation as well
    '''
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    _columns = {
        'price_unit': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price Computation')),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
    }

    _defaults = {
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
    }

purchase_order_line1()


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
            merged_line_list = self.browse(cr, uid, ids, context=context)
            merged_line_order_line_ids = []
            for merged_line in merged_line_list:
                merged_line_order_line_ids.extend([x.id for x in
                    merged_line.order_line_ids])
            unique_order_line_ids = list(set(merged_line_order_line_ids))
            self.pool.get('purchase.order.line').write(cr, uid,
                    unique_order_line_ids,
                    {'price_unit': vals['price_unit'],
                     'old_price_unit': vals['price_unit']},
                    context=new_context)

        res = super(purchase_order_merged_line, self).write(cr, uid, ids, vals, context=context)

        return res

    def _update(self, cr, uid, p_id, po_line_id, product_qty, price=0.00, context=None, no_update=False):
        '''
        Update the quantity and the unit price according to the new qty
        '''
        line = self.browse(cr, uid, p_id, context=context)
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
            self.unlink(cr, uid, [p_id], context=context)
            return False, False

        new_price = False
        new_qty = line.product_qty + float(product_qty)

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
            self.write(cr, uid, [p_id], values, context=context)

        return p_id, new_price or False


purchase_order_merged_line()


class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    def init(self, cr):
        self.pool.get('fields.tools').remove_sql_constraint(cr,
            'purchase_order_line', 'product_qty')
        if hasattr(super(purchase_order_line, self), 'init'):
            super(purchase_order_line, self).init(cr)

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
            if 'product_uom' not in vals:
                tmp_vals.update({'product_uom': line.product_uom.id})
            if 'product_qty' not in vals:
                tmp_vals.update({'product_qty': line.product_qty})

            # If the user changed the product or the UoM or both on the PO line
            if ('product_id' in vals and line.product_id.id != vals['product_id']) or ('product_uom' in vals and line.product_uom.id != vals['product_uom']):
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                merged_id = line.merged_id.id
                change_price_ok = line.change_price_ok
                c = context.copy()
                tmp_import_in_progress = context.get('import_in_progress')
                context['import_in_progress'] = True
                c.update({'change_price_ok': change_price_ok})
                self.write(cr, uid, line_id, {'merged_id': False}, context=context)
                if tmp_import_in_progress:
                    context.update({'import_in_progress': tmp_import_in_progress})
                else:
                    del context['import_in_progress']
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
                noraise_ctx = context.copy()
                noraise_ctx.update({'noraise': True})
                # Need removing the merged_id link before update the merged line because the merged line
                # will be removed if it hasn't attached PO line
                self.write(cr, uid, [line.id], {'merged_id': False}, context=noraise_ctx)
                res_merged = merged_line_obj._update(cr, uid, merged_id, line.id, -line.product_qty, line.price_unit, context=c)

        return vals

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is restriction on lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context:
            context = {}

        for line in self.browse(cr, uid, ids, context=context):
            if line.order_id and line.order_id.partner_id and line.order_id.state != 'done' and line.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, line.product_id.id, vals={'partner_id': line.order_id.partner_id.id}, context=context):
                    return False

        return True

    def _relatedFields(self, cr, uid, vals, context=None):
        '''
        related fields for create and write
        '''
        # recreate description because in readonly
        if ('product_id' in vals) and (vals['product_id']):
            # no nomenclature description
            vals.update({'nomenclature_description':False})
            # update the name (comment) of order line
            # the 'name' is no more the get_name from product, but instead
            # the name of product
            productObj = self.pool.get('product.product').browse(cr, uid, vals['product_id'], context=context)
            vals.update({'name':productObj.name})
            vals.update({'default_code':productObj.default_code})
            vals.update({'default_name':productObj.name})
            # erase the nomenclature - readonly
            self.pool.get('product.product')._resetNomenclatureFields(vals)
        elif ('product_id' in vals) and (not vals['product_id']):
            sale = self.pool.get('sale.order.line')
            sale._setNomenclatureInfo(cr, uid, vals, context)
            # erase default code
            vals.update({'default_code':False})
            vals.update({'default_name':False})

            if 'comment' in vals:
                vals.update({'name':vals['comment']})
        # clear nomenclature filter values
        #self.pool.get('product.product')._resetNomenclatureFields(vals)

    def _update_name_attr(self, cr, uid, vals, context=None):
        """Update the name attribute in `vals` if a product is selected."""
        if context is None:
            context = {}
        prod_obj = self.pool.get('product.product')
        if vals.get('product_id'):
            product = prod_obj.browse(cr, uid, vals['product_id'], context=context)
            vals['name'] = product.name
        elif vals.get('comment'):
            vals['name'] = vals.get('comment', False)

    def _check_product_uom(self, cr, uid, product_id, uom_id, context=None):
        """Check the product UoM."""
        if context is None:
            context = {}
        uom_tools_obj = self.pool.get('uom.tools')
        if not uom_tools_obj.check_uom(cr, uid, product_id, uom_id, context=context):
            raise osv.except_osv(
                _('Error'),
                _('You have to select a product UOM in the same '
                  'category than the purchase UOM of the product !'))

    def create(self, cr, uid, vals, context=None):
        '''
        Create or update a merged line
        '''
        if context is None:
            context = {}

        po_obj = self.pool.get('purchase.order')
        seq_pool = self.pool.get('ir.sequence')
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')

        order_id = vals.get('order_id')
        product_id = vals.get('product_id')
        product_uom = vals.get('product_uom')
        order = po_obj.browse(cr, uid, order_id, context=context)

        if order.from_yml_test:
            vals.update({'change_price_manually': True})
            if not vals.get('product_qty', False):
                vals['product_qty'] = 1.00
            # [imported and adapted from 'analytic_distribution_supply']
            if not vals.get('price_unit', False):
                vals['price_unit'] = 1.00
            # [/]

        # Update the name attribute if a product is selected
        self._update_name_attr(cr, uid, vals, context=context)

        # If we are on a RfQ, use the last entered unit price and update other lines with this price
        if order.rfq_ok:
            vals.update({'change_price_manually': True})
        else:
            if order.po_from_fo or order.po_from_ir:
                vals['from_fo'] = True
            if vals.get('product_qty', 0.00) == 0.00 and not context.get('noraise'):
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

        other_lines = self.search(cr, uid, [('order_id', '=', order_id),
            ('product_id', '=', product_id), ('product_uom', '=', product_uom)],
            limit=1, order='NO_ORDER', context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)

        if vals.get('origin'):
            proc = False
            if vals.get('procurement_id'):
                proc = self.pool.get('procurement.order').browse(cr, uid, vals.get('procurement_id'))
            if not proc or not proc.sale_id:
                vals.update(self.update_origin_link(cr, uid, vals.get('origin'), context=context))

        if (other_lines and stages and order.state != 'confirmed'):
            context.update({'change_price_ok': False})

        if not context.get('offline_synchronization'):
            vals = self._update_merged_line(cr, uid, False, vals, context=dict(context, skipResequencing=True))

        vals.update({'old_price_unit': vals.get('price_unit', False)})

        # [imported from 'order_nomenclature']
        # Don't save filtering data
        self._relatedFields(cr, uid, vals, context)
        # [/]

        # [imported from 'order_line_number']
        # Add the corresponding line number
        #   I leave this line from QT related to purchase.order.merged.line for compatibility and safety reasons
        #   merged lines, set the line_number to 0 when calling create function
        #   the following line should *logically* be removed safely
        #   copy method should work as well, as merged line do *not* need to keep original line number with copy function (QT confirmed)
        if self._name != 'purchase.order.merged.line':
            if order_id:
                # gather the line number from the sale order sequence if not specified in vals
                # either line_number is not specified or set to False from copy, we need a new value
                if not vals.get('line_number', False):
                    # new number needed - gather the line number from the sequence
                    sequence_id = order.sequence_id.id
                    line = seq_pool.get_id(cr, uid, sequence_id, code_or_id='id', context=context)
                    vals.update({'line_number': line})
        # [/]

        # Check the selected product UoM
        if not context.get('import_in_progress', False):
            if vals.get('product_id') and vals.get('product_uom'):
                self._check_product_uom(
                    cr, uid, vals['product_id'], vals['product_uom'], context=context)

        # utp-518:we write the comment from the sale.order.line on the PO line through the procurement (only for the create!!)
        po_procurement_id = vals.get('procurement_id', False)
        if po_procurement_id:
            sale_id = sol_obj.search(cr, uid, [('procurement_id', '=', po_procurement_id)], context=context)
            if sale_id:
                comment_so = sol_obj.read(cr, uid, sale_id, ['comment'], context=context)[0]['comment']
                vals.update(comment=comment_so)

        # add the database Id to the sync_order_line_db_id
        po_line_id = super(purchase_order_line, self).create(cr, uid, vals, context=context)
        if not vals.get('sync_order_line_db_id', False): #'sync_order_line_db_id' not in vals or vals:
            name = order.name
            super(purchase_order_line, self).write(cr, uid, [po_line_id], {'sync_order_line_db_id': name + "_" + str(po_line_id),}, context=context)

        if self._name != 'purchase.order.merged.line' and vals.get('origin') and not vals.get('procurement_id'):
            so_ids = so_obj.search(cr, uid, [('name', '=', vals.get('origin'))], context=context)
            for so_id in so_ids:
                self.pool.get('expected.sale.order.line').create(cr, uid, {
                    'order_id': so_id,
                    'po_line_id': po_line_id,
                }, context=context)

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
        defaults.update({'merged_id': False, 'sync_order_line_db_id': False})

        return super(purchase_order_line, self).copy(cr, uid, line_id, defaults, context=context)

    def copy_data(self, cr, uid, p_id, default=None, context=None):
        """
        """
        # Some verifications
        if not context:
            context = {}
        if not default:
            default = {}

        if 'move_dest_id' not in default:
            default.update({'move_dest_id': False})

        if 'procurement_id' not in default:
            default.update({'procurement_id': False})

        default.update({'sync_order_line_db_id': False})
        return super(purchase_order_line, self).copy_data(cr, uid, p_id, default=default, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update merged line
        '''
        so_obj = self.pool.get('sale.order')
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = False

        # [imported from the 'analytic_distribution_supply']
        # Don't save filtering data
        self._relatedFields(cr, uid, vals, context)
        # [/]

        # Update the name attribute if a product is selected
        self._update_name_attr(cr, uid, vals, context=context)

        if 'price_unit' in vals:
            vals.update({'old_price_unit': vals.get('price_unit')})

        if ('state' in vals and vals.get('state') != 'draft') or ('procurement_id' in vals and vals.get('procurement_id')):
            exp_sol_ids = exp_sol_obj.search(cr, uid, [('po_line_id', 'in', ids)],
                    order='NO_ORDER', context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        # Remove SoQ updated flag in case of manual modification
        if not 'soq_updated' in vals:
            vals['soq_updated'] = False

        for line in self.browse(cr, uid, ids, context=context):
            new_vals = vals.copy()
            # check qty
            if vals.get('product_qty', line.product_qty) <= 0.0 and \
                not line.order_id.rfq_ok and \
                'noraise' not in context and line.state != 'cancel':
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

            if vals.get('origin', line.origin):
                proc = False
                if vals.get('procurement_id', line.procurement_id.id):
                    proc = self.pool.get('procurement.order').browse(cr, uid, vals.get('procurement_id', line.procurement_id.id))
                if not proc or not proc.sale_id:
                    link_so_dict = self.update_origin_link(cr, uid, vals.get('origin', line.origin), context=context)
                    new_vals.update(link_so_dict)

            if line.order_id and not line.order_id.rfq_ok and (line.order_id.po_from_fo or line.order_id.po_from_ir):
                new_vals['from_fo'] = True

            if not context.get('update_merge'):
                new_vals.update(self._update_merged_line(cr, uid, line.id, vals, context=dict(context, skipResequencing=True, noraise=True)))

            res = super(purchase_order_line, self).write(cr, uid, [line.id], new_vals, context=context)

            if self._name != 'purchase.order.merged.line' and vals.get('origin') and not vals.get('procurement_id', line.procurement_id):
                so_ids = so_obj.search(cr, uid, [('name', '=', vals.get('origin'))], order='NO_ORDER', context=context)
                for so_id in so_ids:
                    exp_sol_obj.create(cr, uid, {
                        'order_id': so_id,
                        'po_line_id': line.id,
                    }, context=context)

        # Check the selected product UoM
        if not context.get('import_in_progress', False):
            for pol_read in self.read(cr, uid, ids, ['product_id', 'product_uom']):
                if pol_read.get('product_id'):
                    product_id = pol_read['product_id'][0]
                    uom_id = pol_read['product_uom'][0]
                    self._check_product_uom(cr, uid, product_id, uom_id, context=context)

        return res

    def update_origin_link(self, cr, uid, origin, context=None):
        '''
        Return the FO/IR that matches with the origin value
        '''
        so_obj = self.pool.get('sale.order')

        tmp_proc_context = context.get('procurement_request')
        context['procurement_request'] = True
        so_ids = so_obj.search(cr, uid, [('name', '=', origin), ('state', 'in', ('sourced', 'progress', 'manual'))], context=context)
        context['procurement_request'] = tmp_proc_context
        if so_ids:
            return {'link_so_id': so_ids[0]}

        return {}

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Call the unlink method for lines and if the PO becomes empty
        ask the user if he wants to cancel the PO
        '''
        # Objects
        wiz_obj = self.pool.get('purchase.order.line.unlink.wizard')
        proc_obj = self.pool.get('procurement.order')
        data_obj = self.pool.get('ir.model.data')
        wkf_act_obj = self.pool.get('workflow.activity')
        opl_obj = self.pool.get('stock.warehouse.orderpoint.line')

        # Variables initialization
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Check if the line is not already removed
        ids = self.search(cr, uid, [('id', 'in', ids)], context=context)
        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('The line has been already deleted - Please refresh the page'),
            )

        if context.get('rfq_ok', False):
            view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'rfq_line_unlink_wizard_form_view')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'purchase_override', 'purchase_order_line_unlink_wizard_form_view')[1]

        for line in self.browse(cr, uid, ids, context=context):
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, [line.id], context=context)
            exp_sol_ids = self.get_exp_sol_ids_from_pol_ids(cr, uid, [line.id], context=context)
            if (sol_ids or exp_sol_ids) and not context.get('from_del_wizard'):
                wiz_id = wiz_obj.create(cr, uid, {'line_id': line.id, 'only_exp': (not sol_ids and exp_sol_ids) and True or False}, context=context)
                if sol_ids or wiz_obj.read(cr, uid, wiz_id, ['last_line'], context=context)['last_line']:
                    return {'type': 'ir.actions.act_window',
                            'res_model': 'purchase.order.line.unlink.wizard',
                            'view_type': 'form',
                            'view_mode': 'form',
                            'view_id': [view_id],
                            'res_id': wiz_id,
                            'target': 'new',
                            'context': context}

            # In case of a PO line is created to source a FO/IR but the corresponding
            # FO/IR line will be created when the PO will be confirmed
            if not line.procurement_id and line.origin:
                wiz_id = wiz_obj.create(cr, uid, {'line_id': line.id}, context=context)
                return wiz_obj.just_cancel(cr, uid, [wiz_id], context=context)

            # In case of a PO line is not created to source a FO/IR but from a
            # replenishment rule, cancel the stock move and the procurement order
            if line.move_dest_id:
                self.pool.get('stock.move').action_cancel(cr, uid, [line.move_dest_id.id], context=context)
                proc_ids = proc_obj.search(cr, uid, [('move_id', '=', line.move_dest_id.id)], context=context)
                if proc_ids:
                    # Delete link between proc. order and min/max rule lines
                    opl_ids = opl_obj.search(cr, uid, [('procurement_id', 'in', proc_ids)], context=context)
                    opl_obj.write(cr, uid, opl_ids, {'procurement_id': False}, context=context)
                    wf_service = netsvc.LocalService("workflow")
                    for proc_id in proc_ids:
                        wf_service.trg_delete(uid, 'procurement.order', proc_id, cr)
                        wkf_id = data_obj.get_object_reference(cr, uid, 'procurement', 'act_cancel')[1]
                        activity = wkf_act_obj.browse(cr, uid, wkf_id, context=context)
                        _eval_expr(cr, [uid, 'procurement.order', proc_id], False, activity.action)

        context['from_del_wizard'] = False
        return self.unlink(cr, uid, ids, context=context)

    def cancel_sol(self, cr, uid, ids, context=None):
        '''
        Re-source the FO line
        '''
        context = context or {}
        sol_obj = self.pool.get('sale.order.line')
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj = self.pool.get('sale.order')
        uom_obj = self.pool.get('product.uom')

        if isinstance(ids, (int, long)):
            ids = [ids]

        sol_to_update = {}
        sol_not_to_delete_ids = []
        ir_to_potentialy_cancel_ids = []
        sol_of_po_line_resourced_ids = []

        so_to_cancel_ids = []
        for line in self.browse(cr, uid, ids, context=context):
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, [line.id], context=context)

            if not sol_ids and line.origin:
                origin_ids = so_obj.search(cr, uid, [('name', '=', line.origin)], context=context)
                for origin in so_obj.read(cr, uid, origin_ids, ['order_line'], context=context):
                    exp_sol_ids = exp_sol_obj.search(cr, uid, [('order_id', '=', origin['id']), ('po_line_id', '!=', line.id)],
                        limit=1, order='NO_ORDER', context=context)
                    if not origin['order_line'] and not exp_sol_ids:
                        so_to_cancel_ids.extend(origin_ids)

            line_qty = line.product_qty
            if 'pol_qty' in context and line.id in context['pol_qty']:
                line_qty = context['pol_qty'].get(line.id, 0.00)

            for sol in sol_obj.browse(cr, uid, sol_ids, context=context):
                diff_qty = uom_obj._compute_qty(cr, uid, line.product_uom.id, line_qty, sol.product_uom.id)
                # In case of the product qty of the PO line is decrease before the cancelation, check if there
                # is some other PO lines related to this FO line, then cancel the whole line.
                if 'pol_qty' not in context and sol.procurement_id:
                    pol_ids = self.search(cr, uid, [('procurement_id', '=', sol.procurement_id.id)], context=context)
                    if len(pol_ids) == 1 and pol_ids[0] == line.id:
                        diff_qty = sol.product_uom_qty

                sol_to_update.setdefault(sol.id, 0.00)
                sol_to_update[sol.id] += diff_qty
                if line.has_to_be_resourced:
                    sol_obj.add_resource_line(cr, uid, sol, False, diff_qty, context=context)
                    sol_of_po_line_resourced_ids.append(sol.id)
                if sol.order_id.procurement_request:
                    # UFTP-82: do not delete IR line, cancel it
                    sol_not_to_delete_ids.append(sol.id)
                    if sol.order_id.id not in ir_to_potentialy_cancel_ids:
                        ir_to_potentialy_cancel_ids.append(sol.order_id.id)

        context['pol_ids'] = ids
        # In case of cancelation and resourcing from IN cancelation
        for sol in sol_to_update:
            context['update_or_cancel_line_not_delete'] = sol in sol_not_to_delete_ids
            if context.get('update_or_cancel_line_not_delete', False) or not context.get('from_in_cancel', False):
                so_to_cancel_id = sol_obj.update_or_cancel_line(cr, uid, sol, sol_to_update[sol], context=context)
                if so_to_cancel_id:
                    so_to_cancel_ids.append(so_to_cancel_id)

        del context['pol_ids']

        if context.get('update_or_cancel_line_not_delete', False):
            del context['update_or_cancel_line_not_delete']

        # UFTP-82: IR and its PO is cancelled
        # IR cancel all lines that have to be cancelled
        # and cancel IR if all its lines cancelled
        if ir_to_potentialy_cancel_ids:
            for ir in so_obj.browse(cr, uid, ir_to_potentialy_cancel_ids, context=context):
                # new IR state:
                # we change his state to 'cancel' if at least one line cancelled
                # we change his state to 'done' if all lines cancelled and resourced
                # else NO CHANGE
                ir_new_state = 'cancel'
                lines_to_cancel_ids = []
                all_lines_resourced = True

                # check if at least one line is cancelled
                # or all lines cancel and resourced
                for irl in ir.order_line:
                    line_cancelled = False
                    if ir.is_ir_from_po_cancel and \
                        (irl.state == 'cancel' or irl.state == 'exception'):
                        # note PO sourced from IR, IR cancelled line can be in 'exception' as a 'cancelled' one
                        line_cancelled = True
                        if irl.id not in sol_of_po_line_resourced_ids:
                            all_lines_resourced = False  # one cancelled line not resourced
                        if irl.state == 'exception':
                            lines_to_cancel_ids.append(irl.id)  # to be set to cancel
                    if not line_cancelled:
                        ir_new_state = False  # no cancelled line left, then no change
                if ir_new_state and all_lines_resourced:
                    # 'state change' flaged and all line resourced, state to done
                    ir_new_state = 'done'

                if lines_to_cancel_ids:
                    sol_obj.write(cr, uid, lines_to_cancel_ids,
                        {'state': ir_new_state if ir_new_state else 'cancel'},
                        context=context)
                if ir_new_state:
                    so_obj.write(cr, uid, ir.id,
                        {'state':  ir_new_state}, context=context)

        return so_to_cancel_ids

    def fake_unlink(self, cr, uid, ids, context=None):
        '''
        Add an entry to cancel (and resource if needed) the line when the
        PO will be confirmed
        '''
        proc_obj = self.pool.get('procurement.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        so_to_cancel = []

        proc_ids = []
        purchase_ids = []
        line_to_cancel = []

        for line in self.browse(cr, uid, ids, context=context):
            # Set the procurement orders to delete
            # Set the list of linked purchase orders
            if line.procurement_id:
                proc_ids.append(line.procurement_id.id)
            if line.order_id.id not in purchase_ids:
                purchase_ids.append(line.order_id.id)

            if not self.pool.get('sale.order.line.cancel').search(cr, uid, [
                ('sync_order_line_db_id', '=', line.sync_order_line_db_id),
            ], limit=1, order='NO_ORDER', context=context):
                so_to_cancel = self.cancel_sol(cr, uid, [line.id], context=context)

            # we want to skip resequencing because unlink is performed on merged purchase order lines
            tmp_Resequencing = context.get('skipResequencing', False)
            context['skipResequencing'] = True
            self._update_merged_line(cr, uid, line.id, False, context=context)
            context['skipResequencing'] = tmp_Resequencing

            line_to_cancel.append(line.id)

        # Cancel the listed procurement orders
        for proc_id in proc_ids:
            if not self.search(cr, uid, [
                ('order_id.state', '!=', 'split'),
                ('id', 'not in', ids),
                ('procurement_id', '=', proc_id)],
                limit=1, order='NO_ORDER', context=context):
                proc_obj.action_cancel(cr, uid, [proc_id])

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        self.unlink(cr, uid, line_to_cancel, context=context)

        return so_to_cancel

    def unlink(self, cr, uid, ids, context=None):
        '''
        Update the merged line
        '''
        po_obj = self.pool.get('purchase.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        order_ids = []
        for line in self.read(cr, uid, ids, ['id', 'order_id'], context=context):
            # we want to skip resequencing because unlink is performed on merged purchase order lines
            tmp_skip_resourcing = context.get('skipResourcing', False)
            context['skipResourcing'] = True
            self._update_merged_line(cr, uid, line['id'], False, context=context)
            context['skipResourcing'] = tmp_skip_resourcing
            if line['order_id'][0] not in order_ids:
                order_ids.append(line['order_id'][0])

        if context.get('from_del_wizard'):
            return self.ask_unlink(cr, uid, ids, context=context)

        res = super(purchase_order_line, self).unlink(cr, uid, ids, context=context)

        for pol_id in ids:
            self.infolog(cr, uid, "The PO/RfQ line id:%s has been deleted" % pol_id)

        po_obj.wkf_confirm_trigger(cr, uid, order_ids, context=context)

        return res

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
        suppinfo_ids = self.pool.get('product.supplierinfo').search(cr, uid,
                [('name', '=', order.partner_id.id),
                 ('product_id', '=', product_id)],
                order='NO_ORDER', context=context)
        if suppinfo_ids:
            pricelist = self.pool.get('pricelist.partnerinfo').search(cr, uid,
                [('currency_id', '=', order.pricelist_id.currency_id.id),
                 ('suppinfo_id', 'in', suppinfo_ids),
                 ('uom_id', '=', uom_id),
                 '|', ('valid_till', '=', False),
                 ('valid_till', '>=', order.date_order)],
                limit=2, context=context)
            if len(pricelist) > 1:
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

    def on_change_select_fo(self, cr, uid, ids, fo_id, context=None):
        '''
        Fill the origin field if a FO is selected
        '''
        so_obj = self.pool.get('sale.order')
        if fo_id:
            fo = so_obj.browse(cr, uid, fo_id, context=context)
            res = {'value': {'origin': fo.name,
                             'display_sync_ref': len(fo.sourced_references) and True or False,
                             'select_fo': False}}
            return res

        return {
            'value': {
                'display_sync_ref': False,
            },
        }

    def on_change_origin(self, cr, uid, ids, origin, procurement_id=False, partner_type='external', context=None):
        '''
        Check if the origin is a known FO/IR
        '''
        res = {}
        if not procurement_id and origin:
            domain = [('name', '=', origin), ('state', 'in', ('sourced', 'progres', 'manual'))]
            o_type = 'a Non-ESC'
            if partner_type == 'esc':
                o_type = 'an ESC'
                domain.append(('split_type_sale_order', '=', 'esc_split_sale_order'))
            else:
                domain.append(('split_type_sale_order', '=', 'local_purchase_split_sale_order'))
            sale_id = self.pool.get('sale.order').search(cr, uid, domain,
                    limit=1, order='NO_ORDER', context=context)
            if not sale_id:
                res['warning'] = {'title': _('Warning'),
                                  'message': _('The reference \'%s\' put in the Origin field doesn\'t match with a confirmed FO/IR sourced with %s supplier. No FO/IR line will be created for this PO line') % (origin, o_type)}
                res['value'] = {
                    'display_sync_ref': False,
                    'instance_sync_order_ref': '',
                }
            else:
                res['value'] = {
                    'display_sync_ref': True,
                }

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

        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            # default values
            result[obj.id] = {'order_state_purchase_order_line': False}
            # order_state_purchase_order_line
            if obj.order_id:
                result[obj.id].update({'order_state_purchase_order_line': obj.order_id.state})

        return result

    def _get_project_po_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the name of the PO at project side
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line_id in ids:
            res[line_id] = ''
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, line_id, context=context)
            for sol in self.pool.get('sale.order.line').browse(cr, uid, sol_ids, context=context):
                if sol.order_id and sol.order_id.client_order_ref:
                    if res[line_id]:
                        res[line_id] += ' - '
                    res[line_id] += sol.order_id.client_order_ref

        return res

    def _get_link_sol_id(self, cr, uid, ids, field_name, args, context=None):
        """
        Return the ID of the first FO line sourced by this PO line
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line_id in ids:
            sol_ids = self.get_sol_ids_from_pol_ids(cr, uid, [line_id], context=context)
            if sol_ids:
                res[line_id] = sol_ids[0]

        return res

    _columns = {
        'is_line_split': fields.boolean(string='This line is a split line?'), # UTP-972: Use boolean to indicate if the line is a split line
        'merged_id': fields.many2one('purchase.order.merged.line', string='Merged line'),
        'origin': fields.char(size=512, string='Origin'),
        'link_so_id': fields.many2one('sale.order', string='Linked FO/IR', readonly=True),
        'dpo_received': fields.boolean(string='Is the IN has been received at Project side ?'),
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
        'external_ref': fields.char(size=256, string='Ext. Ref.'),
        'project_ref': fields.char(size=256, string='Project Ref.'),
        'has_to_be_resourced': fields.boolean(string='Has to be re-sourced'),
        'select_fo': fields.many2one('sale.order', string='FO'),
        'fnct_project_ref': fields.function(_get_project_po_ref, method=True, string='Project PO',
                                            type='char', size=128, store=False),
        'from_fo': fields.boolean(string='From FO', readonly=True),
        'display_sync_ref': fields.boolean(string='Display sync. ref.'),
        'instance_sync_order_ref': fields.many2one(
            'sync.order.label',
            string='Order in sync. instance',
        ),
        'link_sol_id': fields.function(
            _get_link_sol_id,
            method=True,
            type='many2one',
            relation='sale.order.line',
            string='Linked FO line',
            store=False,
        ),
        'soq_updated': fields.boolean(
            string='SoQ updated',
            readonly=True,
        ),
    }

    _defaults = {
        'change_price_manually': lambda *a: False,
        'product_qty': lambda *a: 0.00,
        'price_unit': lambda *a: 0.00,
        'change_price_ok': lambda *a: True,
        'is_line_split': False, # UTP-972: by default not a split line
        'from_fo': lambda self, cr, uid, c: not c.get('rfq_ok', False) and c.get('from_fo', False),
        'soq_updated': False,
    }

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
        partner_price = self.pool.get('pricelist.partnerinfo')
        product_obj = self.pool.get('product.product')

        if not context:
            context = {}

        # If the user modify a line, remove the old quantity for the total quantity
        if ids:
            for line_id in self.browse(cr, uid, ids, context=context):
                all_qty -= line_id.product_qty

        if product and not uom:
            uom = self.pool.get('product.product').browse(cr, uid, product).uom_id.id

        if context and context.get('purchase_id') and state == 'draft' and product:
            domain = [('product_id', '=', product),
                      ('product_uom', '=', uom),
                      ('order_id', '=', context.get('purchase_id'))]
            other_lines = self.search(cr, uid, domain, order='NO_ORDER')
            for l in self.browse(cr, uid, other_lines):
                all_qty += l.product_qty

        res = super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, all_qty, uom,
                                                                 partner_id, date_order, fiscal_position,
                                                                 date_planned, name, price_unit, notes)

        if res.get('warning', {}).get('title', '') == 'No valid pricelist line found !' or qty == 0.00:
            res.update({'warning': {}})

        func_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        if pricelist:
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist).currency_id.id
        else:
            currency_id = func_curr_id

        if product and partner_id:
            # Test the compatibility of the product with a the partner of the order
            res, test = product_obj._on_change_restriction_error(cr, uid, product, field_name='product_id', values=res, vals={'partner_id': partner_id}, context=context)
            if test:
                return res

        # Update the old price value
        res['value'].update({'product_qty': qty})
        if product and not res.get('value', {}).get('price_unit', False) and all_qty != 0.00 and qty != 0.00:
            # Display a warning message if the quantity is under the minimal qty of the supplier
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist).currency_id.id
            tmpl_id = self.pool.get('product.product').read(cr, uid, product, ['product_tmpl_id'])['product_tmpl_id'][0]
            info_prices = []
            suppinfo_ids = self.pool.get('product.supplierinfo').search(cr, uid, [('name', '=', partner_id), ('product_id', '=', tmpl_id)], context=context)
            domain = [('uom_id', '=', uom),
                      ('suppinfo_id', 'in', suppinfo_ids),
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
            st_uom = self.pool.get('product.product').browse(cr, uid, product).uom_id.id
            st_price = self.pool.get('product.product').browse(cr, uid, product).standard_price
            st_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, st_price, round=False, context=context)
            st_price = self.pool.get('product.uom')._compute_price(cr, uid, st_uom, st_price, uom)

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

        if context and context.get('categ') and product:
            # Check consistency of product
            consistency_message = product_obj.check_consistency(cr, uid, product, context.get('categ'), context=context)
            if consistency_message:
                res.setdefault('warning', {})
                res['warning'].setdefault('title', 'Warning')
                res['warning'].setdefault('message', '')

                res['warning']['message'] = '%s \n %s' % (res.get('warning', {}).get('message', ''), consistency_message)

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
        other_lines = self.search(cr, uid,
                [('id', '!=', fake_id),
                 ('order_id', '=', order_id),
                 ('product_id', '=', product_id),
                 ('product_uom', '=', product_uom)],
                limit=1, order='NO_ORDER', context=context)
        stages = self._get_stages_price(cr, uid, product_id, product_uom, order, context=context)

        if not change_price_ok or (other_lines and stages and order.state != 'confirmed' and not context.get('rfq_ok')):
            res.update({'warning': {'title': 'Error',
                                    'message': 'This product get stages prices for this supplier, you cannot change the price manually in draft state '\
                                               'as you have multiple order lines (it is possible in "validated" state.'}})
            res['value'].update({'price_unit': old_price_unit})
        else:
            res['value'].update({'old_price_unit': price_unit})

        return res

    def get_exp_sol_ids_from_pol_ids(self, cr, uid, ids, context=None, po_line=False):
        """
        input: purchase order line ids
        return: expected sale order line ids
        """
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        so_obj = self.pool.get('sale.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if po_line and isinstance(po_line, (int, long)):
            po_line = [po_line]

        so_name = []
        for line in self.read(cr, uid, ids, ['origin'], context=context):
            if line['origin'] and line['origin'] not in so_name:
                so_name.append(line['origin'])

        so_ids = so_obj.search(cr, uid, [('name', 'in', so_name)],
                order='NO_ORDER', context=context)
        exp_sol_domain = [('order_id', 'in', so_ids)]
        if po_line:
            exp_sol_domain.append(('po_line_id', 'not in', po_line))

        return exp_sol_obj.search(cr, uid, exp_sol_domain, context=context)

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
        'unmatched_categ': fields.boolean(string='Unmatched categories'),
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(purchase_order_group, self).default_get(cr, uid, fields, context=context)
        if context.get('active_model','') == 'purchase.order' and len(context['active_ids']) < 2:
            raise osv.except_osv(_('Warning'),
            _('Please select multiple order to merge in the list view.'))

        res['po_value_id'] = context['active_ids'][-1]

        categories = set()
        for po in self.pool.get('purchase.order').read(cr, uid, context['active_ids'], ['categ'], context=context):
            categories.add(po['categ'])

        if len(categories) > 1:
            res['unmatched_categ'] = True

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

    def _product_price(self, cr, uid, ids, field_name, args, context=None):
        res = super(product_product, self)._product_price(cr, uid, ids, field_name, args, context=context)

        for product in res:
            if res[product] == 0.00:
                try:
                    res[product] = self.pool.get('product.product').read(cr, uid, [product], ['standard_price'], context=context)[0]['standard_price']
                except:
                    pass

        return res

    def _get_purchase_type(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for p_id in ids:
            res[p_id] = True

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
        'price': fields.function(_product_price, method=True, type='float', string='Pricelist', digits_compute=dp.get_precision('Sale Price')),
    }

    def check_consistency(self, cr, uid, product_id, category, context=None):
        """
        Check the consistency of product according to category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param product_id: ID of the product.product to check
        :param category: DB value of the category to check
        :param context: Context of the call
        :return: A warning message or False
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if context is None:
            context = {}

        display_message = False

        # No check for Other
        if category == 'other':
            return False

        product = self.read(cr, uid, product_id, [
            'nomen_manda_0',
            'type',
            'transport_ok',
        ], context=context)
        transport_product = product['transport_ok']
        product_type = product['type']
        main_type = product['nomen_manda_0'][0]

        if category == 'medical':
            try:
                med_nomen = nomen_obj.search(cr, uid, [
                    ('level', '=', 0),
                    ('name', '=', 'MED'),
                ], context=context)[0]
            except IndexError:
                raise osv.except_osv(
                    _('Error'),
                    _('MED nomenclature Main Type not found'),
            )

            if main_type != med_nomen:
                display_message = True

        if category == 'log':
            try:
                log_nomen = nomen_obj.search(cr, uid, [
                    ('level', '=', 0),
                    ('name', '=', 'LOG'),
                ], context=context)[0]

            except IndexError:
                raise osv.except_osv(
                    _('Error'),
                    _('LOG nomenclature Main Type not found')
                )

            if main_type != log_nomen:
                display_message = True

        if category == 'service' and product_type != 'service_recep':
            display_message = True

        if category == 'transport' and (product_type != 'service_recep' or not transport_product):
            display_message = True

        if display_message:
            return 'Warning you are about to add a product which does not conform to this' \
                ' order category, do you wish to proceed ?'
        else:
            return False

product_product()


class purchase_order_line_unlink_wizard(osv.osv_memory):
    _name = 'purchase.order.line.unlink.wizard'

    def _get_last_line(self, cr, uid, ids, field_name, args, context=None):
        """
        Return True if the line is the last line to confirm before confirm
        all other PO.
        """
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        sol_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = False

            # Add a check to avoid error in server log
            if not pol_obj.search(cr, uid, [('id', '=', wiz.line_id.id)],
                    limit=1, order='NO_ORDER', context=context):
                continue

            exp_sol_ids = pol_obj.get_exp_sol_ids_from_pol_ids(cr, uid, [wiz.line_id.id], context=context, po_line=wiz.line_id.id)

            if wiz.line_id.procurement_id:
                order_id = wiz.line_id.order_id.id
                po_so_ids, po_ids, so_ids, sol_nc_ids = po_obj.sourcing_document_state(cr, uid, [order_id], context=context)
                sol_ids = sol_obj.search(cr, uid, [('procurement_id', '=', wiz.line_id.procurement_id.id)], order='NO_ORDER', context=context)

                if order_id in po_ids:
                    po_ids.remove(order_id)
                for sol_id in sol_ids:
                    if sol_id in sol_nc_ids:
                        sol_nc_ids.remove(sol_id)

                if po_ids and not sol_nc_ids and not exp_sol_ids:
                    res[wiz.id] = True
            elif wiz.line_id.origin and not exp_sol_ids:
                res[wiz.id] = True

        return res

    _columns = {
        'line_id': fields.many2one('purchase.order.line', 'Line to delete'),
        'last_line': fields.function(
            _get_last_line,
            method=True,
            type='boolean',
            string='Last line to confirm',
            readonly=True,
            store=False,
        ),
        'only_exp': fields.boolean(
            string='Remains only expected FO/IR lines',
            readonly=True,
        ),
    }

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Cancel the line
        '''
        # Objects
        line_obj = self.pool.get('purchase.order.line')
        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        line_ids =[]
        po_ids = set()
        for wiz in self.browse(cr, uid, ids, context=context):
            po_ids.add(wiz.line_id.order_id.id)
            line_ids.append(wiz.line_id.id)

        if context.get('has_to_be_resourced'):
            line_obj.write(cr, uid, line_ids, {'has_to_be_resourced': True}, context=context)

        so_to_cancel_ids = line_obj.fake_unlink(cr, uid, line_ids, context=context)

        if not so_to_cancel_ids:
            return po_obj.check_empty_po(cr, uid, list(po_ids), context=context)
        else:
            context.update({
                'from_po': True,
                'po_ids': list(po_ids),
            })
            return so_obj.open_cancel_wizard(cr, uid, so_to_cancel_ids, context=context)

        return {'type': 'ir.actions.act_window_close'}


    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Flag the line to be re-sourced and run cancel method
        '''
        # Objects
        if context is None:
            context = {}

        context['has_to_be_resourced'] = True

        return self.just_cancel(cr, uid, ids, context=context)

purchase_order_line_unlink_wizard()


class purchase_order_cancel_wizard(osv.osv_memory):
    _name = 'purchase.order.cancel.wizard'

    _columns = {
        'order_id': fields.many2one(
            'purchase.order',
            string='Order to delete',
        ),
        'unlink_po': fields.boolean(
            string='Unlink PO',
        ),
        'last_lines': fields.boolean(
            string='Remove last lines of the FO',
        ),
    }

    def _get_last_lines(self, cr, uid, order_id, context=None):
        """
        Returns True if the deletion of the PO will delete the last lines
        of the FO/IR.
        """
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        po_obj = self.pool.get('purchase.order')

        po_so_ids, po_ids, so_ids, sol_nc_ids = po_obj.sourcing_document_state(cr, uid, [order_id], context=context)
        if order_id in po_ids:
            po_ids.remove(order_id)

        exp_sol_ids = exp_sol_obj.search(cr, uid,
                                         [('order_id', 'in', po_so_ids),
                                          ('po_id', '!=', order_id)],
                                         limit=1, order='NO_ORDER', context=context)

        if not exp_sol_ids and not po_ids:
            return True

        return False

    def fields_view_get(self, cr, uid, view_id=False, view_type='form', context=None, toolbar=False, submenu=False):
        return super(purchase_order_cancel_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

    def ask_unlink(self, cr, uid, order_id, context=None):
        '''
        Return the wizard
        '''
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if self._name == 'rfq.cancel.wizard':
            view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'ask_rfq_cancel_wizard_form_view')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'purchase_override', 'ask_po_cancel_wizard_form_view')[1]
        wiz_id = self.create(cr, uid, {'order_id': order_id}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order.cancel.wizard',
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def close_window(self, cr, uid, ids, context=None):
        '''
        Close the pop-up and reload the PO
        '''
        return {'type': 'ir.actions.act_window_close'}

    def cancel_po(self, cr, uid, ids, context=None):
        '''
        Cancel the PO and display his form
        '''
        po_obj = self.pool.get('purchase.order')
        so_obj = self.pool.get('sale.order')
        line_obj = self.pool.get('purchase.order.line')
        wf_service = netsvc.LocalService("workflow")


        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        line_ids = []
        order_ids = []
        order_to_check = []
        for wiz in self.browse(cr, uid, ids, context=context):
            order_ids.append(wiz.order_id.id)
            if wiz.last_lines and wiz.order_id.id not in order_to_check:
                order_to_check.append(wiz.order_id.id)
            if context.get('has_to_be_resourced'):
                line_ids.extend([l.id for l in wiz.order_id.order_line])

        po_so_ids, po_ids, so_ids, sol_nc_ids = po_obj.sourcing_document_state(cr, uid, order_to_check, context=context)

        # Mark lines as 'To be resourced'
        line_obj.write(cr, uid, line_ids, {'has_to_be_resourced': True}, context=context)

        po_obj.write(cr, uid, order_ids, {'canceled_end': True}, context=context)
        for order_id in order_ids:
            wf_service.trg_validate(uid, 'purchase.order', order_id, 'purchase_cancel', cr)

        if po_so_ids:
            order_to_cancel = []
            for so_id in po_so_ids:
                if so_obj._get_ready_to_cancel(cr, uid, so_id, context=context)[so_id]:
                    order_to_cancel.append(so_id)

            if order_to_cancel:
                context.update({
                    'from_po': True,
                    'po_ids': list(order_to_check),
                })
                return so_obj.open_cancel_wizard(cr, uid, po_so_ids, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_resource(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        context['has_to_be_resourced'] = True

        return self.cancel_po(cr, uid, ids, context=context)

purchase_order_cancel_wizard()


class res_partner(osv.osv):
    _inherit = 'res.partner'

    def address_multiple_get(self, cr, uid, ids, adr_pref=['default']):
        address_obj = self.pool.get('res.partner.address')
        address_ids = address_obj.search(cr, uid, [('partner_id', '=', ids)])
        address_rec = address_obj.read(cr, uid, address_ids, ['type'])
        res = {}
        for addr in address_rec:
            res.setdefault(addr['type'], [])
            res[addr['type']].append(addr['id'])
        if res:
            default_address = res.get('default', False)
        else:
            default_address = False
        result = {}
        for a in adr_pref:
            result[a] = res.get(a, default_address)

        return result

res_partner()


class res_partner_address(osv.osv):
    _inherit = 'res.partner.address'

    def _get_dummy(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for a_id in ids:
            res[a_id] = True

        return res

    def _src_address(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all the destination addresses of a partner or all default
        addresses if he hasn't destination addresses
        '''
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')
        res = []

        for arg in args:
            if arg[0] == 'dest_address':
                addr_type = 'delivery'
            elif arg[0] == 'inv_address':
                addr_type = 'invoice'

            if arg[2]:
                partner_id = arg[2]
            else:
                partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id
                if arg[1] == 'in':
                    partner_id = [partner_id]

            addr_ids = []
            if isinstance(partner_id, list):
                for partner in partner_id:
                    if not partner:
                        continue
                    addr_ids.extend(partner_obj.address_multiple_get(cr, uid, partner, [addr_type])[addr_type])

            else:
                addr_ids = partner_obj.address_multiple_get(cr, uid, partner_id, [addr_type])[addr_type]

            res.append(('id', 'in', list(i for i in addr_ids if i)))

        return res

    _columns = {
        'dest_address': fields.function(_get_dummy, fnct_search=_src_address, method=True,
                                           type='boolean', string='Dest. Address', store=False),
        'inv_address': fields.function(_get_dummy, fnct_search=_src_address, method=True,
                                           type='boolean', string='Invoice Address', store=False),
    }


res_partner_address()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
