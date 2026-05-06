# -*- coding:utf-8 -*-

from osv import osv
from tools.translate import _
import pooler
from time import strptime
from datetime import datetime
from report import report_sxw
import csv
import zipfile
import tempfile
from tools.misc import Path
from tools.misc import month_abbr
import os


class hq_report_ubuntu(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def update_percent(self, cr, uid, percent):
        if self.bk_id:
            self.pool.get('memory.background.report').write(cr, uid, self.bk_id, {'percent': percent})


    def create(self, cr, uid, ids, data, context=None):

        if not data.get('form', False):
            raise osv.except_osv(_('Error'), _('No data retrieved. Check that the wizard is filled in.'))

        if context is None:
            context = {}

        pool = pooler.get_pool(cr.dbname)

        # new cursor to execute queries inside the fetch(500) loop
        new_cr = pooler.get_db(cr.dbname).cursor()

        self.bk_id = context.get('background_id')
        self.pool = pool

        mi_obj = pool.get('msf.instance')
        period_obj = pool.get('account.period')
        excluded_journal_types = ['hq', 'engagement']
        excluded_journal_types_formatted = ['migration', 'inkind', 'extra']

        form = data.get('form')
        period_id = form.get('period_id', False)
        instance_ids = form.get('instance_ids', False)
        instance_id = form.get('instance_id', False)

        if form.get('selection', False) == 'all':
            to_export = ('f', 't')
        else:
            to_export = ('f', )

        if not period_id or not instance_ids or not instance_id:
            raise osv.except_osv(_('Warning'), _('Some information is missing: either fiscal year or period or instance.'))

        period = period_obj.browse(cr, uid, period_id, context=context,
                                   fields_to_fetch=['date_start', 'date_stop', 'number', 'fiscalyear_id'])
        first_day_of_period = period.date_start
        tm = strptime(first_day_of_period, '%Y-%m-%d')
        year_num = tm.tm_year
        period_yyyymm = '%dP%02d' % (year_num, tm.tm_mon)
        period_mmyyyy = '%s-%d' % (month_abbr[tm.tm_mon], year_num-2000)
        company_curr = pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.currency_id.name

        kes_ids = pool.get('res.currency').search(cr, uid, [('name', '=', 'KES'), ('currency_table_id', '=', False), ('active', 'in', ['t', 'f'])])

        country_map = ''
        country_map_obj = pool.get('country.export.mapping')
        countries = country_map_obj.search(cr, uid, [('instance_id', '=', instance_id)])
        if countries:
            country_map = country_map_obj.browse(cr, uid, countries[0]).mapping_value

        sql_params = {
            'instance_ids': tuple(instance_ids),
            'period_id': period_id,
            'min_date': period.date_start,
            'max_date':  period.date_stop,
            'j_type': tuple(excluded_journal_types),
            'first_day_of_period': period.date_start,
            'last_day_of_period': period.date_stop,
            'kes_id': kes_ids and kes_ids[0] or 0,
            'to_export': to_export,
        }


        self.update_percent(cr, uid, 0.10)
        # analytic lines raw_data
        analytic_query = """
          CREATE TEMP TABLE export_ubuntu_temp ON COMMIT DROP AS
                SELECT
                    'account_analytic_line' as object,
                    al.id as id,
                    aml.id as account_move_line_id,
                    i.instance as instance,
                    j.code as journal_code,
                    j.type as journal_type,
                    al.entry_sequence,
                    al.name as description,
                    coalesce(al.ref,'False') as reference,
                    al.document_date as document_date,
                    al.date as posting_date,
                    a.code as gl_account,
                    dest.code as destination,
                    cost_center.code as cost_center,
                    fp.code as fp,
                    coalesce(al.partner_txt, 'False') as partner_txt,
                    case when coalesce(hr.employee_type, '') = 'ex' then hr.identification_id else '' END as employee_id,
                    (select
                            rate.rate
                        from
                            res_currency_rate rate
                        where
                            rate.currency_id = al.currency_id
                            and rate.name <= date_trunc('month', coalesce(al.source_date, al.date))
                        order by
                            rate.name desc
                        limit 1
                    ) as fx_rate,

                    CASE WHEN al.amount_currency < 0 AND aml.is_addendum_line = 'f' THEN round(ABS(al.amount_currency), 2) ELSE 0.0 END AS book_debit,
                    CASE WHEN al.amount_currency > 0 AND aml.is_addendum_line = 'f' THEN round(al.amount_currency, 2) ELSE 0.0 END AS book_credit,
                    CASE WHEN al.amount < 0  THEN round(ABS(al.amount), 2) ELSE 0.0 END AS func_debit,
                    CASE WHEN al.amount > 0  THEN round(al.amount, 2) ELSE 0.0 END AS func_credit,
                    c.name as book_currency,
                    (select
                            kes_rate.rate
                        from
                            res_currency_rate kes_rate
                        where
                            kes_rate.currency_id = %(kes_id)s
                            and kes_rate.name <= date_trunc('month', coalesce(aml.source_date, aml.date))
                        order by
                            kes_rate.name desc
                        limit 1
                    ) as kes_rate
                FROM
                    account_analytic_line AS al,
                    account_account AS a,
                    account_analytic_account AS dest,
                    account_analytic_account AS cost_center,
                    account_analytic_account AS fp,
                    res_currency AS c,
                    res_currency AS move_c,
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
                    AND fp.id = al.account_id
                    AND a.id = al.general_account_id
                    AND c.id = al.currency_id
                    AND j.id = al.journal_id
                    AND aml.id = al.move_id
                    AND am.id = aml.move_id
                    AND move_c.id = aml.currency_id
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
                    AND al.exported in %(to_export)s
        """

        move_line_query = """
           INSERT INTO export_ubuntu_temp
                SELECT
                    'account_move_line' as object,
                    aml.id as id,
                    NULL as account_move_line_id,
                    i.instance as instance,
                    j.code as journal_code,
                    j.type as journal_type,
                    m.name as entry_sequence,
                    aml.name as description,
                    coalesce(aml.ref, 'False') as reference,
                    aml.document_date,
                    aml.date as posting_date,
                    a.code as gl_account,
                    NULL as destination,
                    NULL as cost_center,
                    NULL as fp,
                    coalesce(aml.partner_txt, 'False') as partner_txt,
                    case when coalesce(hr.employee_type, '') = 'ex' then hr.identification_id else '' END as employee_id,
                    (select
                            rate.rate
                        from
                            res_currency_rate rate
                        where
                            rate.currency_id = aml.currency_id
                            and rate.name <= date_trunc('month', coalesce(aml.source_date, aml.date))
                        order by
                            rate.name desc
                        limit 1
                    ) as fx_rate,
                    round(aml.debit_currency, 2) as book_debit,
                    round(aml.credit_currency, 2) as book_credit,
                    round(aml.debit, 2) as func_debit,
                    round(aml.credit, 2) as func_credit,
                    c.name as book_currency,
                    (select
                            kes_rate.rate
                        from
                            res_currency_rate kes_rate
                        where
                            kes_rate.currency_id = %(kes_id)s
                            and kes_rate.name <= date_trunc('month', coalesce(aml.source_date, aml.date))
                        order by
                            kes_rate.name desc
                        limit 1
                    ) as kes_rate
                FROM
                    account_move_line aml
                    INNER JOIN account_move AS m ON aml.move_id = m.id
                    LEFT JOIN hr_employee hr ON hr.id = aml.employee_id
                    INNER JOIN account_account AS a ON aml.account_id = a.id
                    INNER JOIN res_currency AS c ON aml.currency_id = c.id
                    INNER JOIN account_journal AS j ON aml.journal_id = j.id
                    INNER JOIN msf_instance AS i ON aml.instance_id = i.id
                    LEFT JOIN account_analytic_line aal ON aal.move_id = aml.id
                WHERE
                    aal.id IS NULL
                    AND aml.period_id = %(period_id)s
                    AND j.type NOT IN %(j_type)s
                    AND aml.instance_id IN %(instance_ids)s
                    AND m.state = 'posted'
                    AND aml.exported in %(to_export)s
                ORDER BY
                    aml.id
        """

        full_col_header = [
            ('Proprietary Instance', ),
            ('Journal Code', ),
            ('Entry Sequence', ),
            ('Description', ),
            ('Reference', ),
            ('Document Date', ),
            ('Posting Date', ),
            ('Period', ),
            ('G/L Account', ),
            ('UF Budget Line', ),
            ('Country Program', ),
            ('Cost Center', ),
            ('Funding Pool', False) ,
            ('Third Party', ),
            ('Employee ID', ),
            ('Booking Debit', ),
            ('Booking Credit', ),
            ('Booking Currency', ),
            ('Functionnal Debit', False),
            ('Functionnal Credit', False),
            ('Functionnal Currency', False),
            ('%s rate' % company_curr, ),
            ('KES rate', ),
        ]

        formatted_file = tempfile.NamedTemporaryFile('w', delete=False, newline='')
        formatted_file_name = formatted_file.name
        formatted_writer = csv.writer(formatted_file, quoting=csv.QUOTE_MINIMAL, delimiter=",")
        formatted_writer.writerow([x[0] for x in full_col_header if len(x) == 1 or x[1]])

        raw_file = tempfile.NamedTemporaryFile('w', delete=False, newline='')
        raw_file_name = raw_file.name
        raw_writer = csv.writer(raw_file, quoting=csv.QUOTE_MINIMAL, delimiter=",")
        raw_writer.writerow([x[0] for x in full_col_header])

        for sql in [analytic_query, move_line_query]:
            cr.execute(sql, sql_params)

        cr.execute('select * from export_ubuntu_temp order by entry_sequence')
        while True:
            ajis = set()
            amls = set()
            rows = cr.dictfetchmany(500)

            if not rows:
                break
            for row in rows:
                if row['object'] == 'account_analytic_line':
                    ajis.add(row['id'])
                    amls.add(row['account_move_line_id'])
                else:
                    amls.add(row['id'])

                # general is used as accrual for AJIs
                if row['journal_type'] in ('cur_adj', 'revaluation'):
                    rate = 1
                    debit = row['func_debit']
                    credit = row['func_credit']
                    currency = company_curr

                else:
                    rate = row['fx_rate']
                    debit = row['book_debit']
                    credit = row['book_credit']
                    currency = row['book_currency']


                kes_rate = 0
                if row.get('kes_rate') and rate:
                    kes_rate = round(row['kes_rate'] / rate, 6)

                line = [
                    row['instance'],
                    row['journal_code'],
                    row['entry_sequence'],
                    row['description'],
                    row['reference'],
                    datetime.strptime(row['document_date'], '%Y-%m-%d').strftime('%d/%m/%Y'),
                    datetime.strptime(row['posting_date'], '%Y-%m-%d').strftime('%d/%m/%Y'),
                    period_mmyyyy,
                    row['gl_account'],
                    row.get('destination', ''),
                    country_map or '',
                    row.get('cost_center', ''),
                    row.get('fp', ''),
                    row['partner_txt'],
                    row['employee_id'],
                    debit,
                    credit,
                    currency,
                    row['func_debit'],
                    row['func_credit'],
                    company_curr,
                    rate,
                    kes_rate
                ]


                raw_writer.writerow(line)
                if row['journal_type'] not in excluded_journal_types_formatted and (
                        row['book_debit'] != 0 or row['book_credit'] != 0 or row['func_debit'] != 0 or row['func_credit'] != 0 ):
                    f_line = [x[1] for x in enumerate(line) if len(full_col_header[x[0]]) == 1 or full_col_header[x[0]][1]]
                    formatted_writer.writerow(f_line)
            if ajis:
                new_cr.execute("update account_analytic_line set exported='t' where id in %s", (tuple(ajis), ))
            if amls:
                new_cr.execute("update account_move_line set exported='t' where id in %s", (tuple(amls), ))

            self.update_percent(new_cr, uid, 0.45)

        self.update_percent(cr, uid, 0.80)

        self.update_percent(cr, uid, 0.90)

        formatted_file.close()
        raw_file.close()


        if data.get('output_file'):
            tmpzipname = data['output_file']
        else:
            null1, tmpzipname = tempfile.mkstemp()
        zf = zipfile.ZipFile(tmpzipname, 'w')

        inst = mi_obj.browse(cr, uid, instance_id, context=context, fields_to_fetch=['code'])
        prefix = inst and inst.code[:3] or ''
        formatted_file_zip_name = '%s_%s_formatted data D365 import.csv' % (prefix, period_yyyymm)
        raw_file_zip_name = '%s_%s_Raw data D365 import.csv' % (prefix, period_yyyymm)
        zf.write(formatted_file_name, formatted_file_zip_name)
        zf.write(raw_file_name, raw_file_zip_name)
        zf.close()

        if not data.get('output_file'):
            os.close(null1)

        new_cr.commit()
        new_cr.close(True)
        return (Path(tmpzipname, delete=True), 'zip')



hq_report_ubuntu('report.hq.ubuntu', 'account.move.line', False, parser=False)
