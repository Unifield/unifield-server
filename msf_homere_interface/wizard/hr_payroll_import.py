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

class hr_payroll_import_period(osv.osv):
    _name = 'hr.payroll.import.period'
    _description = 'Payroll Import Periods'

    _columns = {
        'field': fields.char('Field', size=255, readonly=True, required=True),
        'period_id': fields.many2one('account.period', string="Period", required=True, readonly=True),
    }

    _sql_constraints = [
        ('period_uniq', 'unique (period_id, field)', 'This period have already been validated!'),
    ]

hr_payroll_import_period()

class hr_payroll_import(osv.osv_memory):
    _name = 'hr.payroll.import'
    _description = 'Payroll Import'

    _columns = {
        'file': fields.binary(string="File", filters="*.zip", required=True),
    }

    def update_payroll_entries(self, cr, uid, data='', field='', context=None):
        """
        Import payroll entries regarding all elements given in "data"
        """
        # Some verifications
        if not context:
            context = {}
        # Prepare some values
        # to have more info on import
        res_amount = 0.0
        res = False
        created = 0
        # verify that some data exists
        if not data:
            return False, res_amount, created
        if not field:
            raise osv.except_osv(_('Error'), _('No field given for payroll import!'))
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
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Wrong format for date: %s' % date[0]))
        period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, line_date)
        if not period_ids:
            raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % (line_date,))
        if len(period_ids) > 1:
            raise osv.except_osv(_('Warning'), _('More than one period found for given date: %s') % (line_date,))
        period_id = period_ids[0]
        period = self.pool.get('account.period').browse(cr, uid, period_id)
        # Check that period have not been inserted in database yet
        period_validated_ids = self.pool.get('hr.payroll.import.period').search(cr, uid, [('period_id', '=', period_id), ('field', '=', field)])
        if period_validated_ids:
            raise osv.except_osv(_('Error'), _('Payroll entries have already been validated for: %s in this period: "%s"!') % (field, period.name,))
        period = self.pool.get('account.period').browse(cr, uid, period_id)
        # Check that account exists in OpenERP
        if not accounting_code or not accounting_code[0]:
            raise osv.except_osv(_('Warning'), _('One accounting code is missing!'))
        account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', ustr(accounting_code[0]))])
        if not account_ids:
            raise osv.except_osv(_('Warning'), _('The accounting code \'%s\' doesn\'t exist!') % (ustr(accounting_code[0]),))
        if len(account_ids) > 1:
            raise osv.except_osv(_('Warning'), _('There is more than one account that have \'%s\' code!') % (ustr(accounting_code[0]),))
        # Fetch DEBIT/CREDIT
        debit = 0.0
        credit = 0.0
        if expense and expense[0]:
            debit = float(expense[0])
        if receipt and receipt[0]:
            credit = float(receipt[0])
        amount = round(debit - credit, 2)
        # Verify account type
        # if view type, raise an error
        account = self.pool.get('account.account').browse(cr, uid, account_ids[0])
        if account.type == 'view':
            raise osv.except_osv(_('Warning'), _('This account is a view type account: %s') % (ustr(accounting_code[0]),))
        # Check if it's a payroll rounding line
        is_payroll_rounding = False
        if third and third[0] and ustr(third[0]) == 'SAGA_BALANCE':
            is_payroll_rounding = True
        # Check if it's a counterpart line (In HOMERE import, it seems to be lines that have a filled in column "third")
        is_counterpart = False
        if third and third[0] and third[0] != '':
            is_counterpart = True
        # If expense type, fetch employee ID
        if account.user_type.code == 'expense':
            if second_description and second_description[0] and not is_payroll_rounding:
                if not is_counterpart:
                    # fetch employee ID
                    employee_identification_id = ustr(second_description[0]).split(' ')[-1]
                    employee_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id', '=', employee_identification_id)])
                    if not employee_ids:
                        employee_name = ustr(second_description[0]).replace(employee_identification_id, '')
                        raise osv.except_osv(_('Error'), _('No employee found for this code: %s (%s).\nDEBIT: %s.\nCREDIT: %s.') % (employee_identification_id, employee_name, debit, credit,))
                    if len(employee_ids) > 1:
                        raise osv.except_osv(_('Error'), _('More than one employee have the same identification ID: %s') % (employee_identification_id,))
                    employee_id = employee_ids[0]
                # Create description
                name = 'Salary ' + str(time.strftime('%b %Y', time.strptime(date[0], '%d/%m/%Y')))
                # Create reference
                separator = str(time.strftime('%m/%Y', time.strptime(date[0], '%d/%m/%Y')))
                ref = description and description[0] and ustr(description[0]).split(separator) and ustr(description[0]).split(separator)[1] or ''
        # Fetch description
        if not name:
            name = description and description[0] and ustr(description[0]) or ''
        if is_payroll_rounding:
            name = 'Payroll rounding'
        if not employee_id:
            if second_description and second_description[0]:
                ref = ustr(second_description[0])
        # Check if currency exists
        if not currency and not currency[0]:
            raise osv.except_osv(_('Warning'), _('One currency is missing!'))
        currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', ustr(currency[0])), ('active', '=', True)])
        if not currency_ids:
            raise osv.except_osv(_('Error'), _('No \'%s\' currency or non-active currency.') % (ustr(currency[0]),))
        if len(currency_ids) > 1:
            raise osv.except_osv(_('Error'), _('More than one currency \'%s\' found.') % (ustr(currency[0]),))
        currency_id = currency_ids[0]
        # Create the payroll entry
        vals = {
            'date': line_date,
            'document_date': line_date,
            'period_id': period_id,
            'employee_id': employee_id,
            'name': name,
            'ref': ref,
            'account_id': account.id,
            'amount': amount,
            'currency_id': currency_id,
            'state': 'draft',
            'field': field,
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
        res = self.pool.get('hr.payroll.msf').create(cr, uid, vals, context={'from': 'import'})
        if res:
            created += 1
        return True, amount, created

    def button_validate(self, cr, uid, ids, context=None):
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
        message = _("Payroll import failed.")
        res = False
        created = 0
        processed = 0
        
        # Search homere password file
        homere_file = os.path.join(os.path.expanduser('~'),relativepath)
        if not os.path.exists(homere_file):
            raise osv.except_osv(_("Error"), _("File '%s' doesn't exist!") % (homere_file,))
        
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
            try:
                zipobj = zf(fileobj.name, 'r')
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Given file is not a zip file!'))
            if zipobj.namelist():
                namelist = zipobj.namelist()
                # Search CSV
                csvfile = None
                for name in namelist:
                    if name.split(file_ext_separator) and name.split(file_ext_separator)[-1] == file_ext:
                        csvfile = name
                if not 'envoi.ini' in namelist:
                    raise osv.except_osv(_('Warning'), _('No envoi.ini file found in given ZIP file!'))
                # Read information from 'envoi.ini' file
                field = False
                try:
                    import ConfigParser
                    Config = ConfigParser.SafeConfigParser()
                    Config.readfp(zipobj.open('envoi.ini', 'r', xyargv))
                    field = Config.get('DEFAUT', 'PAYS')
                except Exception, e:
                    raise osv.except_osv(_('Error'), _('Could not read envoi.ini file in given ZIP file.'))
                if not field:
                    raise osv.except_osv(_('Warning'), _('Field not found in envoi.ini file.'))
                # Read CSV file
                if csvfile:
                    try:
                        reader = csv.reader(zipobj.open(csvfile, 'r', xyargv), delimiter=';', quotechar='"', doublequote=False, escapechar='\\')
                        reader.next()
                    except:
                        fileobj.close()
                        raise osv.except_osv(_('Error'), _('Problem to read given file.'))
                    res = True
                    res_amount = 0.0
                    amount = 0.0
                    for line in reader:
                        processed += 1
                        update, amount, nb_created = self.update_payroll_entries(cr, uid, line, field)
                        res_amount += round(amount, 2)
                        if not update:
                            res = False
                        created += nb_created
                    # Check balance
                    if round(res_amount, 2) != 0.0:
                        # adapt difference by writing on payroll rounding line
                        pr_ids = self.pool.get('hr.payroll.msf').search(cr, uid, [('state', '=', 'draft'), ('name', '=', 'Payroll rounding')])
                        if not pr_ids:
                            raise osv.except_osv(_('Error'), _('An error occured on balance and no payroll rounding line found.'))
                        # Fetch Payroll rounding amount
                        pr = self.pool.get('hr.payroll.msf').browse(cr, uid, pr_ids[0])
                        # To compute new amount, you should:
                        # - take payroll rounding amount
                        # - take the opposite of res_amount (wich is the current difference)
                        # - add both
                        new_amount = round(pr.amount, 2) + (-1 * round(res_amount, 2))
                        self.pool.get('hr.payroll.msf').write(cr, uid, pr_ids[0], {'amount': round(new_amount, 2),})
                else:
                    raise osv.except_osv(_('Error'), _('Right CSV is not present in this zip file. Please use "File > File sending > Monthly" in Homère.'))
            fileobj.close()
        
        if res:
            message = _("Payroll import successful")
        context.update({'message': message})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        # This is to redirect to Payroll Tree View
        context.update({'from': 'payroll_import'})
        
        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'total': processed, 'state': 'payroll'})
        
        return {
            'name': 'Payroll Import Confirmation',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.import.confirmation',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

hr_payroll_import()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
