# -*- coding: utf-8 -*-

from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from board import queries_finance
from osv import osv
from tools.translate import _


class integrity_finance(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(integrity_finance, self).__init__(cr, uid, name, context=context)
        self.sql_additional = ""  # to add the criteria from the wizard filters
        self.sql_params = []
        self.sql_rec_additional = ""  # specific to queries related to reconciliations
        self.sql_rec_params = []
        self.localcontext.update({
            'get_title': self.get_title,
            'list_checks': self.list_checks,
            'get_results': self.get_results,
            '_t': self._t,
        })

    def set_context(self, objects, data, ids, report_type=None):
        """
        Fills in:
        - self.sql_additional and self.sql_rec_additional with the part of SQL request corresponding to the criteria selected (string)
        - self.sql_params and self.sql_rec_params with the related parameters (list)

        For reconciliation queries the reconciliation dates must be within the FY/periods/dates selected.
        For other queries the JI dates is used.
        """
        period_obj = self.pool.get('account.period')
        fy_obj = self.pool.get('account.fiscalyear')
        if data.get('form', False):
            # instances
            instance_ids = data['form'].get('instance_ids', False)
            if instance_ids:
                self.sql_additional += " AND l.instance_id IN %s "
                self.sql_params.append(tuple(instance_ids,))
                self.sql_rec_additional += " AND l.instance_id IN %s "
                self.sql_rec_params.append(tuple(instance_ids,))
            # FY
            fiscalyear_id = data['form'].get('fiscalyear_id', False)
            if fiscalyear_id:
                self.sql_additional += " AND l.period_id IN (SELECT id FROM account_period WHERE fiscalyear_id = %s) "
                self.sql_params.append(fiscalyear_id)
                fiscalyear = fy_obj.browse(self.cr, self.uid, fiscalyear_id, fields_to_fetch=['date_start', 'date_stop'], context=data.get('context', {}))
                self.sql_rec_additional += " AND l.reconcile_date >= %s AND l.reconcile_date <= %s "
                self.sql_rec_params.append(fiscalyear.date_start)
                self.sql_rec_params.append(fiscalyear.date_stop)
            wiz_filter = data['form'].get('filter', '')
            # periods
            if wiz_filter == 'filter_period':
                period_from = data['form'].get('period_from', False)
                period_to = data['form'].get('period_to', False)
                if not period_from or not period_to:
                    raise osv.except_osv(_('Error'), _('Either the Start period or the End period is missing.'))
                else:
                    period_ids = period_obj.get_period_range(self.cr, self.uid, period_from, period_to, context=data.get('context', {}))
                    if period_ids:
                        self.sql_additional += " AND l.period_id IN %s "
                        self.sql_params.append(tuple(period_ids,))
                    per_from = period_obj.browse(self.cr, self.uid, period_from, fields_to_fetch=['date_start'], context=data.get('context', {}))
                    per_to = period_obj.browse(self.cr, self.uid, period_to, fields_to_fetch=['date_stop'], context=data.get('context', {}))
                    self.sql_rec_additional += " AND l.reconcile_date >= %s AND l.reconcile_date <= %s "
                    self.sql_rec_params.append(per_from.date_start)
                    self.sql_rec_params.append(per_to.date_stop)
            # dates
            if wiz_filter in ('filter_date_doc', 'filter_date'):
                date_from = data['form'].get('date_from', False)
                date_to = data['form'].get('date_to', False)
                if not date_from or not date_to:
                    raise osv.except_osv(_('Error'), _('Either the Start date or the End date is missing.'))
                else:
                    if wiz_filter == 'filter_date_doc':
                        # JI doc dates
                        self.sql_additional += " AND l.document_date >= %s AND l.document_date <= %s "
                    else:
                        # JI posting dates
                        self.sql_additional += " AND l.date >= %s AND l.date <= %s "
                    self.sql_params.append(date_from)
                    self.sql_params.append(date_to)
                    # reconciliation dates
                    self.sql_rec_additional += " AND l.reconcile_date >= %s AND l.reconcile_date <= %s "
                    self.sql_rec_params.append(date_from)
                    self.sql_rec_params.append(date_to)
        return super(integrity_finance, self).set_context(objects, data, ids, report_type=report_type)

    def get_title(self):
        return _('Entries Data Integrity')

    def list_checks(self):
        return queries_finance.queries

    def get_results(self, sql, query_ref):
        if not sql:
            return []
        # reconciliation queries
        if query_ref in ('unbalanced_rec_fctal', 'unbalanced_rec_booking'):
            sql = sql % self.sql_rec_additional
            if self.sql_rec_params:
                self.cr.execute(sql, tuple(self.sql_rec_params))
            else:
                self.cr.execute(sql)
        # other queries
        else:
            sql = sql % self.sql_additional
            if self.sql_params:
                self.cr.execute(sql, tuple(self.sql_params))
            else:
                self.cr.execute(sql)
        return self.cr.fetchall()

    def _t(self, source):
        return _(source)

SpreadsheetReport('report.integrity.finance', 'board.board', 'board/report/integrity.mako', parser=integrity_finance)
