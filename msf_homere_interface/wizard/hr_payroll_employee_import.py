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
from osv import osv
from osv import fields
from tempfile import NamedTemporaryFile
import csv
from base64 import decodestring
from time import strftime
from tools.misc import ustr
from tools.translate import _
from lxml import etree

class hr_payroll_import_confirmation(osv.osv_memory):
    _name = 'hr.payroll.import.confirmation'
    _description = 'Import Confirmation'

    _columns = {
        'updated': fields.integer(string="Updated", size=64, readonly=True),
        'created': fields.integer(string="Created", size=64, readonly=True),
        'total': fields.integer(string="Processed", size=64, readonly=True),
        'state': fields.selection([('none', 'None'), ('employee', 'From Employee'), ('payroll', 'From Payroll'), ('hq', 'From HQ Entries')], 
            string="State", required=True, readonly=True),
        'error_line_ids': fields.many2many("hr.payroll.employee.import.errors", "employee_import_error_relation", "wizard_id", "error_id", "Error list", 
            readonly=True),
        'errors': fields.text(string="Errors", readonly=True),
        'nberrors': fields.integer(string="Errors", readonly=True),
        'filename': fields.char(string="Filename", size=256, readonly=True),
    }

    _defaults = {
        'updated': lambda *a: 0,
        'created': lambda *a: 0,
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
            if isinstance(wiz_ids, (int, long)):
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
            view['arch'] = etree.tostring(tree)
        return view

    def button_validate(self, cr, uid, ids, context=None):
        """
        Return rigth view
        """
        if not context:
            return {'type': 'ir.actions.act_window_close'}
        if context.get('from', False):
            result = False
            domain = False
            if context.get('from') == 'employee_import':
                result = ('editable_view_employee_tree', 'hr.employee')
                context.update({'search_default_employee_type_local': 1, 'search_default_active': 1})
            if context.get('from') == 'payroll_import':
                result = ('view_hr_payroll_msf_tree', 'hr.payroll.msf')
                domain = "[('state', '=', 'draft'), ('account_id.user_type.code', '=', 'expense')]"
            if context.get('from') == 'hq_entries_import':
                result = ('hq_entries_tree', 'hq.entries', 'account_hq_entries')
                domain = ""
                context.update({'search_default_non_validated': 1})
            if context.get('from') == 'expat_employee_import':
                result = ('editable_view_employee_tree', 'hr.employee')
                context.update({'search_default_employee_type_expatriate': 1})
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

    def update_employee_check(self, cr, uid, staffcode=False, missioncode=False, staff_id=False, uniq_id=False, wizard_id=None, employee_name=False):
        """
        Check that:
        - no more than 1 employee exist for "missioncode + staff_id + uniq_id"
        - only one employee have this staffcode
        """
        # Some verifications
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
            self.pool.get('hr.payroll.employee.import.errors').create(cr, uid, {'wizard_id': wizard_id, 'msg': message})
            return False
        # Check employees
        search_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_codeterrain', '=', missioncode), ('homere_id_staff', '=', staff_id), ('homere_id_unique', '=', uniq_id)])
        if search_ids and len(search_ids) > 1:
            self.pool.get('hr.payroll.employee.import.errors').create(cr, uid, {'wizard_id': wizard_id, 'msg': _("Database have more than one employee with the unique code of this employee: %s") % (employee_name,)})
            return False
        # Check staffcode
        staffcode_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id', '=', staffcode)])
        if staffcode_ids:
            message = "Several employee have the same ID code: "
            employee_error_list = []
            for employee in self.pool.get('hr.employee').browse(cr, uid, staffcode_ids):
                if employee.homere_codeterrain != missioncode or str(employee.homere_id_staff) != staff_id or employee.homere_id_unique != uniq_id:
                    employee_error_list.append(employee.name)
            if employee_error_list:
                message += ' ; '.join([employee_name] + employee_error_list)
                self.pool.get('hr.payroll.employee.import.errors').create(cr, uid, {'wizard_id': wizard_id, 'msg': message})
                return False
        return True

    def update_employee_infos(self, cr, uid, employee_data='', wizard_id=None, line_number=None):
        """
        Get employee infos and set them to DB.
        """
        # Some verifications
        created = 0
        updated = 0
        if not employee_data or not wizard_id:
            message = _('No data found for this line: %s.') % line_number
            self.pool.get('hr.payroll.employee.import.errors').create(cr, uid, {'wizard_id': wizard_id, 'msg': message})
            return False, created, updated
        # Prepare some values
        vals = {}
        current_date = strftime('%Y-%m-%d')
        # Extract information
        try:
            adresse, adressecontact, anciennete, anglais, annee_diplome, annee_diplome2, asuivre, autrecausedeces, autreidentite, autrelangue, bqbic, \
                bqcommentaire, bqiban, bqmodereglement, bqnom, bqnumerocompte, bqsortnumber, canddetachement, carteemploye, causedeces, civilite, \
                code_staff, codeterrain, commentaire, date_maj, datedebanciennete, datedeces, dateemission, dateentree, dateexpiration, datenaissance, \
                decede, delegue, diplome, diplome2, email, enfants, espagnol, fax, fichierstaff, francais, id_staff, id_unique, lieuemission, \
                lieunaissance, nation, nom, num_soc, numidentite, OPE1EMPLOYER, OPE1OCCUPATION, OPE1YEAR, OPE2EMPLOYER, OPE2OCCUPATION, OPE2YEAR, \
                OPE3EMPLOYER, OPE3OCCUPATION, OPE3YEAR, pays, PIN1, PIN2, PIN3, PIN4, PIN5, poolurgence, portable, prenom, qui, relocatedstaff, sexe, \
                statutfamilial, tel_bureau, tel_prive, typeidentite = zip(employee_data)
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('The given file is probably corrupted!\n%s') % (e))
        # Process data
        if codeterrain and codeterrain[0] and id_staff and id_staff[0] and id_unique and id_unique[0] and code_staff and code_staff[0]:
            # Employee name
            employee_name = (nom and prenom and nom[0] and prenom[0] and ustr(nom[0]) + ', ' + ustr(prenom[0])) or (nom and ustr(nom[0])) or (prenom and ustr(prenom[0])) or False
            # Do some check
            employee_check = self.update_employee_check(cr, uid, ustr(code_staff[0]), ustr(codeterrain[0]), id_staff[0], ustr(id_unique[0]), wizard_id, employee_name)
            if not employee_check:
                return False, created, updated
            # Search employee regarding a unique trio: codeterrain, id_staff, id_unique
            e_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_codeterrain', '=', codeterrain[0]), ('homere_id_staff', '=', id_staff[0]), ('homere_id_unique', '=', id_unique[0])])
            # Prepare vals
            res = False
            name = (nom and prenom and nom[0] and prenom[0] and ustr(nom[0]) + ', ' + ustr(prenom[0])) or (nom and ustr(nom[0])) or (prenom and ustr(prenom[0])) or False
            vals = {
                'active': True,
                'employee_type': 'local',
                'homere_codeterrain': codeterrain[0],
                'homere_id_staff': id_staff[0],
                'homere_id_unique': id_unique[0],
                'photo': False,
                'identification_id': code_staff and code_staff[0] or False,
                'notes': commentaire and ustr(commentaire[0]) or '',
                'birthday': datenaissance and datenaissance[0] or False,
                'work_email': email and email[0] or False,
                # Do "NOM, Prenom"
                'name': employee_name,
                'name': name,
                'ssnid': num_soc and num_soc[0] or False,
                'mobile_phone': portable and portable[0] or False,
                'work_phone': tel_bureau and tel_bureau[0] or False,
                'private_phone': tel_prive and tel_prive[0] or False,
            }
            # Update Birthday if equal to 0000-00-00
            if datenaissance and datenaissance[0] and datenaissance[0] == '0000-00-00':
                vals.update({'birthday': False,})
            # Update Nationality
            if nation and nation[0]:
                n_ids = self.pool.get('res.country').search(cr, uid, [('code', '=', ustr(nation[0]))])
                res_nation = False
                # Only get nationality if one result
                if n_ids:
                    if len(n_ids) == 1:
                        res_nation = n_ids[0]
                    else:
                        raise osv.except_osv(_('Error'), _('An error occured on nationality. Please verify all nationalities.'))
                vals.update({'country_id': res_nation})
            # Update gender
            if sexe and sexe[0]:
                gender = 'unknown'
                if sexe[0] == 'M':
                    gender = 'male'
                elif sexe[0] == 'F':
                    gender = 'female'
                vals.update({'gender': gender})
            # Update Marital Status
            if statutfamilial and statutfamilial[0]:
                statusname = False
                status = False
                if statutfamilial[0] == 'MA':
                    statusname = 'Married'
                elif statutfamilial[0] == 'VE':
                    statusname = 'Widower'
                elif statutfamilial == 'CE':
                    statusname = 'Single'
                if statusname:
                    s_ids = self.pool.get('hr.employee.marital.status').search(cr, uid, [('name', '=', statusname)])
                    if s_ids and len(s_ids) == 1:
                        status = s_ids[0]
                vals.update({'marital': status})
            # In case of death, desactivate employee
            if decede and decede[0] and decede[0] == 'Y':
                vals.update({'active': False})
            # Desactivate employee if:
            # - no contract line found
            # - end of current contract exists and is inferior to current date
            # - no contract line found with current = True
            contract_ids = self.pool.get('hr.contract.msf').search(cr, uid, [('homere_codeterrain', '=', codeterrain[0]), ('homere_id_staff', '=', id_staff[0])])
            if not contract_ids:
                vals.update({'active': False})
            current_contract = False
            for contract in self.pool.get('hr.contract.msf').browse(cr, uid, contract_ids):
                # Check current contract
                if contract.current:
                    current_contract = True
                    if contract.date_end and contract.date_end < strftime('%Y-%m-%d'):
                        vals.update({'active': False})
                # Check job
                if contract.job_id:
                    vals.update({'job_id': contract.job_id.id})
            # Desactivate employee if no current contract
            if not current_contract:
                vals.update({'active': False})
            if not e_ids:
                res = self.pool.get('hr.employee').create(cr, uid, vals, {'from': 'import'})
                if res:
                    created += 1
            else:
                res = self.pool.get('hr.employee').write(cr, uid, e_ids, vals, {'from': 'import'})
                if res:
                    updated += 1
        else:
            message = _('Line %s. One of this column is missing: code_terrain, id_unique or id_staff. This often happens when the line is empty.') % (line_number)
            self.pool.get('hr.payroll.employee.import.errors').create(cr, uid, {'wizard_id': wizard_id, 'msg': message})
            return False, created, updated
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
                'homere_id_unique': line.get('id_unique') or False,
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
            if line.get('fonction'):
                job_ids = self.pool.get('hr.job').search(cr, uid, [('code', '=', line.get('fonction'))])
                if job_ids:
                    vals.update({'job_id': job_ids[0]})
            # Add entry to database
            new_line = self.pool.get('hr.contract.msf').create(cr, uid, vals)
            if new_line:
                res.append(new_line)
        return res

    def update_job(self, cr, uid, ids, reader, context=None):
        """
        Read lines from reader and update database
        """
        res = []
        if not reader:
            return res
        for line in reader:
            # Check that no line with same code exist
            if line.get('code', False):
                search_ids = self.pool.get('hr.job').search(cr, uid, [('code', '=', line.get('code'))])
                if search_ids:
                    continue
                vals = {
                    'homere_codeterrain': line.get('codeterrain') or False,
                    'homere_id_unique': line.get('id_unique') or False,
                    'code': line.get('code') or '',
                    'name': line.get('libelle') or '',
                }
                # Add entry to database
                new_line = self.pool.get('hr.job').create(cr, uid, vals)
                if new_line:
                    res.append(new_line)
        return res

    def button_validate(self, cr, uid, ids, context=None):
        """
        Open ZIP file and search staff.csv
        """
        if not context:
            context = {}
        # Prepare some values
        staff_file = 'staff.csv'
        contract_file = 'contrat.csv'
        job_file = 'fonction.csv'
        res = False
        message = _("Employee import FAILED.")
        created = 0
        updated = 0
        processed = 0
        filename = ""
        # Delete old errors
        error_ids = self.pool.get('hr.payroll.employee.import.errors').search(cr, uid, [])
        if error_ids:
            self.pool.get('hr.payroll.employee.import.errors').unlink(cr, uid, error_ids)
        for wiz in self.browse(cr, uid, ids):
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            fileobj = NamedTemporaryFile('w+b', delete=False)
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            filename = fileobj.name
            fileobj.close()
            try:
                zipobj = zf(filename)
                filename = wiz.filename or ""
            except:
                raise osv.except_osv(_('Error'), _('Given file is not a zip file!'))
            # read the staff's job file
            job_ids = False
            if zipobj.namelist() and job_file in zipobj.namelist():
                job_reader = csv.DictReader(zipobj.open(job_file), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
                job_ids = self.update_job(cr, uid, ids, job_reader, context=context)
            # Do not raise error for job file because it's just a useful piece of data, but not more.
            # read the contract file
            contract_ids = False
            if zipobj.namelist() and contract_file in zipobj.namelist():
                contract_reader = csv.DictReader(zipobj.open(contract_file), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
                contract_ids = self.update_contract(cr, uid, ids, contract_reader, context=context)
            else:
                raise osv.except_osv(_('Error'), _('%s not found in given zip file!') % (contract_file,))
            # read the staff file
            if zipobj.namelist() and staff_file in zipobj.namelist():
                # Doublequote and escapechar avoid some problems
                reader = csv.reader(zipobj.open(staff_file), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
            else:
                raise osv.except_osv(_('Error'), _('%s not found in given zip file!') % (staff_file,))
            try:
                reader.next()
            except:
                raise osv.except_osv(_('Error'), _('Problem to read given file.'))
            res = True
            for i, employee_data in enumerate(reader):
                update, nb_created, nb_updated = self.update_employee_infos(cr, uid, employee_data, wiz.id, i)
                if not update:
                    res = False
                created += nb_created
                updated += nb_updated
                processed += 1
            # Close Temporary File
            # Delete previous created lines for employee's contracts
            if contract_ids:
                self.pool.get('hr.contract.msf').unlink(cr, uid, contract_ids)
        if res:
            message = _("Employee import successful.")
        else:
            context.update({'employee_import_wizard_ids': ids})
        context.update({'message': message})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        # This is to redirect to Employee Tree View
        context.update({'from': 'employee_import'})
        
        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'filename': filename, 'created': created, 'updated': updated, 'total': processed, 'state': 'employee'}, context)
        
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
