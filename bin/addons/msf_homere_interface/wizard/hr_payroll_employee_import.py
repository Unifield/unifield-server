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

from zipfile import ZipFile as zf
from zipfile import is_zipfile
import io
from osv import osv
from osv import fields
from tempfile import NamedTemporaryFile,mkdtemp
import csv
from base64 import b64decode
from time import strftime
from tools.misc import ustr
from addons import get_module_resource
from tools.which import which
from tools.translate import _
from lxml import etree
import subprocess
import os
import shutil
import configparser

def get_7z():
    if os.name == 'nt':
        return get_module_resource('msf_homere_interface', 'wizard', '7za.exe')
    try:
        return which('7z')
    except:
        raise osv.except_osv(_('Error'), _('7z is not installed on the server. Please install the package p7zip-full'))



class hr_payroll_import_confirmation(osv.osv_memory):
    _name = 'hr.payroll.import.confirmation'
    _description = 'Import Confirmation'

    def _get_from(self, cr, uid, ids, name, arg, context=None):
        """
        Returns the value stored in context at index "from" = from where the wizard has been opened
        """
        if context is None:
            context = {}
        res = {}
        for wiz_id in ids:
            res[wiz_id] = context.get('from')
        return res

    _columns = {
        'updated': fields.integer(string="Updated", size=64, readonly=True),
        'created': fields.integer(string="Created", size=64, readonly=True),
        'rejected': fields.integer(string="Rejected", size=64, readonly=True),
        'total': fields.integer(string="Processed", size=64, readonly=True),
        'state': fields.selection([('none', 'None'), ('employee', 'From Employee'), ('payroll', 'From Payroll'), ('hq', 'From HQ Entries')],
                                  string="State", required=True, readonly=True),
        'error_line_ids': fields.many2many("hr.payroll.employee.import.errors", "employee_import_error_relation", "wizard_id", "error_id", "Error list",
                                           readonly=True),
        'errors': fields.text(string="Errors", readonly=True),
        'nberrors': fields.integer(string="Errors", readonly=True),
        'filename': fields.char(string="Filename", size=256, readonly=True),
        # WARNING: this wizard model is used for the import of employees from Homere, expats, nat. staff, Payroll, HQ entries...
        'from': fields.function(_get_from, type='char', method=True, string="From where has this wizard been opened?", store=False),
    }

    _defaults = {
        'updated': lambda *a: 0,
        'created': lambda *a: 0,
        'rejected': lambda *a: 0,
        'total': lambda *a: 0,
        'state': lambda *a: 'none',
        'nberrors': lambda *a: 0,
    }

    def create(self, cr, uid, vals, context=None):
        """
        Attach errors if context contents "employee_import_wizard_ids"
        """
        if not context:
            context={}
        if context.get('employee_import_wizard_ids', False):
            wiz_ids = context.get('employee_import_wizard_ids')
            if isinstance(wiz_ids, int):
                wiz_ids = [wiz_ids]
            line_ids = self.pool.get('hr.payroll.employee.import.errors').search(cr, uid, [('wizard_id', 'in', wiz_ids)])
            if line_ids:
                vals.update({'error_line_ids': [(6, 0, line_ids)], 'nberrors': len(line_ids) or 0})
        return super(hr_payroll_import_confirmation, self).create(cr, uid, vals, context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change message field
        """
        if not context:
            context = {}
        view = super(hr_payroll_import_confirmation, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='form' and context.get('message', False):
            message = context.get('message')
            tree = etree.fromstring(view['arch'])
            labels = tree.xpath('/form/label[@string="Nothing"]')
            for label in labels:
                label.set('string', "%s" % message)
            view['arch'] = etree.tostring(tree, encoding='unicode')
        return view

    def button_validate(self, cr, uid, ids, context=None):
        """
        Return rigth view
        """
        if not context:
            return {'type': 'ir.actions.act_window_close'}
        # Clean up error table
        if context.get('employee_import_wizard_ids', False):
            wiz_ids = context.get('employee_import_wizard_ids')
            if isinstance(wiz_ids, int):
                wiz_ids = [wiz_ids]
            line_ids = self.pool.get('hr.payroll.employee.import.errors').search(cr, uid, [('wizard_id', 'in', wiz_ids)])
            if line_ids:
                self.pool.get('hr.payroll.employee.import.errors').unlink(cr, uid, line_ids)
        if context.get('from', False):
            result = False
            domain = False
            if context.get('from') == 'employee_import':
                result = ('editable_view_employee_tree', 'hr.employee')
                context.update({'search_default_active': 1})
                domain = "[('employee_type', '=', 'local')]"
            if context.get('from') == 'payroll_import':
                result = ('view_hr_payroll_msf_tree', 'hr.payroll.msf')
                domain = "[('state', '=', 'draft'), ('account_id.is_analytic_addicted', '=', True)]"
            if context.get('from') == 'hq_entries_import':
                result = ('hq_entries_tree', 'hq.entries', 'account_hq_entries')
                domain = ""
                context.update({'search_default_non_validated': 1})
            if context.get('from') == 'expat_employee_import':
                context.update({'search_default_employee_type_expatriate': 1})
                action = self.pool.get('ir.actions.act_window').for_xml_id(cr,
                                                                           uid, 'hr', 'open_view_employee_list_my', context=context)
                action['target'] = 'same'
                action['context'] = context
                return action
            if context.get('from') == 'nat_staff_import':
                result = ('inherit_view_employee_tree', 'hr.employee')
                context.update({'search_default_employee_type_local': 1, 'search_default_active': 1})
            if result:
                module_name = 'msf_homere_interface'
                if result and len(result) > 2:
                    module_name = result[2]
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module_name, result[0])
                if view_id:
                    view_id = view_id and view_id[1] or False
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': result[1],
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'view_id': [view_id],
                    'target': 'crush',
                    'context': context,
                    'domain': domain,
                }
        return {'type': 'ir.actions.act_window_close', 'context': context}

hr_payroll_import_confirmation()

class hr_payroll_employee_import_errors(osv.osv):
    _name = 'hr.payroll.employee.import.errors'
    _rec_name = 'wizard_id'
    _description = 'Employee Import Errors'

    _columns = {
        'wizard_id': fields.integer("Payroll employee import wizard", readonly=True, required=True),
        'msg': fields.text("Message", readonly=True, required=True),
    }

hr_payroll_employee_import_errors()

class hr_payroll_employee_import(osv.osv_memory):
    _name = 'hr.payroll.employee.import'
    _description = 'Employee Import'

    _columns = {
        'file': fields.binary(string="File", filters='*.zip', required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    def store_error(self, errors, wizard_id, message):
        """
        Stores the "message" in the dictionary "errors" at index "wizard_id"
        """
        if errors is not None:
            if wizard_id not in errors:
                errors[wizard_id] = []
            errors[wizard_id].append(message)

    def generate_errors(self, cr, uid, errors, context=None):
        """
        Deletes the old errors in DB and replaces them by the new ones
        """
        if context is None:
            context = {}
        error_obj = self.pool.get('hr.payroll.employee.import.errors')
        error_ids = error_obj.search(cr, uid, [], order='NO_ORDER', context=context)
        if error_ids:
            error_obj.unlink(cr, uid, error_ids, context=context)
        for wiz_id in errors:
            for err in errors[wiz_id]:
                error_obj.create(cr, uid, {'wizard_id': wiz_id, 'msg': err}, context=context)

    def read_employee_infos(self, cr, uid, line='', context=None):
        """
        Read each line to extract infos (code, name and surname)
        """
        res = False
        code_staff = line.get('code_staff', False)
        nom = line.get('nom', False)
        prenom = line.get('prenom', False)
        if code_staff:
            res = (code_staff, nom, prenom)
        return res

    def update_employee_infos(self, cr, uid, employee_data='', wizard_id=None,
                              line_number=None, errors=None, context=None):
        """
        Get employee infos and set them to DB.
            return (status (True/False), is_new (0/1), is_update (0/1))

        if status is False: full import is blocked

        """

        if context is None:
            context = {}

        if line_number is not None:
            line_number = line_number + 2  # cf. the count starts at "1" and the header line is ignored

        payment_method_obj = self.pool.get('hr.payment.method')
        if not employee_data or not wizard_id:
            message = _('No data found for this line: %s.') % line_number
            self.store_error(errors, wizard_id, message)
            return False, 0, 0

        # Prepare some values
        vals = {}
        # Extract information
        try:
            code_staff = employee_data.get('code_staff', False) # UF identification_id
            codeterrain = employee_data.get('codeterrain', False)
            decede = employee_data.get('decede', False)
            id_staff = employee_data.get('id_staff', False)
            id_unique = employee_data.get('id_unique', False)
            uuid_key = employee_data.get('uuid_key', False) # UF home_uuid_key
            nom = employee_data.get('nom', False)
            prenom = employee_data.get('prenom', False)
            bqmodereglement = employee_data.get('bqmodereglement', False)
            bqnom = employee_data.get('bqnom', False)
            bqnumerocompte = employee_data.get('bqnumerocompte', False)
        except ValueError as e:
            raise osv.except_osv(_('Error'), _('The given file is probably corrupted!\n%s') % (e))

        # check max uuid size
        uuid_field = self.pool.get('hr.employee')._columns.get('homere_uuid_key')
        if uuid_key and uuid_field:
            uuid_key = ustr(uuid_key)
            uuid_field_size = uuid_field.size
            if len(uuid_key) > uuid_field_size:
                message = _('Line %s. The UUID_key has more than %d characters.') % (line_number, uuid_field_size)
                self.store_error(errors, wizard_id, message)
                return False, 0, 0

        # Due to UF-1742, if no id_unique, we fill it with "empty"
        uniq_id = id_unique or False
        if not id_unique:
            uniq_id = 'empty'

        if not codeterrain or not id_staff or not code_staff:
            message = _('Line %s. One of this column is missing: code_terrain, id_unique or id_staff. This often happens when the line is empty.') % (line_number, )
            self.store_error(errors, wizard_id, message)
            return False, 0, 0

        if not uuid_key:
            self.store_error(errors, wizard_id, _('Line %s. Required Homere uuid_key field is missing in the file.') % (line_number, ))
            return False, 0, 0

        # Employee name
        nom = nom and nom.strip() or ''
        prenom = prenom and prenom.strip() or ''
        employee_name = (nom and prenom and ustr(nom) + ', ' + ustr(prenom)) or (nom and ustr(nom)) or (prenom and ustr(prenom)) or False


        # employee by uuid_key
        e_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_uuid_key', '=', uuid_key)])
        if len(e_ids) > 1:
            with_id_staff_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_uuid_key', '=', uuid_key), ('homere_id_staff', '=', id_staff)])
            if len(with_id_staff_ids) == 1:
                e_ids = with_id_staff_ids
            else:
                dups = self.pool.get('hr.employee').browse(cr, uid, e_ids, fields_to_fetch=['name', 'homere_id_staff'])
                if len(with_id_staff_ids) > 1:
                    self.store_error(errors, wizard_id, _('Homere uuid_key %s is duplicated in the UF database, Homere id_staff: %s, number of records: %d: %s') % (uuid_key, id_staff, len(with_id_staff_ids), '; '.join([x.name for x in dups])))
                    return False, 0, 0
                else:
                    self.store_error(errors, wizard_id, _('Homere uuid_key %s is duplicated in the UF database, but no match with id_staff %s, number of records: %d: %s') % (uuid_key, id_staff, len(e_ids), '; '.join(['%s %s'%(x.name, x.homere_id_staff) for x in dups])))
                    return False, 0, 0
        if not e_ids:
            # else no uuid, same name, same identification_id
            e_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id','=', code_staff), ('name', '=', employee_name), ('homere_uuid_key', '=', False)])
            if len(e_ids) > 1:
                self.store_error(errors, wizard_id,
                                 _('%d employees in the db have the same combination identification_id/name/empty uuid "%s / %s "') %
                                 (len(e_ids), code_staff, employee_name)
                                 )
                return False, 0, 0

            if not e_ids:
                # Search employee regarding a unique trio: codeterrain, id_staff, id_unique
                e_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_codeterrain', '=', codeterrain), ('homere_id_staff', '=', id_staff), ('homere_id_unique', '=', uniq_id), ('homere_uuid_key', '=', False)])
                if len(e_ids) > 1:
                    dups = self.pool.get('hr.employee').browse(cr, uid, e_ids, fields_to_fetch=['name'])
                    self.store_error(errors, wizard_id,
                                     _('Several employees in the db have the same combination codeterrain/id_staff/(id_unique)/empty uuid "%s / %s / (%s)": %s') %
                                     (codeterrain, id_staff, uniq_id, ' ; '.join([x.name for x in dups]))
                                     )
                    return False, 0, 0

        if code_staff:
            employee_dom = [('identification_id', '=', code_staff)]
            if e_ids:
                employee_dom.append(('id', '!=', e_ids[0]))
            dup_ids = self.pool.get('hr.employee').search(cr, uid, employee_dom, context=context)
            if dup_ids:
                dups = self.pool.get('hr.employee').browse(cr, uid, dup_ids, fields_to_fetch=['name'])
                self.store_error(errors, wizard_id,
                                 _('Several employees have the same identification_id %s: %s (Import file), %s') %
                                 (code_staff, employee_name, ','.join(['%s (UniField)' % x.name for x in dups]))
                                 )
                return False, 0, 0

        vals = {
            'active': True,
            'employee_type': 'local',
            'homere_codeterrain': codeterrain,
            'homere_id_staff': id_staff,
            'homere_id_unique': uniq_id,
            'homere_uuid_key': uuid_key,
            'photo': False,
            'identification_id': code_staff or False,
            'name': employee_name,
            'bank_name': bqnom,
            'bank_account_number': bqnumerocompte,
        }


        # Update the payment method
        payment_method_id = False
        if bqmodereglement:
            payment_method_ids = payment_method_obj.search(cr, uid, [('name', '=', bqmodereglement)], limit=1, context=context)
            if payment_method_ids:
                payment_method_id = payment_method_ids[0]
            else:
                message = _('Payment Method %s not found for line: %s. Please fix Homere configuration or request a new Payment Method to the HQ.') % (ustr(bqmodereglement), line_number)
                self.store_error(errors, wizard_id, message)
                return False, 0, 0

        vals.update({'payment_method_id': payment_method_id})

        # In case of death, desactivate employee
        if decede and decede == 'Y':
            vals.update({'active': False})
        # Desactivate employee if:
        # - no contract line found
        # - end of current contract exists and is inferior to current date
        # - no contract line found with current = True

        # sort contract: get current one, then by start date
        contract_ids = self.pool.get('hr.contract.msf').search(cr, uid, [('homere_codeterrain', '=', codeterrain), ('homere_id_staff', '=', id_staff)], order='current desc,date_start desc')
        if not contract_ids:
            vals.update({'active': False})
        current_contract = False
        if contract_ids:
            contract = self.pool.get('hr.contract.msf').browse(cr, uid, contract_ids[0])
            # Check current contract
            if contract.current:
                current_contract = True
                if contract.date_end and contract.date_end < strftime('%Y-%m-%d'):
                    vals.update({'active': False})
                # Check job
                if contract.job_name:
                    vals.update({'job_name': contract.job_name})
            # Check the contract dates
            vals.update({'contract_start_date': contract.date_start or False})
            vals.update({'contract_end_date': contract.date_end or False})
        # Desactivate employee if no current contract
        if not current_contract:
            vals.update({'active': False})

        created = 0
        updated = 0

        if not e_ids:
            self.pool.get('hr.employee').create(cr, uid, vals, {'from': 'import'})
            created = 1
        else:
            self.pool.get('hr.employee').write(cr, uid, e_ids, vals, {'from': 'import'})
            updated = 1


        return True, created, updated

    def update_contract(self, cr, uid, ids, reader, context=None):
        """
        Read lines from reader and update database
        """
        res = []
        if not reader:
            return res
        for line in reader:
            if not line.get('contratencours'): #or not line.get('contratencours') == 'O':
                continue
            vals = {
                'homere_codeterrain': line.get('codeterrain') or False,
                'homere_id_staff': line.get('id_staff') or False,
                'homere_id_unique': line.get('id_unique') or 'empty',
                'current': False,
            }
            # Update values for current field
            if line.get('contratencours'):
                if line.get('contratencours') == 'O':
                    vals.update({'current': True})
            # Update values for datedeb and datefin fields
            for field in [('datedeb', 'date_start'), ('datefin', 'date_end')]:
                if line.get(field[0]):
                    if line.get(field[0]) == '0000-00-00':
                        vals.update({field[1]: False})
                    else:
                        vals.update({field[1]: line.get(field[0])})
            # Update values for job
            if line.get('libfonction', False):
                vals.update({'job_name': line.get('libfonction')})
            # Add entry to database
            new_line = self.pool.get('hr.contract.msf').create(cr, uid, vals)
            if new_line:
                res.append(new_line)
        return res

    def _extract_7z(self, cr, uid, filename):
        tmp_dir = mkdtemp()
        passwd = self.pool.get('hr.payroll.import')._get_homere_password(cr, uid, pass_type='permois')
        szexe = get_7z()
        devnull = open(os.devnull, 'w')
        szret = subprocess.call([szexe, 'x', '-p%s' % passwd, '-o%s' % tmp_dir, '-y', filename], stdout=devnull)
        devnull.close()
        if szret != 0:
            raise osv.except_osv(_('Error'), _('Error when extracting the file with 7-zip'))
        return tmp_dir

    def read_files(self, cr, uid, filename):
        staff_file = 'staff.csv'
        contract_file = 'contrat.csv'
        job_file = 'fonction.csv'
        ini_file = 'envoi.ini'
        job_reader =False
        contract_reader = False
        staff_reader = False
        config_parser = False
        desc_to_close = []
        tmpdir = False
        encoding = self.pool.get('ir.config_parameter').get_param(cr, uid, 'HOMERE_ENCODING')
        if not encoding:
            encoding = 'iso-8859-15'
        if is_zipfile(filename):
            zipobj = zf(filename)
            if zipobj:
                desc_to_close.append(zipobj)
            if zipobj.namelist() and job_file in zipobj.namelist():
                job_reader = csv.DictReader(io.TextIOWrapper(zipobj.open(job_file), encoding=encoding), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
                # Do not raise error for job file because it's just a useful piece of data, but not more.
            # read the contract file
            if zipobj.namelist() and contract_file in zipobj.namelist():
                contract_reader = csv.DictReader(io.TextIOWrapper(zipobj.open(contract_file), encoding=encoding), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
            # read the staff file
            if zipobj.namelist() and staff_file in zipobj.namelist():
                # Doublequote and escapechar avoid some problems
                staff_reader = csv.DictReader(io.TextIOWrapper(zipobj.open(staff_file), encoding=encoding), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
            # read the ini file
            if zipobj.namelist() and ini_file in zipobj.namelist():
                ini_desc = zipobj.open(ini_file, 'r')
                config_parser = configparser.SafeConfigParser()
                # io.TextIOWrapper to open the file as text instead of binary (required by config_parser)
                config_parser.read_file(io.TextIOWrapper(ini_desc, encoding='utf_8_sig'))
        else:
            tmpdir = self._extract_7z(cr, uid, filename)
            job_file_name = os.path.join(tmpdir, job_file)
            if os.path.isfile(job_file_name):
                job_file_desc = open(job_file_name, 'r', encoding=encoding)
                desc_to_close.append(job_file_desc)
                job_reader = csv.DictReader(job_file_desc, quotechar='"', delimiter=',', doublequote=False, escapechar='\\')

            contract_file_name = os.path.join(tmpdir, contract_file)
            if os.path.isfile(contract_file_name):
                contract_file_desc = open(contract_file_name, 'r', encoding=encoding)
                desc_to_close.append(contract_file_desc)
                contract_reader = csv.DictReader(contract_file_desc, quotechar='"', delimiter=',', doublequote=False, escapechar='\\')

            staff_file_name = os.path.join(tmpdir, staff_file)
            if os.path.isfile(staff_file_name):
                staff_file_desc = open(staff_file_name, 'r', encoding=encoding)
                desc_to_close.append(staff_file_desc)
                staff_reader = csv.DictReader(staff_file_desc, quotechar='"', delimiter=',', doublequote=False, escapechar='\\')

            ini_file_name = os.path.join(tmpdir, ini_file)
            if os.path.isfile(ini_file_name):
                ini_file_desc = open(ini_file_name, 'r', encoding='utf_8_sig')
                desc_to_close.append(ini_file_desc)
                config_parser = configparser.SafeConfigParser()
                config_parser.readfp(ini_file_desc)

        if not contract_reader:
            raise osv.except_osv(_('Error'), _('%s not found in given zip file!') % (contract_file,))
        if not staff_reader:
            raise osv.except_osv(_('Error'), _('%s not found in given zip file!') % (staff_file,))
        if not config_parser:
            raise osv.except_osv(_('Error'), _('%s not found in given zip file!') % (ini_file,))
        return job_reader, contract_reader, staff_reader, config_parser, desc_to_close, tmpdir

    def button_validate(self, cr, uid, ids, context=None):
        """
        Open ZIP file and search staff.csv
        """
        if not context:
            context = {}
        # Prepare some values
        res = False
        message = _("Employee import FAILED.")
        created = 0
        updated = 0
        processed = 0
        filename = ""
        errors = {}
        for wiz in self.browse(cr, uid, ids):
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            fileobj = NamedTemporaryFile('w+b', delete=False)
            fileobj.write(b64decode(wiz.file))
            # now we determine the file format
            filename = fileobj.name
            fileobj.close()
            job_reader, contract_reader, staff_reader, config_parser, desc_to_close, tmpdir = self.read_files(cr, uid, filename)
            filename = wiz.filename or ""
            # Check data from the ini file
            mois_ko = not config_parser.has_option('DEFAUT', 'MOIS')
            liste_terr_ko = not config_parser.has_option('DEFAUT', 'LISTETERRAIN') or \
                config_parser.get('DEFAUT', 'LISTETERRAIN').count(';') > 1  # it should contain only 1 project code
            if mois_ko or liste_terr_ko:
                # block all the import if the file imported is not a valid PER_MOIS file
                raise osv.except_osv(_('Error'), _("You can't import this file. Please check that it contains data "
                                                   "for only one month and one field."))
            # read the contract file
            contract_ids = False
            if contract_reader:
                contract_ids = self.update_contract(cr, uid, ids, contract_reader, context=context)
            # UF-2472: Read all lines to check employee's code before importing
            staff_data = []
            staff_seen = []

            staff_codes_seen = {}
            staff_codes_duplicated = {}

            codeterrain_id_staff_seen = {}
            codeterrain_id_staff_duplicated = {}

            uuid_seen = {}
            uuid_duplicated = {}

            for line in staff_reader:
                staff_seen.append(line)
                data = self.read_employee_infos(cr, uid, line)
                processed += 1
                if data: # to avoid False value in staff_data list
                    staff_data.append(data)
                    code = data[0]

                    # code_staff (uf identification_id) unicity
                    if code in staff_codes_seen:
                        staff_codes_duplicated[code] =True
                    staff_codes_seen.setdefault(code, []).append('%s, %s (%s)' % (ustr(data[1]), ustr(data[2]),_('Import File')))


                    if line.get('codeterrain') and line.get('id_staff'): # if not, error will be raised later
                        codeterrain_id_staff_key = (line['codeterrain'], line['id_staff'])
                        if codeterrain_id_staff_key in codeterrain_id_staff_seen:
                            codeterrain_id_staff_duplicated[codeterrain_id_staff_key] = True
                        codeterrain_id_staff_seen.setdefault(codeterrain_id_staff_key, []).append('%s, %s (%s)' % (ustr(data[1]), ustr(data[2]),_('Import File')))

                    if line.get('uuid_key'): # if not, error raised later
                        if line['uuid_key'] in uuid_seen:
                            uuid_duplicated[line['uuid_key']] = True
                        uuid_seen.setdefault(line['uuid_key'], []).append('%s, %s (%s)' % (ustr(data[1]), ustr(data[2]), _('Import File')))

            res = True
            if not staff_codes_duplicated and not codeterrain_id_staff_duplicated and not uuid_duplicated:
                created = 0
                processed = 0
                updated = 0
                # UF-2504 read staff file again for next enumeration
                # (because already read/looped above for staff codes)
                for i, employee_data in enumerate(staff_seen):
                    update, nb_created, nb_updated = self.update_employee_infos(
                        cr, uid, employee_data, wiz.id, i,
                        errors=errors, context=context)
                    if not update:
                        res = False
                    created += nb_created
                    updated += nb_updated
                    processed += 1
            else:
                res = False
                # create a different error line for each employee code being duplicated
                for emp_code in staff_codes_duplicated:
                    message = _('Several employees have the same Identification No "%s": %s') % (emp_code, ' ; '.join(staff_codes_seen[emp_code]))
                    self.store_error(errors, wiz.id, message)
                for codeterrain_dup, id_staff_dup in codeterrain_id_staff_duplicated:
                    message = _('Several employees have the same combination codeterrain %s, id_staff %s : %s') % (codeterrain_dup, id_staff_dup , ' ; '.join(codeterrain_id_staff_seen[(codeterrain_dup, id_staff_dup)]))
                    self.store_error(errors, wiz.id, message)
                for uuid_dup in uuid_duplicated:
                    message = _('Several employees have the same uuid_key %s : %s') % (uuid_dup , ' ; '.join(uuid_seen[uuid_dup]))
                    self.store_error(errors, wiz.id, message)

            # Close Temporary File
            # Delete previous created lines for employee's contracts
            if contract_ids:
                self.pool.get('hr.contract.msf').unlink(cr, uid, contract_ids)
            for to_close in desc_to_close:
                to_close.close()
            if tmpdir:
                shutil.rmtree(tmpdir)
        if res:
            rejected = processed - created - updated
            message = _("Employee import successful.")
        else:
            # reject the import of all employees
            cr.rollback()
            rejected = processed
            created = updated = 0
            context.update({'employee_import_wizard_ids': ids})

        # handle the errors at the end of the process to ensure the deletion & creation aren't affected by the rollback
        self.generate_errors(cr, uid, errors, context=context)

        context.update({'message': message})

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False

        # This is to redirect to Employee Tree View
        context.update({'from': 'employee_import'})

        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'filename': filename, 'created': created,
                                                                                  'updated': updated, 'total': processed,
                                                                                  'rejected': rejected, 'state': 'employee'}, context)
        return {
            'name': 'Employee Import Confirmation',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.import.confirmation',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

hr_payroll_employee_import()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
