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

    def parse_date(self, date):
        try:
            pdate = time.strptime(date, '%d/%m/%y')
        except ValueError, e:
            pdate = time.strptime(date, '%d/%m/%Y')
        return time.strftime('%Y-%m-%d', pdate)

    def update_hq_entries(self, cr, uid, line):
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
            description, reference, date, document_date, account_description, third_party, booking_amount, booking_currency, \
                destination, cost_center, funding_pool, free1, free2 = line
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Unknown format.'))
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
        if document_date:
            try:
                dd = self.parse_date(document_date)
                vals.update({'document_date': dd})
            except ValueError, e:
                raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (document_date, e))
        # Retrieve account
        if account_description:
            account_data = account_description.split(' ')
            account_code = account_data and account_data[0] or False
            if not account_code:
                raise osv.except_osv(_('Error'), _('No account code found!'))
            account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', account_code)])
            if not account_ids:
                raise osv.except_osv(_('Error'), _('Account code %s doesn\'t exist!') % (account_code,))
            vals.update({'account_id': account_ids[0], 'account_id_first_value': account_ids[0]})
        else:
            raise osv.except_osv(_('Error'), _('No account code found!'))
        # Retrieve Destination
        destination_id = False
        account = self.pool.get('account.account').browse(cr, uid, account_ids[0])
        if account.user_type.code == 'expense':
            # Set default destination
            if not account.default_destination_id:
                raise osv.except_osv(_('Warning'), _('No default Destination defined for expense account: %s') % (account.code or '',))
            destination_id = account.default_destination_id and account.default_destination_id.id or False
            # But use those from CSV file if given
            if destination:
                dest_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', destination)])
                if dest_id:
                    destination_id = dest_id[0]
        # Retrieve Cost Center and Funding Pool
        if cost_center:
            cc_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', cost_center)])
            if not cc_id:
                raise osv.except_osv(_('Error'), _('Cost Center %s doesn\'t exist!') % (cost_center,))
            cc_id = cc_id[0]
        else:
            try:
                cc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1]
            except ValueError:
                cc_id = 0
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        vals.update({'destination_id': destination_id, 'cost_center_id': cc_id, 'analytic_id': fp_id, 'cost_center_id_first_value': cc_id, 'analytic_id_first_value': fp_id,})
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
        errors = []
        
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids):
            # Decode file string
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            fileobj.seek(0)
            # Read CSV file
            try:
                reader = csv.reader(fileobj, delimiter=',', quotechar='"')
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Problem to read given file.'))
            res = True
            res_amount = 0.0
            amount = 0.0
            # Omit first line that contains columns ' name
            reader.next()
            nbline = 1
            for line in reader:
                nbline += 1
                processed += 1
                try:
                    update = self.update_hq_entries(cr, uid, line)
                    created += 1
                except osv.except_osv, e:
                    errors.append('Line %s, %s'%(nbline, e.value))
            fileobj.close()
        
        if res:
            message = _("HQ Entries import successful")
        context.update({'message': message})
        
        if errors:
            cr.rollback()
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_error')
        else:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        # This is to redirect to HQ Entries Tree View
        context.update({'from': 'hq_entries_import'})
        

        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'total': processed, 'state': 'hq', 'errors':"\n".join(errors), 'nberrors': len(errors)})
        
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
