# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
import datetime


class unreserved_stock_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(unreserved_stock_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getInstanceName': self.get_instance_name,
            'getDate': self.get_date,
            'getUnreservedMovesData': self.get_unreserved_moves_data,
        })

    def get_instance_name(self):
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.name

    def get_date(self):
        return datetime.date.today()

    def get_unreserved_moves_data(self):
        cross_docking_id = self.pool.get('ir.model.data').\
            get_object_reference(self.cr, self.uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
        self.cr.execute("""
            SELECT m.product_id, l.name, pp.default_code, pt.name, r.name, pl.name, m.expired_date, SUM(m.product_qty)
            FROM stock_move m, stock_location l, product_product pp, product_template pt, stock_picking p, 
                stock_production_lot pl, res_currency r
            WHERE m.location_id = l.id AND m.product_id = pp.id AND pp.product_tmpl_id = pt.id AND m.picking_id = p.id 
                AND m.prodlot_id = pl.id AND m.product_uom = r.id AND m.state = 'cancel' AND m.location_id = %s
                AND m.product_qty > 0 AND p.type = 'out' AND p.subtype IN ('standard', 'picking')
            GROUP BY m.product_id, pp.default_code, m.prodlot_id, pl.name, m.expired_date, m.product_qty, pt.name, 
                r.name, l.name
            ORDER BY m.product_id, pl.name, m.expired_date
        """, (cross_docking_id,))

        lines = self.cr.fetchall()
        res = []
        prod_ids = []
        line_sum = {}
        sum_qty = 0.00
        index = 0
        for i, line in enumerate(lines):
            res.append({
                'sum_line': False,
                'loc_name': line[1],
                'prod_name': line[2],
                'prod_desc': line[3],
                'prod_uom': line[4],
                'batch': line[5] or '-',
                'exp_date': line[6] or '-',
                'prod_qty': line[7],
                'sum_qty': 0.00,
            })
            if line[0] in prod_ids:
                sum_qty += line[7]
                line_sum.update({'sum_qty': sum_qty})
                if i == len(lines) - 1:
                    res.insert(index, line_sum)
            else:
                if line_sum:
                    res.insert(index, line_sum)
                sum_qty = line[7]
                line_sum = {
                    'sum_line': True,
                    'loc_name': line[1],
                    'prod_name': line[2],
                    'prod_desc': line[3],
                    'prod_uom': line[4],
                    'batch': '',
                    'exp_date': '',
                    'prod_qty': 0.00,
                    'sum_qty': line[7],
                }
                prod_ids.append(line[0])
                index = len(res) - 1

        return res


SpreadsheetReport('report.unreserved.stock.report', 'stock.move', 'stock/report/unreserved_stock_report_xls.mako', parser=unreserved_stock_report)
