#!/usr/bin/env python
# -*- coding: utf-8 -*-

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


    def search_employee(self, cr, uid, codeterrain, id_staff, uniq_id, uuid_key, identification_id):
        e_ids = []
        emp_obj = self.pool.get('hr.employee')

        domain = [('homere_codeterrain', '=', codeterrain,), ('homere_id_staff', '=', id_staff), ('homere_id_unique', '=', uniq_id)]
        if uuid_key:
            e_ids = emp_obj.search(cr, uid, domain + [('homere_uuid_key', '=', uuid_key), ('identification_id', '=', identification_id)])
        if not e_ids and uuid_key:
            e_ids = emp_obj.search(cr, uid, domain + [('homere_uuid_key', '=', uuid_key)])
        if not e_ids:
            e_ids = emp_obj.search(cr, uid, domain)
        return e_ids


    def update_employee_check(self, cr, uid,
                              staffcode=False, missioncode=False, staff_id=False, uniq_id=False,
                              wizard_id=None, employee_name=False, registered_keys=None, homere_fields=None, uuid_key=None, errors=None):
        """
        Check that:
        - no more than 1 employee exist for "missioncode + staff_id + uniq_id"
        - only one employee have this staffcode
        :return (ok, what_changed)
        :rtype tuple
        """

        if homere_fields is None:
            homere_fields = {}

        def changed(mission1, mission2, staff1, staff2, unique1, unique2):
            res = None
            if mission1 != mission2:
                res = 'mission'
            elif staff1 != staff2:
                res = 'staff'
            elif unique1 != unique2:
                res = 'unique'
            return res

        res = False
        what_changed = None

        # Checks
        if not staffcode or not missioncode or not staff_id or not uniq_id:
            name = employee_name or _('Nonamed Employee')
            message = _('Unknown error for employee %s') % name
            if not staffcode:
                message = _('No "code_staff" found for employee %s!') % (name,)
            elif not missioncode:
                message = _('No "code_terrain" found for employee %s!') % (name,)
            elif not staff_id:
                message = _('No "id_staff" found for employee %s!') % (name,)
            elif not uniq_id:
                message = _('No "id_unique" found for employee %s!') % (name,)
            self.store_error(errors, wizard_id, message)
            return (res, what_changed)

        # Check employees

        # US-1404: check duplicates on the import files itself
        # => as not already in db
        check_key = missioncode + staff_id + uniq_id
        if check_key in registered_keys:
            # if check_key is in homere_fields BUT its value is empty, the related msg has already been created => skip the msg creation part
            if check_key not in homere_fields or homere_fields.get(check_key):
                # if possible list all the duplicated employees
                if homere_fields.get(check_key):
                    list_duplicates = ['%s (%s)' % (empl, _('Import File')) for empl in homere_fields[check_key]]
                    # empty the list so that the msg with all employees is displayed only once (and not once per duplicated employee)
                    homere_fields[check_key] = []
                # if not possible only the current employee name will be displayed
                else:
                    list_duplicates = ['%s (%s)' % (employee_name, _('Import File'))]
                self.store_error(errors, wizard_id,
                                 _('Several employees have the same combination key codeterrain/id_staff/(id_unique) "%s / %s / (%s)": %s') %
                                  (missioncode, staff_id, uniq_id, ' ; '.join(list_duplicates))
                                 )
            return (res, what_changed)


        # check duplicates already in db
        search_ids = self.search_employee(cr, uid, missioncode, staff_id, uniq_id, uuid_key, staffcode)

        if search_ids and len(search_ids) > 1:
            emp_duplicates = self.pool.get('hr.employee').browse(cr, uid, search_ids, fields_to_fetch=['name'])
            # create a list with the employee from the file...
            name_duplicates = ['%s (%s)' % (employee_name, _('Import File'))]
            # ... and the duplicates already in UniField
            name_duplicates.extend(['%s (UniField)' % emp.name for emp in emp_duplicates if emp.name])
            self.store_error(errors, wizard_id,
                             _('Several employees have the same combination key codeterrain/id_staff/(id_unique) "%s / %s / (%s)": %s') %
                              (missioncode, staff_id, uniq_id, ' ; '.join(name_duplicates))
                             )
            return (res, what_changed)

        # Check staffcode
        staffcode_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id', '=', staffcode)])
        if staffcode_ids:
            employee_error_list = []
            # UTP-1098: Do not make an error if the employee have the same code staff and the same name
            for employee in self.pool.get('hr.employee').browse(cr, uid, staffcode_ids):
                what_changed = changed(employee.homere_codeterrain, missioncode, str(employee.homere_id_staff), staff_id, employee.homere_id_unique, uniq_id)
                if employee.name == employee_name or (uuid_key and employee.homere_uuid_key == uuid_key):
                    continue
                if what_changed != None:
                    # duplicated employees in UniField
                    employee_error_list.append("%s (UniField)" % (employee.name,))
            if employee_error_list:
                # add the duplicated employee from Import File
                message = _('Several employees have the same Identification No "%s": %s') % \
                    (staffcode, ' ; '.join(["%s (%s)" % (employee_name, _('Import File'))] + employee_error_list))
                self.store_error(errors, wizard_id, message)
                return (res, what_changed)

        res = True
        return (res, what_changed)

    def _check_identification_id_duplication(self, cr, uid, vals, employee_check, what_changed, current_id=None, context=None):
        """
        Method used to check if the Identification No to be used for the employee about to be created/edited doesn't
        already exist for another employee in UniField.
        Returns False if there is a duplication AND we are in the use case where the related and detailed error has
        already been stored in the list of errors to display (but the process wasn't blocked earlier since "what_changed" had a value).
        Otherwise returns True => the generic create/write checks will then apply (i.e. a generic error msg will be displayed)
        """
        if context is None:
            context = {}
        employee_obj = self.pool.get('hr.employee')
        if not employee_check and what_changed and vals.get('identification_id'):
            employee_dom = [('identification_id', '=', vals['identification_id'])]
            if current_id is not None:
                employee_dom.append(('id', '!=', current_id))
            if employee_obj.search_exist(cr, uid, employee_dom, context=context):
                return False
        return True

    def get_job_libelles(self, cr, uid, job_reader, context=None):
        '''
        US-12690: Only for retro-compatibility with Homere v4 file format
        '''
        lib_dict = {}
        if not job_reader:
            return {}
        for job_line in job_reader:
            if job_line.get('code', False) and job_line.get('libelle', False):
                lib_dict.update({job_line.get('code'): job_line.get('libelle')})
        return lib_dict

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
                              line_number=None, registered_keys=None, homere_fields=None, errors=None, context=None):
        """
        Get employee infos and set them to DB.
        """
        # Some verifications
        created = 0
        updated = 0
        if homere_fields is None:
            homere_fields = {}

        if context is None:
            context = {}
        if line_number is not None:
            line_number = line_number + 2  # cf. the count starts at "1" and the header line is ignored
        if not employee_data or not wizard_id:
            message = _('No data found for this line: %s.') % line_number
            self.store_error(errors, wizard_id, message)
            return False, created, updated
        # Prepare some values
        vals = {}
        # Extract information
        try:
            code_staff = employee_data.get('code_staff', False)
            codeterrain = employee_data.get('codeterrain', False)
            decede = employee_data.get('decede', False)
            id_staff = employee_data.get('id_staff', False)
            id_unique = employee_data.get('id_unique', False)
            uuid_key = employee_data.get('uuid_key', False)
            nom = employee_data.get('nom', False)
            prenom = employee_data.get('prenom', False)
            if not nom and not prenom:
                message = _('There is an employee with empty name staff.csv file')
                if code_staff:
                    message = message + _(': employee with code_staff %s') % code_staff
                self.store_error(errors, wizard_id, message)
                return False, created, updated
        except ValueError as e:
            raise osv.except_osv(_('Error'), _('The given file is probably corrupted!\n%s') % (e))
        # Process data
        uuid_field = self.pool.get('hr.employee')._columns.get('homere_uuid_key')
        if uuid_key and uuid_field:
            uuid_key = ustr(uuid_key)
            uuid_field_size = uuid_field.size
            if len(uuid_key) > uuid_field_size:
                message = _('Line %s. The UUID_key has more than %d characters.') % (line_number, uuid_field_size)
                self.store_error(errors, wizard_id, message)
                return False, created, updated
        # Due to UF-1742, if no id_unique, we fill it with "empty"
        uniq_id = id_unique or False
        if not id_unique:
            uniq_id = 'empty'
        if codeterrain and id_staff and code_staff:
            # Employee name
            nom = nom and nom.strip() or ''
            prenom = prenom and prenom.strip() or ''
            employee_name = (nom and prenom and ustr(nom) + ', ' + ustr(prenom)) or (nom and ustr(nom)) or (prenom and ustr(prenom)) or False

            # Do some check
            employee_check, what_changed = self.update_employee_check(cr, uid,
                                                                      staffcode=ustr(code_staff), missioncode=ustr(codeterrain),
                                                                      staff_id=id_staff, uniq_id=ustr(uniq_id),
                                                                      wizard_id=wizard_id, employee_name=employee_name,
                                                                      registered_keys=registered_keys, homere_fields=homere_fields, uuid_key=uuid_key,
                                                                      errors=errors)
            if not employee_check and not what_changed:
                return False, created, updated

            # UTP-1098: If what_changed is not None, we should search the employee only on code_staff
            if what_changed:
                e_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id', '=', ustr(code_staff)), '|', ('name', '=', employee_name), ('homere_uuid_key', '=', uuid_key)])
            else:
                e_ids = self.search_employee(cr, uid, codeterrain, id_staff, uniq_id, uuid_key, code_staff)

            # Prepare vals
            res = False
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
            }

            # In case of death, desactivate employee
            if decede and decede == 'Y':
                vals.update({'active': False})
            # Desactivate employee if:
            # - no contract line found
            # - end of current contract exists and is inferior to current date
            # - no contract line found with current = True

            # sort contract: get current one, then by start date
            contract_ids = self.pool.get('hr.contract.msf').search(cr, uid, [('homere_codeterrain', '=', codeterrain), ('homere_id_staff', '=', id_staff)], order='current desc,date_start desc,id')
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
            if not e_ids:
                if not self._check_identification_id_duplication(cr, uid, vals, employee_check, what_changed, context=context):
                    return False, created, updated
                res = self.pool.get('hr.employee').create(cr, uid, vals, {'from': 'import'})
                if res:
                    created += 1
            else:
                if not self._check_identification_id_duplication(cr, uid, vals, employee_check, what_changed, current_id=e_ids[0], context=context):
                    return False, created, updated
                res = self.pool.get('hr.employee').write(cr, uid, e_ids, vals, {'from': 'import'})
                if res:
                    updated += 1
            registered_keys[codeterrain + id_staff + uniq_id] = True
        else:
            message = _('Line %s. One of this column is missing: code_terrain, id_unique or id_staff. This often happens when the line is empty.') % (line_number)
            self.store_error(errors, wizard_id, message)
            return False, created, updated

        return True, created, updated

    def update_contract(self, cr, uid, ids, contract_readers, job_reader, context=None):
        """
        Read lines from reader and update database
        """
        res = []
        libelle_dict = {}
        if job_reader:
            libelle_dict = self.get_job_libelles(cr, uid, job_reader, context=context)
        for contract_reader in contract_readers:
            for line in contract_reader:
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
                else:
                    job_code = line.get('fonction', False)
                    if job_code:
                        vals.update({'job_name': libelle_dict.get(job_code)})
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
        staff_I_file = 'staff_I.csv'
        contract_file = 'contrat.csv'
        contract_I_file = 'contrat_I.csv'
        job_file = 'fonction.csv'
        ini_file = 'envoi.ini'
        job_reader = False
        contract_reader = []
        staff_reader = []
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

            zip_namelist = zipobj.namelist()
            if zip_namelist:
                if job_file in zip_namelist:
                    job_reader = csv.DictReader(io.TextIOWrapper(zipobj.open(job_file), encoding=encoding), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
                    # Do not raise error for job file because it's just a useful piece of data, but not more.
                # read the contract file
                for contract_f in [contract_file, contract_I_file]:
                    if contract_f in zip_namelist:
                        contract_reader.append(csv.DictReader(io.TextIOWrapper(zipobj.open(contract_f), encoding=encoding), quotechar='"', delimiter=',', doublequote=False, escapechar='\\'))
                for staff_f in [staff_file, staff_I_file]:
                    if staff_f in zip_namelist:
                        staff_reader.append(csv.DictReader(io.TextIOWrapper(zipobj.open(staff_f), encoding=encoding), quotechar='"', delimiter=',', doublequote=False, escapechar='\\'))
                # read the ini file
                if ini_file in zip_namelist:
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

            for contract_f in [contract_file, contract_I_file]:
                contract_file_name = os.path.join(tmpdir, contract_f)
                if os.path.isfile(contract_file_name):
                    contract_file_desc = open(contract_file_name, 'r', encoding=encoding)
                    desc_to_close.append(contract_file_desc)
                    contract_reader.append(csv.DictReader(contract_file_desc, quotechar='"', delimiter=',', doublequote=False, escapechar='\\'))

            for staff_f in [staff_file, staff_I_file]:
                staff_file_name = os.path.join(tmpdir, staff_f)
                if os.path.isfile(staff_file_name):
                    staff_file_desc = open(staff_file_name, 'r', encoding=encoding)
                    desc_to_close.append(staff_file_desc)
                    staff_reader.append(csv.DictReader(staff_file_desc, quotechar='"', delimiter=',', doublequote=False, escapechar='\\'))

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
        registered_keys = {}
        errors = {}
        for wiz in self.browse(cr, uid, ids):
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            fileobj = NamedTemporaryFile('w+b', delete=False)
            fileobj.write(b64decode(wiz.file))
            # now we determine the file format
            filename = fileobj.name
            fileobj.close()
            job_reader, contract_readers, staff_readers, config_parser, desc_to_close, tmpdir = self.read_files(cr, uid, filename)
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
            if contract_readers:
                contract_ids = self.update_contract(cr, uid, ids, contract_readers, job_reader, context=context)
            # UF-2472: Read all lines to check employee's code before importing
            staff_data = []
            staff_codes = []
            duplicates = []
            staff_seen = []
            code_staff_seen = {}
            homere_fields = {}
            staff_file_number = 0
            for staff_reader in staff_readers:
                for line in staff_reader:
                    # in case of saff_I: ignore duplicated code_staff (found in previous Homere version)
                    if not staff_file_number and line.get('code_staff'):
                        code_staff_seen[line['code_staff']] = True
                    if staff_file_number > 0 and line.get('code_staff') in code_staff_seen:
                        # 2nd file read, ignore code_staff already seen
                        continue

                    staff_seen.append(line)
                    data = self.read_employee_infos(cr, uid, line)
                    processed += 1
                    if data: # to avoid False value in staff_data list
                        staff_data.append(data)
                        code = data[0]
                        if code in staff_codes:
                            duplicates.append(code)
                        staff_codes.append(code)
                    # store the Homere fields combination for all employees
                    if line.get('nom'):
                        # "no id_unique" is replaced by the string "empty"
                        homere_fields_key = "%s%s%s" % (line.get('codeterrain', ''), line.get('id_staff', ''), line.get('id_unique') or 'empty')
                        if homere_fields_key not in homere_fields:
                            homere_fields[homere_fields_key] = []
                        homere_fields[homere_fields_key].append(line['nom'])
                staff_file_number += 1
            # Delete duplicates of… duplicates!
            duplicates = list(set(duplicates))
            details = {}
            for employee_infos in staff_data:
                employee_code = employee_infos[0]
                if employee_code in duplicates:
                    # add (Import File) after the employee info so that it is clearer for the user that the duplicates are inside the file itself
                    if employee_code not in details:
                        details[employee_code] = []
                    details[employee_code].append(','.join([ustr(employee_infos[1]), "%s (%s)" % (ustr(employee_infos[2]), _('Import File'))]))
            res = True
            if not details:
                created = 0
                processed = 0
                updated = 0
                # UF-2504 read staff file again for next enumeration
                # (because already read/looped above for staff codes)
                for i, employee_data in enumerate(staff_seen):
                    update, nb_created, nb_updated = self.update_employee_infos(
                        cr, uid, employee_data, wiz.id, i,
                        registered_keys=registered_keys, homere_fields=homere_fields, errors=errors, context=context)
                    if not update:
                        res = False
                    created += nb_created
                    updated += nb_updated
                    processed += 1
            else:
                res = False
                # create a different error line for each employee code being duplicated
                for emp_code in details:
                    message = _('Several employees have the same Identification No "%s": %s') % (emp_code, ' ; '.join(details[emp_code]))
                    self.store_error(errors, wiz.id, message)
            # Close Temporary File
            # Delete previous created lines for employee's contracts
            if contract_ids:
                self.pool.get('hr.contract.msf').unlink(cr, uid, contract_ids)
            for to_close in desc_to_close:
                to_close.close()
            if tmpdir:
                shutil.rmtree(tmpdir)
        del registered_keys
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
