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
import os.path
from base64 import decodestring
from tempfile import NamedTemporaryFile
import csv
from tools.misc import ustr
from tools.translate import _
import time
import locale

class hq_entries_import_wizard(osv.osv_memory):
    _name = 'hq.entries.import'
    _description = 'HQ Entries Import Wizard'

    _columns = {
        'file': fields.binary(string="File", filters="*.csv", required=True),
    }

    def update_hq_entries(self, cr, uid, line):
        """
        Import hq entry regarding all elements given in "line"
        """
        # Seems that some line could be empty
        if line.count('') == 16:
            return False
        # Prepare some values
        vals = {
            'user_validated': False,
        }
        sequence, date, period, mission_name, mission_code, unknown_number, account_description, booking_currency, booking_amount, \
        amount, unknown_rate, unknown_rate_date, unknown_code, unknown_number2, description, unknown_code = zip(line)
        # Set locale 'C' because of period
        locale.setlocale(locale.LC_ALL, 'C')
        # Check period
        if not date and not date[0]:
            raise osv.except_osv(_('Warning'), _('A date is missing!'))
        try:
            line_date = time.strftime('%Y-%m-%d', time.strptime(date[0], '%d-%b-%y'))
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Wrong format for date: %s.\n%s') % (date[0], e))
        period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, line_date)
        if not period_ids:
            raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % (line_date,))
        if len(period_ids) > 1:
            raise osv.except_osv(_('Warning'), _('More than one period found for given date: %s') % (line_date,))
        period_id = period_ids[0]
        vals.update({'period_id': period_id, 'date': line_date})
        # Retrive account
        if account_description and account_description[0]:
            account_data = account_description[0].split(' ')
            account_code = account_data and account_data[0] or False
            if not account_code:
                raise osv.except_osv(_('Error'), _('No account code found!'))
            account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', account_code)])
            if not account_ids:
                raise osv.except_osv(_('Error'), _('Account code %s doesn\'t exist!') % (account_code,))
            vals.update({'account_id': account_ids[0], 'account_id_first_value': account_ids[0]})
        # Retrieve Cost Center and Funding Pool
        try:
            cc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1]
        except ValueError:
            cc_id = 0
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        vals.update({'cost_center_id': cc_id, 'analytic_id': fp_id, 'cost_center_id_first_value': cc_id, 'analytic_id_first_value': fp_id,})
        # Fetch description
        if description and description[0]:
            vals.update({'name': description[0]})
        # Fetch currency
        if booking_currency and booking_currency[0]:
            currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', booking_currency[0]), ('active', 'in', [False, True])])
            if not currency_ids:
                raise osv.except_osv(_('Error'), _('This currency was not found or is not active: %s') % (booking_currency[0],))
            if currency_ids and currency_ids[0]:
                vals.update({'currency_id': currency_ids[0],})
        # Fetch amount
        if booking_amount and booking_amount[0]:
            vals.update({'amount': booking_amount[0],})
        # Line creation
        res = self.pool.get('hq.entries').create(cr, uid, vals)
        if res:
            return True
        return False

    def button_validate(self, cr, uid, ids, context=None):
        """
        Take a CSV file and fetch some informations for HQ Entries
        """
        # Do verifications
        if not context:
            context = {}
        
        # Verify that an HQ journal exists
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hq')])
        if not journal_ids:
            raise osv.except_osv(_('Error'), _('You cannot import HQ entries because no HQ Journal exists.'))
        
        # Prepare some values
        file_ext_separator = '.'
        file_ext = "csv"
        message = _("HQ Entries import failed.")
        res = False
        created = 0
        processed = 0
        
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids):
            # Decode file string
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            fileobj.seek(0)
            # Read CSV file
            try:
                reader = csv.reader(fileobj, delimiter=',')
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Problem to read given file.'))
            res = True
            res_amount = 0.0
            amount = 0.0
            for line in reader:
                processed += 1
                update = self.update_hq_entries(cr, uid, line)
                if update:
                    created += 1
            fileobj.close()
        
        if res:
            message = _("Payroll import successful")
        context.update({'message': message})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        # This is to redirect to HQ Entries Tree View
        context.update({'from': 'hq_entries_import'})
        
        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'total': processed, 'state': 'hq'})
        
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
