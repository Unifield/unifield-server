# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import datetime
import csv
import StringIO
import pooler
import zipfile
from tempfile import NamedTemporaryFile
import os

from report import report_sxw


class hq_report_oca(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st

    def translate_country(self, cr, uid, pool, browse_instance, context={}):
        mapping_obj = pool.get('country.export.mapping')
        if browse_instance:
            mapping_ids = mapping_obj.search(cr, uid, [('instance_id', '=', browse_instance.id)], context=context)
            if len(mapping_ids) > 0:
                mapping = mapping_obj.browse(cr, uid, mapping_ids[0], context=context)
                return mapping.mapping_value
        return "0"

    def create_counterpart(self, cr, uid, line):
        pool = pooler.get_pool(cr.dbname)
        # method to create counterpart line
        return line[:2] + \
               ["20750",
                "0",
                "0",
                line[5],
                line[6],
                line[7],
                line[9],
                line[8]] + line[10:]

    def create_subtotal(self, cr, uid, line_key, line_debit, line_functional_debit, counterpart_date, country_code, sequence_number):
        pool = pooler.get_pool(cr.dbname)
        # method to create subtotal + counterpart line
        if len(line_key) > 2 and line_debit != 0.0 and line_functional_debit != 0.0:
            return [["01",
                     country_code,
                     line_key[0],
                     "0",
                     "0",
                     counterpart_date,
                     line_key[1],
                     round(line_debit / line_functional_debit, 8),
                     line_debit > 0 and round(line_debit, 2) or "",
                     line_debit < 0 and round(-line_debit, 2) or "",
                     sequence_number,
                     "",
                     "Subtotal - " + line_key[0] + " - " + line_key[1] + " - " + line_key[2],
                     "0",
                     counterpart_date,
                     "0"]
                    ,["01",
                      country_code,
                      "20750",
                      "0",
                      "0",
                      counterpart_date,
                      line_key[1],
                      round(line_debit / line_functional_debit, 8),
                      line_debit < 0 and round(-line_debit, 2) or "",
                      line_debit > 0 and round(line_debit, 2) or "",
                      sequence_number,
                      "",
                      "Automatic counterpart for " + line_key[0] + " - " + line_key[1] + " - " + line_key[2],
                      "0",
                      counterpart_date,
                      "0"]]

    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)

        first_header = ['Proprietary Instance',
                        'Journal Code',
                        'Entry Sequence',
                        'Description',
                        'Reference',
                        'Document Date',
                        'Posting Date',
                        'Period',
                        'G/L Account',
                        'Destination',
                        'Cost Centre',
                        'Funding Pool',
                        'Third Parties',
                        'Booking Debit',
                        'Booking Credit',
                        'Booking Currency',
                        'Functional Debit',
                        'Functional Credit',
                        'Functional Currency',
                        'Exchange Rate']

        # Initialize lists: one for the first report...
        first_result_lines = []
        # ...one for the second report...
        second_result_lines = []
        # ...and subdivisions for the third report.
        third_report = []
        account_lines = []
        account_lines_debit = {}
        account_lines_functional_debit = {}
        # General variables
        period = pool.get('account.period').browse(cr, uid, data['form']['period_id'])
        period_name = period and period.code or "0"
        counterpart_date = period and period.date_stop and \
                           datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').date().strftime('%d/%m/%Y') or ""
        integration_ref = "0"
        country_code = "0"
        move_prefix = "0"
        if len(data['form']['instance_ids']) > 0:
            parent_instance = pool.get('msf.instance').browse(cr, uid, data['form']['instance_ids'][0], context=context)
            if parent_instance:
                country_code = self.translate_country(cr, uid, pool, parent_instance)
                if period and period.date_start:
                    integration_ref = parent_instance.code[:2] + period.date_start[5:7]
                    move_prefix = parent_instance.move_prefix[:2]

        move_line_ids = pool.get('account.move.line').search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                                       ('instance_id', 'in', data['form']['instance_ids']),
                                                                       ('account_id.is_analytic_addicted', '=', False),
                                                                       ('analytic_distribution_id', '=', False),
                                                                       ('journal_id.type', 'not in', ['hq', 'migration'])], context=context)
        for move_line in pool.get('account.move.line').browse(cr, uid, move_line_ids, context=context):
            journal = move_line.journal_id
            account = move_line.account_id
            currency = move_line.currency_id
            func_currency = move_line.functional_currency_id
            rate = "0.00"
            if currency and func_currency:
                cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(move_line.functional_currency_id.id, move_line.date))
                if cr.rowcount:
                    func_rate = cr.fetchall()[0][0]
                cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(currency.id, move_line.date))
                if cr.rowcount:
                    curr_rate = cr.fetchall()[0][0]
                if func_rate != 0.00:
                    rate = round(1 / curr_rate / func_rate, 5)
            # For first report: as if
            formatted_data = [move_line.instance_id and move_line.instance_id.code or "",
                              journal and journal.code or "",
                              move_line.move_id and move_line.move_id.name or "",
                              move_line.name,
                              move_line.ref,
                              datetime.datetime.strptime(move_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              datetime.datetime.strptime(move_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              move_line.period_id and move_line.period_id.code or "",
                              account and account.code + " " + account.name,
                              "",
                              "",
                              "",
                              move_line.partner_txt,
                              round(move_line.debit_currency, 2),
                              round(move_line.credit_currency, 2),
                              currency and currency.name or "",
                              round(move_line.debit, 2),
                              round(move_line.credit, 2),
                              func_currency and func_currency.name or "",
                              rate]
            first_result_lines.append(formatted_data)

            # For third report: add to corresponding sub
            if not account.shrink_entries_for_hq:
                expat_employee = "0"
                # Expat employees are the only third party in this report
                if move_line.partner_txt and move_line.employee_id and move_line.employee_id.employee_type == 'ex':
                    expat_employee = move_line.partner_txt[:5]
                other_formatted_data = ["01",
                                        country_code,
                                        account and account.code or "0",
                                        "0",
                                        "0",
                                        move_line.date and datetime.datetime.strptime(move_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y') or "0",
                                        currency and currency.name or "0",
                                        rate,
                                        move_line.debit_currency != 0.0 and round(move_line.debit_currency, 2) or "",
                                        move_line.credit_currency != 0.0 and round(move_line.credit_currency, 2) or "",
                                        move_line.move_id and move_line.move_id.name or "0",
                                        "",
                                        move_line.name or "0",
                                        expat_employee,
                                        move_line.document_date and datetime.datetime.strptime(move_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y') or "0",
                                        move_line.ref or "0"]
                account_lines.append(other_formatted_data)
            else:
                if (account.code, currency.name, period_name) not in account_lines_debit:
                    account_lines_debit[(account.code, currency.name, period_name)] = 0.0
                    account_lines_functional_debit[(account.code, currency.name, period_name)] = 0.0
                account_lines_debit[(account.code, currency.name, period_name)] += (move_line.debit_currency - move_line.credit_currency)
                account_lines_functional_debit[(account.code, currency.name, period_name)] += (move_line.debit - move_line.credit)

        # UFTP-375: Do not include FREE1 and FREE2 analytic lines
        analytic_line_ids = pool.get('account.analytic.line').search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                                               ('instance_id', 'in', data['form']['instance_ids']),
                                                                               ('journal_id.type', 'not in', ['hq', 'engagement', 'migration']),
                                                                               ('account_id.category', 'not in', ['FREE1', 'FREE2'])], context=context)
        for analytic_line in pool.get('account.analytic.line').browse(cr, uid, analytic_line_ids, context=context):
            journal = analytic_line.move_id and analytic_line.move_id.journal_id
            account = analytic_line.general_account_id
            currency = analytic_line.currency_id
            func_currency = analytic_line.move_id.functional_currency_id
            rate = ""
            if func_currency:
                cr.execute("SELECT rate FROM res_currency_rate WHERE currency_id = %s AND name <= %s ORDER BY name desc LIMIT 1" ,(currency.id, analytic_line.date))
                if cr.rowcount:
                    rate = round(1 / cr.fetchall()[0][0], 5)
            # For first report: as is
            formatted_data = [analytic_line.instance_id and analytic_line.instance_id.code or "",
                              analytic_line.journal_id and analytic_line.journal_id.code or "",
                              analytic_line.move_id and analytic_line.move_id.move_id and analytic_line.move_id.move_id.name or "",
                              analytic_line.name or "",
                              analytic_line.ref or "",
                              datetime.datetime.strptime(analytic_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              analytic_line.period_id and analytic_line.period_id.code or "",
                              account and account.code + " " + account.name or "",
                              analytic_line.destination_id and analytic_line.destination_id.code or "",
                              analytic_line.cost_center_id and analytic_line.cost_center_id.code or "",
                              analytic_line.account_id and analytic_line.account_id.code or "",
                              analytic_line.partner_txt or "",
                              analytic_line.amount_currency > 0 and "0.00" or round(-analytic_line.amount_currency, 2),
                              analytic_line.amount_currency > 0 and round(analytic_line.amount_currency, 2) or "0.00",
                              currency and currency.name or "",
                              analytic_line.amount > 0 and "0.00" or round(-analytic_line.amount, 2),
                              analytic_line.amount > 0 and round(analytic_line.amount, 2) or "0.00",
                              func_currency and func_currency.name or "",
                              rate]
            first_result_lines.append(formatted_data)

            # Add to second report (expenses only)
            other_formatted_data = [integration_ref ,
                                    analytic_line.document_date and datetime.datetime.strptime(analytic_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y') or "0",
                                    "0",
                                    "0",
                                    analytic_line.cost_center_id and analytic_line.cost_center_id.code or "0",
                                    "1",
                                    account and account.code + " " + account.name or "0",
                                    currency and currency.name or "0",
                                    analytic_line.amount_currency and round(-analytic_line.amount_currency, 2) or "0.00",
                                    "0",
                                    rate,
                                    analytic_line.date and datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y') or "0",
                                    analytic_line.move_id and analytic_line.move_id.move_id and analytic_line.move_id.move_id.name or "0",
                                    "0",
                                    analytic_line.name or "0",
                                    analytic_line.ref or "0",
                                    analytic_line.destination_id and analytic_line.destination_id.code or "0"]
            second_result_lines.append(other_formatted_data)

        first_result_lines = sorted(first_result_lines, key=lambda line: line[2])
        first_report = [first_header] + first_result_lines

        second_report = sorted(second_result_lines, key=lambda line: line[12])

        for line in sorted(account_lines, key=lambda line: line[10]):
            third_report.append(line)
            third_report.append(self.create_counterpart(cr, uid, line))

        sequence_index = 1
        for key in sorted(account_lines_debit.iterkeys(), key=lambda tuple: tuple[0]):
            # create the sequence number for those lines
            sequence_number = move_prefix + "-" + \
                              period.date_start[5:7] + "-" + \
                              period.date_start[:4] + "-" + \
                              key[0] + "-" + \
                              key[1]

            subtotal_lines = self.create_subtotal(cr, uid, key,
                                                  account_lines_debit[key],
                                                  account_lines_functional_debit[key],
                                                  counterpart_date,
                                                  country_code,
                                                  sequence_number)
            if subtotal_lines:
                third_report += subtotal_lines

        zip_buffer = StringIO.StringIO()
        first_fileobj = NamedTemporaryFile('w+b', delete=False)
        second_fileobj = NamedTemporaryFile('w+b', delete=False)
        third_fileobj = NamedTemporaryFile('w+b', delete=False)
        writer = csv.writer(first_fileobj, quoting=csv.QUOTE_ALL)
        for line in first_report:
            writer.writerow(map(self._enc,line))
        first_fileobj.close()
        writer = csv.writer(second_fileobj, quoting=csv.QUOTE_ALL)
        for line in second_report:
            writer.writerow(map(self._enc,line))
        second_fileobj.close()
        writer = csv.writer(third_fileobj, quoting=csv.QUOTE_ALL)
        for line in third_report:
            line.pop()
            line.pop()
            writer.writerow(map(self._enc,line))
        third_fileobj.close()
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        out_zipfile.write(first_fileobj.name, "%sRaw_Data.csv" % (integration_ref and integration_ref+'_' or ''), zipfile.ZIP_DEFLATED)
        out_zipfile.write(second_fileobj.name, "%sUp_Expenses.csv" % (integration_ref and integration_ref+'_' or ''), zipfile.ZIP_DEFLATED)
        out_zipfile.write(third_fileobj.name, "%sUp_Balances.csv" % (integration_ref and integration_ref+'_' or ''), zipfile.ZIP_DEFLATED)
        out_zipfile.close()
        out = zip_buffer.getvalue()
        os.unlink(first_fileobj.name)
        os.unlink(second_fileobj.name)
        os.unlink(third_fileobj.name)
        return (out, 'zip')

hq_report_oca('report.hq.oca', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
