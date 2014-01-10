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
import pooler

from account_tools import finance_export

from report import report_sxw

class finance_archive(finance_export.finance_archive):
    """
    Extend existing class with new methods for this particular export.
    """

    def postprocess_add_functional(self, cr, uid, data, changes, column_deletion=False):
        """
        Change each line of 'data' to add some amount in another currency.
        'changes' is a dict containing:
         - currency: the column number containing the currency_id
         - columns: the columns to change into another amount
         - date: the date to use to do amount processing
        """
        # Checks
        if not changes or not changes.get('currency', False) or not changes.get('columns', False) or not changes.get('date', False):
            return data
        # Prepare some values
        pool = pooler.get_pool(cr.dbname)
        new_data = []
        company_currency = pool.get('res.users').browse(cr, uid, uid).company_id.currency_id
        date = changes.get('date')
        columns = changes.get('columns')
        context = {'date': date}
        currency = changes.get('currency')
        for line in data:
            tmp_line = list(line[:-1])
            # Add new columns
            for col in sorted(columns):
                new_amount = pool.get('res.currency').compute(cr, uid, line[currency], company_currency.id, line[col], round=False, context=context)
                tmp_line.append(new_amount)
            # Add company currency
            tmp_line.append(company_currency.name)
            # Delete useless columns
            if column_deletion:
                tmp_line = self.delete_x_column(tmp_line, column_deletion)
            # Convert to UTF-8
            tmp_line = self.line_to_utf8(tmp_line)
            # write changes
            new_data.append(tmp_line)
        return new_data

    def postprocess_consolidated_entries(self, cr, uid, data, date, column_deletion=False):
        """
        Use current SQL result (data) to fetch IDs and mark lines as used.
        Then do another request.
        Finally mark lines as exported.

        Data is a list of tuples.
        """
        # Checks
        if not date:
            raise osv.except_osv(_('Warning'), _('Need a date for next SQL request.'))
        # Prepare some values
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        ids = [x and x[0] for x in data]
        # In case where no line to return, abort process and return empty data
        if not ids:
            return new_data
        # Create new export sequence
        seq = pool.get('ir.sequence').get(cr, uid, 'finance.ocb.export')
        # Mark lines as used
        sqlmark = """UPDATE account_move_line SET exporting_sequence = %s WHERE id in %s;"""
        cr.execute(sqlmark, (seq, tuple(ids),))
        # Do right request
        sqltwo = """SELECT j.code || '-' || p.code || '-' || f.code || '-' || a.code || '-' || c.name AS "entry_sequence", 'Automated counterpart - ' || j.code || '-' || a.code || '-' || p.code || '-' || f.code AS "desc", '' AS "ref", p.date_stop AS "document_date", p.date_stop AS "date", a.code AS "account", '' AS "partner_txt", '' AS "dest", '' AS "cost_center", '' AS "funding_pool", CASE WHEN req.total > 0 THEN req.total ELSE 0.0 END AS "debit", CASE WHEN req.total < 0 THEN ABS(req.total) ELSE 0.0 END as "credit", c.name AS "booking_currency", c.id
            FROM (
                SELECT aml.period_id, aml.journal_id, aml.currency_id, aml.account_id, SUM(amount_currency) AS total
                FROM account_move_line AS aml, account_journal AS j
                WHERE aml.exporting_sequence = %s
                AND aml.journal_id = j.id
                AND j.type NOT IN ('hq', 'migration')
                GROUP BY aml.period_id, aml.journal_id, aml.currency_id, aml.account_id
                ORDER BY aml.account_id
            ) AS req, account_account AS a, account_period AS p, account_journal AS j, res_currency AS c, account_fiscalyear AS f
            WHERE req.account_id = a.id
            AND req.period_id = p.id
            AND req.journal_id = j.id
            AND req.currency_id = c.id
            AND p.fiscalyear_id = f.id
            AND a.shrink_entries_for_hq = 't';"""
        cr.execute(sqltwo, (seq,))
        datatwo = cr.fetchall()
        # post process datas
        new_data = self.postprocess_add_functional(cr, uid, datatwo, {'currency': 13, 'date': date, 'columns': [10, 11]}, column_deletion=column_deletion)
        # mark lines as exported
        sqlmarktwo = """UPDATE account_move_line SET exported = 't', exporting_sequence = Null WHERE id in %s;"""
        cr.execute(sqlmarktwo, (tuple(ids),))
        # return result
        return new_data

    def postprocess_register(self, cr, uid, data, column_deletion=False):
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
            new_data.append(self.line_to_utf8(tmp_line))
        return self.postprocess_selection_columns(cr, uid, new_data, [('account.bank.statement', 'state', 6)], column_deletion=column_deletion)

    def postprocess_add_period(self, cr, uid, data, period_name, column_deletion=False):
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
            # Convert to UTF-8
            tmp_line = self.line_to_utf8(tmp_line)
            # Delete useless columns
            if column_deletion:
                tmp_line = self.delete_x_column(tmp_line, column_deletion)
            new_data.append(tmp_line)
        return new_data

