#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from base64 import decodestring
from tempfile import NamedTemporaryFile
import csv
from tools.translate import _
import time
#import locale
from account_override import ACCOUNT_RESTRICTED_AREA
from tools.misc import ustr


class hq_entries_import_wizard(osv.osv_memory):
    _name = 'hq.entries.import'
    _description = 'HQ Entries Import Wizard'

    _columns = {
        'file': fields.binary(string="File", filters="*.csv", required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    def parse_date(self, date):
        try:
            pdate = time.strptime(date, '%d/%m/%y')
        except ValueError:
            pdate = time.strptime(date, '%d/%m/%Y')
        return time.strftime('%Y-%m-%d', pdate)

    def update_hq_entries(self, cr, uid, line, context=None):
        """
        Import hq entry regarding all elements given in "line"
        """
        # Seems that some line could be empty
        if line.count('') == 12:
            return False
        for x in xrange(0,12-len(line)):
            line.append('')
        # Prepare some values
        vals = {
            'user_validated': False,
        }
        try:
            description, reference, document_date, date, account_description, third_party, booking_amount, booking_currency, \
                destination, cost_center, funding_pool, free1, free2 = line
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Unknown format.'))
        acc_obj = self.pool.get('account.account')
        anacc_obj = self.pool.get('account.analytic.account')
        hq_obj = self.pool.get('hq.entries')
        ### TO USE IF DATE HAVE some JAN or MAR or OCT instead of 01 ####
        ### Set locale 'C' because of period
        ## locale.setlocale(locale.LC_ALL, 'C')
        # Check period
        if not date:
            raise osv.except_osv(_('Warning'), _('A date is missing!'))
        try:
            line_date = self.parse_date(date)
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (date, e))
        period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, line_date)
        if not period_ids:
            raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % (line_date,))
        if len(period_ids) > 1:
            raise osv.except_osv(_('Warning'), _('More than one period found for given date: %s') % (line_date,))
        period_id = period_ids[0]
        vals.update({'period_id': period_id, 'date': line_date})
        dd = False
        if document_date:
            try:
                dd = self.parse_date(document_date)
                vals.update({'document_date': dd})
            except ValueError, e:
                raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (document_date, e))
        # [utp-928]
        # Make it impossible to import HQ entries where Doc Date > Posting Date,
        # it will spare trouble at HQ entry validation.
        self.pool.get('finance.tools').check_document_date(cr, uid,
                                                           dd, line_date, show_date=True)
        # Retrieve account
        if account_description:
            account_data = account_description.split(' ')
            account_code = account_data and account_data[0] or False
            if not account_code:
                raise osv.except_osv(_('Error'), _('No account code found!'))
            account_ids = acc_obj.search(cr, uid, [('code', '=', account_code)] + ACCOUNT_RESTRICTED_AREA['hq_lines_import'])
            if not account_ids:
                raise osv.except_osv(_('Error'), _('Account code %s doesn\'t exist or is not allowed in HQ Entries!') % (account_code,))

            if not acc_obj.read(cr, uid, account_ids[0], ['filter_active'], context={'date': line_date})['filter_active']:
                raise osv.except_osv(_('Error'), _('Account code %s is inactive for this date %s') % (account_code, date))

            vals.update({'account_id': account_ids[0], 'account_id_first_value': account_ids[0]})
        else:
            raise osv.except_osv(_('Error'), _('No account code found!'))
        aa_check_ids = []
        destination_id = False
        fp_id = False
        free1_id = False
        free2_id = False
        account = acc_obj.browse(cr, uid, account_ids[0])
        if account.user_type.code not in ['expense', 'income']:  # B/S accounts
            if destination or funding_pool or free1 or free2:
                raise osv.except_osv(_('Error'), _('The B/S account %s cannot have an Analytic Distribution. '
                                                   'Only a Cost Center should be given.') % (account_description,))
            elif not cost_center:
                # a CC is needed for synchro (it can't be added after the import as the B/S lines are not editable)
                raise osv.except_osv(_('Error'), _('Cost Center is missing for the account %s.') % (account_description,))
        else:  # expense or income accounts
            # Retrieve Destination
            # Set default destination
            if not account.default_destination_id:
                raise osv.except_osv(_('Warning'), _('No default Destination defined for account: %s') % (account.code or '',))
            destination_id = account.default_destination_id and account.default_destination_id.id or False
            # But use those from CSV file if given
            if destination:
                dest_id = anacc_obj.search(cr, uid, ['|', ('code', '=', destination), ('name', '=', destination)])
                if dest_id:
                    destination_id = dest_id[0]
                else:
                    raise osv.except_osv(_('Error'), _('Destination "%s" doesn\'t exist!') % (destination,))
            if destination_id:
                aa_check_ids.append(destination_id)
            # Retrieve Funding Pool
            if funding_pool:
                fp_id = anacc_obj.search(cr, uid, ['|', ('code', '=', funding_pool), ('name', '=', funding_pool), ('category', '=', 'FUNDING')])
                if not fp_id:
                    raise osv.except_osv(_('Error'), _('Funding Pool "%s" doesn\'t exist!') % (funding_pool,))
                fp_id = fp_id[0]
            else:
                try:
                    fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                except ValueError:
                    fp_id = 0
            if fp_id:
                aa_check_ids.append(fp_id)
            # Retrieve Free 1 / Free 2
            if free1:
                free1_id = anacc_obj.search(cr, uid, ['|', ('code', '=', free1), ('name', '=', free1), ('category', '=', 'FREE1')])
                if not free1_id:
                    raise osv.except_osv(_('Error'), _('Free 1 "%s" doesn\'t exist!') % (free1,))
                free1_id = free1_id[0]
                aa_check_ids.append(free1_id)
            if free2:
                free2_id = anacc_obj.search(cr, uid, ['|', ('code', '=', free2), ('name', '=', free2), ('category', '=', 'FREE2')])
                if not free2_id:
                    raise osv.except_osv(_('Error'), _('Free 2 "%s" doesn\'t exist!') % (free2,))
                free2_id = free2_id[0]
                aa_check_ids.append(free2_id)

        # Retrieve Cost Center
        cc_id = False
        if cost_center:
            cc_id = anacc_obj.search(cr, uid, ['|', ('code', '=', cost_center), ('name', '=', cost_center), ('category', '=', 'OC')])
            if not cc_id:
                raise osv.except_osv(_('Error'), _('Cost Center "%s" doesn\'t exist!') % (cost_center,))
            cc_id = cc_id[0]
            if cc_id:
                aa_check_ids.append(cc_id)

        vals.update({'destination_id_first_value': destination_id, 'destination_id': destination_id, 'cost_center_id': cc_id, 'analytic_id': fp_id, 'cost_center_id_first_value': cc_id, 'analytic_id_first_value': fp_id, 'free_1_id': free1_id, 'free_2_id': free2_id,})

        # [utp-928] do not import line with a
        # 'Destination' or 'Cost Center' or 'Funding Pool',
        # of type 'view'
        aa_check_errors = []
        aa_check_category_map = {
            'OC': 'Cost Center',
            'FUNDING': 'Funding Pool',
            'DEST': 'Destination',
            'FREE1': 'Free 1',
            'FREE2': 'Free 2',
        }
        if aa_check_ids:
            for aa_r in anacc_obj.read(cr, uid, aa_check_ids,
                                       ['code', 'name', 'type', 'category']):
                if aa_r['type'] and aa_r['type'] == 'view' and account.user_type_code in ['expense', 'income']:
                    category = ''
                    if aa_r['category']:
                        if aa_r['category'] in aa_check_category_map:
                            category += aa_check_category_map[aa_r['category']] + ' '
                    aa_check_errors.append(_('%s "%s - %s" of type "view" is not allowed '
                                           'for the account "%s - %s"') % (category, aa_r['code'], aa_r['name'], account.code, account.name))
        if aa_check_errors:
            raise osv.except_osv(_('Error'), ", ".join(aa_check_errors))

        # Fetch description
        if description:
            vals.update({'name': description})
        # Fetch reference
        if reference:
            vals.update({'ref': reference})
        # Fetch 3rd party
        if third_party:
            vals.update({'partner_txt': third_party})
        # Fetch currency
        if booking_currency:
            currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', booking_currency), ('active', 'in', [False, True])])
            if not currency_ids:
                raise osv.except_osv(_('Error'), _('This currency was not found or is not active: %s') % (booking_currency,))
            if currency_ids and currency_ids[0]:
                vals.update({'currency_id': currency_ids[0],})
        # Fetch amount
        if booking_amount:
            vals.update({'amount': booking_amount,})

        # BKLG-63/US-414: unicity check
        # Description (name), Reference (ref), Posting date (date),
        # Document date (document_date), Amount (amount),
        # and Account (account_id) and 3rd Party and CC
        unicity_fields = [
            'name', 'ref', 'date', 'document_date', 'amount', 'account_id',
            'cost_center_id',
        ]

        unicity_domain = [
            (f, '=', vals.get(f, False)) for f in unicity_fields
        ]
        # US-414: add 3rd party for unicity check
        unicity_domain.append(('partner_txt', '=', third_party or False))

        if hq_obj.search(cr, uid, unicity_domain, limit=1, context=context):
            # raise unicity check failure
            # (fields listed like in csv order for user info)

            pattern = _("Entry already imported: %s / %s / %s (doc) /" \
                        " %s (posting) / %s (account) / %s (amount) / %s (3rd party) /" \
                        " %s (%s)")
            raise osv.except_osv(_('Error'), pattern % (
                ustr(description), ustr(reference), document_date, date,
                ustr(account_description), booking_amount,
                ustr(third_party),
                ustr(cost_center),
                'CC'
            ))

        # Line creation
        res = hq_obj.create(cr, uid, vals)
        if res:
            hq_line = hq_obj.browse(cr, uid, res)
            if not hq_line.cost_center_id_first_value:
                return True
            if hq_line.analytic_state == 'invalid':
                raise osv.except_osv(_('Error'), _('Analytic distribution is invalid!'))
            return True
        return False

    def button_validate(self, cr, uid, ids, context=None, auto_import=False):
        """
        Take a CSV file and fetch some informations for HQ Entries
        """
        # Do verifications
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Verify that an HQ journal exists
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hq'),
                                                                        ('is_current_instance', '=', True)])
        if not journal_ids:
            raise osv.except_osv(_('Error'), _('You cannot import HQ entries because no HQ Journal exists.'))

        # Prepare some values
        message = _("HQ Entries import failed.")
        res = False
        created = 0
        processed = 0
        errors = []
        filename = ""
        processed_lines = []
        rejected_lines = []

        def manage_error(line_index, msg, name='', code='', status=''):
            if auto_import:
                rejected_lines.append((line_index, [name, code, status], msg))
            else:
                errors.append('Line %s, %s' % (line_index, _(msg)))

        # Browse all given wizard
        read_result = self.read(cr, uid, ids, ['file', 'filename'],
                                context=context)
        for wiz in read_result:
            if not wiz['file']:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            # Decode file string
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz['file']))
            # now we determine the file format
            fileobj.seek(0)
            # Read CSV file
            try:
                reader = csv.reader(fileobj, delimiter=',', quotechar='"')
                filename = wiz['filename'] or ""
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Problem to read given file.'))
            if filename:
                if filename.split('.')[-1] != 'csv':
                    raise osv.except_osv(_('Warning'), _('You are trying to import a file with the wrong file format; please import a CSV file.'))
            res = True
            # Omit first line that contains hearders
            headers = None
            try:
                headers = reader.next()
            except StopIteration:
                raise osv.except_osv(_('Error'), _('File is empty!'))
            line_index = 1
            for line in reader:
                line_index += 1
                processed += 1
                if auto_import:
                    processed_lines.append((line_index, []))
                try:
                    self.update_hq_entries(cr, uid, line, context=context)
                    created += 1
                except osv.except_osv, e:
                    manage_error(line_index, e.value)
            fileobj.close()

        if res:
            message = _("HQ Entries import successful")
        context.update({'message': message})

        if errors or rejected_lines:
            cr.rollback()
            view_id = self.pool.get('ir.model.data').get_object_reference(cr,
                                                                          uid, 'msf_homere_interface', 'payroll_import_error')
        else:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr,
                                                                          uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False

        # This is to redirect to HQ Entries Tree View
        context.update({'from': 'hq_entries_import'})

        if auto_import:
            return processed_lines, rejected_lines, headers

        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'filename': filename, 'created': created, 'total': processed, 'state': 'hq', 'errors': "\n".join(errors), 'nberrors': len(errors)}, context=context)

        return {
            'name': 'HQ Entries Import Confirmation',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.import.confirmation',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

hq_entries_import_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
