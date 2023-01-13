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

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class sale_follow_up_multi_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(sale_follow_up_multi_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLang': self._get_lang,
            'parse_date_xls': self._parse_date_xls,
            'upper': self._upper,
            'getLines': self._get_lines,
            'getOrders': self._get_orders,
            'getProducts': self._get_products,
        })
        self._order_iterator = 0
        self._nb_orders = 0
        self._dates_context = {}
        self._report_context = {}

        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

    def _get_lang(self):
        return self.localcontext.get('lang', 'en_MF')

    def _get_orders(self, report, grouped=False, only_bo=False):
        orders = []
        for order_id in report.order_ids:
            if self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)]):
                orders.append(order_id)

        self._nb_orders = len(orders)

        for order in orders:
            if only_bo:
                for line in self._get_lines(order, grouped=grouped, only_bo=only_bo):
                    # A line existe, just break the second loop
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

    def _get_order_line(self, order_id):
        order_line_ids = self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)])
        ftf = ['id', 'line_number', 'state', 'state_to_display', 'order_id', 'product_id', 'product_uom_qty',
               'product_uom', 'esti_dd', 'confirmed_delivery_date', 'move_ids']
        for order_line_id in order_line_ids:
            yield self.pool.get('sale.order.line').browse(self.cr, self.uid, order_line_id,
                                                          fields_to_fetch=ftf, context=self.localcontext)

        raise StopIteration

    def _is_returned(self, move):
        '''
        Is the given move returned at shipment level ?
        '''
        if not move.picking_id or not move.picking_id.shipment_id:
            return False
        self.cr.execute('''SELECT id FROM stock_move WHERE not_shipped = 't' AND pick_shipment_id = %s AND id = %s''',
                        (move.picking_id.shipment_id.id, move.id))
        if self.cr.fetchone():
            return True
        return False

    def in_line_data_expected_date(self, pol_id):
        '''
         Get data from the IN moves' linked to the PO
        '''
        self.cr.execute('''
            SELECT DISTINCT(m.date_expected) FROM stock_move m, stock_picking p
            WHERE m.picking_id = p.id AND m.purchase_line_id = %s AND p.type = 'in' AND m.state != 'cancel'
        ''', (pol_id,))

        return [data[0] for data in self.cr.fetchall()]

    def _get_lines(self, order_id, grouped=False, only_bo=False):
        '''
        Get all lines with OUT/PICK for an order
        '''
        sol_obj = self.pool.get('sale.order.line')
        pol_obj = self.pool.get('purchase.order.line')
        uom_obj = self.pool.get('product.uom')
        ship_obj = self.pool.get('shipment')
        keys = []

        if only_bo:
            grouped = True

        transport_info = ship_obj.fields_get(self.cr, self.uid, ['transport_type'], context=self.localcontext).get('transport_type', {}).get('selection', {})
        transport_dict = dict(transport_info)
        if not isinstance(order_id, int):
            order_id = order_id.id

        line_state_display_dict = dict(sol_obj.fields_get(self.cr, self.uid, ['state_to_display'], context=self.localcontext).get('state_to_display', {}).get('selection', []))
        for line in self._get_order_line(order_id):
            if not grouped:
                keys = []
            lines = []
            first_line = True
            fl_index = 0
            m_index = 0
            bo_qty = line.product_uom_qty
            po_name = '-'

            supplier_name = '-'

            edd = False
            cdd = False
            if self.localcontext.get('lang', False) == 'fr_MF':
                date_format = '%d/%m/%Y'
            else:
                date_format = '%d-%b-%Y'

            linked_pol = pol_obj.search(self.cr, self.uid, [('linked_sol_id', '=', line.id)])
            if linked_pol:
                linked_pol = pol_obj.browse(self.cr, self.uid, linked_pol)[0]
                po_name = linked_pol.order_id.name
                edd = linked_pol.esti_dd or linked_pol.order_id.delivery_requested_date_modified
                cdd = linked_pol.confirmed_delivery_date
                supplier_name = linked_pol.order_id.partner_id.name
                if line.product_id:
                    in_data = self.in_line_data_expected_date(linked_pol.id)
                    if len(in_data) > 1:
                        cdd = ', '.join([datetime.strptime(exp_date[:10], '%Y-%m-%d').strftime(date_format) for exp_date in in_data])
                    elif len(in_data) == 1:
                        cdd = in_data[0][:10]
            if not edd and line.esti_dd:
                edd = line.esti_dd
            if not cdd and (line.confirmed_delivery_date or line.order_id.delivery_confirmed_date):
                cdd = line.confirmed_delivery_date or line.order_id.delivery_confirmed_date

            data = {
                'state': line.state,
                'state_display': line_state_display_dict.get(line.state_to_display),
            }

            for move in line.move_ids:
                m_type = move.product_qty != 0.00 and move.picking_id.type == 'out'
                ppl = move.picking_id.subtype == 'packing' and move.picking_id.shipment_id and not self._is_returned(move)
                ppl_not_shipped = move.picking_id.subtype == 'ppl' and move.picking_id.state not in ('cancel', 'done')
                s_out = move.picking_id.subtype == 'standard' and move.state == 'done' and move.location_dest_id.usage == 'customer'
                cancelled_pick = line.state not in ('cancel', 'cancel_r') and move.picking_id.type == 'out' and\
                                 move.picking_id.subtype in ('standard', 'picking') and move.state == 'cancel'
                if m_type and (ppl or s_out or ppl_not_shipped or cancelled_pick):
                    # bo_qty < 0 if we receipt (IN) more quantities then expected (FO):
                    bo_qty -= uom_obj._compute_qty(self.cr, self.uid, move.product_uom.id, move.product_qty, line.product_uom.id)
                    data.update({
                        'po_name': po_name,
                        'supplier_name': supplier_name,
                        'edd': edd,
                        'cdd': cdd,
                        'line_number': line.line_number,
                        'product_name': line.product_id.name,
                        'product_code': line.product_id.code,
                        'is_delivered': False,
                        'backordered_qty': 0.00,
                    })
                    if first_line:
                        data.update({
                            'uom_id': line.product_uom.name,
                            'ordered_qty': line.product_uom_qty,
                            'backordered_qty': 0.00,
                            'first_line': True,
                        })
                        first_line = False

                    if ppl or ppl_not_shipped:
                        eta = ''
                        is_delivered = False
                        is_shipment_done = False
                        if ppl:
                            packing = move.picking_id.previous_step_id.name or '-'
                            shipment = move.picking_id.shipment_id and move.picking_id.shipment_id.name or '-'
                            eta = datetime.strptime(move.picking_id.shipment_id.shipment_actual_date[0:10], '%Y-%m-%d')
                            eta += timedelta(days=line.order_id.partner_id.supplier_lt or 0.00)
                            is_delivered = move.picking_id.shipment_id.state == 'delivered' or False
                            is_shipment_done = move.picking_id.shipment_id.state == 'done' or False
                        else:
                            packing = move.picking_id.name or '-'
                            shipment = '-'

                        if not grouped:
                            key = (packing, shipment, move.product_uom.name)
                        else:
                            key = (packing, shipment, move.product_uom.name, line.line_number)
                        data.update({
                            'packing': packing,
                            'shipment': shipment,
                            'is_delivered': is_delivered,
                            'delivered_qty': not only_bo and (is_shipment_done or is_delivered) and move.product_qty or 0.00,
                            'delivered_uom': not only_bo and (is_shipment_done or is_delivered) and move.product_uom.name or '-',
                            'backordered_qty': not is_shipment_done and not is_delivered and line.order_id.state != 'cancel' and move.product_qty or 0.00,
                            'rts': not only_bo and move.picking_id.shipment_id and move.picking_id.shipment_id.shipment_expected_date[0:10] or '',
                            'eta': not only_bo and eta and eta.strftime('%Y-%m-%d'),
                            'transport': not only_bo and move.picking_id.shipment_id and transport_dict.get(move.picking_id.shipment_id.transport_type, ''),
                        })
                    elif cancelled_pick:
                        data.update({
                            'ordered_qty': line.product_uom_qty,
                            'rts': line.order_id.state not in ('draft', 'validated', 'cancel') and line.order_id.ready_to_ship_date,
                            'delivered_qty': 0.00,
                            'delivered_uom': '-',
                        })
                        if not grouped:
                            key = (False, False, move.product_uom.name)
                        else:
                            key = (False, False, move.product_uom.name, line.line_number)
                    else:
                        if move.picking_id.type == 'out' and move.picking_id.subtype == 'packing':
                            packing = move.picking_id.previous_step_id.name
                            shipment = move.picking_id.shipment_id.name or '-'
                            is_shipment_done = move.picking_id.shipment_id.state in ('done', 'delivered')
                        else:
                            shipment = move.picking_id.name or '-'
                            is_shipment_done = move.picking_id.state in ('done', 'delivered')
                            packing = '-'
                        if not grouped:
                            key = (packing, s_out and shipment or False, move.product_uom.name)
                        else:
                            key = (packing, s_out and shipment or False, move.product_uom.name, line.line_number)
                        if not only_bo:
                            data.update({
                                'packing': packing,
                                'is_delivered': is_shipment_done,
                                'delivered_qty': is_shipment_done and move.product_qty or 0.00,
                                'delivered_uom': is_shipment_done and move.product_uom.name or '-',
                                'rts': line.order_id.ready_to_ship_date,
                                'shipment': shipment,
                            })

                    if key in keys and lines:
                        for rline in lines:
                            if rline['packing'] == key[0] and rline['shipment'] == key[1] and rline['delivered_uom'] == key[2]:
                                if not grouped or (grouped and line.line_number == key[3]):
                                    rline.update({
                                        'delivered_qty': rline['delivered_qty'] + data['delivered_qty'],
                                    })
                            if rline['packing'] == key[0] and rline['shipment'] == key[1] and move.product_uom.name == key[2]\
                                    and (ppl_not_shipped or not is_shipment_done):
                                if not grouped or (grouped and line.line_number == key[3]):
                                    rline.update({
                                        'backordered_qty': rline['backordered_qty'] + data['backordered_qty'],
                                    })
                    else:
                        keys.append(key)
                        lines.append(data)
                        if data.get('first_line'):
                            fl_index = m_index
                        m_index += 1

                    # reset the data to prevent delivered_qty problem when line is split in PICK
                    data = {}

            if first_line:
                if linked_pol and linked_pol.order_type == 'direct' and linked_pol.state == 'done':
                    data = {
                        'line_number': line.line_number,
                        'po_name': po_name,
                        'supplier_name': supplier_name,
                        'edd': edd,
                        'cdd': cdd,
                        'rts': line.state not in ('draft', 'validated', 'validated_n', 'cancel', 'cancel_r')
                        and line.order_id.ready_to_ship_date or '',
                        'product_name': line.product_id.name,
                        'product_code': line.product_id.code,
                        'backordered_qty': 0.00,
                        'uom_id': line.product_uom.name,
                        'ordered_qty': line.product_uom_qty,
                        'delivered_uom': line.product_uom.name,
                        'delivered_qty': line.product_uom_qty,
                        'first_line': True,
                        'is_delivered': True,
                    }
                    bo_qty -= line.product_uom_qty
                    first_line = False
                else:
                    data.update({
                        'line_number': line.line_number,
                        'po_name': po_name,
                        'supplier_name': supplier_name,
                        'product_code': line.product_id.default_code,
                        'product_name': line.product_id.name,
                        'uom_id': line.product_uom.name,
                        'ordered_qty': line.product_uom_qty,
                        'rts': line.order_id.state not in ('draft', 'validated', 'cancel') and line.order_id.ready_to_ship_date,
                        'delivered_qty': 0.00,
                        'delivered_uom': '-',
                        'backordered_qty': line.product_uom_qty if line.order_id.state != 'cancel' else 0.00,
                        'edd': edd,
                        'cdd': cdd,
                    })
                lines.append(data)
            # Put the backorderd qty on the first line
            if not lines:
                continue
            if not only_bo and bo_qty and bo_qty > 0 and not first_line and line.order_id.state != 'cancel':
                lines.append({
                    'po_name': po_name,
                    'supplier_name': supplier_name,
                    'edd': edd,
                    'cdd': cdd,
                    'line_number': line.line_number,
                    'product_name': line.product_id.name,
                    'product_code': line.product_id.code,
                    'is_delivered': False,
                    'backordered_qty': bo_qty if line.order_id.state != 'cancel' else 0.00,
                })
            elif only_bo:
                lines[fl_index].update({
                    'backordered_qty': bo_qty if line.order_id.state != 'cancel' else 0.00,
                })
                if not first_line:
                    lines[fl_index].update({
                        'shipment': '-',
                        'packing': '-',
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
