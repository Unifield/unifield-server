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
from zipfile import ZipFile as zf
import csv
from tools.misc import ustr
from tools.translate import _
import time

class hr_payroll_import(osv.osv_memory):
    _name = 'hr.payroll.import'
    _description = 'Payroll Import'

    _columns = {
        'file': fields.binary(string="File", filters="*.zip", required=True),
    }

    def update_payroll_entries(self, cr, uid, data='', context={}):
        """
        Import payroll entries regarding 
        """
        # Some verifications
        if not context:
            context = {}
        res_amount = 0.0
        if not data:
            return False, res_amount
        # Prepare some values
        vals = {}
        employee_id = False
        line_date = False
        name = ''
        ref = ''
        accounting_code, description, second_description, third, expense, receipt, project, financing_line, \
        financing_contract, date, currency, project, analytic_line = zip(data)
        # Check period
        if not date and not date[0]:
            raise osv.except_osv(_('Warning'), _('A date is missing!'))
        try:
            line_date = time.strftime('%Y-%m-%d', time.strptime(date[0], '%d/%m/%Y'))
        except:
            raise osv.except_osv(_('Error'), _('Wrong format for date: %s' % date[0]))
        period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, line_date)
        if not period_ids:
            raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % line_date)
        if len(period_ids) > 1:
            raise osv.except_osv(_('Warning'), _('More than one period found for given date: %s') % line_date)
        period_id = period_ids[0]
        period = self.pool.get('account.period').browse(cr, uid, period_id)
        # Check that account exists in OpenERP
        if not accounting_code or not accounting_code[0]:
            raise osv.except_osv(_('Warning'), _('One accounting code is missing!'))
        account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', ustr(accounting_code[0]))])
        if not account_ids:
            raise osv.except_osv(_('Warning'), _('The accounting code \'%s\' doesn\'t exist!') % ustr(accounting_code[0]))
        if len(account_ids) > 1:
            raise osv.except_osv(_('Warning'), _('There is more than one account that have \'%s\' code!') % ustr(accounting_code[0]))
        # Verify account type. If expense type, fetch employee ID
        account = self.pool.get('account.account').browse(cr, uid, account_ids[0])
        if account.user_type.code == 'expense':
            # Check second description (if not equal to 'Payroll rounding')
            if second_description and second_description[0] and ustr(second_description[0]) != 'Payroll rounding':
                # fetch employee ID
                employee_identification_id = ustr(second_description[0]).split(' ')[-1]
                employee_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id', '=', employee_identification_id)])
                if not employee_ids:
                    raise osv.except_osv(_('Error'), _('No employee found for this code: %s.') % employee_identification_id)
                if len(employee_ids) > 1:
                    raise osv.except_osv(_('Error'), _('More than one employee have the same identification ID: %s') % employee_identification_id)
                employee_id = employee_ids[0]
                # Create description
                name = 'Salary ' + time.strftime('%b %Y')
                # Create reference
                ref = description and description[0] and ustr(description[0])
        # Fetch description
        if not name:
            name = description and description[0] and ustr(description[0]) or ''
        if ustr(second_description[0]) == 'Payroll rounding':
                name = 'Payroll rounding'
                ref = description and description[0] and ustr(description[0]) or ''
        debit = 0.0
        credit = 0.0
        if expense and expense[0]:
            debit = float(expense[0])
        if receipt and receipt[0]:
            credit = float(receipt[0])
        amount = debit - credit
        # Check if currency exists
        if not currency and not currency[0]:
            raise osv.except_osv(_('Warning'), _('One currency is missing!'))
        currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', ustr(currency[0])), ('active', '=', True)])
        if not currency_ids:
            raise osv.except_osv(_('Error'), _('No \'%s\' currency or non-active currency.') % ustr(currency[0]))
        if len(currency_ids) > 1:
            raise osv.except_osv(_('Error'), _('More than one currency \'%s\' found.') % ustr(currency[0]))
        currency_id = currency_ids[0]
        # Create the payroll entry
        vals = {
            'date': line_date,
            'period_id': period_id,
            'employee_id': employee_id,
            'name': name,
            'ref': ref,
            'account_id': account.id,
            'amount': amount,
            'currency_id': currency_id,
            'state': 'draft',
        }
        # Retrieve analytic distribution from employee
        if employee_id:
            employee_data = self.pool.get('hr.employee').read(cr, uid, employee_id, ['cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id'])
            vals.update({
                'cost_center_id': employee_data and employee_data.get('cost_center_id', False) and employee_data.get('cost_center_id')[0] or False,
                'funding_pool_id': employee_data and employee_data.get('funding_pool_id', False) and employee_data.get('funding_pool_id')[0] or False,
                'free1_id': employee_data and employee_data.get('free1_id', False) and employee_data.get('free1_id')[0] or False,
                'free2_id': employee_data and employee_data.get('free2_id', False) and employee_data.get('free2_id')[0] or False,
            })
        # Write payroll entry
        self.pool.get('hr.payroll.msf').create(cr, uid, vals, context={'from': 'import'})
        return True, amount

    def button_validate(self, cr, uid, ids, context={}):
        """
        Open ZIP file, take the CSV file into and parse it to import payroll entries
        """
        # Do verifications
        if not context:
            context = {}
        
        # Verify that no draft payroll entries exists
        line_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [('state', '=', 'draft')])
        if len(line_ids):
            raise osv.except_osv(_('Error'), _('You cannot import payroll entries. Please validate first draft payroll entries!'))
        
        # Prepare some values
        file_ext_separator = '.'
        file_ext = "csv"
        relativepath = 'tmp/homere.password' # relative path from user directory to homere password file
        message = "Payroll import failed."
        res = False
        
        # Search homere password file
        homere_file = os.path.join(os.path.expanduser('~'),relativepath)
        if not os.path.exists(homere_file):
            raise osv.except_osv(_("Error"), _("File '%s' doesn't exist!") % homere_file)
        
        # Read homere file
        homere_file_data = open(homere_file, 'rb')
        if homere_file_data:
            pwd = homere_file_data.readlines()[0]
        xyargv = pwd.decode('base64')
        
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids):
            # Decode file string
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            fileobj.seek(0)
            zipobj = zf(fileobj.name, 'r')
            if zipobj.namelist():
                namelist = zipobj.namelist()
                # Search CSV
                csvfile = None
                for name in namelist:
                    if name.split(file_ext_separator) and name.split(file_ext_separator)[-1] == file_ext:
                      csvfile = name
                if csvfile:
                    reader = csv.reader(zipobj.open(csvfile, 'r', xyargv), delimiter=';', quotechar='"', doublequote=False, escapechar='\\')
                    if reader:
                        reader.next()
                    res = True
                    res_amount = 0.0
                    amount = 0.0
                    for line in reader:
                        update, amount = self.update_payroll_entries(cr, uid, line)
                        res_amount += amount
                        if not update:
                            res = False
                    if res_amount != 0.0 and abs(res_amount) >= 10**-2:
                        raise osv.except_osv(_('Error'), _('Elements from given file are unbalanced!'))
            fileobj.close()
        
        if res:
            message = "Payroll import successful"
        context.update({'message': message})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        return {
            'name': 'Payroll Import Confirmation',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.import.confirmation',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'target': 'new',
            'context': context,
        }

hr_payroll_import()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
