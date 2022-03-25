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
            'get_reconcile_date': self.get_reconcile_date,
            '_t': self._t,
        })

    def set_context(self, objects, data, ids, report_type=None):
        """
        Fills in:
        - self.sql_additional and self.sql_rec_additional with the part of SQL request corresponding to the criteria selected (string)
        - self.sql_params and self.sql_rec_params with the related parameters (list)

        For reconciliation queries the reconciliation dates must be within the FY/periods/dates selected.
        For other queries the JI dates are used.
        """
        period_obj = self.pool.get('account.period')
        fy_obj = self.pool.get('account.fiscalyear')
        if data.get('form', False):
            # note: the JE id is used and not the JI one to make sure whole entries are retrieved (cf. JI doc dates can differ within a JE)
            sql_additional_subreq = """
                AND m.id IN 
                (
                    SELECT DISTINCT (m.id)
                    FROM account_move m, account_move_line l
                    WHERE l.move_id = m.id
                    %s
                )
            """
            sql_rec_additional_subreq = """
                AND l.reconcile_id IN 
                (
                    SELECT DISTINCT (reconcile_id)
                    FROM account_move m, account_move_line l
                    WHERE l.move_id = m.id
                    AND l.reconcile_id IS NOT NULL
                    %s
                )
            """
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
            # entry status
            move_state = data['form'].get('move_state', '')
            if move_state:
                self.sql_additional += " AND m.state = %s "
                self.sql_params.append(move_state)
                # note: JE should always be posted for rec. queries (check kept as this report is used to spot inconsistencies...)
                self.sql_rec_additional += " AND m.state = %s "
                self.sql_rec_params.append(move_state)
            # periods
            if wiz_filter == 'filter_period':
                period_from = data['form'].get('period_from', False)
                period_to = data['form'].get('period_to', False)
                if not period_from or not period_to:
                    raise osv.except_osv(_('Error'), _('Either the Start period or the End period is missing.'))
                else:
                    period_ids = period_obj.get_period_range(self.cr, self.uid, period_from, period_to, context=data.get('context', {}))
                    if not period_ids:
                        raise osv.except_osv(_('Error'), _('No period matches the selected criteria.'))
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
            # LAST STEP: if the request additional parts aren't empty: add the related subrequests
            if self.sql_additional:
                self.sql_additional = sql_additional_subreq % self.sql_additional
            if self.sql_rec_additional:
                self.sql_rec_additional = sql_rec_additional_subreq % self.sql_rec_additional
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
        # not run entries query
        if query_ref == 'not_runs_entries':
            self.cr.execute(sql)
        # other queries
        elif query_ref in ('mismatch_ji_aji_fctal', 'mismatch_ji_aji_booking', 'ji_unbalanced_fctal', 'ji_unbalanced_booking'):
            sql = sql % self.sql_additional
            if self.sql_params:
                self.cr.execute(sql, tuple(self.sql_params))
            else:
                self.cr.execute(sql)
        return self.cr.fetchall()

    def get_reconcile_date(self, reconcile_ref):
        """
        Returns the reconcile_date of the reconciliation in parameter (or None if the reconciled entries have no reconcile_date).
        Note that this date isn't retrieved directly in the original requests as there are old entries for which within a same reconciliation
        some lines have a reconcile_date and some others haven't any, so to be consistent the results can't be "grouped by" reconcile date.
        """
        reconcile_date = None
        if reconcile_ref:
            rec_date_sql = """
            SELECT reconcile_date
            FROM account_move_line
            WHERE reconcile_date IS NOT NULL
            AND reconcile_id = (SELECT id FROM account_move_reconcile WHERE name = %s LIMIT 1)
            LIMIT 1;
            """
            self.cr.execute(rec_date_sql, (reconcile_ref,))
            rec_date_res = self.cr.fetchone()
            if rec_date_res:
                reconcile_date = rec_date_res[0]
        return reconcile_date

    def _t(self, source):
        return _(source)

SpreadsheetReport('report.integrity.finance', 'board.board', 'board/report/integrity.mako', parser=integrity_finance)
