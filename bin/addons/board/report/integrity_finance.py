# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from board import queries_finance
from tools.translate import _


class integrity_finance(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(integrity_finance, self).__init__(cr, uid, name, context=context)
        self.sql_additional = ""  # to add the criteria from the wizard filters
        self.sql_params = []
        self.localcontext.update({
            'get_title': self.get_title,
            'list_checks': self.list_checks,
            'get_results': self.get_results,
            '_t': self._t,
        })

    def set_context(self, objects, data, ids, report_type=None):
        """
        Fills in:
        - self.sql_additional with the part of SQL request corresponding to the criteria selected in the wizard (string)
        - self.sql_params with the related parameters (list)
        """
        if data.get('form', False):
            instance_ids = data['form'].get('instance_ids', False)
            if instance_ids:
                self.sql_additional += " AND l.instance_id IN %s "
                self.sql_params.append(tuple(instance_ids,))
            fiscalyear_id = data['form'].get('fiscalyear_id', False)
            if fiscalyear_id:
                self.sql_additional += " AND l.period_id IN (SELECT id FROM account_period WHERE fiscalyear_id = %s) "
                self.sql_params.append(fiscalyear_id)
        return super(integrity_finance, self).set_context(objects, data, ids, report_type=report_type)

    def get_title(self):
        return _('Entries Data Integrity')

    def list_checks(self):
        return queries_finance.queries

    def get_results(self, sql):
        if not sql:
            return []
        sql = sql % self.sql_additional
        if self.sql_params:
            self.cr.execute(sql, tuple(self.sql_params))
        else:
            self.cr.execute(sql)
        return self.cr.fetchall()

    def _t(self, source):
        return _(source)

SpreadsheetReport('report.integrity.finance', 'board.board', 'board/report/integrity.mako', parser=integrity_finance)
