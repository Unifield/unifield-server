# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport


class segment_parser(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(segment_parser, self).__init__(cr, uid, name, context=context)

SpreadsheetReport('report.report_replenishment_segment_xls', 'replenishment.segment', 'addons/procurement_cycle/report/replenishment_segment.mako', parser=segment_parser)
