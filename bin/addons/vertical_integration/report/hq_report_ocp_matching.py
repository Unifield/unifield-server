# -*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 TeMPO Consulting, MSF. All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from tools.translate import _
import pooler

import time
from time import strftime
from time import strptime

from account_override import finance_export

from report import report_sxw


##### WARNING #####
### IN CASE CHANGES ARE MADE TO THIS FILE, keep in mind that it is used for OCB matching export as well. ###


class finance_archive(finance_export.finance_archive):
    """
    Extends existing class with new methods for OCP Matching Export.

    Note: this report has NOT been translated: headers of all reports for OCP VI remain in English whatever the language selected
    """

    def postprocess_reconciliation_data(self, cr, uid, data, model, column_deletion=False):
        """
        1st column: adds the DB id
        15th column: replaces the reconcile id by the reconcile name.
        """
        if not data:
            return []
        pool = pooler.get_pool(cr.dbname)
        new_data = []
        reconcile_obj = pool.get('account.move.reconcile')
        for line in data:
            tmp_line = list(line)
            reconcile_id = line[14]
            if reconcile_id:
                reconcile = reconcile_obj.read(cr, uid, reconcile_id, ['name'])
                if reconcile and reconcile.get('name', False):
                    tmp_line[14] = reconcile.get('name')
            line_ids = str(line[0])
            tmp_line[0] = self.get_hash(cr, uid, line_ids, model)
            new_data.append(self.line_to_utf8(tmp_line))
        return new_data

    def postprocess_reconcilable(self, cr, uid, data, model, column_deletion=False):
        """
        - For the reconciled entries:
            - check that all the legs have a posting date within or before the selected period
            - otherwise: don't keep any of the legs for the report
            - (note that the partial reconciliations are already excluded from the list)
        - For the unreconciled entries, check the old reconciliation:
            - all legs must have a posting date within or before the selected period
            - the old reconciliation must have been total
            - otherwise: don't keep any of the legs for the report
        - Call postprocess_reconciliation_data on the new data
        """
        new_data = []
        entries_kept = set()
        entries_not_kept = set()
        pool = pooler.get_pool(cr.dbname)
        aml_obj = pool.get('account.move.line')
        # column numbers corresponding to properties
        id_from_db = 0  # this has to correspond to the real id from the DB and not the new id displayed in the file
        reconcile_id_col = 14
        date_stop = 15
        unreconcile_txt_col = 16
        for line in data:
            line_list = list(line)
            entry_kept = False
            line_id = line_list[id_from_db]
            # if the checks have already been done on the line reconcile number, don't repeat the same checks:
            # add the line if it must be kept / otherwise skip to next line
            if line_id in entries_kept:
                entry_kept = True
                aml_list = []  # clear the list => avoid to add the old list content to final data
            elif line_id in entries_not_kept:
                continue
            elif line_list[reconcile_id_col]:
                # reconciled entries
                reconcile_id = line_list[reconcile_id_col]
                # get the JI with the same reconcile_id
                aml_list = aml_obj.search(cr, uid, [('reconcile_id', '=', reconcile_id)])
                # check that they all have a posting date within or before the selected period
                nb_aml = aml_obj.search(cr, uid, [('id', 'in', aml_list), ('date', '<=', line_list[date_stop])], count=True)
                if nb_aml and nb_aml == len(aml_list):
                    entry_kept = True
            else:
                # unreconciled entries
                unreconcile_txt = line_list[unreconcile_txt_col]
                # get the JI with the same unreconcile_txt (old reconcile number)
                aml_list = aml_obj.search(cr, uid, [('unreconcile_txt', '=', unreconcile_txt)])
                # check that they all have a posting date within or before the selected period
                nb_aml = aml_obj.search(cr, uid, [('id', 'in', aml_list), ('date', '<=', line_list[date_stop])], count=True)
                if nb_aml and nb_aml == len(aml_list):
                    # if the dates are ok, check that the entries are balanced
                    booking_debit = 0
                    booking_credit = 0
                    for unreconciled_aml in aml_obj.browse(cr, uid, aml_list, fields_to_fetch=['debit_currency', 'credit_currency']):
                        booking_debit += unreconciled_aml.debit_currency or 0.0
                        booking_credit += unreconciled_aml.credit_currency or 0.0
                    if abs(booking_debit - booking_credit) <= 10 ** -3:
                        entry_kept = True
            if entry_kept:
                # if the entry is kept, delete the columns not used anymore
                line_list = column_deletion and self.delete_x_column(line_list, column_deletion)
                # add the line to the final data
                new_data.append(tuple(line_list))
                # all the entries from the same reconciliation are acceptable
                entries_kept.update(aml_list)
            else:
                # all the entries from the same reconciliation must be excluded
                entries_not_kept.update(aml_list)
        return self.postprocess_reconciliation_data(cr, uid, new_data, model)


