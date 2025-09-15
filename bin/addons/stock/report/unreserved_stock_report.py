# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
import datetime


class unreserved_stock_report(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(unreserved_stock_report, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'getInstance': self.get_instance,
            'getDate': self.get_date,
            'getUnreservedMovesData': self.get_unreserved_moves_data,
        })

    def get_instance(self):
        return self.pool.get('res.users').browse(self.cr, self.uid, self.uid).company_id.instance_id.instance

    def get_date(self):
        return datetime.date.today()

    def get_unreserved_moves_data(self):
        prod_obj = self.pool.get('product.product')
        lot_obj = self.pool.get('stock.production.lot')
        loc_obj = self.pool.get('stock.location')

        cross_docking_id = self.pool.get('ir.model.data').\
            get_object_reference(self.cr, self.uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]

        self.cr.execute("""
            SELECT product_id, prodlot_id, SUM(qty) 
            FROM (
                SELECT product_id, prodlot_id, SUM(-m1.product_qty*uom.factor) AS qty 
                FROM stock_move m1, product_uom uom 
                WHERE uom.id = m1.product_uom AND m1.location_id = %s AND m1.location_dest_id != %s 
                    AND m1.state IN ('done','assigned') 
                GROUP BY product_id, prodlot_id
                    UNION
                SELECT product_id, prodlot_id, sum(m2.product_qty*uom.factor) AS qty 
                FROM stock_move m2, product_uom uom 
                WHERE uom.id = m2.product_uom AND m2.location_id != %s AND m2.location_dest_id = %s 
                    AND m2.state IN ('done') 
                GROUP BY product_id, prodlot_id
            )
            x GROUP BY product_id, prodlot_id HAVING SUM(qty) > 0
            ORDER BY product_id, prodlot_id
        """, (cross_docking_id, cross_docking_id, cross_docking_id, cross_docking_id,))

        lines = self.cr.fetchall()
        res = []
        prod_ids = []
        line_sum = {}
        sum_qty = 0.00
        index = 0
        loc_name = loc_obj.browse(self.cr, self.uid, cross_docking_id, fields_to_fetch=['name'],
                                  context=self.localcontext).name
        for i, line in enumerate(lines):
            product = False
            prodlot = False
            if line[0]:
                product = prod_obj.browse(self.cr, self.uid, line[0], fields_to_fetch=['default_code', 'name', 'uom_id'],
                                          context=self.localcontext)
            if line[1]:
                prodlot = lot_obj.browse(self.cr, self.uid, line[1], fields_to_fetch=['name', 'life_date'],
                                         context=self.localcontext)
            res.append({
                'sum_line': False,
                'loc_name': loc_name,
                'prod_name': product and product.default_code or False,
                'prod_desc': product and product.name or False,
                'prod_uom': product and product.uom_id.name or False,
                'batch': prodlot and prodlot.name or '-',
                'exp_date': prodlot and prodlot.life_date or '-',
                'prod_qty': line[2],
                'sum_qty': 0.00,
            })
            if line[0] in prod_ids:
                sum_qty += line[2]
                line_sum.update({'sum_qty': sum_qty})
            else:
                if line_sum:
                    res.insert(index, line_sum)
                sum_qty = line[2]
                line_sum = {
                    'sum_line': True,
                    'loc_name': loc_name,
                    'prod_name': product and product.default_code or False,
                    'prod_desc': product and product.name or False,
                    'prod_uom': product and product.uom_id.name or False,
                    'batch': '',
                    'exp_date': '',
                    'prod_qty': 0.00,
                    'sum_qty': line[2],
                }
                prod_ids.append(line[0])
                index = len(res) - 1
            if i == len(lines) - 1:
                res.insert(index, line_sum)

        return res


SpreadsheetReport('report.unreserved.stock.report', 'stock.move', 'stock/report/unreserved_stock_report_xls.mako', parser=unreserved_stock_report)
