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


class ir_follow_up_location_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context=None):
        super(ir_follow_up_location_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'getLang': self._get_lang,
            'parse_date_xls': self._parse_date_xls,
            'upper': self._upper,
            'getLines': self._get_lines,
            'getOrders': self._get_orders,
            'getProducts': self._get_products,
            'getIrAmountEstimated': self._get_ir_amount_estimated,
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

    def _get_orders(self, report, only_bo=False):
        orders = []
        for order_id in report.order_ids:
            if self.pool.get('sale.order.line').search(self.cr, self.uid, [('order_id', '=', order_id)]):
                orders.append(order_id)

        self._nb_orders = len(orders)

        for order in orders:
            if only_bo:
                for line in self._get_lines(order, only_bo=only_bo):
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

    def in_line_data(self, po_id, prod_id, pol_id):
        res = []

        # Get data for cancel IN line
        self.cr.execute('''select
                                move.product_uom,
                                move.product_qty
                            from stock_move move, stock_picking pick
                            where
                                pick.purchase_id = %s and
                                product_id = %s and
                                pick.id = move.picking_id and
                                pick.state = 'cancel'
                        ''', (po_id, prod_id)
                        )
        res.append(self.cr.fetchall())

        # Get expected dates from the IN moves' linked to the PO
        self.cr.execute('''
            SELECT DISTINCT(m.date_expected) FROM stock_move m, stock_picking p
            WHERE m.picking_id = p.id AND m.purchase_line_id = %s AND p.type = 'in' AND m.state != 'cancel'
            ORDER BY m.date_expected
        ''', (pol_id, ))
        res.append([data[0] for data in self.cr.fetchall()])

        return res

    def _get_lines(self, order_id, only_bo=False):
        '''
        Get all lines for an order
        '''
        sol_obj = self.pool.get('sale.order.line')
        pol_obj = self.pool.get('purchase.order.line')
        uom_obj = self.pool.get('product.uom')

        if not isinstance(order_id, int):
            order_id = order_id.id

        sort_state = {'cancel': 1}
        line_state_display_dict = dict(sol_obj.fields_get(self.cr, self.uid, ['state_to_display'], context=self.localcontext).get('state_to_display', {}).get('selection', []))

        for line in self._get_order_line(order_id):
            keys = []
            lines = []
            first_line = True
            fl_index = 0
            m_index = 0
            bo_qty = line.product_uom_qty
            po_name = '-'

            cdd = False
            if self.datas.get('is_rml') or self.localcontext.get('lang', False) == 'fr_MF':
                date_format = '%d/%m/%Y'
            else:
                date_format = '%d-%b-%Y'

            from_stock = line.type == 'make_to_stock'
            cancel_in_moves = []
            linked_pol = pol_obj.search(self.cr, self.uid, [('linked_sol_id', '=', line.id)])
            if linked_pol:
                linked_pol = pol_obj.browse(self.cr, self.uid, linked_pol)[0]
                po_name = linked_pol.order_id.name
                cdd = linked_pol.confirmed_delivery_date
                if line.product_id:
                    in_data = self.in_line_data(linked_pol.order_id.id, line.product_id.id, linked_pol.id)
                    cancel_in_moves = in_data[0]
                    if len(in_data[1]) > 1:
                        cdd = ', '.join([datetime.strptime(exp_date[:10], '%Y-%m-%d').strftime(date_format) for exp_date in in_data[1]])
                    elif len(in_data[1]) == 1:
                        cdd = in_data[1][0][:10]
            if not cdd and (line.confirmed_delivery_date or line.order_id.delivery_confirmed_date):
                cdd = line.confirmed_delivery_date or line.order_id.delivery_confirmed_date

            # cancel IN at line level: qty on IR line is adjusted
            # cancel all IN: qty on IR is untouched
            for cancel_in in cancel_in_moves:
                bo_qty -= uom_obj._compute_qty(self.cr, self.uid, cancel_in[0], cancel_in[1], line.product_uom.id)

            received_qty = 0.00  # for received non-stockable products
            if len(line.move_ids) > 0:
                for move in sorted(line.move_ids, cmp=lambda x, y: cmp(sort_state.get(x.state, 0), sort_state.get(y.state, 0)) or cmp(x.id, y.id)):
                    data = {
                        'state': line.state,
                        'state_display': line_state_display_dict.get(line.state_to_display),
                    }
                    m_type = move.state in ('cancel', 'cancel_r') or move.product_qty != 0.00 and move.picking_id.type == 'out'
                    ppl = move.picking_id.subtype == 'packing' and move.picking_id.shipment_id and not self._is_returned(move)
                    ppl_not_shipped = move.picking_id.subtype == 'ppl' and move.picking_id.state not in ('cancel', 'done')
                    s_out = move.picking_id.subtype == 'standard' and move.location_dest_id.usage == 'customer'

                    if (m_type and (ppl or ppl_not_shipped or s_out)) or move.type == 'internal':
                        # bo_qty < 0 if we receipt (IN) more quantities then expected (FO):
                        #if move.state == 'done' or move.picking_id.state == 'cancel':
                        if move.state != 'cancel':
                            bo_qty -= self.pool.get('product.uom')._compute_qty(
                                self.cr,
                                self.uid,
                                move.product_uom.id,
                                move.product_qty,
                                line.product_uom.id,
                            )
                        delivery_order = move.picking_id.name
                        if move.picking_id.state not in ('done', 'delivered'):
                            delivery_order = '-'
                        data.update({
                            'po_name': po_name,
                            'cdd': cdd,
                            'line_number': line.line_number,
                            'line_comment': line.comment or '-',
                            'product_name': line.product_id.name or '-',
                            'product_code': line.product_id.code or '-',
                            'is_delivered': False,
                            'delivery_order': delivery_order,
                            'packing': '-',
                            'shipment': '-',
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
                                eta = datetime.strptime(move.picking_id.shipment_id.shipment_actual_date[0:10],'%Y-%m-%d')
                                eta += timedelta(days=line.order_id.partner_id.supplier_lt or 0.00)
                                is_delivered = move.picking_id.shipment_id.state == 'delivered' or False
                                is_shipment_done = move.picking_id.shipment_id.state == 'done' or False
                            else:
                                packing = move.picking_id.name or '-'
                                shipment = '-'
                            key = (packing, shipment, move.product_uom.name, line.line_number)
                            data.update({
                                'packing': packing,
                                'shipment': shipment,
                                'is_delivered': is_delivered,
                                'delivered_qty': (is_shipment_done or is_delivered) and move.product_qty or 0.00,
                                'delivered_uom': (is_shipment_done or is_delivered) and move.product_uom.name or '-',
                                'backordered_qty': not is_shipment_done and not is_delivered and line.order_id.state != 'cancel' and move.product_qty or 0.00,
                                'rts': move.picking_id.shipment_id and move.picking_id.shipment_id.shipment_expected_date[0:10],
                                'eta': eta and eta.strftime('%Y-%m-%d'),
                                'transport': move.picking_id.shipment_id and move.picking_id.shipment_id.transport_type or '-',
                            })
                        elif (not ppl and not ppl_not_shipped and s_out) or from_stock:
                            state = move.state == 'cancel'
                            if move.picking_id.type == 'out' and move.picking_id.subtype == 'packing':
                                packing = move.picking_id.previous_step_id.name
                                shipment = move.picking_id.shipment_id.name or '-'
                                is_shipment_done = move.picking_id.shipment_id.state == 'done'
                            elif from_stock:
                                packing = move.picking_id.name or '-'
                                shipment = '-'
                                is_shipment_done = move.picking_id.state in ('done', 'delivered') and move.state != 'cancel'
                                state = move.picking_id.state
                            else:
                                shipment = move.picking_id.name or '-'
                                is_shipment_done = move.picking_id.state in ('done', 'delivered')
                                packing = '-'
                            key = (packing, shipment, move.product_uom.name, line.line_number, state)
                            data.update({
                                'packing': packing,
                                'shipment': shipment,
                                'delivered_qty': is_shipment_done and move.product_qty or 0.00,
                                'delivered_uom': move.product_uom.name or '-',
                                'is_delivered': is_shipment_done,
                                'backordered_qty': not is_shipment_done and line.order_id.state != 'cancel' and move.state != 'cancel' and move.product_qty or 0.00,
                                'rts': line.order_id.ready_to_ship_date,
                            })
                        else:
                            if move.picking_id.type == 'out' and move.picking_id.subtype == 'packing':
                                packing = move.picking_id.previous_step_id.name
                                shipment = move.picking_id.shipment_id.name or '-'
                                is_shipment_done = move.picking_id.shipment_id.state == 'done'
                            else:
                                shipment = move.picking_id.name or '-'
                                is_shipment_done = move.picking_id.state in ('done', 'delivered')
                                packing = '-'
                            key = (packing, False, move.product_uom.name, line.line_number)
                            data.update({
                                'packing': packing,
                                'delivered_qty': is_shipment_done and move.product_qty or 0.00,
                                'delivered_uom': is_shipment_done and move.product_uom.name or '-',
                                'rts': line.order_id.ready_to_ship_date,
                                'shipment': shipment,
                            })

                        if key in keys:
                            for rline in lines:
                                if rline['packing'] == key[0] and rline['shipment'] == key[1] and \
                                        rline['delivered_uom'] == key[2] and line.line_number == key[3]:
                                    if rline['is_delivered']:
                                        rline.update({
                                            'delivered_qty': rline['delivered_qty'] + data['delivered_qty'],
                                        })
                                    rline.update({
                                        'backordered_qty': rline['backordered_qty'] + data['backordered_qty'],
                                    })
                        else:
                            keys.append(key)
                            lines.append(data)
                            if data.get('first_line'):
                                fl_index = m_index
                            m_index += 1
            else:  # No move found
                # Look for received qty in the IN(s)
                self.cr.execute("""
                    SELECT m.product_qty FROM stock_move m 
                    LEFT JOIN purchase_order_line pl ON m.purchase_line_id = pl.id
                    LEFT JOIN sale_order_line sl ON pl.linked_sol_id = sl.id
                    WHERE m.state = 'done' AND m.type = 'in' AND sl.id = %s
                """, (line.id,))
                for move in self.cr.fetchall():
                    received_qty += move[0]

                if first_line:
                    data = {
                        'state': line.state,
                        'state_display': line_state_display_dict.get(line.state_to_display),
                        'line_number': line.line_number,
                        'line_comment': line.comment or '-',
                        'po_name': po_name,
                        'product_code': line.product_id.default_code or '-',
                        'product_name': line.product_id.name or '-',
                        'uom_id': line.product_uom.name,
                        'ordered_qty': line.product_uom_qty,
                        'rts': line.order_id.state not in ('draft', 'validated', 'cancel') and line.order_id.ready_to_ship_date,
                        'delivered_qty': received_qty,
                        'delivered_uom': received_qty and line.product_uom.name or '-',
                        'delivery_order': '-',
                        'backordered_qty': line.order_id.state != 'cancel' and line.product_uom_qty - received_qty or 0.00,
                        'cdd': cdd,
                    }
                    lines.append(data)

            # Put the backorderd qty on the first line
            if not lines:
                continue
            if bo_qty and bo_qty > 0 and not first_line and line.state not in ('cancel', 'cancel_r', 'done'):
                lines.append({
                    'po_name': po_name,
                    'cdd': cdd,
                    'line_number': line.line_number,
                    'line_comment': line.comment or '-',
                    'product_name': line.product_id.name or '-',
                    'product_code': line.product_id.code or '-',
                    'is_delivered': False,
                    'backordered_qty': bo_qty if line.order_id.state != 'cancel' else 0.00,
                })
            elif bo_qty < 0:
                lines[fl_index]['extra_qty'] = abs(bo_qty) if line.order_id.state != 'cancel' else 0.00

            for ln in lines:
                if only_bo and (ln.get('backordered_qty', 0.00) <= 0.00 or line.state in ('cancel', 'cancel_r')):
                    continue
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
