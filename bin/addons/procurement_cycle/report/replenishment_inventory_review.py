# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tools import misc
from tools.translate import _


class inventory_parser(report_sxw.rml_parse):

    _
    def __init__(self, cr, uid, name, context):
        super(inventory_parser, self).__init__(cr, uid, name, context=context)

        self.localcontext.update({
            'get_month': self.get_month,
        })

    def get_month(self, start, nb_month):
        return _(misc.month_abbr[(datetime.strptime(start, '%Y-%m-%d') + relativedelta(hour=0, minute=0, second=0, months=nb_month)).month])

SpreadsheetReport('report.report_replenishment_inventory_review_xls', 'replenishment.inventory.review', 'addons/procurement_cycle/report/replenishment_inventory_review.mako', parser=inventory_parser)

