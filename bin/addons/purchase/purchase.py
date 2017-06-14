# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time
from osv import osv, fields
import netsvc
from tools.translate import _
import decimal_precision as dp
from osv.orm import browse_record, browse_null
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
import logging
import pooler
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta
from mx.DateTime import Parser
from mx.DateTime import RelativeDateTime
from workflow.wkf_expr import _eval_expr


class purchase_order(osv.osv):
    _name = "purchase.order"
    _description = "Purchase Order"
    _order = "name desc"


    def _calc_amount(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = {}
        for order in self.browse(cr, uid, ids):
            res[order.id] = 0
            for oline in order.order_line:
                res[order.id] += oline.price_unit * oline.product_qty
        return res

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            val = val1 = 0.0
            cur = order.pricelist_id.currency_id
            for line in order.order_line:
                val1 += line.price_subtotal
                for c in self.pool.get('account.tax').compute_all(cr, uid, line.taxes_id, line.price_unit, line.product_qty, order.partner_address_id.id, line.product_id.id, order.partner_id)['taxes']:
                    val += c.get('amount', 0.0)
            res[order.id]['amount_tax']=cur_obj.round(cr, uid, cur.rounding, val)
            res[order.id]['amount_untaxed']=cur_obj.round(cr, uid, cur.rounding, val1)
            res[order.id]['amount_total']=res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

    def _set_minimum_planned_date(self, cr, uid, ids, name, value, arg, context=None):
        if not value: return False
        if type(ids)!=type([]):
            ids=[ids]
        for po in self.browse(cr, uid, ids, context=context):
            if po.order_line:
                cr.execute("""update purchase_order_line set
                        date_planned=%s
                    where
                        order_id=%s and
                        (date_planned=%s or date_planned<%s)""", (value,po.id,po.minimum_planned_date,value))
            cr.execute("""update purchase_order set
                    minimum_planned_date=%s where id=%s""", (value, po.id))
        return True

    def _minimum_planned_date(self, cr, uid, ids, field_name, arg, context=None):
        res={}
        purchase_obj=self.browse(cr, uid, ids, context=context)
        for purchase in purchase_obj:
            res[purchase.id] = False
            if purchase.order_line:
                min_date=purchase.order_line[0].date_planned
                for line in purchase.order_line:
                    if line.date_planned < min_date:
                        min_date=line.date_planned
                res[purchase.id]=min_date
        return res

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
                        inv_ids = inv_obj.search_exist(cursor, user, [('picking_id', '=', sp)])
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

    def _shipped_rate(self, cr, uid, ids, name, arg, context=None):
        if not ids: return {}
        res = {}
        for id in ids:
            res[id] = [0.0,0.0]
        cr.execute('''SELECT
                p.purchase_id,sum(m.product_qty), m.state
            FROM
                stock_move m
            LEFT JOIN
                stock_picking p on (p.id=m.picking_id)
            WHERE
                p.purchase_id IN %s GROUP BY m.state, p.purchase_id''',(tuple(ids),))
        for oid,nbr,state in cr.fetchall():
            if state=='cancel':
                continue
            if state=='done':
                res[oid][0] += nbr or 0.0
                res[oid][1] += nbr or 0.0
            else:
                res[oid][1] += nbr or 0.0
        for r in res:
            if not res[r][1]:
                res[r] = 0.0
            else:
                res[r] = 100.0 * res[r][0] / res[r][1]
        return res

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()

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
        """
        Compute the number of Purchase order lines in each purchase order.
        A split line is count as one line
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of purchase.order ID to compute
        :param field_name: Name of the field to compute
        :param args: Extra parameters
        :param context: Context of the call
        :return: A dictionnary with the purchase.order ID as keys and the number of Purchase
                 order lines for each of them as value
        """
        pol_obj = self.pool.get('sale.order.line')

        if context is None:
            context =  {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for order_id in ids:
            res[order_id] = pol_obj.search_count(cr, uid, [
                ('order_id', '=', order_id),
                ('is_line_split', '=', False),
            ], context=context)

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
                    sol_exist = sol_obj.search_exist(
                        cr, uid,
                        [('procurement_id', 'in', proc_ids)],
                        context=context)
                    res[po_data['id']]['po_from_ir'] = sol_exist
                    if sol_exist:
                        # po_from_fo
                        sol_exist = sol_obj.search_exist(
                            cr, uid,
                            [('procurement_id', 'in', proc_ids),
                             ('order_id.procurement_request', '=', False)],
                            context=context)
                    res[po_data['id']]['po_from_fo'] = sol_exist
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
        so_obj = self.pool.get('sale.order')
        for po in ids:
            res[po] = {
                'fnct_project_ref': '',
                'sourced_references': '',
            }

            so_ids = self.get_so_ids_from_po_ids(cr, uid, po, context=context)
            for so in so_obj.read(cr, uid, so_ids, ['client_order_ref', 'name'], context=context):
                if so['client_order_ref']:
                    if res[po]['fnct_project_ref']:
                        res[po]['fnct_project_ref'] += ' - '
                    res[po]['fnct_project_ref'] += so['client_order_ref']

                if res[po]['sourced_references']:
                    res[po]['sourced_references'] += ','
                res[po]['sourced_references'] += so['name']

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


    def _invoiced(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.read(cursor, user, ids, ['invoiced_rate'], context=context):
            invoiced = False
            if purchase['invoiced_rate'] == 100.00:
                invoiced = True
            res[purchase['id']] = invoiced
        return res

    def _src_customer_ref(self, cr, uid, obj, name, args, context=None):
        '''
        return a domain when user filter on the customer_ref field
        '''
        if not args:
            return []

        pol_obj = self.pool.get('purchase.order.line')
        so_obj = self.pool.get('sale.order')
        proc_obj = self.pool.get('procurement.order')

        po_ids = []
        for tu in args:
            if tu[1] == 'ilike' or tu[1] == 'not ilike' or tu[1] == '=' or tu[1] == '!=':
                so_ids = so_obj.search(cr, uid, [('client_order_ref', tu[1], tu[2])], context=context)
                proc_ids = proc_obj.search(cr, uid, [('sale_id', 'in', so_ids)], context=context)
                pol_ids = pol_obj.search(cr, uid, [('procurement_id', 'in', proc_ids)], context=context)
                po_ids = set()
                for pol in pol_obj.read(cr, uid, pol_ids, ['order_id'], context=context):
                    if pol.get('order_id'):
                        po_ids.add(pol['order_id'][0])
            else:
                raise osv.except_osv(_('Error'), _('Bad operator : You can only use \'=\', \'!=\', \'ilike\' or \'not ilike\' as operator'))

        return [('id', 'in', list(po_ids))]

    def _get_customer_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return a concatenation of the PO's customer references from the project (case of procurement request)
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        so_obj = self.pool.get('sale.order')
        for po_id in ids:
            res[po_id] = ""

            so_ids = self.get_so_ids_from_po_ids(cr, uid, po_id, context=context)
            for so in so_obj.read(cr, uid, so_ids, ['client_order_ref'], context=context):
                if so['client_order_ref']:
                    if res[po_id]:
                        res[po_id] += ';'
                    res[po_id] += so['client_order_ref']

        return res

    def _get_line_count(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of line(s) for the PO
        '''
        pol_obj = self.pool.get('purchase.order.line')

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}.fromkeys(ids, 0)
        line_number_by_order = {}

        lines = pol_obj.search(cr, uid, [('order_id', 'in', ids)], context=context)
        for l in pol_obj.read(cr, uid, lines, ['order_id', 'line_number'], context=context):
            line_number_by_order.setdefault(l['order_id'][0], set())
            line_number_by_order[l['order_id'][0]].add(l['line_number'])

        for po_id, ln in line_number_by_order.iteritems():
            res[po_id] = len(ln)

        return res


# FROM PUCHASE OVERRIDE

    STATE_SELECTION = [
        ('draft', 'Request for Quotation'),
        ('wait', 'Waiting'),
        ('confirmed', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('except_picking', 'Shipping Exception'),
        ('except_invoice', 'Invoice Exception'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ]


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
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),
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
        'partner_ref': fields.char('Supplier Reference', size=128),
        'product_id': fields.related('order_line', 'product_id', type='many2one', relation='product.product', string='Product'),
        'no_line': fields.function(_get_no_line, method=True, type='boolean', string='No line'),
        'active': fields.boolean('Active', readonly=True),
        'po_from_ir': fields.function(_po_from_x, method=True, type='boolean', string='Is PO from IR ?', multi='po_from_x'),
        'po_from_fo': fields.function(_po_from_x, method=True, type='boolean', string='Is PO from FO ?', multi='po_from_x'),
        'canceled_end': fields.boolean(string='Canceled End', readonly=True),
        'is_a_counterpart': fields.boolean('Counterpart?', help="This field is only for indicating that the order is a counterpart"),
        'po_updated_by_sync': fields.boolean('PO updated by sync', readonly=False),
        'origin': fields.text('Source Document', help="Reference of the document that generated this purchase order request."),
        # UF-2267: Store also the parent PO as reference in the sourced PO
        'parent_order_name': fields.many2one('purchase.order', string='Parent PO name', help='If the PO is created from a re-source FO, this field contains the relevant original PO name'),
        'project_ref': fields.char(size=256, string='Project Ref.'),
        'message_esc': fields.text(string='ESC Message'),
        'fnct_project_ref': fields.function(_get_project_ref, method=True, string='Project Ref.',
                                            type='char', size=256, store=False, multi='so_info'),
        'dest_partner_ids': fields.many2many('res.partner', 'res_partner_purchase_order_rel', 'purchase_order_id', 'partner_id', 'Customers'),  # uf-2223
        'dest_partner_names': fields.function(_get_dest_partner_names, type='char', size=256,  string='Customers', method=True),  # uf-2223
        'split_po': fields.boolean('Created by split PO', readonly=True),
        'sourced_references': fields.function(_get_project_ref, method=True, string='Sourced references', type='text', store=False, multi='so_info'),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'requested_date_in_past': fields.function(_get_requested_date_in_past, method=True, string='Requested date in past', type='boolean', store=False),
        'update_in_progress': fields.boolean(string='Update in progress', readonly=True),
        # US-1765: register the 1st call of wkf_confirm_trigger to prevent recursion error
        'po_confirmed': fields.boolean('PO', readonly=True),
        'customer_ref': fields.function(_get_customer_ref, fnct_search=_src_customer_ref, method=True, string='Customer Ref.', type='text', store=False),
        'line_count': fields.function(_get_line_count, method=True, type='integer', string="Line count", store=False),

        'date_approve':fields.date('Date Approved', readonly=1, select=True, help="Date on which purchase order has been approved"),
        'dest_address_id':fields.many2one('res.partner.address', 'Destination Address',
                                          states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]},
                                          help="Put an address if you want to deliver directly from the supplier to the customer." \
                                          "In this case, it will remove the warehouse link and set the customer location."
                                          ),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'location_id': fields.many2one('stock.location', 'Destination', required=True, domain=[('usage','<>','view')]),
        'pricelist_id':fields.many2one('product.pricelist', 'Pricelist', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)],'done':[('readonly',True)]}, help="The pricelist sets the currency used for this purchase order. It also computes the supplier price for the selected products/quantities."),
        'state': fields.selection(STATE_SELECTION, 'State', readonly=True, help="The state of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' state. Then the order has to be confirmed by the user, the state switch to 'Confirmed'. Then the supplier must confirm the order to change the state to 'Approved'. When the purchase order is paid and received, the state becomes 'Done'. If a cancel action occurs in the invoice or in the reception of goods, the state becomes in exception.", select=True),
        'validator' : fields.many2one('res.users', 'Validated by', readonly=True),
        'notes': fields.text('Notes'),
        'picking_ids': fields.one2many('stock.picking', 'purchase_id', 'Picking List', readonly=True, help="This is the list of picking list that have been generated for this purchase"),
        'shipped':fields.boolean('Received', readonly=True, select=True, help="It indicates that a picking has been done"),
        'shipped_rate': fields.function(_shipped_rate, method=True, string='Received', type='float'),
        'invoiced': fields.function(_invoiced, method=True, string='Invoiced', type='boolean', help="It indicates that an invoice has been generated"),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'minimum_planned_date':fields.function(_minimum_planned_date, fnct_inv=_set_minimum_planned_date, method=True, string='Expected Date', type='date', select=True, help="This is computed as the minimum scheduled date of all purchase order lines' products.",
                                               store = {
                                                   'purchase.order.line': (_get_order, ['date_planned'], 10),
                                               }
                                               ),
        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Purchase Price'), string='Untaxed Amount',
                                          store={
            'purchase.order.line': (_get_order, ['price_subtotal', 'taxes_id', 'price_unit', 'product_qty', 'product_id'], 10),
        }, multi="sums", help="The amount without tax"),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Purchase Price'), string='Taxes',
                                      store={
            'purchase.order.line': (_get_order, ['price_subtotal', 'taxes_id', 'price_unit', 'product_qty', 'product_id'], 10),
        }, multi="sums", help="The tax amount"),
        'amount_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Purchase Price'), string='Total',
                                        store={
            'purchase.order.line': (_get_order, ['price_subtotal', 'taxes_id', 'price_unit', 'product_qty', 'product_id'], 10),
        }, multi="sums",help="The total amount"),
        'fiscal_position': fields.many2one('account.fiscal.position', 'Fiscal Position'),
        'create_uid':  fields.many2one('res.users', 'Responsible'),
        'company_id': fields.many2one('res.company','Company',required=True,select=1),
    }
    _defaults = {
        'po_confirmed': lambda *a: False,
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: 'other',
        'loan_duration': 2,
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
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
        'shipped': 0,
        'invoiced': 0,
        'partner_address_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['default'])['default'],
        'pricelist_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').browse(cr, uid, context['partner_id']).property_product_pricelist_purchase.id,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'purchase.order', context=c),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique !'),
    ]

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
                    if self.pool.get('res.partner').read(cr, uid, vals.get('partner_id'), ['partner_type'], context=context)['partner_type'] == 'esc':
                        vals.update({'invoice_method': 'manual'})
            else:
                vals.update({'invoice_method': 'picking'})

        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)
        # we need to update the location_id because it is readonly and so does not pass in the vals of create and write
        vals = self._get_location_id(cr, uid, vals, warehouse_id=vals.get('warehouse_id', False), context=context)
        res = super(purchase_order, self).create(cr, uid, vals, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Check if the partner is correct.
        # UTP-114 demand purchase_list PO to be "from picking" as invoice_method
        '''
        if not ids:
            return True
        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)


        res_partner_obj = self.pool.get('res.partner')
        for order in self.read(cr, uid, ids, ['partner_id', 'warehouse_id'], context=context):
            partner_type = res_partner_obj.read(cr, uid, vals.get('partner_id', order['partner_id'][0]), ['partner_type'], context=context)['partner_type']
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
            vals = self._get_location_id(cr, uid, vals,  warehouse_id=vals.get('warehouse_id', order['warehouse_id'] and order['warehouse_id'][0] or False), context=context)
            # FIXME here it is useless to continue as the next loop will
            # overwrite vals
            break

        res = super(purchase_order, self).write(cr, uid, ids, vals, context=context)

        # Delete expected sale order line
        if 'state' in vals and vals.get('state') not in ('draft', 'confirmed'):
            exp_sol_ids = self.pool.get('expected.sale.order.line').search(cr,
                                                                           uid, [('po_id', 'in', ids)], order='NO_ORDER', context=context)
            self.pool.get('expected.sale.order.line').unlink(cr, uid, exp_sol_ids, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        if self.get_so_ids_from_po_ids(cr, uid, ids, context=context):
            raise osv.except_osv(_('Error'), _('You cannot remove a Purchase order that is linked to a Field Order or an Internal Request. Please cancel it instead.'))

        purchase_orders = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in purchase_orders:
            if s['state'] in ['draft','cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Purchase Order(s) which are in %s State!')  % _(dict(purchase_order.STATE_SELECTION).get(s['state'])))

        # TODO: temporary fix in 5.0, to remove in 5.2 when subflows support
        # automatically sending subflow.delete upon deletion
        wf_service = netsvc.LocalService("workflow")
        for id in unlink_ids:
            wf_service.trg_validate(uid, 'purchase.order', id, 'purchase_cancel', cr)
        # force removal on concurrency-check field from context because
        # system will raise an error if record was modified by workflow
        if context and unlink_ids:
            context.pop(self.CONCURRENCY_CHECK_FIELD, None)

        return super(purchase_order, self).unlink(cr, uid, unlink_ids, context=context)

    def _hook_copy_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        HOOK from purchase>purchase.py for COPY function. Modification of default copy values
        define which name value will be used
        '''
        return {'state':'draft',
                'shipped':False,
                'invoiced':False,
                'invoice_ids': [],
                'picking_ids': [],
                'name': self.pool.get('ir.sequence').get(cr, uid, 'purchase.order'),
                }


    def copy(self, cr, uid, p_id, default=None, context=None):
        '''
        Remove loan_id field on new purchase.order
        '''
        if not default:
            default = {}
        if context is None:
            context = {}

        update_values = self._hook_copy_name(cr, uid, [id], context=context, default=default)
        default.update(update_values)
        # if the copy comes from the button duplicate
        if context.get('from_button'):
            default.update({'is_a_counterpart': False})
        default.update({'loan_id': False, 'merged_line_ids': False, 'partner_ref': False, 'po_confirmed': False})
        if not context.get('keepOrigin', False):
            default.update({'origin': False})

        if not 'date_confirm' in default:
            default['date_confirm'] = False
        if not default.get('related_sourcing_id', False):
            default['related_sourcing_id'] = False

        return super(purchase_order, self).copy(cr, uid, p_id, default, context=context)

    def inv_line_create(self, cr, uid, a, ol):
        return (0, False, {
            'name': ol.name,
            'account_id': a,
            'price_unit': ol.price_unit or 0.0,
            'quantity': ol.product_qty,
            'product_id': ol.product_id.id or False,
            'uos_id': ol.product_uom.id or False,
            'invoice_line_tax_id': [(6, 0, [x.id for x in ol.taxes_id])],
            'account_analytic_id': ol.account_analytic_id.id or False,
        })

    def action_invoice_create(self, cr, uid, ids, *args):
        res = False

        for o in self.browse(cr, uid, ids):
            il = []
            todo = []
            for ol in o.order_line:
                todo.append(ol.id)
                if ol.product_id:
                    a = ol.product_id.product_tmpl_id.property_account_expense.id
                    if not a:
                        a = ol.product_id.categ_id.property_account_expense_categ.id
                    if not a:
                        raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (id:%d)') % (ol.product_id.name, ol.product_id.id,))
                else:
                    a = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category').id
                fpos = o.fiscal_position or False
                a = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, a)
                il.append(self.inv_line_create(cr, uid, a, ol))

            a = o.partner_id.property_account_payable.id

            # US-268: Pick the correct journal of the current instance, could have many same journal but for different instances
            journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)])
            if not journal_ids:
                raise osv.except_osv(_('Error !'),
                                     _('There is no purchase journal defined for this company: "%s" (id:%d)') % (o.company_id.name, o.company_id.id))
            inv = {
                'name': o.partner_ref or o.name,
                'reference': o.partner_ref or o.name,
                'account_id': a,
                'type': 'in_invoice',
                'partner_id': o.partner_id.id,
                'currency_id': o.pricelist_id.currency_id.id,
                'address_invoice_id': o.partner_address_id.id,
                'address_contact_id': o.partner_address_id.id,
                'journal_id': len(journal_ids) and journal_ids[0] or False,
                'origin': o.name,
                'invoice_line': il,
                'fiscal_position': o.fiscal_position.id or o.partner_id.property_account_position.id,
                'payment_term': o.partner_id.property_payment_term and o.partner_id.property_payment_term.id or False,
                'company_id': o.company_id.id,
            }
            if o.order_type == 'purchase_list':
                inv['purchase_list'] = 1
            elif o.order_type == 'in_kind':
                inkind_journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'inkind'), ('is_current_instance', '=', True)])
                if not inkind_journal_ids:
                    raise osv.except_osv(_('Error'), _('No In-kind Donation journal found!'))
                inv['journal_id'] = inkind_journal_ids[0]
                inv['is_inkind_donation'] = True

            inv_id = self.pool.get('account.invoice').create(cr, uid, inv, {'type':'in_invoice', 'journal_type': 'purchase'})
            self.pool.get('account.invoice').button_compute(cr, uid, [inv_id], {'type':'in_invoice'}, set_total=True)
            self.pool.get('purchase.order.line').write(cr, uid, todo, {'invoiced':True})
            self.write(cr, uid, [o.id], {'invoice_ids': [(4, inv_id)]})
            res = inv_id
        return res

    def button_dummy(self, cr, uid, ids, context=None):
        return True

    def onchange_dest_address_id(self, cr, uid, ids, adr_id):
        if not adr_id:
            return {}
        values = {'warehouse_id': False}
        part_id = self.pool.get('res.partner.address').browse(cr, uid, adr_id).partner_id
        if part_id:
            loc_id = part_id.property_stock_customer.id
            values.update({'location_id': loc_id})
        return {'value':values}


    def _hook_o_line_value(self, cr, uid, *args, **kwargs):
        o_line = super(purchase_order, self)._hook_o_line_value(cr, uid, *args, **kwargs)
        order_line = kwargs['order_line']

        # Copy all fields except order_id and analytic_distribution_id
        fields = ['product_uom', 'price_unit', 'move_dest_id', 'product_qty', 'partner_id',
                  'confirmed_delivery_date', 'nomenclature_description', 'default_code',
                  'nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3',
                  'nomenclature_code', 'name', 'default_name', 'comment', 'date_planned',
                  'to_correct_ok', 'text_error', 'select_fo', 'project_ref', 'external_ref',
                  'nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4',
                  'nomen_sub_5', 'procurement_id', 'change_price_manually', 'old_price_unit',
                  'origin', 'account_analytic_id', 'product_id', 'company_id', 'notes', 'taxes_id',
                  'link_so_id', 'from_fo', 'sale_order_line_id', 'tender_line_id', 'dest_partner_id']

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

    def do_merge(self, cr, uid, ids, context=None):
        """
        To merge similar type of purchase orders.
        Orders will only be merged if:
        * Purchase Orders are in draft
        * Purchase Orders belong to the same partner
        * Purchase Orders are have same stock location, same pricelist
        Lines will only be merged if:
        * Order lines are exactly the same except for the quantity and unit

         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param ids: the ID or list of IDs
         @param context: A standard dictionary

         @return: new purchase order id

        """
        line_obj = self.pool.get('purchase.order.line')
        wf_service = netsvc.LocalService("workflow")
        def make_key(br, fields):
            list_key = []
            for field in fields:
                field_val = getattr(br, field)
                if field in ('product_id', 'move_dest_id', 'account_analytic_id'):
                    if not field_val:
                        field_val = False
                if isinstance(field_val, browse_record):
                    field_val = field_val.id
                elif isinstance(field_val, browse_null):
                    field_val = False
                elif isinstance(field_val, list):
                    field_val = ((6, 0, tuple([v.id for v in field_val])),)
                list_key.append((field, field_val))
            list_key.sort()
            return tuple(list_key)

    # compute what the new orders should contain

        new_orders = {}

        for porder in [order for order in self.browse(cr, uid, ids, context=context) if order.state == 'draft']:
            order_key = make_key(porder, ('partner_id', 'pricelist_id', 'loan_id'))
            new_order = new_orders.setdefault(order_key, ({}, []))
            new_order[1].append(porder.id)
            order_infos = new_order[0]
            if not order_infos:
                order_infos.update({
                    'origin': porder.origin,
                    'date_order': time.strftime('%Y-%m-%d'),
                    'partner_id': porder.partner_id.id,
                    'partner_address_id': porder.partner_address_id.id,
                    'dest_address_id': porder.dest_address_id.id,
                    'warehouse_id': porder.warehouse_id.id,
                    'location_id': porder.location_id.id,
                    'pricelist_id': porder.pricelist_id.id,
                    'state': 'draft',
                    'order_line': {},
                    'notes': '%s' % (porder.notes or '',),
                    'fiscal_position': porder.fiscal_position and porder.fiscal_position.id or False,
                })
            else:
                if porder.notes:
                    order_infos['notes'] = (order_infos['notes'] or '') + ('\n%s' % (porder.notes,))
                if porder.origin:
                    order_infos['origin'] = (order_infos['origin'] or '') + ' ' + porder.origin
            order_infos = self._hook_order_infos(cr, uid, order_infos=order_infos, order_id=porder)

            no_proc_ids = []
            for order_line in porder.order_line:
                line_key = make_key(order_line, ('id', 'order_id', 'name', 'date_planned', 'taxes_id', 'price_unit', 'notes', 'product_id', 'move_dest_id', 'account_analytic_id'))
                o_line = order_infos['order_line'].setdefault(line_key, {})
                if o_line:
                    o_line = self._hook_o_line_value(cr, uid, o_line=o_line, order_line=order_line)
                    # merge the line with an existing line
                    o_line['product_qty'] += order_line.product_qty * order_line.product_uom.factor / o_line['uom_factor']
                else:
                    # append a new "standalone" line
                    for field in ('product_qty', 'product_uom'):
                        field_val = getattr(order_line, field)
                        if isinstance(field_val, browse_record):
                            field_val = field_val.id
                        o_line[field] = field_val
                    o_line['uom_factor'] = order_line.product_uom and order_line.product_uom.factor or 1.0
                    o_line = self._hook_o_line_value(cr, uid, o_line=o_line, order_line=order_line)
                if order_line.procurement_id:
                    no_proc_ids.append(order_line.id)

            if no_proc_ids:
                line_obj.write(cr, uid, no_proc_ids, {'procurement_id': False}, context=context)

        allorders = []
        orders_info = {}
        for order_key, (order_data, old_ids) in new_orders.iteritems():
            # skip merges with only one order
            if len(old_ids) < 2:
                allorders += (old_ids or [])
                continue

            # cleanup order line data
            for key, value in order_data['order_line'].iteritems():
                del value['uom_factor']
                value.update(dict(key))
            order_data['order_line'] = [(0, 0, value) for value in order_data['order_line'].itervalues()]

            # create the new order
            neworder_id = self.create(cr, uid, order_data)
            orders_info.update({neworder_id: old_ids})
            allorders.append(neworder_id)

            # make triggers pointing to the old orders point to the new order
            for old_id in old_ids:
                wf_service.trg_redirect(uid, 'purchase.order', old_id, neworder_id, cr)
                wf_service.trg_validate(uid, 'purchase.order', old_id, 'purchase_cancel', cr)
        return orders_info

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
        for po in self.read(cr, uid, ids, ['order_line'], context=context):
            for l in po['order_line']:
                if line_obj.get_sol_ids_from_pol_ids(cr, uid, [l], context=context):
                    wiz_id = wiz_obj.create(cr, uid, {
                        'order_id': po['id'],
                        'last_lines': wiz_obj._get_last_lines(cr, uid, po['id'], context=context),
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
                    exp_sol_ids = exp_sol_obj.search(cr, uid, [('po_id', '=', po['id'])], context=context)
                    for exp in exp_sol_obj.browse(cr, uid, exp_sol_ids, context=context):
                        if not exp.order_id.order_line:
                            so_to_cancel_ids.add(exp.order_id.id)

            wf_service.trg_validate(uid, 'purchase.order', po['id'], 'purchase_cancel', cr)

        # Ask user to choose what must be done on the FO/IR
        if so_to_cancel_ids:
            context.update({
                'from_po': True,
                'po_ids': list(ids),
            })
            return so_obj.open_cancel_wizard(cr, uid, so_to_cancel_ids, context=context)


        return True

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check restriction on products
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('purchase.order.line')
        res = True

        for order in self.read(cr, uid, ids, ['order_line'], context=context):
            res = res and line_obj._check_restriction_line(cr, uid, order['order_line'], context=context)

        return res

    def _check_user_company(self, cr, uid, company_id, context=None):
        '''
        Remove the possibility to make a PO to user's company
        '''
        user_company_id = self.pool.get('res.users').read(cr, uid, uid, ['company_id'], context=context)['company_id'][0]
        if company_id == user_company_id:
            raise osv.except_osv(_('Error'), _('You cannot made a purchase order to your own company !'))

        return True


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

        # check if the current PO was created from scratch :
        proc_obj = self.pool.get('procurement.order')
        if order_type == 'direct':
            if not proc_obj.search_exist(cr, uid, [('purchase_id', 'in', ids)]):
                return {
                    'value': {'order_type': 'regular'},
                    'warning': {
                        'title': _('Error'),
                        'message': _('You cannot create a direct purchase order from scratch')
                    },
                }

        # Search the local market partner id
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj.search(cr, uid,
                                  [('module', '=', 'order_types'),
                                   ('model', '=', 'res.partner'),
                                      ('name', '=', 'res_partner_local_market')],
                                  limit=1, order='NO_ORDER')
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
            partner = partner_obj.read(cr, uid, partner_id, ['partner_type'])
            if partner['partner_type'] in ('internal', 'esc') and order_type in ('regular', 'direct'):
                v['invoice_method'] = 'manual'
            elif partner['partner_type'] not in ('external', 'esc') and order_type == 'direct':
                v.update({'partner_address_id': False, 'partner_id': False, 'pricelist_id': False,})
                w.update({'message': 'You cannot have a Direct Purchase Order with a partner which is not external or an ESC',
                          'title': 'An error has occurred !'})
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

        if not part:
            return  {'value':{'partner_address_id': False, 'fiscal_position': False}}

        addr = self.pool.get('res.partner').address_get(cr, uid, [part], ['default'])
        part = self.pool.get('res.partner').browse(cr, uid, part)
        pricelist = part.property_product_pricelist_purchase.id
        fiscal_position = part.property_account_position and part.property_account_position.id or False
        res = {'value':{'partner_address_id': addr['default'], 'pricelist_id': pricelist, 'fiscal_position': fiscal_position}}


        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        partner = partner_obj.read(cr, uid, part.id, ['partner_type'])
        if ids:
            # Check the restrction of product in lines
            for order in self.browse(cr, uid, ids):
                for line in order.order_line:
                    if line.product_id:
                        res, test = product_obj._on_change_restriction_error(cr, uid, line.product_id.id, field_name='partner_id', values=res, vals={'partner_id': part})
                        if test:
                            res.setdefault('value', {}).update({'partner_address_id': False})
                            return res
        if partner['partner_type'] in ('internal', 'esc'):
            res['value']['invoice_method'] = 'manual'
        elif ids and partner['partner_type'] == 'intermission':
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

    def onchange_warehouse_id(self, cr, uid, ids,  warehouse_id, order_type, dest_address_id):
        '''
        Change the destination address to the destination address of the company if False
        '''
        res = {}
        if not warehouse_id:
            wh_info = self.pool.get('stock.warehouse').read(cr, uid, [warehouse_id], ['lot_input_id'])
            res = {'value':{'location_id': wh_info[0]['lot_input_id'][0], 'dest_address_id': False, 'cross_docking_ok': False}}

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
                    todo2 = sale_line_obj.search(cr, uid, [('procurement_id', 'in', todo)], order='NO_ORDER', context=context)

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
                if data['order_id'][0] not in so_ids:
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
        # sale order lines list
        sol_ids = []

        pol_obj = self.pool.get('purchase.order.line')
        order_lines = set()
        for po in self.read(cr, uid, ids, ['order_line'], context=context):
            for line in po['order_line']:
                order_lines.add(line)

        proc_ids = set()
        result = pol_obj.read(cr, uid, list(order_lines), ['procurement_id'],
                              context=context)
        result = dict([(x['id'], x['procurement_id'][0]) for x in result if x['procurement_id']])
        if result:
            for line_id, procurement_id in result.items():
                proc_ids.add(procurement_id)

        # get the corresponding sale order line list
        if proc_ids:
            sol_ids = sol_obj.search(cr, uid, [('procurement_id', 'in',
                                                list(proc_ids))], context=context)
        return sol_ids


    def create_extra_lines_on_fo(self, cr, uid, ids, context=None):
        '''
        Creates FO/IR lines according to PO extra lines
        '''
        # Objects
        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        ad_obj = self.pool.get('analytic.distribution')
        ccl_obj = self.pool.get('cost.center.distribution.line')
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

            # Make check on partner_type of the AD cost center lines
            ccl_ids = ccl_obj.search(cr, uid, [
                ('distribution_id', '=', new_distrib),
                ('partner_type', '!=', l.link_so_id.partner_type)
            ], context=context)
            if ccl_ids:
                ccl_obj.write(cr, uid, ccl_ids, {'partner_type': l.link_so_id.partner_type}, context=context)

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
                self.infolog(cr, uid, "The FO/IR line id:%s (line number: %s) has been added from the PO line id:%s (line number: %s)" % (
                    sol_id, sol_obj.read(cr, uid, sol_id, ['line_number'], context=context)['line_number'],
                    l.id, l.line_number,
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
            self.infolog(cr, uid, "The FO/IR line id:%s (line number: %s) has been added from the PO line id:%s (line number: %s)" % (
                new_line_id, sol_obj.read(cr, uid, new_line_id, ['line_number'], context=context)['line_number'],
                l.id, l.line_number,
            ))

        if sol_ids:
            so_obj.action_ship_proc_create(cr, uid, list(sol_ids), context=context)

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
        data_obj = self.pool.get('ir.model.data')
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        wf_service = netsvc.LocalService("workflow")

        tbd_product_id = data_obj.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]

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
                move_to_delete = []
                sol_ids = pol_obj.get_sol_ids_from_pol_ids(cr, uid, [line.id], context=context)
                if sol_ids:
                    store_to_call += sol_ids


                    sol = sol_obj.browse(cr, uid, sol_ids[0], context=context)
                    so = sol.order_id
                    # US-1931: Remove code that do not update Internal Requests with internal requestor location

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
                        for opl in pol_obj.read(cr, uid, other_po_lines, ['sync_order_line_db_id', 'product_uom', 'product_qty'], context=context):
                            # Check if the other PO line will not be canceled
                            socl_ids = socl_obj.search(cr, uid, [
                                ('sync_order_line_db_id', '=', opl['sync_order_line_db_id']),
                            ], limit=1, order='NO_ORDER', context=context)
                            if socl_ids:
                                continue

                            if opl['product_uom'][0] != line.product_uom.id:
                                line_qty += uom_obj._compute_qty(cr, uid, opl['product_uom'][0], opl['product_qty'], line.product_uom.id)
                            else:
                                line_qty += opl['product_qty']

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

                    cond2 = not sol.product_id or sol.product_id.id != line.procurement_id.product_id.id
                    cond1 = so.procurement_request and so.location_requestor_id.usage == 'customer'
                    cond3 = bool(line.procurement_id.move_id and not line.procurement_id.move_id.processed_stock_move)

                    if cond2 and line.product_id:
                        proc_obj.write(cr, uid, [line.procurement_id.id], {'product_id': line.product_id.id})

                    if (cond1 or (not so.procurement_request and cond2)) and cond3:

                        # In case of FO with not only no product lines, the picking tickes will be created with normal flow
                        if not so.procurement_request and cond2:
                            if sol_obj.search_exist(cr, uid, [('order_id', '=', so.id),
                                                              ('id', '!=', sol.id)],
                                                    context=context):
                                continue

                        cond4 = line.product_id.id != line.procurement_id.product_id.id
                        cond5 = line.procurement_id.product_id.type in ('service', 'service_recep', 'consu')
                        cond6 = line.procurement_id.product_id.id == tbd_product_id
                        cond7 = line.product_id.type == 'product'
                        # In case of replacement of a non-stockable product by a stockable product or replacement of To be Defined product
                        if cond4 and (cond5 or cond6) and cond7 and so.procurement_request:
                            # Get OUT linked to IR or PICK linked to FO
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
                                if so.procurement_request:
                                    pick_to_confirm = out_ids

                            sol = sol_obj.browse(cr, uid, sol.id, context=context)
                            move_data = so_obj._get_move_data(cr, uid, so, sol, out_ids[0], context=context)
                            new_move_id = move_obj.create(cr, uid, move_data, context=context)
                            out_move_id = line.procurement_id.move_id.id
                            proc_obj.write(cr, uid, [line.procurement_id.id], {'move_id': new_move_id, 'product_id': sol.product_id.id}, context=context)
                            move_to_delete.append(out_move_id)

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
                            if out_pick_id:
                                move_obj.write(cr, uid, [out_move_id.id], {'state': 'draft'})
                                picks_to_check.setdefault(out_pick_id, [])
                                picks_to_check[out_pick_id].append(out_move_id.id)
                            else:
                                move_to_delete.append(out_move_id.id)

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

                        for sp_move in move_obj.read(cr, uid, sp_moves, ['product_uom', 'product_qty'], context=context):
                            if sp_move['product_uom'][0] != out_move_id.product_uom.id:
                                minus_qty += uom_obj._compute_qty(cr, uid, bom.product_uom.id, bom.product_qty, out_move_id.product_uom.id)
                            else:
                                minus_qty += sp_move['product_qty']

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
                move_obj.unlink(cr, uid, move_to_delete, context=context, force=True)

            if store_to_call:
                sol_obj._call_store_function(cr, uid, store_to_call, keys=None, bypass=False, context=context)
            # compute so dates -- only if we get a confirmed value, because rts is mandatory on So side
            # update after lines update, as so write triggers So workflow, and we dont want the Out document
            # to be created with old So datas
            if po.delivery_confirmed_date:
                for so in so_obj.read(cr, uid, so_ids, ['est_transport_lead_time'], context=context):
                    # Fo rts = Po confirmed date + prep_lt
                    delivery_confirmed_date = datetime.strptime(po.delivery_confirmed_date, db_date_format)
                    so_rts = delivery_confirmed_date + relativedelta(days=prep_lt or 0)
                    so_rts = so_rts.strftime(db_date_format)

                    # Fo confirmed date = confirmed date + prep_lt + ship_lt + transport_lt
                    so_confirmed = self.compute_confirmed_delivery_date(cr, uid, ids, po.delivery_confirmed_date,
                                                                        prep_lt, ship_lt, so['est_transport_lead_time'],
                                                                        db_date_format, context=context)
                    # write data to so
                    so_obj.write(cr, uid, [so['id']], {'delivery_confirmed_date': so_confirmed,
                                                       'ready_to_ship_date': so_rts}, context=context)
                    wf_service.trg_write(uid, 'sale.order', so['id'], cr)

        move_to_delete = set()
        pick_id_to_delete = set()
        for out_pick_id, out_move_ids in picks_to_check.iteritems():
            full_out = pick_obj.read(cr, uid, out_pick_id, ['move_lines'])['move_lines']
            for om_id in out_move_ids:
                if om_id in full_out:
                    full_out.remove(om_id)

            if out_pick_id and not full_out:
                pick_id_to_delete.add(out_pick_id)
            move_to_delete.update(out_move_ids)
        if pick_id_to_delete:
            pick_obj.write(cr, uid, list(pick_id_to_delete), {'state': 'draft'}, context=context)
            pick_obj.unlink(cr, uid, list(pick_id_to_delete))
        if move_to_delete:
            move_obj.unlink(cr, uid, list(move_to_delete), context=context, force=True)
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
            if exp_sol_obj.search_exist(cr, uid,
                                        [('order_id', 'in', all_so_ids)], context=context):
                return False

            if sol_obj.search_exist(cr, uid,
                                    [('order_id', 'in', all_so_ids),
                                     ('type', '=', 'make_to_order'),
                                        #('product_id', '!=', False),
                                        ('procurement_id.state', '!=', 'cancel'),
                                        ('order_id.procurement_request', '=', False),
                                        ('state', 'not in', ['confirmed', 'done'])],
                                    context=context):
                return False

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
                                               'confirmed_delivery_date': loan_duration.strftime('%Y-%m-%d'),
                                               'delay': 60.0,
                                               'name': line.name,
                                               'type': line.product_id.procure_method})
            self.write(cr, uid, [order.id], {'loan_id': order_id})

            sale = sale_obj.read(cr, uid, order_id, ['name'])
            message = _("Loan counterpart '%s' has been created and validated. Please confirm it.") % (sale['name'],)

            sale_obj.log(cr, uid, order_id, message)

        return order_id

    def has_stockable_product(self,cr, uid, ids, *args):
        '''
        Override the has_stockable_product to return False
        when the order_type of the order is 'direct'
        '''

        # TODO: See with Synchro team which object the system will should create
        # to have an Incoming Movement in the destination instance
        for order in self.read(cr, uid, ids, ['order_type']):
            if order['order_type'] != 'direct':
                for order in self.browse(cr, uid, ids):
                    for order_line in order.order_line:
                        if order_line.product_id and order_line.product_id.product_tmpl_id.type in ('product', 'consu'):
                            return True
        return False

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
            elif order.order_type == 'loan':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
            elif order.order_type == 'donation_st':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
            elif order.order_type == 'donation_exp':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
            elif order.order_type == 'in_kind':
                reason_type_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_in_kind_donation')[1]

            if reason_type_id:
                picking_values.update({'reason_type_id': reason_type_id})

            # US-917: Check if any IN exists for the given PO
            pick_obj = self.pool.get('stock.picking')
            if pick_obj.search_exist(cr, uid, [('purchase_id', 'in', [order.id])], context=context):
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
                    'name': ''.join((order.name, ': ', (order_line.name or ''))),
                    'product_id': order_line.product_id.id,
                    'product_qty': order_line.product_qty,
                    'product_uos_qty': order_line.product_qty,
                    'product_uom': order_line.product_uom.id,
                    'product_uos': order_line.product_uom.id,
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
                    'comment': order_line.comment or '',
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
                for null, store_object, store_ids, store_fields2 in compute_store:
                    if store_fields2 in ('dpo_incoming', 'dpo_out', 'overall_qty', 'line_state') and not (store_object, store_ids, store_fields2) in done:
                        self.pool.get(store_object)._store_set_values(cr, uid, store_ids, store_fields2, context)
                        done.append((store_object, store_ids, store_fields2))
            if moves_to_update:
                move_obj.write(cr, uid, moves_to_update, {'location_id':order.location_id.id})
            move_obj.confirm_and_force_assign(cr, uid, todo_moves)
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id

    def _get_location_id(self, cr, uid, vals, warehouse_id=False, context=None):
        """
        Get the location_id according to the cross_docking_ok option
        Return vals
        """
        if 'cross_docking_ok' not in vals:
            return vals

        stock_warehouse_obj = self.pool.get('stock.warehouse')
        if not warehouse_id:
            warehouse_id = stock_warehouse_obj.search(cr, uid, [], context=context)[0]

        if isinstance(warehouse_id, str):
            try:
                warehouse_id = int(warehouse_id)
            except ValueError:
                raise osv.except_osv(
                    _('Error'),
                    _('The field \'warehouse_id\' is a float field but value is a string - Please contact your administrator'),
                )

        if not vals.get('cross_docking_ok', False):
            vals.update({'location_id': stock_warehouse_obj.read(cr, uid, warehouse_id, ['lot_input_id'], context=context)['lot_input_id'][0]})
        elif vals.get('cross_docking_ok', False):
            vals.update({'location_id': self.pool.get('stock.location').get_cross_docking_location(cr, uid)})

        return vals

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
            cr.close(True)

        return True

#CTRL
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
        ], order='NO_ORDER', context=context)
        line_obj.unlink(cr, uid, no_price_line_ids, context=context)

        data = self.read(cr, uid, new_po_id, ['name'], context=context)
        # log message describing the previous action
        self.log(cr, uid, new_po_id, _('The Purchase Order %s has been generated from Request for Quotation.')%data['name'])
        # close the current po
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'purchase.order', ids[0], 'rfq_done', cr)

        return new_po_id
purchase_order()


class stock_invoice_onshipping(osv.osv_memory):
    _inherit = "stock.invoice.onshipping"

    def create_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        res = super(stock_invoice_onshipping,self).create_invoice(cr, uid, ids, context=context)
        purchase_obj = self.pool.get('purchase.order')
        picking_obj = self.pool.get('stock.picking')
        for pick_id in res:
            pick = picking_obj.browse(cr, uid, pick_id, context=context)
            if pick.purchase_id:
                purchase_obj.write(cr, uid, [pick.purchase_id.id], {
                    'invoice_ids': [(4, res[pick_id])]}, context=context)
        return res

stock_invoice_onshipping()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
