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
from openpyxl.utils.cell import get_column_letter


class XlsxReport(report_int):

    def __init__(self, name, parser, write_only=False, template=False):
        super(XlsxReport, self).__init__(name)
        self.parser = parser
        self.write_only = write_only
        self.template = template
        if not netsvc.Service._services.get(self.name2):
            netsvc.Service._services[self.name2] = parser

    def create(self, cr, uid, ids, datas, context):
        wb_t = False
        if self.template:
            if self.write_only:
                wb_t = openpyxl.load_workbook(file_open(self.template))
            else:
                wb = openpyxl.load_workbook(file_open(self.template))

        if self.write_only:
            wb = openpyxl.Workbook(write_only=True)
            wb.create_sheet()
        else:
            wb = openpyxl.Workbook()
        wb.iso_dates = True
        self.parser(cr, uid, ids, wb, wb_t, context).generate(context=context)
        tmp = NamedTemporaryFile(delete=False)
        wb.save(tmp.name)
        wb.close()
        if wb_t:
            wb_t.close()
        tmp.seek(0)
        return (Path(tmp.name, delete=True), 'xlsx')

class XlsxReportParser():
    def __init__(self, cr, uid, ids, workbook, workbook_template, context):
        self.cr = cr
        self.uid = uid
        self.ids = ids
        self.context = context
        self.workbook = workbook
        self.workbook_template = workbook_template
        self.pool = pooler.get_pool(cr.dbname)

    def duplicate_column_dimensions(self, default_width=None):
        for x in range(1, self.workbook_template.active.max_column+1):
            letter = get_column_letter(x)
            tmp_column = self.workbook_template.active.column_dimensions[letter]
            width = False
            if not tmp_column.customWidth and default_width:
                width = default_width
            elif tmp_column.customWidth:
                width = tmp_column.width

            if width:
                self.workbook.active.column_dimensions[letter].width = width

    def duplicate_row_dimensions(self, row_range):
        for x in row_range:
            self.workbook.active.row_dimensions[x].height = self.workbook_template.active.row_dimensions[x].height

    def apply_template_style(self, cell_index, target):
        self.duplicate_cell_style(self.workbook_template.active[cell_index], target)

    def duplicate_cell_style(self, src, target):
        target.style = copy(src.style)
        target.font = copy(src.font)
        target.fill = copy(src.fill)
        target.border = copy(src.border)
        target.alignment = copy(src.alignment)
        target.number_format = copy(src.number_format)

    def create_style_from_cell(self, name, src):
        new_style = NamedStyle(name=name)
        self.duplicate_cell_style(src, new_style)
        return new_style

    def create_style_from_template(self, name, cell_index):
        new_style = self.create_style_from_cell(name, self.workbook_template.active[cell_index])
        self.workbook.add_named_style(new_style)
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

