# -*- coding: utf-8 -*-

from lxml import etree
from mx import DateTime
from tools.translate import _
from tools.misc import file_open
from osv import osv
from report_webkit.webkit_report import WebKitParser
from report import report_sxw

class SpreadsheetReport(WebKitParser):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        if not rml:
            rml = 'addons/spreadsheet_xml/report/spreadsheet_xls.mako'
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        if self.tmpl:
            f = file_open(self.tmpl)
            report_xml.report_webkit_data = f.read()
            report_xml.report_file = None
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(SpreadsheetReport, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create(self, cr, uid, ids, data, context=None):
        a = super(SpreadsheetReport, self).create(cr, uid, ids, data, context)
        return (a[0], 'xls')
