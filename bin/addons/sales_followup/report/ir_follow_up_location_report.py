# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

from datetime import datetime
from datetime import timedelta

import tools
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class ir_follow_up_location_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(ir_follow_up_location_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'parse_date_xls': self._parse_date_xls,
            'upper': self._upper,
            'getLines': self._get_lines,
            'getOrders': self._get_orders,
            'getProducts': self._get_products,
            'getIrAmountEstimated': self._get_ir_amount_estimated,
            'saleUstr': self._sale_ustr,
        })
        self._order_iterator = 0
        self._nb_orders = 0
        self._dates_context = {}
        self._report_context = {}

        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

    def _sale_ustr(self, string):
        return tools.ustr(string)

    def _get_orders(self, report, grouped=False, only_bo=False):
        orders = []
        for order_id in report.order_ids:
            if self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)]):
                orders.append(order_id)

        self._nb_orders = len(orders)

        for order in orders:
            if only_bo:
                for line in self._get_lines(order, grouped=grouped, only_bo=only_bo):
                    # A line exist, just break the second loop
                    break
                else:
                    # No line exist for this order, go to the next one
                    continue
            yield self.pool.get('sale.order').browse(self.cr, self.uid, order)

        raise StopIteration

    def _get_products(self, order, count=False):
        '''
        Returns the list of products in the order
        '''
        self.cr.execute('''SELECT COUNT(DISTINCT(product_id)) FROM sale_order_line WHERE order_id = %(order_id)s''', {'order_id': order.id})
        return self.cr.fetchone()[0]

    def _get_ir_amount_estimated(self, order):
        '''
        Return the estimated amount for the IR
        '''
        sol_obj = self.pool.get('sale.order.line')
        sol_ids = sol_obj.search(self.cr, self.uid, [('order_id', '=', order.id)])
        res = 0.00

        for sol_id in sol_ids:
            sol = sol_obj.browse(self.cr, self.uid, sol_id)
            res += (sol.cost_price * sol.product_uom_qty)
        if res > 0:
            res += order.amount_tax

        return res

    def _get_order_line(self, order_id):
        order_line_ids = self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)])
        for order_line_id in order_line_ids:
            yield self.pool.get('sale.order.line').browse(self.cr, self.uid, order_line_id, context=self.localcontext)

        raise StopIteration

    def _is_returned(self, move):
        '''
        Is the given move returned at shipment level ?
        '''
        if not move.picking_id or not move.picking_id.shipment_id:
            return False
        for pack_fam_mem in move.picking_id.shipment_id.pack_family_memory_ids:
            for m in pack_fam_mem.move_lines:
                if m.not_shipped and m.id == move.id:
                    return True
        return False

    def _get_move_from_line(self, product_id, origin):
        '''
        Returns the move of the given line
        '''
        res = False
        sm_obj = self.pool.get('stock.move')
        sm_ids = sm_obj.search(self.cr, self.uid, {('product_id', '=', product_id), ('origin', 'like', origin)}, order='id desc')

        if len(sm_ids) > 0:
            res = sm_obj.browse(self.cr, self.uid, sm_ids[0])

        return res

    def _get_lines(self, order_id, grouped=False, only_bo=False):
        '''
        Get all lines with OUT/PICK for an order
        '''
        keys = []

        if only_bo:
            grouped = True

        if not isinstance(order_id, int):
            order_id = order_id.id

        for line in self._get_order_line(order_id):
            if not grouped:
                keys = []
            lines = []
            first_line = True
            fl_index = 0
            m_index = 0
            bo_qty = line.product_uom_qty
            po_name = ''
            cdd = False
            from_stock = line.type == 'make_to_stock'
            if line.procurement_id and line.procurement_id.purchase_id:
                po_name = line.procurement_id.purchase_id.name
                cdd = line.procurement_id.purchase_id.delivery_confirmed_date
            if not cdd and line.order_id.delivery_confirmed_date:
                cdd = line.order_id.delivery_confirmed_date

            # fetch the move in case the line doesn't have move_ids
            # if no move found for this line, it's set to False
            line_move = self._get_move_from_line(line.product_id.id, line.order_id.name)

            if len(line.move_ids) > 0 and not from_stock:
                for move in line.move_ids:
                    m_type = move.product_qty != 0.00 and move.picking_id.type == 'out'
                    ppl = move.picking_id.subtype == 'packing' and move.picking_id.shipment_id and not self._is_returned(move)
                    ppl_not_shipped = move.picking_id.subtype == 'ppl' and move.picking_id.state not in ('cancel', 'done')
                    s_out = move.picking_id.subtype == 'standard' and move.state == 'done' and move.location_dest_id.usage == 'customer'

                    if m_type and (ppl or s_out or ppl_not_shipped):
                        # bo_qty < 0 if we receipt (IN) more quantities then expected (FO):
                        bo_qty -= self.pool.get('product.uom')._compute_qty(
                            self.cr,
                            self.uid,
                            move.product_uom.id,
                            move.product_qty,
                            line.product_uom.id,
                        )
                        data = {
                            'po_name': po_name,
                            'cdd': cdd,
                            'line_number': line.line_number,
                            'line_comment': line.comment,
                            'product_name': line.product_id.name,
                            'product_code': line.product_id.code,
                            'is_delivered': False,
                            'delivery_order': move.picking_id.name,
                        }
                        if first_line:
                            data.update({
                                'uom_id': line.product_uom.name,
                                'ordered_qty': line.product_uom_qty,
                                'backordered_qty': 0.00,
                                'first_line': True,
                            })
                            first_line = False

                        if ppl or ppl_not_shipped:
                            is_delivered = False
                            is_shipment_done = False
                            if ppl:
                                is_delivered = move.picking_id.shipment_id.state == 'delivered' or False
                                is_shipment_done = move.picking_id.shipment_id.state == 'done' or False

                            if not grouped:
                                key = (move.product_uom.name)
                            else:
                                key = (move.product_uom.name, line.line_number)
                            data.update({
                                'is_delivered': is_delivered,
                                'delivered_qty': not only_bo and (is_shipment_done or is_delivered) and move.product_qty or 0.00,
                                'delivered_uom': not only_bo and (is_shipment_done or is_delivered) and move.product_uom.name or '',
                                'backordered_qty': not is_shipment_done and not is_delivered and line.order_id.state != 'cancel' and move.product_qty or 0.00,
                                'rts': not only_bo and move.picking_id.shipment_id and move.picking_id.shipment_id.shipment_expected_date[0:10] or '',
                            })
                        else:
                            if move.picking_id.type == 'out' and move.picking_id.subtype == 'packing':
                                is_shipment_done = move.picking_id.shipment_id.state == 'done'
                            else:
                                is_shipment_done = move.picking_id.state == 'done'
                            if not grouped:
                                key = (move.product_uom.name)
                            else:
                                key = (move.product_uom.name, line.line_number)
                            if not only_bo:
                                data.update({
                                    'delivered_qty': is_shipment_done and move.product_qty or 0.00,
                                    'delivered_uom': is_shipment_done and move.product_uom.name or '',
                                    'rts': line.order_id.ready_to_ship_date,
                                })

                        if key in keys:
                            for rline in lines:
                                if rline['delivered_uom'] == key[1]:
                                    if not grouped or (grouped and line.line_number == key[2]):
                                        rline.update({
                                            'delivered_qty': rline['delivered_qty'] + data['delivered_qty'],
                                        })
                        else:
                            keys.append(key)
                            lines.append(data)
                            if data.get('first_line'):
                                fl_index = m_index
                            m_index += 1
            elif line_move and ((len(line.move_ids) == 0 and line.procurement_id.move_id) or from_stock):
                m_type = line_move.product_qty != 0.00

                if m_type:
                    # bo_qty < 0 if we receipt (IN) more quantities then expected (FO):
                    bo_qty -= self.pool.get('product.uom')._compute_qty(
                        self.cr,
                        self.uid,
                        line_move.product_uom.id,
                        line_move.product_qty,
                        line.product_uom.id,
                    )
                    delivery_order = line_move.picking_id.name
                    if 'INT' in line_move.picking_id.name and line_move.picking_id.state != 'done':
                        delivery_order = ''
                    data = {
                        'po_name': po_name,
                        'cdd': cdd,
                        'line_number': line.line_number,
                        'line_comment': line.comment,
                        'product_name': line.product_id.name,
                        'product_code': line.product_id.code,
                        'is_delivered': False,
                        'delivery_order': delivery_order,
                    }
                    if first_line:
                        data.update({
                            'uom_id': line.product_uom.name,
                            'ordered_qty': line.product_uom_qty,
                            'backordered_qty': 0.00,
                            'first_line': True,
                        })
                        first_line = False

                    is_done = line_move.picking_id.state == 'done'
                    if not grouped:
                        key = line_move.product_uom.name
                    else:
                        key = (line_move.product_uom.name, line.line_number)
                    if not only_bo:
                        data.update({
                            'delivered_qty': is_done and line_move.product_qty or 0.00,
                            'delivered_uom': is_done and line_move.product_uom.name or '',
                            'is_delivered': is_done,
                            'backordered_qty': not is_done and line.order_id.state != 'cancel' and line_move.product_qty or 0.00,
                            'rts': line.order_id.ready_to_ship_date,
                        })

                    if key in keys:
                        for rline in lines:
                            if rline['delivered_uom'] == key[1]:
                                if not grouped or (grouped and line.line_number == key[2]):
                                    rline.update({
                                        'delivered_qty': rline['delivered_qty'] + data['delivered_qty'],
                                    })
                    else:
                        keys.append(key)
                        lines.append(data)
                        if data.get('first_line'):
                            fl_index = m_index
                        m_index += 1
            else:  # No move found
                if first_line:
                    data = {
                        'line_number': line.line_number,
                        'line_comment': line.comment,
                        'po_name': po_name,
                        'product_code': line.product_id.default_code,
                        'product_name': line.product_id.name,
                        'uom_id': line.product_uom.name,
                        'ordered_qty': line.product_uom_qty,
                        'rts': line.order_id.state not in ('draft', 'validated', 'cancel') and line.order_id.ready_to_ship_date or '',
                        'delivered_qty': 0.00,
                        'delivered_uom': '',
                        'delivery_order': '',
                        'backordered_qty': line.product_uom_qty if line.order_id.state != 'cancel' else 0.00,
                        'cdd': cdd,
                    }
                    lines.append(data)

            # Put the backorderd qty on the first line
            if not lines:
                continue
            if not only_bo and bo_qty and bo_qty > 0 and not first_line and line.order_id.state != 'cancel':
                lines.append({
                    'po_name': po_name,
                    'cdd': cdd,
                    'line_number': line.line_number,
                    'line_comment': line.comment,
                    'product_name': line.product_id.name,
                    'product_code': line.product_id.code,
                    'is_delivered': False,
                    'backordered_qty': bo_qty if line.order_id.state != 'cancel' else 0.00,
                })
            elif only_bo:
                lines[fl_index].update({
                    'backordered_qty': bo_qty if line.order_id.state != 'cancel' else 0.00,
                })

            elif bo_qty < 0:
                lines[fl_index]['extra_qty'] = abs(bo_qty) if line.order_id.state != 'cancel' else 0.00

            for ln in lines:
                if only_bo and ln.get('backordered_qty', 0.00) <= 0.00:
                    continue
                elif only_bo:
                    ln['delivered_qty'] = line.product_uom_qty - ln.get('backordered_qty', 0.00)
                yield ln

        self._order_iterator += 1

        if self.back_browse:
            percent = float(self._order_iterator) / float(self._nb_orders)
            self.pool.get('memory.background.report').update_percent(self.cr, self.uid, [self.back_browse.id], percent)

        raise StopIteration

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def _upper(self, s):
        if not isinstance(s, (str, unicode)):
            return s
        if s:
            return s.upper()
        return s

report_sxw.report_sxw(
    'report.ir.follow.up.location.report_pdf',
    'ir.followup.location.wizard',
    'addons/sales_followup/report/ir_follow_up_location_report.rml',
    parser=ir_follow_up_location_report_parser,
    header=False)


class ir_follow_up_location_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
                 header='external', store=False):
        super(ir_follow_up_location_report_xls, self).__init__(name, table,
                                                              rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(ir_follow_up_location_report_xls, self).create(cr, uid, ids,
                                                                data, context)
        return (a[0], 'xls')

ir_follow_up_location_report_xls(
    'report.ir.follow.up.location.report_xls',
    'ir.followup.location.wizard',
    'addons/sales_followup/report/ir_follow_up_location_report_xls.mako',
    parser=ir_follow_up_location_report_parser,
    header=False)
