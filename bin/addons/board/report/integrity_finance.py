# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from board import queries_finance
from tools.translate import _


class integrity_finance(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(integrity_finance, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'get_title': self.get_title,
            'list_checks': self.list_checks,
            'get_results': self.get_results,
            '_t': self._t,
        })

    def get_title(self):
        return _('Entries Data Integrity')

    def list_checks(self):
        return queries_finance.queries

    def get_results(self, sql):
        if not sql:
            return []
        self.cr.execute(sql)
        return self.cr.fetchall()

    def _t(self, source):
        return _(source)

SpreadsheetReport('report.integrity.finance', 'board.board', 'stock/report/integrity.mako', parser=integrity_finance)
