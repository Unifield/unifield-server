# -*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
import csv
import StringIO
import pooler
import zipfile
from tempfile import NamedTemporaryFile
import os

from report import report_sxw

class hq_report_ocb(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def get_selection(self, cr, model, field):
        """
        Return a list of all selection from a field in a given model.
        """
        pool = pooler.get_pool(cr.dbname)
        data = pool.get(model).fields_get(cr, 1, [field])
        return dict(data[field]['selection'])

    def postprocess_register(self, cr, uid, data):
        """
        Replace statement id by its field 'msf_calculated_balance'. If register is closed, then display balance_end_real content.
        Also launch postprocess_selection_columns on these data to change state column value.
        """
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
        new_data = []
        for line in data:
            tmp_line = list(line)
            st_id = line[4]
            state = line[6]
            if state != 'closed':
                tmp_line[4] = pool.get('account.bank.statement').read(cr, uid, [st_id], ['msf_calculated_balance'])[0].get('msf_calculated_balance', 0.0)
            else:
                tmp_line[4] = line[5]
            new_data.append(tmp_line)
        return self.postprocess_selection_columns(cr, uid, new_data, [('account.bank.statement', 'state', 6)])

    def postprocess_add_period(self, cr, uid, data, period_name):
        """
        This method takes each line from data and add period at end of line.
        """
        # Checks
        if not period_name:
            return data
        # Prepare some values
        new_data = []
        # Browse lines and add period_name at the end
        for line in data:
            tmp_line = list(line)
            tmp_line.append(period_name)
            new_data.append(tmp_line)
        return new_data

    def postprocess_selection_columns(self, cr, uid, data, changes):
        """
        This method takes each line from data and change some columns regarding "changes" variable.
        'changes' should be a list containing some tuples. A tuple is composed of:
         - a model (example: res.partner)
         - the selection field in which retrieve all real values (example: partner_type)
         - the column number in the data lines from which you want to change the value
        """
        # Checks
        if not changes:
            return data
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
        new_data = []
        # Fetch selections
        changes_values = {}
        for change in changes:
            model = change[0]
            field = change[1]
            changes_values[change] = self.get_selection(cr, model, field)
        # Browse each line to replace partner type by it's human readable value (selection)
        # partner_type is the 3rd column
        for line in data:
            tmp_line = list(line)
            for change in changes:
                column = change[2]
                # use line value to search into changes_values[change] (the list of selection) the right value
                tmp_line[column] = changes_values[change][tmp_line[column]]
            new_data.append(tmp_line)
        return new_data

    def create(self, cr, uid, ids, data, context=None):
        """
        Create a kind of report and return its content.
        The content is composed of:
         - 3rd parties list (partners)
         - Employees list
         - Journals
         - Cost Centers
         - FX Rates
         - Liquidity balances
         - Financing Contracts
         - Raw data (a kind of synthesis of funding pool analytic lines)
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
        # Fetch data from wizard
        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))
        form = data.get('form')
        fy_id = form.get('fiscalyear_id', False)
        period_id = form.get('period_id', False)
        instance_ids = form.get('instance_ids', False)
        if not fy_id or not period_id or not instance_ids:
            raise osv.except_osv(_('Warning'), _('Some info are missing. Either fiscalyear or period or instance.'))
        period = pool.get('account.period').browse(cr, uid, period_id)
        last_day_of_period = period.date_stop
        first_day_of_period = period.date_start
        period_name = period.name
        # open buffer for result zipfile
        zip_buffer = StringIO.StringIO()

        # SQLREQUESTS DICTIONNARY
        # - key: name of the SQL request
        # - value: the SQL request to use
        sqlrequests = {
            'partner': """
                SELECT name, ref, partner_type, CASE WHEN active='t' THEN 'True' WHEN active='f' THEN 'False' END AS active
                FROM res_partner;
                """,
            'employee': """
                SELECT r.name, e.identification_id, r.active, e.employee_type
                FROM hr_employee AS e, resource_resource AS r
                WHERE e.resource_id = r.id;
                """,
            'journal': """
                SELECT i.name, j.code, j.name, j.type
                FROM account_journal AS j, msf_instance AS i
                WHERE j.instance_id = i.id;
                """,
            'costcenter': """
                SELECT name, code, type, date_start, date, CASE WHEN date_start < %s AND (date IS NULL OR date > %s) THEN 'Active' ELSE 'Inactive' END AS Status
                FROM account_analytic_account
                WHERE category = 'OC'
                AND id in (
                    SELECT cost_center_id
                    FROM account_target_costcenter
                    WHERE instance_id in %s
                );
                """,
            'fxrate': """
                SELECT c.currency_name, c.name, r.rate
                FROM res_currency AS c
                LEFT JOIN res_currency_rate r ON r.currency_id = c.id AND r.id IN (
                    SELECT dd.id
                    FROM res_currency_rate dd
                    WHERE dd.currency_id = c.id
                    AND dd.name <= %s
                    AND dd.name >= %s
                    ORDER BY dd.name ASC LIMIT 1
                )
                ORDER BY c.name;
                """,
            'register': """
                SELECT i.name as instance, st.name, p.name as period, st.balance_start, st.id, CASE WHEN st.balance_end_real IS NOT NULL THEN st.balance_end_real ELSE 0.0 END as balance_end_real, st.state, st.journal_id
                FROM account_bank_statement AS st, msf_instance AS i, account_period AS p
                WHERE st.instance_id = i.id
                AND st.period_id = p.id
                ORDER BY st.name, p.number;
                """,
            'contract': """
                SELECT c.name, c.code, d.code, c.grant_amount, rc.name, c.state
                FROM financing_contract_contract AS c, financing_contract_donor AS d, res_currency AS rc
                WHERE c.donor_id = d.id
                AND c.reporting_currency = rc.id;
                """,
            'rawdata': """
                SELECT al.entry_sequence, al.name, al.ref, al.document_date, al.date, a.code, al.partner_txt, aa.code AS dest, aa2.code AS cost_center_id, aa3.code AS funding_pool, CASE WHEN al.amount_currency > 0 THEN al.amount_currency ELSE 0.0 END AS debit, CASE WHEN al.amount_currency < 0 THEN ABS(al.amount_currency) ELSE 0.0 END AS credit, c.name AS "booking_currency", CASE WHEN al.amount > 0 THEN al.amount ELSE 0.0 END AS debit, CASE WHEN al.amount < 0 THEN ABS(al.amount) ELSE 0.0 END AS credit, cc.name AS "functional_currency"
                FROM account_analytic_line AS al, account_account AS a, account_analytic_account AS aa, account_analytic_account AS aa2, account_analytic_account AS aa3, res_currency AS c, res_company AS e, res_currency AS cc
                WHERE al.destination_id = aa.id
                AND al.cost_center_id = aa2.id
                AND al.account_id = aa3.id
                AND al.general_account_id = a.id
                AND al.currency_id = c.id
                AND aa3.category = 'FUNDING'
                AND al.company_id = e.id
                AND e.currency_id = cc.id;
                """,
            'bs_entries_consolidated': """
                SELECT j.code || '-' || p.code || '-' || f.code || '-' || a.code || '-' || c.name AS entry_sequence, 'Automated counterpart - ' || j.code || '-' || a.code || '-' || p.code || '-' || f.code AS "desc", '' AS "ref", '' AS "document_date", '' AS "date", a.code AS "account", '' AS "partner_txt", '' AS "dest", '' AS "cost_center", '' AS "funding_pool", CASE WHEN req.total > 0 THEN req.total ELSE 0.0 END as debit, CASE WHEN req.total < 0 THEN ABS(req.total) ELSE 0.0 END as credit, c.name AS "booking_currency"
                FROM (
                    SELECT aml.account_id, aml.journal_id, aml.currency_id, SUM(aml.amount_currency) AS total, aml.period_id
                    FROM account_move_line AS aml, account_account AS aa
                    WHERE aml.period_id = %s
                    AND aml.account_id = aa.id
                    AND aa.type = 'liquidity'
                    AND aa.ocb_export_subtotal = 't'
                    GROUP BY aml.period_id, aml.account_id, aml.journal_id, aml.currency_id
                    ORDER BY aml.account_id
                ) AS req, account_account AS a, account_journal AS j, res_currency AS c, account_period AS p, account_fiscalyear AS f
                WHERE req.account_id = a.id
                AND req.journal_id = j.id
                AND req.currency_id = c.id
                AND req.period_id = p.id
                AND p.fiscalyear_id = f.id
                AND a.type = 'liquidity'
                AND a.ocb_export_subtotal = 't'
                ORDER BY a.code;
                """,
            'bs_entries': """
                SELECT m.name AS "entry_sequence", aml.name AS "desc", aml.ref, aml.document_date, aml.date, a.code AS "account", aml.partner_txt, '' AS "dest", '' AS "cost_center", '' AS "funding_pool", aml.debit_currency, aml.credit_currency, c.name AS "booking_currency", aml.debit, aml.credit, cc.name AS "functional_currency"
                FROM account_move_line AS aml, account_account AS a, res_currency AS c, account_move AS m, res_company AS e, res_currency AS cc
                WHERE aml.period_id = %s
                AND a.type = 'liquidity'
                AND a.ocb_export_subtotal = 'f'
                AND aml.account_id = a.id
                AND aml.currency_id = c.id
                AND aml.move_id = m.id
                AND aml.company_id = e.id
                AND e.currency_id = cc.id;
                """,
        }

        # PROCESS REQUESTS LIST: list of dict containing info to process some SQL requests
        # Dict:
        # - filename: the name of the result filename in the future ZIP file
        # - key: the name of the key in SQLREQUESTS DICTIONNARY to have the right SQL request
        # - [optional] query_params: data to use to complete SQL requests
        # - [optional] function: name of the function to postprocess data (example: to change selection field into a human readable text)
        # - [optional] fnct_params: params that would used on the given function
        processrequests = [
            {
                'filename': 'partners.csv',
                'key': 'partner',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('res.partner', 'partner_type', 2)],
                },
            {
                'filename': 'employees.csv',
                'key': 'employee',
                },
            {
                'filename': 'journals.csv',
                'key': 'journal',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('account.journal', 'type', 3)],
                },
            {
                'filename': 'cost_centers.csv',
                'key': 'costcenter',
                'query_params': (last_day_of_period, last_day_of_period, tuple(instance_ids)),
                'function': 'postprocess_selection_columns',
                'fnct_params': [('account.analytic.account', 'type', 2)],
                },
            {
                'filename': 'fxrates.csv',
                'key': 'fxrate',
                'query_params': (last_day_of_period, first_day_of_period),
                'function': 'postprocess_add_period',
                'fnct_params': period_name,
                },
            {
                'filename': 'liquidities.csv',
                'key': 'register',
                'function': 'postprocess_register',
                },
            {
                'filename': 'contacts.csv',
                'key': 'contract',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('financing.contract.contract', 'state', 5)],
                },
            {
                'filename': 'Raw_Data.csv',
                'key': 'rawdata',
                },
            {
                'filename': 'BS_Entries_consolidated.csv',
                'key': 'bs_entries_consolidated',
                'query_params': ([period.id]),
                },
            {
                'filename': 'BS_Entries.csv',
                'key': 'bs_entries',
                'query_params': ([period.id]),
                },
        ]

        # List is composed of a tuple containing:
        # - filename
        # - key of sqlrequests dict to fetch its SQL request
        files = []
        for fileparams in processrequests:
            if not fileparams.get('filename', False):
                raise osv.except_osv(_('Error'), _('Filename param is missing!'))
            if not fileparams.get('key', False):
                raise osv.except_osv(_('Error'), _('Key param is missing!'))
            # temporary file
            filename = fileparams['filename']
            tmp_file = NamedTemporaryFile('w+b', delete=False)

            # fetch data with given sql query
            sql = sqlrequests[fileparams['key']]
            if fileparams.get('query_params', False):
                cr.execute(sql, fileparams['query_params'])
            else:
                cr.execute(sql)
            fileres = cr.fetchall()
            # Check if a function is given. If yes, use it
            if fileparams.get('function', False):
                fnct = getattr(self, fileparams['function'], False)
                # If the function has some params, use them.
                if fnct and fileparams.get('fnct_params', False):
                    fileres = fnct(cr, uid, fileres, fileparams['fnct_params'])
                elif fnct:
                    fileres = fnct(cr, uid, fileres)
            # Change to UTF-8 all elements
            newlines = []
            for line in fileres:
                newline = []
                for element in line:
                    if type(element) == unicode:
                        newline.append(element.encode('utf-8'))
                    else:
                        newline.append(element)
                newlines.append(newline)
            # Write result in a CSV writer then close it.
            writer = csv.writer(tmp_file, quoting=csv.QUOTE_ALL)
            writer.writerows(newlines)
            tmp_file.close()
            files.append((tmp_file.name, filename))

        # WRITE RESULT INTO AN ARCHIVE
        # Create a ZIP file
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        for tmp_filename, filename in files:
            out_zipfile.write(tmp_filename, filename, zipfile.ZIP_DEFLATED)
            # unlink file
            os.unlink(tmp_filename)
        # close zip
        out_zipfile.close()
        out = zip_buffer.getvalue()
        # Return result
        return (out, 'zip')

hq_report_ocb('report.hq.ocb', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
