# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class stock_reception_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(stock_reception_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
            'getMoves': self.get_moves,
        })

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def get_moves(self, moves_ids):
        move_obj = self.pool.get('stock.move')
        curr_obj = self.pool.get('res.currency')
        model_obj = self.pool.get('ir.model.data')
        res = []

        ave_price_list = {}
        self.cr.execute("""
            SELECT distinct on (m.id) m.id, new_standard_price FROM stock_move m
            LEFT JOIN standard_price_track_changes tc on tc.product_id = m.product_id AND tc.change_date >= m.date
            WHERE m.id IN %s
            ORDER BY m.id, change_date ASC;
        """, (tuple(moves_ids),))
        for move_d in self.cr.fetchall():
            ave_price_list[move_d[0]] = move_d[1]

        for move in move_obj.browse(self.cr, self.uid, moves_ids, context=self.localcontext):
            pick = move.picking_id
            pol = move.purchase_line_id or False
            po = pol and pol.order_id or False
            sol = pol and pol.linked_sol_id or False
            int_name = move.move_dest_id and move.move_dest_id.picking_id.type == 'internal' and \
                move.move_dest_id.picking_id.subtype == 'standard' and move.move_dest_id.picking_id.name or ''
            func_price_unit = move.price_unit
            if pol and move.company_id.currency_id.id != po.pricelist_id.currency_id.id:
                self.localcontext['currency_date'] = move.date
                func_price_unit = round(curr_obj.compute(self.cr, self.uid, po.pricelist_id.currency_id.id,
                                                         move.company_id.currency_id.id, move.price_unit,
                                                         round=False, context=self.localcontext), 2)
            func_ave_price = ave_price_list.get(move.id, False) or move.product_id.standard_price
            if move.company_id.currency_id.id != move.product_id.currency_id.id:
                func_ave_price = round(curr_obj.compute(self.cr, self.uid, move.product_id.currency_id.id,
                                                        move.company_id.currency_id.id, func_ave_price,
                                                        round=False, context=self.localcontext), 2)

            # Get the linked INT's move using move.move_dest_id
            cross_docking_id = model_obj.get_object_reference(self.cr, self.uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
            if sol and sol.procurement_request:
                if move.move_dest_id and move.move_dest_id.picking_id.type == 'internal' \
                        and move.move_dest_id.picking_id.subtype == 'standard' and sol.order_id.location_requestor_id.usage == 'internal':
                    final_dest_loc = move.move_dest_id.location_dest_id.name
                elif sol.order_id.location_requestor_id.usage != 'customer' and move.location_dest_id.id == cross_docking_id:
                    # For the UC with IR (Stock location) to IN sent to Cross Docking
                    final_dest_loc = move.location_dest_id.name
                elif sol.order_id.location_requestor_id.usage == 'customer' and move.location_dest_id.id != cross_docking_id:
                    # For the UC with IR (Consumption Unit) to IN not sent to Cross Docking
                    if move.move_dest_id.state == 'done':
                        final_dest_loc = move.move_dest_id.location_dest_id.name
                    else:
                        final_dest_loc = ''
                else:
                    final_dest_loc = sol.order_id.location_requestor_id.name
            elif move.location_dest_id.id == cross_docking_id:
                if sol:
                    final_dest_loc = sol.order_id.partner_id.name
                else:  # In case the IN has no linked FO/IR but sent to Cross Docking
                    final_dest_loc = move.location_dest_id.name
            elif move.move_dest_id and move.move_dest_id.picking_id.type == 'internal' \
                    and move.move_dest_id.picking_id.subtype == 'standard':
                if move.move_dest_id.state == 'done':
                    final_dest_loc = move.move_dest_id.location_dest_id.name
                else:  # Do not show the destination if the linked INT move is not done
                    final_dest_loc = ''
            elif move.location_dest_id:
                final_dest_loc = move.location_dest_id.name
            else:
                final_dest_loc = ''

            res.append({
                'ref': pick.name,
                'reason_type': move.reason_type_id and move.reason_type_id.name or '',
                'purchase_order': pick.purchase_id and pick.purchase_id.name or '',
                'supplier': pick.partner_id and pick.partner_id.name or '',
                'purchase_id': po,  # For category, type and priority
                'dr_date': pol and (pol.date_planned or po.delivery_requested_date) or False,
                'dc_date': pol and (pol.confirmed_delivery_date or po.delivery_confirmed_date) or False,
                'origin': move.origin or '',
                'backorder': pick.backorder_id and pick.backorder_id.name or '',
                'line': move.line_number,
                'product_code': move.product_id and move.product_id.default_code or '',
                'product_desc': move.product_id and move.product_id.name or '',
                'uom': move.product_uom and move.product_uom.name or '',
                'qty_ordered': pol and pol.product_qty or 0.00,
                'qty_received': move.product_qty,
                'unit_price': move.price_unit,
                'currency': move.price_currency_id and move.price_currency_id.name or '',
                'ave_price_func': func_ave_price,
                'total_cost': move.product_qty * move.price_unit,
                'total_cost_func': move.product_qty * func_price_unit,
                'ave_total_cost_func': move.product_qty * func_ave_price,
                'comment': move.comment or '',
                'dest_loc': move.location_dest_id and move.location_dest_id.name or '',
                'final_dest_loc': final_dest_loc,
                'exp_receipt_date': move.date_expected,
                'actual_receipt_date': move.date,
                'phys_recep_date': pick.physical_reception_date,
                'int_name': int_name,
            })

        return res


SpreadsheetReport(
    'report.stock.reception.report_xls',
    'stock.reception.wizard',
    'stock/report/stock_reception_report_xls.mako',
    parser=stock_reception_report
)
