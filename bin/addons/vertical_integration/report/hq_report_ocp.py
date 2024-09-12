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
from datetime import datetime
from account_override import finance_export
from . import hq_report_ocb
import logging
from report import report_sxw
import csv
import zipfile
import tempfile
from tools.misc import Path
import os

class finance_archive(finance_export.finance_archive):
    """
    Extend existing class with new methods for this particular export.

    Note: this report has NOT been translated: headers of all reports for OCP VI remain in English whatever the language selected
    """

    _journal_types = None

    def _get_journal_types(self, cr, uid):
        """
        Returns a dictionary containing key and value of the Journal Types
        """
        if not self._journal_types:
            pool = pooler.get_pool(cr.dbname)
            journal_obj = pool.get('account.journal')
            self._journal_types = dict(journal_obj.fields_get(cr, uid)['type']['selection'])
        return self._journal_types

    def _get_journal_type_value(self, cr, uid, journal_type_key):
        """
        Returns the value of the Journal Type corresponding to the key in parameter (e.g. inkind => In-kind Donation...)
        If no corresponding value is found, returns the key.
        """
        journal_types = self._get_journal_types(cr, uid)
        return journal_types.get(journal_type_key, journal_type_key)

    def _handle_od_ji_entries(self, cr, uid, data):
        """
        Takes data in parameter corresponding to ACCOUNT MOVE LINES (results from 'bs_entries' or 'plresult' requests)
        1) Replaces the journal type "key" by its corresponding "value" (e.g. inkind => In-kind Donation)
        2) Modifies it for all entries that originate from HQ entry corrections:
        - instance: 'EAUD' or 'SIEG' if this matches the first 4 characters of the original HQ entry (if not: 'SIEG' by default)
        - journal: the journal name corresponds to the 9-to-11 characters of the reference field of the original HQ entry
        Returns a list of tuples (same format as data)
        """
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        aml_obj = pool.get('account.move.line')
        # column numbers corresponding to properties
        id_from_db = 0  # this has to correspond to the real id from the DB and not the new id displayed in the file
        instance_code = 1
        journal = 2
        journal_type = 22
        for line in data:
            line_list = list(line)
            line_list[journal_type] = self._get_journal_type_value(cr, uid, line_list[journal_type])
            od_hq_entry = False
            if line_list[journal] in ('OD', 'ODHQ'):  # 'OD' for entries before US-6692
                aml = aml_obj.browse(cr, uid, line_list[id_from_db], fields_to_fetch=['corrected_line_id', 'reversal_line_id'])
                corrected_aml = aml.corrected_line_id
                reversed_aml = aml.reversal_line_id
                # US-2346 If there are several levels of correction use the last one to check if the original entry was an HQ entry
                corr_aml = corrected_aml or reversed_aml
                if corr_aml:
                    initial_id = -1
                    final_id = -2
                    while initial_id != final_id:
                        initial_id = corr_aml.id
                        # check if the corrected line corrects another line
                        corr_aml = corr_aml.corrected_line_id or corr_aml
                        final_id = corr_aml.id
                    if corr_aml.journal_id.type == 'hq':
                        od_hq_entry = True
                if od_hq_entry:
                    original_ref = corr_aml.ref or ''
                    line_list[instance_code] = original_ref.startswith('EAUD') and 'EAUD' or 'SIEG'
                    line_list[journal] = original_ref[8:11] or ''
            new_data.append(tuple(line_list))
        return new_data

    def _handle_od_aji_entries(self, cr, uid, data):
        """
        Takes data in parameter corresponding to ACCOUNT ANALYTIC LINES (results from 'rawdata' request)
        1) Replaces the journal type "key" by its corresponding "value" (e.g. inkind => In-kind Donation)
        2) Modifies it for all entries that originate from HQ entry corrections:
        - instance: 'EAUD' or 'SIEG' if this matches the first 4 characters of the original HQ entry (if not: 'SIEG' by default)
        - journal: the journal name corresponds to the 9-to-11 characters of the reference field of the original HQ entry
        Returns a list of tuples (same format as data)
        """
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        aal_obj = pool.get('account.analytic.line')
        # column numbers corresponding to properties
        id_from_db = 0  # this has to correspond to the real id from the DB and not the new id displayed in the file
        instance_code = 1
        journal = 2
        journal_type = 22
        for line in data:
            line_list = list(line)
            line_list[journal_type] = self._get_journal_type_value(cr, uid, line_list[journal_type])
            od_hq_entry = False
            if line_list[journal] in ('OD', 'ODHQ'):  # 'OD' for entries before US-6692
                aal = aal_obj.browse(cr, uid, line_list[id_from_db], fields_to_fetch=['last_corrected_id', 'reversal_origin'])
                corrected_aal = aal.last_corrected_id
                reversed_aal = aal.reversal_origin
                # US-2346 If there are several levels of correction use the last one to check if the original entry was an HQ entry
                corr_aal = corrected_aal or reversed_aal
                if corr_aal:
                    initial_id = -1
                    final_id = -2
                    while initial_id != final_id:
                        initial_id = corr_aal.id
                        # check if the corrected line corrects another line
                        corr_aal = corr_aal.last_corrected_id or corr_aal
                        final_id = corr_aal.id
                    if corr_aal.journal_id.type == 'hq':
                        od_hq_entry = True
                if od_hq_entry:
                    original_ref = corr_aal.ref or ''
                    line_list[instance_code] = original_ref.startswith('EAUD') and 'EAUD' or 'SIEG'
                    line_list[journal] = original_ref[8:11] or ''
            new_data.append(tuple(line_list))
        return new_data

    def postprocess_ji_entries(self, cr, uid, data, model, column_deletion=False):
        """
        ##### WARNING #####
        ### THIS CALLS THE METHOD postprocess_add_db_id FROM OCB ###
        - first modify the data for all lines corresponding to entries originating from HQ entry corrections
        - then call OCB method on the new data to change first column for the DB ID
        """
        new_data = self._handle_od_ji_entries(cr, uid, data)  # we handle account move lines
        finance_archive_ocb = hq_report_ocb.finance_archive(self.sqlrequests, self.processrequests)
        return finance_archive_ocb.postprocess_add_db_id(cr, uid, new_data, model, column_deletion)

    def postprocess_aji_entries(self, cr, uid, data, model, column_deletion=False):
        """
        ##### WARNING #####
        ### THIS CALLS THE METHOD postprocess_add_db_id FROM OCB ###
        - first modify the data for all lines corresponding to entries originating from HQ entry corrections
        - then call OCB method on the new data to change first column for the DB ID
        """
        new_data = self._handle_od_aji_entries(cr, uid, data)  # we handle account analytic lines
        finance_archive_ocb = hq_report_ocb.finance_archive(self.sqlrequests, self.processrequests)
        return finance_archive_ocb.postprocess_add_db_id(cr, uid, new_data, model, column_deletion)

    def postprocess_consolidated_entries(self, cr, uid, data, excluded_journal_types, column_deletion=False):
        """
        ##### WARNING #####
        ### THIS CALLS THE METHOD FROM OCB ###
        Handle of the consolidate entries:
        aggregate the lines that are on an account where "Shrink entries for HQ export" is checked
        """
        finance_archive_ocb = hq_report_ocb.finance_archive(self.sqlrequests, self.processrequests)
        new_data = finance_archive_ocb.postprocess_consolidated_entries(cr, uid, data, excluded_journal_types, column_deletion, display_journal_type=True)
        # For the Instance column (never empty), display only the first 3 characters
        # Use the same value to fill in the Cost Center column (that is empty otherwise)
        instance_code_col = 1
        cc_col = 11
        journal_type_col = 21
        for line in new_data:
            instance_code = line[instance_code_col][:3]
            line[instance_code_col] = instance_code
            line[cc_col] = instance_code
            # Replaces the journal type "key" by its corresponding "value" (e.g. inkind => In-kind Donation)
            line[journal_type_col] = self._get_journal_type_value(cr, uid, line[journal_type_col])
        return new_data

    def postprocess_liquidity_balances(self, cr, uid, data, context=None, column_deletion=False):
        """
        Note that the param "column_deletion" is needed (see def archive in finance_export) but NOT used here.
        """
        return hq_report_ocb.postprocess_liquidity_balances(self, cr, uid, data, context=context)


