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

class report_hq_export(report_sxw.report_sxw):
            
    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)
    
    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st
    
    def create_counterpart(self, cr, uid, line_key, line_debit, counterpart_date, period_name):
        pool = pooler.get_pool(cr.dbname)
        # method to create counterpart line
        if len(line_key) > 3 and line_debit != 0.0:
            journal = pool.get('account.journal').browse(cr, uid, line_key[1])
            currency = pool.get('res.currency').browse(cr, uid, line_key[2])
            return [journal.instance_id and journal.instance_id.code or "",
                    line_key[0],
                    "",
                    line_key[3],
                    "",
                    counterpart_date,
                    counterpart_date,
                    period_name,
                    "10100055 - Buffer Account",
                    "",
                    "",
                    "",
                    line_debit > 0 and "0.00" or round(-line_debit, 2),
                    line_debit > 0 and round(line_debit, 2) or "0.00",
                    currency.name]
    
    def create_subtotal(self, cr, uid, line_key, line_debit, counterpart_date, period_name):
        pool = pooler.get_pool(cr.dbname)
        # method to create subtotal + counterpart line
        if len(line_key) > 3 and line_debit != 0.0:
            account = pool.get('account.account').browse(cr, uid, line_key[3])
            journal = pool.get('account.journal').browse(cr, uid, line_key[1])
            currency = pool.get('res.currency').browse(cr, uid, line_key[2])
            return [[journal.instance_id and journal.instance_id.code or "",
                     journal.code,
                     "",
                     "",
                     "",
                     counterpart_date,
                     counterpart_date,
                     period_name,
                     account.code + " " + account.name,
                     "",
                     "",
                     "",
                     line_debit > 0 and round(line_debit, 2) or "0.00",
                     line_debit > 0 and "0.00" or round(-line_debit, 2),
                     currency.name],
                    [journal.instance_id and journal.instance_id.code or "",
                     journal.code,
                     "",
                     "",
                     "",
                     counterpart_date,
                     counterpart_date,
                     period_name,
                     "10100055 - Buffer Account",
                     "",
                     "",
                     "",
                     line_debit > 0 and "0.00" or round(-line_debit, 2),
                     line_debit > 0 and round(line_debit, 2) or "0.00",
                     currency.name]]
        
    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        # Create the header
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
                        'Functional Currency']
        
        second_header = ['Proprietary Instance',
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
                         'Third Parties',
                         'Booking Debit',
                         'Booking Credit',
                         'Booking Currency']
        
        # Initialize lists: one for the first report...
        first_result_lines = []
        # ...and subdivisions for the second report.
        second_result_lines = []
        main_lines = {}
        main_lines_debit = {}
        account_lines_debit = {}
        
        
        move_line_ids = pool.get('account.move.line').search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                                       ('instance_id', 'in', data['form']['instance_ids']),
                                                                       ('analytic_distribution_id', '=', False),
                                                                       ('journal_id.type', 'not in', ['hq', 'cur_adj', 'inkind'])], context=context)
        
        for move_line in pool.get('account.move.line').browse(cr, uid, move_line_ids, context=context):
            journal = move_line.journal_id
            account = move_line.account_id
            currency = move_line.currency_id
            # For first report: as if
            formatted_data = [move_line.instance_id and move_line.instance_id.code or "",
                              journal and journal.code or "",
                              move_line.move_id and move_line.move_id.name or "",
                              move_line.name,
                              move_line.ref,
                              datetime.datetime.strptime(move_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              datetime.datetime.strptime(move_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              move_line.period_id and move_line.period_id.code or "",
                              account and account.code + " " + account.name or "",
                              "",
                              "",
                              "",
                              move_line.partner_txt,
                              round(move_line.debit_currency, 2),
                              round(move_line.credit_currency, 2),
                              currency and currency.name or "",
                              round(move_line.debit, 2),
                              round(move_line.credit, 2),
                              move_line.functional_currency_id and move_line.functional_currency_id.name or ""]
            first_result_lines.append(formatted_data)
            
            # For second report: add to corresponding sub
            if journal.type in ['correction', 'intermission'] or account.is_settled_at_hq:
                if (journal.code, journal.id, currency.id, "") not in main_lines:
                    main_lines[(journal.code, journal.id, currency.id, "")] = []
                    main_lines_debit[(journal.code, journal.id, currency.id, "")] = 0.0
                main_lines[(journal.code, journal.id, currency.id, "")].append(formatted_data[:11] + formatted_data[12:16])
                main_lines_debit[(journal.code, journal.id, currency.id, "")] += (move_line.debit_currency - move_line.credit_currency)
            else:
                if (account.code, journal.id, currency.id, account.id) not in account_lines_debit:
                    account_lines_debit[(account.code, journal.id, currency.id, account.id)] = 0.0
                account_lines_debit[(account.code, journal.id, currency.id, account.id)] += (move_line.debit_currency - move_line.credit_currency)
                            
                            
                            
        cur_adj_journal_ids = pool.get('account.journal').search(cr, uid, [('type', '=', 'cur_adj')], context=context)
        ana_cur_journal_ids = []
        for journal in pool.get('account.journal').browse(cr, uid, cur_adj_journal_ids, context=context):
            if journal.analytic_journal_id and journal.analytic_journal_id.id not in ana_cur_journal_ids:
                ana_cur_journal_ids.append(journal.analytic_journal_id.id)
        
        analytic_line_ids = pool.get('account.analytic.line').search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                                               ('instance_id', 'in', data['form']['instance_ids']),
                                                                               ('journal_id.type', 'not in', ['hq', 'engagement', 'inkind']),
                                                                               ('journal_id', 'not in', ana_cur_journal_ids)], context=context)
        for analytic_line in pool.get('account.analytic.line').browse(cr, uid, analytic_line_ids, context=context):
            journal = analytic_line.move_id and analytic_line.move_id.journal_id
            account = analytic_line.general_account_id
            currency = analytic_line.currency_id
            # For first report: as is
            formatted_data = [analytic_line.instance_id and analytic_line.instance_id.code or "",
                              analytic_line.journal_id and analytic_line.journal_id.code or "",
                              analytic_line.move_id and analytic_line.move_id.move_id and analytic_line.move_id.move_id.name or "",
                              analytic_line.name,
                              analytic_line.ref,
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
                              analytic_line.functional_currency_id and analytic_line.functional_currency_id.name or ""]
            first_result_lines.append(formatted_data)
            
            # For second report: add to regular lines
            line_name = ""
            if journal.type == 'cash':
                line_name = "Tresorerie des missions cash " + journal.code + " - Contrepartie compte d'expense"
            elif journal.type == 'bank':
                line_name = "Tresorerie des missions banque " + journal.code + " - Contrepartie compte d'expense"
            elif journal.type == 'cheque':
                line_name = "Tresorerie des missions cheque " + journal.code + " - Contrepartie compte d'expense"
            elif account.user_type and account.user_type.code == 'payable':
                line_name = "Local A/P - Contrepartie compte d'expense"
            elif account.user_type and account.user_type.code == 'receivable':
                line_name = "Local A/R - Contrepartie compte d'expense"
            elif account.accrual_account:
                line_name = "Local accrual - Contrepartie compte d'expense"
            if (journal.code, journal.id, currency.id, line_name) not in main_lines:
                main_lines[(journal.code, journal.id, currency.id, line_name)] = []
                main_lines_debit[(journal.code, journal.id, currency.id, line_name)] = 0.0
            main_lines[(journal.code, journal.id, currency.id, line_name)].append(formatted_data[:11] + formatted_data[12:16])
            main_lines_debit[(journal.code, journal.id, currency.id, line_name)] -= analytic_line.amount_currency
        
        first_result_lines = sorted(first_result_lines, key=lambda line: line[2])
        first_report = [first_header] + first_result_lines
        
        # Regroup second report lines
        period = pool.get('account.period').browse(cr, uid, data['form']['period_id'])
        counterpart_date = period and period.date_stop and \
                           datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').date().strftime('%d/%m/%Y') or ""
        period_name = period and period.code or ""
        
        for key in sorted(main_lines.iterkeys(), key=lambda tuple: tuple[0]):
            second_result_lines += sorted(main_lines[key], key=lambda line: line[2])
            counterpart_line = self.create_counterpart(cr, uid, key,
                                                       main_lines_debit[key],
                                                       counterpart_date,
                                                       period_name)
            if counterpart_line:
                second_result_lines.append(counterpart_line)
        
        for key in sorted(account_lines_debit.iterkeys(), key=lambda tuple: tuple[0]):
            subtotal_lines = self.create_subtotal(cr, uid, key,
                                                  account_lines_debit[key],
                                                  counterpart_date,
                                                  period_name)
            if subtotal_lines:
                second_result_lines += subtotal_lines
        
        second_report = [second_header] + second_result_lines
        
        # Write lines as exported
