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
import hq_report_ocb

from report import report_sxw


class finance_archive(finance_export.finance_archive):
    """
    Extend existing class with new methods for this particular export.
    """

    def _get_journal_type_value(self, cr, uid, journal_type_key):
        """
        Returns the value of the Journal Type corresponding to the key in parameter (ex: inkind => In-kind Donation...)
        If no corresponding value is found, returns the key.
        """
        pool = pooler.get_pool(cr.dbname)
        journal_obj = pool.get('account.journal')
        journal_type_list = journal_obj.fields_get(cr, uid)['type']['selection']
        return journal_type_key in dict(journal_type_list) and dict(journal_type_list)[journal_type_key] or journal_type_key

    def _handle_od_ji_entries(self, cr, uid, data):
        """
        Takes data in parameter corresponding to ACCOUNT MOVE LINES (results from 'bs_entries' or 'plresult' requests)
        1) Replaces the journal type "key" by its corresponding "value" (ex: inkind => In-kind Donation)
        2) Modifies it for all OD entries that originate from HQ entry corrections:
        - instance: becomes 'SIEG'
        - journal: for the journal name, the description field is used: we take the 3 digits starting from the 11th one
        Returns a list of tuples (same format as data)
        """
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        aml_obj = pool.get('account.move.line')
        # column numbers corresponding to properties
        id_from_db = 0  # this has to correspond to the real id from the DB and not the new id displayed in the file
        instance_code = 1
        journal = 2
        description = 4
        journal_type = 22
        for line in data:
            line_list = list(line)
            line_list[journal_type] = self._get_journal_type_value(cr, uid, line_list[journal_type])
            od_hq_entry = False
            if line_list[journal] == 'OD':
                aml = aml_obj.browse(cr, uid, line_list[id_from_db], fields_to_fetch=['corrected_line_id', 'reversal_line_id'])
                corrected_aml = aml.corrected_line_id
                reversed_aml = aml.reversal_line_id
                if corrected_aml and corrected_aml.journal_id.type == 'hq' or False:
                    # COR entries
                    od_hq_entry = True
                elif reversed_aml and reversed_aml.journal_id.type == 'hq' or False:
                    # REV entries
                    od_hq_entry = True
                if od_hq_entry:
                    line_list[instance_code] = 'SIEG'
                    # for the 3 characters of the journal name taken from the 11th character of the description field:
                    # exclude the "COR1 - " or "REV - " part
                    line_list[journal] = ' - ' in line_list[description] and line_list[description].split(' - ')[1][10:13] or ''
            new_data.append(tuple(line_list))
        return new_data

    def _handle_od_aji_entries(self, cr, uid, data):
        """
        Takes data in parameter corresponding to ACCOUNT ANALYTIC LINES (results from 'rawdata' request)
        1) Replaces the journal type "key" by its corresponding "value" (ex: inkind => In-kind Donation)
        2) Modifies it for all OD entries that originate from HQ entry corrections:
        - instance: becomes 'SIEG'
        - journal: for the journal name, the description field is used: we take the 3 digits starting from the 11th one
        Returns a list of tuples (same format as data)
        """
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        aal_obj = pool.get('account.analytic.line')
        # column numbers corresponding to properties
        id_from_db = 0  # this has to correspond to the real id from the DB and not the new id displayed in the file
        instance_code = 1
        journal = 2
        description = 4
        journal_type = 22
        for line in data:
            line_list = list(line)
            line_list[journal_type] = self._get_journal_type_value(cr, uid, line_list[journal_type])
            od_hq_entry = False
            if line_list[journal] == 'OD':
                aal = aal_obj.browse(cr, uid, line_list[id_from_db], fields_to_fetch=['last_corrected_id', 'reversal_origin'])
                corrected_aal = aal.last_corrected_id
                reversed_aal = aal.reversal_origin
                if corrected_aal and corrected_aal.journal_id.type == 'hq' or False:
                    # COR entries
                    od_hq_entry = True
                elif reversed_aal and reversed_aal.journal_id.type == 'hq' or False:
                    # REV entries
                    od_hq_entry = True
                if od_hq_entry:
                    line_list[instance_code] = 'SIEG'
                    # for the 3 characters of the journal name taken from the 11th character of the description field:
                    # exclude the "COR1 - " or "REV - " part
                    line_list[journal] = ' - ' in line_list[description] and line_list[description].split(' - ')[1][10:13] or ''
            new_data.append(tuple(line_list))
        return new_data

    def postprocess_ji_entries(self, cr, uid, data, model, column_deletion=False):
        """
        ##### WARNING #####
        ### THIS CALLS THE METHOD postprocess_add_db_id FROM OCB ###
        - first modify the data for all lines corresponding to OD entries originating from HQ entry corrections
        - then call OCB method on the new data to change first column for the DB ID
        """
        new_data = self._handle_od_ji_entries(cr, uid, data)  # we handle account move lines
        finance_archive_ocb = hq_report_ocb.finance_archive(self.sqlrequests, self.processrequests)
        return finance_archive_ocb.postprocess_add_db_id(cr, uid, new_data, model, column_deletion)

    def postprocess_aji_entries(self, cr, uid, data, model, column_deletion=False):
        """
        ##### WARNING #####
        ### THIS CALLS THE METHOD postprocess_add_db_id FROM OCB ###
        - first modify the data for all lines corresponding to OD entries originating from HQ entry corrections
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
            # Replaces the journal type "key" by its corresponding "value" (ex: inkind => In-kind Donation)
            line[journal_type_col] = self._get_journal_type_value(cr, uid, line[journal_type_col])
        return new_data


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
        excluded_journal_types = ['hq', 'cur_adj']  # journal types that should not be used to take lines
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
        period = pool.get('account.period').browse(cr, uid, period_id, context=context,
                                                   fields_to_fetch=['date_start', 'date_stop', 'number'])
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
            # Pay attention to take analytic lines that are not on HQ, MIGRATION and FXA journals.
            'rawdata': """
                SELECT al.id, SUBSTR(i.code, 1, 3),
                       CASE WHEN j.code = 'OD' THEN j.code ELSE aj.code END AS journal,
                       al.entry_sequence, al.name, al.ref, al.document_date, al.date,
                       a.code, al.partner_txt, aa.code AS dest, aa2.code AS cost_center_id, aa3.code AS funding_pool, 
                       CASE WHEN al.amount_currency < 0 AND aml.is_addendum_line = 'f' THEN ABS(al.amount_currency) ELSE 0.0 END AS debit, 
                       CASE WHEN al.amount_currency > 0 AND aml.is_addendum_line = 'f' THEN al.amount_currency ELSE 0.0 END AS credit, 
                       c.name AS "booking_currency", 
                       CASE WHEN al.amount < 0 THEN ABS(ROUND(al.amount, 2)) ELSE 0.0 END AS debit, 
                       CASE WHEN al.amount > 0 THEN ROUND(al.amount, 2) ELSE 0.0 END AS credit,
                       cc.name AS "functional_currency", hr.identification_id as "emplid", aml.partner_id, hr.name_resource as hr_name,
                       CASE WHEN j.code = 'OD' THEN j.type ELSE aj.type END AS journal_type
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
            # Exclude lines that come from a HQ, MIGRATION or FXA journal
            # Take all lines that are on account that is "shrink_entries_for_hq" which will make a consolidation of them (with a second SQL request)
            # The subrequest enables to disallow lines that have analytic lines. This is to not retrieve expense/income accounts
            'bs_entries_consolidated': """
                SELECT aml.id
                FROM account_move_line AS aml, account_account AS aa, account_journal AS j
                WHERE aml.period_id = %s
                AND aml.account_id = aa.id
                AND aml.journal_id = j.id
                AND j.type not in %s
                AND aa.shrink_entries_for_hq = 't'
                AND aml.id not in (SELECT amla.id FROM account_move_line amla, account_analytic_line al WHERE al.move_id = amla.id)
                AND aml.instance_id in %s;
                """,
            # Do not take lines that come from a HQ or MIGRATION journal
            # Do not take journal items that have analytic lines because they are taken from "rawdata" SQL request
            # For these entries instead of the "Cost centre" we take the same value as in the "Instance" column
            'bs_entries': """
                SELECT aml.id, SUBSTR(i.code, 1, 3), j.code, m.name as "entry_sequence", aml.name, aml.ref, aml.document_date, aml.date,
                       a.code, aml.partner_txt, '', SUBSTR(i.code, 1, 3), '', aml.debit_currency, aml.credit_currency, c.name,
                       ROUND(aml.debit, 2), ROUND(aml.credit, 2), cc.name, hr.identification_id as "Emplid", aml.partner_id,
                       hr.name_resource as hr_name, j.type
                FROM account_move_line aml left outer join hr_employee hr on hr.id = aml.employee_id, 
                     account_account AS a, 
                     res_currency AS c, 
                     account_move AS m, 
                     res_company AS e, 
                     account_journal AS j, 
                     res_currency AS cc, 
                     msf_instance AS i
                WHERE aml.account_id = a.id
                AND aml.id not in (
                  SELECT amla.id
                  FROM account_analytic_line al, account_move_line amla
                  WHERE al.move_id = amla.id
                )
                AND aml.move_id = m.id
                AND aml.currency_id = c.id
                AND aml.company_id = e.id
                AND aml.journal_id = j.id
                AND e.currency_id = cc.id
                AND aml.instance_id = i.id
                AND aml.period_id = %s
                AND a.shrink_entries_for_hq != 't'
                AND j.type not in %s
                AND aml.instance_id in %s
                AND m.state = 'posted'
                ORDER BY aml.id;
                """,
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
        # First3DigitsOfInstanceCode_chosenPeriod_currentDatetime_Monthly Export.csv (ex: KE1_201609_171116110306_Monthly Export.csv)
        inst = mi_obj.browse(cr, uid, instance_id, context=context, fields_to_fetch=['code'])
        instance_code = inst and inst.code[:3] or ''
        selected_period = strftime('%Y%m', strptime(first_day_of_period, '%Y-%m-%d')) or ''
        current_time = time.strftime('%d%m%y%H%M%S')
        monthly_export_filename = '%s_%s_%s_Monthly Export.csv' % (instance_code, selected_period, current_time)

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
        fe = finance_archive(sqlrequests, processrequests)
        # Use archive method to create the archive
        return fe.archive(cr, uid)

hq_report_ocp('report.hq.ocp', 'account.move.line', False, parser=False)