# request used for OCP VI only (removed from OCG VI in US-6516)
# Journals excluded from the Account Balances: Migration, In-kind Donation, OD-Extra Accounting
account_balances_per_currency_sql = """
    SELECT i.code AS instance, acc.code, acc.name, %(period_yyymm)s AS period, req.opening, req.calculated, req.closing,
           c.name AS currency
    FROM
    (
        SELECT instance_id, account_id, currency_id, SUM(col1) AS opening,
               SUM(col2) AS calculated, SUM(col3) AS closing
        FROM (
            (
                SELECT aml.instance_id AS instance_id, aml.account_id AS account_id,
                       aml.currency_id AS currency_id,
                ROUND(SUM(amount_currency), 2) as col1, 0.00 as col2, 0.00 as col3
                FROM account_move_line AS aml
                LEFT JOIN account_journal j ON aml.journal_id = j.id
                LEFT JOIN account_account acc ON aml.account_id = acc.id
                LEFT JOIN res_currency curr ON aml.currency_id = curr.id
                WHERE acc.active = 't'
                AND curr.active = 't'
                AND ( aml.date < %(first_day_of_period)s or aml.period_id in %(include_period_opening)s )
                AND j.instance_id IN %(instance_ids)s
                AND j.type NOT IN ('migration', 'inkind', 'extra')
                GROUP BY aml.instance_id, aml.account_id, aml.currency_id
            )
        UNION
            (
                SELECT aml.instance_id AS instance_id, aml.account_id AS account_id,
                       aml.currency_id AS currency_id,
                0.00 as col1, ROUND(SUM(amount_currency), 2) as col2, 0.00 as col3
                FROM account_move_line AS aml
                LEFT JOIN account_journal j ON aml.journal_id = j.id
                LEFT JOIN account_account acc ON aml.account_id = acc.id
                LEFT JOIN res_currency curr ON aml.currency_id = curr.id
                WHERE acc.active = 't'
                AND curr.active = 't'
                AND aml.period_id = %(period_id)s
                AND j.instance_id IN %(instance_ids)s
                AND j.type NOT IN ('migration', 'inkind', 'extra')
                GROUP BY aml.instance_id, aml.account_id, aml.currency_id
            )
        UNION
            (
                SELECT aml.instance_id AS instance_id, aml.account_id AS account_id,
                       aml.currency_id AS currency_id,
                0.00 as col1, 0.00 as col2, ROUND(SUM(amount_currency), 2) as col3
                FROM account_move_line AS aml
                LEFT JOIN account_journal j ON aml.journal_id = j.id
                LEFT JOIN account_account acc ON aml.account_id = acc.id
                LEFT JOIN res_currency curr ON aml.currency_id = curr.id
                WHERE acc.active = 't'
                AND curr.active = 't'
                AND ( aml.date <= %(last_day_of_period)s and aml.period_id not in %(exclude_period_closing)s )
                AND j.instance_id IN %(instance_ids)s
                AND j.type NOT IN ('migration', 'inkind', 'extra')
                GROUP BY aml.instance_id, aml.account_id, aml.currency_id
            )
        ) AS ssreq
        GROUP BY instance_id, account_id, currency_id
        ORDER BY instance_id, account_id, currency_id
    ) AS req
    INNER JOIN account_account acc ON req.account_id = acc.id
    INNER JOIN res_currency c ON req.currency_id = c.id
    INNER JOIN msf_instance i ON req.instance_id = i.id
    WHERE (req.opening != 0.0 OR req.calculated != 0.0 OR req.closing != 0.0);
    """

account_balances_per_currency_with_euro_sql = """
    SELECT i.code AS instance, acc.code, acc.name, %(period_yyymm)s AS period, c.name AS currency, req.opening, req.calculated, req.closing, req.opening_eur, req.calculated_eur, req.closing_eur
    FROM
    (
        SELECT instance_id, account_id, currency_id, SUM(col1) AS opening,
               SUM(col2) AS calculated, SUM(col3) AS closing,
               sum(col4) as opening_eur, sum(col5) as calculated_eur, sum(col6) as closing_eur
        FROM (
            (
                SELECT aml.instance_id AS instance_id, aml.account_id AS account_id,
                       aml.currency_id AS currency_id,
                ROUND(SUM(amount_currency), 2) as col1, 0.00 as col2, 0.00 as col3,
                ROUND(SUM(coalesce(debit, 0) - coalesce(credit, 0)), 2) as col4, 0.00 as col5, 0.00 as col6
                FROM account_move_line AS aml
                LEFT JOIN account_journal j ON aml.journal_id = j.id
                LEFT JOIN account_account acc ON aml.account_id = acc.id
                LEFT JOIN res_currency curr ON aml.currency_id = curr.id
                WHERE acc.active = 't'
                AND curr.active = 't'
                AND ( aml.date < %(first_day_of_period)s or aml.period_id in %(include_period_opening)s )
                AND j.instance_id IN %(instance_ids)s
                AND j.type NOT IN ('migration', 'inkind', 'extra')
                GROUP BY aml.instance_id, aml.account_id, aml.currency_id
            )
        UNION
            (
                SELECT aml.instance_id AS instance_id, aml.account_id AS account_id,
                       aml.currency_id AS currency_id,
                0.00 as col1, ROUND(SUM(amount_currency), 2) as col2, 0.00 as col3,
                0.00 as col4, ROUND(SUM(coalesce(debit, 0) - coalesce(credit, 0)), 2) as col5, 0.00 as col6
                FROM account_move_line AS aml
                LEFT JOIN account_journal j ON aml.journal_id = j.id 
                LEFT JOIN account_account acc ON aml.account_id = acc.id
                LEFT JOIN res_currency curr ON aml.currency_id = curr.id
                WHERE acc.active = 't'
                AND curr.active = 't'
                AND aml.period_id = %(period_id)s
                AND j.instance_id IN %(instance_ids)s
                AND j.type NOT IN ('migration', 'inkind', 'extra')
                GROUP BY aml.instance_id, aml.account_id, aml.currency_id
            )
        UNION
            (
                SELECT aml.instance_id AS instance_id, aml.account_id AS account_id,
                       aml.currency_id AS currency_id,
                0.00 as col1, 0.00 as col2, ROUND(SUM(amount_currency), 2) as col3,
                0.00 as col4, 0.00 as col5, ROUND(SUM(coalesce(debit, 0) - coalesce(credit, 0)), 2) as col6
                FROM account_move_line AS aml
                LEFT JOIN account_journal j ON aml.journal_id = j.id
                LEFT JOIN account_account acc ON aml.account_id = acc.id
                LEFT JOIN res_currency curr ON aml.currency_id = curr.id
                WHERE acc.active = 't'
                AND curr.active = 't'
                AND ( aml.date <= %(last_day_of_period)s and aml.period_id not in %(exclude_period_closing)s )
                AND j.instance_id IN %(instance_ids)s
                AND j.type NOT IN ('migration', 'inkind', 'extra')
                GROUP BY aml.instance_id, aml.account_id, aml.currency_id
            )
        ) AS ssreq
        GROUP BY instance_id, account_id, currency_id
        ORDER BY instance_id, account_id, currency_id
    ) AS req
    INNER JOIN account_account acc ON req.account_id = acc.id
    INNER JOIN res_currency c ON req.currency_id = c.id
    INNER JOIN msf_instance i ON req.instance_id = i.id
    WHERE (req.opening != 0.0 OR req.calculated != 0.0 OR req.closing != 0.0);
    """


