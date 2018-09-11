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
            SELECT l.name, pp.default_code, pt.name, m.product_uom, pl.name, m.expired_date, m.product_qty
            FROM stock_move m, stock_location l, product_product pp, product_template pt, stock_picking p, 
                stock_production_lot pl
            WHERE m.location_id = l.id AND m.product_id = pp.id AND pp.product_tmpl_id = pt.id AND m.picking_id = p.id 
                AND m.prodlot_id = pl.id AND m.state != 'cancel' AND m.location_id = %s
            GROUP BY m.product_id, pl.name, m.expired_date
        """, (cross_docking_id,))

        res = self.cr.fetchall()

        return res


SpreadsheetReport('report.unreserved.stock', 'stock.move', 'stock/report/unreserved_stock_report_xls.mako', parser=unreserved_stock_report)
