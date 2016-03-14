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

import netsvc
from osv import osv
from osv.orm import except_orm
import pooler
import tools
from tools.translate import _
from threading import Lock
import logging

class procurement_order(osv.osv):
    _inherit = 'procurement.order'
    
    def _hook_request_vals(self, cr, uid, *args, **kwargs):
        '''
        Hook to change the request values
        '''
        return kwargs['request_vals']
    
    def _hook_add_purchase_created(self, cr, uid, *args, **kwargs):
        '''
        Returns the created docs in report
        '''
        return ''

    def _procure_confirm(self, cr, uid, ids=None, use_new_cursor=False, context=None):
        '''
        Call the scheduler to check the procurement order

        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param ids: List of selected IDs
        @param use_new_cursor: False or the dbname
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        '''
        logger = logging.getLogger('procure.confirm')

        if context is None:
            context = {}

        try:
            if use_new_cursor:
                cr = pooler.get_db(use_new_cursor).cursor()
            wf_service = netsvc.LocalService("workflow")

            procurement_obj = self.pool.get('procurement.order')
            if not ids:
                ids = procurement_obj.search(cr, uid, [], order="date_planned")
            for id in ids:
                wf_service.trg_validate(uid, 'procurement.order', id, 'button_restart', cr)
            if use_new_cursor:
                cr.commit()
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            maxdate = (datetime.today() + relativedelta(days=company.schedule_range)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            start_date = time.strftime('%Y-%m-%d, %Hh %Mm %Ss')
            offset = 0
            report = []
            report_total = 0
            report_except = 0
            report_later = 0
            purchase_ids = []
            while True:
                cr.execute("select id from procurement_order where state='confirmed' and procure_method='make_to_order' order by priority,date_planned limit 500 offset %s", (offset,))
                ids = map(lambda x: x[0], cr.fetchall())
                # Put a lock on procurement.order
                procurement_obj.write(cr, uid, ids, {}, context=context)
                for proc in procurement_obj.browse(cr, uid, ids, context=context):
                    if maxdate >= proc.date_planned:
                        try:
                            wf_service.trg_validate(uid, 'procurement.order', proc.id, 'button_check', cr)
                        except except_orm, e:
                            ids.remove(proc.id)
                            continue
                    else:
                        offset += 1
                        report_later += 1
                for proc in procurement_obj.browse(cr, uid, ids, context=context):
                    if proc.state == 'exception':
                        report.append('PROC %d: on order - %3.2f %-5s - %s' % \
                                (proc.id, proc.product_qty, proc.product_uom.name,
                                    proc.product_id.name))
                        report_except += 1
                    elif proc.purchase_id:
                        purchase_ids.append(proc.id)
                    report_total += 1
                if use_new_cursor:
                    cr.commit()
                if not ids:
                    break
            offset = 0
            ids = []
            while True:
                report_ids = []
                ids = procurement_obj.search(cr, uid, [('state', '=', 'confirmed'), ('procure_method', '=', 'make_to_stock')], offset=offset)
                for proc in procurement_obj.browse(cr, uid, ids):
                    if maxdate >= proc.date_planned:
                        wf_service.trg_validate(uid, 'procurement.order', proc.id, 'button_check', cr)
                        report_ids.append(proc.id)
                    else:
                        report_later += 1
                    report_total += 1
                for proc in procurement_obj.browse(cr, uid, report_ids, context=context):
                    if proc.state == 'exception':
                        report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                                (proc.id, proc.product_qty, proc.product_uom.name,
                                    proc.product_id.name,))
                        report_except += 1
                if use_new_cursor:
                    cr.commit()
                offset += len(ids)
                if not ids: break
            end_date = time.strftime('%Y-%m-%d, %Hh %Mm %Ss')
            if uid:
                request = self.pool.get('res.request')
                summary = '''Here is the procurement scheduling report.

        Start Time: %s
        End Time: %s
        Total Procurements processed: %d
        Procurements with exceptions: %d
        Skipped Procurements (scheduled date outside of scheduler range) %d

        \n'''% (start_date, end_date, report_total, report_except, report_later)
                if purchase_ids:
                    summary += self._hook_add_purchase_created(cr, uid, purchase_ids=purchase_ids)
                summary += '''
        Exception : \n
        '''
                summary += '\n'.join(report)
                request_vals = {'name': "Procurement Processing Report.",
                        'act_from': uid,
                        'act_to': uid,
                        'body': summary,
                    }
                self._hook_request_vals(cr, uid, request_vals=request_vals, context=context)
                request.create(cr, uid, request_vals)

            if use_new_cursor:
                cr.commit()
        finally:
            if use_new_cursor:
                try:
                    cr.close()
                except Exception:
                    pass
        return {}

    def create_automatic_op(self, cr, uid, context=None):
        """
        Create procurement of  virtual stock < 0

        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        """
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        proc_obj = self.pool.get('procurement.order')
        warehouse_obj = self.pool.get('stock.warehouse')
        wf_service = netsvc.LocalService("workflow")

        warehouse_ids = warehouse_obj.search(cr, uid, [], context=context)

        cr.execute('select p.id from product_product p \
                        join product_template t on (p.product_tmpl_id=t.id) \
                        where p.active=True and t.purchase_ok=True')
        products_id = [x for x, in cr.fetchall()]

        for warehouse in warehouse_obj.browse(cr, uid, warehouse_ids, context=context):
            context['warehouse'] = warehouse
            for product in product_obj.browse(cr, uid, products_id, context=context):
                if product.virtual_available >= 0.0:
                    continue

                newdate = datetime.today()
                if product.supply_method == 'buy':
                    location_id = warehouse.lot_input_id.id
                elif product.supply_method == 'produce':
                    location_id = warehouse.lot_stock_id.id
                else:
                    continue
                proc_id = proc_obj.create(cr, uid, {
                    'name': _('Automatic OP: %s') % (product.name,),
                    'origin': _('SCHEDULER'),
                    'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                    'product_id': product.id,
                    'product_qty': -product.virtual_available,
                    'product_uom': product.uom_id.id,
                    'location_id': location_id,
                    'procure_method': 'make_to_order',
                    })
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_check', cr)
                
    def _do_create_proc_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        hook to update defaults data
        kwargs['op'] is the current min/max rule
        kwargs['opl'] is the current min/max rule line
        kwargs['qty'] is the quantity to generate
        kwargs['newdate'] is the new planned date
        '''
        op = kwargs.get('op', False)
        opl = kwargs.get('opl', False)
        qty = kwargs.get('qty', False)
        newdate = kwargs.get('newdate', False)
        assert op, 'missing op'
        assert qty, 'missing qty'
        assert newdate, 'missing newdate'
        
        values = {'name': op.name,
                  'date_planned': newdate.strftime('%Y-%m-%d'),
                  'product_id': opl.product_id.id,
                  'product_qty': qty,
                  'product_uom': opl.product_uom_id.id,
                  'location_id': op.location_id.id,
                  'procure_method': 'make_to_order',
                  'origin': op.name,
                  }
        
        return values
    
    def _hook_product_type_consu(self, cr, uid, *args, **kwargs):
        '''
        kwargs['op'] is the current min/max rule
        kwargs['opl'] is the current min/max rule line
        '''
        opl = kwargs['opl']
        return opl.product_id.type not in ('consu')

    def _procure_orderpoint_confirm(self, cr, uid, automatic=False,
            use_new_cursor=False, context=None, user_id=False):
        '''
        Create procurement based on Orderpoint
        use_new_cursor: False or the dbname

        UTP-1186:
            - compute is done now at stock warehouse order point LINE level,
            - each stock warehouse order point line is linked to a procurement,
            - the procurement at header level is just a link to the last
                procurement created at line level.

        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param user_id: The current user ID for security checks
        @param context: A standard dictionary for contextual values
        @param param: False or the dbname
        @return:  Dictionary of values
        """
        '''
        if context is None:
            context = {}
        if use_new_cursor:
            cr = pooler.get_db(use_new_cursor).cursor()
        orderpoint_obj = self.pool.get('stock.warehouse.orderpoint')
        orderpoint_line_obj = self.pool.get('stock.warehouse.orderpoint.line')
        location_obj = self.pool.get('stock.location')
        procurement_obj = self.pool.get('procurement.order')
        request_obj = self.pool.get('res.request')
        wf_service = netsvc.LocalService("workflow")
        report = []
        offset = 0
        ids = [1]
        created_proc = []
        report_except = 0
        start_date = time.strftime('%Y-%m-%d %H:%M:%S')
        if automatic:
            self.create_automatic_op(cr, uid, context=context)

        self.check_exception_proc(cr, uid, [], context=context)

        while ids:
            ids = orderpoint_obj.search(cr, uid, [], offset=offset, limit=100)
            # Put a lock on stock.warehouse.orderpoint
            orderpoint_obj.write(cr, uid, ids, {}, context=context)
            for op in orderpoint_obj.browse(cr, uid, ids, context=context):
                for opl in op.line_ids:
                    if opl.procurement_id.state != 'exception':
                        if opl.procurement_id and \
                            opl.procurement_id.purchase_id and \
                            opl.procurement_id.purchase_id.state in (
                                'draft', 'confirmed'):
                            continue

                    prods = location_obj._product_virtual_get(cr, uid,
                            op.location_id.id, [opl.product_id.id],
                            {'uom': opl.product_uom_id.id},
                            ['confirmed', 'waiting', 'assigned', 'done', 'hidden'])[opl.product_id.id]

                    if prods < opl.product_min_qty:
                        qty = max(opl.product_min_qty, opl.product_max_qty)-prods

                        reste = qty % opl.qty_multiple
                        if reste > 0:
                            qty += opl.qty_multiple - reste

                        newdate = datetime.today() + relativedelta(
                                days = int(opl.product_id.seller_delay))
                        if qty <= 0:
                            continue
                        if self._hook_product_type_consu(cr, uid, op=op, opl=opl):
    #                    if opl.product_id.type not in ('consu'):
                            if opl.procurement_id and \
                                opl.procurement_id.state == 'draft':
                                # Check draft procurement related to this order point line
                                pro_ids = [x.id for x in op.procurement_draft_ids]
                                cr.execute('select id, product_qty from procurement_order where id = %s order by product_qty desc', str(opl.procurement_id.id))
                                procure_datas = cr.dictfetchall()
                                to_generate = qty
                                for proc_data in procure_datas:
                                    if to_generate >= proc_data['product_qty']:
                                        wf_service.trg_validate(uid,
                                            'procurement.order',
                                            proc_data['id'], 'button_confirm',
                                            cr)
                                        procurement_obj.write(cr, uid,
                                            [proc_data['id']],
                                            {'origin': op.name},
                                            context=context)
                                        to_generate -= proc_data['product_qty']
                                    if not to_generate:
                                        break
                                qty = to_generate

                        if qty:
                            values = self._do_create_proc_hook(cr, uid, ids,
                                context=context, op=op, opl=opl, qty=qty,
                                newdate=newdate)
                            proc_id = procurement_obj.create(cr, uid, values,
                                context=context)
                            created_proc.append(proc_id)
                            wf_service.trg_validate(uid, 'procurement.order',
                                proc_id, 'button_confirm', cr)
                            wf_service.trg_validate(uid, 'procurement.order',
                                proc_id, 'button_check', cr)
                            orderpoint_line_obj.write(cr, uid, [opl.id],
                                    {'procurement_id': proc_id},
                                    context=context)  # order point line procurement created
                            orderpoint_obj.write(cr, uid, [op.id],
                                    {'procurement_id': proc_id},
                                    context=context)  # header level log of last procurement created
            offset += len(ids)
            if use_new_cursor:
                cr.commit()

        ###
        # Add created document and exception in a request
        ###
        created_doc = '''################################
 Created documents : \n'''

        for proc in procurement_obj.browse(cr, uid, created_proc):
            if proc.state == 'exception':
                report.append('PROC %d: from stock - %3.2f %-5s - %s' % \
                    (proc.id, proc.product_qty, proc.product_uom.name,
                     proc.product_id.name,))
                report_except += 1
            elif proc.purchase_id:
                created_doc += "    * %s => %s \n" % (proc.name, proc.purchase_id.name)

        end_date = time.strftime('%Y-%m-%d %H:%M:%S')

        summary = '''Here is the procurement scheduling report for Automatic Supplies

 Start Time: %s
 End Time: %s
 Total Procurements processed: %d
 Procurements with exceptions: %d
 
 \n %s \n  Exceptions: \n'''% (start_date, end_date, len(created_proc), report_except, len(created_proc) > 0 and created_doc or '')

        summary += '\n'.join(report)

        if uid and summary:
            request_vals = {
                'name': "Procurement Processing Report (Min/Max rules).",
                'act_from': uid,
                'act_to': uid,
                'body': summary,
            }
            request_vals = self._hook_request_vals(cr, uid, request_vals=request_vals, context=context)
            request_obj.create(cr, uid, request_vals)
        if use_new_cursor:
            cr.commit()
            cr.close()
        return {}

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
