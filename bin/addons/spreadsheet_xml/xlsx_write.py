# -*- coding: utf-8 -*-

from tools.misc import Path, file_open
from report.interface import report_int
import netsvc
import openpyxl
from tempfile import NamedTemporaryFile
from copy import copy
import pooler
import datetime
from openpyxl.styles import NamedStyle

class XlsxReport(report_int):

    def __init__(self, name, parser, template=False):
        super(XlsxReport, self).__init__(name)
        self.parser = parser
        self.template = template
        if not netsvc.Service._services.get(self.name2):
            netsvc.Service._services[self.name2] = parser

    def create(self, cr, uid, ids, datas, context):
        if self.template:
            wb = openpyxl.load_workbook(file_open(self.template))
        else:
            wb = openpyxl.Workbook()
        wb.iso_dates = True
        self.parser(cr, uid, ids, wb, context).generate(context=context)
        tmp = NamedTemporaryFile(delete=False)
        wb.save(tmp.name)
        tmp.seek(0)
        return (Path(tmp.name, delete=True), 'xlsx')

class XlsxReportParser():
    def __init__(self, cr, uid, ids, workbook, context):
        self.cr = cr
        self.uid = uid
        self.ids = ids
        self.context = context
        self.workbook = workbook
        self.pool = pooler.get_pool(cr.dbname)

    def duplicate_cell_style(self, src, target):
        target.style = copy(src.style)
        target.font = copy(src.font)
        target.fill = copy(src.fill)
        target.border = copy(src.border)
        target.alignment = copy(src.alignment)

    def create_style_from_cell(self, src, name):
        new_style = NamedStyle(name=name)
        self.duplicate_cell_style(src, new_style)
        return new_style

    def getSel(self, o, field):
        return self.pool.get('ir.model.fields').get_browse_selection(self.cr, self.uid, o, field, self.context)


    def to_datetime(self, value):
        if not value:
            return ''
        if len(value) == 10:
            str_date = value + ' 00:00:00'
        else:
            str_date = value
        return datetime.datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S")

