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

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
import logging
import threading

from osv import fields, osv
from tools.translate import _
from osv.orm import browse_record
import decimal_precision as dp
import netsvc
import pooler

from . import SALE_ORDER_STATE_SELECTION
from . import SALE_ORDER_SPLIT_SELECTION
from . import SALE_ORDER_LINE_STATE_SELECTION
from . import SALE_ORDER_LINE_DISPLAY_STATE_SELECTION
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from account_override.period import get_period_from_date


class sale_shop(osv.osv):
    _name = "sale.shop"
    _description = "Sales Shop"
    _columns = {
        'name': fields.char('Shop Name', size=64, required=True),
        'payment_default_id': fields.many2one('account.payment.term', 'Default Payment Term', required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse'),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist'),
        'project_id': fields.many2one('account.analytic.account', 'Analytic Account', domain=[('parent_id', '!=', False)]),
        'company_id': fields.many2one('res.company', 'Company', required=False),
    }
    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'sale.shop', context=c),
    }

sale_shop()

class sale_order(osv.osv):
    _name = "sale.order"
    _description = "Sales Order"

    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        '''
        overwrite to allow search on customer and self instance
        '''
        new_dom = []
        product_id = False
        for x in domain:
            if x[0] == 'product_id':
                product_id = x[2]
            else:
                new_dom.append(x)

        ret = super(sale_order, self)._where_calc(cr, uid, new_dom, active_test=active_test, context=context)
        if product_id and isinstance(product_id, int):
            ret.tables.append('"sale_order_line"')
            ret.joins.setdefault('"sale_order"', [])
            ret.joins['"sale_order"'] += [('"sale_order_line"', 'id', 'order_id', 'LEFT JOIN')]
            ret.where_clause.append(''' "sale_order_line"."product_id" = %s  ''')
            ret.where_clause_params.append(product_id)
        return ret

    def copy(self, cr, uid, id, default=None, context=None):
        """
        Copy the sale.order. When copy the sale.order:
            * re-set the sourcing logs,
            * re-set the loan_id field
            * re-set split flag to original value (field order flow) if
              not in default

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param order_id: ID of the sale.order to copy
        :param default: Default values to put on the new sale.order
        :param context: Context of the call

        :return ID of the new sale.order
        :rtype integer
        """
        if context is None:
            context = {}

        if default is None:
            default = {}

        # if the copy comes from the button duplicate
        if context.get('from_button'):
            default.update({'is_a_counterpart': False})

        if 'loan_id' not in default:
            default.update({'loan_id': False})

        default.update({
            'order_policy': 'picking',
            'active': True,
            'sourcing_trace': '',
            'sourcing_trace_ok': False,
            'claim_name_goods_return': '',
            'draft_cancelled': False,
            'stock_take_date': False,
        })

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

        default.update({
            'state': 'draft',
            'shipped': False,
            'invoice_ids': [],
            'picking_ids': [],
            'date_confirm': False,
        })
        return super(sale_order, self).copy(cr, uid, id, default=default, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if 'order_line' not in default:
            default['order_line'] = []
            sol_obj = self.pool.get('sale.order.line')
            line_ids = sol_obj.search(cr, uid, [('order_id', '=', id), ('state', 'not in', ['cancel', 'cancel_r'])], context=context)
            line_ids.sort()
            for line_id in line_ids:
                d = sol_obj.copy_data(cr, uid, line_id, context=context)
                if d:
                    default['order_line'].append((0, 0, d))

        return super(sale_order, self).copy_data(cr, uid, id, default, context)

    def _amount_line_tax(self, cr, uid, line, context=None):
        val = 0.0
        for c in self.pool.get('account.tax').compute_all(cr, uid, line.tax_id, line.price_unit * (1-(line.discount or 0.0)/100.0), line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)['taxes']:
            val += c.get('amount', 0.0)
        return val

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            if not order.procurement_request:
                val = val1 = 0.0
                cur = order.pricelist_id.currency_id
                for line in order.order_line:
                    if line.state not in ('cancel', 'cancel_r'):
                        val1 += line.price_subtotal
                        val += self._amount_line_tax(cr, uid, line, context=context)
                res[order.id]['amount_tax'] = cur_obj.round(cr, uid, cur.rounding, val)
                res[order.id]['amount_untaxed'] = cur_obj.round(cr, uid, cur.rounding, val1)
                res[order.id]['amount_total'] = res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

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
                    if invoice.state not in ('paid', 'inv_close'):
                        res[sale.id] = False
                        break
                if not sale.invoice_ids:
                    res[sale.id] = False
        return res

    def _invoiced_search(self, cursor, user, obj, name, args, context=None):
        if not len(args):
            return []
        clause = ''
        sale_clause = ''
        no_invoiced = False
        for arg in args:
            if arg[1] == '=':
                if arg[2]:
                    clause += 'AND inv.state in (\'paid\', \'inv_close\') OR (sale.state != \'draft\' AND (sale.order_type != \'regular\' OR part.partner_type = \'internal\'))'
                else:
                    clause += 'AND inv.state != \'cancel\' AND sale.state != \'cancel\'  AND inv.state not in  (\'paid\', \'inv_close\') AND sale.order_type = \'regular\''
                    no_invoiced = True

        cursor.execute('SELECT rel.order_id ' \
                       'FROM sale_order_invoice_rel AS rel, account_invoice AS inv, sale_order AS sale, res_partner AS part ' + sale_clause + \
                       'WHERE rel.invoice_id = inv.id AND rel.order_id = sale.id AND sale.partner_id = part.id ' + clause) # not_a_user_entry
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

    def _picked_rate(self, cr, uid, ids, name, arg, context=None):
        uom_obj = self.pool.get('product.uom')
        if not ids:
            return {}
        res = {}

        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = 0.00
            amount_total = 0.00
            amount_received = 0.00
            for line in order.order_line:
                if line.state == 'cancel':
                    continue

                amount_total += line.product_uom_qty*line.price_unit
                for move in line.move_ids:
                    if move.state == 'done' and move.location_dest_id.usage == 'customer':
                        move_qty = uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, line.product_uom.id)
                        amount_received += move_qty*line.price_unit

            if amount_total:
                res[order.id] = (amount_received/amount_total)*100

        return res

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('sale.order.line').browse(cr, uid, ids, fields_to_fetch=['order_id'], context=context):
            result[line.order_id.id] = True
        return result.keys()

    def _get_order_state(self, cr, uid, ids, context=None):
        # recompute FO amount total only if state switches to cancel(_r)
        result = {}
        for line in self.pool.get('sale.order.line').browse(cr, uid, ids, fields_to_fetch=['order_id', 'state'],context=context):
            if line.state in ('cancel', 'cancel_r'):
                result[line.order_id.id] = True
        return result.keys()

    def _check_browse_param(self, param, method):
        """
        Returns an error message if the parameter is not a
        browse_record instance

        :param param: The parameter to test
        :param method: Name of the method that call the _check_browse_param()

        :return True
        """
        if not isinstance(param, browse_record):
            raise osv.except_osv(
                _('Bad parameter'),
                _("""Exception when call the method '%s' of the object '%s' :
The parameter '%s' should be an browse_record instance !""") % (method, self._name, param)
            )

        return True

    def _get_noinvoice(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for sale in self.browse(cr, uid, ids):
            res[sale.id] = sale.order_type != 'regular' or sale.partner_id.partner_type == 'internal'
        return res

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
            ('model', '=', 'sale.order'),
            ('res_id', '=', order_id),
        ]

        object_id = model_obj.search(cr, uid, [('model', '=', 'sale.order')], context=context)[0]
        # If the field 'state_hidden_sale_order' is not in the fields to trace, don't trace it.
        fld_ids = fld_obj.search(cr, uid, [
            ('model', '=', 'sale.order'),
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
        for st in SALE_ORDER_STATE_SELECTION:
            if new_state_txt and old_state_txt:
                break
            if new_state == st[0]:
                new_state_txt = _(st[1])
            if old_state == st[0]:
                old_state_txt = _(st[1])

        vals = {
            'user_id': uid,
            'method': 'write',
            'name': _('State'),
            'object_id': object_id,
            'res_id': order_id,
            'fct_object_id': False,
            'fct_res_id': False,
            'sub_obj_name': '',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'field_id': fld_ids[0],
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




    def _get_no_line(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for order in self.read(cr, uid, ids, ['order_line'], context=context):
            res[order['id']] = True
            if order['order_line']:
                res[order['id']] = False
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

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    def _check_empty_line(self, cr, uid, ids, context=None):
        '''
        Check if all lines have a quantity larger than 0.00
        '''
        # Objects
        line_obj = self.pool.get('sale.order.line')

        line_ids = line_obj.search(cr, uid, [
            ('order_id', 'in', ids),
            ('state', 'not in', ['draft', 'cancel', 'cancel_r']),
            ('order_id.import_in_progress', '=', False),
            ('product_uom_qty', '<=', 0.00),
        ], limit=1, order='NO_ORDER', context=context)

        if line_ids:
            return False

        return True

    def _get_state_hidden(self, cr, uid, ids, field_name, arg, context=None):
        '''
        get function values
        '''
        if context is None:
            context = {}

        result = {}
        for so in self.browse(cr, uid, ids, context=context):
            if so.draft_cancelled:
                result[so.id] = 'cancel'
            else:
                result[so.id] = so.state

        return result

    def _get_less_advanced_sol_state(self, cr, uid, ids, field_name, arg, context=None):
        """
        Get the less advanced state of the sale order lines
        Used to compute sale order state
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        sols_obj = self.pool.get('sale.order.line.state')
        sos_obj = self.pool.get('sale.order.state')

        res = {}
        for so in self.browse(cr, uid, ids, fields_to_fetch=['draft_cancelled', 'state'], context=context):
            sol_states = set()
            cr.execute("select distinct(state) from sale_order_line where order_id=%s", (so.id, ))
            for x in cr.fetchall():
                sol_states.add(x[0])

            if so.draft_cancelled:
                res[so.id] = 'cancel'
            elif not sol_states:
                res[so.id] = 'draft'
            elif all([s.startswith('cancel') for s in sol_states]): # if all lines are cancelled then the FO is cancelled
                res[so.id] = 'cancel'
            else:  # else compute the less advanced state:
                sol_states.discard('cancel')
                sol_states.discard('cancel_r')

                res[so.id] = self.pool.get('sale.order.line.state').get_less_advanced_state(cr, uid, ids, sol_states, context=context)

                if res[so.id] == 'draft': # set the draft-p state ?
                    draft_sequence = self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, 'draft', context=context)
                    # do we have a line further then draft in our FO ?
                    if any([self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, s, context=context) > draft_sequence for s in sol_states]):
                        res[so.id] = 'draft_p'
                elif res[so.id] == 'validated': # set the validated-p state ?
                    validated_sequence = self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, 'validated', context=context)
                    # do we have a line further then validated in our FO ?
                    if any([self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, s, context=context) > validated_sequence for s in sol_states]):
                        res[so.id] = 'validated_p'
                elif res[so.id].startswith('sourced'): # set the source-p state ?
                    sourced_sequence = self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, 'sourced', context=context)
                    # do we have a line further then sourced in our FO ?
                    if any([self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, s, context=context) > sourced_sequence for s in sol_states]):
                        res[so.id] = 'sourced_p'
                    else:
                        res[so.id] = 'sourced'
                elif res[so.id] == 'confirmed': # set the source-p state ?
                    confirmed_sequence = self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, 'confirmed', context=context)
                    # do we have a line further then confirmed in our FO ?
                    if any([self.pool.get('sale.order.line.state').get_sequence(cr, uid, ids, s, context=context) > confirmed_sequence for s in sol_states]):
                        res[so.id] = 'confirmed_p'

            # SO state must not go back:
            if sos_obj.get_sequence(cr, uid, [], res[so.id]) < sos_obj.get_sequence(cr, uid, [], so.state):
                res[so.id] = so.state
                # add the '_p' if needed:
                if res[so.id] in ['draft', 'validated', 'confirmed']:
                    current_state_sequence = sols_obj.get_sequence(cr, uid, [], so.state)
                    has_line_further = any([sols_obj.get_sequence(cr, uid, [], s, context=context) > current_state_sequence for s in sol_states])
                    if has_line_further:
                        res[so.id] = '%s_p' % res[so.id]


            # add audit line in track change if state has changed:
            if so.state != res[so.id]:
                self.add_audit_line(cr, uid, so.id, so.state, res[so.id], context=context)

        return res

    def _get_line_count(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of non-cancelled line(s) for the SO
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for so_id in ids:
            res[so_id] = 0

        cr.execute("""
            SELECT order_id, COUNT(*) FROM sale_order_line 
            WHERE order_id IN %s AND state NOT IN ('cancel', 'cancel_r') GROUP BY order_id
        """, (tuple(ids),))
        for so in cr.fetchall():
            res[so[0]] = so[1]

        return res

    def _get_short_client_ref(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return a shortened version of Customer Reference, with only the Order Reference
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        ref_by_order = {}
        for so in self.browse(cr, uid, ids, fields_to_fetch=['client_order_ref'], context=context):
            ref_by_order[so.id] = so.client_order_ref and so.client_order_ref.split('.')[-1] or ''

        return ref_by_order

    def _get_msg_big_qty(self, cr, uid, ids, name, arg, context=None):
        res = {}
        max_value = self.pool.get('sale.order.line')._max_value

        for id in ids:
            res[id] = ''

        cr.execute('''select line_number, order_id from sale_order_line
            where
                order_id in %s
                and ( product_uom_qty >= %s or product_uom_qty*price_unit >= %s)
                and state not in ('cancel', 'cancel_r')
            ''', (tuple(ids), max_value, max_value))
        for x in cr.fetchall():
            res[x[1]] += ' #%s' % x[0]

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
                target_object='sale.order' and
                target_id in %s
            group by target_id""", (tuple(ids),))
        for x in cr.fetchall():
            ret[x[0]] = x[1]

        return ret

    def _get_fake(self, cr, uid, ids, name, args, context=None):
        '''
        Fake method for 'product_id' field
        '''
        res = {}
        if not ids:
            return res
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

    _columns = {
        'name': fields.char('Order Reference', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}, select=True, sort_column='id'),
        'origin': fields.char('Source Document', size=512, help="Reference of the document that generated this sales order request."),
        'state': fields.function(_get_less_advanced_sol_state, string='Order State', method=True, type='selection', selection=SALE_ORDER_STATE_SELECTION, readonly=True,
                                 store = {
                                     'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line','draft_cancelled'], 10),
                                     'sale.order.line': (_get_order, ['state'], 10),
                                 },
                                 select=True, help="Gives the state of the quotation or sales order. \nThe exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'."
                                 ),
        'state_hidden_sale_order': fields.function(_get_state_hidden, method=True, type='selection', selection=SALE_ORDER_STATE_SELECTION, readonly=True, string='State'),
        'date_order': fields.date('Ordered Date', required=True, readonly=True, select=True),
        'create_date': fields.date('Creation Date', readonly=True, select=True, help="Date on which sales order is created."),
        'date_confirm': fields.date('Confirmation Date', readonly=True, select=True, help="Date on which sales order is confirmed."),
        'user_id': fields.many2one('res.users', 'Salesman', states={'draft': [('readonly', False)]}, select=True),
        'incoterm': fields.many2one('stock.incoterms', 'Incoterm', help="Incoterm which stands for 'International Commercial terms' implies its a series of sales terms which are used in the commercial transaction."),
        'picking_policy': fields.selection([('direct', 'Partial Delivery'), ('one', 'Complete Delivery')],
                                           'Picking Policy', required=True, readonly=True, states={'draft': [('readonly', False)]}, help="""If you don't have enough stock available to deliver all at once, do you accept partial shipments or not?"""),
        'project_id': fields.many2one('account.analytic.account', 'Analytic Account', readonly=True, states={'draft': [('readonly', False)]}, help="The analytic account related to a sales order."),
        'invoice_ids': fields.many2many('account.invoice', 'sale_order_invoice_rel', 'order_id', 'invoice_id', 'Invoices', readonly=True, help="This is the list of invoices that have been generated for this sales order. The same sales order may have been invoiced in several times (by line for example)."),
        'picking_ids': fields.one2many('stock.picking', 'sale_id', 'Related Picking', readonly=True, help="This is a list of picking that has been generated for this sales order."),
        'shipped': fields.boolean('Delivered', readonly=True, help="It indicates that the sales order has been delivered. This field is updated only after the scheduler(s) have been launched."),
        'note': fields.text('Notes'),

        'amount_untaxed': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Untaxed Amount',
                                          store = {
            'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
            'sale.order.line': [
                (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
                (_get_order_state, ['state'], 10),
            ]
        },
            multi='sums', help="The amount without tax."),
        'amount_tax': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes',
                                      store = {
            'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
            'sale.order.line': [
                (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
                (_get_order_state, ['state'], 10),
            ]
        },
            multi='sums', help="The tax amount."),
        'amount_total': fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total',
                                        store = {
            'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line'], 10),
            'sale.order.line': [
                (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
                (_get_order_state, ['state'], 10),
            ]
        },
            multi='sums', help="The total amount."),

        'payment_term': fields.many2one('account.payment.term', 'Payment Term'),
        'fiscal_position': fields.many2one('account.fiscal.position', 'Fiscal Position'),
        'company_id': fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        # we increase the size of client_order_ref field from 64 to 128
        'client_order_ref': fields.char('Customer Reference', size=128),
        'short_client_ref': fields.function(_get_short_client_ref, method=True, string='Customer Reference', type='char', size=64, store=False),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'draft_p': [('readonly', False)], 'validated': [('readonly', False)]}),
        'partner_id': fields.many2one('res.partner', 'Customer', required=True, change_default=True, select=True),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), ],
                                       string='Order Type', required=True, readonly=True),
        'loan_id': fields.many2one('purchase.order', string='Linked loan', readonly=True),
        'priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        'categ': fields.selection(ORDER_CATEGORY, string='Order category', required=True, readonly=True, states={'draft': [('readonly', False)]}, add_empty=True),
        # we increase the size of the 'details' field from 30 to 86
        'details': fields.char(size=86, string='Details', readonly=True),
        'invoiced': fields.function(_invoiced, method=True, string='Paid',
                                    fnct_search=_invoiced_search, type='boolean', help="It indicates that an invoice has been paid."),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'noinvoice': fields.function(_get_noinvoice, method=True, string="Don't create an invoice", type='boolean'),
        'picked_rate': fields.function(_picked_rate, method=True, string='Picked', type='float'),
        'loan_duration': fields.integer(string='Loan duration', help='Loan duration in months', readonly=False),
        'yml_module_name': fields.char(size=1024, string='Name of the module which created the object in the yml tests', readonly=True),
        'company_id2': fields.many2one('res.company', 'Company', select=1),
        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=False),
        'partner_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'draft_p': [('readonly', False)], 'validated': [('readonly', False)]}, help="Invoice address for current field order."),
        'partner_order_id': fields.many2one('res.partner.address', 'Ordering Contact', readonly=True, required=True, states={'draft': [('readonly', False)], 'draft_p': [('readonly', False)], 'validated': [('readonly', False)]}, help="The name and address of the contact who requested the order or quotation."),
        'partner_shipping_id': fields.many2one('res.partner.address', 'Shipping Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'draft_p': [('readonly', False)], 'validated': [('readonly', False)]}, help="Shipping address for current field order."),
        'pricelist_id': fields.many2one('product.pricelist', 'Currency', required=True, readonly=True, states={'draft': [('readonly', False)], 'draft_p': [('readonly', False)], 'validated': [('readonly', False)]}, help="Currency for current field order."),
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
        'split_type_sale_order': fields.selection(SALE_ORDER_SPLIT_SELECTION, required=True, readonly=True, internal=1),
        'original_so_id_sale_order': fields.many2one('sale.order', 'Original Field Order', readonly=True),
        'active': fields.boolean('Active', readonly=True),
        'product_id': fields.function(_get_fake, method=True, type='many2one', relation='product.product', string='Product', help='Product to find in the lines', store=False, readonly=True),
        'no_line': fields.function(_get_no_line, method=True, type='boolean', string='No line'),
        'manually_corrected': fields.function(_get_manually_corrected, method=True, type='boolean', string='Manually corrected'),
        'is_a_counterpart': fields.boolean('Counterpart?', help="This field is only for indicating that the order is a counterpart"),
        'fo_created_by_po_sync': fields.boolean('FO created by PO after SYNC', readonly=True),
        'fo_to_resource': fields.boolean(string='FO created to resource FO in exception', readonly=True),
        'parent_order_name': fields.char(size=64, string='Parent order name', help='In case of this FO is created to re-source a need, this field contains the name of the initial FO (before split).'),
        'sourced_references': fields.one2many(
            'sync.order.label',
            'order_id',
            string='FO/IR sourced',
        ),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'stock_take_date': fields.date(string='Date of Stock Take', required=False),
        'claim_name_goods_return': fields.char(string='Customer Claim Name', help='Name of the claim that created the IN-replacement/-missing which created the FO', size=512),
        'draft_cancelled': fields.boolean(string='State', readonly=True),
        'line_count': fields.function(_get_line_count, method=True, type='integer', string="Line count", store=False),
        'msg_big_qty': fields.function(_get_msg_big_qty, type='char', string='Lines with 10 digits total amounts', method=1),
        'nb_creation_message_nr': fields.function(_get_nb_creation_message_nr, type='integer', method=1, string='Number of NR creation messages'),
    }

    _defaults = {
        'picking_policy': 'direct',
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'draft',
        'user_id': lambda obj, cr, uid, context: uid,
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'sale.order'),
        'partner_invoice_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['invoice'])['invoice'],
        'partner_order_id': lambda self, cr, uid, context: context.get('partner_id', False) and  self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['contact'])['contact'],
        'partner_shipping_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
        'order_type': lambda *a: 'regular',
        'invoice_quantity': lambda *a: 'procurement',
        'priority': lambda *a: 'normal',
        'categ': lambda *a: False,
        'loan_duration': lambda *a: 2,
        'company_id2': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
        'order_policy': lambda *a: 'picking',
        'split_type_sale_order': 'original_sale_order',
        'active': True,
        'no_line': lambda *a: True,
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'draft_cancelled': False,
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique !'),
    ]

    _constraints = [
        (_check_empty_line, 'All lines must have a quantity larger than 0.00', ['order_line']),
    ]

    _order = 'id desc'

    def _check_stock_take_date(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Do not prevent modification during synchro
        if not context.get('sync_update_execution') and not context.get('sync_message_execution'):
            for so in self.browse(cr, uid, ids, context=context):
                if so.state in ['draft', 'draft_p', 'validated', 'sourced', 'sourced_p', 'confirmed', 'confirmed_p'] \
                        and so.stock_take_date and so.stock_take_date > so.date_order:
                    raise osv.except_osv(
                        _('Error'),
                        _('The Stock Take Date of %s is not consistent! It should not be later than its creation date')
                        % (so.name,)
                    )

        return True

    # Form filling
    def unlink(self, cr, uid, ids, context=None):
        '''
        Check if the status of the unlinked FO is allowed for unlink.
        '''
        for order in self.read(cr, uid, ids, ['state', 'procurement_request'], context=context):
            if order['state'] not in ('draft', 'cancel'):
                type = order['procurement_request'] and _('Internal Request') or _('Field order')
                raise osv.except_osv(_('Error'), _('Only Draft and Canceled %s can be deleted.') % type)

        sale_orders = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in sale_orders:
            if s['state'] in ['draft', 'cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Sales Order(s) which are already confirmed !'))
        return osv.osv.unlink(self, cr, uid, unlink_ids, context=context)

    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        cr.execute('select id from sale_order_line where order_id IN %s and state=%s', (tuple(ids), 'cancel'))
        line_ids = map(lambda x: x[0], cr.fetchall())
        self.write(cr, uid, ids, {'state': 'draft', 'invoice_ids': [], 'shipped': 0})
        self.pool.get('sale.order.line').write(cr, uid, line_ids, {'invoiced': False, 'state': 'draft', 'invoice_lines': [(6, 0, [])]})
        wf_service = netsvc.LocalService("workflow")
        for inv_id in ids:
            # Deleting the existing instance of workflow for SO
            wf_service.trg_delete(uid, 'sale.order', inv_id, cr)
            wf_service.trg_create(uid, 'sale.order', inv_id, cr)
        for sale in self.browse(cr, uid, ids):
            sale_order_label = _('IR') if sale.procurement_request else _('FO')  # UFTP-93
            message = _("The %s '%s' has been set in draft state.") % (sale_order_label, sale.name,)
            self.log(cr, uid, sale.id, message)
        return True

    def onchange_partner_id_orig(self, cr, uid, ids, part):
        if not part:
            return {'value': {'partner_invoice_id': False, 'partner_shipping_id': False, 'partner_order_id': False, 'payment_term': False, 'fiscal_position': False}}

        addr = self.pool.get('res.partner').address_get(cr, uid, [part], ['delivery', 'invoice', 'contact'])
        part = self.pool.get('res.partner').browse(cr, uid, part)
        pricelist = part.property_product_pricelist and part.property_product_pricelist.id or False
        payment_term = part.property_payment_term and part.property_payment_term.id or False
        fiscal_position = part.property_account_position and part.property_account_position.id or False
        dedicated_salesman = part.user_id and part.user_id.id or uid
        val = {
            'partner_invoice_id': addr['invoice'],
            'partner_order_id': addr['contact'],
            'partner_shipping_id': addr['delivery'],
            'payment_term': payment_term,
            'fiscal_position': fiscal_position,
            'user_id': dedicated_salesman,
        }
        if pricelist:
            val['pricelist_id'] = pricelist
        return {'value': val}

    def onchange_partner_id(self, cr, uid, ids, part=False, order_type=False, *a, **b):
        '''
        Set the intl_customer_ok field if the partner is an ESC or an international partner
        '''
        res = self.onchange_partner_id_orig(cr, uid, ids, part)

        if part and order_type:
            p_obj = self.pool.get('res.partner')
            p_domain = [
                ('id', '=', part),
                ('customer', '=', True),
                ('check_partner_so', '=', {'order_type': order_type, 'partner_id': part}),
            ]
            if not p_obj.search(cr, uid, p_domain, limit=1, order='NO_ORDER'):
                res.setdefault('value', {})
                res['value'].update({
                    'partner_id': False,
                    'partner_type': False,
                    'partner_order_id': False,
                    'partner_invoice_id': False,
                    'partner_shipping_id': False,
                    'pricelist_id': False,
                })
                res['warning'] = {
                    'title': _('Bad partner'),
                    'message': _('You cannot select this partner because it\'s not a customer or have a partner type not compatible with order type'),
                }

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

    def shipping_policy_change(self, cr, uid, ids, policy, context=None):
        if not policy:
            return {}
        inv_qty = 'order'
        if policy == 'prepaid':
            inv_qty = 'order'
        elif policy == 'picking':
            inv_qty = 'procurement'
        return {'value': {'invoice_quantity': inv_qty}}

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Remove the possibility to make a SO to user's company
        '''
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request'):
            for obj in self.read(cr, uid, ids, ['procurement_request']):
                if not obj['procurement_request']:
                    self._check_own_company(cr, uid, vals['partner_id'], context=context)

        if 'partner_id' in vals:
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], fields_to_fetch=['property_product_pricelist', 'partner_type'], context=context)
            if partner.partner_type in ('internal', 'intermission', 'section'):
                vals['pricelist_id'] = partner.property_product_pricelist.id

        for order in self.browse(cr, uid, ids, context=context):
            if order.yml_module_name == 'sale':
                continue
            partner = self.pool.get('res.partner').browse(cr, uid, vals.get('partner_id', order.partner_id.id))
            if vals.get('order_type', order.order_type) != 'regular' or (vals.get('order_type', order.order_type) == 'regular' and partner.partner_type == 'internal'):
                vals['order_policy'] = 'manual'
            else:
                vals['order_policy'] = 'picking'

        if vals.get('order_policy', False):
            if vals['order_policy'] == 'prepaid':
                vals.update({'invoice_quantity': 'order'})
            elif vals['order_policy'] == 'picking':
                vals.update({'invoice_quantity': 'procurement'})

        res = super(sale_order, self).write(cr, uid, ids, vals, context=context)

        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, ids, context=context)

        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        # Don't allow the possibility to make a SO to my owm company
        if 'partner_id' in vals and not context.get('procurement_request') and not vals.get('procurement_request'):
            self._check_own_company(cr, uid, vals['partner_id'], context=context)

        if not 'pricelist_id' in vals and vals.get('partner_id'):
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'], fields_to_fetch=['property_product_pricelist', 'partner_type'], context=context)
            if partner.partner_type in ('internal', 'intermission', 'section'):
                vals['pricelist_id'] = partner.property_product_pricelist.id

        if 'partner_id' in vals:
            partner = self.pool.get('res.partner').browse(cr, uid, vals['partner_id'])
            if vals.get('order_type', 'regular') != 'regular' or (vals.get('order_type', 'regular') == 'regular' and partner.partner_type == 'internal'):
                vals['order_policy'] = 'manual'
            else:
                vals['order_policy'] = 'picking'


        if vals.get('order_policy', False):
            if vals['order_policy'] == 'prepaid':
                vals.update({'invoice_quantity': 'order'})
            if vals['order_policy'] == 'picking':
                vals.update({'invoice_quantity': 'procurement'})

        sale_id = super(sale_order, self).create(cr, uid, vals, context)

        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, sale_id, context=context)
        return sale_id

    def button_dummy(self, cr, uid, ids, context=None):
        return True

    #FIXME: the method should return the list of invoices created (invoice_ids)
    # and not the id of the last invoice created (res). The problem is that we
    # cannot change it directly since the method is called by the sales order
    # workflow and I suppose it expects a single id...
    def _inv_get(self, cr, uid, order, context=None):
        return {}

    def _make_invoice(self, cr, uid, order, lines, context=None):
        journal_obj = self.pool.get('account.journal')
        inv_obj = self.pool.get('account.invoice')
        obj_invoice_line = self.pool.get('account.invoice.line')
        if context is None:
            context = {}

        journal_ids = journal_obj.search(cr, uid, [('type', '=', 'sale'), ('company_id', '=', order.company_id.id)], limit=1)
        if not journal_ids:
            raise osv.except_osv(_('Error !'),
                                 _('There is no sales journal defined for this company: "%s" (id:%d)') % (order.company_id.name, order.company_id.id))
        a = order.partner_id.property_account_receivable.id
        pay_term = order.payment_term and order.payment_term.id or False
        invoiced_sale_line_ids = self.pool.get('sale.order.line').search(cr, uid, [('order_id', '=', order.id), ('invoiced', '=', True)], context=context)
        from_line_invoice_ids = []
        for invoiced_sale_line_id in self.pool.get('sale.order.line').browse(cr, uid, invoiced_sale_line_ids, context=context):
            for invoice_line_id in invoiced_sale_line_id.invoice_lines:
                if invoice_line_id.invoice_id.id not in from_line_invoice_ids:
                    from_line_invoice_ids.append(invoice_line_id.invoice_id.id)
        for preinv in order.invoice_ids:
            if preinv.state not in ('cancel',) and preinv.id not in from_line_invoice_ids:
                for preline in preinv.invoice_line:
                    inv_line_id = obj_invoice_line.copy(cr, uid, preline.id, {'invoice_id': False, 'price_unit': -preline.price_unit})
                    lines.append(inv_line_id)
        inv = {
            'name': order.client_order_ref or '',
            'origin': order.name,
            'type': 'out_invoice',
            'reference': order.client_order_ref or order.name,
            'account_id': a,
            'partner_id': order.partner_id.id,
            'journal_id': journal_ids[0],
            'address_invoice_id': order.partner_invoice_id.id,
            'address_contact_id': order.partner_order_id.id,
            'invoice_line': [(6, 0, lines)],
            'currency_id': order.pricelist_id.currency_id.id,
            'comment': order.note,
            'payment_term': pay_term,
            'fiscal_position': order.fiscal_position.id or order.partner_id.property_account_position.id,
            'date_invoice': context.get('date_invoice',False),
            'company_id': order.company_id.id,
            'user_id': order.user_id and order.user_id.id or False
        }
        inv.update(self._inv_get(cr, uid, order))
        inv_id = inv_obj.create(cr, uid, inv, context=context)
        data = inv_obj.onchange_payment_term_date_invoice(cr, uid, [inv_id], pay_term, time.strftime('%Y-%m-%d'))
        if data.get('value', False):
            inv_obj.write(cr, uid, [inv_id], data['value'], context=context)
        inv_obj.button_compute(cr, uid, [inv_id])
        return inv_id

    def manual_invoice(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        wf_service = netsvc.LocalService("workflow")
        inv_ids = set()
        inv_ids1 = set()
        for id in ids:
            for record in self.pool.get('sale.order').browse(cr, uid, id).invoice_ids:
                inv_ids.add(record.id)
        # inv_ids would have old invoices if any
        for id in ids:
            wf_service.trg_validate(uid, 'sale.order', id, 'manual_invoice', cr)
            for record in self.pool.get('sale.order').browse(cr, uid, id).invoice_ids:
                inv_ids1.add(record.id)
        inv_ids = list(inv_ids1.difference(inv_ids))

        res = mod_obj.get_object_reference(cr, uid, 'account', 'invoice_form')
        res_id = res and res[1] or False,

        return {
            'name': 'Customer Invoices',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': 'account.invoice',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': inv_ids and inv_ids[0] or False,
        }

    def action_invoice_create(self, cr, uid, ids, grouped=False, states=['confirmed', 'done', 'exception'], date_inv = False, context=None):
        res = False
        invoices = {}
        invoice_ids = []
        picking_obj = self.pool.get('stock.picking')
        invoice = self.pool.get('account.invoice')
        obj_sale_order_line = self.pool.get('sale.order.line')
        if context is None:
            context = {}
        # If date was specified, use it as date invoiced, usefull when invoices are generated this month and put the
        # last day of the last month as invoice date
        if date_inv:
            context['date_inv'] = date_inv
        for o in self.browse(cr, uid, ids, context=context):
            lines = []
            for line in o.order_line:
                if line.invoiced:
                    continue
                elif (line.state in states):
                    lines.append(line.id)
            created_lines = obj_sale_order_line.invoice_line_create(cr, uid, lines)
            if created_lines:
                invoices.setdefault(o.partner_id.id, []).append((o, created_lines))
        if not invoices:
            for o in self.browse(cr, uid, ids, context=context):
                for i in o.invoice_ids:
                    if i.state == 'draft':
                        return i.id
        for val in invoices.values():
            if grouped:
                res = self._make_invoice(cr, uid, val[0][0], reduce(lambda x, y: x + y, [l for o, l in val], []), context=context)
                invoice_ref = ''
                for o, l in val:
                    invoice_ref += o.name + '|'
                    self.write(cr, uid, [o.id], {'state': 'progress'})
                    if o.order_policy == 'picking':
                        picking_obj.write(cr, uid, map(lambda x: x.id, o.picking_ids), {'invoice_state': 'invoiced'})
                    cr.execute('insert into sale_order_invoice_rel (order_id,invoice_id) values (%s,%s)', (o.id, res))
                invoice.write(cr, uid, [res], {'origin': invoice_ref, 'name': invoice_ref})
            else:
                for order, il in val:
                    res = self._make_invoice(cr, uid, order, il, context=context)
                    invoice_ids.append(res)
                    self.write(cr, uid, [order.id], {'state': 'progress'})
                    if order.order_policy == 'picking':
                        picking_obj.write(cr, uid, map(lambda x: x.id, order.picking_ids), {'invoice_state': 'invoiced'})
                    cr.execute('insert into sale_order_invoice_rel (order_id,invoice_id) values (%s,%s)', (order.id, res))
        return res

    def action_cancel_orig(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        if context is None:
            context = {}
        sale_order_line_obj = self.pool.get('sale.order.line')
        for sale in self.browse(cr, uid, ids, context=context):
            for pick in sale.picking_ids:
                if pick.state not in ('draft', 'cancel'):
                    raise osv.except_osv(
                        _('Could not cancel sales order !'),
                        _('You must first cancel all picking attached to this sales order.'))
            for r in self.read(cr, uid, ids, ['picking_ids']):
                for pick in r['picking_ids']:
                    wf_service.trg_validate(uid, 'stock.picking', pick, 'button_cancel', cr)
            for inv in sale.invoice_ids:
                if inv.state not in ('draft', 'cancel'):
                    raise osv.except_osv(
                        _('Could not cancel this sales order !'),
                        _('You must first cancel all invoices attached to this sales order.'))
            for r in self.read(cr, uid, ids, ['invoice_ids']):
                for inv in r['invoice_ids']:
                    # TODO: TEST JFB
                    wf_service.trg_validate(uid, 'account.invoice', inv, 'invoice_cancel', cr)
            sale_order_line_obj.write(cr, uid, [l.id for l in  sale.order_line],
                                      {'state': 'cancel'}, context=context)
            sale_order_label = _('IR') if sale.procurement_request else _('FO')  # UFTP-93
            message = _("The %s '%s' has been cancelled.") % (sale_order_label, sale.name,)
            self.log(cr, uid, sale.id, message)
        self.write(cr, uid, ids, {'state': 'cancel'})
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        context.update({'no_check_line': True})
        self.write(cr, uid, ids, {'delivery_confirmed_date': time.strftime('%Y-%m-%d')}, context=context)

        res = self.action_cancel_orig(cr, uid, ids, context=context)

        for order in self.read(cr, uid, ids, ['procurement_request', 'name'], context=context):
            self.infolog(cr, uid, "The %s id:%s (%s) has been canceled." % (
                order['procurement_request'] and  _('Internal request') or _('Field order'),
                order['id'], order['name'],
            ))
        return res

    def action_wait(self, cr, uid, ids, *args):
        for o in self.browse(cr, uid, ids):
            if (o.order_policy == 'manual'):
                self.write(cr, uid, [o.id], {'state': 'manual', 'date_confirm': time.strftime('%Y-%m-%d')})
            else:
                self.write(cr, uid, [o.id], {'state': 'progress', 'date_confirm': time.strftime('%Y-%m-%d')})
            self.pool.get('sale.order.line').button_confirm(cr, uid, [x.id for x in o.order_line if x.product_id])
            message = _("The quotation '%s' has been converted to a sales order.") % (o.name,)
            message = self._hook_message_action_wait(cr, uid, order=o, message=message)
            self.log(cr, uid, o.id, message)
            self.infolog(cr, uid, "The Field Order id:%s (%s) has been confirmed." % (
                o.id, o.name,
            ))
        return True

    def _hook_ship_create_stock_picking(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        Please copy this to your module's method also.
        This hook belongs to the action_ship_create method from sale>sale.py

        - allow to modify the data for stock picking creation
        '''
        result = super(sale_order, self)._hook_ship_create_stock_picking(cr, uid, ids, context=context, *args, **kwargs)
        result['reason_type_id'] = self._get_reason_type(cr, uid, kwargs['order'], context)

        return result

    def _log_event(self, cr, uid, ids, factor=0.7, name='Open Order'):
        invs = self.read(cr, uid, ids, ['date_order', 'partner_id', 'amount_untaxed'])
        for inv in invs:
            part = inv['partner_id'] and inv['partner_id'][0]
            pr = inv['amount_untaxed'] or 0.0
            partnertype = 'customer'
            eventtype = 'sale'
            event = {
                'name': 'Order: '+name,
                'som': False,
                'description': 'Order '+str(inv['id']),
                'document': '',
                'partner_id': part,
                'date': time.strftime('%Y-%m-%d'),
                'canal_id': False,
                'user_id': uid,
                'partner_type': partnertype,
                'probability': 1.0,
                'planned_revenue': pr,
                'planned_cost': 0.0,
                'type': eventtype
            }
            self.pool.get('res.partner.event').create(cr, uid, event)

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

    def onchange_categ(self, cr, uid, ids, category, context=None):
        """
        Check if the list of products is valid for this new category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of purchase.order to check
        :param category: DB value of the new choosen category
        :param context: Context of the call
        :return: A dictionary containing the warning message if any
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        message = {}
        res = False

        if ids and category in ['log', 'medical']:
            # Check if all product nomenclature of products in FO/IR lines are consistent with the category
            try:
                med_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'MED')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('MED nomenclature Main Type not found'))
            try:
                log_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'LOG')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('LOG nomenclature Main Type not found'))

            nomen_id = category == 'log' and log_nomen or med_nomen
            cr.execute('''SELECT l.id
                          FROM sale_order_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN sale_order so ON l.order_id = so.id
                          WHERE (t.nomen_manda_0 != %s) AND so.id in %s LIMIT 1''',
                       (nomen_id, tuple(ids)))
            res = cr.fetchall()

        if ids and category in ['service', 'transport']:
            # Avoid selection of non-service products on Service FO
            category = category == 'service' and 'service_recep' or 'transport'
            transport_cat = ''
            if category == 'transport':
                transport_cat = 'OR p.transport_ok = False'
            cr.execute('''SELECT l.id
                          FROM sale_order_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN sale_order fo ON l.order_id = fo.id
                          WHERE (t.type != 'service_recep' %s) AND fo.id in %%s LIMIT 1''' % transport_cat,
                       (tuple(ids),)) # not_a_user_entry
            res = cr.fetchall()

        if res:
            message.update({
                'title': _('Warning'),
                'message': _('This order category is not consistent with product(s) on this order.'),
            })

        return {'warning': message}

    def ask_resource_lines(self, cr, uid, ids, context=None):
        '''
        Launch the wizard to re-source lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        sale_order = self.browse(cr, uid, ids[0], context=context)
        sol_ids = [sol.id for sol in sale_order.order_line]

        if len(sol_ids) > 0:
            context.update({'lines_ids': sol_ids})
            return self.pool.get('sale.order.line').open_delete_sale_order_line_wizard(cr, uid, sol_ids, context=context)
        else:
            self.write(cr, uid, sale_order.id, {'draft_cancelled': True}, context=context)
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

        order_ids = self.search(cr, uid, [('active', 'in', ('t', 'f')), ('fo_to_resource', '=', True), ('parent_order_name', '=', old_order_name)], context=dict(context, procurement_request=True))
        for old_order in self.read(cr, uid, order_ids, ['name', 'state'], context=context):
            if old_order['state'] == 'draft':
                return old_order['id']

        order_id = self.copy(cr, uid, order.id, {'order_line': [],
                                                 'state': 'draft',
                                                 'parent_order_name': old_order_name,
                                                 'fo_to_resource': True}, context=context)


        order_data = self.read(cr, uid, [order_id], ['name', 'procurement_request'], context=context)[0]
        order_name = order_data['name']
        order_type = order_data['procurement_request'] and _('Internal request') or _('Field order')

        self.log(cr, uid, order_id, _('The %s %s has been created to re-source the canceled needs') % (
            order_name,
            order_type,
        ), context=dict(context, procurement_request=order.procurement_request))

        return order_id

    def get_po_ids_from_so_ids(self, cr, uid, ids, context=None):
        '''
        receive the list of sale order ids
        return the list of purchase order ids corresponding
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        po_ids = set()
        sol_ids = []
        for so in self.browse(cr, uid, ids, context=context):
            sol_ids = [sol.id for sol in so.order_line]

        pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', 'in', sol_ids)], context=context)
        for pol in self.pool.get('purchase.order.line').browse(cr, uid, pol_ids, context=context):
            po_ids.add(pol.order_id.id)

        return list(po_ids)

    def _hook_message_action_wait(self, cr, uid, *args, **kwargs):
        '''
        Hook the message displayed on sale order confirmation
        '''
        return _('The Field order \'%s\' has been confirmed.') % (kwargs['order'].name,)

    def _get_reason_type(self, cr, uid, order, context=None):
        r_types = {
            'regular': 'reason_type_deliver_partner',
            'loan': 'reason_type_loan',
            'donation_st': 'reason_type_donation',
            'donation_exp': 'reason_type_donation_expiry',
        }

        if not order.procurement_request and order.order_type in r_types:
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', r_types[order.order_type])[1]

        return False

    def order_line_change(self, cr, uid, ids, order_line):


        values = {'no_line': True}

        if order_line:
            values = {'no_line': False}

        if not ids:
            return {'value': values}
        assert (len(ids) == 1)
        # Also update the 'state' of the purchase order
        states = self.read(cr, uid, ids, ['state', 'state_hidden_sale_order'])
        values["state"] = states[0]["state"]
        values["state_hidden_sale_order"] = states[0]["state_hidden_sale_order"]

        # We need to fetch and return also the "display strings" for state
        # as it might be needed to update the read-only view...
        raw_display_strings_state = dict(SALE_ORDER_STATE_SELECTION)
        display_strings_state = dict([(k, _(v)) \
                                      for k,v in raw_display_strings_state.items()])

        display_strings = {}
        display_strings["state"] = display_strings_state
        display_strings["state_hidden_sale_order"] = display_strings_state

        return {'value': values, "display_strings": display_strings }


    def _get_date_planned(self, order, line, prep_lt, db_date_format):
        """
        Return the planned date for the FO/IR line according
        to the order and line values.

        :param order: browse_record of a sale.order
        :param line: browse_record of a sale.order.line

        :return The planned date
        :rtype datetime
        """
        # Check type of parameter
        self._check_browse_param(order, '_get_date_planned')
        self._check_browse_param(line, '_get_date_planned')

        date_planned = datetime.strptime(order.ready_to_ship_date, db_date_format)
        date_planned = date_planned - relativedelta(days=prep_lt or 0)
        date_planned = date_planned.strftime(db_date_format)

        return date_planned

    def _get_new_picking(self, line):
        """
        Return True if the line needs a new picking ticket.
        In case of IR to an internal location, the creation
        of a picking is not needed.

        :param line: The browse_record of the sale.order.line to check

        :return True if the line needs a new picking or False
        :rtype boolean
        """
        # Check type of parameter
        self._check_browse_param(line, '_get_new_picking')

        res = line.product_id and line.product_id.type in ['product', 'consu']

        if line.order_id.manually_corrected:
            return False

        if line.order_id.procurement_request and line.type == 'make_to_order':
            # Create OUT lines for MTO lines with an external CU as requestor location
            if line.order_id.location_requestor_id.usage == 'customer' and\
               (not line.product_id or line.product_id.type == 'product'):
                res = True
            else:
                res = False

        return res

    def _get_picking_data(self, cr, uid, order, context=None, get_seq=True, force_simple=False):
        """
        Define the values for the picking ticket associated to the
        FO/IR according to order values.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param order: browse_record of a sale.order

        :return A dictionary with the values of the picking to be create
        :rtype dict
        """
        # Objects
        seq_obj = self.pool.get('ir.sequence')
        config_obj = self.pool.get('unifield.setup.configuration')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        self._check_browse_param(order, '_get_picking_data')

        setup = config_obj.get_config(cr, uid)

        picking_data = {
            'origin': order.name,
            'type': 'out',
            'state': 'draft',
            'move_type': order.picking_policy,
            'sale_id': order.id,
            'address_id': order.partner_shipping_id.id,
            'note': order.note,
            'invoice_state': (order.order_policy == 'picking' and '2binvoiced') or 'none',
            'company_id': order.company_id.id,
        }

        if order.procurement_request:
            location_dest_id = order.location_requestor_id
            if order.procurement_request:
                if location_dest_id and location_dest_id.usage in ('supplier', 'customer'):
                    picking_data.update({
                        'type': 'out',
                        'subtype': 'standard',
                        'already_replicated': False,
                        'reason_type_id': data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_external_supply')[1],
                        'requestor': order.requestor,
                    })
                    seq_name = 'stock.picking.out'
                else:
                    picking_data.update({
                        'type': 'internal',
                        'subtype': 'standard',
                        'reason_type_id': data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1],
                    })
                    seq_name =  'stock.picking.internal'
        else:
            if force_simple or setup.delivery_process == 'simple':
                picking_data['subtype'] = 'standard'
                # use the name according to picking ticket sequence
                seq_name = 'stock.picking.out'
            else:
                picking_data['subtype'] = 'picking'
                # use the name according to picking ticket sequence
                seq_name = 'picking.ticket'

        picking_data.update({
            'flow_type': 'full',
            'backorder_id': False,
            'warehouse_id': order.shop_id.warehouse_id.id,
            'reason_type_id': self._get_reason_type(cr, uid, order, context=context) or picking_data.get('reason_type_id', False),
        })

        if get_seq:
            picking_data['name'] = seq_obj.get(cr, uid, seq_name)
        else:
            picking_data['seq_name'] = seq_name
        return picking_data

    def _get_move_data(self, cr, uid, order, line, picking_id, context=None):
        """
        Define the values for the stock move associated to the
        FO/IR line according to line and order values.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param order: browse_record of a sale.order
        :param line: browse_record of a sale.order.line

        :return A dictionary with the values of the move to be create
        :rtype dict
        """
        # Objects
        data_obj = self.pool.get('ir.model.data')
        config_obj = self.pool.get('unifield.setup.configuration')
        loc_obj = self.pool.get('stock.location')
        pick_obj = self.pool.get('stock.picking')

        if context is None:
            context = {}


        self._check_browse_param(order, '_get_move_data')
        self._check_browse_param(line, '_get_move_data')

        location_id = order.shop_id.warehouse_id.lot_stock_id.id
        output_id = order.shop_id.warehouse_id.lot_output_id.id

        move_data = {
            'name': line.name[:64],
            'picking_id': picking_id,
            'product_id': line.product_id.id,
            'date': order.ready_to_ship_date,
            'date_expected': order.ready_to_ship_date,
            'product_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': line.product_uos_qty,
            'product_uos': (line.product_uos and line.product_uos.id) or line.product_uom.id,
            'product_packaging': line.product_packaging.id,
            'address_id': line.address_allotment_id.id or order.partner_shipping_id.id,
            'location_id': location_id,
            'location_dest_id': output_id,
            'sale_line_id': line.id,
            'tracking_id': False,
            'state': 'draft',
            'note': line.notes,
            'company_id': order.company_id.id,
            'reason_type_id': self._get_reason_type(cr, uid, order),
            'price_currency_id': order.procurement_request and order.functional_currency_id.id or order.pricelist_id.currency_id.id,
            'price_unit': order.procurement_request and line.cost_price or line.price_unit,
            'line_number': line.line_number,
            'comment': line.comment,
        }

        if line.order_id.procurement_request and line.order_id.location_requestor_id.usage == 'customer' and not line.product_id and line.comment:
            move_data['product_id'] = data_obj.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]

        # For IR
        if order.procurement_request and order.location_requestor_id:
            move_data.update({
                'type': 'internal',
                'reason_type_id': data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1],
                'location_dest_id': order.location_requestor_id.id,
            })

            if order.location_requestor_id.usage in ('supplier', 'customer'):
                move_data['type'] = 'out'
        else:
            # first go to packing location (PICK/PACK/SHIP) or output location (Simple OUT)
            # according to the configuration
            # first go to packing location
            setup = config_obj.get_config(cr, uid)
            if setup.delivery_process == 'simple':
                move_data['location_dest_id'] = order.shop_id.warehouse_id.lot_output_id.id
            else:
                move_data['location_dest_id'] = order.shop_id.warehouse_id.lot_packing_id.id

            if line.product_id and line.product_id.type == 'service_recep':
                move_data['location_id'] = loc_obj.get_cross_docking_location(cr, uid)

        if 'sale_line_id' in move_data and move_data['sale_line_id']:
            if line.type == 'make_to_stock':
                move_data['location_id'] = line.location_id and line.location_id.id or order.shop_id.warehouse_id.lot_stock_id.id
            elif line.type == 'make_to_order':
                move_data.update({
                    'location_id': loc_obj.get_cross_docking_location(cr, uid),
                    'move_cross_docking_ok': True,
                })
                # Update the stock.picking
                pick_obj.write(cr, uid, move_data['picking_id'], {'cross_docking_ok': True}, context=context)

        move_data['state'] = 'confirmed'

        return move_data

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
            #  Done picking
            for pick in order.picking_ids:
                if pick.state not in ('cancel', 'done'):
                    wf_service.trg_validate(uid, 'stock.picking', pick.id, 'manually_done', cr)

            for sol in order.order_line:
                order_lines.append(sol.id)

            # Closed loan counterpart
            if order.loan_id and order.loan_id.state not in ('cancel', 'done') and not context.get('loan_id', False) == order.id:
                loan_context = context.copy()
                loan_context.update({'loan_id': order.id})
                self.pool.get('purchase.order').set_manually_done(cr, uid, order.loan_id.id, all_doc=all_doc, context=loan_context)

        # Closed stock moves
        move_ids = self.pool.get('stock.move').search(cr, uid, [('sale_line_id', 'in', order_lines), ('state', 'not in', ('cancel', 'done'))], context=context)
        self.pool.get('stock.move').set_manually_done(cr, uid, move_ids, all_doc=all_doc, context=context)

        if all_doc:
            for order_id in self.browse(cr, uid, ids, context=context):
                for sol in order_id.order_line:
                    if sol.state not in ('done', 'cancel', 'cancel_r'):
                        if not wf_service.trg_validate(uid, 'sale.order.line', sol.id, 'cancel', cr):
                            # sol are in 'exception' state, this is causing issue when UF is trying to compute the SO state ...
                            cr.execute("update sale_order_line set state = 'cancel' where id = %s", (sol.id,))
                self.write(cr, uid, [order_id.id], {'state': 'cancel'}, context=context)
                if self.read(cr, uid, order_id.id, ['state'])['state'] != 'cancel':
                    # idk why but sometimes the write statement doesn't update the SO state
                    cr.execute("update sale_order set state = 'cancel' where id = %s", (order_id.id, ))

        return True

    def _get_related_sourcing_id(self, line):
        """
        Return the ID of the related.sourcing document if any
        :param line: browse_record of FO/IR line
        :return: ID of a related.sourcing record or False
        """
        if line.related_sourcing_ok and line.related_sourcing_id:
            return line.related_sourcing_id.id

        return False

    def _get_ready_to_cancel(self, cr, uid, ids, line_ids=[], context=None):
        """
        Returns for each FO/IR in ids if the next line cancelation can
        cancel the FO/IR.
        """
        line_obj = self.pool.get('sale.order.line')
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]

        res = {}
        for fo in self.browse(cr, uid, ids, context=context):
            res[fo.id] = True
            if fo.state in ('cancel', 'done', 'draft'):
                res[fo.id] = False
                continue

            remain_lines = line_obj.search(cr, uid, [
                ('order_id', '=', fo.id),
                ('id', 'not in', line_ids),
                ('state', 'not in', ['cancel', 'done']),
            ], limit=1, order='NO_ORDER', context=context)
            if remain_lines:
                res[fo.id] = False
                continue

            exp_domain = [('order_id', '=', fo.id)]

            if context.get('pol_ids'):
                exp_domain.append(('po_id', 'not in', context.get('pol_ids')))

            if context.get('tl_ids'):
                exp_domain.append(('tender_id', 'not in', context.get('tl_ids')))

            if exp_sol_obj.search(cr, uid, exp_domain, limit=1,
                                  order='NO_ORDER', context=context):
                res[fo.id] = False
                continue

        return res

    def open_cancel_wizard(self, cr, uid, ids, context=None):
        """
        Create and open the asking cancelation wizard
        """
        wiz_obj = self.pool.get('sale.order.cancelation.wizard')
        wiz_line_obj = self.pool.get('sale.order.leave.close')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz_id = wiz_obj.create(cr, uid, {}, context=context)
        for id in ids:
            wiz_line_obj.create(cr, uid, {
                'wizard_id': wiz_id,
                'order_id': id,
            }, context=context)

        view_id = data_obj.get_object_reference(cr, uid, 'sale', 'sale_order_cancelation_ask_wizard_form_view')[1]

        if context.get('view_id'):
            del context['view_id']

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.cancelation.wizard',
            'res_id': wiz_id,
            'view_id': [view_id],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _manual_create_sync_message(self, cr, uid, res_id, return_info, rule_method, context=None):
        return

    def round_to_soq(self, cr, uid, ids, context=None):
        """
        Create a new thread to check for each line of the order if the quantity
        is compatible with SoQ rounding of the product. If not compatible,
        update the quantity to match with SoQ rounding.
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
        with SoQ rounding of the product. If not compatible, update the
        quantity to match with SoQ rounding.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of sale.order to check and update
        :param context: Context of the call
        :param use_new_cursor: True if this method is called into a new thread
        :return: True
        """
        sol_obj = self.pool.get('sale.order.line')
        uom_obj = self.pool.get('product.uom')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if use_new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()

        try:
            self.write(cr, uid, ids, {
                'import_in_progress': True,
            }, context=context)
            if use_new_cursor:
                cr.commit()

            sol_ids = sol_obj.search(cr, uid, [
                ('order_id', 'in', ids),
                ('product_id', '!=', False),
            ], context=context)

            to_update = {}
            for sol in sol_obj.browse(cr, uid, sol_ids, context=context):
                # Check only products with defined SoQ quantity
                if not sol.product_id.soq_quantity:
                    continue

                # Get line quantity in product UoM
                line_qty = sol.product_uom_qty
                if sol.product_uom.id != sol.product_id.uom_id.id:
                    line_qty = uom_obj._compute_qty_obj(cr, uid, sol.product_uom, sol.product_uom_qty, sol.product_id.uom_id, context=context)

                good_quantity = 0
                if line_qty % sol.product_id.soq_quantity:
                    good_quantity = (line_qty - (line_qty % sol.product_id.soq_quantity)) + sol.product_id.soq_quantity

                if good_quantity and sol.product_uom.id != sol.product_id.uom_id.id:
                    good_quantity = uom_obj._compute_qty_obj(cr, uid, sol.product_id.uom_id, good_quantity, sol.product_uom, context=context)

                if good_quantity:
                    to_update.setdefault(good_quantity, [])
                    to_update[good_quantity].append(sol.id)

            for qty, line_ids in to_update.iteritems():
                sol_obj.write(cr, uid, line_ids, {
                    'product_uom_qty': qty,
                    'soq_updated': True,
                }, context=context)
        except Exception as e:
            logger = logging.getLogger('sale.order.round_to_soq')
            logger.error(e)
        finally:
            self.write(cr, uid, ids, {
                'import_in_progress': False,
            }, context=context)

        if use_new_cursor:
            cr.commit()
            cr.close(True)

        return True

    def create_commitment_voucher_from_so(self, cr, uid, ids, cv_date, context=None):
        '''
        Create a new commitment voucher from the given PO
        @param ids id of the Purchase order
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        commit_id = False
        for so in self.pool.get('sale.order').browse(cr, uid, ids, context=context):
            engagement_ids = self.pool.get('account.analytic.journal').search(cr, uid, [
                ('type', '=', 'engagement'),
                ('instance_id', '=', self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.id)
            ], limit=1, context=context)

            so_partner_type = so.partner_id.partner_type
            if so_partner_type == 'intermission':
                cv_type = 'intermission'
            else:
                cv_type = 'intersection'

            vals = {
                'journal_id': engagement_ids and engagement_ids[0] or False,
                'currency_id': so.currency_id and so.currency_id.id or False,
                'partner_id': so.partner_id and so.partner_id.id or False,
                'sale_id': so.id or False,
                'type': cv_type,
            }
            period_ids = get_period_from_date(self, cr, uid, cv_date, context=context)
            period_id = period_ids and period_ids[0] or False
            if not period_id:
                raise osv.except_osv(_('Error'), _('No period found for given date: %s.') % (cv_date, ))
            vals.update({
                'date': cv_date,
                'period_id': period_id,
            })
            commit_id = self.pool.get('account.commitment').create(cr, uid, vals, context=context)

            commit_data = self.pool.get('account.commitment').read(cr, uid, commit_id, ['name'], context=context)
            message = _("Customer Commitment Voucher %s has been created.") % commit_data.get('name', '')
            self.pool.get('account.commitment').log(cr, uid, commit_id, message, action_xmlid='analytic_distribution.action_account_commitment_from_fo')
            self.infolog(cr, uid, message)

            if so.analytic_distribution_id:
                new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, so.analytic_distribution_id.id, {'sale_id': False, 'commitment_id': commit_id}, context=context)
                # Create funding pool lines if needed
                self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [new_distrib_id], context=context)
                # Update commitment with new analytic distribution
                self.pool.get('account.commitment').write(cr, uid, [commit_id], {'analytic_distribution_id': new_distrib_id}, context=context)

        return commit_id

    def wizard_import_ad(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not self.search_exists(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context):
            raise osv.except_osv(_('Warning !'), _('The FO must be in Draft state.'))
        if not self.pool.get('sale.order.line').search_exists(cr, uid, [('order_id', 'in', ids), ('state', '=', 'draft')], context=context):
            raise osv.except_osv(_('Warning !'), _('The FO has no draft line.'))

        export_id = self.pool.get('wizard.import.ad.line').create(cr, uid, {'sale_id': ids[0], 'state': 'draft'}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.ad.line',
            'res_id': export_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }


sale_order()


# TODO add a field price_unit_uos
# - update it on change product and unit price
# - use it in report if there is a uos
class sale_order_line(osv.osv):

    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax_obj.compute_all(cr, uid, line.tax_id, price, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur.rounding, taxes['total'])
            if price > 0 and res[line.id] < 0.01:
                res[line.id] = 0.01
        return res

    def _number_packages(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            try:
                res[line.id] = int((line.product_uom_qty+line.product_packaging.qty-0.0001) / line.product_packaging.qty)
            except:
                res[line.id] = 1
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

    def _get_state_to_display(self, cr, uid, ids, field_name, args, context=None):
        '''
        return the sale.order.line state to display
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        def get_linked_pol(sol_id):
            '''
            @return PO line (browse_record) linked to the given SO line or None
            '''
            linked_pol_id = self.pool.get('purchase.order.line').search(cr, uid, [('linked_sol_id', '=', sol.id)], context=context)
            linked_pol = None
            if linked_pol_id:
                linked_pol = self.pool.get('purchase.order.line').browse(cr, uid, linked_pol_id[0], fields_to_fetch=['state'], context=context)
            return linked_pol

        res = {}
        for sol in self.browse(cr, uid, ids, context=context):
            # if FO line has been created from ressourced process, then we display the state as 'Resourced-XXX' (excepted for 'done' status)
            if (sol.resourced_original_line or (sol.is_line_split and sol.original_line_id and sol.original_line_id.resourced_original_line)) and sol.state not in ('done', 'cancel', 'cancel_r'):
                if sol.state.startswith('validated'):
                    res[sol.id] = 'resourced_v'
                elif sol.state.startswith('sourced'):
                    linked_pol = get_linked_pol(sol.id)
                    if sol.state == 'sourced_v' or (sol.state == 'sourced_n' and linked_pol and linked_pol.state != 'draft'):
                        res[sol.id] = 'resourced_pv'
                    #elif sol.state == 'sourced_sy':
                    #    res[sol.id] = 'Resourced-sy'
                    # debatable
                    else:
                        res[sol.id] = 'resourced_s'
                elif sol.state.startswith('confirmed'):
                    res[sol.id] = 'resourced_c'
                else: # draft + unexpected PO line state:
                    res[sol.id] = 'resourced_d'
            else: # state_to_display == state
                res[sol.id] = sol.state

        return res

    def _get_display_resourced_orig_line(self, cr, uid, ids, field_name, args, context=None):
        '''
        return the original SO line (from which the current on has been resourced) formatted as wanted
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int,long)):
            ids = [ids]

        res = {}
        for sol in self.browse(cr, uid, ids, context=context):
            res[sol.id] = False
            if sol.resourced_original_line:
                res[sol.id] = '%s' % (sol.resourced_original_line.line_number)

        return res

    def _get_stock_take_date(self, cr, uid, context=None):
        '''
            Returns stock take date
        '''
        if context is None:
            context = {}
        order_obj = self.pool.get('sale.order')
        res = False

        if context.get('sale_id', False):
            so = order_obj.browse(cr, uid, context.get('sale_id'), context=context)
            res = so.stock_take_date

        return res

    def _check_changed(self, cr, uid, ids, name, arg, context=None):
        '''
        Check if an original value has been changed
        '''
        if context is None:
            context = {}
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            changed = False
            if (line.order_id.procurement_request or line.order_id.fo_created_by_po_sync or line.state != 'draft')\
                    and (line.modification_comment or line.created_by_sync or line.cancelled_by_sync
                         or (line.original_qty and line.product_uom_qty != line.original_qty)
                         or (line.original_product and line.product_id and line.product_id.id != line.original_product.id)):
                changed = True

            res[line.id] = changed

        return res

    def _get_pol_external_ref(self, cr, uid, ids, name, arg, context=None):
        '''
        Get the linked PO line's External Reference if there is one
        '''
        if context is None:
            context = {}

        pol_obj = self.pool.get('purchase.order.line')
        res = {}

        for _id in ids:
            linked_pol_ids = pol_obj.search(cr, uid, [('linked_sol_id', '=', _id)], context=context)
            if linked_pol_ids:
                res[_id] = pol_obj.browse(cr, uid, linked_pol_ids[0], fields_to_fetch=['external_ref'],
                                          context=context).external_ref
            else:
                res[_id] = False

        return res

    def _get_dpo_id(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        if not ids:
            return []

        ret = {}
        for _id in ids:
            ret[_id] = False

        cr.execute('''
            select sol.id, pol.order_id
            from
                sale_order_line sol
            left join
                purchase_order_line pol on pol.linked_sol_id = sol.id
            where
                sol.id in %s
        ''', (tuple(ids),))
        for x in cr.fetchall():
            ret[x[0]] = x[1]
        return ret

    _max_value = 10**10
    _max_msg = _('The Total amount of the line is more than 10 digits. Please check that the Qty and Unit price are correct to avoid loss of exact information')
    _name = 'sale.order.line'
    _description = 'Sales Order Line'
    _columns = {
        'order_id': fields.many2one('sale.order', 'Order Reference', required=True, ondelete='cascade', select=True, readonly=True, states={'draft':[('readonly',False)]}, join=True),
        'name': fields.char('Description', size=256, required=True, select=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'delay': fields.float('Delivery Lead Time', required=True, help="Number of days between the order confirmation the shipping of the products to the customer", readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'product_id': fields.many2one('product.product', 'Product', domain=[('sale_ok', '=', True)], change_default=True),
        'invoice_lines': fields.many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id', 'invoice_id', 'Invoice Lines', readonly=True),
        'invoiced': fields.boolean('Invoiced', readonly=True),
        'price_unit': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Sale Price Computation'), readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, en_thousand_sep=False),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal', digits_compute= dp.get_precision('Sale Price')),
        'tax_id': fields.many2many('account.tax', 'sale_order_tax', 'order_line_id', 'tax_id', 'Taxes', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'type': fields.selection([('make_to_stock', 'from stock'), ('make_to_order', 'on order')], 'Procurement Method', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'address_allotment_id': fields.many2one('res.partner.address', 'Allotment Partner'),
        'product_uom_qty': fields.float('Quantity (UoM)', digits=(16, 2), required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, related_uom='product_uom'),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'product_uos_qty': fields.float('Quantity (UoS)', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, related_uom='product_uos'),
        'extra_qty': fields.float('Extra Qty from IN', readonly=True),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'product_packaging': fields.many2one('product.packaging', 'Packaging'),
        'move_ids': fields.one2many('stock.move', 'sale_line_id', 'Inventory Moves', readonly=True),
        'discount': fields.float('Discount (%)', digits=(16, 2), readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'number_packages': fields.function(_number_packages, method=True, type='integer', string='Number Packages'),
        'notes': fields.text('Notes'),
        'th_weight': fields.float('Weight', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'state': fields.selection(SALE_ORDER_LINE_STATE_SELECTION, 'State', required=True, readonly=True, select=1,
                                  help='* The \'Draft\' state is set when the related sales order in draft state. \
            \n* The \'Confirmed\' state is set when the related sales order is confirmed. \
            \n* The \'Exception\' state is set when the related sales order is set as exception. \
            \n* The \'Done\' state is set when the sales order line has been picked. \
            \n* The \'Cancelled\' state is set when a user cancel the sales order related.'),
        'state_to_display': fields.function(_get_state_to_display, method=True, type='selection', selection=SALE_ORDER_LINE_DISPLAY_STATE_SELECTION, string='State', readonly=True,
                                            help='* The \'Draft\' state is set when the related sales order in draft state. \
            \n* The \'Confirmed\' state is set when the related sales order is confirmed. \
            \n* The \'Exception\' state is set when the related sales order is set as exception. \
            \n* The \'Done\' state is set when the sales order line has been picked. \
            \n* The \'Cancelled\' state is set when a user cancel the sales order related.'
                                            ),
        'resourced_original_line': fields.many2one('sale.order.line', 'Original line', readonly=True, help='Original line from which the current one has been cancel and ressourced'),
        'display_resourced_orig_line': fields.function(_get_display_resourced_orig_line, method=True, type='char', readonly=True, string='Original FO/IR line', help='Original line from which the current one has been cancel and ressourced'),
        'resourced_at_state': fields.char('Resourced at state', size=128, help='The state of the original line when the resourced line has been created'),
        'stock_take_date': fields.date('Date of Stock Take', required=False),
        'order_partner_id': fields.related('order_id', 'partner_id', type='many2one', relation='res.partner', store=True, string='Customer', write_relate=False),
        'salesman_id':fields.related('order_id', 'user_id', type='many2one', relation='res.users', store=True, string='Salesman', write_relate=False),
        'company_id': fields.related('order_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'is_line_split': fields.boolean(string='This line is a split line?'),  # UTP-972: Use boolean to indicate if the line is a split line
        'partner_id': fields.related('order_id', 'partner_id', relation="res.partner", readonly=True, type="many2one", string="Customer"),
        # this field is used when the po is modified during on order process, and the so must be modified accordingly
        # the resulting new purchase order line will be merged in specified po_id
        'so_back_update_dest_po_id_sale_order_line': fields.many2one('purchase.order', string='Destination of new purchase order line', readonly=True),
        'so_back_update_dest_pol_id_sale_order_line': fields.many2one('purchase.order.line', string='Original purchase order line', readonly=True),
        'sync_order_line_db_id': fields.text(string='Sync order line DB Id', required=False, readonly=True),
        # This field is used to identify the FO PO line between 2 instances of the sync
        'original_line_id': fields.many2one('sale.order.line', string='Original line', help='ID of the original line before the split'),
        'manually_corrected': fields.boolean(string='FO line is manually corrected by user'),
        'created_by_po': fields.many2one('purchase.order', string='Created by PO'),
        'created_by_po_line': fields.many2one('purchase.order.line', string='Created by PO line'),
        'created_by_rfq': fields.many2one('purchase.order', string='Created by RfQ'),
        'created_by_rfq_line': fields.many2one('purchase.order.line', string='Created by RfQ line'),
        'dpo_line_id': fields.many2one('purchase.order.line', string='DPO line'),
        'dpo_id': fields.function(_get_dpo_id, method=True, type='many2one', relation='purchase.order', string='DPO'),
        'sync_sourced_origin': fields.char(string='Sync. Origin', size=256),
        'cancel_split_ok': fields.float(
            digits=(16,2),
            string='Cancel split',
            help='If the line has been canceled/removed on the splitted FO',
        ),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
        'soq_updated': fields.boolean(string='SoQ updated', readonly=True),
        'set_as_sourced_n': fields.boolean(string='Sourced-n line', help='Line created in a further PO, so we have to create it back in the flow'), # used for wkf transition
        'original_product': fields.many2one('product.product', 'Original Product'),
        'original_qty': fields.float('Original Qty', related_uom='original_uom'),
        'original_price': fields.float('Original Price', digits_compute=dp.get_precision('Sale Price Computation')),
        'original_uom': fields.many2one('product.uom', 'Original UOM'),
        'modification_comment': fields.char('Modification Comment', size=1024),
        'original_changed': fields.function(_check_changed, method=True, string='Changed', type='boolean'),
        # to prevent PO line and IN creation after synchro of FO created by replacement/missing IN
        'in_name_goods_return': fields.char(string='To find the right IN after synchro of FO created by replacement/missing IN', size=256),
        'from_cancel_out': fields.boolean('OUT cancel'),
        'created_by_sync': fields.boolean(string='Created by Synchronisation'),
        'sync_pushed_from_po': fields.boolean('Line added on upper-level PO'),
        'cancelled_by_sync': fields.boolean(string='Cancelled by Synchronisation'),
        'ir_name_from_sync': fields.char(size=64, string='IR/FO name to put on PO line after sync', invisible=True),
        'counterpart_po_line_id': fields.many2one('purchase.order.line', 'PO line counterpart'),
        'pol_external_ref': fields.function(_get_pol_external_ref, method=True, type='char', size=256, string="Linked PO line's External Ref.", store=False),
        'instance_sync_order_ref': fields.many2one('sync.order.label', string='Order in sync. instance'),
        'cv_line_ids': fields.one2many('account.commitment.line', 'so_line_id', string="Commitment Voucher Lines"),
    }
    _order = 'sequence, id desc'
    _defaults = {
        'discount': 0.0,
        'delay': 0.0,
        'product_uom_qty': 1,
        'product_uos_qty': 1,
        'from_cancel_out': False,
        'sequence': 10,
        'invoiced': 0,
        'state': 'draft',
        'type': 'make_to_stock',
        'product_packaging': False,
        'price_unit': 0.0,
        'is_line_split': False,  # UTP-972: By default set False, not split
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'soq_updated': False,
        'set_as_sourced_n': False,
        'stock_take_date': _get_stock_take_date,
        'created_by_sync': False,
        'sync_pushed_from_po': False,
        'cancelled_by_sync': False,
        'ir_name_from_sync': '',
    }

    def _check_stock_take_date(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Do not prevent modification during synchro
        if not context.get('from_back_sync') and not context.get('from_vi_import') and not context.get('sync_update_execution') and not context.get('sync_message_execution'):
            error_lines = []
            linked_order = ''
            for sol in self.browse(cr, uid, ids, fields_to_fetch=['order_id', 'state', 'stock_take_date', 'line_number'], context=context):
                if not linked_order:
                    linked_order = sol.order_id.name
                if sol.state in ['draft', 'validated', 'validated_n'] \
                        and sol.stock_take_date and sol.stock_take_date > sol.order_id.date_order:
                    error_lines.append(str(sol.line_number))
                if len(error_lines) >= 10:  # To not display too much
                    break
            if error_lines:
                raise osv.except_osv(
                    _('Error'),
                    _('The Stock Take Date of the lines %s is not consistent! It should not be later than %s\'s creation date')
                    % (', '.join(error_lines), linked_order or _('the FO/IR'))
                )

        return True

    def invoice_line_create(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        create_ids = []
        sales = {}
        for line in self.browse(cr, uid, ids, context=context):
            if not line.invoiced:
                if line.product_id:
                    a = line.product_id.product_tmpl_id.property_account_income.id
                    if not a:
                        a = line.product_id.categ_id.property_account_income_categ.id
                    if not a:
                        raise osv.except_osv(_('Error !'),
                                             _('There is no income account defined ' \
                                               'for this product: "%s" (id:%d)') % \
                                             (line.product_id.name, line.product_id.id,))
                else:
                    prop = self.pool.get('ir.property').get(cr, uid,
                                                            'property_account_income_categ', 'product.category',
                                                            context=context)
                    a = prop and prop.id or False
                uosqty = line.product_uos_qty
                uos_id = line.product_uos or line.product_uom or False
                pu = 0.0
                if uosqty:
                    pu = round(line.price_unit * line.product_uom_qty / uosqty,
                               self.pool.get('decimal.precision').precision_get(cr, uid, 'Sale Price'))
                fpos = line.order_id.fiscal_position or False
                a = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, a)
                if not a:
                    raise osv.except_osv(_('Error !'),
                                         _('There is no income category account defined in default Properties for Product Category or Fiscal Position is not defined !'))
                inv_id = self.pool.get('account.invoice.line').create(cr, uid, {
                    'name': line.name,
                    'origin': line.order_id.name,
                    'account_id': a,
                    'price_unit': pu,
                    'quantity': uosqty,
                    'discount': line.discount,
                    'uos_id': uos_id,
                    'product_id': line.product_id.id or False,
                    'invoice_line_tax_id': [(6, 0, [x.id for x in line.tax_id])],
                    'note': line.notes,
                    'account_analytic_id': line.order_id.project_id and line.order_id.project_id.id or False,
                })
                cr.execute('insert into sale_order_line_invoice_rel (order_line_id,invoice_id) values (%s,%s)', (line.id, inv_id))
                self.write(cr, uid, [line.id], {'invoiced': True})
                sales[line.order_id.id] = True
                create_ids.append(inv_id)
        # Trigger workflow events
        wf_service = netsvc.LocalService("workflow")
        for sid in sales.keys():
            wf_service.trg_write(uid, 'sale.order', sid, cr)
        return create_ids

    def button_cancel(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if line.invoiced:
                raise osv.except_osv(_('Invalid action !'), _('You cannot cancel a sales order line that has already been invoiced !'))
            for move_line in line.move_ids:
                if move_line.state != 'cancel':
                    raise osv.except_osv(
                        _('Could not cancel sales order line!'),
                        _('You must first cancel stock moves attached to this sales order line.'))
        return self.write(cr, uid, ids, {'state': 'cancel'})

    def button_confirm(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'confirmed'})

    def button_done(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        res = self.write(cr, uid, ids, {'state': 'done'})
        for line in self.browse(cr, uid, ids, context=context):
            wf_service.trg_write(uid, 'sale.order', line.order_id.id, cr)
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        copy from sale order line
        '''
        if not context:
            context = {}

        if not default:
            default = {}

        default.update({
            'sync_order_line_db_id': False,
            'manually_corrected': False,
            'created_by_po': False,
            'created_by_po_line': False,
            'created_by_rfq': False,
            'created_by_rfq_line': False,
            'from_cancel_out': False,
            'created_by_sync': False,
            'cancelled_by_sync': False,
            'dpo_line_id': False,
            'sync_pushed_from_po': False,
            'cv_line_ids': False,
            'extra_qty': False,
        })

        reset_if_not_set = ['ir_name_from_sync', 'in_name_goods_return', 'counterpart_po_line_id', 'instance_sync_order_ref']
        for to_reset in reset_if_not_set:
            if to_reset not in default:
                default[to_reset] = False

        return super(sale_order_line, self).copy(cr, uid, id, default, context)


    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset link to purchase order from update of on order purchase order
        '''
        if not default:
            default = {}

        if context is None:
            context = {}

        # if the po link is not in default, we set both to False (both values are closely related)
        if 'so_back_update_dest_po_id_sale_order_line' not in default:
            default.update({
                'so_back_update_dest_po_id_sale_order_line': False,
                'so_back_update_dest_pol_id_sale_order_line': False,
            })

        default.update({
            'sync_order_line_db_id': False,
            'manually_corrected': False,
            'created_by_po': False,
            'created_by_po_line': False,
            'created_by_rfq': False,
            'created_by_rfq_line': False,
            'state': 'draft',
            'move_ids': [],
            'invoiced': False,
            'invoice_lines': [],
            'set_as_sourced_n': False,
            'created_by_sync': False,
            'cancelled_by_sync': False,
            'stock_take_date': False,
            'dpo_line_id': False,
            'sync_pushed_from_po': False,
            'cv_line_ids': False,
            'extra_qty': False,
        })
        if context.get('from_button') and 'is_line_split' not in default:
            default['is_line_split'] = False

        for x in [
            'modification_comment', 'original_product', 'original_qty', 'original_price',
            'original_uom', 'sync_linked_pol', 'resourced_original_line', 'ir_name_from_sync',
            'in_name_goods_return', 'counterpart_po_line_id', 'from_cancel_out',
            'instance_sync_order_ref', 'sync_sourced_origin'
        ]:
            if x not in default:
                default[x] = False

        new_data = super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)

        # Remove supplier is line is from stock or has a customer-only supplier
        if new_data and new_data.get('supplier'):
            if new_data.get('type') == 'make_to_order':
                ftf = ['supplier', 'manufacturer', 'transporter']
                supp = self.pool.get('res.partner').browse(cr, uid, new_data['supplier'], fields_to_fetch=ftf, context=context)
                if not (supp.supplier or supp.manufacturer or supp.transporter):
                    new_data['supplier'] = False
            else:
                new_data['supplier'] = False

        return new_data

    def product_id_change_orig(self, cr, uid, ids, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False, name='',
                               partner_id=False, lang=False, update_tax=True, date_order=False, packaging=False,
                               fiscal_position=False, flag=False):
        if not partner_id:
            raise osv.except_osv(_('No Customer Defined !'), _('You have to select a customer in the sales form !\nPlease set one customer before choosing a product.'))
        warning = {}
        product_uom_obj = self.pool.get('product.uom')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        if partner_id:
            lang = partner_obj.browse(cr, uid, partner_id).lang
        context = {'lang': lang, 'partner_id': partner_id}

        if not product:
            return {'value': {'th_weight': 0, 'product_packaging': False,
                              'product_uos_qty': qty}, 'domain': {'product_uom': [],
                                                                  'product_uos': []}}
        if not date_order:
            date_order = time.strftime('%Y-%m-%d')

        result = {}
        product_obj = product_obj.browse(cr, uid, product, context=context)
        if not packaging and product_obj.packaging:
            packaging = product_obj.packaging[0].id
            result['product_packaging'] = packaging

        if packaging:
            default_uom = product_obj.uom_id and product_obj.uom_id.id
            pack = self.pool.get('product.packaging').browse(cr, uid, packaging, context=context)
            q = product_uom_obj._compute_qty(cr, uid, uom, pack.qty, default_uom)
#            qty = qty - qty % q + q
            if qty and (q and not (qty % q) == 0):
                ean = pack.ean or _('(n/a)')
                qty_pack = pack.qty
                type_ul = pack.ul
                warn_msg = _("You selected a quantity of %d Units.\n"
                             "But it's not compatible with the selected packaging.\n"
                             "Here is a proposition of quantities according to the packaging:\n\n"
                             "EAN: %s Quantity: %s Type of ul: %s") % \
                    (qty, ean, qty_pack, type_ul.name)
                warning = {
                    'title': _('Picking Information !'),
                    'message': warn_msg
                }
            result['product_uom_qty'] = qty

        uom2 = False
        if uom:
            uom2 = product_uom_obj.browse(cr, uid, uom)
            if product_obj.uom_id.category_id.id != uom2.category_id.id:
                uom = False
            result['product_uom'] = uom
        if uos:
            if product_obj.uos_id:
                uos2 = product_uom_obj.browse(cr, uid, uos)
                if product_obj.uos_id.category_id.id != uos2.category_id.id:
                    uos = False
            else:
                uos = False
        if product_obj.description_sale:
            result['notes'] = product_obj.description_sale
        fpos = fiscal_position and self.pool.get('account.fiscal.position').browse(cr, uid, fiscal_position) or False
        if update_tax: #The quantity only have changed
            result['delay'] = (product_obj.sale_delay or 0.0)
            result['tax_id'] = self.pool.get('account.fiscal.position').map_tax(cr, uid, fpos, product_obj.taxes_id)
            result.update({'type': product_obj.procure_method})

        if not flag:
            result['name'] = self.pool.get('product.product').name_get(cr, uid, [product_obj.id], context=context)[0][1]
        domain = {}
        if (not uom) and (not uos):
            result['product_uom'] = product_obj.uom_id.id
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
                uos_category_id = product_obj.uos_id.category_id.id
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
                uos_category_id = False
            result['th_weight'] = qty * product_obj.weight
            domain = {'product_uom':
                      [('category_id', '=', product_obj.uom_id.category_id.id)],
                      'product_uos':
                      [('category_id', '=', uos_category_id)]}

        elif uos and not uom: # only happens if uom is False
            result['product_uom'] = product_obj.uom_id and product_obj.uom_id.id
            result['product_uom_qty'] = qty_uos / product_obj.uos_coeff
            result['th_weight'] = result['product_uom_qty'] * product_obj.weight
        elif uom: # whether uos is set or not
            default_uom = product_obj.uom_id and product_obj.uom_id.id
            q = product_uom_obj._compute_qty(cr, uid, uom, qty, default_uom)
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
            result['th_weight'] = q * product_obj.weight        # Round the quantity up

        if not uom2:
            uom2 = product_obj.uom_id
        if not pricelist:
            warning = {
                'title': 'No Pricelist !',
                'message':
                    'You have to select a pricelist or a customer in the sales form !\n'
                    'Please set one before choosing a product.'
            }
        else:
            price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist],
                                                                 product, qty or 1.0, partner_id, {
                'uom': uom,
                'date': date_order,
            })[pricelist]
            if price is False:
                warning = {
                    'title': 'No valid pricelist line found !',
                    'message':
                        "Couldn't find a pricelist line matching this product and quantity.\n"
                        "You have to change either the product, the quantity or the pricelist."
                }
            else:
                result.update({'price_unit': price})
        return {'value': result, 'domain': domain, 'warning': warning}

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False, name='',
                          partner_id=False, lang=False, update_tax=True, date_order=False, packaging=False,
                          fiscal_position=False, flag=False, context=None):
        """
        If we select a product we change the procurement type to its own procurement method (procure_method).
        If there isn't product, the default procurement method is 'From Order' (make_to_order).
        Both remains changeable manually.
        """
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        res = self.product_id_change_orig(cr, uid, ids, pricelist, product, qty, uom, qty_uos, uos, name, partner_id,
                                          lang, update_tax, date_order, packaging, fiscal_position, flag)

        if 'domain' in res:
            del res['domain']

        if product:
            if partner_id:
                # Test the compatibility of the product with the partner of the order
                res, test = product_obj._on_change_restriction_error(cr, uid, product, field_name='product_id', values=res, vals={'partner_id': partner_id, 'obj_type': 'sale.order'})
                if test:
                    return res

            type = product_obj.read(cr, uid, [product], ['procure_method'])[0]['procure_method']
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


    def product_uom_change(self, cursor, user, ids, pricelist, product, qty=0,
                           uom=False, qty_uos=0, uos=False, name='', partner_id=False,
                           lang=False, update_tax=True, date_order=False):
        res = self.product_id_change(cursor, user, ids, pricelist, product,
                                     qty=qty, uom=uom, qty_uos=qty_uos, uos=uos, name=name,
                                     partner_id=partner_id, lang=lang, update_tax=update_tax,
                                     date_order=date_order)
        if 'product_uom' in res['value']:
            del res['value']['product_uom']
        if not uom:
            res['value']['price_unit'] = 0.0
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        When delete a FO/IR line, check if the FO/IR must be confirmed
        """
        lines_to_check = []
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context is None:
            context = {}

        context['procurement_request'] = True

        lines_to_log = []

        for line in self.browse(cr, uid, ids, context=context):
            ltc_ids = self.search(cr, uid, [
                ('order_id', '=', line.order_id.id),
                ('order_id.state', '=', 'validated'),
                ('id', '!=', line.id),
            ], limit=1, context=context)
            if ltc_ids and ltc_ids[0] not in lines_to_check:
                lines_to_check.append(ltc_ids[0])

            lines_to_log.append((
                line.id,
                line.line_number,
                line.order_id.procurement_request and 'Internal request' or 'Field order',
                line.order_id.id,
                line.order_id.name,
            ))

        """Allows to delete sales order lines in draft,cancel states"""
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.state not in ['draft', 'validated', 'cancel'] and not context.get('call_unlink', False):
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete a sales order line which is %s !') %(rec.state,))

        res = super(sale_order_line, self).unlink(cr, uid, ids, context=context)

        for ltl in lines_to_log:
            self.infolog(cr, uid, "The line id:%s (line number: %s) of the %s id:%s (%s) has been deleted." % ltl)

        if lines_to_check:
            self.check_confirm_order(cr, uid, lines_to_check, run_scheduler=True, context=context, update_lines=False)

        return res

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Method to cancel a SO line
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        for sol_id in ids:
            wf_service.trg_validate(uid, 'sale.order.line', sol_id, 'cancel', cr)

        return True

    def cancel_partial_qty(self, cr, uid, ids, qty_to_cancel, resource=False, cancel_move=None, context=None):
        '''
        cancel partially a SO line: create a split and cancel the split
        '''
        if isinstance(ids, (int,long)):
            ids = [ids]
        if context is None:
            context = {}
        wf_service = netsvc.LocalService("workflow")
        signal = 'cancel_r' if resource else 'cancel'

        if context.get('sol_done_instead_of_cancel'):
            signal = 'done'

        for sol in self.browse(cr, uid, ids, context=context):
            orig_qty = sol.product_uom_qty
            # create split to cancel:
            split_id = self.pool.get('split.sale.order.line.wizard').create(cr, uid, {
                'sale_line_id': sol.id,
                'original_qty': orig_qty,
                'old_line_qty': sol.product_uom_qty - qty_to_cancel,
                'new_line_qty': qty_to_cancel,
            }, context=context)
            context.update({'return_new_line_id': True})
            new_line_id = self.pool.get('split.sale.order.line.wizard').split_line(cr, uid, split_id, context=context)
            if signal == 'done':
                self.pool.get('sale.order.line').write(cr, uid, [new_line_id], {'from_cancel_out': True}, context=context)
            context.update({'return_new_line_id': True})
            wf_service.trg_validate(uid, 'sale.order.line', new_line_id, signal, cr)
            if cancel_move:
                self.pool.get('stock.move').write(cr, uid, [cancel_move], {'sale_line_id': new_line_id}, context=context)

        return True

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

    def update_or_cancel_line(self, cr, uid, line, qty_diff, resource=False, cancel_move=None, context=None):
        '''
        Update the quantity of the IR/FO line with the qty_diff - Update also
        the quantity in procurement attached to the IR/Fo line.

        If the qty_diff is equal or larger than the line quantity, delete the
        line and its procurement.
        @param resource: is the line cancel and resourced ? usefull to set the 'cancel_r' state
        '''

        if context is None:
            context = {}

        so_obj = self.pool.get('sale.order')
        wf_service = netsvc.LocalService("workflow")

        signal = 'cancel'
        if resource:
            signal = 'cancel_r'
        elif context.get('sol_done_instead_of_cancel'):
            signal = 'done'

        if isinstance(line, (int, long)):
            line = self.browse(cr, uid, line, context=context)

        order = line.order_id and line.order_id.id

        context['cancel_only'] = not resource

        if line.extra_qty:
            self.infolog(cr, uid, 'Cancel Extra - FO %s  line id:%s, qty cancelled %s, extra qty: %s' % (line.order_id.name, line.id, qty_diff, line.extra_qty))
            if line.extra_qty >= qty_diff:
                self.write(cr, uid, [line.id], {'extra_qty': line.extra_qty - qty_diff}, context=context)
                return line.id
            self.write(cr, uid, [line.id], {'extra_qty': 0}, context=context)
            qty_diff = qty_diff - line.extra_qty

        if qty_diff >= line.product_uom_qty:
            if signal == 'done':
                self.write(cr, uid, [line.id], {'from_cancel_out': True}, context=context)

            wf_service.trg_validate(uid, 'sale.order.line', line.id, signal, cr)
        else:
            # Update the line and the procurement
            self.cancel_partial_qty(cr, uid, [line.id], qty_diff, resource, cancel_move=cancel_move, context=context)

        context.pop('cancel_only')
        so_to_cancel_id = False
        if context.get('cancel_type', False) != 'update_out' and so_obj._get_ready_to_cancel(cr, uid, order, context=context)[order]:
            so_to_cancel_id = order

        return so_to_cancel_id

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
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}
        if isinstance(line, (int, long)):
            line = self.browse(cr, uid, line, context=context)

        if not order_id:
            order_id = order_obj.create_resource_order(cr, uid, line.order_id, context=context)

        if not qty_diff:
            qty_diff = line.product_uom_qty

        values = {
            'order_id': order_id,
            'resourced_original_line': line.id,
            'resourced_original_remote_line': line.sync_linked_pol,
            'resourced_at_state': line.state,
            'product_uom_qty': qty_diff,
            'product_uos_qty': qty_diff,
        }
        context['keepDateAndDistrib'] = True
        if not line.analytic_distribution_id and line.order_id and line.order_id.analytic_distribution_id:
            new_distrib = ad_obj.copy(cr, uid, line.order_id.analytic_distribution_id.id, {}, context=context)
            values['analytic_distribution_id'] = new_distrib

        line_id = self.copy(cr, uid, line.id, values, context=context)
        wf_service.trg_validate(uid, 'sale.order.line', line_id, 'validated', cr)

        order_name = self.pool.get('sale.order').read(cr, uid, [order_id], ['name'], context=context)[0]['name']

        if line.order_id and line.order_id.procurement_request:
            view_id = data_obj.get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')[1]
        else:
            resource_line_sync_id = self.read(cr, uid, line_id, ['sync_order_line_db_id'])['sync_order_line_db_id']
            self.pool.get('sale.order.line.cancel').create(cr, uid, {'sync_order_line_db_id': line.sync_order_line_db_id,
                                                                     'partner_id': line.order_id.partner_id.id,
                                                                     'partner_type': line.order_id.partner_id.partner_type,
                                                                     'resource_sync_line_db_id': resource_line_sync_id}, context=context)
            view_id = data_obj.get_object_reference(cr, uid, 'sale', 'view_order_form')[1]
        context.update({'view_id': view_id})

        """UFTP-90
        put a 'clean' context for 'log' without potential 'Enter a reason' wizard infos
        _terp_view_name, wizard_name, ..., these causes a wrong name of the FO/IR linked view
        form was opened with 'Enter a Reason for Incoming cancellation' name
        we just keep the view id (2 distincts ids for FO/IR)"""
        self.pool.get('sale.order').log(cr, uid, order_id,
                                        _('A line was added to the %s %s to re-source the canceled line.') % (
                                            line.order_id and line.order_id.procurement_request and _('Internal Request') or _('Field Order'),
                                            order_name
                                        ),
                                        context={'view_id': context.get('view_id', False)})

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

    def open_delete_sale_order_line_wizard(self, cr, uid, ids, context=None):
        '''
        Open the wizard to delete the line
        '''
        # we need the context
        if context is None:
            context = {}

        model = 'delete.sale.order.line.wizard'
        name = _('Warning!')
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)


    def open_order_line_to_correct(self, cr, uid, ids, context=None):
        '''
        Open Order Line in form view
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'sale', 'view_order_line_to_correct_form')[1]
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
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        obj_browse = self.browse(cr, uid, ids, context=context)
        vals = {}
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

    def product_id_on_change(self, cr, uid, ids, pricelist, product, qty=0,
                             uom=False, qty_uos=0, uos=False, name='', partner_id=False,
                             lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
        """
        Call sale_order_line.product_id_change() method and check if the selected product is consistent
        with order category.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of sale.order.line where product is changed
        :param pricelist: ID of the product.pricelist of the order of the line
        :param product: ID of product.product of the selected product
        :param qty: Quantity of the sale.order.line
        :param uom: ID of the product.uom of the UoM of the sale.order.line
        :param qty_uos: Quantity of the sale.order.line converted in UoS
        :param uos: ID of the product.uom of the Unit of Sale of the sale.order.line
        :param name: Description of the sale.order.line
        :param partner_id: ID of res.partner of the order of the line
        :param lang: Lang of the user
        :param update_tax: Boolean to check if the taxes should be updated
        :param date_order: Date of the order of the line
        :param packaging: Packaging selected for the line
        :param fiscal_position: Fiscal position selected on the order of the line
        :param flag: ???
        :param context: Context of the call
        :return: Result of the sale_order_line.product_id_change() method
        """
        prod_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        res = self.product_id_change(cr, uid, ids,
                                     pricelist,
                                     product,
                                     qty=qty,
                                     uom=uom,
                                     qty_uos=qty_uos,
                                     uos=uos,
                                     name=name,
                                     partner_id=partner_id,
                                     lang=lang,
                                     update_tax=update_tax,
                                     date_order=date_order,
                                     packaging=packaging,
                                     fiscal_position=fiscal_position,
                                     flag=flag,
                                     context=context)

        if context and context.get('categ') and product:
            # Check consistency of product
            consistency_message = prod_obj.check_consistency(cr, uid, product, context.get('categ'), context=context)
            if consistency_message:
                res.setdefault('warning', {})
                res['warning'].setdefault('title', 'Warning')
                res['warning'].setdefault('message', '')

                res['warning']['message'] = '%s \n %s' % \
                    (res.get('warning', {}).get('message', ''), consistency_message)

        return res

    def default_get(self, cr, uid, fields, context=None, from_web=False):
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
            if data:
                self.pool.get('sale.order').write(cr, uid, [context.get('sale_id')], data, context=context)

        default_data = super(sale_order_line, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        default_data.update({'product_uom_qty': 0.00, 'product_uos_qty': 0.00})
        sale_id = context.get('sale_id', [])
        if not sale_id:
            return default_data
        else:
            default_data.update({'type': 'make_to_order'})
        return default_data

    def check_empty_line(self, cr, uid, ids, vals, context=None):
        '''
        Return an error if the line has no qty
        '''
        context = context is None and {} or context

        if context.get('button') in ['button_remove_lines', 'button_cancel_lines', 'check_lines_to_fix', 'add_multiple_lines', 'wizard_import_ir_line']:
            return True
        cond1 = not context.get('noraise')
        cond2 = not context.get('import_in_progress')

        if cond1 and cond2:
            empty_lines = False
            if ids and not 'product_uom_qty' in vals:
                empty_lines = self.search(cr, uid, [
                    ('id', 'in', ids),
                    ('order_id.state', '!=', 'cancel'),
                    ('product_uom_qty', '<=', 0.00),
                    ('state', '!=', 'cancel'),
                ], limit=1, order='NO_ORDER', context=context)
            elif 'product_uom_qty' in vals:
                if ids and len(ids) == 1:
                    line_state = self.browse(cr, uid, ids[0], fields_to_fetch=['state'], context=context).state
                    empty_lines = True if vals.get('product_uom_qty', 0.) <= 0. and line_state != 'cancel' else False
                else:
                    empty_lines = True if vals.get('product_uom_qty', 0.) <= 0. else False
            if empty_lines:
                raise osv.except_osv(
                    _('Error'),
                    _('You can not have an order line with a negative or zero quantity')
                )

        return True

    def create(self, cr, uid, vals, context=None):
        """
        Override create method so that the procurement method is on order if no product is selected
        If it is a procurement request, we update the cost price.
        """
        if context is None:
            context = {}
        if not vals.get('product_id') and context.get('sale_id', []):
            vals.update({'type': 'make_to_order'})
        so_obj = self.pool.get('sale.order')

        self.check_empty_line(cr, uid, False, vals, context=context)
        # UF-1739: as we do not have product_uos_qty in PO (only in FO), we recompute here the product_uos_qty for the SYNCHRO
        qty = vals.get('product_uom_qty')
        product_id = vals.get('product_id')
        product_obj = self.pool.get('product.product')
        if product_id and qty:
            if isinstance(qty, str):
                qty = float(qty)
            vals.update({'product_uos_qty' : qty * product_obj.read(cr, uid, product_id, ['uos_coeff'])['uos_coeff']})

        if vals.get('po_cft', False) == 'pli':
            vals.update({'po_cft': 'po'})
        # If the supplier is Local Market, set the default PO/CFT to Purchase List
        if vals.get('supplier'):
            # Look if the supplier is the same res_partner as Local Market
            data_obj = self.pool.get('ir.model.data')
            is_loc_mar = data_obj.search_exists(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'),
                                                          ('name', '=', 'res_partner_local_market'), ('res_id', '=', vals['supplier'])], context=context)
            if is_loc_mar:
                vals.update({'po_cft': 'pli'})

        pricelist = False
        order_id = vals.get('order_id', False)
        order_data = False
        if order_id:
            ftf = ['procurement_request', 'pricelist_id', 'fo_created_by_po_sync', 'partner_id']
            order_data = so_obj.browse(cr, uid, order_id, fields_to_fetch=ftf, context=context)

        if product_id:  # Check constraints on lines
            partner_id = False
            if order_data:
                partner_id = order_data.partner_id.id
            if order_data and order_data.procurement_request:
                self.pool.get('product.product')._get_restriction_error(cr, uid, [product_id],
                                                                        {'constraints': 'consumption'}, context=context)
            else:
                self._check_product_constraints(cr, uid, vals.get('type'), vals.get('po_cft'), product_id, partner_id,
                                                check_fnct=False, context=context)

        # Internal request
        if order_data:
            if order_data.procurement_request:
                vals.update({'cost_price': vals.get('cost_price', False)})
            if order_data.pricelist_id:
                pricelist = order_data.pricelist_id.id
            # New line created out of synchro on a FO/IR created by synchro
            if order_data.fo_created_by_po_sync and not context.get('sync_message_execution'):
                vals.update({'created_by_sync': True})

        # force the line creation with the good state, otherwise track changes for order state will
        # go back to draft (US-3671):
        if vals.get('set_as_sourced_n', False):
            vals['state'] = 'sourced_n'

        # US-4620 : Set price_unit to the product's standard price in case of synchro
        if vals.get('sync_linked_pol') and product_id:
            new_ctx = context.copy()
            if pricelist:
                new_ctx['pricelist'] = pricelist
            vals.update({
                'price_unit': product_obj.read(cr, uid, product_id, ['price'], context=new_ctx)['price']
            })

        '''
        Add the database ID of the SO line to the value sync_order_line_db_id
        '''
        if vals.get('instance_sync_order_ref'):
            vals['sync_sourced_origin'] = self.pool.get('sync.order.label').read(cr, uid, vals['instance_sync_order_ref'], ['name'])['name']

        so_line_id = super(sale_order_line, self).create(cr, uid, vals, context=context)

        if not vals.get('sync_order_line_db_id', False):  # 'sync_order_line_db_id' not in vals or vals:
            if vals.get('order_id', False):
                name = so_obj.browse(cr, uid, vals.get('order_id'), context=context).name
                super(sale_order_line, self).write(cr, uid, so_line_id, {'sync_order_line_db_id': name + "_" + str(so_line_id), } , context=context)

        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, so_line_id, context=context)

        if order_id and not context.get('sync_message_execution') and not vals.get('dpo_line_id'):
            # new line added on COO FO but validated, confirmed, sent after all other lines and reception done on project: new line added on project closed PO (KO)
            if self.pool.get('sale.order').search_exist(cr, uid, [('id', '=', order_id), ('client_order_ref', '!=', False), ('partner_type', 'in', ['internal', 'intermission', 'intersection']), ('procurement_request', '=', False)], context=context):
                self.pool.get('sync.client.message_rule')._manual_create_sync_message(cr, uid, 'sale.order.line', so_line_id, {},
                                                                                      'purchase.order.line.sol_update_original_pol', self._logger, check_identifier=False, context=context, force_domain=True)

        return so_line_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Override write method so that the procurement method is on order if no product is selected.
        If it is a procurement request, we update the cost price.
        """
        if not ids:
            return True
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # UTP-392: fixed from the previous code: check if the sale order line contains the product, and not only from vals!
        product_id = vals.get('product_id')
        if context.get('sale_id', False):
            if not product_id:
                product_id = self.browse(cr, uid, ids, context=context)[0].product_id

            if not product_id:
                vals.update({'type': 'make_to_order'})
        # Internal request
        order_id = vals.get('order_id', False)
        if order_id and self.pool.get('sale.order').read(cr, uid, order_id, ['procurement_request'], context)['procurement_request']:
            vals.update({'cost_price': vals.get('cost_price', False)})

        self.check_empty_line(cr, uid, ids, vals, context=context)

        # Remove SoQ updated flag in case of manual modification
        if not 'soq_updated' in vals:
            vals['soq_updated'] = False

        if vals.get('instance_sync_order_ref'):
            if self.search_exists(cr, uid, [('id', 'in', ids), ('state', '=', 'draft'), ('sync_sourced_origin', '=', False)], context=context):
                vals['sync_sourced_origin'] = self.pool.get('sync.order.label').read(cr, uid, vals['instance_sync_order_ref'], ['name'])['name']

        res = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

        if vals.get('stock_take_date'):
            self._check_stock_take_date(cr, uid, ids, context=context)

        return res

    def on_change_instance_sync_order_ref(self, cr, uid, ids, instance_sync_order_ref, context=None):
        if instance_sync_order_ref:
            return {'warning':
                    {
                        'title': _('Warning'),
                        'message': _("Please ensure that you selected the correct Source document because once the line is saved you will not be able to edit this field anymore. In case of mistake, the only option will be to Cancel the line and Create a new one with the correct Source document."),
                    }
                    }
        return {}

    def get_error(self, cr, uid, ids, context=None):
        '''
        Show error message
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'sale', 'fo_ir_line_error_message_view')[1]
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order.line',
            'type': 'ir.actions.act_window',
            'res_id': ids[0],
            'target': 'new',
            'context': context,
            'view_id': [view_id],
        }

    def _check_max_price(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        msg = _('The Total amount of the following lines is more than 28 digits. Please check that the Qty and Unit price are correct, the current values are not allowed')
        error = []
        ftf = ['product_uom_qty', 'price_unit', 'order_id', 'line_number']
        for sol in self.browse(cr, uid, ids, fields_to_fetch=ftf, context=context):
            nb_digits_allowed = 25
            if sol.product_uom_qty >= 10**nb_digits_allowed:
                error.append('%s #%s' % (sol.order_id.name, sol.line_number))
            else:
                total_int = int(sol.product_uom_qty * sol.price_unit)
                if len(str(total_int)) > nb_digits_allowed:
                    error.append('%s #%s' % (sol.order_id.name, sol.line_number))

        if error:
            raise osv.except_osv(_('Error'), '%s: %s' % (msg, ' ,'.join(error)))

        return True

    _constraints = [
        (_check_max_price, _("The Total amount of the following lines is more than 28 digits. Please check that the Qty and Unit price are correct, the current values are not allowed"), ['price_unit', 'product_uom_qty']),
    ]


sale_order_line()


class sale_config_picking_policy(osv.osv_memory):
    _name = 'sale.config.picking_policy'
    _inherit = 'res.config'

    _columns = {
        'name': fields.char('Name', size=64),
        'picking_policy': fields.selection([
            ('direct', 'Direct Delivery'),
            ('one', 'All at Once')
        ], 'Picking Default Policy', required=True, help="The Shipping Policy is used to configure per order if you want to deliver as soon as possible when one product is available or you wait that all products are available.."),
        'order_policy': fields.selection([
            ('manual', 'Invoice Based on Sales Orders'),
            ('picking', 'Invoice Based on Deliveries'),
        ], 'Shipping Default Policy', required=True,
           help="You can generate invoices based on sales orders or based on shippings."),
        'step': fields.selection([
            ('one', 'Delivery Order Only'),
            ('two', 'Picking List & Delivery Order')
        ], 'Steps To Deliver a Sales Order', required=True,
           help="By default, OpenERP is able to manage complex routing and paths "\
           "of products in your warehouse and partner locations. This will configure "\
           "the most common and simple methods to deliver products to the customer "\
           "in one or two operations by the worker.")
    }
    _defaults = {
        'picking_policy': 'direct',
        'order_policy': 'manual',
        'step': 'one'
    }

    def execute(self, cr, uid, ids, context=None):
        for o in self.browse(cr, uid, ids, context=context):
            ir_values_obj = self.pool.get('ir.values')
            ir_values_obj.set(cr, uid, 'default', False, 'picking_policy', ['sale.order'], o.picking_policy)
            ir_values_obj.set(cr, uid, 'default', False, 'order_policy', ['sale.order'], o.order_policy)
            if o.step == 'two':
                md = self.pool.get('ir.model.data')
                location_id = md.get_object_reference(cr, uid, 'stock', 'stock_location_output')
                location_id = location_id and location_id[1] or False
                self.pool.get('stock.location').write(cr, uid, [location_id], {'chained_auto_packing': 'manual'})

sale_config_picking_policy()

### SALE_OVERRIDE BEGIN

class sync_order_label(osv.osv):
    '''
    Class used to know the name of the document of another instance
    sourced by a FO.
    '''
    _name = 'sync.order.label'
    _description = 'Original order'

    _columns = {
        'name': fields.char(
            string='Name',
            size=256,
            required=True,
        ),
        'order_id': fields.many2one(
            'sale.order',
            string='Linked FO',
            required=True,
            ondelete='cascade',
        ),
    }

sync_order_label()

class sync_sale_order_line_split(osv.osv):
    _name = 'sync.sale.order.line.split'
    _rec_name = 'partner_id'

    _columns = {
        'partner_id': fields.many2one(
            'res.partner',
            'Partner',
            readonly=True,
        ),
        'old_sync_order_line_db_id': fields.text(
            string='Sync order line DB Id of the splitted line',
            required=True,
            readonly=True,
        ),
        'new_sync_order_line_db_id': fields.text(
            string='Sync order line DB ID of the new created line',
            required=True,
            readonly=True,
        ),
        'old_line_qty': fields.float(
            digits=(16,2),
            string='Old line qty',
            required=True,
            readonly=True,
        ),
        'new_line_qty': fields.float(
            digit=(16,2),
            string='New line qty',
            required=True,
            readonly=True,
        ),
    }

sync_sale_order_line_split()

class sale_order_sourcing_progress(osv.osv):
    _name = 'sale.order.sourcing.progress'
    _rec_name = 'order_id'
    _order = 'id desc'

    def _get_nb_lines_by_type(self, cr, uid, order_id=None, context=None):
        """
        Returns the number of FO/IR lines numbers by type of sourcing.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param order: ID of a sale.order to get number of line
        :param context: Context of the call
        :return: A tuple with number of FO/IR lines form stock and number of FO/IR lines on order
        """
        sol_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        # No order given
        if not order_id:
            return (0, 0)

        # Get number of 'make_to_stock' lines
        fsl_nb = sol_obj.search(cr, uid, [
            ('order_id', '=', order_id),
            ('type', '=', 'make_to_stock'),
        ], count=True, order='NO_ORDER', context=context)
        # Get number of 'make_to_order' lines
        ool_nb = sol_obj.search(cr, uid, [
            ('order_id', '=', order_id),
            ('type', '!=', 'make_to_stock'),
        ], count=True, order='NO_ORDER', context=context)

        return (fsl_nb, ool_nb)

    def _get_line_completed(self, mem_res, fsl_nb=0, ool_nb=0):
        """
        Computes the 'Source lines' status
        :param mem_res: A dictionnary with the number of 'from stock' and 'on order' completed lines
        :param fsl_nb: The number of 'From stock' lines in the sale.order
        :param ool_nb: The number of 'On order' lines in the sale.order
        :return: A string containing the status of the 'Source lines' field
        """
        mem_fsl_nb = mem_res['line_from_stock_completed']
        mem_ool_nb = mem_res['line_on_order_completed']

        fs_state = fsl_nb and _('Not started') or _('Nothing to do') # From stock lines state
        oo_state = ool_nb and _('Not started') or _('Nothing to do') # On order lines state

        # No lines to complete
        if fsl_nb == ool_nb == 0:
            return _('Nothing to do')

        # No line completed
        if mem_fsl_nb == mem_ool_nb == 0:
            return _('Not started (0/%s)') % (fsl_nb + ool_nb,)

        def build_state():
            """
            Build the status message to return
            """
            return _('From stock: %s (%s/%s)\nOn order: %s (%s/%s)') % (
                fs_state, mem_fsl_nb, fsl_nb,
                oo_state, mem_ool_nb, ool_nb,
            )

        def cmp_lines(mem_nb, nb, state):
            """
            Return the status of the line
            """
            if not nb:
                return state
            elif mem_nb == nb:
                return _('Done')
            else:
                return _('In Progress')

        fs_state = cmp_lines(mem_fsl_nb, fsl_nb, fs_state)
        oo_state = cmp_lines(mem_ool_nb, ool_nb, oo_state)

        return build_state()

    def _compute_sourcing_value(self, cr, uid, order, context=None):
        """
        Computes the sourcing value for the sourcing progress line.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param order: browse_record of the sale.order of the line
        :param context: Context of the call
        """
        order_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        order_ids = order_obj.search(cr, uid, [
            '|',
            ('original_so_id_sale_order', '=', order.id),
            '&',
            ('procurement_request', '=', True),
            ('id', '=', order.id),
        ], context=context)

        # Get min and max date of the documents that source the FO/IR lines
        cr.execute('''
            SELECT min(first_date), max(last_date)
            FROM procurement_request_sourcing_document
            WHERE order_id IN %s
        ''', (tuple(order_ids),))
        min_date, max_date = cr.fetchone()

        # Number of lines in the FO
        nb_all_lines = sol_obj.search(cr, uid, [
            ('order_id', 'in', order_ids),
        ], count=True, order='NO_ORDER', context=context)

        mem_fsl_nb = 0
        mem_ool_nb = 0

        # Build message by sourcing document
        sourcing = ''

        fsl_nb = 0
        ool_nb = 0
        for order_id in order_ids:
            # Save number of lines in the sale.order records
            on_stock_nb_lines, on_order_nb_lines = self._get_nb_lines_by_type(cr, uid, order_id, context=context)
            fsl_nb += on_stock_nb_lines
            ool_nb += on_order_nb_lines

        mem_res = {
            'line_from_stock_completed': mem_fsl_nb,
            'line_on_order_completed': mem_ool_nb,
        }

        sourcing_ok = fsl_nb + ool_nb >= nb_all_lines
        sourcing_completed = self._get_line_completed(mem_res, fsl_nb, ool_nb)
        return {
            'sourcing': sourcing,
            'sourcing_completed': sourcing_completed,
            'sourcing_start': min_date,
            'sourcing_stop': sourcing_ok and max_date or False,
        }


    def _get_percent(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns the different percentage of sourced lines
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of sale.order.sourcing.progress to compute
        :param field_name: List of fields to compute
        :param args: Extra arguments
        :param context: Context of the call
        :return: A dictionnary with ID of sale.order.sourcing.progress as keys
                 and a dictionnary with computed field values as values.
        """
        mem_obj = self.pool.get('sale.order.sourcing.progress.mem')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        f_to_read = [
            'line_from_stock_completed',
            'line_on_order_completed',
            'split_order',
            'check_data',
            'prepare_picking',
        ]

        res = {}
        for sp in self.browse(cr, uid, ids, context=context):
            res[sp.id] = {}

            # Save number of lines in the sale.order record
            on_stock_nb_lines, on_order_nb_lines = self._get_nb_lines_by_type(cr, uid, sp.order_id.id, context=context)
            nb_lines = on_stock_nb_lines + on_order_nb_lines

            if not sp.order_id:
                continue

            # Confirmation of the order in progress
            if sp.order_id.sourcing_trace_ok:
                mem_ids = mem_obj.search(cr, uid, [
                    ('order_id', '=', sp.order_id.id),
                ], context=context)
                if mem_ids:
                    for mem_res in mem_obj.read(cr, uid, mem_ids, f_to_read, context=context):
                        res[sp.id] = {
                            'line_completed': self._get_line_completed(mem_res, on_stock_nb_lines, on_order_nb_lines),
                            'split_order': mem_res['split_order'],
                            'check_data': mem_res['check_data'],
                            'prepare_picking': mem_res['prepare_picking'],
                        }
                elif sp.order_id.sourcing_trace and sp.order_id.sourcing_trace != _('Sourcing in progress'):
                    res[sp.id] = {
                        'line_completed': _('Error'),
                        'split_order': _('Error'),
                        'check_data': _('Error'),
                        'prepare_picking': _('An error occurred during the sourcing '), #UFTP-367 Use a general error message
                    }
                else:
                    res[sp.id] = {
                        'line_completed': _('Not started (0/%s)') % nb_lines,
                        'split_order': _('Not started'),
                        'check_data': _('Not started'),
                        'prepare_picking': _('Not started'),
                    }
            elif (sp.order_id.state_hidden_sale_order in 'split_so' or \
                  (sp.order_id.procurement_request and sp.order_id.state in ('manual', 'progress'))):
                line_completed = _('From stock: %s (%s/%s)\nOn order: %s (%s/%s)') % (
                    _('Done'), on_stock_nb_lines, on_stock_nb_lines,
                    _('Done'), on_order_nb_lines, on_order_nb_lines,
                )
                res[sp.id] = {
                    'line_completed': line_completed,
                    'split_order': _('Done (%s/%s)') % (nb_lines, nb_lines),
                    'check_data': _('Done'),
                    'prepare_picking': _('Done'),
                }
                res[sp.id].update(self._compute_sourcing_value(cr, uid, sp.order_id, context=context))

        return res

    _columns = {
        'order_id': fields.many2one(
            'sale.order',
            string='Order',
            required=True,
        ),
        'line_completed': fields.function(
            _get_percent,
            method=True,
            type='text',
            size=64,
            string='Source lines',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'split_order': fields.function(
            _get_percent,
            method=True,
            type='char',
            size=64,
            string='Split order',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'check_data': fields.function(
            _get_percent,
            method=True,
            type='char',
            size=64,
            string='Check data',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'prepare_picking': fields.function(
            _get_percent,
            method=True,
            type='char',
            size=64,
            string='Prepare picking',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'sourcing': fields.function(
            _get_percent,
            method=True,
            type='text',
            string='Sourcing Result',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'sourcing_completed': fields.function(
            _get_percent,
            method=True,
            type='text',
            size=64,
            string='Sourcing status',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'sourcing_start': fields.function(
            _get_percent,
            method=True,
            type='datetime',
            size=64,
            string='Sourcing start date',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'sourcing_stop': fields.function(
            _get_percent,
            method=True,
            type='datetime',
            size=64,
            string='Sourcing end date',
            readonly=True,
            store=False,
            multi='memory',
        ),
        'start_date': fields.datetime(
            string='Start date',
            readonly=True,
        ),
        'end_date': fields.datetime(
            string='End date',
            readonly=True,
        ),
        'error': fields.text(
            string='Error',
        ),
    }

    _defaults = {
        'line_completed': '/',
        'split_order': '/',
        'check_data': '/',
        'prepare_picking': '/',
        'sourcing': '/',
        'end_date': False,
        'sourcing_start': False,
        'sourcing_stop': False,
    }

sale_order_sourcing_progress()

class sale_order_sourcing_progress_mem(osv.osv_memory):
    _name = 'sale.order.sourcing.progress.mem'
    _rec_name = 'order_id'

    _columns = {
        'order_id': fields.many2one(
            'sale.order',
            string='Order',
            required=True,
        ),
        'line_from_stock_completed': fields.integer(
            string='Source lines from stock',
            size=64,
            readonly=True,
        ),
        'line_on_order_completed': fields.integer(
            string='Source lines on order',
            size=64,
            readonly=True,
        ),
        'split_order': fields.char(
            string='Split order',
            size=64,
            readonly=True,
        ),
        'check_data': fields.char(
            string='Check order data',
            size=64,
            readonly=True,
        ),
        'prepare_picking': fields.char(
            string='Prepare pickings',
            size=64,
            readonly=True,
        ),
    }

    _defaults = {
        'line_from_stock_completed': 0,
        'line_on_order_completed': 0,
        'split_order': '/',
        'check_data': '/',
        'prepare_picking': '/',
    }

sale_order_sourcing_progress_mem()

class sale_order_line_cancel(osv.osv):
    _name = 'sale.order.line.cancel'
    _rec_name = 'sync_order_line_db_id'

    _columns = {
        'sync_order_line_db_id': fields.text(string='Sync order line DB ID', required=True),
        'partner_id': fields.many2one('res.partner', string='Destination'),
        'resource_ok': fields.boolean(string='Is resourced ?'),
        'resource_sync_line_db_id': fields.text(string='DB ID of the line that resource the cancel line'),
        'fo_sync_order_line_db_id': fields.text(string='DB ID of the FO/IR line that is resourced'),
        'partner_type': fields.char(size=64, string='Partner type'),
    }

sale_order_line_cancel()


class expected_sale_order_line(osv.osv):
    _name = 'expected.sale.order.line'
    _rec_name = 'order_id'

    _columns = {
        'order_id': fields.many2one(
            'sale.order',
            string='Order',
            required=True,
            ondelete='cascade',
        ),
        'po_line_id': fields.many2one(
            'purchase.order.line',
            string='Purchase order line',
            ondelete='cascade',
        ),
        'po_id': fields.related('po_line_id', 'order_id', type='many2one', relation='purchase.order', write_relate=False),
    }

expected_sale_order_line()


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
        'order_id': fields.many2one('sale.order', 'Order to delete', required=False),
        'order_ids': fields.one2many(
            'sale.order.leave.close',
            'wizard_id',
            string='Orders to check',
        ),
    }

    def leave_it(self, cr, uid, ids, context=None):
        """
        Close the window or open another window according to context
        """
        if context is None:
            context = {}

        if context.get('from_po') and context.get('po_ids'):
            po_obj = self.pool.get('purchase.order')
            return po_obj.check_empty_po(cr, uid, context.get('po_ids'), context=context)
        elif context.get('from_tender') and context.get('tender_ids'):
            tender_obj = self.pool.get('tender')
            return tender_obj.check_empty_tender(cr, uid, context.get('tender_ids'), context=context)

        return {'type': 'ir.actions.act_window_close'}

    def close_fo(self, cr, uid, ids, context=None):
        """
        Make a trg_write on FO to check if it can be canceled
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            for lc in wiz.order_ids:
                if not lc.action:
                    raise osv.except_osv(
                        _('Error'),
                        _('You must choose an action for each order'),
                    )

        return self.leave_it(cr, uid, ids, context=context)

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


class sale_order_leave_close(osv.osv_memory):
    _name = 'sale.order.leave.close'
    _rec_name = 'order_id'

    _columns = {
        'wizard_id': fields.many2one(
            'sale.order.cancelation.wizard',
            string='Wizard',
            required=True,
            ondelete='cascade',
        ),
        'order_id': fields.many2one(
            'sale.order',
            string='Order name',
            required=True,
            ondelete='cascade',
        ),
        'order_state': fields.related(
            'order_id',
            'state',
            type='selection',
            string='Order state',
            selection=SALE_ORDER_STATE_SELECTION,
            write_relate=False,
        ),
        'action': fields.selection(
            selection=[
                ('close', 'Close it'),
                ('leave', 'Leave it open'),
            ],
            string='Action to do',
        ),
    }

    _defaults = {
        'action': lambda *a: False,
    }

sale_order_leave_close()


class sale_order_line_state(osv.osv):
    _name = "sale.order.line.state"
    _description = "States of a sale order line"

    _columns = {
        'name': fields.text(string='FO state', store=True),
        'sequence': fields.integer(string='Sequence'),
    }

    def get_less_advanced_state(self, cr, uid, ids, states, context=None):
        '''
        Return the less advanced state of gives sale order line states
        @param states: a list of string
        '''
        if not states:
            return False

        cr.execute("""
            SELECT name
            FROM sale_order_line_state
            WHERE name IN %s
            ORDER BY sequence;
        """, (tuple(states),))
        min_state = cr.fetchone()

        return min_state[0] if min_state else False

    def get_sequence(self, cr, uid, ids, state, context=None):
        '''
        return the sequence of the given state
        @param state: the state's name as a string
        '''
        if not state:
            return False

        cr.execute("""
            SELECT sequence
            FROM sale_order_line_state
            WHERE name = %s;
        """, (state,))
        sequence = cr.fetchone()

        return sequence[0] if sequence else False


sale_order_line_state()


class sale_order_state(osv.osv):
    _name = "sale.order.state"
    _description = "States of a sale order"

    _columns = {
        'name': fields.text(string='SO state', store=True),
        'sequence': fields.integer(string='Sequence'),
    }

    def get_less_advanced_state(self, cr, uid, ids, states, context=None):
        '''
        Return the less advanced state of gives sale order states
        @param states: a list of string
        '''
        if not states:
            return False

        cr.execute("""
            SELECT name
            FROM sale_order_state
            WHERE name IN %s
            ORDER BY sequence;
        """, (tuple(states),))
        min_state = cr.fetchone()

        return min_state[0] if min_state else False

    def get_sequence(self, cr, uid, ids, state, context=None):
        '''
        return the sequence of the given state
        @param state: the state's name as a string
        '''
        if not state:
            return False

        cr.execute("""
            SELECT sequence
            FROM sale_order_state
            WHERE name = %s;
        """, (state,))
        sequence = cr.fetchone()

        return sequence[0] if sequence else False

sale_order_state()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