class hq_report_ocp(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        """
        Create a report and return its content.
        The content is composed of:
         - Raw data (a kind of synthesis of funding pool analytic lines)
        """
        if context is None:
            context = {}
        pool = pooler.get_pool(cr.dbname)
        ayec_obj = pool.get('account.year.end.closing')
        mi_obj = pool.get('msf.instance')
        m_obj = pool.get('account.move')
        ml_obj = pool.get('account.move.line')
        period_obj = pool.get('account.period')
        excluded_journal_types = ['hq', 'migration', 'inkind', 'extra']  # journal types that should not be used to take lines
        # Fetch data from wizard
        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))
        form = data.get('form')
        fy_id = form.get('fiscalyear_id', False)
        period_id = form.get('period_id', False)
        instance_ids = form.get('instance_ids', False)
        instance_id = form.get('instance_id', False)
        all_missions = form.get('all_missions', False)
        if not fy_id or not period_id or not instance_ids or (not instance_id and not all_missions):
            raise osv.except_osv(_('Warning'), _('Some information is missing: either fiscal year or period or instance.'))
        period = period_obj.browse(cr, uid, period_id, context=context,
                                   fields_to_fetch=['date_start', 'date_stop', 'number', 'fiscalyear_id'])
        first_day_of_period = period.date_start
        tm = strptime(first_day_of_period, '%Y-%m-%d')
        year_num = tm.tm_year

        # US-822: if December is picked should:
        # - include Period 16 action 2 Year end PL RESULT entries
        #   of target Coordo
        plresult_ji_in_ids = []
        if period.number == 12:
            period16_id = ayec_obj._get_period_id(cr, uid, fy_id, 16)
            if period16_id:
                # get potential PL RESULT entries of us-822 book_pl_results
                func_ccy_name = pool.get('res.users').browse(cr, uid, [uid],
                                                             context=context)[0].company_id.currency_id.name
                seqnums = [
                    ayec_obj._book_pl_results_seqnum_pattern % (year_num,
                                                                instance_rec.code, func_ccy_name, ) \
                    for instance_rec in mi_obj.browse(cr, uid, instance_ids,
                                                      context=context) \
                    if instance_rec.level == 'coordo'
                ]

                if seqnums:
                    je_ids = m_obj.search(cr, uid, [ ('name', 'in', seqnums) ],
                                          context=context)
                    if je_ids:
                        plresult_ji_in_ids = ml_obj.search(cr, uid, [
                            ('move_id', 'in', je_ids)
                        ], context=context)

        # Prepare SQL requests and PROCESS requests for finance_archive object

        # SQLREQUESTS DICTIONNARY
        # - key: name of the SQL request
        # - value: the SQL request to use
        sqlrequests = {
            # Pay attention to take analytic lines that are not on HQ, MIGRATION, IN-KIND and ODX journals.
            'rawdata': """
                SELECT al.id, SUBSTR(i.code, 1, 3),
                       CASE WHEN j.code IN ('OD', 'ODHQ') THEN j.code ELSE aj.code END AS journal,
                       al.entry_sequence, al.name, al.ref, al.document_date, al.date,
                       a.code, al.partner_txt, aa.code AS dest, aa2.code AS cost_center_id, aa3.code AS funding_pool, 
                       CASE WHEN al.amount_currency < 0 AND aml.is_addendum_line = 'f' THEN ABS(al.amount_currency) ELSE 0.0 END AS debit,
                       CASE WHEN al.amount_currency > 0 AND aml.is_addendum_line = 'f' THEN al.amount_currency ELSE 0.0 END AS credit,
                       c.name AS "booking_currency",
                       CASE WHEN al.amount < 0 THEN ABS(ROUND(al.amount, 2)) ELSE 0.0 END AS debit,
                       CASE WHEN al.amount > 0 THEN ROUND(al.amount, 2) ELSE 0.0 END AS credit,
                       cc.name AS "functional_currency", hr.identification_id as "emplid", aml.partner_id, hr.name_resource as hr_name,
                       CASE WHEN j.code IN ('OD', 'ODHQ') THEN j.type ELSE aj.type END AS journal_type
                FROM account_analytic_line AS al, 
                     account_account AS a, 
                     account_analytic_account AS aa, 
                     account_analytic_account AS aa2, 
                     account_analytic_account AS aa3,
                     res_currency AS c, 
                     res_company AS e, 
                     res_currency AS cc, 
                     account_analytic_journal AS j, 
                     account_move_line aml left outer join hr_employee hr on hr.id = aml.employee_id, 
                     account_journal AS aj, msf_instance AS i 
                WHERE al.destination_id = aa.id
                AND al.cost_center_id = aa2.id
                AND al.account_id = aa3.id
                AND al.general_account_id = a.id
                AND al.currency_id = c.id
                AND aa3.category = 'FUNDING'
                AND al.company_id = e.id
                AND e.currency_id = cc.id
                AND al.journal_id = j.id
                AND al.move_id = aml.id
                AND aml.id in (select aml2.id 
                               from account_move_line aml2, account_move am,
                               account_period as p2
                               where am.id = aml2.move_id and p2.id = am.period_id
                               and p2.number not in (0, 16) and am.state = 'posted'
                              )
                AND al.instance_id = i.id
                AND aml.journal_id = aj.id
                AND ((not a.is_analytic_addicted and aml.period_id = %s) or (a.is_analytic_addicted and (al.real_period_id = %s or (al.real_period_id is NULL and al.date >= %s and al.date <= %s))))
                AND j.type not in %s
                AND al.instance_id in %s;
                """,
            # Exclude lines that come from HQ, MIGRATION, IN-KIND or ODX journals
            # Take all lines that are on account that is "shrink_entries_for_hq" which will make a consolidation of them (with a second SQL request)
            # Don't include the lines that have analytic lines. This is to not retrieve expense/income accounts
            'bs_entries_consolidated': """
                SELECT aml.id
                FROM account_move_line AS aml
                INNER JOIN account_account AS aa ON aml.account_id = aa.id
                INNER JOIN account_journal AS j ON aml.journal_id = j.id
                LEFT JOIN account_analytic_line aal ON aml.id = aal.move_id
                WHERE aml.period_id = %s
                AND j.type NOT IN %s
                AND aa.shrink_entries_for_hq = 't'
                AND aal.id IS NULL
                AND aml.instance_id IN %s;
                """,
            # Do not take lines that come from HQ, MIGRATION, IN-KIND or ODX journals
            # Do not take journal items that have analytic lines because they are taken from "rawdata" SQL request
            # For these entries instead of the "Cost centre" we take the same value as in the "Instance" column
            'bs_entries': """
                SELECT aml.id, SUBSTR(i.code, 1, 3), j.code, m.name as "entry_sequence", aml.name, aml.ref, aml.document_date, aml.date,
                       a.code, aml.partner_txt, '', SUBSTR(i.code, 1, 3), '', aml.debit_currency, aml.credit_currency, c.name,
                       ROUND(aml.debit, 2), ROUND(aml.credit, 2), cc.name, hr.identification_id as "Emplid", aml.partner_id,
                       hr.name_resource as hr_name, j.type
                FROM account_move_line aml 
                LEFT JOIN hr_employee hr ON hr.id = aml.employee_id
                INNER JOIN account_account AS a ON aml.account_id = a.id
                INNER JOIN res_currency AS c ON aml.currency_id = c.id
                INNER JOIN account_move AS m ON aml.move_id = m.id
                INNER JOIN res_company AS e ON aml.company_id = e.id
                INNER JOIN account_journal AS j ON aml.journal_id = j.id
                INNER JOIN res_currency AS cc ON e.currency_id = cc.id
                INNER JOIN msf_instance AS i ON aml.instance_id = i.id
                LEFT JOIN account_analytic_line aal ON aal.move_id = aml.id
                WHERE aal.id IS NULL
                AND aml.period_id = %s
                AND a.shrink_entries_for_hq != 't'
                AND j.type NOT IN %s
                AND aml.instance_id IN %s
                AND m.state = 'posted'
                ORDER BY aml.id;
                """,
            'liquidity': hq_report_ocb.liquidity_sql,

            'account_balances_per_currency': account_balances_per_currency_sql,
        }
        if plresult_ji_in_ids:
            # NOTE: for these entries: booking and functional ccy are the same
            # For these entries instead of the "Cost centre" we take the same value as in the "Instance" column
            ''' columns
                'DB ID', 'Instance', 'Journal', 'Entry sequence', 'Description',
                'Reference', 'Document date', 'Posting date', 'G/L Account',
                'Third party', 'Destination', 'Cost centre', 'Funding pool',
                'Booking debit', 'Booking credit', 'Booking currency',
                'Functional debit', 'Functional credit', 'Functional CCY',
                'Emplid', 'Partner DB ID' 'Employee Name' 'Journal Type' '''
            sqlrequests['plresult'] = """
                SELECT aml.id, SUBSTR(i.code, 1, 3), j.code, m.name as "entry_sequence", aml.name,
                    aml.ref, aml.document_date, aml.date, a.code,
                    aml.partner_txt, '', SUBSTR(i.code, 1, 3), '',
                    ROUND(aml.debit_currency, 2), ROUND(aml.credit_currency, 2), c.name,
                    ROUND(aml.debit, 2), ROUND(aml.credit, 2), c.name,
                    '', '', '', j.type
                FROM account_move_line aml
                INNER JOIN msf_instance i on i.id = aml.instance_id
                INNER JOIN account_journal j on j.id = aml.journal_id
                INNER JOIN account_move m on m.id = aml.move_id
                INNER JOIN account_account a on a.id = aml.account_id
                INNER JOIN res_currency c on c.id = aml.currency_id
                WHERE aml.id in %s
            """

        # PROCESS REQUESTS LIST: list of dict containing info to process some SQL requests
        # Dict:
        # - [optional] headers: list of headers that should appear in the CSV file
        # - filename: the name of the result filename in the future ZIP file
        # - key: the name of the key in SQLREQUESTS DICTIONARY to have the right SQL request
        # - [optional] query_params: data to use to complete SQL requests
        # - [optional] function: name of the function to postprocess data (example: to change selection field into a human readable text)
        # - [optional] fnct_params: params that would be used on the given function
        # - [optional] delete_columns: list of columns to delete before writing files into result
        # - [optional] id (need 'object'): number of the column that contains the ID of the element.
        # - [optional] object (need 'id'): name of the object in the system. For example: 'account.bank.statement'.
        # TIP & TRICKS:
        # + More than 1 request in 1 file: just use same filename for each request you want to be in the same file.
        # + If you cannot do a SQL request to create the content of the file, do a simple request (with key) and add a postprocess function that returns the result you want

        # Define the file name according to the following format:
        # AllinstancesORFirst3CharactersOfInstanceCode_chosenPeriod_currentDatetime_Monthly_Export.csv
        # (e.g. KE1_201609_171116110306_Monthly_Export.csv)
        if all_missions:
            prefix = 'Allinstances'
        elif instance_id:
            inst = mi_obj.browse(cr, uid, instance_id, context=context, fields_to_fetch=['code'])
            prefix = inst and inst.code[:3] or ''
        else:
            prefix = ''
        selected_period = strftime('%Y%m', strptime(first_day_of_period, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        monthly_export_filename = '%s_%s_%s_Monthly_Export.csv' % (prefix, selected_period, current_time)
        liquidity_balance_filename = account_balance_filename = ''
        if not all_missions:
            liquidity_balance_filename = '%s_%s_%s_Liquidity_Balances.csv' % (prefix, selected_period, current_time)
            account_balance_filename = '%s_%s_%s_Account_Balances.csv' % (prefix, selected_period, current_time)

        processrequests = [
            {
                'headers': ['DB ID', 'Instance', 'Journal', 'Entry sequence', 'Description', 'Reference', 'Document date', 'Posting date', 'G/L Account', 'Third party', 'Destination', 'Cost centre', 'Funding pool', 'Booking debit', 'Booking credit', 'Booking currency', 'Functional debit', 'Functional credit',  'Functional CCY', 'Emplid', 'Partner DB ID', 'Journal Type'],
                'filename': monthly_export_filename,
                'key': 'rawdata',
                'function': 'postprocess_aji_entries',
                'fnct_params': 'account.analytic.line',
                'query_params': (period_id, period_id, period.date_start, period.date_stop, tuple(excluded_journal_types), tuple(instance_ids)),
                'delete_columns': [0],
                'id': 0,
                'object': 'account.analytic.line',
            },
            {
                'filename': monthly_export_filename,
                'key': 'bs_entries_consolidated',
                'query_params': (period_id, tuple(excluded_journal_types), tuple(instance_ids)),
                'function': 'postprocess_consolidated_entries',
                'fnct_params': excluded_journal_types,
            },
            {
                'filename': monthly_export_filename,
                'key': 'bs_entries',
                'function': 'postprocess_ji_entries',
                'fnct_params': 'account.move.line',
                'query_params': (period_id, tuple(excluded_journal_types), tuple(instance_ids)),
                'delete_columns': [0],
                'id': 0,
                'object': 'account.move.line',
            },
        ]
        if not all_missions:
            year = str(year_num)
            month = '%02d' % (tm.tm_mon)
            period_yyyymm = "{0}{1}".format(year, month)
            last_day_of_period = period.date_stop
            reg_types = ('cash', 'bank', 'cheque')
            include_period_opening = [0]
            exclude_period_closing = [0]

            if period.number in (13, 14, 15):
                include_period_opening = period_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id), ('number', 'in', [12, 13, 14]), ('number', '<', period.number)], context=context)
                if not include_period_opening:
                    include_period_opening = [0]

            if period.number in (12, 13, 14):
                exclude_period_closing = period_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id), ('special', '=', 't'), ('number', '>', period.number)], context=context)
                if not exclude_period_closing:
                    exclude_period_closing = [0]

            # Liquidity Balances
            processrequests.append(
                {
                    'headers': ['Instance', 'Code', 'Name', 'Period', 'Starting balance', 'Calculated balance',
                                'Closing balance', 'Currency'],
                    'filename': liquidity_balance_filename,
                    'key': 'liquidity',
                    'dict_query_params': {
                        'period_title': period_yyyymm,
                        'j_type': reg_types,
                        'date_from': first_day_of_period,
                        'date_to': last_day_of_period,
                        'instance_ids': tuple(instance_ids),
                    },
                    'function': 'postprocess_liquidity_balances',
                    'fnct_params': context,
                }
            )
            # Account Balances
            processrequests.append(
                {
                    'headers': ['Instance', 'Account', 'Account Name', 'Period', 'Starting balance',
                                'Calculated balance', 'Closing balance', 'Booking Currency'],
                    'filename': account_balance_filename,
                    'key': 'account_balances_per_currency',
                    'dict_query_params': {
                        'period_yyymm': period_yyyymm,
                        'first_day_of_period': first_day_of_period,
                        'last_day_of_period': last_day_of_period,
                        'instance_ids': tuple(instance_ids),
                        'period_id': period.id,
                        'include_period_opening': tuple(include_period_opening),
                        'exclude_period_closing': tuple(exclude_period_closing),

                    }
                },
            )
        if plresult_ji_in_ids:
            processrequests.append({
                'filename': monthly_export_filename,
                'key': 'plresult',
                'function': 'postprocess_ji_entries',
                'fnct_params': 'account.move.line',
                'query_params': (tuple(plresult_ji_in_ids), ),
                'delete_columns': [0],
                'id': 0,
                'object': 'account.move.line',
            })

        # Create a finance archive object
        fe = finance_archive(sqlrequests, processrequests, context=context)
        # Use archive method to create the archive
        return fe.archive(cr, uid)

