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
        res = []

        for move in move_obj.browse(self.cr, self.uid, moves_ids, context=self.localcontext):
            pick = move.picking_id
            pol = move.purchase_line_id
            po = pol.order_id
            sol = move.purchase_line_id.sale_order_line_id
            res.append({
                'ref': pick.name,
                'reason_type': move.reason_type_id and move.reason_type_id.name or '',
                'purchase_order': pick.purchase_id and pick.purchase_id.name or '',
                'supplier': pick.partner_id and pick.partner_id.name or '',
                'purchase_id': po,  # For category, type and priority
                'dr_date': pol.date_planned or po.delivery_requested_date,
                'dc_date': pol.confirmed_delivery_date or po.confirmed_delivery_date,
                'origin': move.origin,
                'backorder': pick.backorder_id and pick.backorder_id.name or '',
                'line': move.line_number,
                'product_code': move.product_id and move.product_id.default_code or '',
                'product_desc': move.product_id and move.product_id.name or '',
                'uom': move.product_uom and move.product_uom.name or '',
                'qty_ordered': pol.product_qty,
                'qty_received': move.product_qty,
                'unit_price': move.price_unit,
                'currency': move.price_currency_id and move.price_currency_id.name or '',
                'total_cost': move.product_qty * move.price_unit,
                'dest_loc': move.location_dest_id and move.location_dest_id.name or '',
                'final_dest_loc': sol and (sol.procurement_request and sol.order_id.location_requestor_id.name or sol.order_id.partner_id.name)
                or move.location_dest_id and move.location_dest_id.name or '',
                'exp_receipt_date': move.date_expected,
                'actual_receipt_date': move.date,
                'phys_recep_date': pick.physical_reception_date,
            })

        return res


SpreadsheetReport(
    'report.stock.reception.report_xls',
    'stock.reception.wizard',
    'stock/report/stock_reception_report_xls.mako',
    parser=stock_reception_report
)
