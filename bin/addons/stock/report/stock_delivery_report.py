# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class stock_delivery_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(stock_delivery_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
            'getMoves': self.get_moves,
        })

        self._order_iterator = 0
        self._nb_orders = 0
        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

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

        self._nb_orders = len(moves_ids)

        for move in move_obj.browse(self.cr, self.uid, moves_ids, context=self.localcontext):
            pick = move.picking_id
            ppl = pick.subtype == 'packing' and pick.previous_step_id or False
            ship = pick.shipment_id
            fo = pick.sale_id or False
            prod = move.product_id
            price = prod and prod.standard_price
            currency = prod and prod.currency_id or False
            curr_price = self.pool.get('res.currency').compute(self.cr, self.uid, move.price_currency_id.id, currency
                                                               and currency.id or False, price, context=self.localcontext)
            res.append({
                'ref': ppl and ppl.name or pick.name,
                'reason_type': ppl and ppl.reason_type_id.complete_name or pick.reason_type_id
                and pick.reason_type_id.complete_name or '',
                'ship': ship and ship.name or '',
                'origin': pick.origin or '',
                'partner': pick.partner_id and pick.partner_id.name or '',
                'details': ppl and ppl.details or pick.details or '',
                'fo': fo,
                'header': ppl or pick,
                'line_num': move.line_number,
                'prod_code': prod and prod.default_code or '',
                'prod_desc': prod and prod.name or '',
                'prod_uom': move.product_uom and move.product_uom.name or '',
                'qty': move.product_qty,
                'prodlot': move.prodlot_id and move.prodlot_id.name or '',
                'expiry_date': move.prodlot_id and move.prodlot_id.life_date or False,
                'price': price,
                'currency': currency and currency.name or '',
                'total_currency': price and curr_price * move.product_qty,
                'location': ppl and move.backmove_id and move.backmove_id.location_id
                and move.backmove_id.location_id.name or move.location_id.name or '',
                'destination': ppl and pick.partner_id.name or fo and not fo.procurement_request and fo.partner_id.name
                or move.location_dest_id.name or '',
                'create_date': pick.date,
                'shipped_date': ppl and ship and ship.shipment_actual_date or pick.date_done,
            })

            self._order_iterator += 1
            if self.back_browse:
                percent = float(self._order_iterator) / float(self._nb_orders)
                self.pool.get('memory.background.report').update_percent(self.cr, self.uid, [self.back_browse.id], percent)

        return res


SpreadsheetReport(
    'report.stock.delivery.report_xls',
    'stock.delivery.wizard',
    'stock/report/stock_delivery_report_xls.mako',
    parser=stock_delivery_report
)
