#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from osv import fields
from tools.translate import _
from time import strftime
from tempfile import NamedTemporaryFile
from base64 import decodestring
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import threading
import pooler
import mx
from base import currency_date
from msf_doc_import import ACCOUNTING_IMPORT_JOURNALS
from spreadsheet_xml import SPECIAL_CHAR
import re


class msf_doc_import_accounting(osv.osv_memory):
    _name = 'msf.doc.import.accounting'

    _columns = {
        'date': fields.date(string="Date", required=True),
        'file': fields.binary(string="File", filters='*.xml, *.xls', required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'progression': fields.float(string="Progression", readonly=True),
        'message': fields.char(string="Message", size=256, readonly=True),
        'state': fields.selection([('draft', 'Created'), ('inprogress', 'In Progress'), ('error', 'Error'), ('done', 'Done')], string="State", readonly=True, required=True),
        'error_ids': fields.one2many('msf.doc.import.accounting.errors', 'wizard_id', "Errors", readonly=True),
    }

    _defaults = {
        'date': lambda *a: strftime('%Y-%m-%d'),
        'progression': lambda *a: 0.0,
        'state': lambda *a: 'draft',
        'message': lambda *a: _('Initialization…'),
    }

    def create_entries(self, cr, uid, ids, journal_id, context=None):
        """
        Create journal entry
        """
        # Checks
        if not context:
            context = {}
        # Browse all wizards
        for w in self.browse(cr, uid, ids):
            # Search lines
            entries = self.pool.get('msf.doc.import.accounting.lines').search(cr, uid, [('wizard_id', '=', w.id)])
            if not entries:
                raise osv.except_osv(_('Error'), _('No lines…'))
            # Browse result
            b_entries = self.pool.get('msf.doc.import.accounting.lines').browse(cr, uid, entries)
            # Update wizard
            self.write(cr, uid, [w.id], {'message': _('Grouping by currency and date…'), 'progression': 10.0})
            # Group entries by currency, period and doc date (to create moves)
            curr_date_group = {}
            for entry in b_entries:
                # note: having different periods is possible only for December dates (ex: Period 13 and 14)
                if (entry.currency_id.id, entry.period_id.id, entry.document_date) not in curr_date_group:
                    curr_date_group[(entry.currency_id.id, entry.period_id.id, entry.document_date)] = []
                curr_date_group[(entry.currency_id.id, entry.period_id.id, entry.document_date)].append(entry)
            # Update wizard
            self.write(cr, uid, ids, {'message': _('Writing of the Journal Entries…'), 'progression': 20.0})
            num = 1
            nb_entries = float(len(curr_date_group))
            remaining_percent = 80.0
            step = float(remaining_percent / nb_entries)
            for currency_id, period_id, document_date in curr_date_group:
                # Create a move
                move_vals = {
                    'currency_id': currency_id,
                    'manual_currency_id': currency_id,
                    'journal_id': journal_id,  # the instance_id will be the instance of this journal i.e. the current one
                    'document_date': document_date,
                    'date': w.date,
                    'period_id': period_id,
                    'status': 'manu',
                    'imported': True,
                }
                move_id = self.pool.get('account.move').create(cr, uid, move_vals, context)
                for l_num, l in enumerate(curr_date_group[(currency_id, period_id, document_date)]):
                    # Update wizard
                    progression = 20.0 + ((float(l_num) / float(len(b_entries))) * step) + (float(num - 1) * step)
                    self.write(cr, uid, [w.id], {'progression': progression})
                    distrib_id = False
                    # Create analytic distribution
                    if l.account_id.is_analytic_addicted:
                        distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context)
                        curr_date = currency_date.get_date(self, cr, l.document_date, l.date)
                        common_vals = {
                            'distribution_id': distrib_id,
                            'currency_id': currency_id,
                            'percentage': 100.0,
                            'date': l.date,
                            'source_date': curr_date,
                            'destination_id': l.destination_id.id,
                        }
                        common_vals.update({'analytic_id': l.cost_center_id.id,})
                        self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                        common_vals.update({'analytic_id': l.funding_pool_id.id, 'cost_center_id': l.cost_center_id.id,})
                        self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    # Create move line
                    move_line_vals = {
                        'move_id': move_id,
                        'name': l.description,
                        'reference': l.ref,
                        'account_id': l.account_id.id,
                        'period_id': period_id,
                        'document_date': l.document_date,
                        'date': l.date,
                        'journal_id': journal_id,  # the instance_id will be the instance of this journal i.e. the current one
                        'debit_currency': l.debit,
                        'credit_currency': l.credit,
                        'currency_id': currency_id,
                        'analytic_distribution_id': distrib_id,
                        'partner_id': l.partner_id and l.partner_id.id or False,
                        'employee_id': l.employee_id and l.employee_id.id or False,
                        'transfer_journal_id': l.transfer_journal_id and l.transfer_journal_id.id or False,
                    }
                    self.pool.get('account.move.line').create(cr, uid, move_line_vals, context, check=False)
                # Validate the Journal Entry for lines to be valid (if possible)
                self.write(cr, uid, [w.id], {'message': _('Validating journal entry…')})
                self.pool.get('account.move').validate(cr, uid, [move_id], context=context)
                # Update wizard
                progression = 20.0 + (float(num) * step)
                self.write(cr, uid, [w.id], {'progression': progression})
                num += 1
        return True

    def _check_has_data(self, line):
        """
        Returns True if there is data on the line
        """
        for i in range(len(line)):
            if line[i]:
                return True
        return False

    def _format_special_char(self, line):
        """
        Replaces back the arbitrary strings used for the special characters with their corresponding hexadecimal codes
        and replace all occurrences of special character  &#20 (DEVICE CONTROL FOUR-DC4) by ordinary spaces
        """
        for i in range(len(line)):
            if line[i] and isinstance(line[i], basestring) and SPECIAL_CHAR in line[i]:
                line[i] = re.sub('%s_(20)' % SPECIAL_CHAR, ' ', line[i]) # US-11090 Replaces DC4 by ordinary spaces
                line[i] = re.sub('%s_([0-9][0-9]{0,1})' % SPECIAL_CHAR, lambda a: chr(int(a.group(1))), line[i])
        return line

    def _import(self, dbname, uid, ids, context=None):
        """
        Do treatment before validation:
        - check data from wizard
        - check that file exists and that data are inside
        - check integrity of data in files
        """
        # Some checks
        if context is None:
            context = {}
        # Prepare some values
        # Do changes because of YAML tests
        cr = pooler.get_db(dbname).cursor()
        created = 0
        processed = 0
        errors = []
        current_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id or False

        current_line_num = None
        try:
            # Update wizard
            self.write(cr, uid, ids, {'message': _('Cleaning up old imports…'), 'progression': 1.00})
            # Clean up old temporary imported lines
            old_lines_ids = self.pool.get('msf.doc.import.accounting.lines').search(cr, uid, [])
            self.pool.get('msf.doc.import.accounting.lines').unlink(cr, uid, old_lines_ids)

            # Check wizard data
            ad_obj = self.pool.get('analytic.distribution')
            period_obj = self.pool.get('account.period')
            period_ctx = context.copy()
            period_ctx['extend_december'] = True
            for wiz in self.browse(cr, uid, ids):
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': 2.00})
                # UF-2045: Check that the given date is in an open period
                wiz_period_ids = period_obj.get_period_from_date(
                    cr, uid, wiz.date, period_ctx)
                if not wiz_period_ids:
                    raise osv.except_osv(_('Warning'), _('No period found!'))
                date = wiz.date or False

                # Check that a file was given
                if not wiz.file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Copying file…'), 'progression': 3.00})
                fileobj = NamedTemporaryFile('w+b', delete=False)
                fileobj.write(decodestring(wiz.file))
                fileobj.close()
                context.update({'from_je_import': True})
                content = SpreadsheetXML(xmlfile=fileobj.name, context=context)
                if not content:
                    raise osv.except_osv(_('Warning'), _('No content'))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Processing line…'), 'progression': 4.00})
                rows = content.getRows()
                nb_rows = len([x for x in content.getRows()])
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Reading headers…'), 'progression': 5.00})
                # Use the first row to find which column to use
                cols = {}
                col_names = ['Proprietary Instance', 'Journal Code', 'Description', 'Reference', 'Document Date', 'Posting Date', 'Period',
                             'G/L Account', 'Partner', 'Employee', 'Journal', 'Destination', 'Cost Centre', 'Funding Pool', 'Booking Debit',
                             'Booking Credit', 'Booking Currency']
                for num, r in enumerate(rows):
                    header = [x and x.data for x in r.iter_cells()]
                    for el in col_names:
                        if el in header:
                            cols[el] = header.index(el)
                    break
                # Number of line to bypass in line's count
                base_num = 2

                # global journal code for the file
                file_journal_id = 0
                aj_obj = self.pool.get('account.journal')

                for el in col_names:
                    if not el in cols:
                        raise osv.except_osv(_('Error'), _("'%s' column not found in file.") % (el or '',))
                # All lines
                money = {}
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Reading lines…'), 'progression': 6.00})
                # Check file's content
                for num, r in enumerate(rows):
                    # Update wizard
                    progression = ((float(num+1) * 94) / float(nb_rows)) + 6
                    self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': progression})
                    # Prepare some values
                    r_debit = 0
                    r_credit = 0
                    r_currency = False
                    r_partner = False
                    r_employee = False
                    r_journal = False
                    r_account = False
                    r_destination = False
                    r_fp = False
                    r_cc = False
                    # UTP-1047: Use Document date column (contrary of UTP-766)
                    r_document_date = False
                    current_line_num = num + base_num
                    # Fetch all XML row values
                    line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, r, context=context)

                    # ignore empty lines
                    if not self._check_has_data(line):
                        continue

                    self._format_special_char(line)

                    file_prop_inst = line[cols['Proprietary Instance']] or ''
                    if current_instance and current_instance.code != file_prop_inst.strip():
                        errors.append(_('Line %s. The Proprietary Instance must be the current instance %s.') % (current_line_num, current_instance.code))
                        continue
                    # Check document date
                    if not line[cols['Document Date']]:
                        errors.append(_('Line %s. No document date specified!') % (current_line_num,))
                        continue
                    if not isinstance(line[cols['Document Date']], type(mx.DateTime.now())):
                        errors.append(_('Line %s, the column \'Document Date\' have to be of type DateTime. Check the spreadsheet format (or export a document to have an example).') % (current_line_num,))
                        continue
                    r_document_date = line[cols['Document Date']].strftime('%Y-%m-%d')
                    # Check on booking amounts: ensure that one (and only one) value exists and that its amount isn't negative
                    book_debit = 0
                    book_credit = 0
                    try:
                        book_debit = line[cols['Booking Debit']]
                        book_credit = line[cols['Booking Credit']]
                        if book_debit and book_credit:
                            errors.append(_('Line %s. Only one value (Booking Debit or Booking Credit) should be filled in.') % (current_line_num,))
                            continue
                        if not book_debit and not book_credit:
                            # /!\ display different messages depending if values are zero or empty
                            debit_is_zero = book_debit is 0 or book_debit is 0.0
                            credit_is_zero = book_credit is 0 or book_credit is 0.0
                            if debit_is_zero and credit_is_zero:
                                errors.append(_('Line %s. Booking Debit and Booking Credit at 0, please change.') % (current_line_num,))
                                continue
                            elif not debit_is_zero and not credit_is_zero:
                                # empty cells
                                errors.append(_('Line %s. Please fill in either a Booking Debit or a Booking Credit value.') % (current_line_num,))
                                continue
                            else:
                                amount_zero_str = debit_is_zero and _('Booking Debit') or _('Booking Credit')
                                amount_empty_str = debit_is_zero and _('Booking Credit') or _('Booking Debit')
                                errors.append(_('Line %s. %s at 0, %s empty, please change.') % (current_line_num,
                                                                                                 amount_zero_str, amount_empty_str))
                                continue
                        if (book_debit and not isinstance(book_debit, (int, long, float))) or \
                                (book_credit and not isinstance(book_credit, (int, long, float))):
                            errors.append(_('Line %s. The Booking Debit or Credit amount is invalid and should be a number.') % (current_line_num,))
                            continue
                        if (book_debit and book_debit < 0) or (book_credit and book_credit < 0):
                            errors.append(_('Line %s. Negative numbers are forbidden for the Booking Debit and Credit amounts.') % (current_line_num,))
                            continue
                    except IndexError:
                        errors.append(_('Line %s. The Booking Debit and Credit amounts are missing.') % (current_line_num,))
                        continue
                    processed += 1
                    # Check that currency is active
                    if not line[cols['Booking Currency']]:
                        errors.append(_('Line %s. No currency specified!') % (current_line_num,))
                        continue
                    booking_curr = line[cols['Booking Currency']]
                    curr_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', booking_curr)])
                    if not curr_ids:
                        errors.append(_('Line %s. Currency not found: %s') % (current_line_num, booking_curr,))
                        continue
                    for c in self.pool.get('res.currency').browse(cr, uid, curr_ids):
                        if not c.active:
                            errors.append(_('Line %s. Currency is not active: %s') % (current_line_num, booking_curr,))
                            continue
                    r_currency = curr_ids[0]
                    if not line[cols['Period']]:
                        errors.append(_('Line %s. Period is missing.') % (current_line_num))
                        continue
                    period_name = line[cols['Period']]
                    if not isinstance(period_name, basestring):
                        period_name = '%s' % period_name
                    if not period_obj.search_exist(cr, uid, [('name', '=', period_name)], context=context):
                        errors.append(_("Line %s. The period %s doesn't exist.") % (current_line_num, period_name,))
                        continue
                    if not (booking_curr, period_name, r_document_date) in money:
                        money[(booking_curr, period_name, r_document_date)] = {}
                    if not 'debit' in money[(booking_curr, period_name, r_document_date)]:
                        money[(booking_curr, period_name, r_document_date)]['debit'] = 0
                    if not 'credit' in money[(booking_curr, period_name, r_document_date)]:
                        money[(booking_curr, period_name, r_document_date)]['credit'] = 0
                    # Increment global debit/credit
                    if book_debit:
                        money[(booking_curr, period_name, r_document_date)]['debit'] += book_debit
                        r_debit = book_debit
                    if book_credit:
                        money[(booking_curr, period_name, r_document_date)]['credit'] += book_credit
                        r_credit = book_credit

                    # Check the journal code which must match with one of the journal types listed in ACCOUNTING_IMPORT_JOURNALS
                    journal_type = ''
                    if not line[cols['Journal Code']]:
                        errors.append(_('Line %s. No Journal Code specified') % (current_line_num,))
                        continue
                    else:
                        # check for a valid journal code
                        aj_ids = aj_obj.search(cr, uid,
                                               [('code', '=', line[cols['Journal Code']]),
                                                ('instance_id', '=', current_instance.id),
                                                ('is_active', '=', True)],
                                               limit=1)
                        if not aj_ids:
                            errors.append(_('Line %s. Journal Code not found or inactive: %s.') %
                                          (current_line_num, line[cols['Journal Code']]))
                            continue
                        else:
                            aj_data = aj_obj.read(cr, uid, aj_ids, ['type'])[0]
                            journal_type = aj_data.get('type', False)
                            if journal_type is False or journal_type not in ACCOUNTING_IMPORT_JOURNALS:
                                journal_list = ', '.join([x[1] for x in aj_obj.get_journal_type(cr, uid) if x[0] in ACCOUNTING_IMPORT_JOURNALS])
                                errors.append(_('Line %s. Import of entries only allowed on the following journal(s): %s') % (current_line_num, journal_list))
                                continue
                        aj_id = aj_ids[0]
                        if file_journal_id == 0:  # take the journal from the first line where there was no "continue"
                            file_journal_id = aj_id
                        else:
                            if file_journal_id != aj_id:
                                errors.append(_('Line %s. Only a single Journal Code can be specified per file') % (current_line_num,))
                                continue

                    # Check G/L account
                    if not line[cols['G/L Account']]:
                        errors.append(_('Line %s. No G/L account specified!') % (current_line_num,))
                        continue
                    account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', line[cols['G/L Account']])])
                    if not account_ids:
                        errors.append(_('Line %s. G/L account %s not found!') % (current_line_num, line[cols['G/L Account']],))
                        continue
                    r_account = account_ids[0]
                    account = self.pool.get('account.account').browse(cr, uid, r_account)

                    # Third party
                    # Check that Third party exists (if not empty)
                    tp_label = False
                    tp_content = False
                    if line[cols['Partner']]:
                        tp_ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', line[cols['Partner']])])
                        if not tp_ids:
                            tp_label = _('Partner')
                            tp_content = line[cols['Partner']]
                        else:
                            r_partner = tp_ids[0]
                    if line[cols['Employee']]:
                        tp_ids = self.pool.get('hr.employee').search(cr, uid, [('name', '=', line[cols['Employee']])],
                                                                     order='active desc, id', limit=1)
                        if not tp_ids:
                            tp_label = _('Employee')
                            tp_content = line[cols['Employee']]
                        else:
                            r_employee = tp_ids[0]
                    if line[cols['Journal']]:
                        tp_ids = self.pool.get('account.journal').search(cr, uid, ['|', ('name', '=', line[cols['Journal']]), ('code', '=', line[cols['Journal']]), ('instance_id', '=', current_instance.id)])
                        if not tp_ids:
                            tp_label = _('Journal')
                            tp_content = line[cols['Journal']]
                        else:
                            r_journal = tp_ids[0]
                    if tp_label and tp_content:
                        errors.append(_('Line %s. %s not found: %s') % (current_line_num, tp_label, tp_content,))
                        continue

                    list_third_party = []
                    if r_employee:
                        list_third_party.append(r_employee)
                    if r_partner:
                        list_third_party.append(r_partner)
                    if r_journal:
                        list_third_party.append(r_journal)
                    if len(list_third_party) > 1:
                        errors.append(_('Line %s. You cannot only add partner or employee or journal.') % (current_line_num,))
                        continue

                    # US-672 check Third party compat with account
                    tp_check_res = self.pool.get('account.account').is_allowed_for_thirdparty(
                        cr, uid, [r_account],
                        employee_id=r_employee or False,
                        transfer_journal_id=r_journal or False,
                        partner_id=r_partner or False,
                        context=context)[r_account]
                    if not tp_check_res:
                        errors.append(_("Line %s. Thirdparty not compatible with account '%s - %s'") % (current_line_num, account.code, account.name, ))
                        continue

                    # US-3461 Accounts that can't be corrected on Account Codes are not allowed here
                    if account.is_not_hq_correctible:
                        errors.append(_("Line %s. The account \"%s - %s\" cannot be used because it is set as "
                                        "\"Prevent correction on account codes\".") % (current_line_num, account.code, account.name,))
                        continue

                    if account.type_for_register == 'donation' and journal_type != 'extra':
                        jtype_value = journal_type and \
                            dict(aj_obj.fields_get(cr, uid, context=context)['type']['selection']).get(journal_type) or ''
                        errors.append(_('Line %s. The donation accounts are not compatible with the journal type %s.') %
                                      (current_line_num, jtype_value))
                        continue

                    # Check analytic axis only if G/L account is analytic-a-holic
                    if account.is_analytic_addicted:
                        # Check Destination
                        if not line[cols['Destination']]:
                            errors.append(_('Line %s. No destination specified!') % (current_line_num,))
                            continue
                        destination_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'DEST'), '|', ('name', '=', line[cols['Destination']]), ('code', '=', line[cols['Destination']])])
                        if not destination_ids:
                            errors.append(_('Line %s. Destination %s not found!') % (current_line_num, line[cols['Destination']],))
                            continue
                        r_destination = destination_ids[0]
                        # Check Cost Center
                        if not line[cols['Cost Centre']]:
                            errors.append(_('Line %s. No cost center specified!') % (current_line_num,))
                            continue
                        # If necessary cast the CC into a string, otherwise the below search would crash
                        if not isinstance(line[cols['Cost Centre']], basestring):
                            line[cols['Cost Centre']] = '%s' % (line[cols['Cost Centre']])
                        cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), '|', ('name', '=', line[cols['Cost Centre']]), ('code', '=', line[cols['Cost Centre']])])
                        if not cc_ids:
                            errors.append(_('Line %s. Cost Center %s not found!') % (current_line_num, line[cols['Cost Centre']]))
                            continue
                        r_cc = cc_ids[0]
                        # Check Cost Center type
                        cc = self.pool.get('account.analytic.account').browse(cr, uid, r_cc, context)
                        if cc.type == 'view':
                            errors.append(_('Line %s. %s is a VIEW type Cost Center!') % (current_line_num, line[cols['Cost Centre']]))
                            continue
                        # Check Funding Pool (added since UTP-1082)
                        if not line[cols['Funding Pool']]:
                            errors.append(_('Line %s. No Funding Pool specified!') % (current_line_num,))
                            continue
                        else:
                            fp_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'FUNDING'), '|', ('name', '=', line[cols['Funding Pool']]), ('code', '=', line[cols['Funding Pool']])])
                            if not fp_ids:
                                errors.append(_('Line %s. Funding Pool %s not found!') % (current_line_num, line[cols['Funding Pool']]))
                                continue
                            r_fp = fp_ids[0]
                        if r_destination not in [d.id for d in account.destination_ids]:
                            errors.append(_('Line %s. The destination %s is not compatible with the account %s.') %
                                          (current_line_num, line[cols['Destination']], line[cols['G/L Account']]))
                            continue
                        if not ad_obj.check_dest_cc_compatibility(cr, uid, r_destination, r_cc, context=context):
                            errors.append(_('Line %s. The Cost Center %s is not compatible with the Destination %s.') %
                                          (current_line_num, line[cols['Cost Centre']], line[cols['Destination']]))
                            continue
                        if not ad_obj.check_fp_acc_dest_compatibility(cr, uid, r_fp, account.id, r_destination, context=context):
                            errors.append(_('Line %s. The combination "account %s and destination %s" is not '
                                            'compatible with the Funding Pool %s.') %
                                          (current_line_num, line[cols['G/L Account']], line[cols['Destination']], line[cols['Funding Pool']]))
                            continue
                        if not ad_obj.check_fp_cc_compatibility(cr, uid, r_fp, cc.id, context=context):
                            errors.append(_('Line %s. The Cost Center %s is not compatible with the Funding Pool %s.') %
                                          (current_line_num, line[cols['Cost Centre']], line[cols['Funding Pool']]))
                            continue

                    # US-937: use period of import file
                    if period_name.startswith('Period 16'):
                        errors.append(_("Line %s. You can't import entries in Period 16.") % current_line_num)
                        continue
                    period_ids = period_obj.search(
                        cr, uid, [
                            ('id', 'in', wiz_period_ids),
                            ('name', '=', period_name),
                        ], limit=1, context=context)
                    if not period_ids:
                        errors.append(_('Line %s. The date chosen in the wizard is not in the same period as the imported entries.') %
                                      current_line_num)
                        continue
                    period = period_obj.browse(
                        cr, uid, period_ids[0], context=context)
                    if period.state != 'draft':
                        errors.append(_('Line %s. %s is not open!') % (current_line_num, period.name, ))
                        continue

                    # NOTE: There is no need to check G/L account, Cost Center and Destination regarding document/posting date because this check is already done at Journal Entries validation.

                    # Registering data regarding these "keys":
                    # - G/L Account
                    # - Third Party
                    # - Destination
                    # - Cost Centre
                    # - Booking Currency
                    vals = {
                        'description': line[cols['Description']] or '',
                        'ref': line[cols['Reference']] or '',
                        'account_id': r_account or False,
                        'debit': r_debit or 0.0,
                        'credit': r_credit or 0.0,
                        'cost_center_id': r_cc or False,
                        'destination_id': r_destination or False,
                        'document_date': r_document_date or False,
                        'funding_pool_id': r_fp or False,
                        'date': date or False,
                        'currency_id': r_currency or False,
                        'wizard_id': wiz.id,
                        'period_id': period and period.id or False,
                        'employee_id': r_employee or False,
                        'partner_id': r_partner or False,
                        'transfer_journal_id': r_journal or False,
                    }

                    # US-2470
                    if not vals['description']:
                        errors.append(_('Line %s. Description is missing for the given account: %s.') % (current_line_num, account.code))
                        continue

                    # UTP-1056: Add employee possibility. So we need to check if employee and/or partner is authorized
                    partner_needs = self.pool.get('account.bank.statement.line').onchange_account(cr, uid, False, account_id=account.id, context=context)
                    if not partner_needs:
                        errors.append(_('Line %s. No info about given account: %s') % (current_line_num, account.code,))
                        continue
                    # Check partner type compatibility regarding the Account "Type for specific treatment"
                    partner_options = partner_needs['value']['partner_type']['options']
                    partner_type_mandatory = 'partner_type_mandatory' in partner_needs['value'] and \
                                             partner_needs['value']['partner_type_mandatory'] or False
                    type_for_reg = account.type_for_register
                    if r_partner and ('res.partner', 'Partner') not in partner_options:
                        errors.append(_('Line %s. You cannot use a partner for the given account: %s.') % (current_line_num, account.code))
                        continue
                    if r_employee and ('hr.employee', 'Employee') not in partner_options:
                        errors.append(_('Line %s. You cannot use an employee for the given account: %s.') % (current_line_num, account.code))
                        continue
                    if r_journal and ('account.journal', 'Journal') not in partner_options:
                        errors.append(_('Line %s. You cannot use a journal for the given account: %s.') % (current_line_num, account.code))
                        continue
                    if partner_type_mandatory and not r_partner and not r_employee and not r_journal:
                        errors.append(_('Line %s. A Third Party is mandatory for the given account: %s.') % (current_line_num, account.code))
                        continue
                    # Check that the currency and type of the (journal) third party is correct
                    # in case of an "Internal Transfer" account
                    partner_journal = r_journal and aj_obj.browse(cr, uid, r_journal,
                                                                  fields_to_fetch=['currency', 'type', 'is_active', 'code'],
                                                                  context=context)
                    if partner_journal and not partner_journal.is_active:  # no need to check further in case the journal is inactive
                        errors.append(_('Line %s. The Journal Third Party "%s" is inactive.') % (current_line_num, partner_journal.code))
                        continue
                    is_liquidity = partner_journal and partner_journal.type in ['cash', 'bank', 'cheque'] and partner_journal.currency
                    if type_for_reg == 'transfer_same' and (not is_liquidity or partner_journal.currency.id != r_currency):
                        errors.append(_('Line %s. The Third Party must be a liquidity journal with the same currency '
                                        'as the booking one for the given account: %s.') % (current_line_num, account.code))
                        continue
                    if type_for_reg == 'transfer' and (not is_liquidity or partner_journal.currency.id == r_currency):
                        errors.append(_('Line %s. The Third Party must be a liquidity journal with a currency '
                                        'different from the booking one for the given account: %s.') % (current_line_num, account.code))
                        continue

                    if is_liquidity and file_journal_id == partner_journal.id:
                        errors.append(_('Line %s. The journal used for the internal transfer must be different from the '
                                        'Journal Entry Journal for the given account: %s.') % (current_line_num, account.code))
                        continue

                    if account.type == 'liquidity':
                        # do not permit to import line with liquidity account
                        # except when importing in Migration journal
                        if file_journal_id and aj_obj.read(cr, uid,
                                                           file_journal_id, ['type'],
                                                           context=context)['type'] != 'migration':
                            errors.append(_('Line %s. It is not possible to import account of type \'Liquidity\', '
                                            'please check the account %s.') % (current_line_num, account.code))
                            continue

                    line_res = self.pool.get('msf.doc.import.accounting.lines').create(cr, uid, vals, context)
                    if not line_res:
                        errors.append(_('Line %s. A problem occurred for line registration. Please contact an Administrator.') % (current_line_num,))
                        continue
                    created += 1
                # Check if all is ok for the file
                ## The lines should be balanced for each currency
                if not errors:
                    # to compare the right amounts do the check only if no line has been ignored because of an error
                    for curr, per, doc_date in money:
                        amount = money[(curr, per, doc_date)]['debit'] - money[(curr, per, doc_date)]['credit']
                        if abs(amount) > 10**-3:
                            errors.append(_('An error occurred. Error: Amount unbalanced for the Currency %s and the '
                                            'Document Date %s (Period: %s): %s') % (curr, doc_date, per, amount,))
            # Update wizard
            self.write(cr, uid, ids, {'message': _('Check complete. Reading potential errors or write needed changes.'), 'progression': 100.0})

            wiz_state = 'done'
            # If errors, cancel probable modifications
            if errors:
                cr.rollback()
                created = 0
                message = _('Import FAILED.')
                # Delete old errors
                error_ids = self.pool.get('msf.doc.import.accounting.errors').search(cr, uid, [], context)
                if error_ids:
                    self.pool.get('msf.doc.import.accounting.errors').unlink(cr, uid, error_ids ,context)
                # create errors lines
                for e in errors:
                    self.pool.get('msf.doc.import.accounting.errors').create(cr, uid, {'wizard_id': wiz.id, 'name': e}, context)
                wiz_state = 'error'
            else:
                # Update wizard
                self.write(cr, uid, ids, {'message': _('Writing changes…'), 'progression': 0.0})
                # Create all journal entries
                self.create_entries(cr, uid, ids, file_journal_id, context)
                message = _('Import successful.')

            # Update wizard
            self.write(cr, uid, ids, {'message': message, 'state': wiz_state, 'progression': 100.0})

            # Close cursor
            cr.commit()
            cr.close(True)
        except osv.except_osv as osv_error:
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occurred. %s: %s") % (osv_error.name, osv_error.value,), 'state': 'done', 'progression': 100.0})
            cr.close(True)
        except Exception as e:
            cr.rollback()
            if current_line_num is not None:
                message = _("An error occurred on line %s: %s") % (current_line_num, e.args and e.args[0] or '')
            else:
                message = _("An error occurred: %s") % (e.args and e.args[0] or '',)
            self.write(cr, uid, ids, {'message': message, 'state': 'done', 'progression': 100.0})
            cr.close(True)
        return True

    def button_validate(self, cr, uid, ids, context=None):
        """
        Launch process in a thread and return a wizard
        """
        # Some checks
        if not context:
            context = {}
        # Launch a thread if we come from web
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        res = self.write(cr, uid, ids, {'state': 'inprogress'}, context=context)
        return res

    def button_update(self, cr, uid, ids, context=None):
        """
        Update view
        """
        return False