#        pool.get('account.move.line').write(cr, uid, move_line_ids, {'exported': True}, context=context)
#        pool.get('account.analytic.line').write(cr, uid, analytic_line_ids, {'exported': True}, context=context)
#        
        
        # file names
        prefix = ""
        for instance in pool.get('msf.instance').browse(cr, uid, data['form']['instance_ids'], context=context):
            if instance.level == 'coordo':
                prefix += instance.top_cost_center_id and instance.top_cost_center_id.code or "xxx"
                break
        prefix += "_"
        period = pool.get('account.period').browse(cr, uid, data['form']['period_id'], context=context)
        if period and period.date_start:
            prefix += datetime.datetime.strptime(period.date_start, '%Y-%m-%d').date().strftime('%Y%m')
        else:
            prefix += "xxxxxx"
        prefix += "_"
        
        zip_buffer = StringIO.StringIO()
        first_fileobj = NamedTemporaryFile('w+b', delete=False)
        second_fileobj = NamedTemporaryFile('w+b', delete=False)
        writer = csv.writer(first_fileobj, quoting=csv.QUOTE_ALL)
        for line in first_report:
            writer.writerow(map(self._enc,line))
        first_fileobj.close()
        writer = csv.writer(second_fileobj, quoting=csv.QUOTE_ALL)
        for line in second_report:
            writer.writerow(map(self._enc,line))
        second_fileobj.close()
        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        out_zipfile.write(first_fileobj.name, prefix + "raw data UF export.csv", zipfile.ZIP_DEFLATED)
        out_zipfile.write(second_fileobj.name, prefix + "formatted data AX import.csv", zipfile.ZIP_DEFLATED)
        out_zipfile.close()
        out = zip_buffer.getvalue()
        os.unlink(first_fileobj.name)
        os.unlink(second_fileobj.name)
        return (out, 'zip')

report_hq_export('report.hq.export', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
