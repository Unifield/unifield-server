# -*- coding: utf-8 -*-
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.safe_eval import safe_eval

class ErrorLine(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(ErrorLine, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_row': self.get_row,
            'with_error': lambda *a: True,
        })

    def get_row(self, obj_id):
        rej_obj = self.pool.get('esc.line.import.rejected')

        limit = 500
        offset = 0
        while True:
            ids = rej_obj.search(self.cr, self.uid, [('wiz_id', '=', obj_id)], offset=offset, limit=limit)
            offset += limit
            if not ids:
                return

            for x in rej_obj.browse(self.cr, self.uid, ids):
                rows = safe_eval(x.xls_row)
                yield rows, x.error

            if len(ids) < limit:
                return

SpreadsheetReport('report.esc_line_import_rejected', 'esc.line.import', 'account_hq_entries/report/esc_line_import_template.mako', parser=ErrorLine)


class Template(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Template, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_row': lambda *a, **b: [],
            'with_error': lambda *a: False,
        })

SpreadsheetReport('report.esc_line_import_template', 'esc.line.import', 'account_hq_entries/report/esc_line_import_template.mako', parser=Template)