class hq_report_ocb(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

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

        ## TO BE DELETE DURING INTEGRATION
        if form.get('reset', False):
            delete_sql = "UPDATE account_move_line set exported='f';"
            cr.execute(delete_sql)
            delete2_sql = "UPDATE account_analytic_line set exported='f';"
            cr.execute(delete2_sql)
        ##################################

        # Prepare SQL requests and PROCESS requests for finance_archive object

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
                SELECT name, code, type, CASE WHEN date_start < %s AND (date IS NULL OR date > %s) THEN 'Active' ELSE 'Inactive' END AS Status
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
                SELECT i.name AS instance, st.name, p.name AS period, st.balance_start, st.id, CASE WHEN st.balance_end_real IS NOT NULL THEN st.balance_end_real ELSE 0.0 END AS balance_end_real, st.state, j.code AS "journal_code"
                FROM account_bank_statement AS st, msf_instance AS i, account_period AS p, account_journal AS j
                WHERE st.instance_id = i.id
                AND st.period_id = p.id
                AND st.journal_id = j.id
                AND p.id = %s
                ORDER BY st.name, p.number;
                """,
            'contract': """
                SELECT c.name, c.code, d.code, c.grant_amount, rc.name, c.state
                FROM financing_contract_contract AS c, financing_contract_donor AS d, res_currency AS rc
                WHERE c.donor_id = d.id
                AND c.reporting_currency = rc.id;
                """,
            # Pay attention to take analytic line that are not on HQ and MIGRATION journals.
            'rawdata': """
                SELECT al.id, al.entry_sequence, al.name, al.ref, al.document_date, al.date, a.code, al.partner_txt, aa.code AS dest, aa2.code AS cost_center_id, aa3.code AS funding_pool, CASE WHEN al.amount_currency < 0 THEN ABS(al.amount_currency) ELSE 0.0 END AS debit, CASE WHEN al.amount_currency > 0 THEN al.amount_currency ELSE 0.0 END AS credit, c.name AS "booking_currency", CASE WHEN al.amount < 0 THEN ABS(al.amount) ELSE 0.0 END AS debit, CASE WHEN al.amount > 0 THEN al.amount ELSE 0.0 END AS credit, cc.name AS "functional_currency"
                FROM account_analytic_line AS al, account_account AS a, account_analytic_account AS aa, account_analytic_account AS aa2, account_analytic_account AS aa3, res_currency AS c, res_company AS e, res_currency AS cc, account_analytic_journal AS j
                WHERE al.destination_id = aa.id
                AND al.cost_center_id = aa2.id
                AND al.account_id = aa3.id
                AND al.general_account_id = a.id
                AND al.currency_id = c.id
                AND aa3.category = 'FUNDING'
                AND al.company_id = e.id
                AND e.currency_id = cc.id
                AND al.journal_id = j.id
                AND j.type not in ('hq', 'migration')
                AND al.exported != 't';
                """,
            # Exclude lines that come from a HQ or MIGRATION journal
            # Take all lines that are on account that is "shrink_entries_for_hq" which will make a consolidation of them (with a second SQL request)
            # The subrequest permit to disallow lines that have analytic lines. This is to not retrieve expense/income accounts
            'bs_entries_consolidated': """
                SELECT aml.id
                FROM account_move_line AS aml, account_account AS aa, account_journal AS j
                WHERE aml.period_id = %s
                AND aml.account_id = aa.id
                AND aml.journal_id = j.id
                AND j.type not in ('hq', 'migration')
                AND aa.shrink_entries_for_hq = 't'
                AND aml.id not in (SELECT amla.id FROM account_move_line amla, account_analytic_line al WHERE al.move_id = amla.id)
                AND aml.exported != 't';
                """,
            # Do not take lines that come from a HQ or MIGRATION journal
            # Do not take journal items that have analytic lines because they are taken from "rawdata" SQL request
            'bs_entries': """
                SELECT aml.id, m.name as "entry_sequence", aml.name, aml.ref, aml.document_date, aml.date, a.code, aml.partner_txt, '', '', '', aml.debit_currency, aml.credit_currency, c.name, aml.debit, aml.credit, cc.name
                FROM account_move_line AS aml, account_account AS a, res_currency AS c, account_move AS m, res_company AS e, account_journal AS j, res_currency AS cc
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
                AND aml.period_id = %s
                AND a.shrink_entries_for_hq != 't'
                AND j.type not in ('hq', 'migration')
                AND aml.exported != 't'
                ORDER BY aml.id;
                """,
        }

        # PROCESS REQUESTS LIST: list of dict containing info to process some SQL requests
        # Dict:
        # - [optional] headers: list of headers that should appears in the CSV file
        # - filename: the name of the result filename in the future ZIP file
        # - key: the name of the key in SQLREQUESTS DICTIONNARY to have the right SQL request
        # - [optional] query_params: data to use to complete SQL requests
        # - [optional] function: name of the function to postprocess data (example: to change selection field into a human readable text)
        # - [optional] fnct_params: params that would used on the given function
        # - [optional] delete_columns: list of columns to delete before writing files into result
        # - [optional] id (need 'object'): number of the column that contains the ID of the element.
        # - [optional] object (need 'id'): name of the object in the system. For an example: 'account.bank.statement'.
        # TIP & TRICKS:
        # + More than 1 request in 1 file: just use same filename for each request you want to be in the same file.
        # + If you cannot do a SQL request to create the content of the file, do a simple request (with key) and add a postprocess function that returns the result you want
        processrequests = [
            {
                'headers': ['Name', 'Reference', 'Partner type', 'Active/inactive'],
                'filename': 'partners.csv',
                'key': 'partner',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('res.partner', 'partner_type', 2)],
                },
            {
                'headers': ['Name', 'Identification No', 'Active', 'Employee type'],
                'filename': 'employees.csv',
                'key': 'employee',
                },
            {
                'headers': ['Instance', 'Code', 'Name', 'Journal type'],
                'filename': 'journals.csv',
                'key': 'journal',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('account.journal', 'type', 3)],
                },
            {
                'headers': ['Name', 'Code', 'Type', 'Status'],
                'filename': 'cost_centers.csv',
                'key': 'costcenter',
                'query_params': (last_day_of_period, last_day_of_period, tuple(instance_ids)),
                'function': 'postprocess_selection_columns',
                'fnct_params': [('account.analytic.account', 'type', 2)],
                },
            {
                'headers': ['CCY code', 'CCY name', 'Rate', 'Month'],
                'filename': 'fxrates.csv',
                'key': 'fxrate',
                'query_params': (last_day_of_period, first_day_of_period),
                'function': 'postprocess_add_period',
                'fnct_params': period_name,
                },
            {
                'headers': ['Instance', 'Name', 'Period', 'Opening balance', 'Calculated balance', 'Closing balance', 'State', 'Journal code'],
                'filename': 'liquidities.csv',
                'key': 'register',
                'query_params': tuple([period.id]),
                'function': 'postprocess_register',
                },
            {
                'headers': ['Name', 'Code', 'Donor code', 'Grant amount', 'Reporting CCY', 'State'],
                'filename': 'contracts.csv',
                'key': 'contract',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('financing.contract.contract', 'state', 5)],
                },
            {
                'headers': ['Entry sequence', 'Description', 'Reference', 'Document date', 'Posting date', 'G/L Account', 'Third party', 'Destination', 'Cost centre', 'Funding pool', 'Booking debit', 'Booking credit', 'Booking currency', 'Functional debit', 'Functional credit', 'Functional CCY'],
                'filename': 'Export_Data.csv',
                'key': 'rawdata',
                'delete_columns': [0],
                'id': 0,
                'object': 'account.analytic.line',
                },
            {
                'filename': 'Export_Data.csv',
                'key': 'bs_entries_consolidated',
                'query_params': ([period.id]),
                'function': 'postprocess_consolidated_entries',
                'fnct_params': last_day_of_period,
                },
            {
                'filename': 'Export_Data.csv',
                'key': 'bs_entries',
                'query_params': ([period.id]),
                'delete_columns': [0],
                'id': 0,
                'object': 'account.move.line',
                },
        ]
        # Launch finance archive object
        fe = finance_archive(sqlrequests, processrequests)
        # Use archive method to create the archive
        return fe.archive(cr, uid)

hq_report_ocb('report.hq.ocb', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
