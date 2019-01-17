# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import datetime


class stock_expired_damaged_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(stock_expired_damaged_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
            'getReasonTypesText': self.reason_types_text,
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

    def reason_types_text(self, rt_ids):
        rt_obj = self.pool.get('stock.reason.type')

        rts_text = []
        for rt in rt_obj.browse(self.cr, self.uid, rt_ids, context=self.localcontext):
            if rt.parent_id:
                rts_text.append(str(rt.parent_id.id) + '.' + str(rt.code))
            else:
                rts_text.append(str(rt.code))

        return rts_text and ', '.join(rts_text) or ''

    def get_moves(self, moves_ids):
        move_obj = self.pool.get('stock.move')
        res = []

        for move in move_obj.browse(self.cr, self.uid, moves_ids, context=self.localcontext):
            price_at_date = False
            self.cr.execute("""SELECT distinct on (product_id) product_id, new_standard_price
            FROM standard_price_track_changes
            WHERE product_id = %s AND change_date <= %s
            ORDER BY product_id, change_date desc
            """, (move.product_id.id, move.date))
            for x in self.cr.fetchall():
                price_at_date = x[1]
            res.append({
                'ref': move.picking_id.name,
                'reason_type': move.reason_type_id and move.reason_type_id.name or '',
                'main_type': move.product_id and move.product_id.nomen_manda_0 and move.product_id.nomen_manda_0.name or '',
                'product_code': move.product_id and move.product_id.default_code or '',
                'product_desc': move.product_id and move.product_id.name or '',
                'uom': move.product_uom and move.product_uom.name or '',
                'qty': move.product_qty,
                'batch': move.prodlot_id and move.prodlot_id.name or '',
                'exp_date': move.expired_date,
                'unit_price': price_at_date or move.price_unit,
                'currency': move.price_currency_id and move.price_currency_id.name or
                            move.product_id.currency_id and move.product_id.currency_id.name or '',
                'total_price': price_at_date and move.product_qty * price_at_date or
                               move.product_qty * move.price_unit,
                'src_loc': move.location_id and move.location_id.name or '',
                'dest_loc': move.location_dest_id and move.location_dest_id.name or '',
                'crea_date': move.picking_id.date,
                'move_date': move.date,
            })

        return res


SpreadsheetReport(
    'report.stock.expired.damaged.report_xls',
    'stock.expired.damaged.wizard',
    'stock/report/stock_expired_damaged_report_xls.mako',
    parser=stock_expired_damaged_report
)
