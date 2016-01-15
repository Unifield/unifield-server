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
import tools
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class sale_follow_up_multi_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_follow_up_multi_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'parse_date_xls': self._parse_date_xls,
            'upper': self._upper,
            'getLines': self._get_lines,
            'getOrders': self._get_orders,
            'getProducts': self._get_products,
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

    def _get_orders(self, report):
        orders = []
        for order_id in report.order_ids:
            if self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)]):
                orders.append(order_id)

        self._nb_orders = len(orders)

        for order in orders:
            yield self.pool.get('sale.order').browse(self.cr, self.uid, order)

        raise StopIteration

    def _get_products(self, order, count=False):
        '''
        Returns the list of products in the order
        '''
        self.cr.execute('''SELECT COUNT(DISTINCT(product_id)) FROM sale_order_line WHERE order_id = %(order_id)s''', {'order_id': order.id})
        return self.cr.fetchone()[0]

    def _get_order_line(self, order_id):
        order_line_ids = self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)])
        for order_line_id in order_line_ids:
            yield self.pool.get('sale.order.line').browse(self.cr, self.uid, order_line_id)

        raise StopIteration

    def _get_lines(self, order, grouped=False):
        '''
        Get all lines with OUT/PICK for an order
        '''
        keys = []
        for line in self._get_order_line(order.id):
            if not grouped:
                keys = []
            lines = []
            first_line = True
            fl_index = 0
            m_index = 0
            bo_qty = line.product_uom_qty
            for move in line.move_ids:
                m_type = move.product_qty != 0.00 and move.picking_id.type == 'out'
                ppl = move.picking_id.subtype == 'packing' and move.picking_id.shipment_id and move.location_dest_id.usage == 'customer'
                s_out = move.subtype == 'standard' and move.state == 'done' and move.location_dest_id.usage == 'customer'

                if m_type and (ppl or s_out):
                    data = {}
                    if first_line:
                        data.update({
                            'line_number': line.line_number,
                            'product_name': line.product_id.name,
                            'product_code': line.product_id.code,
                            'uom_id': line.product_uom.name,
                            'ordered_qty': line.product_uom_qty,
                            'backordered_qty': '',
                            'first_line': True,
                        })
                        first_line = False

                    if ppl:
                        packing = move.picking_id.previous_step_id.name
                        shipment = move.picking_id.shipment_id.name
                        if not grouped:
                            key = (packing, shipment, move.product_uom.name)
                        else:
                            key = (packing, shipment, move.product_uom.name, line.line_number)
                        data.update({
                            'packing': packing,
                            'shipment': shipment,
                            'delivered_qty': move.product_qty,
                            'delivered_uom': move.product_uom.name,
                            'rts': move.picking_id.shipment_id.shipment_expected_date[0:10],
                            'eta': move.picking_id.shipment_id.planned_date_of_arrival,
                            'transport': move.picking_id.shipment_id.transport_type,
                        })
                    else:
                        packing = move.picking_id.name
                        if not grouped:
                            key = (packing, False, move.product_uom.name)
                        else:
                            key = (packing, False, move.product_uom.name, line.line_number)
                        data.update({
                            'packing': packing,
                            'delivery_qty': move.product_qty,
                            'delivered_uom': move.product_uom.name,
                            'rts': move.picking_id.min_date[0:10],
                        })

                    bo_qty -= self.pool.get('product.uom')._compute_qty(
                        self.cr,
                        self.uid,
                        move.product_uom.id,
                        move.product_qty,
                        line.product_uom.id,
                    )

                    if key in keys:
                        for rline in lines:
                            if rline['packing'] == key[0] and rline['shipment'] == key[1] and rline['delivered_uom'] == key[2]:
                                if not grouped or (grouped and line.line_number == key[3]):
                                    rline.update({
                                        'delivered_qty': rline['delivered_qty'] + data['delivered_qty'],
                                    })
                    else:
                        keys.append(key)
                        lines.append(data)
                        if data.get('first_line'):
                            fl_index= m_index
                        m_index += 1

            # No move found
            if first_line:
                data = {
                    'line_number': line.line_number,
                    'product_code': line.product_id.default_code,
                    'product_name': line.product_id.name,
                    'uom_id': line.product_uom.name,
                    'ordered_qty': line.product_uom_qty,
                    'packing': '',
                    'shipment': '',
                    'delivered_qty': 0.00,
                    'delivered_uom': '',
                    'backordered_qty': line.product_uom_qty,
                }
                lines.append(data)

            # Put the backorderd qty on the first line
            if not lines:
                continue
            lines[fl_index]['backordered_qty'] = bo_qty

            for line in lines:
                yield line

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
    'report.sales.follow.up.multi.report_pdf',
    'sale.followup.multi.wizard',
    'addons/sales_followup/report/sale_follow_up_multi_report.rml',
    parser=sale_follow_up_multi_report_parser,
    header=False)


class sale_follow_up_multi_report_xls(SpreadsheetReport):
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse,
        header='external', store=False):
        super(sale_follow_up_multi_report_xls, self).__init__(name, table,
            rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(sale_follow_up_multi_report_xls, self).create(cr, uid, ids,
        data, context)
        return (a[0], 'xls')

sale_follow_up_multi_report_xls(
    'report.sales.follow.up.multi.report_xls',
    'sale.followup.multi.wizard',
    'addons/sales_followup/report/sale_follow_up_multi_report_xls.mako',
    parser=sale_follow_up_multi_report_parser,
    header=False)