hq_report_ocp('report.hq.ocp', 'account.move.line', False, parser=False)


class hq_report_ocp_workday(hq_report_ocp):

    def update_percent(self, cr, uid, percent):
        if self.bk_id:
            self.pool.get('memory.background.report').write(cr, uid, self.bk_id, {'percent': percent})


    def create(self, cr, uid, ids, data, context=None):

        debug = True

        if debug:
            logger = logging.getLogger('OCP Export')

        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))

        if context is None:
            context = {}

        pool = pooler.get_pool(cr.dbname)

        new_cr = pooler.get_db(cr.dbname).cursor()

        self.bk_id = context.get('background_id')
        self.pool = pool

        mi_obj = pool.get('msf.instance')
        period_obj = pool.get('account.period')
        excluded_journal_types = ['hq', 'migration', 'inkind', 'extra', 'engagement']  # journal types that should not be used to take lines

        form = data.get('form')
        period_id = form.get('period_id', False)
        instance_ids = form.get('instance_ids', False)
        instance_id = form.get('instance_id', False)
        all_missions = form.get('all_missions', False)
        if not period_id or not instance_ids or (not instance_id and not all_missions):
            raise osv.except_osv(_('Warning'), _('Some information is missing: either fiscal year or period or instance.'))

        period = period_obj.browse(cr, uid, period_id, context=context,
                                   fields_to_fetch=['date_start', 'date_stop', 'number', 'fiscalyear_id'])
        first_day_of_period = period.date_start
        tm = strptime(first_day_of_period, '%Y-%m-%d')
        year_num = tm.tm_year
        period_yyyymm = '%d%02d' % (year_num, tm.tm_mon)
        include_period_opening = [0]
        exclude_period_closing = [0]
        if period.number in (13, 14, 15):
            include_period_opening = period_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id), ('number', 'in', [12, 13, 14]), ('number', '<', period.number)], context=context)
            if not include_period_opening:
                include_period_opening = [0]

        if period.number in (12, 13, 14):
            exclude_period_closing = period_obj.search(cr, uid, [('fiscalyear_id', '=', period.fiscalyear_id.id), ('special', '=', 't'), ('number', '>', period.number)], context=context)
            if not exclude_period_closing:
                exclude_period_closing = [0]

        journal_type = dict(pool.get('account.journal').fields_get(cr, uid)['type']['selection'])


        # get budget rates
        fx_budget_rate = {}
        cr.execute('''
            select
                 DISTINCT ON (c.name) c.name, r.rate
            from
                res_currency_rate r, res_currency c, res_currency_table t
            where
                c.currency_table_id = t.id and
                r.currency_id = c.id and
                t.state = 'valid' and
                r.name < %s
                order by c.name, r.name desc
            ''', (period.date_stop, ))
        for x in cr.fetchall():
            fx_budget_rate[x[0]] = x[1]

        cr.execute('delete from hq_report_no_decimal where period_id = %s and instance_id in %s', (period_id, tuple(instance_ids)))
        cr.execute('delete from hq_report_func_adj where period_id = %s and instance_id in %s', (period_id, tuple(instance_ids)))
        # round AJI for match JI funct amount
        cr.execute("""
            select
                aml.id, round(aml.credit, 2) - round(aml.debit, 2)  - sum(round(al.amount, 2)), array_agg(al.id)
            from
                account_analytic_line AS al,
                res_currency AS c,
                account_analytic_journal AS j,
                account_journal AS aj,
                account_period p,
                account_move_line aml,
                account_move am
            where
                    c.id = al.currency_id
                    AND j.id = al.journal_id
                    AND aml.id = al.move_id
                    AND am.id = aml.move_id
                    AND p.id = am.period_id
                    AND p.number not in (0, 16)
                    AND (
                        al.real_period_id = %(period_id)s
                        or al.real_period_id is NULL and al.date >= %(min_date)s and al.date <= %(max_date)s
                    )
                    AND aml.period_id = %(period_id)s
                    AND am.name = al.entry_sequence
                    AND am.state = 'posted'
                    AND aml.journal_id = aj.id
                    AND j.type not in %(j_type)s
                    AND al.instance_id in %(instance_ids)s
                    AND aml.is_addendum_line = 'f'
            group by
                aml.id
            having
                abs(round(aml.credit, 2) - round(aml.debit, 2)  - sum(round(al.amount, 2))) >= 0.01
            """, {
            'instance_ids': tuple(instance_ids),
            'period_id': period_id,
            'min_date': period.date_start,
            'max_date':  period.date_stop,
            'j_type': tuple(excluded_journal_types),
        })
        for bal in cr.fetchall():
            cr.execute('''
                insert into hq_report_func_adj (account_analytic_line_id, rounded_func_amount, period_id, instance_id)
                    select
                        id,
                        round(round(amount, 2) + %s, 2),
                        real_period_id,
                        instance_id
                    from
                        account_analytic_line
                    where
                        move_id = %s and
                        real_period_id = %s and
                        id in %s
                    order by abs(amount) desc, id limit 1
            ''', (bal[1], bal[0], period_id, tuple(bal[2])))

        # pure AD
        cr.execute("""
            select
                al.move_id, sum(round(al.amount, 2)), array_agg(al.id)
            from
                account_analytic_line AS al
                inner join res_currency AS c on c.id = al.currency_id
                inner join account_analytic_journal AS j on j.id = al.journal_id
                inner join account_period p on p.id = al.real_period_id
                left join account_move_line aml on aml.id = al.move_id and aml.period_id = %(period_id)s
                left join account_move am on am.id = aml.move_id and am.name = al.entry_sequence
            where
                    p.id = al.real_period_id
                    AND p.number not in (0, 16)
                    AND al.real_period_id = %(period_id)s
                    AND j.type not in %(j_type)s
                    AND al.instance_id in %(instance_ids)s
                    AND am.id is null
                    AND aml.id is null
            group by
                al.move_id
            having
                abs(sum(round(al.amount, 2))) >= 0.01
            """, {
            'instance_ids': tuple(instance_ids),
            'period_id': period_id,
            'min_date': period.date_start,
            'max_date':  period.date_stop,
            'j_type': tuple(excluded_journal_types),
        })
        for bal in cr.fetchall():
            cr.execute('''
                insert into hq_report_func_adj (account_analytic_line_id, rounded_func_amount, period_id, instance_id)
                    select
                        id,
                        round(round(amount, 2) - %s, 2),
                        real_period_id,
                        instance_id
                    from
                        account_analytic_line
                    where
                        move_id = %s and
                        real_period_id = %s and
                        id in %s
                    order by abs(amount) desc, id offset 1 limit 1
            ''', (bal[1], bal[0], period_id, tuple(bal[2])))

        # fix rounded booking value JE
        cr.execute("""insert into hq_report_no_decimal (account_move_id, account_analytic_line_id, original_amount, rounded_amount, period_id, instance_id)
            select
                aml.move_id,
                al.id,
                -1*al.amount_currency,
                CASE WHEN al.amount_currency=0 or abs(al.amount_currency)>=1
                    THEN -1*round(al.amount_currency)
                    WHEN al.amount_currency < 0 THEN 1
                    ELSE -1 END,
                %(period_id)s,
                al.instance_id
            from
                account_analytic_line AS al,
                res_currency AS c,
                account_analytic_journal AS j,
                account_move_line aml,
                account_move am,
                account_journal AS aj,
                account_period p
            where
                    c.ocp_workday_decimal = 0
                    and c.id = al.currency_id
                    AND j.id = al.journal_id
                    AND aml.id = al.move_id
                    AND am.id = aml.move_id
                    AND p.id = am.period_id
                    AND p.number not in (0, 16)
                    AND (
                        al.real_period_id = %(period_id)s
                        or al.real_period_id is NULL and al.date >= %(min_date)s and al.date <= %(max_date)s
                    )
                    AND am.state = 'posted'
                    AND aml.journal_id = aj.id
                    AND j.type not in %(j_type)s
                    AND al.instance_id in %(instance_ids)s
                    AND aml.is_addendum_line = 'f'
            """, {
            'instance_ids': tuple(instance_ids),
            'period_id': period_id,
            'min_date': period.date_start,
            'max_date':  period.date_stop,
            'j_type': tuple(excluded_journal_types),
        })

        cr.execute("""insert into hq_report_no_decimal (account_move_id, account_move_line_id, original_amount, rounded_amount, period_id, instance_id)
            select
                m.id,
                aml.id,
                aml.debit_currency - aml.credit_currency,
                CASE WHEN aml.debit_currency - aml.credit_currency=0 OR abs(aml.debit_currency - aml.credit_currency) >= 1
                    THEN round(aml.debit_currency - aml.credit_currency)
                    WHEN aml.debit_currency - aml.credit_currency > 0 THEN 1
                    ELSE -1 END,
                %(period_id)s,
                aml.instance_id
            from
                account_move_line aml
                INNER JOIN account_move AS m ON aml.move_id = m.id
                INNER JOIN account_account AS a ON aml.account_id = a.id
                INNER JOIN res_currency AS c ON aml.currency_id = c.id
                INNER JOIN account_journal AS j ON aml.journal_id = j.id
                LEFT JOIN account_analytic_line aal ON aal.move_id = aml.id
            where
                c.ocp_workday_decimal = 0
                AND aal.id IS NULL
                AND aml.period_id = %(period_id)s
                AND j.type NOT IN %(j_type)s
                AND aml.instance_id IN %(instance_ids)s
                AND m.state = 'posted'
                AND aml.is_addendum_line = 'f'
            """, {
            'instance_ids': tuple(instance_ids),
            'period_id': period_id,
            'j_type': tuple(excluded_journal_types),
        })

        sql_params = {
            'instance_ids': tuple(instance_ids),
            'period_id': period_id,
            'min_date': period.date_start,
            'max_date':  period.date_stop,
            'j_type': tuple(excluded_journal_types),
            'period_yyymm': period_yyyymm,
            'first_day_of_period': period.date_start,
            'last_day_of_period': period.date_stop,
            'include_period_opening': tuple(include_period_opening),
            'exclude_period_closing': tuple(exclude_period_closing),
        }


        cr.execute('''
            select
                account_move_id, sum(rounded_amount)
            from
                hq_report_no_decimal d
            where
                period_id = %s and instance_id in %s
            group by account_move_id
            having(sum(d.rounded_amount)!=0 and abs(sum(d.original_amount))<0.01)
        ''', (period_id, tuple(instance_ids)))
        for x in cr.fetchall():
            # add gap on the biggest B/S line
            move_id, gap = x
            cr.execute("""
                update
                    hq_report_no_decimal d1 set rounded_amount = rounded_amount - %s 
                where
                    d1.id in (
                        select id
                        from hq_report_no_decimal d2
                        where
                            d2.account_move_id=%s and period_id = %s
                        order by
                            account_analytic_line_id is not null,
                            abs(rounded_amount) desc
                        limit 1
                )
            """, (gap, move_id, period_id))

        # end balance rounded amounts

        self.update_percent(cr, uid, 0.10)
        # analytic lines raw_data
        analytic_query = """
                SELECT
                    al.id as id, -- 0
                    i.instance as instance, -- 1
                    al.entry_sequence, -- 2
                    al.date as posting_date, -- 3
                    CASE WHEN j.code IN ('OD', 'ODHQ') THEN j.type ELSE aj.type END AS journal_type, -- 4
                    CASE WHEN al.amount_currency < 0 AND aml.is_addendum_line = 'f' THEN ABS(al.amount_currency) ELSE 0.0 END AS book_debit, -- 5
                    CASE WHEN al.amount_currency > 0 AND aml.is_addendum_line = 'f' THEN al.amount_currency ELSE 0.0 END AS book_credit, -- 6
                    c.name AS booking_currency, -- 7
                    CASE WHEN coalesce(func_rounded.rounded_func_amount, al.amount) < 0 THEN ABS(ROUND(coalesce(func_rounded.rounded_func_amount,al.amount), 2)) ELSE 0.0 END AS func_debit, -- 8
                    CASE WHEN coalesce(func_rounded.rounded_func_amount, al.amount) > 0 THEN ROUND(coalesce(func_rounded.rounded_func_amount, al.amount), 2) ELSE 0.0 END AS func_credit, -- 9
                    al.name as description, -- 10
                    al.ref, -- 11
                    al.document_date, -- 12
                    cost_center.code AS cost_center, -- 13
                    aml.partner_id, -- 14
                    aj.code as journal_code, -- 15
                    a.code as account_code, -- 16
                    hr.identification_id as emplid, -- 17
                    aml.id as account_move_line_id, -- 18
                    dest.code as destination_code, -- 19
                    c.ocp_workday_decimal = 0 as no_decimal, -- 20
                    rounded.rounded_amount as rounded_amount, -- 21
                    hr.employee_type as employee_type, -- 22
                    al.partner_txt as partner_txt -- 23
                FROM
                    account_analytic_line AS al
                        left join hq_report_no_decimal rounded on rounded.account_analytic_line_id = al.id
                        left join hq_report_func_adj func_rounded on func_rounded.account_analytic_line_id = al.id,
                    account_account AS a,
                    account_analytic_account AS dest,
                    account_analytic_account AS cost_center,
                    res_currency AS c,
                    account_analytic_journal AS j,
                    account_move_line aml
                        left outer join hr_employee hr on hr.id = aml.employee_id,
                    account_move am,
                    account_journal AS aj,
                    account_period p,
                    msf_instance AS i
                WHERE
                    dest.id = al.destination_id
                    AND cost_center.id = al.cost_center_id
                    AND a.id = al.general_account_id
                    AND c.id = al.currency_id
                    AND j.id = al.journal_id
                    AND aml.id = al.move_id
                    AND am.id = aml.move_id
                    AND p.id = am.period_id
                    AND p.number not in (0, 16)
                    AND (
                        al.real_period_id = %(period_id)s
                        or al.real_period_id is NULL and al.date >= %(min_date)s and al.date <= %(max_date)s
                    )
                    AND am.state = 'posted'
                    AND al.instance_id = i.id
                    AND aml.journal_id = aj.id
                    AND j.type not in %(j_type)s
                    AND al.instance_id in %(instance_ids)s
        """

        # B/S lines no shrink
        move_line_query = """
                SELECT
                    aml.id as id,  -- 0
                    i.instance as instance,  -- 1
                    m.name as entry_sequence, -- 2
                    aml.date as posting_date,  -- 3
                    j.type as journal_type,  -- 4
                    aml.debit_currency as book_debit,  -- 5
                    aml.credit_currency as book_credit,  -- 6
                    c.name AS booking_currency,  -- 7
                    ROUND(aml.debit, 2) as func_debit, -- 8
                    ROUND(aml.credit, 2) as func_credit,  -- 9
                    aml.name as description, -- 10
                    aml.ref,  -- 11
                    aml.document_date,  -- 12
                    '' as cost_center, -- 13
                    aml.partner_id,  -- 14
                    j.code as journal_code, -- 15
                    a.code as account_code,  -- 16
                    hr.identification_id as emplid,  -- 17
                    c.ocp_workday_decimal = 0 as no_decimal, -- 18
                    rounded.rounded_amount as rounded_amount, -- 19
                    hr.employee_type as employee_type, -- 20
                    aml.partner_txt as partner_txt
                FROM
                    account_move_line aml
                    INNER JOIN account_move AS m ON aml.move_id = m.id
                    LEFT JOIN hr_employee hr ON hr.id = aml.employee_id
                    INNER JOIN account_account AS a ON aml.account_id = a.id
                    INNER JOIN res_currency AS c ON aml.currency_id = c.id
                    INNER JOIN account_journal AS j ON aml.journal_id = j.id
                    INNER JOIN msf_instance AS i ON aml.instance_id = i.id
                    LEFT JOIN account_analytic_line aal ON aal.move_id = aml.id
                    left join hq_report_no_decimal rounded on rounded.account_move_line_id = aml.id
                WHERE
                    aal.id IS NULL
                    AND aml.period_id = %(period_id)s
                    AND a.shrink_entries_for_hq != 't'
                    AND j.type NOT IN %(j_type)s
                    AND aml.instance_id IN %(instance_ids)s
                    AND m.state = 'posted'
                ORDER BY
                    aml.id
        """

        col_header = [
            'DB-ID',
            'Instance',
            'Entry Sequence',
            'Valeur fixe',
            'Func. Currency',
            'Posting date',
            'Journal Type',
            'Booking Debit',
            'Booking Credit',
            'Booking Debit Arrondi',
            'Booking Credit Arrondi',
            'Ecart',
            'Book. Currency',
            'Func. Debit',
            'Func. Credit',
            'Description',
            'Reference',
            'Document Date',
            'Cost Center',
            'Partner DB ID',
            'Journal_PCash',
            'Journal_BBank',
            'G/L Account',
            'EMPLID',
            'Code-Mission',
            'Destination',
            'Debit/Credit EUR Budget Rate',
            'Third party text',
        ]

        lines_file = tempfile.NamedTemporaryFile('w', delete=False, newline='')
        lines_file_name = lines_file.name
        writer = csv.writer(lines_file, quoting=csv.QUOTE_ALL, delimiter=",")
        writer.writerow(col_header)

        if debug:
            tot_book = 0
            tot_book_round = 0
            tot_func = 0
            all_tot = {}

        for sql, obj in [
                (analytic_query, 'account.analytic.line'),
                (move_line_query, 'account.move.line')]:
            cr.execute(sql, sql_params)
            while True:
                ajis = set()
                amls = set()
                rows = cr.dictfetchmany(500)
                if not rows:
                    break
                for row in rows:
                    if obj == 'account.analytic.line':
                        ajis.add(row['id'])
                        amls.add(row['account_move_line_id'])
                        #if row[15] == 'ODHQ':
                        #    aal = aal_obj.browse(cr, uid, row[0], fields_to_fetch=['last_corrected_id', 'reversal_origin'])
                        #    cor_or_rev = aal.last_corrected_id or aal.reversal_origin
                        #    while cor_or_rev:
                        #        cor_or_rev = last_corrected_id
                        #    if cor_or_rev and cor_or_rev.journal_id.type == 'hq':
                        #        original_ref = cor_or_rev.ref or ''
                        #        seq = original_ref.startswith('EAUD') and 'EAUD' or 'SIEG'
                        #        journal = original_ref[8:11] or ''

                    else:
                        amls.add(row['id'])

                    local_employee = row['employee_type'] and row['employee_type'] != 'ex'

                    if row['no_decimal'] and (row['book_credit'] or row['book_debit']):
                        book_debit_round = 0
                        book_credit_round = 0
                        if row['rounded_amount'] > 0:
                            book_debit_round = row['rounded_amount']
                        else:
                            book_credit_round = abs(row['rounded_amount'])

                        ecart = round( (book_credit_round - book_debit_round) - (row['book_credit'] - row['book_debit']), 2)
                    else:
                        book_debit_round = row['book_debit']
                        book_credit_round = row['book_credit']
                        ecart = 0

                    if debug:
                        if row['entry_sequence'] not in all_tot:
                            all_tot[row['entry_sequence']] = {'book': 0, 'book_round': 0, 'func': 0}

                        all_tot[row['entry_sequence']]['book'] += row['book_credit'] - row['book_debit']
                        all_tot[row['entry_sequence']]['book_round'] += book_credit_round - book_debit_round
                        all_tot[row['entry_sequence']]['func'] += row['func_credit'] - row['func_debit']
                        tot_book = tot_book + row['book_credit'] - row['book_debit']
                        tot_book_round = tot_book_round + book_credit_round - book_debit_round
                        tot_func = tot_func + row['func_credit'] - row['func_debit']
                    budget_amount = row['book_credit'] - row['book_debit']
                    if fx_budget_rate.get(row['booking_currency']):
                        budget_amount = round(budget_amount / fx_budget_rate.get(row['booking_currency']), 2)

                    writer.writerow([
                        finance_archive._get_hash(new_cr, uid, ids='%s'%row['id'], model=obj), # DB-ID
                        row['instance'], # Instance
                        row['entry_sequence'], # Entry Sequence
                        'Company_Reference_ID', # Valeur fixe
                        'EUR', # Func. Currency
                        datetime.strptime(row['posting_date'], '%Y-%m-%d').strftime('%d/%m/%Y'), # Posting date
                        journal_type.get(row['journal_type'], row['journal_type']), # Journal Type
                        row['book_debit'], # Booking Debit
                        row['book_credit'], # Booking Credit
                        book_debit_round,
                        book_credit_round,
                        ecart,
                        row['booking_currency'], # Book. Currency
                        row['func_debit'], # Func. Debit
                        row['func_credit'], # Func. Credit
                        row['description'], # Description
                        row['ref'], # Reference
                        datetime.strptime(row['document_date'], '%Y-%m-%d').strftime('%d/%m/%Y'), # Document Date
                        row['cost_center'] or '',# Cost Center
                        local_employee and row['emplid'] or row['partner_id'] or '', # Partner DB ID
                        row['journal_code'] if row['journal_type'] == 'cash' else '', # Journal Cash
                        row['journal_code'] if row['journal_type'] in ('bank', 'cheque') else '', # Journal Cash
                        row['account_code'], # G/L Account,
                        not local_employee and row['emplid'] or '', # EMPLID
                        row['entry_sequence'][0:3], # 3 digits seq.
                        row.get('destination_code') or '',
                        budget_amount,
                        row.get('partner_txt') or '',
                    ])
                if ajis:
                    new_cr.execute("update account_analytic_line set exported='t' where id in %s", (tuple(ajis), ))
                if amls:
                    new_cr.execute("update account_move_line set exported='t' where id in %s", (tuple(amls), ))

                self.update_percent(new_cr, uid, 0.45)

        self.update_percent(cr, uid, 0.80)

        # B/S lines consolidated
        cr.execute("""
                SELECT
                    array_agg(aml.id ORDER BY aml.id) AS concat,  -- 0
                    i.instance, -- 1
                    j.code || '-' || p.code || '-' || f.code || '-' || a.code || '-' || c.name AS entry_sequence,  -- 2
                    p.date_stop AS posting_date, -- 3
                    j.type,  -- 4
                    SUM(aml.amount_currency) as book_amount, -- 5
                    c.name AS "booking_currency", -- 6
                    SUM(aml.debit - aml.credit) as func_amount, -- 7
                    'Automated counterpart - ' || j.code || '-' || a.code || '-' || p.code || '-' || f.code AS description,  -- 8
                    p.date_stop AS document_date,  -- 9
                    j.code as journal_code,  -- 10
                    a.code as account_code, -- 11
                    i.code as instance_code, -- 12
                    c.ocp_workday_decimal = 0 as no_decimal, -- 13
                    sum(coalesce(rounded.rounded_amount, aml.amount_currency)) -- 14
                FROM
                    account_move_line aml
                    LEFT JOIN hq_report_no_decimal rounded on rounded.account_move_line_id = aml.id
                    INNER JOIN account_move AS m ON aml.move_id = m.id
                    INNER JOIN account_account AS a ON aml.account_id = a.id
                    INNER JOIN res_currency AS c ON aml.currency_id = c.id
                    INNER JOIN account_journal AS j ON aml.journal_id = j.id
                    INNER JOIN msf_instance AS i ON aml.instance_id = i.id
                    LEFT JOIN account_analytic_line aal ON aal.move_id = aml.id
                    INNER JOIN account_period p ON p.id = aml.period_id
                    INNER JOIN account_fiscalyear f ON f.id = p.fiscalyear_id
                WHERE
                    aal.id IS NULL
                    AND aml.period_id = %(period_id)s
                    AND a.shrink_entries_for_hq = 't'
                    AND j.type NOT IN %(j_type)s
                    AND aml.instance_id IN %(instance_ids)s
                    AND m.state = 'posted'
                GROUP BY
                    i.instance,
                    i.code,
                    j.code,
                    p.code,
                    f.code,
                    a.code,
                    c.name,
                    p.date_stop,
                    j.type,
                    p.date_stop,
                    c.ocp_workday_decimal
        """, sql_params)
        while True:
            rows = cr.fetchmany(500)
            if not rows:
                break
            amls = set()
            for row in rows:
                amls.update(row[0])
                if row[13]:
                    amount_currency_round = row[14]
                    if row[5] > 0 and not amount_currency_round:
                        amount_currency_round = 1
                    elif row[5] < 0 and not amount_currency_round:
                        amount_currency_round = -1
                    ecart =  round(amount_currency_round - row[5], 2)
                else:
                    amount_currency_round = row[5]
                    ecart = 0

                budget_amount = row[5]
                if fx_budget_rate.get(row[6]):
                    budget_amount = round(budget_amount / fx_budget_rate.get(row[6]), 2)

                writer.writerow([
                    finance_archive._get_hash(new_cr, uid, ids=row[0], model='account.move.line'), # DB-ID
                    row[1], # Instance
                    row[2], # Entry Sequence
                    'Company_Reference_ID', # Valeur fixe
                    'EUR', # Func. Currency
                    row[3], # Posting date
                    journal_type.get(row[4], row[4]), # Journal Type
                    -1*row[5] if row[5] < 0 else 0, # Booking Debit
                    row[5] if row[5] > 0 else 0, # Booking Credit
                    -1*amount_currency_round if row[5] < 0 else 0,
                    amount_currency_round if row[5] > 0 else 0,
                    ecart,
                    row[6], # Book. Currency
                    -1 * row[7] if row[7] < 0 else 0, # Func. Debit
                    row[7] if row[7] > 0 else 0, # Func. Credit
                    row[8], # Description
                    '', # Reference
                    '',# Cost Center
                    '', # Partner DB ID
                    row[10] if row[4] == 'cash' else '', # Journal Cash
                    row[10] if row[4] in ('bank', 'cheque') else '', # Journal Cash
                    row[11], # G/L Account,
                    '', # EMPLID
                    row[12][0:3], # 3 digits seq
                    budget_amount,
                    '',
                ])
            if amls:
                new_cr.execute("update account_move_line set exported='t' where id in %s", (tuple(amls),))

        self.update_percent(cr, uid, 0.90)

        lines_file.close()

        balances_file = tempfile.NamedTemporaryFile('w', delete=False, newline='')
        balances_file_name = balances_file.name
        writer = csv.writer(balances_file, quoting=csv.QUOTE_ALL, delimiter=",")
        writer.writerow([
            'Instance', 'Account', 'Account Name', 'Period', 'Booking Currency',
            'Starting balance', 'Calculated balance', 'Closing balance',
            'Starting balance in EUR', 'Calculated balance in EUR', 'Closing balance in EUR'
        ])

        cr.execute(account_balances_per_currency_with_euro_sql, sql_params)
        while True:
            rows = cr.fetchmany(500)
            if not rows:
                break
            for row in rows:
                writer.writerow(row)
        balances_file.close()
        self.update_percent(cr, uid, 0.75)

        if data.get('output_file'):
            tmpzipname = data['output_file']
        else:
            null1, tmpzipname = tempfile.mkstemp()
        zf = zipfile.ZipFile(tmpzipname, 'w')

        if all_missions:
            prefix = 'Allinstances'
        elif instance_id:
            inst = mi_obj.browse(cr, uid, instance_id, context=context, fields_to_fetch=['code'])
            prefix = inst and inst.code[:3] or ''
        else:
            prefix = ''
        if debug:
            logger.warn('=========== %s %s %s %s %s' % (inst.code[:3], period_yyyymm, round(tot_book,2), round(tot_book_round, 2), round(tot_func, 2)))
            if round(tot_book,2) != 0 or  round(tot_book_round, 2) != 0 or round(tot_func, 2) != 0:
                for entr_seq in all_tot:
                    if abs(all_tot[entr_seq]['book']) > 0.001 or abs(all_tot[entr_seq]['book_round']) > 0.001 or abs(all_tot[entr_seq]['func']) > 0.001:
                        logger.warn('%s %r' % (entr_seq, all_tot[entr_seq]))
        selected_period = strftime('%Y%m', strptime(first_day_of_period, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        lines_file_zip_name = '%s_%s_%s_Monthly_Export.csv' % (prefix, period_yyyymm, current_time)
        balances_file_zip_name = '%s_%s_%s_Account_Balances.csv' % (prefix, selected_period, current_time)
        zf.write(lines_file_name, lines_file_zip_name)
        zf.write(balances_file_name, balances_file_zip_name)
        zf.close()

        if not data.get('output_file'):
            os.close(null1)

        new_cr.commit()
        new_cr.close(True)
        return (Path(tmpzipname, delete=True), 'zip')



hq_report_ocp_workday('report.hq.ocp.workday', 'account.move.line', False, parser=False)
