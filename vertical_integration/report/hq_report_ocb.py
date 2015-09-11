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
from time import strptime

from account_override import finance_export

from report import report_sxw


class finance_archive(finance_export.finance_archive):
    """
    Extend existing class with new methods for this particular export.
    """

    def postprocess_partners(self, cr, uid, data, column_deletion=False):
        """
        Add XML_ID of each element.
        """
        # Prepare some values
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        for line in data:
            tmp_line = list(line)
            p_id = line[0]
            tmp_line[0] = self.get_hash(cr, uid, [p_id], 'res.partner')
            new_data.append(self.line_to_utf8(tmp_line))

        return self.postprocess_selection_columns(cr, uid, new_data, [('res.partner', 'partner_type', 3)], column_deletion=column_deletion)

    def postprocess_add_db_id(self, cr, uid, data, model, column_deletion=False):
        """
        Change first column for the DB ID composed of:
          - database name
          - model
          - id
        """
        # Prepare some values
        context = {}
        new_data = []
        dbname = cr.dbname
        pool = pooler.get_pool(dbname)
        column_number = 0
        partner_obj = pool.get('res.partner')
        partner_name_column_number = 10
        partner_id_column_number = 21
        employee_name_column = 22
        for line in data:
            tmp_line = list(line)
            line_ids = str(line[column_number])
            tmp_line[column_number] = self.get_hash(cr, uid, line_ids, model)
            # Check if we have a partner_id in last column
            partner_id_present = False
            partner_id = False
            partner_hash = ''
            if len(tmp_line) > (partner_id_column_number - 1):
                partner_id = tmp_line[partner_id_column_number - 1]
                if partner_id:
                    # US-497: extract name from partner_id (better than partner_txt)
                    tmp_line[partner_name_column_number - 1] = partner_obj.read(cr, uid, partner_id, ['name'])['name']
            # If not partner_id, then check 'Third Party' column to search it by name
            if not partner_id_present:
                partner_name = tmp_line[partner_name_column_number - 1]
                # Search only if partner_name is not empty
                if partner_name:
                    # UFT-8 encoding
                    if isinstance(partner_name, unicode):
                        partner_name = partner_name.encode('utf-8')
                    partner_ids = partner_obj.search(cr, uid, [('name', '=ilike', partner_name), ('active', 'in', ['t', 'f'])], order='id')
                    if partner_ids:
                        partner_id = partner_ids[0]
            # If we get some ids, fetch the partner hash
            if partner_id:
                if isinstance(partner_id, (int, long)):
                    partner_id = [partner_id]
                partner_hash = self.get_hash(cr, uid, partner_id, 'res.partner')
            # Complete last column with partner_hash
            if not partner_id_present:
                tmp_line.append('')
            emplid = tmp_line[partner_id_column_number - 2]

            if not emplid and not partner_id and tmp_line[partner_name_column_number - 1]:
                employee_obj = pool.get('hr.employee')
                # we don't have partner and employee, if update employee creation is not run check if he duplicates in the DB
                partner_name = tmp_line[partner_name_column_number - 1]
                if isinstance(partner_name, unicode):
                    partner_name = partner_name.encode('utf-8')
                emp_ids = employee_obj.search(cr, uid, [('name', '=', partner_name), ('active', 'in', ['t', 'f'])])
                if emp_ids:
                    empl_code = employee_obj.read(cr, uid, emp_ids[0], ['identification_id'])['identification_id']
                    if empl_code:
                        tmp_line[partner_id_column_number - 2] = empl_code

            if emplid:
                partner_hash = ''
                if tmp_line[employee_name_column - 1]:
                    tmp_line[partner_name_column_number - 1] = tmp_line[employee_name_column - 1]
            tmp_line[partner_id_column_number - 1] = partner_hash
            del(tmp_line[employee_name_column - 1])
            # Add result to new_data
            new_data.append(self.line_to_utf8(tmp_line))
        res = self.postprocess_selection_columns(cr, uid, new_data, [], column_deletion=column_deletion)
        return res

    def postprocess_consolidated_entries(self, cr, uid, data, excluded_journal_types, column_deletion=False):
        """
        Use current SQL result (data) to fetch IDs and mark lines as used.
        Then do another request.
        Finally mark lines as exported.

        Data is a list of tuples.
        """
        # Checks
        if not excluded_journal_types:
            raise osv.except_osv(_('Warning'), _('Excluded journal_types not found!'))
        # Prepare some values
        new_data = []
        pool = pooler.get_pool(cr.dbname)
        ids = [x and x[0] for x in data]
        company_currency = pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.name
        # In case where no line to return, abort process and return empty data
        if not ids:
            return new_data
        # Create new export sequence
        seq = pool.get('ir.sequence').get(cr, uid, 'finance.ocb.export')
        # Mark lines as used
        sqlmark = """UPDATE account_move_line SET exporting_sequence = %s WHERE id in %s;"""
        cr.execute(sqlmark, (seq, tuple(ids),))
        # Do right request
        sqltwo = """SELECT req.concat AS "DB ID", i.code, j.code, j.code || '-' || p.code || '-' || f.code || '-' || a.code || '-' || c.name AS "entry_sequence", 'Automated counterpart - ' || j.code || '-' || a.code || '-' || p.code || '-' || f.code AS "desc", '' AS "ref", p.date_stop AS "document_date", p.date_stop AS "date", a.code AS "account", '' AS "partner_txt", '' AS "dest", '' AS "cost_center", '' AS "funding_pool", 
CASE WHEN req.total > 0 THEN req.total ELSE 0.0 END AS "debit", 
CASE WHEN req.total < 0 THEN ABS(req.total) ELSE 0.0 END as "credit", 
c.name AS "booking_currency", 
CASE WHEN req.func_total > 0 THEN req.func_total ELSE 0.0 END AS "func_debit", 
CASE WHEN req.func_total < 0 THEN ABS(req.func_total) ELSE 0.0 END AS "func_credit"
            FROM (
                SELECT aml.instance_id, aml.period_id, aml.journal_id, aml.currency_id, aml.account_id, 
                       SUM(amount_currency) AS total, 
                       SUM(debit - credit) AS func_total, 
                       array_to_string(array_agg(aml.id), ',') AS concat
                FROM account_move_line AS aml, account_journal AS j
                WHERE aml.exporting_sequence = %s
                AND aml.journal_id = j.id
                AND j.type NOT IN %s
                GROUP BY aml.instance_id, aml.period_id, aml.journal_id, aml.currency_id, aml.account_id
                ORDER BY aml.account_id
            ) AS req, 
                 account_account AS a, 
                 account_period AS p, 
                 account_journal AS j, 
                 res_currency AS c, 
                 account_fiscalyear AS f, 
                 msf_instance AS i
            WHERE req.account_id = a.id
            AND req.period_id = p.id
            AND req.journal_id = j.id
            AND req.currency_id = c.id
            AND req.instance_id = i.id
            AND p.fiscalyear_id = f.id
            AND a.shrink_entries_for_hq = 't';"""
        cr.execute(sqltwo, (seq, tuple(excluded_journal_types)))
        datatwo = cr.fetchall()
        # post process datas (add functional currency name, those from company)
        for line in datatwo:
            tmp_line = list(line)
            tmp_line.append(company_currency)
            line_ids = tmp_line[0]
            tmp_line[0] = self.get_hash(cr, uid, line_ids, 'account.move.line')
            new_data.append(tmp_line)
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
        excluded_journal_types = ['hq'] # journal types that should not be used to take lines
        # Fetch data from wizard
        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))
        form = data.get('form')
        fy_id = form.get('fiscalyear_id', False)
        period_id = form.get('period_id', False)
        instance_ids = form.get('instance_ids', False)
        instance_id = form.get('instance_id', False)
        if not fy_id or not period_id or not instance_ids or not instance_id:
            raise osv.except_osv(_('Warning'), _('Some info are missing. Either fiscalyear or period or instance.'))
        fy = pool.get('account.fiscalyear').browse(cr, uid, fy_id)
        last_fy_year = strptime(fy.date_start, '%Y-%m-%d').tm_year - 1 # Take previous year regarding given fiscalyear
        first_day_of_last_fy = '%s-01-01' % (last_fy_year)
        period = pool.get('account.period').browse(cr, uid, period_id)
        last_day_of_period = period.date_stop
        first_day_of_period = period.date_start
        period_name = period.name
        selection = form.get('selection', False)
        to_export = ['f'] # Default export value for exported field on analytic/move lines
        year = '%s' % (strptime(first_day_of_period, '%Y-%m-%d').tm_year)
        month = '%02d' % (strptime(first_day_of_period, '%Y-%m-%d').tm_mon)
        period_yyyymm = "{0}{1}".format(year,month)
        if not selection:
            raise osv.except_osv(_('Error'), _('No selection value for lines to select.'))
        if selection == 'all':
            to_export = ['f', 't']
        elif selection == 'unexported':
            to_export = ['f']
        else:
            raise osv.except_osv(_('Error'), _('Wrong value for selection: %s.') % (selection,))

        # Prepare SQL requests and PROCESS requests for finance_archive object

        # SQLREQUESTS DICTIONNARY
        # - key: name of the SQL request
        # - value: the SQL request to use
        sqlrequests = {
            'partner': """
                SELECT id, name, ref, partner_type, CASE WHEN active='t' THEN 'True' WHEN active='f' THEN 'False' END AS active
                FROM res_partner 
                WHERE partner_type != 'internal'
                  and name != 'To be defined';
                """,
            'employee': """
                SELECT r.name, e.identification_id, r.active, e.employee_type
                FROM hr_employee AS e, resource_resource AS r
                WHERE e.resource_id = r.id;
                """,
            'journal': """
                SELECT i.code, j.code, j.name, j.type, c.name
                FROM account_journal AS j LEFT JOIN res_currency c ON j.currency = c.id, msf_instance AS i
                WHERE j.instance_id = i.id
                AND j.instance_id in %s;
                """,
            'costcenter': """
            SELECT tr.value, aa.code, aa.type, 
            CASE WHEN aa.date_start < %s AND (aa.date IS NULL OR aa.date > %s) THEN 'Active' ELSE 'Inactive' END AS Status
                FROM account_analytic_account aa, ir_translation tr 
                WHERE tr.res_id = aa.id 
                  and tr.lang = 'en_MF' 
                  and tr.name = 'account.analytic.account,name' 
                  and tr.value is not null
                and aa.category = 'OC'
                AND aa.id in (
                    SELECT cost_center_id
                    FROM account_target_costcenter
                    WHERE instance_id in %s)
            UNION ALL
            SELECT aa.name, aa.code, aa.type, 
                CASE WHEN aa.date_start < %s AND (aa.date IS NULL OR aa.date > %s) THEN 'Active' ELSE 'Inactive' END AS Status
                FROM account_analytic_account aa
                where aa.category = 'OC'
                AND aa.id in (
                    SELECT cost_center_id
                    FROM account_target_costcenter
                    WHERE instance_id in %s)
                AND NOT EXISTS (select 'X' 
                    from ir_translation tr 
                    WHERE tr.res_id = aa.id 
                    and tr.lang = 'en_MF' 
                    and tr.name = 'account.analytic.account,name');
                """, 
            'fxrate': """
                SELECT req.name, req.code, req.rate, req.period
                FROM (
                    SELECT rc.currency_name AS "name", rc.name AS "code", r.rate AS "rate", r.name AS "date", to_char(p.date_start,'YYYYMM') AS "period"
                    FROM account_period AS p, res_currency_rate AS r LEFT JOIN res_currency rc ON r.currency_id = rc.id
                    WHERE p.date_start <= r.name
                    AND p.date_stop >= r.name
                    AND r.currency_id IS NOT NULL
                    AND rc.active = 't'
                    AND p.number NOT IN (13, 14, 15)
                    and rc.reference_currency_id is null
                    ORDER BY rc.name
                ) AS req
                WHERE req.date >= %s
                AND req.date <= %s;
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
            'liquidity': """
                SELECT i.code AS instance, j.code, j.name, %s AS period, req.opening, req.calculated, req.closing
                FROM (
                    SELECT journal_id, account_id, SUM(col1) AS opening, SUM(col2) AS calculated, SUM(col3) AS closing
                    FROM (
                        (
                            SELECT aml.journal_id AS journal_id, aml.account_id AS account_id, ROUND(SUM(amount_currency), 2) as col1, 0.00 as col2, 0.00 as col3
                            FROM account_move_line AS aml 
                            LEFT JOIN account_journal j 
                                ON aml.journal_id = j.id 
                            WHERE j.type IN ('cash', 'bank', 'cheque')
                            AND aml.date < %s
                            AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id)
                            GROUP BY aml.journal_id, aml.account_id
                        )
                    UNION
                        (
                            SELECT aml.journal_id AS journal_id, aml.account_id AS account_id, 0.00 as col1, ROUND(SUM(amount_currency), 2) as col2, 0.00 as col3
                            FROM account_move_line AS aml 
                            LEFT JOIN account_journal j 
                                ON aml.journal_id = j.id 
                            WHERE j.type IN ('cash', 'bank', 'cheque')
                            AND aml.period_id = %s
                            AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id)
                            GROUP BY aml.journal_id, aml.account_id
                        )
                    UNION
                        (
                            SELECT aml.journal_id AS journal_id, aml.account_id AS account_id, 0.00 as col1, 0.00 as col2, ROUND(SUM(amount_currency), 2) as col3
                            FROM account_move_line AS aml 
                            LEFT JOIN account_journal j 
                                ON aml.journal_id = j.id 
                            WHERE j.type IN ('cash', 'bank', 'cheque')
                            AND aml.date <= %s
                            AND aml.account_id IN (j.default_debit_account_id, j.default_credit_account_id)
                            GROUP BY aml.journal_id, aml.account_id
                        )
                    ) AS ssreq
                    GROUP BY journal_id, account_id
                    ORDER BY journal_id, account_id
                ) AS req, account_journal j, msf_instance i
                WHERE req.journal_id = j.id
                AND j.instance_id = i.id
                AND j.instance_id IN %s;
            """,
            'contract': """
                SELECT c.name, c.code, d.code, c.grant_amount, rc.name, c.state
                FROM financing_contract_contract AS c, financing_contract_donor AS d, res_currency AS rc
                WHERE c.donor_id = d.id
                AND c.reporting_currency = rc.id
                AND c.instance_id in %s
                AND c.state != 'draft';
                """,
            # Pay attention to take analytic line that are not on HQ and MIGRATION journals.
            'rawdata': """
                SELECT al.id, i.code, aj.code, al.entry_sequence, al.name, al.ref, al.document_date, al.date, 
                       a.code, al.partner_txt, aa.code AS dest, aa2.code AS cost_center_id, aa3.code AS funding_pool, 
                       CASE WHEN al.amount_currency < 0 AND aml.is_addendum_line = 'f' THEN ABS(al.amount_currency) ELSE 0.0 END AS debit, 
                       CASE WHEN al.amount_currency > 0 AND aml.is_addendum_line = 'f' THEN al.amount_currency ELSE 0.0 END AS credit, 
                       c.name AS "booking_currency", 
                       CASE WHEN al.amount < 0 THEN ABS(ROUND(al.amount, 2)) ELSE 0.0 END AS debit, 
                       CASE WHEN al.amount > 0 THEN ROUND(al.amount, 2) ELSE 0.0 END AS credit,
                       cc.name AS "functional_currency", hr.identification_id as "emplid", aml.partner_id, hr.name_resource as hr_name
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
                               from account_move_line aml2, account_move am
                               where am.id = aml2.move_id 
                                and am.state = 'posted')
                AND al.instance_id = i.id
                AND aml.journal_id = aj.id
                AND al.date >= %s
                AND al.date <= %s
                AND j.type not in %s
                AND al.exported in %s
                AND al.instance_id in %s;
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
                AND j.type not in %s
                AND aa.shrink_entries_for_hq = 't'
                AND aml.id not in (SELECT amla.id FROM account_move_line amla, account_analytic_line al WHERE al.move_id = amla.id)
                AND aml.exported in %s
                AND aml.instance_id in %s;
                """,
            # Do not take lines that come from a HQ or MIGRATION journal
            # Do not take journal items that have analytic lines because they are taken from "rawdata" SQL request
            'bs_entries': """
                SELECT aml.id, i.code, j.code, m.name as "entry_sequence", aml.name, aml.ref, aml.document_date, aml.date, 
                       a.code, aml.partner_txt, '', '', '', aml.debit_currency, aml.credit_currency, c.name,
                       ROUND(aml.debit, 2), ROUND(aml.credit, 2), cc.name, hr.identification_id as "Emplid", aml.partner_id, hr.name_resource as hr_name
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
                AND aml.exported in %s
                AND aml.instance_id in %s
                AND m.state = 'posted'
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
        instance = pool.get('msf.instance').browse(cr, uid, instance_id)
        instance_name = instance.code[0:3] # Take only 3 first digits
        processrequests = [
            {
                'headers': ['XML_ID', 'Name', 'Reference', 'Partner type', 'Active/inactive'],
                'filename': instance_name + '_' + year + month + '_Partners.csv',
                'key': 'partner',
                'function': 'postprocess_partners',
                },
            {
                'headers': ['Name', 'Identification No', 'Active', 'Employee type'],
                'filename': instance_name + '_' + year + month + '_Employees.csv',
                'key': 'employee',
                'function': 'postprocess_selection_columns',
                'fnct_params': [('hr.employee', 'employee_type', 3)],
                },
            {
                'headers': ['Instance', 'Code', 'Name', 'Journal type', 'Currency'],
                'filename': instance_name + '_' + year + month + '_Journals.csv',
                'key': 'journal',
                'query_params': (tuple(instance_ids),),
                'function': 'postprocess_selection_columns',
                'fnct_params': [('account.journal', 'type', 3)],
                },
            {
                'headers': ['Name', 'Code', 'Type', 'Status'],
                'filename': instance_name + '_' + year + month + '_Cost Centres.csv',
                'key': 'costcenter',
                'query_params': (last_day_of_period, last_day_of_period, tuple(instance_ids),last_day_of_period, last_day_of_period, tuple(instance_ids)),
                'function': 'postprocess_selection_columns',
                'fnct_params': [('account.analytic.account', 'type', 2)],
                },
            {
                'headers': ['CCY name', 'CCY code', 'Rate', 'Month'],
                'filename': instance_name + '_' + year + month + '_FX rates.csv',
                'key': 'fxrate',
                'query_params': (first_day_of_last_fy, last_day_of_period),
                },
            {
                'headers': ['Instance', 'Code', 'Name', 'Period', 'Opening balance', 'Calculated balance', 'Closing balance'],
                'filename': instance_name + '_' + year + month + '_Liquidity Balances.csv',
                'key': 'liquidity',
                'query_params': (tuple([period_yyyymm]), first_day_of_period, period.id, last_day_of_period, tuple(instance_ids)),
                },
            {
                'headers': ['Name', 'Code', 'Donor code', 'Grant amount', 'Reporting CCY', 'State'],
                'filename': instance_name + '_' + year + month + '_Financing contracts.csv',
                'key': 'contract',
                'query_params': (tuple(instance_ids),),
                'function': 'postprocess_selection_columns',
                'fnct_params': [('financing.contract.contract', 'state', 5)],
                },
            {
                'headers': ['DB ID', 'Instance', 'Journal', 'Entry sequence', 'Description', 'Reference', 'Document date', 'Posting date', 'G/L Account', 'Third party', 'Destination', 'Cost centre', 'Funding pool', 'Booking debit', 'Booking credit', 'Booking currency', 'Functional debit', 'Functional credit',  'Functional CCY', 'Emplid', 'Partner DB ID'],
                'filename': instance_name + '_' + year + month + '_Monthly Export.csv',
                'key': 'rawdata',
                'function': 'postprocess_add_db_id', # to take analytic line IDS and make a DB ID with
                'fnct_params': 'account.analytic.line',
                'query_params': (first_day_of_period, last_day_of_period, tuple(excluded_journal_types), tuple(to_export), tuple(instance_ids)),
                'delete_columns': [0],
                'id': 0,
                'object': 'account.analytic.line',
                },
            {
                'filename': instance_name + '_' + year + month + '_Monthly Export.csv',
                'key': 'bs_entries_consolidated',
                'query_params': (period.id, tuple(excluded_journal_types), tuple(to_export), tuple(instance_ids)),
                'function': 'postprocess_consolidated_entries',
                'fnct_params': excluded_journal_types,
                },
            {
                'filename': instance_name + '_' + year + month + '_Monthly Export.csv',
                'key': 'bs_entries',
                'function': 'postprocess_add_db_id', # to take analytic line IDS and make a DB ID with
                'fnct_params': 'account.move.line',
                'query_params': (period.id, tuple(excluded_journal_types), tuple(to_export), tuple(instance_ids)),
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
