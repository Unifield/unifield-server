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
from osv import osv
from tools.translate import _
from time import strptime

from report import report_sxw


class hq_report_oca(report_sxw.report_sxw):

    def __init__(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        report_sxw.report_sxw.__init__(self, name, table, rml=rml, parser=parser, header=header, store=store)

    def _enc(self, st):
        if isinstance(st, unicode):
            return st.encode('utf8')
        return st

    def translate_account(self, cr, uid, pool, browse_account, context=None):
        """
        Returns the "HQ System Account Code" of the account in parameter if it exists, else returns the standard account code
        """
        if context is None:
            context = {}
        mapping_obj = pool.get('account.export.mapping')
        if browse_account:
            mapping_ids = mapping_obj.search(cr, uid, [('account_id', '=', browse_account.id)], context=context)
            if len(mapping_ids) > 0:
                mapping = mapping_obj.browse(cr, uid, mapping_ids[0], fields_to_fetch=['mapping_value'], context=context)
                return mapping.mapping_value
            else:
                return browse_account.code
        return ""

    def translate_country(self, cr, uid, pool, browse_instance, context=None):
        """
        Returns the "HQ System Country Code" of the instance in parameter if it exists, else returns 0
        """
        if context is None:
            context = {}
        mapping_obj = pool.get('country.export.mapping')
        if browse_instance:
            mapping_ids = mapping_obj.search(cr, uid, [('instance_id', '=', browse_instance.id)], context=context)
            if len(mapping_ids) > 0:
                mapping = mapping_obj.browse(cr, uid, mapping_ids[0], context=context)
                return mapping.mapping_value
        return "0"

    def rmv_spec_char(self, field_value):
        if not field_value:
            return field_value
        res = field_value
        field_ascii_arr = [ord(x) for x in field_value]
        for i, _ in enumerate(field_ascii_arr[:-1]):
            pair = field_ascii_arr[i:i + 2]
            if pair[0] == 20 and pair[1] > 126:
                res = res[:i] + res[i+1:]
        return res

    def create_subtotal(self, cr, uid, line_key, line_debit, counterpart_date, period, department_info, field_activity, context=None):
        if context is None:
            context = {}
        pool = pooler.get_pool(cr.dbname)
        curr_obj = pool.get('res.currency')
        rate_obj = pool.get('res.currency.rate')
        # method to create subtotal + counterpart line
        period_code = period.code or ""
        if len(line_key) > 1 and abs(line_debit) > 10**-3:
            currency = curr_obj.browse(cr, uid, line_key[1], context=context)
            # rate at the first day of the selected period
            rate = 0
            rate_ids = rate_obj.search(cr, uid, [('currency_id', '=', currency.id), ('name', '<=', period.date_start)],
                                       order='name DESC', limit=1, context=context)
            if rate_ids:
                rate = rate_obj.browse(cr, uid, rate_ids[0], fields_to_fetch=['rate'], context=context).rate
            # Description for the line
            if line_key[0] == "1000 0000":
                description = "Mvts_BANK_" + period_code + "_" + currency.name
            elif line_key[0] == "1000 0001":
                description = "Mvts_CASH_" + period_code + "_" + currency.name
            else:
                mapping_obj = pool.get('account.export.mapping')
                account_values = ""
                mapping_ids = mapping_obj.search(cr, uid, [('mapping_value', '=', line_key[0])], context=context)
                for mapping in mapping_obj.browse(cr, uid, mapping_ids, fields_to_fetch=['account_id'], context=context):
                    if account_values != "":
                        account_values += "-"
                    account_values += mapping.account_id.code
                description = "Mvts_" + account_values + period_code + "_" + currency.name

            return [["",
                     "",
                     "",
                     description,
                     "",
                     counterpart_date,
                     counterpart_date,
                     period_code,
                     line_key[0],
                     "",
                     department_info,
                     "",
                     "",
                     "",
                     rate,
                     line_debit > 0 and round(line_debit, 2) or "0.00",
                     line_debit > 0 and "0.00" or round(-line_debit, 2),
                     currency.name,
                     field_activity]]

    def create(self, cr, uid, ids, data, context=None):
        if context is None:
            context = {}
        # data should always be in English whatever the language settings
        context.update({'lang': 'en_MF'})
        pool = pooler.get_pool(cr.dbname)
        rate_obj = pool.get('res.currency.rate')
        period_obj = pool.get('account.period')
        inst_obj = pool.get('msf.instance')
        aml_obj = pool.get('account.move.line')
        aal_obj = pool.get('account.analytic.line')
        rates = {}  # store the rates already computed

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
                         'Employee Id',
                         'Exchange rate',
                         'Booking Debit',
                         'Booking Credit',
                         'Booking Currency',
                         'Field Activity']

        period = period_obj.browse(cr, uid, data['form']['period_id'], context=context)

        # list the journal types for which the rate used will always be 1
        # i.e. REVAL, Curr. Adjustment, and Accrual
        no_rate_journal_types = ['revaluation', 'cur_adj', 'accrual']
        no_rate_analytic_journal_types = ['revaluation', 'cur_adj', 'general']  # Analytic Accrual Journals have the type "general"

        # Initialize lists: one for the first report...
        first_result_lines = []
        # ...and subdivisions for the second report.
        second_result_lines = []
        main_lines = {}
        account_lines_debit = {}
        # Get department code filled in through the country code mapping
        department_info = ""
        field_activity = ""  # always empty
        parent_instance = False
        if len(data['form']['instance_ids']) > 0:
            parent_instance = inst_obj.browse(cr, uid, data['form']['instance_ids'][0], context=context)
            if parent_instance:
                department_info = self.translate_country(cr, uid, pool, parent_instance, context=context)

        # UFTP-375: Add export all/previous functionality
        selection = data['form'].get('selection', False)
        to_export = ['f'] # Default export value for exported field on analytic/move lines
        if not selection:
            raise osv.except_osv(_('Error'), _('No selection value for lines to select.'))
        if selection == 'all':
            to_export = ['f', 't']
        elif selection == 'unexported':
            to_export = ['f']
        else:
            raise osv.except_osv(_('Error'), _('Wrong value for selection: %s.') % (selection,))

        move_line_ids = aml_obj.search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                 ('instance_id', 'in', data['form']['instance_ids']),
                                                 ('account_id.is_analytic_addicted', '=', False),
                                                 ('journal_id.type', 'not in', ['migration', 'hq']),
                                                 ('exported', 'in', to_export)],
                                       context=context)

        nb_move_line = len(move_line_ids)
        move_line_count = 0
        if 'background_id' in context:
            bg_id = context['background_id']
        else:
            bg_id = None

        move_share = 0.4  # 40% of the total process

        for move_line in aml_obj.browse(cr, uid, move_line_ids, context=context):
            if move_line.move_id.state != 'posted':  # only posted move lines are kept
                move_line_count += 1
                continue
            journal = move_line.journal_id
            account = move_line.account_id
            currency = move_line.currency_id
            # For the first report:
            round_debit_booking = round(move_line.debit_currency or 0.0, 2)
            round_credit_booking = round(move_line.credit_currency or 0.0, 2)
            round_debit_fctal = round(move_line.debit or 0.0, 2)
            round_credit_fctal = round(move_line.credit or 0.0, 2)
            name = self.rmv_spec_char(move_line.name)
            ref = self.rmv_spec_char(move_line.ref)
            partner_txt = self.rmv_spec_char(move_line.partner_txt)
            formatted_data = [move_line.instance_id and move_line.instance_id.code or "",
                              journal and journal.code or "",
                              move_line.move_id and move_line.move_id.name or "",
                              name,
                              ref,
                              datetime.datetime.strptime(move_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              datetime.datetime.strptime(move_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              move_line.period_id and move_line.period_id.code or "",
                              self.translate_account(cr, uid, pool, account, context=context),
                              account and account.code + " " + account.name,
                              "",
                              "",
                              "",
                              partner_txt,
                              round_debit_booking,
                              round_credit_booking,
                              currency and currency.name or "",
                              round_debit_fctal,
                              round_credit_fctal,
                              move_line.functional_currency_id and move_line.functional_currency_id.name or ""]
            first_result_lines.append(formatted_data)

            # For the second report:
            # exclude In-kind Donations, OD-Extra Accounting entries, and lines with zero amount from the "formatted data" file
            zero_move_line = not round_debit_booking and not round_credit_booking and not round_debit_fctal and not round_credit_fctal
            if move_line.journal_id.type not in ['inkind', 'extra'] and not zero_move_line:
                if not account.shrink_entries_for_hq:
                    # data for the "Employee Id" column
                    employee_id = ''
                    if move_line.employee_id and move_line.employee_id.employee_type == 'ex':  # expat staff
                        employee_id = move_line.employee_id.identification_id or ''
                    # data for the columns: Exchange rate, Booking Debit, Booking Credit, Booking Currency
                    exchange_rate = 0
                    booking_amounts = [round_debit_booking, round_credit_booking]
                    booking_curr = formatted_data[16:17]
                    if move_line.journal_id.type in no_rate_journal_types:
                        # use 1 as exchange rate and display the functional values in the "booking" columns
                        exchange_rate = 1
                        booking_amounts = [round_debit_fctal, round_credit_fctal]
                        booking_curr = formatted_data[19:20]
                    # automatic corrections
                    elif move_line.journal_id.type == 'correction' and (move_line.corrected_line_id or move_line.reversal_line_id):
                        # If there are several levels of correction use the last one
                        corr_aml = move_line.corrected_line_id or move_line.reversal_line_id  # JI corrected or reversed
                        initial_id = -1
                        final_id = -2
                        while initial_id != final_id:
                            initial_id = corr_aml.id
                            # check if the corrected line corrects another line
                            corr_aml = corr_aml.corrected_line_id or corr_aml
                            final_id = corr_aml.id
                        # rate of the original corrected entry
                        if currency.id not in rates:
                            rates[currency.id] = {}
                        if corr_aml.date not in rates[currency.id]:
                            rate = 0
                            rate_ids = rate_obj.search(cr, uid, [('currency_id', '=', currency.id), ('name', '<=', corr_aml.date)],
                                                       order='name DESC', limit=1, context=context)
                            if rate_ids:
                                rate = rate_obj.browse(cr, uid, rate_ids[0], fields_to_fetch=['rate'], context=context).rate
                            rates[currency.id][corr_aml.date] = rate
                        exchange_rate = rates[currency.id][corr_aml.date]
                    # other lines
                    elif currency:
                        # rate of the period selected
                        if currency.id not in rates:
                            rates[currency.id] = {}
                        if period.date_start not in rates[currency.id]:
                            rate = 0
                            rate_ids = rate_obj.search(cr, uid, [('currency_id', '=', currency.id), ('name', '<=', period.date_start)],
                                                       order='name DESC', limit=1, context=context)
                            if rate_ids:
                                rate = rate_obj.browse(cr, uid, rate_ids[0], fields_to_fetch=['rate'], context=context).rate
                            rates[currency.id][period.date_start] = rate
                        exchange_rate = rates[currency.id][period.date_start]

                    if (journal.code, journal.id, currency.id) not in main_lines:
                        main_lines[(journal.code, journal.id, currency.id)] = []
                    main_lines[(journal.code, journal.id, currency.id)].append(formatted_data[:9] + [formatted_data[10]] +
                                                                               [department_info] + [formatted_data[11]] +
                                                                               [formatted_data[13]] + [employee_id] +
                                                                               [exchange_rate] + booking_amounts +
                                                                               booking_curr + [field_activity])
                else:
                    translated_account_code = self.translate_account(cr, uid, pool, account, context=context)
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

        analytic_line_ids = aal_obj.search(cr, uid, [('period_id', '=', data['form']['period_id']),
                                                     ('instance_id', 'in', data['form']['instance_ids']),
                                                     ('journal_id.type', 'not in', ['migration', 'hq', 'engagement']),
                                                     ('account_id.category', 'not in', ['FREE1', 'FREE2']),
                                                     ('exported', 'in', to_export)], context=context)
        nb_analytic_line = len(analytic_line_ids)
        analytic_line_count = 0

        analytic_share = 0.5  # 50% of the total process

        for analytic_line in aal_obj.browse(cr, uid, analytic_line_ids, context=context):
            # restrict to analytic lines coming from posted move lines
            if analytic_line.move_state != 'posted':
                analytic_line_count += 1
                continue
            journal = analytic_line.move_id and analytic_line.move_id.journal_id
            account = analytic_line.general_account_id
            currency = analytic_line.currency_id
            cost_center_code = analytic_line.cost_center_id and analytic_line.cost_center_id.code or ""
            aji_period_id = analytic_line and analytic_line.period_id or False
            name = self.rmv_spec_char(analytic_line.name)
            ref = self.rmv_spec_char(analytic_line.ref)
            partner_txt = self.rmv_spec_char(analytic_line.partner_txt)

            # For the first report:
            round_aal_booking = round(analytic_line.amount_currency or 0.0, 2)
            round_aal_fctal = round(analytic_line.amount or 0.0, 2)
            formatted_data = [analytic_line.instance_id and analytic_line.instance_id.code or "",
                              analytic_line.journal_id and analytic_line.journal_id.code or "",
                              analytic_line.entry_sequence or analytic_line.move_id and analytic_line.move_id.move_id and analytic_line.move_id.move_id.name or "",
                              name or "",
                              ref or "",
                              datetime.datetime.strptime(analytic_line.document_date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              datetime.datetime.strptime(analytic_line.date, '%Y-%m-%d').date().strftime('%d/%m/%Y'),
                              aji_period_id and aji_period_id.code or "",
                              self.translate_account(cr, uid, pool, account, context=context),
                              account and account.code + " " + account.name or "",
                              analytic_line.destination_id and analytic_line.destination_id.code or "",
                              cost_center_code,
                              analytic_line.account_id and analytic_line.account_id.code or "",
                              partner_txt or "",
                              analytic_line.amount_currency > 0 and "0.00" or -round_aal_booking,
                              analytic_line.amount_currency > 0 and round_aal_booking or "0.00",
                              currency and currency.name or "",
                              analytic_line.amount > 0 and "0.00" or -round_aal_fctal,
                              analytic_line.amount > 0 and round_aal_fctal or "0.00",
                              analytic_line.functional_currency_id and analytic_line.functional_currency_id.name or ""]
            first_result_lines.append(formatted_data)

            # exclude In-kind Donations, OD-Extra Accounting entries, and lines with zero amount from the "formatted data" file
            zero_analytic_line = not round_aal_fctal and not round_aal_booking
            if analytic_line.journal_id.type not in ['inkind', 'extra'] and not zero_analytic_line:
                # format CC as: P + the 4 digits from the right
                cost_center = formatted_data[11] and "P%s" % formatted_data[11][-4:] or ""
                # data for the "Employee Id" column
                employee_id = ''
                if analytic_line.move_id and analytic_line.move_id.employee_id and analytic_line.move_id.employee_id.employee_type == 'ex':  # expat staff
                    employee_id = analytic_line.move_id.employee_id.identification_id or ''

                # data for the columns: Exchange rate, Booking Debit, Booking Credit, Booking Currency
                exchange_rate = 0
                booking_amounts = [analytic_line.amount_currency > 0 and "0.00" or -round_aal_booking,
                                   analytic_line.amount_currency > 0 and round_aal_booking or "0.00"]
                booking_curr = formatted_data[16:17]
                if analytic_line.journal_id.type in no_rate_analytic_journal_types:
                    # use 1 as exchange rate and display the functional values in the "booking" columns
                    exchange_rate = 1
                    booking_amounts = [analytic_line.amount > 0 and "0.00" or -round_aal_fctal,
                                       analytic_line.amount > 0 and round_aal_fctal or "0.00"]
                    booking_curr = formatted_data[19:20]
                # automatic corrections
                elif analytic_line.journal_id.type == 'correction' and (analytic_line.last_corrected_id or analytic_line.reversal_origin):
                    # If there are several levels of correction use the last one
                    corr_aal = analytic_line.last_corrected_id or analytic_line.reversal_origin  # AJI corrected or reversed
                    initial_id = -1
                    final_id = -2
                    while initial_id != final_id:
                        initial_id = corr_aal.id
                        # check if the corrected line corrects another line
                        corr_aal = corr_aal.last_corrected_id or corr_aal
                        final_id = corr_aal.id
                    # rate of the original corrected entry
                    if currency.id not in rates:
                        rates[currency.id] = {}
                    if corr_aal.date not in rates[currency.id]:
                        rate = 0
                        rate_ids = rate_obj.search(cr, uid, [('currency_id', '=', currency.id), ('name', '<=', corr_aal.date)],
                                                   order='name DESC', limit=1, context=context)
                        if rate_ids:
                            rate = rate_obj.browse(cr, uid, rate_ids[0], fields_to_fetch=['rate'], context=context).rate
                        rates[currency.id][corr_aal.date] = rate
                    exchange_rate = rates[currency.id][corr_aal.date]
                # other lines
                elif currency:
                    # rate of the period selected
                    if currency.id not in rates:
                        rates[currency.id] = {}
                    if period.date_start not in rates[currency.id]:
                        rate = 0
                        rate_ids = rate_obj.search(cr, uid, [('currency_id', '=', currency.id), ('name', '<=', period.date_start)],
                                                   order='name DESC', limit=1, context=context)
                        if rate_ids:
                            rate = rate_obj.browse(cr, uid, rate_ids[0], fields_to_fetch=['rate'], context=context).rate
                        rates[currency.id][period.date_start] = rate
                    exchange_rate = rates[currency.id][period.date_start]

                if (journal.code, journal.id, currency.id) not in main_lines:
                    main_lines[(journal.code, journal.id, currency.id)] = []
                main_lines[(journal.code, journal.id, currency.id)].append(formatted_data[:9] + [formatted_data[10]] +
                                                                           [department_info] + [cost_center] +
                                                                           [formatted_data[13]] + [employee_id] +
                                                                           [exchange_rate] + booking_amounts +
                                                                           booking_curr + [field_activity])

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

        counterpart_date = period and period.date_stop and \
            datetime.datetime.strptime(period.date_stop, '%Y-%m-%d').date().strftime('%d/%m/%Y') or ""

        # regroup second report lines
        for key in sorted(main_lines.iterkeys(), key=lambda tuple: tuple[0]):
            second_result_lines += sorted(main_lines[key], key=lambda line: line[2])

        for key in sorted(account_lines_debit.iterkeys(), key=lambda tuple: tuple[0]):
            # for entries "shrunk for HQ export"
            subtotal_lines = self.create_subtotal(cr, uid, key, account_lines_debit[key], counterpart_date, period,
                                                  department_info, field_activity, context=context)
            if subtotal_lines:
                second_result_lines += subtotal_lines

        self.shared_update_percent(cr, uid, pool, [bg_id],
                                   share=0.05, finished=True,
                                   already_done=move_share+analytic_share)

        second_report = [second_header] + second_result_lines

        # set prefix for file names
        mission_code = ''
        if parent_instance:
            mission_code = "%s" % parent_instance.code[:3]
        tm = strptime(period.date_start, '%Y-%m-%d')
        year = str(tm.tm_year)
        period_number = period and period.number and '%02d' % period.number or ''
        prefix = '%sY%sP%s_' % (mission_code, year, period_number)

        if data.get('output_file'):
            # report generated by auto export
            zip_buffer = data['output_file']
            in_memory = False
            out = ''
        else:
            # manual export
            zip_buffer = StringIO.StringIO()
            in_memory = True
        first_fileobj = NamedTemporaryFile('w+b', delete=False)
        second_fileobj = NamedTemporaryFile('w+b', delete=False)
        # for Raw data file: use double quotes for all entries
        writer = csv.writer(first_fileobj, quoting=csv.QUOTE_ALL, delimiter=",")
        for line in first_report:
            writer.writerow(map(self._enc, line))
        first_fileobj.close()
        # for formatted data file: use double quotes only for entries containing double quote or comma
        writer = csv.writer(second_fileobj, quoting=csv.QUOTE_MINIMAL, delimiter=",")
        for line in second_report:
            writer.writerow(map(self._enc, line))
        second_fileobj.close()

        out_zipfile = zipfile.ZipFile(zip_buffer, "w")
        out_zipfile.write(first_fileobj.name, prefix + "Raw data UF export.csv", zipfile.ZIP_DEFLATED)
        out_zipfile.write(second_fileobj.name, prefix + "formatted data D365 import.csv", zipfile.ZIP_DEFLATED)
        out_zipfile.close()
        if in_memory:
            out = zip_buffer.getvalue()
        os.unlink(first_fileobj.name)
        os.unlink(second_fileobj.name)

        # if manual export set period state as exported (no more auto export)
        if in_memory:
            cr.execute("UPDATE account_period_state SET auto_export_vi = 't' WHERE instance_id in %s AND period_id = %s", (tuple(data['form']['instance_ids']), data['form']['period_id']))

        # Mark lines as exported
        if move_line_ids:
            sql = """UPDATE account_move_line SET exported = 't' WHERE id in %s;"""
            cr.execute(sql, (tuple(move_line_ids),))
        if analytic_line_ids:
            sqltwo = """UPDATE account_analytic_line SET exported = 't' WHERE id in %s;"""
            cr.execute(sqltwo, (tuple(analytic_line_ids),))

        self.shared_update_percent(cr, uid, pool, [bg_id],
                                   share=0.02, finished=True,
                                   already_done=move_share+analytic_share+0.05)
        return (out, 'zip')

hq_report_oca('report.hq.oca', 'account.move.line', False, parser=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
