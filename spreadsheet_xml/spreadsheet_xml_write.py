# -*- coding: utf-8 -*-

from lxml import etree
from mx import DateTime
from tools.translate import _
from tools.misc import file_open
from osv import osv
from report_webkit.webkit_report import WebKitParser
from report import report_sxw

from mako.template import Template
from mako import exceptions
from tools.misc import file_open
import pooler

class SpreadsheetReport(WebKitParser):
    _fields_process = {
        'date': report_sxw._date_format,
        'datetime': report_sxw._dttime_format
    }


    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        if not rml:
            rml = 'addons/spreadsheet_xml/report/spreadsheet_xls.mako'
        WebKitParser.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
        self.sheet_name_used = []
        self.total_sheet_number = 1

    def sheet_name(self, default_name=False, context=None):
        sheet_max_size = 31
        if not default_name:
            default_name = 'Sheet %s' % (self.total_sheet_number, )

        default_name = default_name[0:sheet_max_size]

        if default_name in self.sheet_name_used:
            default_name = '%s %s'% (default_name[0:sheet_max_size - len('%s' % self.total_sheet_number) - 1], self.total_sheet_number)

        self.sheet_name_used.append(default_name)
        self.total_sheet_number += 1
        return default_name

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        if self.tmpl:
            f = file_open(self.tmpl)
            report_xml.report_webkit_data = f.read()
            report_xml.report_file = None
        report_xml.webkit_debug = 1
        report_xml.header= " "
        report_xml.webkit_header.html = "${_debug or ''|n}"
        return super(SpreadsheetReport, self).create_single_pdf(cr, uid, ids, data, report_xml, context)

    def getObjects(self, cr, uid, ids, context):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        self.sheet_name_used = []
        self.total_sheet_number = 1
        self.parser_instance.localcontext['sheet_name'] = self.sheet_name
        return table_obj.browse(cr, uid, ids, list_class=report_sxw.browse_record_list, context=context, fields_process=self._fields_process)

    def create(self, cr, uid, ids, data, context=None):
        a = super(SpreadsheetReport, self).create(cr, uid, ids, data, context)
        # This permit to test XLS report generation with tools.tests_reports without given some warning
        # Cf. tools/tests_reports.py:89
        if context and context.get('from_yml', False) and context.get('from_yml') is True:
            return (a[0], 'foobar')
        return (a[0], 'xls')

class SpreadsheetCreator(object):
    def __init__(self, title, headers, datas):
        self.headers = headers
        self.datas = datas
        self.title = title

    def get_xml(self, default_filters=[]):
        f, filename = file_open('addons/spreadsheet_xml/report/spreadsheet_writer_xls.mako', pathinfo=True)
        f[0].close()
        tmpl = Template(filename=filename, input_encoding='utf-8', output_encoding='utf-8', default_filters=default_filters)
        return tmpl.render(objects=self.datas, headers=self.headers, title= self.title)
