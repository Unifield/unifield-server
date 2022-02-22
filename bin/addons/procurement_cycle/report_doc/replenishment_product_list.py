# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(parser, self).__init__(cr, uid, name, context=context)

        self.localcontext.update({
            'get_list': self.get_list,
            'get_prod': self.get_prod,
        })

    def get_list(self):
        self.list_id = self.localcontext.get('data').get('list_id')
        return self.pool.get('product.list').browse(self.cr,self.uid, self.list_id, context={'lang': self.localcontext.get('lang')})

    def get_prod(self, list_id):
        prod_list_obj = self.pool.get('replenishment.product.list')
        prod_ids = prod_list_obj.search(self.cr, self.uid, [('list_ids', '=', list_id)])
        return prod_list_obj.browse(self.cr, self.uid, prod_ids, context={'lang': self.localcontext.get('lang')})

SpreadsheetReport('report.report_replenishment_product_list', 'replenishment.product.list', 'addons/procurement_cycle/report_doc/replenishment_product_list.mako', parser=parser)

