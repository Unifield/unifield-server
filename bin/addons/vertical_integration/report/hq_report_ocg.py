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


class hq_report_ocg(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st

    def translate_account(self, cr, uid, pool, browse_account, context={}):
        mapping_obj = pool.get('account.export.mapping')
        if browse_account:
            mapping_ids = mapping_obj.search(cr, uid, [('account_id', '=', browse_account.id)], context=context)
            if len(mapping_ids) > 0:
                mapping = mapping_obj.browse(cr, uid, mapping_ids[0], context=context)
                return mapping.mapping_value
            else:
                return browse_account.code
        return ""

    def create_subtotal(self, cr, uid, line_key, line_debit, counterpart_date, period_name, department_info):
        pool = pooler.get_pool(cr.dbname)
        # method to create subtotal + counterpart line
        if len(line_key) > 1 and abs(line_debit) > 10**-3:
            currency = pool.get('res.currency').browse(cr, uid, line_key[1])
            description = ""
            # Description for the line
            if line_key[0] == "1000 0000":
                description = "Mvts_BANK_" + period_name + "_" + currency.name
            elif line_key[0] == "1000 0001":
                description = "Mvts_CASH_" + period_name + "_" + currency.name
            else:
                mapping_obj = pool.get('account.export.mapping')
                account_values = ""
                mapping_ids = mapping_obj.search(cr, uid, [('mapping_value', '=', line_key[0])], context={})
                for mapping in mapping_obj.browse(cr, uid, mapping_ids, context={}):
                    if account_values != "":
                        account_values += "-"
                    account_values += mapping.account_id.code
                description = "Mvts_" + account_values + period_name + "_" + currency.name

            return [["", # US-20 was 'journal.instance_id.code' now breakdown account+ccy instead of account+journal+ccy
                     "",  # US-20 was 'journal.code' now breakdown account+ccy instead of account+journal+ccy
                     "",
                     description,
                     "",
                     counterpart_date,
                     counterpart_date,
                     period_name,
                     line_key[0],
                     "",
                     department_info,
                     "",
                     "",
                     line_debit > 0 and round(line_debit, 2) or "0.00",
                     line_debit > 0 and "0.00" or round(-line_debit, 2),
                     currency.name]]

    def _get_destination_code(self, analytic_line, context):
        """
        For the OCG-POC VI: returns the code of the default destination of the G/L account
        For the standard OCG VI: returns the code of the destination used on the AJI
        """
        if context is None:
            context = {}
        if context.get('ocg_poc'):
            dest = analytic_line.general_account_id.default_destination_id
        else:
            dest = analytic_line.destination_id
        return dest and dest.code or ""

    def create(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
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
                        'Unifield Account',
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
                         'Department',
                         'Cost Centre',
                         'Third Parties',
                         'Booking Debit',
                         'Booking Credit',
                         'Booking Currency',
                         'Field Activity']

        period = pool.get('account.period').browse(cr, uid, data['form']['period_id'])

        # Initialize lists: one for the first report...
        first_result_lines = []
        # ...and subdivisions for the second report.
        second_result_lines = []
        main_lines = {}
        account_lines_debit = {}
        # Get department info code: 3 first characters of main instance's code
        department_info = ""
        if len(data['form']['instance_ids']) > 0:
            parent_instance = pool.get('msf.instance').browse(cr, uid, data['form']['instance_ids'][0], context=context)
            if parent_instance:
                department = parent_instance.code[:3]
                department_info = department == 'CD1' and 'CD5' or department  # set "CD5" for "CD1" mission

        move_line_ids = pool.get('account.move.line').search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                                       ('instance_id', 'in', data['form']['instance_ids']),
                                                                       ('account_id.is_analytic_addicted', '=', False),
                                                                       ('journal_id.type', 'not in', ['migration', 'hq', 'cur_adj', 'inkind', 'extra'])], context=context)

        nb_move_line = len(move_line_ids)
        move_line_count = 0
        if 'background_id' in context:
            bg_id = context['background_id']
        else:
            bg_id = None

        # assume that this for loop is about 40% of the total treatment
        move_share = 0.4

        for move_line in pool.get('account.move.line').browse(cr, uid, move_line_ids, context=context):
            # UFTP-194: Just take posted move lines
            if move_line.move_id.state != 'posted':
                move_line_count += 1
                continue
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
                              self.translate_account(cr, uid, pool, account),
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
                              move_line.functional_currency_id and move_line.functional_currency_id.name or ""]
            first_result_lines.append(formatted_data)

            # For second report: add to corresponding sub
            # exclude lines with zero amount from the "formatted data" file
            zero_move_line = not move_line.debit_currency and not move_line.credit_currency and not move_line.debit and not move_line.credit
            if not zero_move_line:
                if not account.shrink_entries_for_hq:
                    if (journal.code, journal.id, currency.id) not in main_lines:
                        main_lines[(journal.code, journal.id, currency.id)] = []
                    main_lines[(journal.code, journal.id, currency.id)].append(formatted_data[:9] + [formatted_data[10]] + [department_info] + formatted_data[11:12] + formatted_data[13:17])
                else:
                    translated_account_code = self.translate_account(cr, uid, pool, account)
                    if (translated_account_code, currency.id) not in account_lines_debit:
                        account_lines_debit[(translated_account_code, currency.id)] = 0.0
                    account_lines_debit[(translated_account_code, currency.id)] += (move_line.debit_currency - move_line.credit_currency)

            move_line_count += 1
            if move_line_count % 30 == 0:
                # update percentage every 30 lines, not to do it too often
                percent = move_line_count / float(nb_move_line)
                self.shared_update_percent(cr, uid, pool, [bg_id],
                                           percent=percent, share=move_share)

        self.shared_update_percent(cr, uid, pool, [bg_id],
                                   share=move_share, finished=True)

        cur_adj_journal_ids = pool.get('account.journal').search(cr, uid, [('type', '=', 'cur_adj')], context=context)
        ana_cur_journal_ids = []
        for journal in pool.get('account.journal').browse(cr, uid, cur_adj_journal_ids, context=context):
            if journal.analytic_journal_id and journal.analytic_journal_id.id not in ana_cur_journal_ids:
                ana_cur_journal_ids.append(journal.analytic_journal_id.id)

        analytic_line_ids = pool.get('account.analytic.line').search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                                               ('instance_id', 'in', data['form']['instance_ids']),
                                                                               ('journal_id.type', 'not in', ['migration', 'hq', 'engagement', 'inkind', 'extra']),
                                                                               ('journal_id', 'not in', ana_cur_journal_ids)], context=context)
        nb_analytic_line = len(analytic_line_ids)
        analytic_line_count = 0

        # assume that this for loop is about 50% of the total treatment
        analytic_share = 0.5

        for analytic_line in pool.get('account.analytic.line').browse(cr, uid, analytic_line_ids, context=context):
            # Just take analytic lines that comes from posted move lines
            if analytic_line.move_state != 'posted':
                analytic_line_count += 1
                continue
            journal = analytic_line.move_id and analytic_line.move_id.journal_id
            account = analytic_line.general_account_id
            currency = analytic_line.currency_id
            cost_center_code = analytic_line.cost_center_id and analytic_line.cost_center_id.code or ""

            # US-1375: cancel US-817
            aji_period_id = analytic_line and analytic_line.period_id or False

            # For first report: as is
            formatted_data = [analytic_line.instance_id and analytic_line.instance_id.code or "",
                              analytic_line.journal_id and analytic_line.journal_id.code or "",
                              analytic_line.entry_sequence or analytic_line.move_id and analytic_line.move_id.move_id and analytic_line.move_id.move_id.name or "",
                              analytic_line.name or "",
                              analytic_line.ref or "",
                              datetime.datetime.strptime(analytic_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              aji_period_id and aji_period_id.code or "",
                              self.translate_account(cr, uid, pool, account),
                              #account and account.code,
                              account and account.code + " " + account.name or "",
                              self._get_destination_code(analytic_line, context),
                              cost_center_code,
                              analytic_line.account_id and analytic_line.account_id.code or "",
                              analytic_line.partner_txt or "",
                              analytic_line.amount_currency > 0 and "0.00" or round(-analytic_line.amount_currency, 2),
                              analytic_line.amount_currency > 0 and round(analytic_line.amount_currency, 2) or "0.00",
                              currency and currency.name or "",
                              analytic_line.amount > 0 and "0.00" or round(-analytic_line.amount, 2),
                              analytic_line.amount > 0 and round(analytic_line.amount, 2) or "0.00",
                              analytic_line.functional_currency_id and analytic_line.functional_currency_id.name or ""]
            first_result_lines.append(formatted_data)

            # exclude lines with zero amount from the "formatted data" file
            zero_analytic_line = not analytic_line.amount and not analytic_line.amount_currency
            if not zero_analytic_line:
                cost_center = formatted_data[11][:5] or " "
                field_activity = formatted_data[11][6:] or " "
                # UTP-1104: Hard code the fact that cc-intermission should appear as MI998 + SUPZZZ
                if cost_center_code == 'cc-intermission':
                    cost_center = 'MI998'
                    field_activity = 'SUPZZZ'
                if cost_center:
                    department_info = cost_center[:3] == 'CD1' and 'CD5' or cost_center[:3]  # set "CD5" for "CD1" CCs

                if (journal.code, journal.id, currency.id) not in main_lines:
                    main_lines[(journal.code, journal.id, currency.id)] = []
                main_lines[(journal.code, journal.id, currency.id)].append(formatted_data[:9] + [formatted_data[10]] +
                                                                           [department_info] + [cost_center] + formatted_data[13:17] +
                                                                           [field_activity])

            analytic_line_count += 1
            if analytic_line_count % 30 == 0:
                # update percentage every 30 lines, not to do it too often
                percent = analytic_line_count / float(nb_analytic_line)
                self.shared_update_percent(cr, uid, pool, [bg_id],
                                           percent=percent, share=analytic_share,
                                           already_done=move_share)

        self.shared_update_percent(cr, uid, pool, [bg_id],
                                   share=analytic_share, finished=True, already_done=move_share)

        first_result_lines = sorted(first_result_lines, key=lambda line: line[2])
        first_report = [first_header] + first_result_lines

        # Regroup second report lines
        counterpart_date = period and period.date_stop and \
            datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').date().strftime('%d/%m/%Y') or ""
        period_name = period and period.code or ""

        for key in sorted(main_lines.iterkeys(), key=lambda tuple: tuple[0]):
            second_result_lines += sorted(main_lines[key], key=lambda line: line[2])

        # get main instance code for department of subtotal lines and set "CD5" for "CD1" mission
        department_info = department == 'CD1' and 'CD5' or department
        for key in sorted(account_lines_debit.iterkeys(), key=lambda tuple: tuple[0]):
            subtotal_lines = self.create_subtotal(cr, uid, key,
                                                  account_lines_debit[key],
                                                  counterpart_date,
                                                  period_name,
                                                  department_info)
            if subtotal_lines:
                second_result_lines += subtotal_lines

        self.shared_update_percent(cr, uid, pool, [bg_id],
                                   share=0.05, finished=True,
                                   already_done=move_share+analytic_share)

        second_report = [second_header] + second_result_lines

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
        self.shared_update_percent(cr, uid, pool, [bg_id],
                                   share=0.02, finished=True,
                                   already_done=move_share+analytic_share+0.05)
        return (out, 'zip')

hq_report_ocg('report.hq.ocg', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
