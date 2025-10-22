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
from tools.misc import _get_header_msl_mml_alert
import decimal_precision as dp
from osv.orm import browse_record, browse_null
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
import logging
import pooler
import json
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta
from . import PURCHASE_ORDER_STATE_SELECTION
from tender_flow import RFQ_STATE_SELECTION
from . import ORDER_TYPES_SELECTION
from account_override.period import get_period_from_date
from msf_order_date.order_dates import common_create, get_type, common_requested_date_change, common_onchange_transport_lt, common_onchange_date_order, common_onchange_transport_type, common_onchange_partner_id
from msf_partner import PARTNER_TYPE
from msf_order_date import TRANSPORT_TYPE
from msf_order_date import ZONE_SELECTION
from sourcing.purchase_order import COMPATS

class purchase_order(osv.osv):
    _name = "purchase.order"
    _description = "Purchase Order"
    _order = "id desc"

    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        '''
            overwrite to allow search on customer and self instance

        '''
        new_dom = []
        dest_partner_names = False
        product_id = False
        for x in domain:
            if x[0] == 'dest_partner_names':
                dest_partner_names = x[2]
            elif x[0] == 'product_id':
                product_id = x[2]
            else:
                new_dom.append(x)

        ret = super(purchase_order, self)._where_calc(cr, uid, new_dom, active_test=active_test, context=context)
        if dest_partner_names:
            ret.tables.append('"res_partner_purchase_order_rel"')
            ret.joins['"purchase_order"'] = [('"res_partner_purchase_order_rel"', 'id', 'purchase_order_id', 'LEFT JOIN')]
            ret.tables.append('"res_partner"')
            ret.joins['"res_partner_purchase_order_rel"'] = [('"res_partner"', 'partner_id', 'id', 'LEFT JOIN')]
            if self.pool.get('sync.client.entity').search_exist(cr, uid, [('name', 'ilike', dest_partner_names)], context=context):
                ret.where_clause.append(' ("res_partner"."name" ilike %s OR "res_partner_purchase_order_rel".partner_id IS NULL) ')
            else:
                ret.where_clause.append(' "res_partner"."name" ilike %s ')
            ret.where_clause_params.append('%%%s%%'%dest_partner_names)
            ret.having_group_by = ' GROUP BY "purchase_order"."id" '
        if product_id and isinstance(product_id, int):
            ret.tables.append('"purchase_order_line"')
            ret.joins.setdefault('"purchase_order"', [])
            ret.joins['"purchase_order"'] += [('"purchase_order_line"', 'id', 'order_id', 'LEFT JOIN')]
            ret.where_clause.append(''' "purchase_order_line"."product_id" = %s  ''')
            ret.where_clause_params.append(product_id)
        return ret

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        cur_obj = self.pool.get('res.currency')
        pol_obj = self.pool.get('purchase.order.line')
        tax_obj = self.pool.get('account.tax')
        for order in self.browse(cr, uid, ids, fields_to_fetch=['pricelist_id', 'partner_address_id', 'partner_id', 'tender_id'], context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
                'amount_total_tender_currency': 0.0,
                'has_tax_at_line_level': False,
            }
            amount_tax = 0
            amount_untaxed = 0
            cur = order.pricelist_id.currency_id

            cr.execute("""select exists(
                select pol.id from purchase_order_line pol, purchase_order_taxe t
                where
                    t.ord_id = pol.id and pol.state not in ('cancel', 'cancel_r') and pol.order_id = %s)""", (order.id, ))
            res[order.id]['has_tax_at_line_level'] = cr.fetchone()[0]

            if not res[order.id]['has_tax_at_line_level']:
                cr.execute("select sum(price_unit * product_qty) from purchase_order_line where order_id = %s and state not in ('cancel', 'cancel_r')", (order.id, ))
                amount_untaxed = cr.fetchone()[0] or 0

                cr.execute("select sum(amount) from account_invoice_tax where purchase_id = %s", (order.id, ))
                amount_tax = cr.fetchone()[0] or 0

            else:
                cr.execute("select pol.id from purchase_order_line pol where pol.state not in ('cancel', 'cancel_r') and pol.order_id = %s", (order.id, ))
                pol_ids = [x[0] for x in cr.fetchall()]
                max_size = 400
                offset = 0
                while offset < len(pol_ids):
                    for line in pol_obj.browse(cr, uid, pol_ids[offset:max_size+offset], fields_to_fetch=['taxes_id', 'price_unit', 'product_qty', 'product_id'], context=context):
                        tax_data = tax_obj.compute_all(cr, uid, line.taxes_id, line.price_unit, line.product_qty, order.partner_address_id.id, line.product_id.id, order.partner_id)
                        amount_untaxed += tax_data.get('total', 0)
                        for c in tax_data['taxes']:
                            amount_tax += c.get('amount', 0.0)
                        offset += max_size

            res[order.id]['amount_tax'] = cur_obj.round(cr, uid, cur.rounding, amount_tax)
            res[order.id]['amount_untaxed'] = cur_obj.round(cr, uid, cur.rounding, amount_untaxed)
            res[order.id]['amount_total'] = res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']

            if order.tender_id and order.tender_id.currency_id \
                    and order.tender_id.currency_id.id != order.pricelist_id.currency_id.id:
                res[order.id]['amount_total_tender_currency'] = round(cur_obj.compute(cr, uid, cur.id, order.tender_id.currency_id.id,
                                                                                      res[order.id]['amount_total'], round=False, context=context), 2)
            else:
                res[order.id]['amount_total_tender_currency'] = res[order.id]['amount_total']
        return res

    def _set_minimum_planned_date(self, cr, uid, ids, name, value, arg, context=None):
        if not value: return False
        if type(ids) != type([]):
            ids = [ids]
        for po in self.browse(cr, uid, ids, context=context):
            if po.order_line:
                cr.execute("""update purchase_order_line set
                        date_planned=%s
                    where
                        order_id=%s and
                        (date_planned=%s or date_planned<%s)""", (value, po.id, po.minimum_planned_date, value))
            cr.execute("""update purchase_order set
                    minimum_planned_date=%s where id=%s""", (value, po.id))
        return True

    def _minimum_planned_date(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        purchase_obj = self.browse(cr, uid, ids, context=context)
        for purchase in purchase_obj:
            res[purchase.id] = False
            if purchase.order_line:
                min_date = purchase.order_line[0].date_planned
                for line in purchase.order_line:
                    if line.date_planned < min_date:
                        min_date = line.date_planned
                res[purchase.id] = min_date
        return res

    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        sp_obj = self.pool.get('stock.picking')
        inv_obj = self.pool.get('account.invoice')
        for purchase in self.browse(cursor, user, ids, context=context):
            if ((purchase.order_type == 'regular' and purchase.partner_id.partner_type in ('internal', 'esc')) or \
                    purchase.order_type in ['donation_exp', 'donation_st', 'loan', 'loan_return', 'in_kind']):
                res[purchase.id] = purchase.shipped_rate
            else:
                # if all PO lines have been invoiced and the SI aren't in Draft anymore: invoiced rate must be 100%
                # (event if some SI amounts have been lowered)
                po_states = ['done']
                if purchase.order_type == 'direct' and purchase.po_version == 1:  # DPO v1 use case: CV and SI are both created at DPO confirmation
                    po_states = ['confirmed', 'confirmed_p', 'done']
                if purchase.state in po_states and all(x.state != 'draft' for x in purchase.invoice_ids):
                    res[purchase.id] = 100.0
                    continue
                tot = 0.0
                # UTP-808: Deleted invoices amount should be taken in this process. So what we do:
                # 1/ Take all closed stock picking linked to the purchase
                # 2/ Search invoices linked to these stock picking
                # 3/ Take stock picking not linked to an invoice
                # 4/ Use these non-invoiced closed stock picking to add their amount to the "invoiced" amount
                for invoice in purchase.invoice_ids:
                    if invoice.state not in ('draft', 'cancel'):
                        tot += invoice.amount_untaxed
                stock_pickings = sp_obj.search(cursor, user, [('purchase_id', '=', purchase.id), ('state', '=', 'done')])
                if stock_pickings:
                    sp_ids = list(stock_pickings)
                    if isinstance(stock_pickings, int):
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
        uom_obj = self.pool.get('product.uom')
        if not ids: return {}
        res = {}

        for order in self.browse(cr, uid, ids, context=context):
            # Direct PO v1 is 100.00% received when a user confirm the reception at customer side
            if order.po_version == 1 and order.order_type == 'direct' and order.state == 'done':
                res[order.id] = 100.00
                continue
            elif order.po_version == 1 and order.order_type == 'direct' and order.state != 'done':
                res[order.id] = 0.00
                continue
            res[order.id] = 0.00
            amount_total = 0.00
            amount_received = 0.00
            for line in order.order_line:
                if line.state in ['cancel', 'cancel_r']:
                    continue

                amount_total += line.product_qty
                for move in line.move_ids:
                    if move.state == 'done':
                        move_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, line.product_uom.id)
                        if move.type == 'in':
                            amount_received += move_qty

            if amount_total:
                res[order.id] = (amount_received / amount_total) * 100

        return res

    def _get_order_from_corner_tax(self, cr, uid, ids, context=None):
        if ids:
            cr.execute('select purchase_id from account_invoice_tax where id in %s', (tuple(ids),))
            return [x[0] for x in cr.fetchall()]
        return []

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(cr, uid, ids, fields_to_fetch=['order_id'], context=context):
            result[line.order_id.id] = True
        return list(result.keys())

    def _get_order_state_changed(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(cr, uid, ids, fields_to_fetch=['order_id', 'state'], context=context):
            if line.state in ('cancel', 'cancel_r'):
                result[line.order_id.id] = True
        return list(result.keys())

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
        Check if the PO has lines
        """

        res = {}
        for _id in ids:
            res[_id] = True
        cr.execute("select order_id from purchase_order_line where order_id in %s group by order_id", (tuple(ids),))
        for x in cr.fetchall():
            res[x[0]] = False
        return res


    def _po_from_x(self, cr, uid, ids, field_name, args, context=None):
        """
        fields.function multi for 'po_from_ir' and 'po_from_fo' fields.
        As one PO can contains lines from IR and from FO, both fields can be True
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            return {}
        res = {}

        for _id in ids:
            res[_id] = {
                'po_from_ir': False,
                'po_from_fo': False,
            }
        cr.execute('''
            select  pol.order_id, bool_or(not so.procurement_request)
            from purchase_order_line pol
            inner join sale_order_line sol on sol.id = pol.linked_sol_id
            inner join sale_order so on so.id = sol.order_id
            where
            pol.order_id in %s
            group by pol.order_id
        ''', (tuple(ids), ))
        for x in cr.fetchall():
            res[x[0]] = {
                'po_from_ir': True,
                'po_from_fo': x[1],
            }

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
            else:
                names = self.pool.get('res.company')._get_instance_record(cr, uid).instance
            res[po_r['id']] = names
        return res

    def _get_project_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the name of the POs at project side
        '''
        if isinstance(ids, int):
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
        if isinstance(ids, int):
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

        po_ids = set()
        for tu in args:
            if tu[1] in ('ilike', 'not ilike', '=', '!='):
                so_ids = self.pool.get('sale.order').search(cr, uid, [('client_order_ref', tu[1], tu[2])], context=context)
                sol_ids = self.pool.get('sale.order.line').search(cr, uid, [('order_id', 'in', so_ids)], context=context)
                pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', 'in', sol_ids)], context=context)
                for pol in self.pool.get('purchase.order.line').browse(cr, uid, pol_ids, context=context):
                    po_ids.add(pol.order_id.id)
            else:
                raise osv.except_osv(_('Error'), _('Bad operator : You can only use \'=\', \'!=\', \'ilike\' or \'not ilike\' as operator'))

        return [('id', 'in', list(po_ids))]

    def _get_short_partner_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return a shortened version of Supplier Reference, with only the Order Reference
        '''
        if isinstance(ids, int):
            ids = [ids]

        partner_ref = {}
        for po in self.browse(cr, uid, ids, fields_to_fetch=['partner_ref', 'partner_id'], context=context):
            partner_ref[po.id] = ''
            if po.partner_ref:
                if '.' in po.partner_ref and po.partner_id.name in po.partner_ref:
                    partner_ref[po.id] = po.partner_ref.split('.')[-1]
                else:
                    partner_ref[po.id] = po.partner_ref

        return partner_ref

    def onchange_short_partner_ref(self, cr, uid, ids, short_partner_ref=False, context=None):
        '''
        Set Partner Ref. value to the value of the Short Partner Ref.
        '''
        if context is None:
            context = {}

        res = {}
        res['value'] = {'partner_ref': short_partner_ref}

        return res

    def _get_customer_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return a concatenation of the PO's customer references from the project (case of procurement request)
        '''
        if isinstance(ids, int):
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

    def _get_short_customer_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return a concatenation of the PO's customer references from the project (case of procurement request)
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        so_obj = self.pool.get('sale.order')
        for po_id in ids:
            res[po_id] = ""

            so_ids = self.get_so_ids_from_po_ids(cr, uid, po_id, context=context)
            for so in so_obj.read(cr, uid, so_ids, ['short_client_ref'], context=context):
                if so['short_client_ref']:
                    if res[po_id]:
                        res[po_id] += ';'
                    res[po_id] += so['short_client_ref']

        return res

    def _get_line_count(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of non-cancelled line(s) for the PO
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for po_id in ids:
            res[po_id] = 0

        cr.execute("""
            SELECT order_id, COUNT(*) FROM purchase_order_line 
            WHERE order_id IN %s AND state NOT IN ('cancel', 'cancel_r') GROUP BY order_id
        """, (tuple(ids),))
        for po in cr.fetchall():
            res[po[0]] = po[1]

        return res

    def _get_location_data(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for po in self.browse(cr, uid, ids, fields_to_fetch=['order_line', 'state'], context=context):
            if po.order_line:
                not_cancel = ""
                if po.state != 'cancel':
                    not_cancel = " AND pl.state NOT IN ('cancel', 'cancel_r')"
                cr.execute("""
                    SELECT DISTINCT(l.id), l.name FROM purchase_order p 
                        LEFT JOIN purchase_order_line pl ON pl.order_id = p.id
                        LEFT JOIN stock_location l ON pl.reception_dest_id = l.id
                    WHERE p.id = %s""" + not_cancel, (po.id,)) # not_a_user_entry
                location_ids = []
                location_names = []
                for loc in cr.fetchall():
                    location_ids.append(loc[0])
                    location_names.append(loc[1])
                res[po.id] = {
                    'location_ids': location_ids,
                    'location_names': "; ".join(location_names)
                }
            else:
                input_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking',
                                                                               'stock_location_input')[1]
                res[po.id] = {'location_ids': [input_id], 'location_names': _('Input')}
        return res

    def _get_less_advanced_line_state(self, cr, uid, ids, field_name, arg, context=None):
        """
        Get the less advanced state of the purchase order lines
        Used to compute PO and RfQ state
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        if not ids:
            return {}

        res = {}
        po_update_date_confirm = []
        ftf = ['state', 'push_fo', 'empty_po_cancelled', 'rfq_state', 'rfq_ok']
        for po in self.browse(cr, uid, ids, fields_to_fetch=ftf, context=context):
            res[po.id] = {}
            if not po.rfq_ok:  # If the document is not RfQ
                po_state_seq = {
                    'draft': 10,
                    'draft_p': 15,
                    'validated': 20,
                    'validated_p': 25,
                    'sourced_p': 30,
                    'confirmed': 35,
                    'confirmed_p': 40,
                    'done': 50
                }

                po_update_date_confirm = []
                if po.empty_po_cancelled:
                    res[po.id]['state'] = 'cancel'
                else:
                    pol_states = set()
                    cr.execute('select distinct(state) from purchase_order_line where order_id = %s', (po.id, ))
                    for x in cr.fetchall():
                        pol_states.add(x[0])
                    if pol_states:
                        if all([s.startswith('cancel') for s in pol_states]):  # if all lines are cancelled then the PO is cancelled
                            res[po.id]['state'] = 'cancel'
                        else:  # else compute the less advanced state:
                            # cancel state must be ignored:
                            pol_states.discard('cancel')
                            pol_states.discard('cancel_r')
                            res[po.id]['state'] = self.pool.get('purchase.order.line.state').get_less_advanced_state(cr, uid, ids, pol_states, context=context)

                            if res[po.id]['state'] == 'draft':  # set the draft-p state ?
                                draft_sequence = self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, 'draft', context=context)
                                # do we have a line further than draft in our FO ?
                                if any([self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, s, context=context) > draft_sequence for s in pol_states]):
                                    res[po.id]['state'] = 'draft_p'
                            elif res[po.id]['state'] in ('validated', 'validated_n'): # set the validated-p state ?
                                validated_sequence = self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, 'validated', context=context)
                                # do we have a line further than validated in our FO ?
                                if any([self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, s, context=context) > validated_sequence for s in pol_states]):
                                    res[po.id]['state'] = 'validated_p'
                                else:
                                    res[po.id]['state'] = 'validated'
                            elif res[po.id]['state'].startswith('sourced'):  # set the sourced-p state ?
                                sourced_sequence = self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, 'sourced', context=context)
                                # do we have a line further than sourced in our FO ?
                                if any([self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, s, context=context) > sourced_sequence for s in pol_states]):
                                    res[po.id]['state'] = 'sourced_p'
                                else:
                                    res[po.id]['state'] = 'sourced'
                            elif res[po.id]['state'] == 'confirmed':  # set the confirmed-p state ?
                                po_update_date_confirm.append(po.id)
                                confirmed_sequence = self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, 'confirmed', context=context)
                                # do we have a line further then confirmed in our FO ?
                                if any([self.pool.get('purchase.order.line.state').get_sequence(cr, uid, ids, s, context=context) > confirmed_sequence for s in pol_states]):
                                    res[po.id]['state'] = 'confirmed_p'
                            # PO state must not go back:
                            if po.push_fo:
                                # fo push, 2 line added, L2 cancel , sync => resulting PO must be validated
                                po_state_seq['draft_p'] = 0
                                po_state_seq['sourced_p'] = 5
                            if po_state_seq.get(res[po.id]['state'], 100) < po_state_seq.get(po.state, 0):
                                res[po.id]['state'] = po.state
                    else:
                        res[po.id]['state'] = 'draft'

                # add audit line in track change if state has changed:
                if po.state != res[po.id]['state']:
                    self.add_audit_line(cr, uid, po.id, po.state, res[po.id]['state'], context=context)
            else:  # If the PO is RfQ
                rfq_state_seq = {'draft': 10, 'sent': 20, 'updated': 30, 'done': 40}

                if po.empty_po_cancelled:
                    res[po.id]['rfq_state'] = 'cancel'
                else:
                    rfql_states = set()
                    cr.execute('select distinct(rfq_line_state) from purchase_order_line where order_id = %s', (po.id,))
                    for x in cr.fetchall():
                        rfql_states.add(x[0])
                    if rfql_states:
                        if all([s.startswith('cancel') for s in rfql_states]):  # if all lines are cancelled then the PO is cancelled
                            res[po.id]['rfq_state'] = 'cancel'
                        else:  # else compute the less advanced state:
                            # cancel state must be ignored:
                            rfql_states.discard('cancel')
                            rfql_states.discard('cancel_r')
                            res[po.id]['rfq_state'] = self.pool.get('rfq.line.state').\
                                get_less_advanced_state(cr, uid, ids, rfql_states, context=context)

                            if rfq_state_seq.get(res[po.id]['rfq_state'], 100) < rfq_state_seq.get(po.rfq_state, 0):
                                res[po.id]['rfq_state'] = po.rfq_state
                    else:
                        res[po.id]['rfq_state'] = 'draft'

                # add audit line in track change if state has changed:
                if po.rfq_state != res[po.id]['rfq_state']:
                    self.add_audit_line(cr, uid, po.id, po.rfq_state, res[po.id]['rfq_state'], context=context)

        if po_update_date_confirm:
            cr.execute('''
                update purchase_order po
                    set date_confirm=max_pol.confirmation_date
                from
                    (
                        select
                            pol.order_id, max(pol.confirmation_date) as confirmation_date
                        from
                            purchase_order_line pol
                        where
                            pol.order_id in %(po_ids)s
                        group by
                            pol.order_id
                    ) max_pol
                where
                    max_pol.order_id = po.id and
                    po.id in %(po_ids)s
                ''', {'po_ids': tuple(po_update_date_confirm)})
        return res

    def _is_fixed_type(self, cr, uid, ids, field_name, args, context=None):
        """
        For each PO, set is the Order Type of the PO can be changed or not
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of purchase.order records to check
        :param field_name: Name of the field to compute
        :param args: Extra parameters
        :param context: Context of the call
        :return: A dictionnary with ID of the purchase.order record as keys and True/Fales as values
        """
        if isinstance(ids, int):
            ids = [ids]

        if context is None:
            context = {}

        old_value = context.get('procurement_request', False)
        context['procurement_request'] = True

        res = {}
        for po in self.browse(cr, uid, ids, fields_to_fetch=['po_from_fo', 'po_from_ir'], context=context):
            if po.po_from_fo or po.po_from_ir:
                src_type = {}
                sale_ids = self.get_so_ids_from_po_ids(cr, uid, [po.id], context=context)
                if sale_ids:
                    for sale in self.pool.get('sale.order').read(cr, uid, sale_ids, ['procurement_request', 'order_type'], context=context):
                        if sale['procurement_request'] or sale['order_type'] in ['regular', 'donation_prog']:
                            src_type['purchase_list'] = 1
                            src_type['regular'] = 1

                        if not sale['procurement_request']:
                            if sale['order_type'] in ['regular', 'donation_prog']:
                                src_type['direct'] = 1
                            elif sale['order_type'] == 'loan':
                                src_type['loan'] = 1
                            elif sale['order_type'] == 'loan_return':
                                src_type['loan_return'] = 1
                            elif sale['order_type'] == 'donation_exp':
                                src_type['donation_exp'] = 1
                            elif sale['order_type'] == 'donation_st':
                                src_type['donation_st'] = 1
                res[po.id] = json.dumps(list(src_type))
            else:
                res[po.id] = json.dumps([x[0] for x in ORDER_TYPES_SELECTION])

        context['procurement_request'] = old_value
        return res

    def _order_line_order_type(self, cr, uid, ids, context=None):
        """
        Return the list of ID of purchase.order records to update
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of purchase.order.line records updated
        :param context: Context of the call
        :return: A list that represents a domain to apply on purchase.order records
        """
        lines = self.read(cr, uid, ids, ['order_id'], context=context)
        po_ids = set()
        for l in lines:
            po_ids.add(l['order_id'][0])

        return list(po_ids)

    def _get_receipt_date(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the date of the first picking for the the PO
        '''
        if context is None:
            context = {}
        res = {}
        pick_obj = self.pool.get('stock.picking')

        for order in self.browse(cr, uid, ids, context=context):
            pick_ids = pick_obj.search(cr, uid, [('purchase_id', '=', order.id)], offset=0, limit=1, order='date_done', context=context)
            if not pick_ids:
                res[order.id] = False
            else:
                res[order.id] = pick_obj.browse(cr, uid, pick_ids[0]).date_done

        return res

    def _get_vals_order_dates(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return function values
        '''
        if context is None:
            context = {}
        res = {}

        if isinstance(field_name, str):
            field_name = [field_name]

        for obj in self.browse(cr, uid, ids, context=context):
            # default dic
            res[obj.id] = {}
            # default value
            for f in field_name:
                res[obj.id].update({f: False})
            # get corresponding partner type
            if obj.partner_id:
                partner_type = obj.partner_id.partner_type
                res[obj.id]['partner_type'] = partner_type

        return res

    def _get_fake(self, cr, uid, ids, name, arg, context=None):
        """
        Fake method for 'has_confirmed_line', 'has_confirmed_or_further_line' and 'product_id' fields
        """
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for po_id in ids:
            res[po_id] = False
        return res

    def _search_has_confirmed_line(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain corresponding to POs having at least one line being exactly in Confirmed state
        """
        if context is None:
            context = {}
        pol_obj = self.pool.get('purchase.order.line')
        if not args:
            return []
        if args[0][1] != '=' or len(args[0]) < 3:
            raise osv.except_osv(_('Error'), _('Filter not implemented on %s') % (name, ))
        operator = args[0][2] is True and 'in' or 'not in'
        po_ids = set()
        pol_ids = pol_obj.search(cr, uid, [('state', '=', 'confirmed')], context=context)
        for pol in pol_obj.browse(cr, uid, pol_ids, fields_to_fetch=['order_id'], context=context):
            po_ids.add(pol.order_id.id)
        return [('id', operator, list(po_ids))]

    def _search_has_confirmed_or_further_line(self, cr, uid, obj, name, args, context=None):
        """
        Returns a domain corresponding to POs having at least one line being in Confirmed state or more
        """
        if context is None:
            context = {}
        pol_obj = self.pool.get('purchase.order.line')
        if not args:
            return []
        if args[0][1] != '=' or len(args[0]) < 3:
            raise osv.except_osv(_('Error'), _('Filter not implemented on %s') % (name, ))
        operator = args[0][2] is True and 'in' or 'not in'
        po_ids = set()
        pol_ids = pol_obj.search(cr, uid, [('state', 'in', ['confirmed', 'done'])], context=context)
        for pol in pol_obj.browse(cr, uid, pol_ids, fields_to_fetch=['order_id'], context=context):
            po_ids.add(pol.order_id.id)
        return [('id', operator, list(po_ids))]

    def _get_msg_big_qty(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}
        res = {}
        max_qty = self.pool.get('purchase.order.line')._max_qty
        max_amount = self.pool.get('purchase.order.line')._max_amount

        for id in ids:
            res[id] = ''

        cr.execute('''select line_number, order_id from purchase_order_line
            where
                order_id in %s and
                ( product_qty >= %s or product_qty*price_unit >= %s) and
                state not in ('cancel', 'cancel_r')
            ''', (tuple(ids), max_qty, max_amount))
        for x in cr.fetchall():
            res[x[1]] += ' #%s' % x[0]

        return res

    def _get_not_beyond_validated(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for po in self.browse(cr, uid, ids, fields_to_fetch=['state', 'order_line'], context=context):
            not_beyond_validated = True
            if po.state in ['draft', 'draft_p', 'validated']:
                if self.pool.get('purchase.order.line').search_exists(cr, uid, [('order_id', '=', po.id), ('state', 'not in', ['draft', 'validated', 'validated_n', 'cancel', 'cancel_r'])], context=context):
                    not_beyond_validated = False
            else:
                not_beyond_validated = False

            res[po.id] = not_beyond_validated

        return res

    def _get_nb_creation_message_nr(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}

        ret = {}
        for _id in ids:
            ret[_id] = 0

        cr.execute("""select target_id, count(*)
            from sync_client_message_received
            where
                run='f' and
                target_object='purchase.order' and
                target_id in %s
            group by target_id""", (tuple(ids),))
        for x in cr.fetchall():
            ret[x[0]] = x[1]

        return ret

    def _get_ad_lines_message_nr(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}

        ret = {}
        for _id in ids:
            ret[_id] = 0

        cr.execute("""select target_id, array_agg(distinct(line_number))
            from sync_client_message_received
            where
                run='f' and
                target_object='purchase.order.ad' and
                target_id in %s
            group by target_id""", (tuple(ids),))
        for x in cr.fetchall():
            ret[x[0]] = ', '.join(['%s'%l for l in x[1]])

        return ret

    def _get_ad_lines_missing_message(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}

        res = {}
        for _id in ids:
            res[_id] = 0

        cr.execute("""
            SELECT p.id, array_agg(DISTINCT(pl.line_number)) FROM purchase_order_line pl, purchase_order p 
            WHERE pl.order_id = p.id AND p.id IN %s AND p.analytic_distribution_id IS NULL 
                AND p.order_type NOT IN ('loan', 'loan_return', 'donation_st', 'donation_exp', 'in_kind') 
                AND p.push_fo = 'f' AND pl.state NOT IN ('cancel', 'cancel_r') AND pl.analytic_distribution_id IS NULL 
            GROUP BY p.id
        """, (tuple(ids),))
        for x in cr.fetchall():
            no_ad_lines = ', '.join(['%s' % (l,) for l in x[1][:20]])
            if len(x[1]) > 20:
                no_ad_lines += _(' and more')
            no_ad_lines += _('. It must be added manually')
            res[x[0]] = no_ad_lines

        return res

    def _get_catalogue_ratio(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}
        ret = {}
        pol_obj = self.pool.get('purchase.order.line')
        for _id in ids:
            ret[_id] = {
                'catalogue_ratio_conform': False,
                'catalogue_ratio_no_catalogue': False,
                'catalogue_ratio_not_conform': False,
                'catalogue_total_price_deviation': False,
                'catalogue_exists': False,
                'catalogue_display_tab': False,
                'catalogue_exists_text': False,
                'catalogue_ratio_text': '',
                'catalogue_ratio_plain_text': '',
                'catalogue_deviation_text': '',
                'catalogue_deviation_plain_text': '',
            }
        pol_obj._compute_catalog_mismatch(cr, uid, order_id=ids, context=context)

        cr.execute("""
            select
                pol.order_id,
                count(pol.catalog_mismatch!='' or NULL),
                count(pol.catalog_mismatch='conform' or NULL),
                count(pol.catalog_mismatch='na' or NULL),
                array_agg(pol.id)
            from
                purchase_order_line pol, purchase_order po
            where
                pol.order_id in %s and
                po.id = pol.order_id and
                po.catalogue_not_applicable != 't' and
                (pol.state not in ('cancel', 'cancel_r') or confirmation_date is not null)
            group by order_id""", (tuple(ids),))
        for x in cr.fetchall():
            if x[1]:
                catalogue_ratio_conform = round(100*x[2]/x[1])
                catalogue_ratio_no_catalogue = round(100*x[3]/x[1])
                catalogue_ratio_not_conform = round(100 - catalogue_ratio_conform - catalogue_ratio_no_catalogue)

                ret[x[0]] = {
                    'catalogue_exists': True,
                    'catalogue_ratio_conform': catalogue_ratio_conform,
                    'catalogue_ratio_no_catalogue': catalogue_ratio_no_catalogue,
                    'catalogue_ratio_not_conform': catalogue_ratio_not_conform,
                    'catalogue_exists_text': "<h2>%d%% %s</h2>" % (catalogue_ratio_conform, _('adherence to catalogue')),
                }
                if catalogue_ratio_conform != 100:
                    ret[x[0]]['catalogue_display_tab'] = True
                ret[x[0]]['catalogue_ratio_text'] = _('<b>Catalogue Adherence Summary:</b><br />PO lines adherence: <span class="readonlyfield">%d%%</span> PO Lines Mismatch: <span class="readonlyfield">%d%%</span> of which Not in catalogue: <span class="readonlyfield">%d%%</span>') % (catalogue_ratio_conform, catalogue_ratio_not_conform, catalogue_ratio_no_catalogue)
                ret[x[0]]['catalogue_ratio_plain_text'] = _('PO lines adherence: %d%% PO Lines Mismatch: %d%% of which Not in catalogue: %d%%') % (catalogue_ratio_conform, catalogue_ratio_not_conform, catalogue_ratio_no_catalogue)

            else:
                ret[x[0]]['catalogue_exists_text'] = '<h2 style="color: red">%s</h2>' % _('No valid catalogue')

            if x[4]:
                po_subtotal, catalog_po_subtotal = 0, 0
                for pol in pol_obj.read(cr, uid, x[4], ['price_subtotal', 'catalog_subtotal'], context=context):
                    # Add to the subtotal only if the line has a catalogue
                    if pol['catalog_subtotal']:
                        po_subtotal += pol['price_subtotal']
                        catalog_po_subtotal += pol['catalog_subtotal']
                catalogue_total_price_deviation = str(round(((po_subtotal - catalog_po_subtotal) / catalog_po_subtotal) * 100, 2))
                if po_subtotal > catalog_po_subtotal:
                    catalogue_total_price_deviation = '+' + catalogue_total_price_deviation
                ret[x[0]].update({
                    'catalogue_total_price_deviation': catalogue_total_price_deviation,
                    'catalogue_deviation_text': _('%% deviation of PO subtotal vs theoretical catalogue subtotal (for catalogue lines): <span class="readonlyfield">%s%%</span>') % (catalogue_total_price_deviation,),
                    'catalogue_deviation_plain_text': _('%% deviation of PO subtotal vs theoretical catalogue subtotal (for catalogue lines): %s%%') % (catalogue_total_price_deviation,),
                })
        return ret

    def _get_catalogue_description_text(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}
        ret = {}
        for _id in ids:
            ret[_id] = {'catalogue_description_text': '', 'catalogue_id': False}

        cr.execute("""
            select
                po.id, p.name, cat.name, cat.period_from, cat.period_to, cat.id, cat.active
            from
                purchase_order po
                inner join res_partner p on p.id = po.partner_id
                inner join product_pricelist curr_pricelist on curr_pricelist.id = po.pricelist_id
                join lateral (
                    select
                        name, period_from, period_to, id, active
                    from
                        supplier_catalogue cat
                    where
                        cat.partner_id = po.partner_id and
                        case when po.date_confirm is null then active = 't' else true end and
                        cat.state = 'confirmed' and
                        (cat.period_from is null or cat.period_from < coalesce(po.date_confirm, NOW())) and
                        (cat.period_to is null or cat.period_to > coalesce(po.date_confirm, NOW()))
                    order by
                        cat.currency_id = curr_pricelist.currency_id, cat.active, id desc
                    limit 1
                ) cat on true
            where
                po.id in %s
            """, (tuple(ids), ))

        date_obj = self.pool.get('date.tools')
        for x in cr.fetchall():
            ret[x[0]] = {
                'catalogue_description_text': '''
                    <label>%(status_text)s</label>: <span class="readonlyfield">%(status)s</span>
                    <label>%(supplier_text)s</label>: <span class="readonlyfield">%(supplier)s</span>
                    <label>%(catalogue_text)s</label>: <span class="readonlyfield">%(catalogue)s</span>
                    <label>%(from_text)s</label>: <span class="readonlyfield">%(date_from)s</span>
                    <label>%(to_text)s</label>: <span class="readonlyfield">%(date_to)s</span>''' % {
                    'status_text': _('Status'),
                    'supplier_text': _('Supplier'),
                    'catalogue_text': _('Catalogue'),
                    'from_text': _('From'),
                    'to_text': _('To'),
                    'status': x[6] and _('Active') or _('Inactive'),
                    'supplier': x[1],
                    'catalogue': x[2],
                    'date_from': x[3] and date_obj.get_date_formatted(cr, uid, datetime=x[3]) or '/',
                    'date_to': x[4] and date_obj.get_date_formatted(cr, uid, datetime=x[4]) or '/'
                },
                'catalogue_id': x[5],
            }
        return ret

    _columns = {
        'order_type': fields.selection(ORDER_TYPES_SELECTION, string='Order Type', required=True),
        'loan_id': fields.many2one('sale.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority'),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, add_empty=True),
        # we increase the size of the 'details' field from 30 to 86
        'details': fields.char(size=86, string='Details'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months'),
        'date_order': fields.date(string='Creation Date', required=True, select=True, help="Date on which this document has been created."),
        'name': fields.char('Order Reference', size=64, required=True, select=True, readonly=True,
                            help="unique number of the purchase order,computed automatically when the purchase order is created", sort_column='id'),
        'invoice_ids': fields.many2many('account.invoice', 'purchase_invoice_rel', 'purchase_id', 'invoice_id', 'Invoices', help="Invoices generated for a purchase order", readonly=True),
        'order_line': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', readonly=False),
        'order_line_mismatch': fields.one2many('purchase.order.line', 'order_id', 'PO Lines Mismatch with Catalogues', readonly=1, domain=['&', '&', ('product_id', '!=', False), ('catalog_mismatch', 'not in', ['conform', '']), '|', ('state', 'not in', ['cancel', 'cancel_r']), ('confirmation_date', '!=', False)], context={'from_mismatch': True}),
        'partner_id': fields.many2one('res.partner', 'Supplier', required=True, change_default=True, domain="[('id', '!=', company_id)]"),
        'partner_address_id': fields.many2one('res.partner.address', 'Address', required=True, domain="[('partner_id', '=', partner_id)]"),
        'dest_partner_id': fields.many2one('res.partner', string='Destination partner'),
        'dest_partner_type': fields.related('dest_partner_id', 'partner_type', string='DPO Dest Partner Type', type='selection', selection=PARTNER_TYPE, readonly=True, write_relate=False),
        'invoice_address_id': fields.many2one('res.partner.address', string='Invoicing address', required=True,
                                              help="The address where the invoice will be sent."),
        'invoice_method': fields.selection([('manual', 'Manual'), ('order', 'From Order'), ('picking', 'From Picking')], 'Invoicing Control', required=True, readonly=True,
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
        'short_partner_ref': fields.function(_get_short_partner_ref, method=True, string='Supplier Reference', type='char', size=64, store=False),
        'product_id': fields.function(_get_fake, method=True, type='many2one', relation='product.product', string='Product', help='Product to find in the lines', store=False, readonly=True),
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
        'dest_partner_names': fields.function(_get_dest_partner_names, type='char', size=256, string='Customers', method=True),  # uf-2223
        'split_po': fields.boolean('Created by split PO', readonly=True),
        'sourced_references': fields.function(_get_project_ref, method=True, string='Sourced references', type='text', store=False, multi='so_info'),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'requested_date_in_past': fields.function(_get_requested_date_in_past, method=True, string='Requested date in past', type='boolean', store=False),
        'update_in_progress': fields.boolean(string='Update in progress', readonly=True),
        # US-1765: register the 1st call of wkf_confirm_trigger to prevent recursion error
        'po_confirmed': fields.boolean('PO', readonly=True),
        'customer_ref': fields.function(_get_customer_ref, fnct_search=_src_customer_ref, method=True, string='Customer Ref.', type='text', store=False),
        'short_customer_ref': fields.function(_get_short_customer_ref, method=True, string='Customer Ref.', type='text', store=False),
        'line_count': fields.function(_get_line_count, method=True, type='integer', string="Line count", store=False),

        'date_approve': fields.date('Date Approved', readonly=1, select=True, help="Date on which purchase order has been approved"),
        'dest_address_id': fields.many2one('res.partner.address', 'Destination Address',
                                           help="Put an address if you want to deliver directly from the supplier to the customer." \
                                           "In this case, it will remove the warehouse link and set the customer location."
                                           ),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse'),
        'location_ids': fields.function(_get_location_data, type='many2many', relation='stock.location', string='Destination', method=True, multi='location_data', readonly=True),
        'location_names': fields.function(_get_location_data, type='char', size=256, string='Destination', method=True, multi='location_data',
                                          readonly=True, store=False, help="""This location is set according to the origin of the line(s) of the document. 
        It can have 'Input', 'Cross Docking', 'Non-Stockable' and/or 'Service' as data"""),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, help="The pricelist sets the currency used for this purchase order. It also computes the supplier price for the selected products/quantities."),
        'state': fields.function(_get_less_advanced_line_state, string='Order State', method=True, type='selection', selection=PURCHASE_ORDER_STATE_SELECTION, readonly=True,
                                 store={
                                     'purchase.order': (lambda obj, cr, uid, ids, c={}: ids, ['empty_po_cancelled'], 10),
                                     'purchase.order.line': (_get_order, ['state'], 10),
                                 },
                                 select=True, multi='get_po_rfq_states',
                                 help="The state of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' state. Then the order has to be confirmed by the user, the state switch to 'Confirmed'. Then the supplier must confirm the order to change the state to 'Approved'. When the purchase order is paid and received, the state becomes 'Done'. If a cancel action occurs in the invoice or in the reception of goods, the state becomes in exception.",
                                 internal="request_for_quotation"
                                 ),
        'rfq_state': fields.function(_get_less_advanced_line_state, string='Order State', method=True, type='selection', selection=RFQ_STATE_SELECTION, readonly=True,
                                     store={
                                         'purchase.order': (lambda obj, cr, uid, ids, c={}: ids, ['empty_po_cancelled'], 10),
                                         'purchase.order.line': (_get_order, ['rfq_line_state'], 10),
                                     }, select=True, multi='get_po_rfq_states', internal="purchase_order"),

        'validator': fields.many2one('res.users', 'Validated by', readonly=True),
        'notes': fields.text('Notes'),
        'picking_ids': fields.one2many('stock.picking', 'purchase_id', 'Picking List', readonly=True, help="This is the list of picking list that have been generated for this purchase"),
        'shipped': fields.boolean('Received', readonly=True, select=True, help="It indicates that a picking has been done"),
        'shipped_rate': fields.function(_shipped_rate, method=True, string='Received', type='float'),
        'invoiced': fields.function(_invoiced, method=True, string='Invoiced', type='boolean', help="It indicates that an invoice has been generated"),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'minimum_planned_date': fields.function(_minimum_planned_date, fnct_inv=_set_minimum_planned_date, method=True, string='Expected Date', type='date', select=True, help="This is computed as the minimum scheduled date of all purchase order lines' products.",
                                                store={
                                                    'purchase.order.line': (_get_order, ['date_planned'], 10),
                                                }
                                                ),
        'has_tax_at_line_level': fields.function(_amount_all, method=True, type='boolean', string='Tax at line', store= {
            'purchase.order.line': [
                (_get_order, ['taxes_id'], 10),
                (_get_order_state_changed, ['state'], 10),
            ]
        }, multi="sums"),
        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Purchase Price'), string='Untaxed Amount',
                                          store={
                                              'purchase.order.line': [
                                                  (_get_order, ['price_subtotal', 'taxes_id', 'price_unit', 'product_qty', 'product_id'], 10),
                                                  (_get_order_state_changed, ['state'], 10),
                                              ]
        }, multi="sums", help="The amount without tax"),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Purchase Price'), string='Taxes',
                                      store={
                                          'purchase.order.line': [
                                              (_get_order, ['price_subtotal', 'taxes_id', 'price_unit', 'product_qty', 'product_id'], 10),
                                              (_get_order_state_changed, ['state'], 10),
                                              (_get_order_from_corner_tax, ['purchase_id', 'amount'], 10),
                                          ],
            'account.invoice.tax': [
                                              (_get_order_from_corner_tax, ['purchase_id', 'amount'], 10),
                                          ],
        }, multi="sums", help="The tax amount"),
        'amount_total': fields.function(_amount_all, method=True, digits_compute=dp.get_precision('Purchase Price'), string='Total',
                                        store={
                                            'purchase.order.line': [
                                                (_get_order, ['price_subtotal', 'taxes_id', 'price_unit', 'product_qty', 'product_id'], 10),
                                                (_get_order_state_changed, ['state'], 10),
                                            ],
                                            'account.invoice.tax': [
                                                (_get_order_from_corner_tax, ['purchase_id', 'amount'], 10),
                                            ],
        }, multi="sums", help="The total amount"),
        'amount_total_tender_currency': fields.function(_amount_all, method=True, string='Total (Comparison Currency)',
                                                        digits_compute= dp.get_precision('Purchase Price'), store=False,
                                                        multi="sums", help="The total amount using the tender's currency for comparison"),
        'fiscal_position': fields.many2one('account.fiscal.position', 'Fiscal Position'),
        'create_uid': fields.many2one('res.users', 'Responsible'),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=1),
        'stock_take_date': fields.date(string='Date of Stock Take', required=False),
        'fixed_order_type': fields.function(_is_fixed_type, method=True, type='char', size=256, string='Possible order types', store={
            'purchase.order': (lambda obj, cr, uid, ids, c={}: ids, ['order_line'], 10),
            'purchase.order.line': (_order_line_order_type, ['order_id'], 10),
        },
        ),
        'delivery_requested_date': fields.date(string='Requested Delivery Date', required=True),
        'delivery_requested_date_modified': fields.date(string='Estimated Delivery Date'),
        'delivery_confirmed_date': fields.date(string='Confirmed Delivery Date'),
        'ready_to_ship_date': fields.date(string='Ready To Ship Date'),
        'shipment_date': fields.date(string='Shipment Date', help='Date on which picking is created at supplier'),
        'arrival_date': fields.date(string='Arrival date in the country', help='Date of the arrival of the goods at custom'),
        'receipt_date': fields.function(_get_receipt_date, type='date', method=True, store=True,
                                        string='Receipt Date', help='for a PO, date of the first godd receipt.'),
        # BETA - to know if the delivery_confirmed_date can be erased - to be confirmed
        'confirmed_date_by_synchro': fields.boolean(string='Confirmed Date by Synchro'),
        # FIELDS PART OF CREATE/WRITE methods
        # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
        'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport Mode',
                                           help='Number of days this field has to be associated with a transport mode selection'),
        # not a function because can be modified by user - **ONLY IN CREATE only if not in vals**
        'est_transport_lead_time': fields.float(digits=(16, 2), string='Est. Transport Lead Time',
                                                help="Estimated Transport Lead-Time in weeks"),
        # not a function because a function value is only filled when saved, not with on change of partner id
        # from partner_id object
        'partner_type': fields.selection(string='Partner Type', selection=PARTNER_TYPE, readonly=True),
        # not a function because a function value is only filled when saved, not with on change of partner id
        # from partner_id object
        'internal_type': fields.selection(string='Type', selection=ZONE_SELECTION, readonly=True),

        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution', select=1),
        'commitment_ids': fields.one2many('account.commitment', 'purchase_id', string="Commitment Vouchers", readonly=True),
        'has_confirmed_line': fields.function(_get_fake, type='boolean', method=True, store=False,
                                              fnct_search=_search_has_confirmed_line,
                                              string='Has a confirmed line',
                                              help='Only used to SEARCH for POs with at least one line in Confirmed state'),
        'has_confirmed_or_further_line': fields.function(_get_fake, type='boolean', method=True, store=False,
                                                         fnct_search=_search_has_confirmed_or_further_line,
                                                         string='Has a confirmed (or further) line',
                                                         help='Only used to SEARCH for POs with at least one line in Confirmed or Closed state'),
        'split_during_sll_mig': fields.boolean('PO split at Coordo during SLL migration'),
        'empty_po_cancelled': fields.boolean('Empty PO cancelled', help='Flag to see if the PO has been cancelled while empty'),
        'from_address': fields.many2one('res.partner.address', string='From Address', required=True),
        'msg_big_qty': fields.function(_get_msg_big_qty, type='char', string='Lines with 10 digits total amounts', method=1),
        'show_default_msg': fields.boolean(string='Show PO Default Message'),
        'not_beyond_validated': fields.function(_get_not_beyond_validated, type='boolean', string="Check if lines' and document's state is not beyond validated", method=1),
        'po_version': fields.integer('Migration: manage old flows', help='v1: dpo reception not synced up, SI/CV generated at PO confirmation', internal=1),
        'nb_creation_message_nr': fields.function(_get_nb_creation_message_nr, type='integer', method=1, string='Number of NR creation messages'),
        'ad_lines_message_nr': fields.function(_get_ad_lines_message_nr, type='char', size=1024, method=1, string='Line number of NR message for missing AD'),
        'ad_lines_missing_message': fields.function(_get_ad_lines_missing_message, type='char', size=1024, method=1, string='Line number of lines missing AD'),
        'tax_line': fields.one2many('account.invoice.tax', 'purchase_id', 'Tax Lines'),
        'alert_msl_mml': fields.function(_get_header_msl_mml_alert, method=True, type='char', string="Contains non-conform MML/MSL"),
        'catalogue_ratio_conform': fields.function(_get_catalogue_ratio, method=True, type='integer', string='PO Lines Adherence', multi='catalogue'),
        'catalogue_ratio_not_conform': fields.function(_get_catalogue_ratio, method=True, type='integer', string='PO Lines Mismatch', multi='catalogue'),
        'catalogue_ratio_no_catalogue': fields.function(_get_catalogue_ratio, method=True, type='integer', string='Not in Catalogue', multi='catalogue'),
        'catalogue_ratio_text': fields.function(_get_catalogue_ratio, method=True, type='char', string='Catalogue Ratio', multi='catalogue'),
        'catalogue_ratio_plain_text': fields.function(_get_catalogue_ratio, method=True, type='char', string='Catalogue Ratio', multi='catalogue'),
        'catalogue_total_price_deviation': fields.function(_get_catalogue_ratio, method=True, type='char', size=16, string='PO Total Price Deviation', multi='catalogue'),
        'catalogue_deviation_text': fields.function(_get_catalogue_ratio, method=True, type='char', string='PO Deviation', multi='catalogue'),
        'catalogue_deviation_plain_text': fields.function(_get_catalogue_ratio, method=True, type='char', string='PO Deviation', multi='catalogue'),
        'catalogue_exists': fields.function(_get_catalogue_ratio, method=True, type='boolean', string='Has a valid catalogue', multi='catalogue'),
        'catalogue_display_tab': fields.function(_get_catalogue_ratio, method=True, type='boolean', string='Display tab catalogue', multi='catalogue'),
        'catalogue_exists_text': fields.function(_get_catalogue_ratio, method=True, type='char', string='Catalogue Lines Status', multi='catalogue'),
        'catalogue_description_text': fields.function(_get_catalogue_description_text,  method=True, type='char', string='Catalogue Text', multi='cat_info'),
        'catalogue_id': fields.function(_get_catalogue_description_text,  method=True, type='many2one', relation='supplier.catalogue', string='Catalogue', multi='cat_info'),
        'catalogue_not_applicable': fields.boolean('PO confirmed before pol catalogue', readonly=1),

    }
    _defaults = {
        'po_version': 2,
        'split_during_sll_mig': False,
        'po_confirmed': lambda *a: False,
        'order_type': lambda *a: 'regular',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: False,
        'loan_duration': 2,
        'invoice_address_id': lambda obj, cr, uid, ctx: obj.pool.get('res.partner').address_get(cr, uid, obj.pool.get('res.users').browse(cr, uid, uid, ctx).company_id.partner_id.id, ['invoice'])['invoice'],
        'invoice_method': lambda *a: 'picking',
        'dest_address_id': lambda obj, cr, uid, ctx: obj.pool.get('res.partner').address_get(cr, uid, obj.pool.get('res.users').browse(cr, uid, uid, ctx).company_id.partner_id.id, ['delivery'])['delivery'],
        'from_address': lambda obj, cr, uid, ctx: obj.pool.get('res.partner').address_get(cr, uid, obj.pool.get('res.users').browse(cr, uid, uid, ctx).company_id.partner_id.id, ['default'])['default'],
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
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'purchase.order', context=c),
        'fixed_order_type': lambda *a: json.dumps([]),
        'confirmed_date_by_synchro': False,
        'empty_po_cancelled': False,
        'show_default_msg': False,
        'not_beyond_validated': True,
        'catalogue_not_applicable': False,
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique !'),
    ]

    def _check_order_type(self, cr, uid, ids, context=None):
        '''
        Check the integrity of the order type and the source order type
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of sale.order to check
        :param context: Context of the call
        :return: True if the integrity is ok.
        '''
        err = []

        order_types_dict = dict((x, y) for x, y in ORDER_TYPES_SELECTION)

        for order in self.read(cr, uid, ids, ['name', 'fixed_order_type', 'order_type', 'is_a_counterpart'], context=context):
            if order['is_a_counterpart'] and order['order_type'] not in ['loan', 'loan_return']:
                err.append(_('%s: This purchase order is a loan counterpart. You cannot change its order type') % order['name'])
            else:
                json_info = json.loads(order['fixed_order_type'])
                if json_info and order['order_type'] not in json_info:
                    allowed_type = ' / '.join([_(order_types_dict.get(x)) for x in json_info])
                    err.append(_('%s: Only %s order types are allowed for this purchase order') % (order['name'], allowed_type))

        if err:
            raise osv.except_osv(
                _('Error'),
                '\n'.join(x for x in err),
            )

        return True

    _constraints = [
        (_check_order_type, 'The order type of the order is not consistent with the order type of the source', ['order_type']),
    ]

    def _check_stock_take_date(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        # Do not prevent modification during synchro
        if not context.get('sync_update_execution') and not context.get('sync_message_execution'):
            for po in self.browse(cr, uid, ids, context=context):
                if po.state in ['draft', 'draft_p', 'validated'] and po.stock_take_date \
                        and po.stock_take_date > po.date_order:
                    raise osv.except_osv(
                        _('Error'), _('The Stock Take Date of %s is not consistent! It should not be later than its creation date')
                        % (po.name,)
                    )
                # Check the lines as well (was for the UC where Creation Date was modified)
                error_lines = []
                for pol in po.order_line:
                    if pol.state in ['draft', 'validated', 'validated_n'] and pol.stock_take_date and \
                            pol.stock_take_date > po.date_order:
                        error_lines.append(str(pol.line_number))
                if error_lines:
                    raise osv.except_osv(
                        _('Error'), _('The Stock Take Date of the lines %s is not consistent! It should not be later than %s\'s creation date')
                        % (', '.join(error_lines), po.name or _('the PO'))
                    )

        return True

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Fill the unallocated_ok field according to Unifield setup
        '''
        res = super(purchase_order, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        setup = self.pool.get('unifield.setup.configuration').get_config(cr, uid)
        res.update({'unallocation_ok': False, 'allocation_setup': setup.allocation_setup})
        if setup.allocation_setup == 'unallocated':
            res.update({'unallocation_ok': True})

        res.update({'name': False})

        return res

    def create(self, cr, uid, vals, context=None):
        """
        # UTP-114 demands purchase_list PO to be 'from picking'.
        """
        if context is None:
            context = {}

        if not 'pricelist_id' in vals and vals.get('partner_id'):
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], fields_to_fetch=['property_product_pricelist_purchase', 'partner_type'], context=context)
            if partner.partner_type in ('internal', 'intermission', 'section'):
                vals['pricelist_id'] = partner.property_product_pricelist_purchase.id

        # common function for so and po
        vals = common_create(self, cr, uid, vals, type=get_type(self), context=context)
        # fill partner_type vals
        if vals.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, vals.get('partner_id'), context=context)
            # erase delivery_confirmed_date if partner_type is internal or section and the date is not filled by synchro - considered updated by synchro by default
            if partner.partner_type in ('internal', 'section') and not vals.get('confirmed_date_by_synchro', True):
                vals.update({'delivery_confirmed_date': False})

        if vals.get('order_type'):
            if vals.get('order_type') in ['donation_exp', 'donation_st']:
                vals.update({'invoice_method': vals.get('partner_type', '') == 'section' and 'picking' or 'manual'})
            elif vals.get('order_type') in ['loan', 'loan_return']:
                vals.update({'invoice_method': 'manual'})
            elif vals.get('order_type') in ['direct']:
                vals.update({'invoice_method': 'picking'})
                if vals.get('partner_id') and self.pool.get('res.partner').read(cr, uid, vals.get('partner_id'), ['partner_type'], context=context)['partner_type'] == 'esc':
                    vals.update({'invoice_method': 'manual'})
                elif vals.get('dest_partner_id') and self.pool.get('res.partner').read(cr, uid, vals.get('dest_partner_id'), ['partner_type'], context=context)['partner_type'] == 'external':
                    vals.update({'invoice_method': 'order'})
            else:
                vals.update({'invoice_method': 'picking'})

        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)
        res = super(purchase_order, self).create(cr, uid, vals, context=context)

        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, res, context=context)

        return res

    def write_web(self, cr, uid, ids, vals, context=None, ignore_access_error=False):
        """
        Overridden method called by the Web on write
        """
        pol_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
        cur_obj = self.pool.get('res.currency')
        suppinf_obj = self.pool.get('product.supplierinfo')
        partinf_obj = self.pool.get('pricelist.partnerinfo')

        if 'partner_id' in vals:
            partner = partner_obj.browse(cr, uid, vals['partner_id'], fields_to_fetch=['property_product_pricelist_purchase', 'partner_type'], context=context)
            to_curr_id = partner.property_product_pricelist_purchase.currency_id.id
            if vals.get('pricelist_id') and partner.partner_type == 'external':
                to_curr_id = self.pool.get('product.pricelist').browse(cr, uid, vals['pricelist_id'], fields_to_fetch=['currency_id'], context=context).currency_id.id

            for order in self.browse(cr, uid, ids, fields_to_fetch=['state', 'date_order', 'partner_id', 'order_line', 'pricelist_id', 'tax_line'], context=context):
                line_changed = False
                if vals['partner_id'] != order.partner_id.id:
                    if order.state != 'draft':
                        raise osv.except_osv(_('Error !'), _('The Partner can not be modified if the Purchase Order is not in Draft state. Please refresh the page to continue using this PO'))

                    for line in order.order_line:
                        if line.state in ('draft', 'validated_n'):
                            if line.product_id:
                                to_suppinf_ids = suppinf_obj.search(cr, uid, [('name', '=', partner.id), ('product_id', '=', line.product_id.id)], context=context)
                                price_to_convert = line.product_id.standard_price
                                from_curr_id = line.product_id.currency_id.id
                                if to_suppinf_ids:
                                    domain = [('uom_id', '=', line.product_uom.id), ('suppinfo_id', 'in', to_suppinf_ids),
                                              '|', ('valid_from', '<=', order.date_order), ('valid_from', '=', False),
                                              '|', ('valid_till', '>=', order.date_order), ('valid_till', '=', False)]
                                    domain_cur = [('currency_id', '=', to_curr_id)]
                                    domain_cur.extend(domain)

                                    part_inf_ids = partinf_obj.search(cr, uid, domain_cur, order='sequence asc, min_quantity asc, id desc', limit=1, context=context)
                                    if not part_inf_ids:
                                        part_inf_ids = partinf_obj.search(cr, uid, domain, order='sequence asc, min_quantity asc, id desc', limit=1, context=context)
                                    if part_inf_ids:
                                        partinf_line = partinf_obj.browse(cr, uid, part_inf_ids[0], fields_to_fetch=['price', 'currency_id'], context=context)
                                        price_to_convert = partinf_line.price
                                        from_curr_id = partinf_line.currency_id.id
                            else:
                                from_curr_id = order.pricelist_id.currency_id.id
                                price_to_convert = line.price_unit

                            line_changed = True
                            new_price = cur_obj.compute(cr, uid, from_curr_id, to_curr_id, price_to_convert, round=False)
                            pol_obj.write(cr, uid, line.id, {'price_unit': new_price}, context=context)
                    if line_changed:
                        tax_line_obj = self.pool.get('account.invoice.tax')
                        for tax_line in order.tax_line:
                            new_price = cur_obj.compute(cr, uid, order.pricelist_id.currency_id.id, to_curr_id, tax_line.amount, round=False)
                            tax_line_obj.write(cr, uid, tax_line.id, {'amount': new_price}, context=context)


        return super(purchase_order, self).write_web(cr, uid, ids, vals, context=context, ignore_access_error=ignore_access_error)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Check if the partner is correct.
        # UTP-114 demand purchase_list PO to be "from picking" as invoice_method
        '''
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        pol_obj = self.pool.get('purchase.order.line')

        if not 'date_order' in vals:
            vals.update({'date_order': self.browse(cr, uid, ids[0]).date_order})

        if 'partner_id' in vals:
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], fields_to_fetch=['property_product_pricelist_purchase', 'partner_type'], context=context)
            if partner.partner_type in ('internal', 'intermission', 'section'):
                vals['pricelist_id'] = partner.property_product_pricelist_purchase.id

        # fill partner_type and zone
        if vals.get('partner_id', False):
            partner = self.pool.get('res.partner').browse(cr, uid, vals.get('partner_id'), context=context)
            # partner type - always set
            vals.update({'partner_type': partner.partner_type})
            if partner.partner_type != 'external':
                vals['tax_line'] = False
                tax_obj = self.pool.get('account.invoice.tax')
                tax_lines_ids = tax_obj.search(cr, uid, [('purchase_id', 'in', ids)], context=context)
                if tax_lines_ids:
                    tax_obj.unlink(cr, uid, tax_lines_ids, context=context)

            # internal type (zone) - always set
            vals.update({'internal_type': partner.zone, })
            # erase delivery_confirmed_date if partner_type is internal or section and the date is not filled by synchro - considered updated by synchro by default
            if partner.partner_type in ('internal', 'section') and not vals.get('confirmed_date_by_synchro', True):
                vals.update({'delivery_confirmed_date': False, })

        if 'partner_id' in vals:
            self._check_user_company(cr, uid, vals['partner_id'], context=context)

        res_partner_obj = self.pool.get('res.partner')
        for order in self.read(cr, uid, ids, ['partner_id', 'warehouse_id', 'partner_ref', 'rfq_ok'], context=context):
            partner_type = res_partner_obj.read(cr, uid, int(vals.get('partner_id', order['partner_id'][0])), ['partner_type'], context=context)['partner_type']
            if order['partner_ref'] and not order['rfq_ok'] and partner_type not in ['external', 'esc'] and \
                    'partner_ref' in vals and vals['partner_ref'] == False:
                vals.pop('partner_ref')
            if vals.get('order_type'):
                if vals.get('order_type') in ['donation_exp', 'donation_st']:
                    vals.update({'invoice_method': partner_type == 'section' and 'picking' or 'manual'})
                elif vals.get('order_type') in ['loan', 'loan_return']:
                    vals.update({'invoice_method': 'manual'})
                elif vals.get('order_type') in ['direct'] and partner_type != 'esc':
                    dest_partner_type = res_partner_obj.read(cr, uid, int(vals.get('dest_partner_id', order['partner_id'][0])), ['partner_type'], context=context)['partner_type']
                    if dest_partner_type == 'external':
                        vals.update({'invoice_method': 'order'})
                    else:
                        vals.update({'invoice_method': 'picking'})
                elif vals.get('order_type') in ['direct'] and partner_type == 'esc':
                    vals.update({'invoice_method': 'manual'})
                else:
                    vals.update({'invoice_method': 'picking'})

            # FIXME here it is useless to continue as the next loop will overwrite vals
            break

        # Fix bug invalid syntax for type date:
        if 'valid_till' in vals and vals['valid_till'] == '':
            vals['valid_till'] = False

        # Check if there's source documents on lines
        if vals.get('order_type') and vals['order_type'] in ['loan', 'loan_return', 'donation_exp', 'donation_st', 'in_kind']:
            # do not raise on existing non draft PO
            draft_po_ids = self.search(cr, uid, [('id', 'in', ids), ('state', '=', 'draft'), ('is_a_counterpart', '=', False)], context=context)
            if draft_po_ids and pol_obj.search_exist(cr, uid, [('order_id', 'in', draft_po_ids), ('origin', '!=', False), ('state', '!=', 'cancel')], context=context):
                raise osv.except_osv(
                    _('Error'),
                    _('You can\'t change the Order Type to Loan, Donation to prevent losses, Standard donation or In Kind Donation if a line has a Source Document')
                )

        res = super(purchase_order, self).write(cr, uid, ids, vals, context=context)

        if vals.get('stock_take_date') or vals.get('date_order'):
            self._check_stock_take_date(cr, uid, ids, context=context)

        # Delete expected sale order line
        if 'state' in vals and vals.get('state') not in ('draft', 'validated'):
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
            if s['state'] in ['draft', 'cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Purchase Order(s) which are in %s State!') % _(dict(PURCHASE_ORDER_STATE_SELECTION).get(s['state'])))

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

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=80):
        '''
        Search all PO by internal or customer reference
        '''
        if context is None:
            context = {}
        if context.get('from_followup'):
            ids = []
            if name and len(name) > 1:
                ids.extend(self.search(cr, uid, [('partner_ref', operator, name)], context=context))
            return self.name_get(cr, uid, ids, context=context)
        elif context.get('from_followup2'):
            # receive input name as a customer name, get customer ids by operator
            # then search customer ids in PO
            ids = []
            if name and len(name) > 1:
                # search for customer
                customer_ids = self.pool.get('res.partner').search(cr, uid,
                                                                   [('name', operator, name)], context=context)
                if customer_ids:
                    # search for m2o 'dest_partner_id' dest_customer in PO (direct PO)
                    po1_ids = ids.extend(self.search(cr, uid,
                                                     [('dest_partner_id', 'in', customer_ids)],
                                                     context=context))
                    # search for m2m 'dest_partner_ids' dest_customer in PO (sourcing PO)
                    query = "SELECT purchase_order_id FROM res_partner_purchase_order_rel"
                    query += " WHERE partner_id in (" + ",".join(map(str, customer_ids)) + ")"
                    cr.execute(query)
                    if cr.rowcount:
                        po2_ids = cr.fetchall()
                        if po1_ids:
                            # po1_ids, po2_ids union
                            for po_id in po1_ids:
                                if po_id not in po2_ids:
                                    po2_ids.append(po_id)
                        ids = po2_ids
                    if ids:
                        domain = [
                            ('rfq_ok', '=', False),
                            ('id', 'in', ids),
                        ]
                        ids = self.search(cr, uid, domain, context=context)
            return self.name_get(cr, uid, ids, context=context)
        else:
            return super(purchase_order, self).name_search(cr, uid, name, args, operator, context, limit)

    def name_get(self, cr, uid, ids, context=None):
        '''
        If the method is called from followup wizard, set the supplier ref in brackets
        '''
        if context is None:
            context = {}
        if context.get('from_followup'):
            res = []
            for r in self.browse(cr, uid, ids, context=context):
                if r.partner_ref:
                    res.append((r.id, '%s' % r.partner_ref))
                else:
                    res.append((r.id, '%s' % r.name))
            return res
        elif context.get('from_followup2'):
            res = []
            for r in self.browse(cr, uid, ids, context=context):
                name = r.name
                customer_names = []
                if r.dest_partner_id:
                    # direct customer
                    customer_names.append(r.dest_partner_id.name)
                if r.dest_partner_ids:
                    # customer from sourcing
                    for customer in r.dest_partner_ids:
                        if r.dest_partner_id and not customer.id == r.dest_partner_id.id:
                            customer_names.append(customer.name)
                        else:
                            customer_names.append(customer.name)
                if customer_names:
                    # display PO and Customers
                    name += " (%s)" % ("; ".join(customer_names),)
                res.append((r.id, name))
            return res
        else:
            return super(purchase_order, self).name_get(cr, uid, ids, context=context)

    def _hook_copy_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        HOOK from purchase>purchase.py for COPY function. Modification of default copy values
        define which name value will be used
        '''
        return {
            'state': 'draft',
            'shipped': False,
            'invoiced': False,
            'invoice_ids': [],
            'picking_ids': [],
            'name': self.pool.get('ir.sequence').get(cr, uid, 'purchase.order'),
        }

    def copy_web(self, cr, uid, id, defaults=None, context=None):
        if defaults is None:
            defaults = {}
        defaults.update({'from_procurement': False, 'tender_id': False})
        is_direct = False
        if self.search_exists(cr, uid, [('id', '=', id), ('order_type', '=', 'direct')], context=context):
            company_partner_id = self.pool.get('res.users').get_current_company_partner_id(cr, uid)[0]
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, company_partner_id, ['delivery'])['delivery']
            defaults['order_type'] = 'regular'
            defaults['dest_partner_id'] = company_partner_id
            defaults['dest_address_id'] = cp_address_id
            defaults['customer_id'] = False
            is_direct = True
        if self.search_exists(cr, uid, [('id', '=', id), ('order_type', '=', 'loan_return')], context=context):
            defaults['order_type'] = 'loan'
        new_id = super(purchase_order, self).copy_web(cr, uid, id, defaults, context=context)
        if is_direct:
            name = self.read(cr, uid, new_id, ['name'], context=context)['name']
            self.log(cr, uid, new_id, _('PO %s created by duplication: Order Type changed from DPO to Regular') % name, action_xmlid='purchase.purchase_form_action')
        return new_id

    def copy(self, cr, uid, p_id, default=None, context=None):
        '''
        Remove loan_id field on new purchase.order
        '''
        if not default:
            default = {}
        if context is None:
            context = {}

        update_values = self._hook_copy_name(cr, uid, [p_id], context=context, default=default)
        default.update(update_values)
        # if the copy comes from the button duplicate
        if context.get('from_button'):
            default.update({'is_a_counterpart': False})
        default.update({'loan_id': False, 'merged_line_ids': False, 'partner_ref': False,
                        'po_confirmed': False, 'split_during_sll_mig': False, 'dest_partner_ids': False, 'order_line_mismatch': False,
                        'catalogue_not_applicable': False})
        if not context.get('keepOrigin', False):
            default.update({'origin': False})

        if not 'date_confirm' in default:
            default['date_confirm'] = False
        if not default.get('related_sourcing_id', False):
            default['related_sourcing_id'] = False
        if not 'rfq_state' in default:
            default['rfq_state'] = 'draft'

        new_id = super(purchase_order, self).copy(cr, uid, p_id, default, context=context)
        if new_id:
            data = self.read(cr, uid, new_id, ['order_line', 'delivery_requested_date'])
            if data['order_line'] and data['delivery_requested_date']:
                self.pool.get('purchase.order.line').write(cr, uid, data['order_line'], {'date_planned': data['delivery_requested_date']})

        return new_id

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        erase dates
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        fields_to_reset = [
            'delivery_requested_date', 'delivery_requested_date_modified', 'ready_to_ship_date',
            'date_order', 'delivery_confirmed_date', 'arrival_date', 'shipment_date', 'arrival_date',
            'date_approve', 'analytic_distribution_id', 'empty_po_cancelled', 'stock_take_date',
            'show_default_msg', 'order_line_mismatch'
        ]
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)
        default['commitment_ids'] = False
        res = super(purchase_order, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
        return res

    def onchange_requested_date(self, cr, uid, ids, part=False, date_order=False, requested_date=False, transport_lt=0, order_type=False, context=None):
        '''
        Set the confirmed date with the requested date if the first is not fill
        And the delivery_confirmed_date takes the value of the computed requested date by default only if order_type == 'purchase_list'
        '''
        if context is None:
            context = {}
        res = {}
        res['value'] = {}
        if order_type == 'purchase_list':
            res['value'].update({'delivery_confirmed_date': requested_date})
        else:
            res['value'].update({'delivery_confirmed_date': False})
        # compute ready to ship date
        res = common_requested_date_change(self, cr, uid, ids, part=part, date_order=date_order, requested_date=requested_date, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res

    def onchange_transport_lt(self, cr, uid, ids, requested_date=False, transport_lt=0, context=None):
        '''
        Fills the Ready to ship date

        SPRINT3 validated - YAML ok
        '''
        if context is None:
            context = {}
        res = {}
        # compute ready to ship date
        res = common_onchange_transport_lt(self, cr, uid, ids, requested_date=requested_date, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        return res

    def onchange_date_order(self, cr, uid, ids, part=False, date_order=False, transport_lt=0, context=None):
        '''
        date_order is changed (creation date)
        '''
        if context is None:
            context = {}
        res = {}

        # Check the stock_take_date
        std_err = ''
        prev_date_order = False
        for po in self.browse(cr, uid, ids, fields_to_fetch=['state', 'stock_take_date', 'order_line', 'date_order'], context=context):
            prev_date_order = po.date_order
            if po.state in ['draft', 'draft_p', 'validated'] and po.stock_take_date \
                    and po.stock_take_date > date_order:
                std_err = _('The Stock Take Date of %s is not consistent! It should not be later than its creation date') % (po.name,)
                break
            # Check the lines as well (was for the UC where Creation Date was modified)
            error_lines = []
            for pol in po.order_line:
                if pol.state in ['draft', 'validated', 'validated_n'] and pol.stock_take_date and \
                        pol.stock_take_date > date_order:
                    error_lines.append(str(pol.line_number))
            if error_lines:
                std_err = _('The Stock Take Date of the lines %s is not consistent! It should not be later than %s\'s creation date') \
                    % (', '.join(error_lines), po.name or _('the PO'))

        if std_err:
            res = {
                'warning': {'title': _('Error'), 'message': std_err},
                'value': {'date_order': prev_date_order}
            }
        else:
            # compute requested date
            res = common_onchange_date_order(self, cr, uid, ids, part=part, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)

        return res

    def onchange_transport_type(self, cr, uid, ids, part=False, transport_type=False, requested_date=False, context=None):
        '''
        transport type changed
        requested date is in the signature because it is needed for children on_change call

        '''
        if context is None:
            context = {}
        res = {}
        res = common_onchange_transport_type(self, cr, uid, ids, part=part, transport_type=transport_type, requested_date=requested_date, type=get_type(self), res=res, context=context)
        return res

    def requested_data(self, cr, uid, ids, context=None):
        '''
        data for requested
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Requested Delivery Date of all/selected Order lines ?'), }

    def estimated_data(self, cr, uid, ids, context=None):
        '''
        data for requested
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Estimated Date of all/selected Order lines ?'), }

    def confirmed_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Confirmed Delivery Date of all/selected Order lines ?'), }

    def stock_take_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed for change line wizard
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Date of Stock Take of all/selected draft Order lines ?'), }

    def update_date(self, cr, uid, ids, context=None):
        '''
        open the update lines wizard
        '''
        # we need the context
        if context is None:
            context = {}
        # field name
        field_name = context.get('field_name', False)
        if field_name == 'estimated':
            if self.search_exists(cr, uid, [('id', 'in', ids), ('delivery_requested_date_modified', '=', False), ('state', '!=', 'draft')], context=context):
                raise osv.except_osv(_('Warning'), _('Please fill the "Estimated Delivery Date" field.'))
            elif self.search_exists(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context):
                field_name = 'requested'
        assert field_name, 'The button is not correctly set.'
        # data
        data = getattr(self, field_name + '_data')(cr, uid, ids, context=context)
        name = data['name']
        model = 'update.lines'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)

    def action_invoice_get_or_create(self, cr, uid, ids, context=None):
        inv_obj = self.pool.get('account.invoice')
        ana_obj = self.pool.get('analytic.distribution')

        single = True
        if isinstance(ids, int):
            ids = [ids]
            single = False

        po_to_inv = {}
        inv_ids = inv_obj.search(cr, uid, [('state', '=', 'draft'), ('main_purchase_id', 'in', ids)], context=context)
        for inv in inv_obj.read(cr, uid, inv_ids, ['main_purchase_id'], context=context):
            po_to_inv[inv['main_purchase_id'][0]] = inv['id']

        for o in self.browse(cr, uid, ids):
            if o.id not in po_to_inv:
                inv_data = {
                    'name': o.partner_ref or o.name,
                    'reference': o.partner_ref or o.name,
                    'account_id': o.partner_id.property_account_payable.id,
                    'type': 'in_invoice',
                    'partner_id': o.partner_id.id,
                    'currency_id': o.pricelist_id.currency_id.id,
                    'address_invoice_id': o.partner_address_id.id,
                    'address_contact_id': o.partner_address_id.id,
                    'origin': o.name,
                    'fiscal_position': o.fiscal_position.id or o.partner_id.property_account_position.id,
                    'payment_term': o.partner_id.property_payment_term and o.partner_id.property_payment_term.id or False,
                    'company_id': o.company_id.id,
                    'main_purchase_id': o.id,
                    'purchase_ids': [(4, o.id)],
                    'from_supply': True,
                }

                if o.analytic_distribution_id:
                    distrib_id = ana_obj.copy(cr, uid, o.analytic_distribution_id.id, {})
                    ana_obj.create_funding_pool_lines(cr, uid, [distrib_id])
                    inv_data['analytic_distribution_id'] = distrib_id

                if o.order_type == 'in_kind':
                    inkind_journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'inkind'), ('is_current_instance', '=', True)])
                    if not inkind_journal_ids:
                        raise osv.except_osv(_('Error'), _('No In-kind Donation journal found!'))
                    inv_data['journal_id'] = inkind_journal_ids[0]
                    inv_data['is_inkind_donation'] = True
                else:
                    journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'purchase'), ('is_current_instance', '=', True)])
                    if not journal_ids:
                        raise osv.except_osv(_('Error !'),
                                             _('There is no purchase journal defined for this company: "%s" (id:%d)') % (o.company_id.name, o.company_id.id))
                    inv_data['journal_id'] = journal_ids[0]
                    if o.order_type == 'purchase_list':
                        inv_data['purchase_list'] = 1

                po_to_inv[o.id] = self.pool.get('account.invoice').create(cr, uid, inv_data, {'type': 'in_invoice', 'journal_type': 'purchase'})
                inv_obj.fetch_analytic_distribution(cr, uid, [po_to_inv[o.id]])
                self.infolog(cr, uid, 'Invoice on order (id:%d) created for PO %s' % (po_to_inv[o.id], o.name))
            else:
                self.infolog(cr, uid, 'Invoice on order (id:%d) already exists for PO %s' % (po_to_inv[o.id], o.name))
        return single and list(po_to_inv.values())[0] or po_to_inv

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on a purchase order
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        purchase = self.browse(cr, uid, ids[0], context=context)
        amount = purchase.amount_total or 0.0
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = purchase.currency_id and purchase.currency_id.id or company_currency
        # Get analytic_distribution_id
        distrib_id = purchase.analytic_distribution_id and purchase.analytic_distribution_id.id
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'purchase_id': purchase.id,
            'currency_id': currency or False,
            'state': 'cc',
            'posting_date': time.strftime('%Y-%m-%d'),
            'document_date': time.strftime('%Y-%m-%d'),
            'partner_type': purchase.partner_type,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Global analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def button_reset_distribution(self, cr, uid, ids, context=None):
        """
        Reset analytic distribution on all purchase order lines.
        To do this, just delete the analytic_distribution id link on each purchase order line.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        purchase_obj = self.pool.get(self._name + '.line')
        # Search purchase order lines
        to_reset = purchase_obj.search(cr, uid, [('order_id', 'in', ids)])
        purchase_obj.write(cr, uid, to_reset, {'analytic_distribution_id': False})
        return True

    def button_dummy(self, cr, uid, ids, context=None):
        return True

    def _copy_line_value(self, cr, uid, *args, **kwargs):
        new_data = {}
        order_line = kwargs['order_line']
        # Copy all fields except order_id and analytic_distribution_id
        fields = ['product_uom', 'price_unit', 'move_dest_id', 'product_qty', 'partner_id',
                  'confirmed_delivery_date', 'nomenclature_description', 'default_code',
                  'nomen_manda_0', 'nomen_manda_1', 'nomen_manda_2', 'nomen_manda_3',
                  'nomenclature_code', 'name', 'default_name', 'comment', 'date_planned',
                  'to_correct_ok', 'text_error', 'select_fo', 'project_ref', 'external_ref',
                  'nomen_sub_0', 'nomen_sub_1', 'nomen_sub_2', 'nomen_sub_3', 'nomen_sub_4',
                  'nomen_sub_5', 'linked_sol_id', 'change_price_manually', 'old_price_unit',
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
            new_data[field] = field_val

        # Set the analytic distribution
        distrib_id = False
        if order_line.analytic_distribution_id:
            distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, order_line.analytic_distribution_id.id)
        elif order_line.order_id.analytic_distribution_id:
            distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, order_line.order_id.analytic_distribution_id.id)

        new_data['analytic_distribution_id'] = distrib_id

        return new_data

    def _hook_order_infos(self, cr, uid, *args, **kwargs):
        '''
        Hook to change the values of the PO
        '''
        order_infos = kwargs['order_infos']
        order_id = kwargs['order_id']

        fields = ['invoice_method', 'minimum_planned_date', 'order_type',
                  'categ', 'priority', 'internal_type', 'arrival_date',
                  'transport_type', 'shipment_date', 'ready_to_ship_date',
                  'cross_docking_ok', 'delivery_confirmed_date',
                  'est_transport_lead_time',
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

    def do_merge(self, cr, uid, ids, tmpl_data=None, context=None):
        """
        To merge similar type of purchase orders.
        Orders will only be merged if:
        * Purchase Orders are in draft
        * Purchase Orders belong to the same partner
        * Purchase Orders are to have the same stock location, pricelist and order type
        * Direct Purchase Orders are to have the same destination partner
        Lines will only be merged if:
        * Order lines are exactly the same except for the quantity and unit

         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param ids: the ID or list of IDs
         @param context: A standard dictionary

         @return: new purchase order id

        """
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
        old_po_name = {}
        first_order_type = False
        first_dest_partner = None
        dest_partner_ids = []

        for porder in [order for order in self.browse(cr, uid, ids, context=context) if order.state == 'draft']:
            # group PO to be merged together
            order_key = make_key(porder, ('partner_id', 'pricelist_id', 'loan_id'))
            new_order = new_orders.setdefault(order_key, ({}, []))
            new_order[1].append(porder.id)
            order_infos = new_order[0]

            if not first_order_type:
                first_order_type = porder.order_type
            elif first_order_type and first_order_type != porder.order_type:
                raise osv.except_osv(_('Error'), _('The Order Type must be the same in all POs to be merged.'))
            if porder.order_type in ['regular', 'direct']:
                if first_dest_partner is None:
                    first_dest_partner = porder.dest_address_id and porder.dest_address_id.id or False
                elif first_dest_partner is not None and first_dest_partner != porder.dest_address_id.id:
                    raise osv.except_osv(_('Error'), _('The Address of the Destination Partner must be the same in all POs/DPOs to be merged.'))

            if porder.dest_partner_ids:
                dest_partner_ids = list(set(dest_partner_ids + [p.id for p in porder.dest_partner_ids]))
            old_po_name[porder.id] = porder.name
            if not order_infos:
                order_infos.update({
                    'origin': porder.origin,
                    'date_order': time.strftime('%Y-%m-%d'),
                    'partner_id': porder.partner_id.id,
                    'partner_address_id': porder.partner_address_id.id,
                    'dest_address_id': porder.dest_address_id.id,
                    'warehouse_id': porder.warehouse_id.id,
                    'pricelist_id': porder.pricelist_id.id,
                    'state': 'draft',
                    'order_line': [],
                    'notes': '%s' % (porder.notes or '',),
                    'fiscal_position': porder.fiscal_position and porder.fiscal_position.id or False,
                })
            else:
                if porder.notes:
                    order_infos['notes'] = (order_infos['notes'] or '') + ('\n%s' % (porder.notes,))
                if porder.origin:
                    order_infos['origin'] = (order_infos['origin'] or '') + ' ' + porder.origin
            order_infos = self._hook_order_infos(cr, uid, order_infos=order_infos, order_id=porder)

            for order_line in porder.order_line:
                if order_line.state != 'draft':
                    continue
                order_infos['order_line'].append((0, 0, self._copy_line_value(cr, uid, order_line=order_line)))

        return_info = {}
        for order_key, (order_data, old_ids) in new_orders.items():
            # skip merges with only one order
            if len(old_ids) < 2:
                continue

            # US-6144: Set the dest_partner_id and related_sourcing_id to the one of the template PO
            if tmpl_data and order_data['order_type'] in ['regular', 'direct']:
                order_data.update({
                    'dest_partner_id': tmpl_data.get('dest_partner_id', False),
                    'related_sourcing_id': tmpl_data.get('related_sourcing_id', False),
                })

            # Put all the customers
            if dest_partner_ids:
                order_data.update({'dest_partner_ids': [(6, 0, dest_partner_ids)]})

            # create the new order
            neworder_id = self.create(cr, uid, order_data)
            self.log(cr, uid, neworder_id, _('PO %s have been merged into %s.') % (', '.join([old_po_name.get(x, '') for x in old_ids]), self.read(cr, uid, neworder_id, ['name'])['name']), action_xmlid='purchase.purchase_form_action')
            return_info.update({neworder_id: old_ids})

            # make triggers pointing to the old orders point to the new order
            for old_po in self.pool.get('purchase.order').browse(cr, uid, old_ids, fields_to_fetch=['order_line'], context=context):
                reset_linked_sol_id = []
                cancel_pol = []
                for old_pol in old_po.order_line:
                    if old_pol.state == 'draft':
                        cancel_pol.append(old_pol.id)
                        if old_pol.linked_sol_id:
                            reset_linked_sol_id.append(old_pol.id)
                if reset_linked_sol_id:
                    self.pool.get('purchase.order.line').write(cr, uid, reset_linked_sol_id, {'linked_sol_id': False}, context=context)
                if cancel_pol:
                    wf_service.trg_validate(uid, 'purchase.order.line', cancel_pol, 'cancel', cr)

        return return_info

    def purchase_cancel(self, cr, uid, ids, context=None):
        '''
        Call the wizard to ask if you want to re-source the line
        '''
        wiz_obj = self.pool.get('purchase.order.cancel.wizard')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if context.get('rfq_ok', False):
            view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'rfq_cancel_wizard_form_view')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'purchase_override', 'purchase_order_cancel_wizard_form_view')[1]

        for po in self.browse(cr, uid, ids, context=context):
            if po.state == 'draft' and not po.order_line:  # for empty PO
                self.write(cr, uid, po.id, {'empty_po_cancelled': True}, context=context)
                return True

            for pol in po.order_line:
                vals = {'order_id': po.id}
                if context.get('rfq_ok', False) and po.tender_id:
                    pending_rfqs_same_tender = self.search(cr, uid, [('id', '!=', po.id), ('state', '!=', 'cancel'),
                                                                     ('tender_id', '=', po.tender_id.id)], context=context)
                    if not pending_rfqs_same_tender:
                        vals.update({'cancel_linked_tender': True})
                wiz_id = wiz_obj.create(cr, uid, vals, context=context)
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order.cancel.wizard',
                    'res_id': wiz_id,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'view_id': [view_id],
                    'target': 'new',
                    'context': context
                }

        return True

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check restriction on products
        '''
        if isinstance(ids, int):
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
        pol_obj = self.pool.get('purchase.order.line')
        v = {}
        # the domain on the onchange was replace by a several fields.function that you can retrieve in the
        # file msf_custom_settings/view/purchase_view.xml: domain="[('supplier', '=', True), ('id', '!=', company_id), ('check_partner_po', '=', order_type),  ('check_partner_rfq', '=', tender_id)]"
        w = {}
        local_market = None
        partner = partner_id and partner_obj.read(cr, uid, partner_id, ['partner_type', 'state']) or False

        if ids:
            order_types_dict = dict((x, y) for x, y in ORDER_TYPES_SELECTION)
            err = []
            for order in self.browse(cr, uid, ids, fields_to_fetch=['name', 'fixed_order_type', 'order_type', 'is_a_counterpart', 'order_line']):
                if order.is_a_counterpart and order_type not in ['loan', 'loan_return']:
                    err.append(_('%s: This purchase order is a loan counterpart. You cannot change its order type') % order['name'])
                elif order_type == 'loan_return':
                    err.append(_('%s: You can not select this Order Type manually') % order['name'])
                else:
                    json_info = json.loads(order.fixed_order_type)
                    if json_info and order_type not in json_info:
                        allowed_type = ' / '.join([_(order_types_dict.get(x)) for x in json_info])
                        err.append(
                            _('%s: Only %s order types are allowed for this purchase order') % (order.name, allowed_type))

                if err:
                    return {
                        'warning': {
                            'title': _('Error'),
                            'message': '\n'.join(x for x in err),
                        },
                        'value': {
                            'order_type': order.order_type,
                        }
                    }

                # Check if any PO line with an Service product has been sourced from a FO/IR
                if order.order_type == 'direct' and order_type != 'direct':
                    for pol in order.order_line:
                        if pol.linked_sol_id and pol.product_id and pol.product_id.type == 'service_recep':
                            return {
                                'value': {'order_type': order.order_type},
                                'warning': {
                                    'title': _('Error'),
                                    'message': _('The Order Type of this Purchase Order can not be changed. One of its lines has a Service Product sourced from a%s.') % (pol.linked_sol_id.procurement_request and _('n Internal Request') or _(' Field Order'))
                                },
                            }

        # check if the current PO was created from scratch :
        if order_type == 'direct':
            if not self.pool.get('purchase.order.line').search_exist(cr, uid, [('order_id', 'in', ids), ('linked_sol_id', '!=', False)]):
                order_type_value = self.read(cr, uid, ids, ['order_type'])
                order_type_value = order_type_value[0].get('order_type', 'regular') if order_type_value else 'regular'
                return {
                    'value': {'order_type': order_type_value},
                    'warning': {
                        'title': _('Error'),
                        'message': _('You cannot create a direct purchase order from scratch')
                    },
                }
        if order_type == 'loan_return':
            return {'value': {'order_type': False}, 'warning': {'title': _('Error'), 'message': _('You can not select this Order Type manually')}}

        if order_type not in ['loan', 'loan_return', 'in_kind', 'donation_st', 'donation_exp'] and partner and partner['state'] == 'phase_out':
            return {
                'value': {'partner_id': False},
                'warning': {'title': _('Error'), 'message': _('The selected Supplier is Phase Out, please select another Supplier')},
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

        if order_type in ['donation_exp', 'donation_st']:
            v['invoice_method'] = partner and partner['partner_type'] == 'section' and 'picking' or 'manual'
        elif order_type in ['loan', 'loan_return']:
            v['invoice_method'] = 'manual'
        elif order_type in ['direct']:
            v['invoice_method'] = 'order'
        elif order_type in ['in_kind', 'purchase_list']:
            v['invoice_method'] = 'picking'
        else:
            v['invoice_method'] = 'picking'

        company_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id

        if order_type == 'direct' and (not dest_partner_id or dest_partner_id == company_id):
            dest_partner_ids = self.pool.get('res.partner').search(cr, uid, [('available_on_po_dpo', '=', ids[0])])
            if not dest_partner_ids:
                return {
                    'value': {'order_type': False},
                    'warning': {
                        'title': _('Error'),
                        'message': _('Direct Purchase Order is not allowed on this order: not all lines are sourced for the same customer.'),
                    }
                }
            dest_partner_id = dest_partner_ids[0]
            v['dest_partner_id'] = dest_partner_id

        if order_type == 'direct' and dest_partner_id and dest_partner_id != company_id:
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, dest_partner_id, ['delivery'])['delivery']
            v.update({'dest_address_id': cp_address_id})
        elif order_type == 'direct':
            v.update({'dest_address_id': False, 'dest_partner_id': False})
        else:
            cp_address_id = self.pool.get('res.partner').address_get(cr, uid, company_id, ['delivery'])['delivery']
            v.update({'dest_address_id': cp_address_id, 'dest_partner_id': company_id})

        if partner and partner_id != local_market:
            if partner['partner_type'] in ('internal', 'esc') and order_type in ('regular', 'direct'):
                v['invoice_method'] = 'manual'
            elif partner['partner_type'] not in ('external', 'esc') and order_type == 'direct':
                v.update({'partner_address_id': False, 'partner_id': False, 'pricelist_id': False})
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

        if order_type == 'regular' and v['invoice_method'] == 'picking' and delivery_requested_date:
            v['cross_docking_ok'] = True

        if order_type == 'purchase_list' and delivery_requested_date:
            v.update({'delivery_confirmed_date': delivery_requested_date})
        # UF-1440: Add today's date if no date and you choose "purchase_list" PO
        elif order_type == 'purchase_list' and not delivery_requested_date:
            v.update({'delivery_requested_date': time.strftime('%Y-%m-%d'), 'delivery_confirmed_date': time.strftime('%Y-%m-%d')})
        else:
            v.update({'delivery_confirmed_date': False})

        if partner and (order_type not in COMPATS or partner['partner_type'] not in COMPATS[order_type]):
            w.update({
                'title': _('An error has occurred !'),
                'message': _('Partner type and order type are incompatible! Please change either order type or partner.'),
            })
            v.update({'order_type': 'regular'})

        # Check if there's source documents on lines
        if order_type in ['loan', 'loan_return', 'donation_exp', 'donation_st', 'in_kind'] and \
                pol_obj.search(cr, uid, [('order_id', 'in', ids), ('origin', '!=', False), ('state', '!=', 'cancel')]):
            return {
                'value': {'order_type': 'regular'},
                'warning': {
                    'title': _('Error'),
                    'message': _('You can\'t change the Order Type to Loan, Donation to prevent losses, Standard donation or In Kind Donation if a line has a Source Document')
                },
            }

        return {'value': v, 'warning': w}

    def onchange_partner_id(self, cr, uid, ids, partner_id=False, date_order=False, transport_lt=False, order_type=False, context=None, *a, **b):
        '''
        Fills the Requested and Confirmed delivery dates
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        if not partner_id:
            return {'value': {'partner_address_id': False, 'fiscal_position': False, 'catalogue_exists_text': '', 'catalogue_display_tab': False}}

        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')

        partner = partner_obj.browse(cr, uid, partner_id)
        if order_type not in ['loan', 'loan_return', 'in_kind', 'donation_st', 'donation_exp'] and partner.state == 'phase_out':
            return {
                'value': {'partner_id': False},
                'warning': {
                    'title': _('Error'),
                    'message': _('The selected Supplier is Phase Out, please select another Supplier')}
            }

        addr = partner_obj.address_get(cr, uid, [partner_id], ['default'])
        pricelist = partner.property_product_pricelist_purchase.id
        fiscal_position = partner.property_account_position and partner.property_account_position.id or False
        res = {'value': {'partner_address_id': addr['default'], 'pricelist_id': pricelist, 'fiscal_position': fiscal_position}}

        if ids:
            # Check the restriction of product in lines
            for order in self.browse(cr, uid, ids):
                for line in order.order_line:
                    if line.product_id:
                        res, test = product_obj._on_change_restriction_error(cr, uid, line.product_id.id, field_name='partner_id', values=res, vals={'partner_id': partner_id})
                        if test:
                            res.setdefault('value', {}).update({'partner_address_id': False})
                            return res
        if partner.partner_type in ('internal', 'esc'):
            res['value']['invoice_method'] = 'manual'

        res = common_onchange_partner_id(self, cr, uid, ids, part=partner_id, date_order=date_order, transport_lt=transport_lt, type=get_type(self), res=res, context=context)
        # reset confirmed date
        res.setdefault('value', {}).update({'delivery_confirmed_date': False, 'catalogue_exists_text': '', 'catalogue_display_tab': False})

        return res

    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, order_type, dest_address_id):
        '''
        Change the destination address to the destination address of the company if False
        '''
        res = {}
        if not warehouse_id:
            res = {'value': {'dest_address_id': False, 'cross_docking_ok': False}}

        if not res.get('value', {}).get('dest_address_id') and order_type != 'direct':
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

        if isinstance(ids, int):
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

    def order_line_change(self, cr, uid, ids, order_line, show_default_msg=None, partner_id=None):

        assert (len(ids) == 1)

        values = {'no_line': True}

        if order_line:
            values = {'no_line': False}

        # Also update the 'state' of the purchase order
        info = self.read(cr, uid, ids, ['state', 'not_beyond_validated', 'show_default_msg', 'catalogue_exists_text', 'catalogue_display_tab', 'partner_id'])
        if partner_id == info[0]['partner_id'][0]:
            values['catalogue_exists_text'] = info[0]['catalogue_exists_text']
            values['catalogue_display_tab'] = info[0]['catalogue_display_tab']
        else:
            values['catalogue_exists_text'] = ''
            values['catalogue_display_tab'] = False

        values['state'] = info[0]['state']
        values['not_beyond_validated'] = info[0]['not_beyond_validated']

        if show_default_msg is not None and not values['not_beyond_validated'] and show_default_msg != info[0]['show_default_msg']:
            # show_default_msg will become read-only but the current value is not saved
            cr.execute("update purchase_order set show_default_msg=%s where id = %s", (show_default_msg, info[0]['id']))

        # We need to fetch and return also the "display strings" for state
        # as it might be needed to update the read-only view...
        raw_display_strings_state = dict(PURCHASE_ORDER_STATE_SELECTION)
        display_strings_state = dict([(k, _(v)) \
                                      for k, v in list(raw_display_strings_state.items())])

        display_strings = {}
        display_strings["state"] = display_strings_state

        return {'value': values, "display_strings": display_strings}

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

    def check_analytic_distribution(self, cr, uid, ids, context=None, create_missing=False):
        """
        Check analytic distribution validity for given PO.
        Also check that partner have a donation account (is PO is in_kind)
        """
        # Objects
        pol_obj = self.pool.get('purchase.order.line')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        po_line_ids = pol_obj.search(cr, uid, [('oder_id', 'in', id), ('state', '!=', 'cancelled')], context=context)
        if po_line_ids:
            return pol_obj.check_analytic_distribution(cr, uid, po_line_ids, context=context, create_missing=create_missing)
        return True

    def get_so_ids_from_po_ids(self, cr, uid, ids, context=None):
        '''
        receive the list of purchase order ids
        return the list of sale order ids corresponding
        '''
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        so_ids = set()
        if ids:  # Even if the browse is None, it would still go in the for in some cases and trigger an error
            for po in self.browse(cr, uid, ids, context=context):
                for pol in po.order_line:
                    if pol.linked_sol_id:
                        so_ids.add(pol.linked_sol_id.order_id.id)

        return list(so_ids)

    def get_sol_ids_from_po_ids(self, cr, uid, ids, context=None):
        '''
        receive the list of purchase order ids
        return the list of sale order line ids corresponding
        '''
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        sol_ids = set()
        for po in self.browse(cr, uid, ids, context=context):
            for pol in po.order_line:
                if pol.linked_sol_id:
                    sol_ids.add(pol.linked_sol_id.id)

        return list(sol_ids)

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

    def has_stockable_product(self, cr, uid, ids, *args):
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

    def ensure_object(self, cr, uid, model, value):
        if isinstance(value, int):
            value = self.pool.get(model).browse(cr, uid, value)
        return value

    def get_reason_type_id(self, cr, uid, order, context=None):

        def get_reference(reason):
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', reason)[1]

        order = self.ensure_object(cr, uid, 'purchase.order', order)

        reason_type_id = False
        if order.order_type in ('regular', 'purchase_list', 'direct') and \
                order.partner_id.partner_type in ('internal', 'intermission', 'section', 'esc'):
            reason_type_id = get_reference('reason_type_internal_supply')
        elif order.order_type in ('regular', 'purchase_list', 'direct'):
            reason_type_id = get_reference('reason_type_external_supply')
        elif order.order_type == 'loan':
            reason_type_id = get_reference('reason_type_loan')
        elif order.order_type == 'loan_return':
            reason_type_id = get_reference('reason_type_loan_return')
        elif order.order_type == 'donation_st':
            reason_type_id = get_reference('reason_type_donation')
        elif order.order_type == 'donation_exp':
            reason_type_id = get_reference('reason_type_donation_expiry')
        elif order.order_type == 'in_kind':
            reason_type_id = get_reference('reason_type_in_kind_donation')
        return reason_type_id

    def create_picking(self, cr, uid, order, context=None, sourced_on_dpo=False, sourced_dpo_id=False):
        if context is None:
            context = {}

        order = self.ensure_object(cr, uid, 'purchase.order', order)

        values = {
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.in'),
            'origin': order.name + ((order.origin and (':' + order.origin)) or ''),
            'type': 'in',
            'partner_id2': order.partner_id.id,
            'address_id': order.partner_address_id.id or False,
            'invoice_state': '2binvoiced' if order.invoice_method == 'picking' else 'none',
            'purchase_id': order.id,
            'company_id': order.company_id.id,
            'move_lines': [],
        }

        if sourced_on_dpo:
            values['dpo_incoming'] = True
        if sourced_dpo_id:
            values['dpo_id_incoming'] = sourced_dpo_id
        reason_type_id = self.get_reason_type_id(cr, uid, order, context)
        if reason_type_id:
            values.update({'reason_type_id': reason_type_id})

        return self.pool.get('stock.picking').create(cr, uid, values, context=context)

    def create_new_incoming_line(self, cr, uid, incoming_id, pol, context=None):
        '''
        create new stock move for incoming shipment
        '''
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')

        pol = self.ensure_object(cr, uid, 'purchase.order.line', pol)
        incoming = self.ensure_object(cr, uid, 'stock.picking', incoming_id)
        if not pol:
            return False

        values = {
            'name': ''.join((pol.order_id.name, ': ', (pol.name or ''))),
            'product_id': pol.product_id.id,
            'product_qty': pol.product_qty,
            'product_uos_qty': pol.product_qty,
            'product_uom': pol.product_uom.id,
            'product_uos': pol.product_uom.id,
            'location_id': pol.order_id.partner_id.property_stock_supplier.id,
            'location_dest_id': pol.reception_dest_id.id,
            'picking_id': incoming.id,
            'move_dest_id': pol.move_dest_id.id,
            'state': 'draft',
            'purchase_line_id': pol.id,
            'company_id': pol.order_id.company_id.id,
            'price_currency_id': pol.order_id.pricelist_id.currency_id.id,
            'price_unit': pol.price_unit,
            'date': pol.confirmed_delivery_date,
            'date_expected': pol.confirmed_delivery_date or pol.date_planned,
            'comment': pol.comment,
            'line_number': pol.line_number,
        }
        if pol.from_dpo_line_id:
            values['dpo_line_id'] = pol.from_dpo_line_id

        if incoming.reason_type_id:
            values.update({'reason_type_id': incoming.reason_type_id.id})

        ctx = context.copy()
        ctx['bypass_store_function'] = [
            ('stock.picking', ['dpo_incoming', 'dpo_out', 'overall_qty', 'line_state'])
        ]

        return move_obj.create(cr, uid, values, context=ctx)

    def create_new_int_line(self, cr, uid, internal_id, pol, incoming_move_id=False, context=None):
        '''
        create new stock.move for INT
        '''
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')

        pol = self.ensure_object(cr, uid, 'purchase.order.line', pol)
        internal = self.ensure_object(cr, uid, 'stock.picking', internal_id)
        if not pol:
            return False

        # compute source location:
        src_location = pol.reception_dest_id

        # compute destination location
        dest = self.pool.get('purchase.order.line').final_location_dest(cr, uid, pol, context=context)

        values = {
            'name': ''.join((pol.order_id.name, ': ', (pol.name or ''))),
            'product_id': pol.product_id.id,
            'product_qty': pol.product_qty,
            'product_uos_qty': pol.product_qty,
            'product_uom': pol.product_uom.id,
            'product_uos': pol.product_uom.id,
            'location_id': src_location.id,
            'location_dest_id': dest,
            'picking_id': internal.id,
            'move_dest_id': pol.move_dest_id.id,
            'state': 'draft',
            'purchase_line_id': pol.id,
            'company_id': pol.order_id.company_id.id,
            'price_currency_id': pol.order_id.pricelist_id.currency_id.id,
            'price_unit': pol.price_unit,
            'date': pol.confirmed_delivery_date,
            'date_expected': pol.confirmed_delivery_date or pol.date_planned,
            'line_number': pol.line_number,
            'comment': pol.comment,
            'linked_incoming_move': incoming_move_id,
        }

        if internal.reason_type_id:
            values.update({'reason_type_id': internal.reason_type_id.id})

        ctx = context.copy()
        ctx['bypass_store_function'] = [
            ('stock.picking', ['dpo_incoming', 'dpo_out', 'overall_qty', 'line_state'])
        ]

        return move_obj.create(cr, uid, values, context=ctx)

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the PO to done state
        '''
        wf_service = netsvc.LocalService("workflow")
        so_obj = self.pool.get('sale.order')

        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        order_lines = []
        for order in self.browse(cr, uid, ids, context=context):
            for line in order.order_line:
                order_lines.append(line.id)

            # Done loan counterpart
            if order.loan_id and order.loan_id.state not in ('cancel', 'done') and not context.get('loan_id', False) == order.id:
                loan_context = context.copy()
                loan_context.update({'loan_id': order.id})
                so_obj.set_manually_done(cr, uid, order.loan_id.id, all_doc=all_doc, context=loan_context)

        if all_doc:
            # Detach the PO from his workflow and set the state to done
            for order_id in self.browse(cr, uid, ids, context=context):
                if order_id.tender_id:
                    raise osv.except_osv(_('Error'), _('You cannot \'Close\' a Request for Quotation attached to a tender. Please make the tender %s to \'Closed\' before !') % order_id.tender_id.name)
                for pol in order_id.order_line:
                    if pol.state not in ('done', 'cancel', 'cancel_r'):
                        wf_service.trg_validate(uid, 'purchase.order.line', pol.id, 'cancel', cr)

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
        rescur_obj = self.pool.get('res.currency')
        partnerprice_obj = self.pool.get('pricelist.partnerinfo')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if use_new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()

        try:
            self.write(cr, uid, ids, {
                'update_in_progress': True,
            }, context=context)
            if use_new_cursor:
                cr.commit()

            po = self.browse(cr, uid, ids[0], fields_to_fetch=['currency_id', 'date_order'], context=context)

            pol_ids = pol_obj.search(cr, uid, [
                ('order_id', 'in', ids),
                ('product_id', '!=', False),
                ('state', '=', 'draft'),
            ], context=context)

            for pol in pol_obj.browse(cr, uid, pol_ids, context=context):

                # Check only products with defined SoQ quantity
                domain = [('name', '=', pol.order_id.partner_id.id),
                          ('product_id', '=', pol.product_id.id),
                          ('active', '=', True)]

                sup_ids = sup_obj.search(cr, uid, domain, context=context)
                if not sup_ids and not pol.product_id.soq_quantity:
                    continue

                good_quantity = None
                good_price = None
                initial_rounding = None
                data_to_write = {}

                if sup_ids:
                    domain = [('suppinfo_id', 'in', sup_ids),
                              '|', ('valid_from', '<=', po.date_order),
                              ('valid_from', '=', False),
                              '|', ('valid_till', '>=', po.date_order),
                              ('valid_till', '=', False)]

                    pl_ids = partnerprice_obj.search(cr, uid, domain, order='min_quantity asc, id desc', context=context)

                    if pl_ids:

                        t_min_qty_price = {}

                        min_applied = False
                        first = True
                        for pl in partnerprice_obj.browse(cr, uid, pl_ids, context=context):
                            if pol.product_uom == pl.uom_id:
                                pl_minqty = pl.min_quantity
                                price_conv = pl.price
                                rounding_conv = pl.rounding
                                min_order_qty = pl.min_order_qty
                            else:
                                pl_minqty = uom_obj._compute_qty_obj(cr, uid, pl.uom_id, pl.min_quantity, pol.product_uom, context=context)
                                price_conv = uom_obj._compute_price(cr, uid, pl.uom_id.id, pl.price, pol.product_uom.id)
                                rounding_conv = uom_obj._compute_qty_obj(cr, uid, pl.uom_id, pl.rounding, pol.product_uom, context=context)
                                min_order_qty = uom_obj._compute_qty_obj(cr, uid, pl.uom_id, pl.min_order_qty, pol.product_uom, context=context)

                            if pl_minqty in t_min_qty_price:
                                # duplicated min qty lines
                                continue

                            t_min_qty_price[pl_minqty] = price_conv
                            if first and pol.product_qty < min_order_qty:
                                # if po qty is less than the 1st min_order_qty
                                good_quantity = min_order_qty
                                tmp_qty = min_order_qty
                                good_price = price_conv
                                initial_rounding = rounding_conv
                                min_applied = True

                            if not min_applied and pol.product_qty >= pl_minqty:
                                # several lines may apply, the last one is the good one
                                initial_rounding = rounding_conv
                                initial_min_order_qty = min_order_qty

                            first = False

                        if not min_applied:
                            tmp_qty = pol.product_qty
                            if pol.product_qty < initial_min_order_qty:
                                # we found a line, apply min_order_qty
                                tmp_qty = initial_min_order_qty
                                good_quantity = initial_min_order_qty

                        if initial_rounding:
                            if tmp_qty % initial_rounding:
                                # apply rounding
                                good_quantity = (tmp_qty - (tmp_qty % initial_rounding)) + initial_rounding

                        if good_quantity:
                            # quantiy changed by soq or by min order qty
                            l_key = list(t_min_qty_price.keys())
                            l_key.sort()
                            for min_qty in l_key:
                                if good_quantity >= min_qty:
                                    good_price = t_min_qty_price[min_qty]

                        if good_price and pl.currency_id != po.currency_id:
                            good_price = rescur_obj.compute(cr, uid, pl.currency_id.id, po.currency_id.id, good_price, False, context=context)

                else:  # Get SoQ value from product not supplier catalogue
                    soq_rounding = pol.product_id.soq_quantity
                    if pol.product_uom != pol.product_id.uom_id:
                        soq_rounding = uom_obj._compute_qty_obj(cr, uid, pol.product_id.uom_id, soq_rounding, pol.product_uom, context=context)

                    if pol.product_qty % soq_rounding:
                        good_quantity = (pol.product_qty - (pol.product_qty % soq_rounding)) + soq_rounding

                if good_quantity and good_quantity != pol.product_qty:
                    data_to_write['product_qty'] = good_quantity

                    if good_price and abs(good_price -  pol.price_unit) > 0.00001:
                        data_to_write['price_unit'] = good_price

                if data_to_write:
                    pol_obj.write(cr, uid, pol.id, data_to_write, context=context)

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

    def remove_line_tax(self, cr, uid, ids, context=None):
        pol_obj = self.pool.get('purchase.order.line')
        pol_ids = pol_obj.search(cr, uid, [('order_id', 'in', ids), ('state', 'not in', ['confirmed', 'cancel', 'cancel_r', 'done']), ('taxes_id', '!=', False)], context=context)
        if pol_ids:
            pol_obj.write(cr, uid, pol_ids, {'taxes_id': [(6, 0, [])]}, context=context)
        return True

    def generate_po_from_rfq(self, cr, uid, ids, context=None):
        '''
        generate a po from the selected request for quotation
        '''
        # Objects
        pol_obj = self.pool.get('purchase.order.line')

        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        rfq = self.browse(cr, uid, ids[0], context=context)
        if not rfq.amount_total:
            raise osv.except_osv(
                _('Error'),
                _('Generation of PO aborted because no price defined on lines.'),
            )

        # copy the po with rfq_ok set to False
        if rfq.origin:
            po_orign = '%s:%s' % (rfq.origin, rfq.name)
        else:
            po_orign = rfq.name

        # Check cross_docking_ok:
        cross_docking_ok = False
        cr.execute("""SELECT pl.id FROM purchase_order_line pl 
                        LEFT JOIN sale_order_line sl ON pl.linked_sol_id = sl.id 
                        LEFT JOIN sale_order s ON sl.order_id = s.id 
                        LEFT JOIN stock_location l ON s.location_requestor_id = l.id 
                    WHERE pl.linked_sol_id IS NOT NULL AND (s.procurement_request = 'f' OR 
                        (s.procurement_request = 't' AND l.usage = 'customer')) AND pl.order_id = %s""", (rfq.id,))
        if cr.fetchone():
            cross_docking_ok = True

        # Create a PO and/or a DPO depending on if one or more lines has a service product and is sourced from a FO
        new_po_id = False
        context.update({'generate_po_from_rfq': True})
        for rfq_line in rfq.order_line:
            # Ignore cancelled lines and lines with a price of 0
            if rfq_line.state in ('cancel', 'cancel_r') or rfq_line.rfq_line_state in ('cancel', 'cancel_r') or \
                    rfq_line.price_unit == 0.00:
                continue

            order_type = rfq.order_type
            nomen_srv = self.pool.get('product.nomenclature').search(cr, uid, [('name', '=', 'SRV'), ('type', '=', 'mandatory'),
                                                                               ('level', '=', 0)], limit=1)
            if order_type in ['regular', 'purchase_list'] and nomen_srv and \
                    ((rfq.from_procurement and not rfq_line.linked_sol_id and not rfq_line.select_fo) or
                     (rfq_line.linked_sol_id and not rfq_line.linked_sol_id.procurement_request) or
                     (rfq_line.select_fo and not rfq_line.select_fo.procurement_request)) and \
                    ((rfq_line.product_id and rfq_line.product_id.type == 'service_recep') or
                     rfq_line.nomen_manda_0.id == nomen_srv[0]):
                order_type = 'direct'

            po_domain = [
                ('partner_id', '=', rfq.partner_id.id),
                ('state', '=', 'draft'),
                ('origin', '=', po_orign),
                ('rfq_ok', '=', False),
                ('order_type', '=', order_type),
            ]
            new_po_ids = self.search(cr, uid, po_domain, context=context)
            if not new_po_ids:
                new_po_vals = {'name': False, 'rfq_ok': False, 'origin': po_orign, 'order_type': order_type, 'order_line': False}
                new_po_id = self.copy(cr, uid, ids[0], new_po_vals, context=dict(context, keepOrigin=True))
                # log message describing the PO creation
                new_po_data = self.read(cr, uid, new_po_id, ['name'], context=context)
                self.log(cr, uid, new_po_id, _('The Purchase Order %s has been generated from Request for Quotation.') % new_po_data['name'])
            else:
                new_po_id = new_po_ids[0]

            pol_values = {'origin': rfq.origin, 'cross_docking_ok': cross_docking_ok, 'order_id': new_po_id}

            # AD will be copied in copy_data for the PO line, the same AD should not and will not be re-used
            if not rfq_line.analytic_distribution_id and rfq_line.linked_sol_id and\
                    not rfq_line.linked_sol_id.procurement_request:
                pol_values['analytic_distribution_id'] = rfq_line.linked_sol_id.analytic_distribution_id.id or rfq_line.linked_sol_id.order_id.analytic_distribution_id.id or False
            elif rfq_line.analytic_distribution_id:
                pol_values['analytic_distribution_id'] = rfq_line.analytic_distribution_id.id

            pol_obj.copy(cr, uid, rfq_line.id, pol_values, context=context)
        context.pop('generate_po_from_rfq')

        return new_po_id

    def create_commitment_voucher_from_po(self, cr, uid, ids, cv_date, context=None):
        '''
        Create a new commitment voucher from the given PO
        @param ids id of the Purchase order
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        commit_id = False
        for po in self.pool.get('purchase.order').browse(cr, uid, ids, context=context):
            engagement_ids = self.pool.get('account.analytic.journal').search(cr, uid, [
                ('type', '=', 'engagement'),
                ('instance_id', '=', self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.id)
            ], limit=1, context=context)

            po_partner_type = po.partner_id.partner_type
            if po_partner_type == 'external':
                cv_type = 'external'
            elif po_partner_type == 'section':
                cv_type = 'intersection'
            elif po_partner_type == 'intermission':
                cv_type = 'intermission'
            else:
                cv_type = 'manual'
            vals = {
                'journal_id': engagement_ids and engagement_ids[0] or False,
                'currency_id': po.currency_id and po.currency_id.id or False,
                'partner_id': po.partner_id and po.partner_id.id or False,
                'purchase_id': po.id or False,
                'type': cv_type,
            }
            # prepare some values
            period_ids = get_period_from_date(self, cr, uid, cv_date, context=context)
            period_id = period_ids and period_ids[0] or False
            if not period_id:
                raise osv.except_osv(_('Error'), _('No period found for given date: %s.') % (cv_date, ))
            vals.update({
                'date': cv_date,
                'period_id': period_id,
            })
            commit_id = self.pool.get('account.commitment').create(cr, uid, vals, context=context)

            # Display a message to inform that a commitment was created
            commit_data = self.pool.get('account.commitment').read(cr, uid, commit_id, ['name'], context=context)
            message = _("Supplier Commitment Voucher %s has been created.") % commit_data.get('name', '')
            self.pool.get('account.commitment').log(cr, uid, commit_id, message, action_xmlid='analytic_distribution.action_account_commitment_tree')
            self.infolog(cr, uid, message)

            # Add analytic distribution from purchase
            if po.analytic_distribution_id:
                new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, po.analytic_distribution_id.id, {}, context=context)
                # Update this distribution not to have a link with purchase but with new commitment
                if new_distrib_id:
                    self.pool.get('analytic.distribution').write(cr, uid, [new_distrib_id],
                                                                 {'purchase_id': False, 'commitment_id': commit_id}, context=context)
                    # Create funding pool lines if needed
                    self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [new_distrib_id], context=context)
                    # Update commitment with new analytic distribution
                    self.pool.get('account.commitment').write(cr, uid, [commit_id], {'analytic_distribution_id': new_distrib_id}, context=context)

        return commit_id

    def _finish_commitment(self, cr, uid, ids, context=None):
        """
        Change commitment(s) to Done state from given Purchase Order.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Browse PO
        for po in self.browse(cr, uid, ids, context=context):
            # Change commitment state if exists
            if po.commitment_ids:
                for com in po.commitment_ids:
                    if com.type != 'manual':
                        self.pool.get('account.commitment').action_commitment_done(cr, uid, [x.id for x in po.commitment_ids], context=context)
        return True

    def action_done(self, cr, uid, ids, context=None):
        """
        Delete commitment from purchase before 'done' state.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Change commitments state
        # Sidestep UF-1183
        # If ONE invoice is in draft state, raise an error!
        to_process = []
        for po in self.browse(cr, uid, ids):
            have_draft_invoice = False
            for inv in po.invoice_ids:
                if inv.state == 'draft':
                    have_draft_invoice = True
                    break
            if not have_draft_invoice or not po.invoice_ids:
                to_process.append(po.id)
        self._finish_commitment(cr, uid, to_process, context=context)
        return super(purchase_order, self).action_done(cr, uid, ids, context=context)

    def check_continue_sourcing(self, cr, uid, ids, context=None):
        '''
        Warn the user if the RfQ, coming from an FO, has both service and non-service products
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        pol_obj = self.pool.get('purchase.order.line')

        for rfq_id in ids:
            nomen_srv = self.pool.get('product.nomenclature').search(cr, uid, [('name', '=', 'SRV'), ('type', '=', 'mandatory'),
                                                                               ('level', '=', 0)], limit=1)
            has_srv_domain = [('order_id', '=', rfq_id), ('state', 'not in', ['cancel', 'cancel_r']),
                              ('rfq_line_state', 'not in', ['cancel', 'cancel_r']), ('price_unit', '!=', 0.00),
                              '|', ('product_id.type', '=', 'service_recep'), ('nomen_manda_0', '=', nomen_srv[0]),
                              '|', '|',
                              '&', '&', ('order_id.from_procurement', '=', True), ('linked_sol_id', '=', False),
                              ('select_fo', '=', False),
                              '&', ('linked_sol_id', '!=', False), ('linked_sol_id.procurement_request', '=', False),
                              '&', ('select_fo', '!=', False), ('select_fo.procurement_request', '=', False)]
            srv_rfq_line_from_fo_ids = pol_obj.search(cr, uid, has_srv_domain, context=context)
            has_not_srv_domain = [('order_id', '=', rfq_id), ('id', 'not in', srv_rfq_line_from_fo_ids),
                                  ('price_unit', '!=', 0.00), ('state', 'not in', ['cancel', 'cancel_r']),
                                  ('rfq_line_state', 'not in', ['cancel', 'cancel_r'])]
            has_not_srv_prod = pol_obj.search_exist(cr, uid, has_not_srv_domain, context=context)
            if srv_rfq_line_from_fo_ids and has_not_srv_prod:
                wiz_id = self.pool.get('rfq.has.service.not.service.product.wizard').create(cr, uid, {'rfq_id': rfq_id}, context=context)
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'purchase', 'rfq_has_service_not_service_product_wizard_form_view')[1]

                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'rfq.has.service.not.service.product.wizard',
                    'res_id': wiz_id,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'view_id': [view_id],
                    'target': 'new',
                    'context': context
                }

        return self.continue_sourcing(cr, uid, ids, context=context)

    def continue_sourcing(self, cr, uid, ids, context=None):
        '''
        On RfQ updated continue sourcing process (create PO)
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        self.generate_po_from_rfq(cr, uid, ids, context=context)
        pol_obj = self.pool.get('purchase.order.line')
        for rfq in self.read(cr, uid, ids, ['id'], context=context):
            rfq_lines_to_close = pol_obj.search(cr, uid, [('rfq_line_state', 'not in', ['cancel', 'cancel_r']),
                                                          ('order_id', '=', rfq['id'])], context=context)
            pol_obj.write(cr, uid, rfq_lines_to_close, {'rfq_line_state': 'done'}, context=context)

        return True

    def add_audit_line(self, cr, uid, order_id, old_state, new_state, context=None):
        """
        If state is modified, add an audittrail.log.line
        @param cr: Cursor to the database
        @param uid: ID of the user that change the state
        @param order_id: ID of the sale.order on which the state is modified
        @param new_state: The value of the new state
        @param context: Context of the call
        @return: True
        """
        audit_line_obj = self.pool.get('audittrail.log.line')
        audit_seq_obj = self.pool.get('audittrail.log.sequence')
        fld_obj = self.pool.get('ir.model.fields')
        model_obj = self.pool.get('ir.model')
        rule_obj = self.pool.get('audittrail.rule')
        log = 1

        if context is None:
            context = {}

        domain = [
            ('model', '=', 'purchase.order'),
            ('res_id', '=', order_id),
        ]

        object_id = model_obj.search(cr, uid, [('model', '=', 'purchase.order')], context=context)[0]
        # If the field 'state_hidden_sale_order' is not in the fields to trace, don't trace it.
        fld_ids = fld_obj.search(cr, uid, [
            ('model', '=', 'purchase.order'),
            ('name', '=', 'state'),
        ], context=context)
        rule_domain = [('object_id', '=', object_id)]
        if not old_state:
            rule_domain.append(('log_create', '=', True))
        else:
            rule_domain.append(('log_write', '=', True))
        rule_ids = rule_obj.search(cr, uid, rule_domain, context=context)
        if fld_ids and rule_ids:
            for fld in rule_obj.browse(cr, uid, rule_ids[0], context=context).field_ids:
                if fld.id == fld_ids[0]:
                    break
            else:
                return

        log_sequence = audit_seq_obj.search(cr, uid, domain)
        if log_sequence:
            log_seq = audit_seq_obj.browse(cr, uid, log_sequence[0]).sequence
            log = log_seq.get_id(code_or_id='id')

        # Get readable value
        new_state_txt = False
        old_state_txt = False
        for st in PURCHASE_ORDER_STATE_SELECTION:
            if new_state_txt and old_state_txt:
                break
            if new_state == st[0]:
                new_state_txt = st[1]
            if old_state == st[0]:
                old_state_txt = st[1]

        vals = {
            'user_id': uid,
            'method': 'write',
            'name': _('State'),
            'object_id': object_id,
            'res_id': order_id,
            'fct_object_id': False,
            'fct_res_id': False,
            'sub_obj_name': '',
            'field_id': fld_ids[0],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'field_description': 'Order state',
            'trans_field_description': _('Order state'),
            'new_value': new_state,
            'new_value_text': new_state_txt or new_state,
            'new_value_fct': False,
            'old_value': old_state,
            'old_value_text': old_state_txt or old_state,
            'old_value_fct': '',
            'log': log,
        }
        audit_line_obj.create(cr, uid, vals, context=context)

    def export_line_mismatch(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        po_name = ''
        if ids:
            po_name = ' ' + self.read(cr, uid, ids[0], ['name'], context=context)['name']

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'report_line_mismatch',
            'datas': {'target_filename': 'PO vs. Catalogue Mismatch%s' % (po_name,)},
            'context': context
        }


purchase_order()


class stock_invoice_onshipping(osv.osv_memory):
    _inherit = "stock.invoice.onshipping"

    def create_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        res = super(stock_invoice_onshipping, self).create_invoice(cr, uid, ids, context=context)
        purchase_obj = self.pool.get('purchase.order')
        picking_obj = self.pool.get('stock.picking')
        for pick_id in res:
            pick = picking_obj.browse(cr, uid, pick_id, context=context)
            if pick.purchase_id:
                purchase_obj.write(cr, uid, [pick.purchase_id.id], {
                    'invoice_ids': [(4, res[pick_id])]}, context=context)
        return res


stock_invoice_onshipping()


class po_custom_text(osv.osv):
    _name = 'po.custom.text'

    _columns = {
        'po_text': fields.char(size=1000, string='PO Custom Text'),
    }

    _defaults = {
        'po_text': '',
    }


po_custom_text()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
