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
from osv.orm import browse_record
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
import netsvc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from mx.DateTime import *
import time
from tools.translate import _
import logging
import threading
from workflow.wkf_expr import _eval_expr

import decimal_precision as dp
import pooler

from sale_override import SALE_ORDER_STATE_SELECTION
from sale_override import SALE_ORDER_SPLIT_SELECTION
from sale_override import SALE_ORDER_LINE_STATE_SELECTION


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
        src_doc_obj = self.pool.get('procurement.request.sourcing.document')
        src_doc_mem = self.pool.get('procurement.request.sourcing.document.mem')

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

        # All documents that source the FO/IR lines
        src_doc_ids = src_doc_obj.search(cr, uid, [
            ('order_id', 'in', order_ids),
        ], context=context)

        # Number of lines in the FO
        nb_all_lines = sol_obj.search(cr, uid, [
            ('order_id', 'in', order_ids),
        ], count=True, order='NO_ORDER', context=context)

        mem_fsl_nb = 0
        mem_ool_nb = 0

        mem_sol_ids = []
        src_doc_mem_ids = src_doc_mem.search(cr, uid, [
            ('order_id', 'in', order_ids),
        ], context=context)
        for mem_doc in src_doc_mem.browse(cr, uid, src_doc_mem_ids, context=context):
            for l in mem_doc.sourcing_lines:
                if l.id not in mem_sol_ids:
                    mem_sol_ids.append(l.id)
                    if l.type == 'make_to_stock':
                        mem_fsl_nb += 1
                    elif l.type == 'make_to_order':
                        mem_ool_nb += 1

        # Get number of sourced lines by type (MTS or MTO)
        res = []
        if src_doc_ids:
            where_sql = ''
            where_params = [tuple(src_doc_ids)]
            if mem_sol_ids:
                where_sql = ' AND sol.id NOT IN %s'
                where_params.append(tuple(mem_sol_ids))
            sql = '''
                SELECT count(*) AS nb_line, sol.type AS type
                FROM sale_order_line sol
                    LEFT JOIN sale_line_sourcing_doc_rel slsdr
                    ON slsdr.sale_line_id = sol.id
                WHERE
                    slsdr.document_id IN %%s
                    %s
                GROUP BY sol.type
            ''' % where_sql
            cr.execute(sql, where_params)
            res = cr.dictfetchall()

        for r in res:
            if r.get('type') == 'make_to_stock':
                mem_fsl_nb += r.get('nb_line', 0)
            elif r.get('type') == 'make_to_order':
                mem_ool_nb += r.get('nb_line', 0)

        # Build message by sourcing document
        sourcing = ''
        for src_doc in src_doc_obj.browse(cr, uid, src_doc_ids, context=context):
            sourcing += _('%s line%s sourced on %s.\n') % (
                len(src_doc.sourcing_lines),
                len(src_doc.sourcing_lines) > 1 and 's' or '',
                src_doc.sourcing_document_name,
            )

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

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    """
    Other methods
    """
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

        return super(sale_order, self).copy(cr, uid, id, default=default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        Check if the status of the unlinked FO is allowed for unlink.
        Statuses allowed : draft / cancel
        '''
        for order in self.read(cr, uid, ids, ['state', 'procurement_request'], context=context):
            if order['state'] not in ('draft', 'cancel'):
                type = order['procurement_request'] and _('Internal Request') or _('Field order')
                raise osv.except_osv(_('Error'), _('Only Draft and Canceled %s can be deleted.') % type)
        return super(sale_order, self).unlink(cr, uid, ids, context=context)

    def action_cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        context.update({'no_check_line': True})
        self.write(cr, uid, ids, {'delivery_confirmed_date': time.strftime('%Y-%m-%d')}, context=context)
        res = super(sale_order, self).action_cancel(cr, uid, ids, context=context)
        for order in self.browse(cr, uid, ids, context=context):
            self.infolog(cr, uid, "The %s id:%s (%s) has been canceled." % (
                order.procurement_request and  'Internal request' or 'Field order',
                order.id, order.name,
            ))
        return res

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
                'FROM sale_order_invoice_rel AS rel, account_invoice AS inv, sale_order AS sale, res_partner AS part ' + sale_clause + \
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

    def add_audit_line(self, cr, uid, order_id, old_state, new_state, context=None):
        """
        If state_hidden_sale_order is modified, add an audittrail.log.line
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
            ('name', '=', 'state_hidden_sale_order'),
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
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'field_description': _('State'),
            'trans_field_description': _('State'),
            'new_value': new_state,
            'new_value_text': new_state_txt or new_state,
            'new_value_fct': False,
            'old_value': old_state,
            'old_value_text': old_state_txt or old_state,
            'old_value_fct': '',
            'log': log,
        }
        audit_line_obj.create(cr, uid, vals, context=context)

    def _vals_get_sale_override(self, cr, uid, ids, fields, arg, context=None):
        '''
        get function values
        '''
        result = {}
        if context is None:
            context = {}

        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {}
            for f in fields:
                result[obj.id].update({f:False})

            # state_hidden_sale_order
            result[obj.id]['state_hidden_sale_order'] = obj.state
            if obj.state == 'done' and obj.split_type_sale_order == 'original_sale_order' and not obj.procurement_request:
                result[obj.id]['state_hidden_sale_order'] = 'split_so'

            if obj.state_hidden_sale_order != result[obj.id]['state_hidden_sale_order'] and \
                (not obj.original_so_id_sale_order or obj.state_hidden_sale_order not in (False, 'draft')):
                real_uid = context.get('computed_for_uid', uid)
                self.add_audit_line(cr, real_uid, obj.id,
                                    obj.state_hidden_sale_order,
                                    result[obj.id]['state_hidden_sale_order'],
                                    context=context)

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
        # we increase the size of client_order_ref field from 64 to 128
        'client_order_ref': fields.char('Customer Reference', size=128),
        'shop_id': fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'partner_id': fields.many2one('res.partner', 'Customer', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, select=True),
        'order_type': fields.selection([('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                        ('donation_st', 'Standard donation'), ('loan', 'Loan'), ],
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
        'company_id2': fields.many2one('res.company', 'Company', select=1),
        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}),
        'partner_invoice_id': fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="Invoice address for current field order."),
        'partner_order_id': fields.many2one('res.partner.address', 'Ordering Contact', readonly=True, required=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="The name and address of the contact who requested the order or quotation."),
        'partner_shipping_id': fields.many2one('res.partner.address', 'Shipping Address', readonly=True, required=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="Shipping address for current field order."),
        'pricelist_id': fields.many2one('product.pricelist', 'Currency', required=True, readonly=True, states={'draft': [('readonly', False)], 'validated': [('readonly', False)]}, help="Currency for current field order."),
        'validated_date': fields.datetime(string='Validated date', help='Date on which the FO was validated.'),
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
                                                   store={'sale.order': (lambda self, cr, uid, ids, c=None: ids, ['state', 'split_type_sale_order'], 10)}),
        'no_line': fields.function(_get_no_line, method=True, type='boolean', string='No line'),
        'manually_corrected': fields.function(_get_manually_corrected, method=True, type='boolean', string='Manually corrected'),
        'is_a_counterpart': fields.boolean('Counterpart?', help="This field is only for indicating that the order is a counterpart"),
        'fo_created_by_po_sync': fields.boolean('FO created by PO after SYNC', readonly=True),
        'fo_to_resource': fields.boolean(string='FO created to resource FO in exception', readonly=True),
        'parent_order_name': fields.char(size=64, string='Parent order name', help='In case of this FO is created to re-source a need, this field contains the name of the initial FO (before split).'),
        'sourced_references': fields.one2many(
            'sync.order.label',
            'order_id',
            string='FO/IR sourced',
        ),
        'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
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
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
    }

    def _check_empty_line(self, cr, uid, ids, context=None):
        '''
        Check if all lines have a quantity larger than 0.00
        '''
        # Objects
        line_obj = self.pool.get('sale.order.line')

        line_ids = line_obj.search(cr, uid, [
            ('order_id', 'in', ids),
            ('order_id.state', 'not in', ['draft', 'cancel']),
            ('order_id.import_in_progress', '=', False),
            ('product_uom_qty', '<=', 0.00),
        ], limit=1, order='NO_ORDER', context=context)

        if line_ids:
            return False

        return True

    _constraints = [
        (_check_empty_line, 'All lines must have a quantity larger than 0.00', ['order_line']),
    ]

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
                       (tuple(ids),))
            res = cr.fetchall()

        if res:
            message.update({
                'title': _('Warning'),
                'message': _('This order category is not consistent with product(s) on this order.'),
            })

        return {'warning': message}

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

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
        return res

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Remove the possibility to make a SO to user's company
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

        res = super(sale_order, self).write(cr, uid, ids, vals, context=context)

        return res

    def update_sourcing_progress(self, cr, uid, order, prog_id=False, values=None, context=None):
        '''
        Update the osv_memory sourcing process object linked to order ID.

        :param cr: Cursor to the database
        :param uid: ID of the user that calls the method
        :param order: browse_record of a sale.order or the ID of a sale.order
        :param prog_id: ID of a sale.order.sourcing.progress.mem to update
        :param values: Dictionary that contains the value to put on sourcing
                       process object
        :param context: Context of the call

        :return: The ID of the sale.order.sourcing.progress.mem that have been
                 updated
        '''
        prog_obj = self.pool.get('sale.order.sourcing.progress.mem')

        if not prog_id:
            if not isinstance(order, browse_record) and isinstance(order, (int, long)):
                order = self.browse(cr, uid, order, context=context)

            order_id = order.original_so_id_sale_order and order.original_so_id_sale_order.id or order.id

            prog_ids = prog_obj.search(cr, uid, [('order_id', '=', order_id)], context=context)
            if prog_ids:
                prog_id = prog_ids[0]
            else:
                prog_id = prog_obj.create(cr, uid, {
                    'order_id': order_id,
                }, context=context)

        if not values:
            return prog_id

        for fld in ['line_on_order_completed', 'line_from_stock_completed']:
            if fld in values:
                line_completed = prog_obj.read(cr, uid, [prog_id], [fld], context=context)[0][fld]
                line_completed += values[fld]
                values[fld] = line_completed

        prog_obj.write(cr, uid, [prog_id], values, context=context)

        return prog_id


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
        """
        Do some checks for SO validation :
            1/ Check of the analytic distribution
            2/ Check if there is lines in order
            3/ Check of line procurement method in case of loan FO
            4/ Check if the currency of the order is compatible with
               the currency of the partner

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of the order to validate
        :param context: Context of the call

        :return True if all order have been written
        :rtype boolean
        """
        # Objects
        line_obj = self.pool.get('sale.order.line')
        pricelist_obj = self.pool.get('product.pricelist')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        order_brw_list = self.browse(cr, uid, ids, context=context)
        reset_soq = []

        # 1/ Check validity of analytic distribution
        self.analytic_distribution_checks(cr, uid, order_brw_list)

        for order in order_brw_list:
            line_ids = []
            for line in order.order_line:
                line_ids.append(line.id)
                if line.soq_updated:
                    reset_soq.append(line.id)
            no_price_lines = []
            if order.order_type == 'regular':
                cr.execute('SELECT line_number FROM sale_order_line WHERE (price_unit*product_uom_qty < 0.01 OR price_unit = 0.00) AND order_id = %s', (order.id,))
                line_errors = cr.dictfetchall()
                for l_id in line_errors:
                    if l_id not in no_price_lines:
                        no_price_lines.append(l_id['line_number'])

            if no_price_lines:
                errors = ' / '.join(str(x) for x in no_price_lines)
                raise osv.except_osv(
                    _('Warning'),
                    _('FO cannot be validated as line cannot have unit price of zero or subtotal of zero. Lines in exception: %s') % errors,
                )

            # 2/ Check if there is lines in order
            if len(order.order_line) < 1:
                raise osv.except_osv(_('Error'), _('You cannot validate a Field order without line !'))

            # 3/ Check of line procurement method in case of loan PO
            if order.order_type == 'loan':
                non_mts_line = line_obj.search(cr, uid, [
                    ('order_id', '=', order.id),
                    ('type', '!=', 'make_to_stock'),
                ], order='NO_ORDER', context=context)
                if non_mts_line:
                    line_obj.write(cr, uid, non_mts_line, {'type': 'make_to_stock'}, context=context)

            # 4/ Check if the currency of the order is compatible with the currency of the partner
            pricelist_ids = pricelist_obj.search(cr, uid, [('in_search', '=', order.partner_id.partner_type)],
                order='NO_ORDER', context=context)
            if order.pricelist_id.id not in pricelist_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('The currency used on the order is not compatible with the supplier. '\
'Please change the currency to choose a compatible currency.'),
                )

            if not order.procurement_request and order.split_type_sale_order == 'original_sale_order':
                line_obj.update_supplier_on_line(cr, uid, line_ids, context=context)

        line_obj.write(cr, uid, reset_soq, {'soq_updated': False,}, context=context)

        self.write(cr, uid, ids, {
            'state': 'validated',
            'validated_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        }, context=context)

        # Display validation message to the user
        for order in order_brw_list:
            if not order.procurement_request:
                self.log(cr, uid, order.id, 'The Field order \'%s\' has been validated (nb lines: %s).' % (order.name, len(order.order_line)), context=context)
                self.infolog(cr, uid, "The Field order id:%s (%s) has been validated." % (order.id, order.name))
            else:
                self.log(cr, uid, order.id, 'The Internal Request \'%s\' has been validated (nb lines: %s).' % (order.name, len(order.order_line)), context=context)
                self.infolog(cr, uid, "The Internal request id:%s (%s) has been validated." % (order.id, order.name))

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
            line_total = len(so.order_line)
            line_done = 0

            prog_id = self.update_sourcing_progress(cr, uid, so, False, {
                'split_order': _('In Progress (%s/%s)') % (line_done, line_total),
            }, context=context)

            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid,
                    [('in_search', '=', so.partner_id.partner_type)],
                    order='NO_ORDER', context=context)
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
                line_done += 1
                prog_id = self.update_sourcing_progress(cr, uid, so, False, {
                    'split_order': _('In Progress (%s/%s)') % (line_done, line_total),
                }, context=context)
                # check that each line must have a supplier specified
                if  line.type == 'make_to_order':
                    if not line.product_id and line.supplier.partner_type != 'esc':
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
                                                              'transport_type': so.transport_type,
                                                              'split_type_sale_order': fo_type,
                                                              'ready_to_ship_date': line.order_id.ready_to_ship_date,
                                                              'original_so_id_sale_order': so.id}, context=dict(context, keepDateAndDistrib=True, keepClientOrder=True))
                        # log the action of split
                        self.log(cr, uid, split_id, _('The %s split %s has been created.') % (selec_name, fo_name))
                        self.infolog(cr, uid, "The %s split id:%s (%s) has been created." % (
                            selec_name, split_id, fo_name,
                        ))
                        split_fo_dic[fo_type] = split_id
                        # For loans, change the subflow
                        if fo_type == 'stock_split_sale_order':
                            po_ids = self.pool.get('purchase.order').search(cr, uid, [('loan_id', '=', so.id)], context=context)
                            netsvc.LocalService("workflow").trg_change_subflow(uid, 'purchase.order', po_ids, 'sale.order', [so.id], split_id, cr)
                # copy the line to the split Fo - the state is forced to 'draft' by default method in original add-ons
                # -> the line state is modified to sourced when the corresponding procurement is created in action_ship_proc_create
                new_context = dict(context, keepDateAndDistrib=True, keepLineNumber=True, no_store_function=['sale.order.line'])
                new_line_id = line_obj.copy(cr, uid, line.id, {'order_id': split_fo_dic[fo_type],
                                                 'original_line_id': line.id}, context=new_context)
                created_line.append(new_line_id)

            line_obj._call_store_function(cr, uid, created_line, keys=None, result=None, bypass=False, context=context)
            # the sale order is treated, we process the workflow of the new so
            prog_id = self.update_sourcing_progress(cr, uid, so, False, {
               'split_order': _('Done'),
               'check_data': _('In Progress'),
            }, context=context)
            for to_treat in [x for x in split_fo_dic.values() if x]:
                wf_service.trg_validate(uid, 'sale.order', to_treat, 'order_validated', cr)
                wf_service.trg_validate(uid, 'sale.order', to_treat, 'order_confirm', cr)

            split_fo_ids = [x for x in split_fo_dic.values() if x]
            self._hook_create_sync_split_fo_messages(cr, uid, split_fo_ids, so.id, context=context) # US-599: Create the sync messages for validated FO and split FO

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


        order_name = self.read(cr, uid, order_id, ['name'], context=context)['name']

        self.log(cr, uid, order_id, _('The Field order %s has been created to re-source the canceled needs') % order_name, context=dict(context, procurement_request=order.procurement_request))

        return order_id

    def _hook_create_sync_split_fo_messages(self, cr, uid, split_ids, original_id, context=None):
        """
        Overrided on sync_module_prod/sync_so/sale.py
        """
        return True

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
        sol_ids = sol_obj.search(cr, uid, [('order_id', 'in', ids)],
                order='NO_ORDER', context=context)
        # set lines state to done
        if sol_ids:
            sol_obj.write(cr, uid, sol_ids, {'state': 'done'}, context=context)
        self.write(cr, uid, ids, {'state': 'done',
                                  'active': False}, context=context)

        for order in self.read(cr, uid, ids, ['name'], context=context):
            self.infolog(cr, uid, "The splitted FO id:%s (%s) has been closed" % (
                order['id'], order['name'],
            ))

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
            if order.is_a_counterpart or order.order_type != 'loan':
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
                                                   'name': line.name, }, context)
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

        if not order.procurement_request and order.order_type in r_types:
            return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', r_types[order.order_type])[1]

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

    def _get_picking_data(self, cr, uid, order, context=None):
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
                    })
                    pick_name = seq_obj.get(cr, uid, 'stock.picking.out')
                else:
                    picking_data.update({
                        'type': 'internal',
                        'subtype': 'standard',
                        'reason_type_id': data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1],
                    })
                    pick_name = seq_obj.get(cr, uid, 'stock.picking.internal')
        else:
            if setup.delivery_process == 'simple':
                picking_data['subtype'] = 'standard'
                # use the name according to picking ticket sequence
                pick_name = seq_obj.get(cr, uid, 'stock.picking.out')
            else:
                picking_data['subtype'] = 'picking'
                # use the name according to picking ticket sequence
                pick_name = seq_obj.get(cr, uid, 'picking.ticket')

        picking_data.update({
            'name': pick_name,
            'flow_type': 'full',
            'backorder_id': False,
            'warehouse_id': order.shop_id.warehouse_id.id,
            'reason_type_id': self._get_reason_type(cr, uid, order, context=context) or picking_data.get('reason_type_id', False),
        })

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
            'product_uos': (line.product_uos and line.product_uos.id)\
                 or line.product_uom.id,
            'product_packaging': line.product_packaging.id,
            'address_id': line.address_allotment_id.id or order.partner_shipping_id.id,
            'location_id': location_id,
            'location_dest_id': output_id,
            'sale_line_id': line.id,
            'tracking_id': False,
            'state': 'draft',
                 # 'state': 'waiting',
            'note': line.notes,
            'company_id': order.company_id.id,
            'reason_type_id': self._get_reason_type(cr, uid, order),
            'price_currency_id': order.procurement_request and order.functional_currency_id.id or order.pricelist_id.currency_id.id,
            'price_unit': order.procurement_request and line.cost_price or line.price_unit,
            'line_number': line.line_number,
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

    # @@@override sale>sale.py>sale_order>action_ship_create()
    def action_ship_create(self, cr, uid, ids, context=None):
        """
        Create the picking ticket with the stock moves and the
        procurement orders according to FO/IR values.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of FO/IR that have been confirmed
        :param context: Context of the call

        :return
        :rtype
        """
        # Objects
        wf_service = netsvc.LocalService("workflow")
        move_obj = self.pool.get('stock.move')
        proc_obj = self.pool.get('procurement.order')
        picking_obj = self.pool.get('stock.picking')
        pol_obj = self.pool.get('purchase.order.line')
        data_obj = self.pool.get('ir.model.data')
        sol_obj = self.pool.get('sale.order.line')
        config_obj = self.pool.get('unifield.setup.configuration')
        prsd_obj = self.pool.get('procurement.request.sourcing.document')
        date_tools = self.pool.get('date.tools')
        fields_tools = self.pool.get('fields.tools')

        msg_type = {
            'in': 'Incoming shipment',
            'internal': 'Internal picking',
            'out': {
                'standard': 'Delivery order',
                'picking': 'Picking Ticket,'
            }
        }

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        setup = config_obj.get_config(cr, uid)
        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)

        for order in self.browse(cr, uid, ids, context=context):

            proc_ids = []
            move_ids = []
            picking_id = False

            prep_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)

            line_total = len(order.order_line)
            line_done = 0
            prog_id = self.update_sourcing_progress(cr, uid, order, False, {
               'check_data': _('Done'),
            }, context=context)
            for line in order.order_line:
                proc_id = False

                # Don't take care of closed lines
                if line.state == 'done':
                    continue

                move_id = False

                # In case of IR to internal location, the creation of
                # a picking is not need.
                if self._get_new_picking(line):
                    if not picking_id:
                        picking_data = self._get_picking_data(cr, uid, order)
                        picking_id = picking_obj.create(cr, uid, picking_data, context=context)
                        self.infolog(cr, uid, "The %s id:%s (%s) has been created from %s id:%s (%s)." % (
                            picking_data.get('type', '') == 'out' and \
                                msg_type.get('out', {}).get(picking_data.get('subtype', ''), '') or \
                                msg_type.get(picking_data.get('type', ''), ''),
                            picking_id, picking_data.get('name', ''),
                            order.procurement_request and 'Internal request' or 'Field order',
                            order.id, order.name,
                        ))

                    # Get move data and create the move
                    move_data = self._get_move_data(cr, uid, order, line, picking_id, context=context)

                    # defer overall_qty computation at the end of this method
                    context['bypass_store_function'] = [('stock.picking', ['overall_qty'])]
                    move_id = self.pool.get('stock.move').create(cr, uid, move_data, context=context)
                    move_ids.append(move_id)
                    context['bypass_store_function'] = False

                    if order.procurement_request:
                        move_obj.action_confirm(cr, uid, [move_id], context=context)

                    prsd_obj.chk_create(cr, uid, {
                        'order_id': order.id,
                        'sourcing_document_id': picking_id,
                        'sourcing_document_model': 'stock.picking',
                        'sourcing_document_type': picking_data.get('type'),
                        'line_ids': line.id,
                    }, context=context)

                    """
                    We update the procurement and the purchase orders if we are treating o FO which is
                    not shipping_exception.
                    PO is only treated if line is make_to_order.
                    IN nor OUT are yet (or just) created, we theoretically won't have problem with
                    backorders and co
                    """
                    if order.state != 'shipping_except' and not order.procurement_request and line.procurement_id:
                        cancel_move_id = False
                        """
                        If the procurement has already a stock move linked to it (during action_confirm of procurement
                        order), we cancel it.
                        UF-1155: Divided the cancel of the move in two times to avaid the cancelation of the field order
                        """
                        if line.procurement_id.move_id:
                            cancel_move_id = line.procurement_id.move_id.id

                        # Update corresponding procurement order with the new stock move
                        proc_obj.write(cr, uid, [line.procurement_id.id], {'move_id': move_id}, context=context)

                        if cancel_move_id:
                            # Ase action_cancel actually, because there is not stock picking or related stock moves
                            move_obj.action_cancel(cr, uid, [line.procurement_id.move_id.id], context=context)

                        if line.type == 'make_to_order':
                            pol_update_ids = pol_obj.search(cr, uid,
                                    [('procurement_id', '=', line.procurement_id.id)],
                                    order='NO_ORDER', context=context)
                            pol_obj.write(cr, uid, pol_update_ids, {'move_dest_id': move_id}, context=context)

                product_id = False
                if line.product_id:
                    product_id = line.product_id.id
                elif order.procurement_request and not line.product_id and line.comment:
                    product_id = data_obj.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]

                if not(line.type == 'make_to_stock' and order.procurement_request) and \
                   order.procurement_request and product_id:
                    # For IR with no product defined, put ToBeDefined UoM as UoM
                    if line.product_id:
                        product_uom = line.product_uom.id
                    elif line.order_id.procurement_request and not line.product_id and line.comment:
                        # do we need to have one product data per uom?
                        product_uom = data_obj.get_object_reference(cr, uid, 'product', 'cat0')[1]

                    rts_date = self._get_date_planned(order, line, prep_lt, db_date_format)
                    proc_data = self._get_procurement_order_data(line, order, rts_date, context)

                    # Just change some values because in case of IR, we need specific values
                    proc_data.update({
                        'product_id': product_id,
                        'product_uom': product_uom,
                        'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                        'move_id': move_id,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                    })

                    proc_id = proc_obj.create(cr, uid, proc_data)
                    proc_ids.append(proc_id)

                    sol_obj.write(cr, uid, [line.id], {'procurement_id': proc_id})
                    if order.state == 'shipping_except':
                        for pick in order.picking_ids:
                            mov_ids = move_obj.search(cr, uid, [
                                ('state', '=', 'cancel'),
                                ('sale_line_id', '=', line.id),
                                ('picking_id', '=', pick.id),
                            ], limit=1, context=context)

                            for mov in move_obj.read(cr, uid, mov_ids, ['product_qty', 'product_uos_qty'], context=context):
                                values = {
                                    'product_qty': mov['product_qty'],
                                    'product_uos_qty': mov['product_uos_qty'],
                                }
                                move_obj.write(cr, uid, [move_id], values, context=context)
                                proc_obj.write(cr, uid, [proc_id], values, context=context)

                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                    if line.type == 'make_to_stock':
                        prog_id = self.update_sourcing_progress(cr, uid, order, False, {
                           'line_from_stock_completed': 1,
                        }, context=context)
                    else:
                        prog_id = self.update_sourcing_progress(cr, uid, order, False, {
                            'line_on_order_completed': 1,
                        }, context=context)

                if line.type == 'make_to_stock' and line.procurement_id:
                    wf_service.trg_validate(uid, 'procurement.order', line.procurement_id.id, 'button_check', cr)

                line_done += 1
                if line.type == 'make_to_stock':
                    msg = 'The line id:%s (line number: %s) of FO/IR id:%s (%s) has been sourced \'from stock\' with the stock.move id:%s' % (
                            line.id, line.line_number,
                            line.order_id.id, line.order_id.name,
                            move_id,
                    )
                    self.infolog(cr, uid, msg)

            prog_id = self.update_sourcing_progress(cr, uid, order, False, {
               'prepare_picking': _('In Progress'),
            }, context=context)

            # compute overall_qty
            if move_ids:
                compute_store = move_obj._store_get_values(cr, uid, move_ids, None, context)
                compute_store.sort()
                done = []
                for store_order, store_object, store_ids, store_fields2 in compute_store:
                    if store_fields2 == ['overall_qty'] and not (store_object, store_ids, store_fields2) in done:
                        self.pool.get(store_object)._store_set_values(cr, uid, store_ids, store_fields2, context)
                        done.append((store_object, store_ids, store_fields2))

            if picking_id and order.procurement_request:
                picking_obj.draft_force_assign(cr, uid , [picking_id], context)
                picking_obj.cancel_assign(cr, uid, [picking_id], context)
                picking_obj.action_assign(cr, uid, [picking_id], context)

            # end for each line
            val = {}

            # On Simple OUT configuration, the system should confirm the OUT and launch a first check availability
            # On P/P/S configuration, the system should only launch a first check availability on Picking Ticket
            if setup.delivery_process != 'simple' and picking_id:
                picking_obj.log_picking(cr, uid, [picking_id], context=context)
            elif picking_id:
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            if picking_id:
                # Launch a first check availability
                picking_obj.action_assign(cr, uid, [picking_id], context=context)

            picks_to_check = set()
            for proc_id in proc_ids:
                if order.procurement_request:
                    proc = proc_obj.browse(cr, uid, [proc_id], context=context)
                    pick_id = proc and proc[0] and proc[0].move_id and proc[0].move_id.picking_id and proc[0].move_id.picking_id.id or False

                    if pick_id:
                        picks_to_check.add(pick_id)

            for pick_id in picks_to_check:
                wf_service.trg_validate(uid, 'stock.picking', pick_id, 'button_confirm', cr)
                # We also do a first 'check availability': cancel then check
                context['already_checked'] = False
                picking_obj.cancel_assign(cr, uid, [pick_id], context)
                picking_obj.action_assign(cr, uid, [pick_id], context)

            if order.state == 'shipping_except':
                manual_lines = False
                if (order.order_policy == 'manual'):
                    manual_lines = sol_obj.search(cr, uid, [
                         ('order_id', '=', order.id),
                         ('invoiced', '=', False),
                         ('state', 'not in', ['cancel', 'draft']),
                    ], limit=1, order='NO_ORDER', context=context)

                val.update({
                    'state': order.order_policy and manual_lines and 'manual' or 'progress',
                    'shipped': False,
                })

            self.write(cr, uid, [order.id], val)

            prog_id = self.update_sourcing_progress(cr, uid, order, False, {
               'prepare_picking': _('Done'),
            }, context=context)
            prog_obj = self.pool.get('sale.order.sourcing.progress')
            prog_ids = prog_obj.search(cr, uid, [('order_id', '=', order.id)],
                    order='NO_ORDER', context=context)
            prog_obj.write(cr, uid, prog_ids, {
                'end_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            }, context=context)

        return True
    # @@@END override sale>sale.py>sale_order>action_ship_create()

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
            #  Done picking
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
            # invoice_error_ids = []
            # for invoice in order.invoice_ids:
            #    if invoice.state == 'draft':
            #        wf_service.trg_validate(uid, 'account.invoice', invoice.id, 'invoice_cancel', cr)
            #    elif invoice.state not in ('cancel', 'done'):
            #        invoice_error_ids.append(invoice.id)

            # if invoice_error_ids:
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

    def _get_related_sourcing_id(self, line):
        """
        Return the ID of the related.sourcing document if any
        :param line: browse_record of FO/IR line
        :return: ID of a related.sourcing record or False
        """
        if line.related_sourcing_ok and line.related_sourcing_id:
            return line.related_sourcing_id.id

        return False

    def _get_procurement_order_data(self, line, order, rts_date, product_id=False, context=None):
        """
        Get data for the  procurement order creation according to
        sale.order.line and sale.order values.

        :param line: browse_record of a sale.order.line
        :param order: browse_record of a sale.order
        :param rts_date: Ready to ship date of the procurement order to create
        :param context: Context of the call
        """
        if context is None:
            context = {}

        # Check type of parameters
        for param in [line, order]:
            self._check_browse_param(param, '_create_procurement_order')

        if line.type == 'make_to_order':
            location_id = order.shop_id.warehouse_id.lot_input_id.id
        else:
            location_id = order.shop_id.warehouse_id.lot_stock_id.id

        proc_data = {
            'name': line.name,
            'origin': order.name,
            'product_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': (line.product_uos and line.product_uos_qty)\
                or line.product_uom_qty,
            'product_uos': (line.product_uos and line.product_uos.id)\
                or line.product_uom.id,
            'location_id': location_id,
            'procure_method': line.type,
            'move_id': False,  # will be completed at ship state in action_ship_create method
            'property_ids': [(6, 0, [x.id for x in line.property_ids])],
            'company_id': order.company_id.id,
            'supplier': line.supplier and line.supplier.id or False,
            'po_cft': line.po_cft or False,
            'related_sourcing_id': self._get_related_sourcing_id(line),
            'date_planned': rts_date,
            'from_yml_test': order.from_yml_test,
            'so_back_update_dest_po_id_procurement_order': line.so_back_update_dest_po_id_sale_order_line.id,
            'so_back_update_dest_pol_id_procurement_order': line.so_back_update_dest_pol_id_sale_order_line.id,
            'sale_id': line.order_id.id,
            'purchase_id': line.created_by_po.id or False,
        }

        if line.created_by_rfq:
            proc_data.update({
                'purchase_id': False,
                'is_rfq': True,
                'is_rfq_done': True,
                'po_cft': 'rfq',
                'rfq_id': line.created_by_rfq and line.created_by_rfq.id,
            })

        if line.created_by_tender:
            proc_data.update({
                'is_tender_done': True,
                'po_cft': 'cft',
                'tender_line_id': line.created_by_tender_line and line.created_by_tender_line.id or False,
                'tender_id': line.created_by_tender and line.created_by_tender.id or False,
            })

        if not product_id and line.product_id:
            product_id = line.product_id.id

        if product_id:
            proc_data['product_id'] = product_id

        return proc_data

    def action_ship_proc_create(self, cr, uid, ids, context=None):
        """
        1/ Check of the analytic distribution
        2/ Check if there is lines in order
        3/ Update the delivery confirmed date of sale order in case of STOCK sale order
           (check split_type_sale_order == 'stock_split_sale_order')
        4/ Update the delivery confirmed date on sale order line
        5/ Update the order policy of the sale order according to partner and order type
        6/ Create and confirm the procurement orders according to line values

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of the order to validate
        :param context: Context of the call

        :return True if all order have been written
        :rtype boolean
        """
        # Objects
        wf_service = netsvc.LocalService("workflow")
        sol_obj = self.pool.get('sale.order.line')
        fields_tools = self.pool.get('fields.tools')
        date_tools = self.pool.get('date.tools')
        proc_obj = self.pool.get('procurement.order')
        pol_obj = self.pool.get('purchase.order.line')
        tl_obj = self.pool.get('tender.line')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        db_date_format = date_tools.get_db_date_format(cr, uid, context=context)
        order_brw_list = self.browse(cr, uid, ids)

        lines = []

        # 1/ Check of the analytic distribution
        self.analytic_distribution_checks(cr, uid, order_brw_list)

        for order in order_brw_list:
            prog_id = self.update_sourcing_progress(cr, uid, order, False, {
               'check_data': _('In Progress'),
            }, context=context)

            o_write_vals = {}
            # 2/ Check if there is lines in order
            if len(order.order_line) < 1:
                raise osv.except_osv(_('Error'), _('You cannot confirm a Field order without line !'))

            # 3/ Update the delivery confirmed date of sale order in case of STOCK sale order
            #    (check split_type_sale_order == 'stock_split_sale_order')
            delivery_confirmed_date = order.delivery_confirmed_date

            prep_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='preparation_lead_time', context=context)

            # If the order is stock So, we update the confirmed delivery date
            if order.split_type_sale_order == 'stock_split_sale_order':
                # date values
                ship_lt = fields_tools.get_field_from_company(cr, uid, object=self._name, field='shipment_lead_time', context=context)
                # confirmed
                days_to_add = (ship_lt or 0) + (order.est_transport_lead_time or 0)
                delivery_confirmed_date = (datetime.today() + relativedelta(days=days_to_add)).strftime(db_date_format)
                # rts
                o_rts = (datetime.today() + relativedelta(days=ship_lt or 0)).strftime(db_date_format)

                o_write_vals.update({
                    'delivery_confirmed_date': delivery_confirmed_date,
                    'ready_to_ship_date': o_rts,
                })

            # Put a default delivery confirmed date
            if not delivery_confirmed_date:
                o_write_vals['delivery_confirmed_date'] = time.strftime('%Y-%m-%d')

            # For all lines, if the confirmed date is not filled, we copy the header value
            line_to_write = sol_obj.search(cr, uid, [
                ('order_id', '=', order.id),
                ('confirmed_delivery_date', '=', False),
            ], order='NO_ORDER', context=context)

            if line_to_write:
                sol_obj.write(cr, uid, line_to_write, {
                    'confirmed_delivery_date': o_write_vals.get('delivery_confirmed_date', order.delivery_confirmed_date),
                }, context=context)

            if (order.partner_id.partner_type == 'internal' and order.order_type == 'regular') or \
               order.order_type in ['donation_exp', 'donation_st', 'loan']:
                o_write_vals['order_policy'] = 'manual'
                lines = sol_obj.search(cr, uid, [('order_id', '=', order.id)],
                        order='NO_ORDER', context=context)


            # flag to prevent the display of the sale order log message
            # if the method is called after po update, we do not display log message
            display_log = True
            line_done = 0
            prog_id = self.update_sourcing_progress(cr, uid, order, False, {
               'check_data': _('Done'),
            }, context=context)
            for line in order.order_line:
                # these lines are valid for all types (stock and order)
                # when the line is sourced, we already get a procurement for the line
                # when the line is confirmed, the corresponding procurement order has already been processed
                # if the line is draft, either it is the first call, or we call the method again after having added a line in the procurement's po
                if line.state not in ['sourced', 'confirmed', 'done'] and not (line.created_by_po_line and line.procurement_id):
                    if not line.product_id and order.procurement_request:
                        continue

                    product_id = line.product_id.id
                    if not order.procurement_request and not line.product_id and line.comment:
                        product_id = \
                            data_obj.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]

                    rts = self._get_date_planned(order, line, prep_lt, db_date_format)
                    proc_data = self._get_procurement_order_data(line, order, rts, product_id=product_id, context=context)
                    proc_id = proc_obj.create(cr, uid, proc_data, context=context)
                    # set the flag for log message
                    if line.so_back_update_dest_po_id_sale_order_line or line.created_by_po:
                        display_log = False

                    if line.created_by_po_line and not line.created_by_po_line.order_id.rfq_ok:
                        pol_obj.write(cr, uid, [line.created_by_po_line.id], {'procurement_id': proc_id}, context=context)

                    line_values = {
                        'procurement_id': proc_id,
                    }
                    # if the line is draft (it should be the case), we set its state to 'sourced'
                    if line.state == 'draft':
                        line_values['state'] = 'sourced'

                    # Avoid a second write on the line if the line must be set as invoiced
                    if line.id in lines:
                        line_values['invoiced'] = 1
                        lines.remove(line.id)

                    sol_obj.write(cr, uid, [line.id], line_values, context=context)

                    if line.created_by_tender_line:
                        tl_obj.write(cr, uid, [line.created_by_tender_line.id], {
                            'sale_order_line_id': line.id,
                        }, context=context)

                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)

                    if line.created_by_po or line.created_by_rfq or line.created_by_tender:
                        wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)

                    if line.created_by_po:
                        proc_obj.write(cr, uid, [proc_id], {'state': 'running'}, context=context)

                    line_done += 1
                    if line.type == 'make_to_stock':
                        prog_id = self.update_sourcing_progress(cr, uid, order, False, {
                            'line_from_stock_completed': 1,
                        }, context=context)
                    else:
                        prog_id = self.update_sourcing_progress(cr, uid, order, False, {
                            'line_on_order_completed': 1,
                        }, context=context)

            # the Fo is sourced we set the state (keep the IR in confirmed state)
            if not order.procurement_request:
                o_write_vals['state'] = 'sourced'
                self.write(cr, uid, [order.id], o_write_vals, context=context)
                # display message for sourced
                if display_log:
                    self.log(cr, uid, order.id, _('The split \'%s\' is sourced.') % (order.name))

            prog_id = self.update_sourcing_progress(cr, uid, order, False, {
                'prepare_picking': _('Done'),
            }, context=context)
            prog_obj = self.pool.get('sale.order.sourcing.progress')
            prog_ids = prog_obj.search(cr, uid, [('order_id', '=', order.id)],
                    order='NO_ORDER', context=context)
            prog_obj.write(cr, uid, prog_ids, {
                'end_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            }, context=context)

        if lines:
            sol_obj.write(cr, uid, lines, {'invoiced': 1}, context=context)

        return True

    def test_lines(self, cr, uid, ids, context=None):
        '''
        return True if all lines of type 'make_to_order' are 'confirmed'

        only if a product is selected
        internal requests are not taken into account (should not be the case anyway because of separate workflow)
        '''
        line_obj = self.pool.get('sale.order.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Update the context to get IR lines
        context['procurement_request'] = True

        for order in self.read(cr, uid, ids, ['from_yml_test', 'order_line', 'procurement_request'], context=context):
            if not self._get_ready_to_cancel(cr, uid, [order['id']], order['order_line'], context=context)[order['id']]:
                return False

            # backward compatibility for yml tests, if test we do not wait
            if order['from_yml_test']:
                continue

            domain = [
                ('order_id', '=', order['id']),
                ('type', '=', 'make_to_order'),
                ('state', '!=', 'confirmed'),
            ]
            if order['procurement_request']:
                domain.append(('product_id', '!=', False))

            domain.extend([
                '|',
                ('procurement_id', '=', 'False'),
                ('procurement_id.state', '!=', 'cancel'),
            ])

            line_error = line_obj.search(cr, uid, domain, limit=1, order='NO_ORDER', context=context)

            if line_error:
                return False

        return True

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

        view_id = data_obj.get_object_reference(cr, uid, 'sale_override', 'sale_order_cancelation_ask_wizard_form_view')[1]

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

sale_order()


class sale_order_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    def init(self, cr):
        self.pool.get('fields.tools').remove_sql_constraint(cr,
            'sale_order_line', 'product_uom_qty')

    def _get_vat_ok(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return True if the system configuration VAT management is set to True
        '''
        vat_ok = self.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok
        res = {}
        for id in ids:
            res[id] = vat_ok

        return res

    _columns = {'price_unit': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Sale Price Computation'), readonly=True, states={'draft': [('readonly', False)]}),
                'is_line_split': fields.boolean(string='This line is a split line?'),  # UTP-972: Use boolean to indicate if the line is a split line
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
                'created_by_rfq': fields.many2one('purchase.order', string='Created by RfQ'),
                'created_by_rfq_line': fields.many2one('purchase.order.line', string='Created by RfQ line'),
                'dpo_line_id': fields.many2one('purchase.order.line', string='DPO line'),
                'sync_sourced_origin': fields.char(string='Sync. Origin', size=256),
                'cancel_split_ok': fields.float(
                    digits=(16,2),
                    string='Cancel split',
                    help='If the line has been canceled/removed on the splitted FO',
                ),
                'vat_ok': fields.function(_get_vat_ok, method=True, type='boolean', string='VAT OK', store=False, readonly=True),
                'soq_updated': fields.boolean(
                    string='SoQ updated',
                    readonly=True,
                ),
                }

    _defaults = {
        'is_line_split': False,  # UTP-972: By default set False, not split
        'vat_ok': lambda obj, cr, uid, context: obj.pool.get('unifield.setup.configuration').get_config(cr, uid).vat_ok,
        'soq_updated': False,
    }

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Call the user to know if the line must be re-sourced
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

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

    def unlink(self, cr, uid, ids, context=None):
        """
        When delete a FO/IR line, check if the FO/IR must be confirmed
        """
        lines_to_check = []
        if isinstance(ids, (int, long)):
            ids = [ids]

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
                line.order_id.procurement_request and 'Internal request' or 'Field orer',
                line.order_id.id,
                line.order_id.name,
        ))

        res = super(sale_order_line, self).unlink(cr, uid, ids, context=context)

        for ltl in lines_to_log:
            self.infolog(cr, uid, "The line id:%s (line number: %s) of the %s id:%s (%s) has been deleted." % ltl)

        if lines_to_check:
            self.check_confirm_order(cr, uid, lines_to_check, run_scheduler=False, context=context)

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
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        po_line_obj = self.pool.get('purchase.order.line')
        so_obj = self.pool.get('sale.order')

        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(line, (int, long)):
            line = self.browse(cr, uid, line, context=context)

        order = line.order_id and line.order_id.id
        order_name = line.order_id and line.order_id.name

        if qty_diff >= line.product_uom_qty:
            proc = line.procurement_id and line.procurement_id.id
            # Delete the line and the procurement
            self.write(cr, uid, [line.id], {'state': 'cancel'}, context=context)

            # UF-2401: Remove OUT line when IR line has been canceled
            picking_ids = set()
            move_ids = move_obj.search(cr, uid, [('sale_line_id', '=', line.id), ('state', 'not in', ['done', 'cancel']), ('in_out_updated', '=', False)], context=context)
            for move in move_obj.read(cr, uid, move_ids, ['picking_id'], context=context):
                if move['picking_id']:
                    picking_ids.add(move['picking_id'][0])

            if line.order_id.procurement_request and line.order_id.location_requestor_id.usage == 'customer':
                move_obj.write(cr, uid, move_ids, {'state': 'draft'}, context=context)
                move_obj.unlink(cr, uid, move_ids, context=context)
            else:
                move_obj.write(cr, uid, move_ids, {'state': 'cancel'}, context=context)
                move_obj.action_cancel(cr, uid, move_ids, context=context)

            for pick in pick_obj.browse(cr, uid, list(picking_ids), context=context):
                if not len(pick.move_lines) or (pick.subtype == 'standard' and all(m.state == 'cancel' for m in pick.move_lines)):
                    pick_obj.action_cancel(cr, uid, [pick.id])
                elif pick.subtype == 'picking' and pick.state == 'draft':
                    pick_obj.validate(cr, uid, [pick.id])

            if line.original_line_id:
                cancel_split_qty = line.original_line_id.cancel_split_ok + line.product_uom_qty
                self.write(cr, uid, [line.original_line_id.id], {'cancel_split_ok': cancel_split_qty}, context=context)