class hq_report_ocp_matching(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        """
        Create a report and return its content.
        The content is composed of:
         - reconcilable lines
        """
        if context is None:
            context = {}
        pool = pooler.get_pool(cr.dbname)
        instance_obj = pool.get('msf.instance')
        period_obj = pool.get('account.period')
        if context.get('ocb_matching'):
            # OCB VI
            excluded_journal_types = ['cur_adj', 'hq', 'inkind', 'migration', 'extra', 'system']
        else:
            # OCP VI
            excluded_journal_types = ['hq', 'migration']
        ocb_numbering = ''

        if context.get('poc_export'):
            ocb_numbering = """,
                ocb_vi.move_number AS "JE ID",
                ocb_vi.line_number AS "Line Number",
                mapping.mapping_value AS "HQ system account code"
            """
        # Fetch data from wizard
        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))
        form = data.get('form')
        fy_id = form.get('fiscalyear_id', False)
        period_id = form.get('period_id', False)
        instance_ids = form.get('instance_ids', False)
        instance_id = form.get('instance_id', False)
        if not fy_id or not period_id or not instance_ids or not instance_id:
            raise osv.except_osv(_('Warning'), _('Some information is missing: either fiscal year or period or instance.'))
        # Prepare SQL requests and PROCESS requests for finance_archive object (CF. account_tools/finance_export.py)
        sqlrequests = {
            # This request returns:
            # - entries where posting date are within the selected period or before
            # - that have either been reconciled OR unreconciled within the period or after
            # Partial reconciliations are excluded.
            'reconcilable': """
                SELECT 
                aml.id,
                m.name AS "entry_sequence",
                aml.name,
                aml.ref,
                aml.document_date,
                aml.date,
                a.code,
                aml.partner_txt,
                debit_currency,
                credit_currency,
                c.name AS "Booking Currency",
                ROUND(aml.debit, 2),
                ROUND(aml.credit, 2),
                cc.name AS "functional_currency",
                aml.reconcile_id,
                %s AS "date_stop",
                aml.unreconcile_txt
            """ + ocb_numbering + """
                FROM account_move_line AS aml
                LEFT JOIN account_move_reconcile amr ON aml.reconcile_id = amr.id
                INNER JOIN account_move AS m ON aml.move_id = m.id
                INNER JOIN account_account AS a ON aml.account_id = a.id
                INNER JOIN res_currency AS c ON aml.currency_id = c.id
                INNER JOIN res_company AS e ON aml.company_id = e.id
                INNER JOIN res_currency AS cc ON e.currency_id = cc.id
                INNER JOIN account_journal AS j ON aml.journal_id = j.id
                INNER JOIN account_period AS p ON p.id = aml.period_id
                LEFT JOIN ocb_vi_export_number ocb_vi ON ocb_vi.move_line_id = aml.id AND ocb_vi.entry_sequence=m.name
                LEFT JOIN account_export_mapping mapping ON mapping.account_id = a.id
                WHERE j.type not in %s
                AND p.number not in (0, 16)
                AND aml.instance_id in %s
                AND aml.date <= %s
                AND reconcile_partial_id IS NULL
                AND (
                    (aml.reconcile_id IS NOT NULL AND aml.reconcile_date >= %s) OR
                    (COALESCE(aml.unreconcile_txt, '') != '' AND aml.unreconcile_date >= %s)
                )
                ORDER BY aml.reconcile_id, aml.unreconcile_txt
                """,
        }

        # Define the file name according to the following format:
        # First3CharactersOfInstanceCode_chosenPeriod_currentDatetime_Check_on_reconcilable_entries.csv
        # (e.g. KE1_201610_171116110306_Check_on_reconcilable_entries.csv)
        instance = instance_obj.browse(cr, uid, instance_id, context=context, fields_to_fetch=['code'])
        instance_code = instance and instance.code[:3] or ''
        period = period_obj.browse(cr, uid, period_id, context=context, fields_to_fetch=['date_start', 'date_stop'])
        date_start = period.date_start
        date_stop = period.date_stop
        selected_period = strftime('%Y%m', strptime(date_start, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        reconcilable_entries_filename = '%s_%s_%s_Check_on_reconcilable_entries.csv' % (instance_code, selected_period, current_time)

        processrequests = [
            {
                'headers': ['DB ID', 'Entry Sequence', 'Description', 'Reference', 'Document Date', 'Posting Date', 'G/L Account',
                            'Third Party', 'Booking Debit', 'Booking Credit', 'Booking Currency', 'Functional Debit',
                            'Functional Credit', 'Functional Currency', 'Reconcile reference', 'Unreconcile reference'],
                'filename': reconcilable_entries_filename,
                'key': 'reconcilable',
                'query_params': (date_stop, tuple(excluded_journal_types), tuple(instance_ids), date_stop, date_start, date_start),
                'function': 'postprocess_reconcilable',
                'fnct_params': 'account.move.line',
                'delete_columns': [15],
            },
        ]
        if context.get('poc_export'):
            processrequests[0]['headers'] += ['JE ID', 'Line Number', 'HQ system account code']
        # Launch finance archive object
        fe = finance_archive(sqlrequests, processrequests, context=context)
        # Use archive method to create the archive
        return fe.archive(cr, uid)

hq_report_ocp_matching('report.hq.ocp.matching', 'account.move.line', False, parser=False)