msf_doc_import_accounting()

class msf_doc_import_accounting_lines(osv.osv):
    _name = 'msf.doc.import.accounting.lines'
    _rec_name = 'document_date'

    _columns = {
        'description': fields.text("Description", required=False, readonly=True),
        'ref': fields.text("Reference", required=False, readonly=True),
        'document_date': fields.date("Document date", required=True, readonly=True),
        'date': fields.date("Posting date", required=True, readonly=True),
        'account_id': fields.many2one('account.account', "G/L Account", required=True, readonly=True),
        'destination_id': fields.many2one('account.analytic.account', "Destination", required=False, readonly=True),
        'cost_center_id': fields.many2one('account.analytic.account', "Cost Center", required=False, readonly=True),
        'funding_pool_id': fields.many2one('account.analytic.account', "Funding Pool", required=False, readonly=True),
        'debit': fields.float("Debit", required=False, readonly=True),
        'credit': fields.float("Credit", required=False, readonly=True),
        'currency_id': fields.many2one('res.currency', "Currency", required=True, readonly=True),
        'partner_id': fields.many2one('res.partner', "Partner", required=False, readonly=True),
        'employee_id': fields.many2one('hr.employee', "Employee", required=False, readonly=True),
        'transfer_journal_id': fields.many2one('account.journal', 'Journal', required=False, readonly=True),
        'period_id': fields.many2one('account.period', "Period", required=True, readonly=True),
        'wizard_id': fields.integer("Wizard", required=True, readonly=True),
    }

    _defaults = {
        'description': lambda *a: '',
        'ref': lambda *a: '',
        'document_date': lambda *a: strftime('%Y-%m-%d'),
        'date': lambda *a: strftime('%Y-%m-%d'),
        'debit': lambda *a: 0.0,
        'credit': lambda *a: 0.0,
    }

msf_doc_import_accounting_lines()

class msf_doc_import_accounting_errors(osv.osv_memory):
    _name = 'msf.doc.import.accounting.errors'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('msf.doc.import.accounting', "Wizard", required=True, readonly=True),
    }

msf_doc_import_accounting_errors()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