#            self.pool.get('sale.order.line.cancel').create(cr, uid, {
#                'sync_order_line_db_id': line.original_line_id and line.original_line_id.sync_order_line_db_id or line.sync_order_line_db_id,
#                'partner_id': line.order_id.partner_id.id,
#                'partner_type': line.order_id.partner_id.partner_type,
#                'resource_ok': True,
#            }, context=context)

            # UFTP-82:
            # do not delete cancelled IR line from PO cancelled
            # see purchase_override/purchase.py
            # - purchase_order_cancel_wizard.cancel_po()
            # - purchase_order_line.cancel_sol()
            if not 'update_or_cancel_line_not_delete' in context \
                or not context['update_or_cancel_line_not_delete']:
                tmp_ctx = context.get('call_unlink', None)
                context['call_unlink'] = True
                self.unlink(cr, uid, [line.id], context=context)
                if tmp_ctx is None:
                    del context['call_unlink']
                else:
                    context['call_unlink'] = tmp_ctx
            elif line.order_id.procurement_request:
                # UFTP-82: flagging SO is an IR and its PO is cancelled
                self.pool.get('sale.order').write(cr, uid, [line.order_id.id], {'is_ir_from_po_cancel': True}, context=context)
            if proc and context.get('cancel_type'):
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

        so_to_cancel_id = False
        if context.get('cancel_type', False) != 'update_out' and so_obj._get_ready_to_cancel(cr, uid, order, context=context)[order]:
            so_to_cancel_id = order
        else:
            wf_service.trg_write(uid, 'sale.order', order, cr)

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
            _('A line was added to the Field Order %s to re-source the canceled line.') % (order_name),
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

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset link to purchase order from update of on order purchase order
        '''
        if not default:
            default = {}
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
        })

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
                                     flag=flag)

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


    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, fiscal_position=False, flag=False, context=None):
        """
        If we select a product we change the procurement type to its own procurement method (procure_method).
        If there isn't product, the default procurement method is 'From Order' (make_to_order).
        Both remains changeable manually.
        """
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

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
            if data:
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

        default.update({
            'sync_order_line_db_id': False,
            'manually_corrected': False,
            'created_by_po': False,
            'created_by_po_line': False,
            'created_by_rfq': False,
            'created_by_rfq_line': False,
        })

        return super(sale_order_line, self).copy(cr, uid, id, default, context)

    def check_empty_line(self, cr, uid, ids, vals, context=None):
        '''
        Return an error if the line has no qty
        '''
        context = context is None and {} or context

        if context.get('button') in ['button_remove_lines', 'check_lines_to_fix', 'add_multiple_lines', 'wizard_import_ir_line']:
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
                ], limit=1, order='NO_ORDER', context=context)
            elif 'product_uom_qty' in vals:
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

        self.check_empty_line(cr, uid, False, vals, context=context)

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
        if order_id and self.pool.get('sale.order').read(cr, uid, order_id, ['procurement_request'], context)['procurement_request']:
            vals.update({'cost_price': vals.get('cost_price', False)})

        '''
        Add the database ID of the SO line to the value sync_order_line_db_id
        '''

        so_line_ids = super(sale_order_line, self).create(cr, uid, vals, context=context)
        if not vals.get('sync_order_line_db_id', False):  # 'sync_order_line_db_id' not in vals or vals:
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

        res = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

        return res

sale_order_line()


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
        'po_id': fields.related(
            'po_line_id',
            'order_id',
            type='many2one',
            relation='purchase.order',
        ),
    }

expected_sale_order_line()


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
        proc_obj = self.pool.get('procurement.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        for wiz in self.browse(cr, uid, ids, context=context):
            for lc in wiz.order_ids:
                if not lc.action:
                    raise osv.except_osv(
                        _('Error'),
                        _('You must choose an action for each order'),
                    )
                if lc.action == 'close':
                    proc_ids = proc_obj.search(cr, uid, [('sale_id', '=', lc.order_id.id)], context=context)
                    proc_obj.action_cancel(cr, uid, proc_ids)
                    wf_service.trg_write(uid, 'sale.order', lc.order_id.id, cr)

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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
