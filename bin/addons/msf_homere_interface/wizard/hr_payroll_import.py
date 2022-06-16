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
from tools import config
from base import currency_date
import time
import sys
import codecs

UF_SIDE_ROUNDING_LINE = {
    'account_code': '67000',
    'name': _('UF Payroll rounding'),

    'eur_gap_limit': 1.,  # EUR amount gap limit to not reach

    'msg_ok': _('Import ready to process. Do you want to proceed ?'),
    'msg_nb': _('Import file is not balanced. Do you want to proceed ? (System will automatically generate a rounding line worth %f %s at import)'),
}


class hr_payroll_import_period(osv.osv):
    _name = 'hr.payroll.import.period'
    _description = 'Payroll Import Periods'
    _rec_name = 'field'

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
        'state': fields.char(string="State", size=10),
        'file': fields.binary(string="File", filters="*.zip", required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'date_format': fields.selection([('%d/%m/%Y', 'dd/mm/yyyy'), ('%m-%d-%Y', 'mm-dd-yyyy'), ('%d-%m-%y', 'dd-mm-yy'), ('%d-%m-%Y', 'dd-mm-yyyy'), ('%d/%m/%y', 'dd/mm/yy'), ('%d.%m.%Y', 'dd.mm.yyyy')], "Date format", required=True, help="This is the date format used in the Homère file in order to recognize them."),
        'msg': fields.text(string='Message'),
    }

    _defaults = {
        'state': 'simu',
    }

    def _check_on_employee(self, cr, uid, third, second_description, debit, credit, account, is_counterpart, context=None):
        """
        Searches for the employee corresponding to data in "Third" or "Secondary description" column.
        Returns a tuple with the employee Identification No, and the employee id if it exists (else False).
        Raises an error if:
        - the employee doesn't exist and the account is analytic-a-holic
        - the same Identification ID matches several employees
        """
        if context is None:
            context = {}
        employee_obj = self.pool.get('hr.employee')
        employee_ids = []
        employee_identification_id = ""
        if third and third[0]:
            # the Third column should contain the exact code of the employee
            employee_identification_id = third[0]
            employee_ids = employee_obj.search(cr, uid,
                                               [('identification_id', '=', employee_identification_id)],
                                               context=context, order='NO_ORDER')
        # check the Secondary description if no employee found (no matter if the Third column is empty or not)
        if not employee_ids and second_description and second_description[0]:
            # Secondary description looks like "John Smith MWNP0001" => extract the employee code MWNP0001
            employee_identification_id = ustr(second_description[0]).split(' ')[-1]
            employee_ids = employee_obj.search(cr, uid,
                                               [('identification_id', '=', employee_identification_id)],
                                               context=context, order='NO_ORDER')
        if employee_identification_id and not employee_ids and account.is_analytic_addicted and not is_counterpart:
            raise osv.except_osv(_('Error'), _('No employee found for this code: %s.\nDEBIT: %s.\nCREDIT: %s.') % (
                employee_identification_id, debit, credit,))
        if employee_ids and len(employee_ids) > 1:
            raise osv.except_osv(_('Error'), _('More than one employee have the same identification ID: %s') % (
                employee_identification_id,))
        employee_id = employee_ids and employee_ids[0] or False
        return employee_identification_id, employee_id

    def update_payroll_entries(self, cr, uid,
                               data='', field='', date_format='%d/%m/%Y',
                               wiz_state='simu', bs_only=True,
                               context=None):
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
        vals = {}
        error_message = ""
        blocking_message = []
        # verify that some data exists
        if not data:
            return False, res_amount, created, vals, "", error_message, bs_only
        if not field:
            raise osv.except_osv(_('Error'), _('No field given for payroll import!'))
        # Prepare some values
        employee_id = False
        partner_id = False
        line_date = False
        name = ''
        ref = ''
        destination_id = False
        destination_code = False
        cost_center_id = False
        cost_center_code = False
        # US-671: This flag is used to indicate whether the DEST and CC of employee needs to be updated
        to_update_employee = False
        partner_obj = self.pool.get('res.partner')
        ad_obj = self.pool.get('analytic.distribution')

        # strip spaces in all columns
        for i in range(len(data)):
            data[i] = data[i].strip()
        if len(data) == 13:
            accounting_code, description, second_description, third, expense, receipt, project, financing_line, \
                financing_contract, date, currency, project, analytic_line = zip(data)
        else:
            accounting_code, description, second_description, third,  expense, receipt, project, financing_line, \
                financing_contract, date, currency, axis1, analytic_line, axis2, analytic_line2 = zip(data)

            # get active cc and dest args before searching
            aaa_obj = self.pool.get('account.analytic.account')
            date_args = aaa_obj._search_filter_active(cr, uid, [], None,  [('filter_active', '=', True)], context=context)

            #US-671: ONLY APPLY FOR THE SAGA THAT CONTAINS Project and Axis1 columns: Retrieve DEST and CC from the Project and axis1 columns
            if project and project[0]:
                # check if the project value exists as a valid costcenter in the local system
                condition = [('category', '=', 'OC'),('type', '!=', 'view'), ('state', '=', 'open'),('code', '=ilike', project[0]),]
                condition.extend(date_args)
                cc_ids = aaa_obj.search(cr, uid, condition, context=context)
                if cc_ids and cc_ids[0]:
                    cost_center_id = cc_ids[0]
                    cost_center_code = project[0]
                else:
                    error_message = _("Invalid Cost Center [%s] will be ignored.") % (project[0])
            if axis1 and axis1[0]:
                # check if the value exists as a valid DEST in the local system
                condition = [('category', '=', 'DEST'),('type', '!=', 'view'),('code', '=ilike', axis1[0]),]
                date_args.extend(condition)
                dest_ids = aaa_obj.search(cr, uid, date_args, context=context)
                if dest_ids and dest_ids[0]:
                    destination_id = dest_ids[0]
                    destination_code = axis1[0]
                else:
                    error_message = error_message + _("Invalid Destination [%s] will be ignored.") % (axis1[0])

        # Check period
        if not date and not date[0]:
            raise osv.except_osv(_('Warning'), _('A date is missing!'))
        try:
            line_date = time.strftime('%Y-%m-%d', time.strptime(date[0], date_format))
        except ValueError:
            raise osv.except_osv(_('Error'), _('Wrong format for date: %s') % date[0])
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
        # if view type or donation account, raise an error
        account = self.pool.get('account.account').browse(cr, uid, account_ids[0])
        if account.type == 'view':
            raise osv.except_osv(_('Warning'), _('This account is a view type account: %s') % (ustr(accounting_code[0]),))
        elif account.type_for_register == 'donation':
            raise osv.except_osv(_('Warning'), _('This account is a Donation account: %s') % (ustr(accounting_code[0]),))
        # Check if it's a payroll rounding line
        is_payroll_rounding = False
        if third and third[0] and ustr(third[0]) == 'SAGA_BALANCE' or accounting_code[0] == '67000':
            is_payroll_rounding = True
        # Check if it's a counterpart line (=> amount in credit)
        is_counterpart = False
        if credit:
            is_counterpart = True

        # Check on partner
        employee_identification_id = ''
        if not is_payroll_rounding:
            if third and third[0]:
                # If Third Party field is filled, check if it matches a Supplier (inactive partners are ignored by default)
                partner_id = partner_obj.search(cr, uid, [('name', '=ilike', third[0])], order='id', limit=1, context=context)
                partner_id = partner_id and partner_id[0] or False
            if not partner_id:
                # if no partner is found check that either the Third or the Secondary Description column matches an employee
                employee_identification_id, employee_id = self._check_on_employee(cr, uid, third, second_description,
                                                                                  debit, credit, account, is_counterpart, context)
        if account.is_analytic_addicted:
            bs_only = False
            if employee_id:
                # Create description
                name = _('Salary ') + str(time.strftime(' %b %Y', time.strptime(date[0], date_format)))
                if not is_counterpart:
                    # US_374: Add Employee number to description
                    name += " - " + employee_identification_id
                # Create reference
                date_format_separator = '/'
                if '-' in date_format:
                    date_format_separator = '-'
                elif '.' in date_format:
                    date_format_separator = '.'
                separator = str(time.strftime('%m' + date_format_separator + '%Y', time.strptime(date[0], date_format)))
                try:
                    ref = description and description[0] and ustr(description[0]).split(separator) and ustr(description[0]).split(separator)[1] or ''
                except IndexError:
                    ref = ''
            # US_263: get employee destination, if haven't get default destination
            if employee_id:
                emp = self.pool.get('hr.employee').browse(cr, uid, employee_id, context=context)
                if destination_id and destination_id !=  emp.destination_id.id:
                    to_update_employee = True # turn the flag to update the employee

                if not destination_id and emp.destination_id: # US-671: Only update if the destination from the import is not valid
                    destination_id = emp.destination_id.id
                    destination_code = emp.destination_id.code
            if not destination_id:
                if not account.default_destination_id:
                    raise osv.except_osv(_('Warning'), _('No default Destination defined for this account: %s') % (account.code or '',))
                destination_id = account.default_destination_id and account.default_destination_id.id or False
                destination_code = account.default_destination_id.code

        # Fetch description
        if not name:
            name = description and description[0] and ustr(description[0]) or ''
        if is_payroll_rounding:
            name = _('Payroll rounding')
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
            'partner_id': partner_id,
            'name': name,
            'ref': ref,
            'account_id': account.id,
            'amount': amount,
            'currency_id': currency_id,
            'state': 'draft',
            'field': field,
            'destination_id': destination_id,
        }
        # Retrieve analytic distribution from employee
        if employee_id:
            employee_data = self.pool.get('hr.employee').read(cr, uid, employee_id, ['cost_center_id', 'funding_pool_id', 'free1_id', 'free2_id', 'name_resource'])
            #US-671: use the cost center from the import, if not retrieve from employee
            temp_cc = employee_data and employee_data.get('cost_center_id', False) and employee_data.get('cost_center_id')[0] or False
            if cost_center_id and cost_center_id != temp_cc:
                to_update_employee =True
            if not cost_center_id:
                cost_center_id = temp_cc
                cost_center_code = employee_data.get('cost_center_id')[1]
            vals.update({
                'cost_center_id': cost_center_id,
                'funding_pool_id': employee_data and employee_data.get('funding_pool_id', False) and employee_data.get('funding_pool_id')[0] or False,
                'free1_id': employee_data and employee_data.get('free1_id', False) and employee_data.get('free1_id')[0] or False,
                'free2_id': employee_data and employee_data.get('free2_id', False) and employee_data.get('free2_id')[0] or False,
            })
            if wiz_state == 'simu' and to_update_employee:
                #check cc compat on (cost_center_id, destination_id, employee_data.funding_pool_id)
                if cost_center_id and destination_id and not ad_obj.check_dest_cc_compatibility(cr, uid, destination_id, cost_center_id, context=context):
                    blocking_message.append(_('Employee %s: the Cost Center %s is not compatible with the Destination %s.') % (employee_data['name_resource'], cost_center_code, destination_code))
                fp_id = employee_data.get('funding_pool_id', False) and employee_data.get('funding_pool_id')[0]
                if fp_id and cost_center_id and not ad_obj.check_fp_cc_compatibility(cr, uid, fp_id, cost_center_id, context=context):
                    blocking_message.append(_('Employee %s: the Cost Center %s is not compatible with the Funding Pool %s.') % (employee_data['name_resource'], cost_center_code, employee_data.get('funding_pool_id')[1]))
        # Write payroll entry
        if wiz_state != 'simu':
            #US-671: In the process mode, update the employee cost center and destination, and use also this one for the payroll object.
            ############################ UPDATE THE EMPLOYEE! AND PREPARE THE LOG FILE WITH WARNING!
            if to_update_employee and employee_id:
                self.pool.get('hr.employee').write(cr, uid, [employee_id], {'cost_center_id': cost_center_id, 'destination_id': destination_id,}, context)

            res = self.pool.get('hr.payroll.msf').create(cr, uid, vals,
                                                         context={'from': 'import'})
            if res:
                created += 1
        else:
            created += 1
        return True, amount, created, vals, currency[0], error_message, blocking_message, bs_only

    def _get_homere_password(self, cr, uid, pass_type='payroll'):
        ##### UPDATE HOMERE.CONF FILE #####
        if sys.platform.startswith('win'):
            homere_file = os.path.join(config['root_path'], 'homere.conf')
        else:
            homere_file = os.path.join(os.path.expanduser('~'),'tmp/homere.conf') # relative path from user directory to homere password file

        # Search homere password file
        if not os.path.exists(homere_file):
            raise osv.except_osv(_("Error"), _("File '%s' doesn't exist!") % (homere_file,))
        # Read homere file
        homere_file_data = open(homere_file, 'rb')
        pwd = homere_file_data.readline()
        if pass_type == 'permois':
            pwd = homere_file_data.readline()
        if not pwd:
            raise osv.except_osv(_("Error"), _("File '%s' does not contain the password !") % (homere_file,))
        homere_file_data.close()
        return pwd.decode('base64')

    def _uf_side_rounding_line_check_gap(self, cr, uid,
                                         currency_id, currency_code, curr_date, gap_amount, context=None):
        """
        US-201 check balance gap no more than 1 EUR
        """
        eur_gap_limit = UF_SIDE_ROUNDING_LINE.get('eur_gap_limit', 1.)

        eur_ids = self.pool.get('res.currency').search(cr, uid,
                                                       [('name', '=', 'EUR')], context=context)
        if not eur_ids:
            msg = _("%s: No EUR currency found") % (
                UF_SIDE_ROUNDING_LINE['name'], )
            raise osv.except_osv(_('Error'), msg)

        if eur_ids[0] != currency_id:
            # booking <> EUR
            new_ctx = context is not None and context.copy() or {}

            new_ctx['currency_date'] = curr_date
            eur_amount = self.pool.get('res.currency').compute(cr, uid,
                                                               currency_id, eur_ids[0], gap_amount, round=True,
                                                               context=new_ctx)

            if abs(eur_amount) > eur_gap_limit:
                msg = _("%s, import aborted, file is balanced with more than" \
                        " %0.02f EUR: %0.02f EUR, %0.02f %s.") % (
                            UF_SIDE_ROUNDING_LINE['name'],
                            eur_gap_limit,
                            eur_amount,
                            gap_amount,
                            currency_code,
                )
                raise osv.except_osv(_('Error'), msg)
        else:
            # booking = EUR
            if abs(gap_amount) > eur_gap_limit:
                msg = _("%s, import aborted, file is balanced with more than" \
                        " %0.02f EUR: %0.02f EUR") % (
                            UF_SIDE_ROUNDING_LINE['name'],
                            eur_gap_limit,
                            gap_amount,
                )
                raise osv.except_osv(_('Error'), msg)

    def _uf_side_rounding_line_create(self, cr, uid, ids,
                                      header_vals=None, amount=0., context=None, field=None):
        """
        US-201: no payroll rounding line, create a rounding payroll entry
        UF side (has importer users can not update the Homere archive)
        http://jira.unifield.org/browse/US-201?focusedCommentId=40713#comment-40713 case 2)
        """
        def err_account(account_code=False):
            msg = _('UF side rounding line account not found')
            if account_code:
                msg += " %s" % (account_code, )
            raise osv.except_osv(_('Error'), msg)

        if context is None:
            context = {}
        context['from'] = 'update'

        # get line account
        account_code = UF_SIDE_ROUNDING_LINE \
            and UF_SIDE_ROUNDING_LINE.get('account_code', False)
        if not account_code:
            err_account()
        account_ids = self.pool.get('account.account').search(cr, uid, [
            ('code', '=', account_code),
        ], context=context)
        if not account_ids:
            err_account(account_code=account_code)

        # get the default Destination to use
        acc_fields = ['default_destination_id', 'code', 'name']
        acc = self.pool.get('account.account').browse(cr, uid, account_ids[0], fields_to_fetch=acc_fields, context=context)
        if not acc.default_destination_id:
            raise osv.except_osv(_('Error'), _('The account %s - %s has no Default Destination.') % (acc.code, acc.name))
        dest = acc.default_destination_id

        # cost center: 1st FX gain loss of instance
        instance = self.pool.get('res.users').browse(cr, uid, [uid],
                                                     context=context)[0].company_id.instance_id
        cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [
            ('category', '=', 'OC'),
            ('for_fx_gain_loss', '=', True),
        ], context=context)
        if not cc_ids:
            msg = _("%s: No 'FX gain loss' cost center found" \
                    " for instance '%s'") % (UF_SIDE_ROUNDING_LINE['name'],
                                             instance.name, )
            raise osv.except_osv(_('Error'), msg)

        # create lines
        name = "%s %s" % (
            header_vals.get('name', ''),
            _(UF_SIDE_ROUNDING_LINE.get('name', False)),
        )
        self.pool.get('hr.payroll.msf').create(cr, uid, {
            'date': header_vals['date'],
            'document_date': header_vals['date'],
            'account_id': account_ids[0],
            'period_id': header_vals['period_id'],
            'name': name,
            'currency_id': header_vals['currency_id'],
            'state': 'draft',
            'amount': amount,
            'field': field or False,

            # AD
            'cost_center_id': cc_ids[0],
            'destination_id': dest.id,
            #'funding_pool_id':  # default is PF
        }, context=context)

    def button_simu(self, cr, uid, ids, context=None):
        return self._do_pass(cr, uid, ids, context=context)

    def button_proceed(self, cr, uid, ids, context=None):
        return self._do_pass(cr, uid, ids, context=context)

    def _do_pass(self, cr, uid, ids, context=None):
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
        message = _("Payroll import failed.")
        res = False
        created = 0
        processed = 0

        header_vals = {}

        xyargv = self._get_homere_password(cr, uid, pass_type='payroll')

        filename = ""
        error_msg = ""
        blocking_msg = []
        wiz_state = False
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids):
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            if not wiz_state:
                wiz_state = wiz.state

            # Decode file string
            fileobj = NamedTemporaryFile('w+b', delete=False)
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            filename = fileobj.name
            fileobj.close()
            try:
                zipobj = zf(filename, 'r')
                filename = wiz.filename or ""
            except:
                raise osv.except_osv(_('Error'), _('Given file is not a zip file!'))
            if zipobj.namelist():
                namelist = zipobj.namelist()
                # Search CSV
                csvfiles = []
                currency_list = []
                for name in namelist:
                    if name.split(file_ext_separator) and name.split(file_ext_separator)[-1] == file_ext:
                        csvfiles.append(name)
                if not 'envoi.ini' in namelist:
                    raise osv.except_osv(_('Warning'), _('No envoi.ini file found in given ZIP file!'))
                # Read information from 'envoi.ini' file
                field = False
                try:
                    import ConfigParser
                    Config = ConfigParser.SafeConfigParser()
                    ini_desc = zipobj.open('envoi.ini', 'r', xyargv)
                    is_bom = ini_desc.read(3)
                    if is_bom != codecs.BOM_UTF8:
                        ini_desc.close()
                        ini_desc = zipobj.open('envoi.ini', 'r', xyargv)
                    Config.readfp(ini_desc)
                    field = Config.get('DEFAUT', 'PAYS')
                except Exception:
                    raise osv.except_osv(_('Error'), _('Could not read envoi.ini file in given ZIP file.'))
                if not field:
                    raise osv.except_osv(_('Warning'), _('Field not found in envoi.ini file.'))
                # Read CSV files
                for csvfile in csvfiles:
                    try:
                        reader = csv.reader(zipobj.open(csvfile, 'r', xyargv), delimiter=';', quotechar='"', doublequote=False, escapechar='\\')
                        reader.next()
                    except:
                        fileobj.close()
                        raise osv.except_osv(_('Error'), _('Problem to read given file.'))
                    res = True
                    res_amount = 0.0
                    amount = 0.0
                    num_line = 1  # the header line is not taken into account
                    file_error_msg = ""  # store the error/warning messages for the current file
                    bs_only = True  # will be set to False as soon as one expense line is found in the file
                    for line in reader:
                        num_line += 1
                        processed += 1
                        update, amount, nb_created, vals, ccy, msg, blocking_message, bs_only = self.update_payroll_entries(
                            cr, uid, data=line, field=field,
                            date_format=wiz.date_format,
                            wiz_state=wiz.state,
                            bs_only=bs_only)
                        res_amount += round(amount, 2)
                        for block in blocking_message:
                            blocking_msg.append(_("Line %s: %s") % (str(num_line), block))
                        if not update:
                            res = False
                        if num_line == 2:  # the first line containing data
                            header_vals = vals
                            header_vals['currency_code'] = ccy  # note that the curr. is different from one file to another
                            if ccy in currency_list:
                                raise osv.except_osv(_('Error'), _('Several files contain lines with the currency %s. '
                                                                   'Please use one file per currency.') % ccy)
                            currency_list.append(ccy)
                        created += nb_created

                        if msg:
                            file_error_msg += _("Line %s: %s\n") % (str(num_line), msg)

                    if bs_only:
                        raise osv.except_osv(_('Error'), _('The file "%s" contains only B/S lines.') % csvfile)

                    # complete the list of error messages with the ones from this file if any
                    if file_error_msg:
                        # add a line break between files
                        error_msg += _("%sFile %s:\n%s") % (error_msg and "\n" or "", csvfile, file_error_msg)

                    # Check balance
                    res_amount_rounded = round(res_amount, 2)
                    if res_amount_rounded != 0.0:
                        curr_date = currency_date.get_date(self, cr, header_vals['document_date'], header_vals['date'])
                        self._uf_side_rounding_line_check_gap(cr, uid,
                                                              header_vals['currency_id'],
                                                              header_vals['currency_code'],
                                                              curr_date,
                                                              res_amount_rounded,
                                                              context=context)

                        # adapt difference by writing on payroll rounding line
                        pr_ids = self.pool.get('hr.payroll.msf').search(
                            cr, uid, [
                                ('state', '=', 'draft'),
                                ('name', '=', _('Payroll rounding')),
                                ('currency_id', '=', header_vals['currency_id']),
                            ])
                        if not pr_ids:
                            # no SAGA BALANCE rounding line in file
                            # => create one UF side (US-201)
                            if wiz.state == 'simu':
                                self.write(cr, uid, [wiz.id], {
                                    'state': 'proceed',
                                    'msg': UF_SIDE_ROUNDING_LINE['msg_nb'] % (
                                        res_amount_rounded,
                                        header_vals['currency_code'] , )
                                })
                            else:
                                self._uf_side_rounding_line_create(cr, uid, ids,
                                                                   context=context, header_vals=header_vals,
                                                                   amount=-1 * res_amount_rounded, field=field)
                            #raise osv.except_osv(_('Error'), _('An error occurred on balance and no payroll rounding line found.'))
                        else:
                            # Fetch Payroll rounding amount line and update
                            pr = self.pool.get('hr.payroll.msf').browse(cr, uid, pr_ids[0])
                            # To compute new amount, you should:
                            # - take payroll rounding amount
                            # - take the opposite of res_amount (wich is the current difference)
                            # - add both
                            new_amount = round(pr.amount, 2) + (-1 * res_amount_rounded)
                            self.pool.get('hr.payroll.msf').write(cr, uid, pr_ids[0], {'amount': round(new_amount, 2),})
                if not csvfiles:
                    raise osv.except_osv(_('Error'), _('Right CSV is not present in this zip file. Please use "File > File sending > Monthly" in Homère.'))
            fileobj.close()

        if wiz_state == 'simu' and ids:
            # US_201: if check raise no error, change state to process
            # US-671: Show message in the wizard if there was warning or not.
            if blocking_msg:
                error_msg = '%s:\n--------------------\n%s' % (_('Please correct following employee analytic distribution errors to allow Import to be processed'), "\n".join(blocking_msg))
            elif error_msg:
                error_msg = _("Import can be processed but with the following warnings:\n-------------------- \n") + error_msg
            else:
                error_msg = _("No warning found for this file. Import can be now processed.")

            self.write(cr, uid, [wiz.id], {'state': 'proceed', 'msg': error_msg})
            view_id = self.pool.get('ir.model.data').get_object_reference(cr,
                                                                          uid, 'msf_homere_interface', 'payroll_import_wizard')
            view_id = view_id and view_id[1] or False

            return {
                'name': 'Payroll Import Confirmation',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.payroll.import',
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': [view_id],
                'res_id': ids[0],
                'target': 'new',
                'context': context,
            }

        if res:
            message = _("Payroll import successful")
        context.update({'message': message})

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False

        # This is to redirect to Payroll Tree View
        context.update({'from': 'payroll_import'})

        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'filename': filename,'created': created, 'total': processed, 'state': 'payroll',}, context=context)

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
