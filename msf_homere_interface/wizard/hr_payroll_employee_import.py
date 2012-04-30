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
    }

    _defaults = {
        'updated': lambda *a: 0,
        'created': lambda *a: 0,
        'total': lambda *a: 0,
        'state': lambda *a: 'none',
    }

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
            if result:
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, result[2] or 'msf_homere_interface', result[0])
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

class hr_payroll_employee_import(osv.osv_memory):
    _name = 'hr.payroll.employee.import'
    _description = 'Employee Import'

    _columns = {
        'file': fields.binary(string="File", filters='*.zip', required=True),
    }

    def update_employee_check(self, cr, uid, staffcode=False, missioncode=False, staff_id=False, uniq_id=False):
        """
        Check that:
        - no more than 1 employee exist for "missioncode + staff_id + uniq_id"
        - only one employee have this staffcode
        """
        # Some verifications
        if not staffcode or not missioncode or not staff_id or not uniq_id:
            return False
        # Check employees
        search_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_codeterrain', '=', missioncode), ('homere_id_staff', '=', staff_id), ('homere_id_unique', '=', uniq_id)])
        if search_ids and len(search_ids) > 1:
            raise osv.except_osv(_('Error'), _('Database have more than one employee with this unique code!'))
        # Check staffcode
        staffcode_ids = self.pool.get('hr.employee').search(cr, uid, [('identification_id', '=', staffcode)])
        if staffcode_ids:
            for employee in self.pool.get('hr.employee').browse(cr, uid, staffcode_ids):
                if employee.homere_codeterrain != missioncode or str(employee.homere_id_staff) != staff_id or employee.homere_id_unique != uniq_id:
                    raise osv.except_osv(_('Error'), _('More than 1 employee have the same unique identification number: %s' % employee.name))
        return True

    def update_employee_infos(self, cr, uid, employee_data=''):
        """
        Get employee infos and set them to DB.
        """
        # Some verifications
        created = 0
        updated = 0
        if not employee_data:
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
            raise osv.except_osv(_('Error'), _('The given file is probably corrupted!'))
        # Process data
        if codeterrain and codeterrain[0] and id_staff and id_staff[0] and id_unique and id_unique[0] and code_staff and code_staff[0]:
            # Do some check
            self.update_employee_check(cr, uid, ustr(code_staff[0]), ustr(codeterrain[0]), id_staff[0], ustr(id_unique[0]))
            # Search employee regarding a unique trio: codeterrain, id_staff, id_unique
            e_ids = self.pool.get('hr.employee').search(cr, uid, [('homere_codeterrain', '=', codeterrain[0]), ('homere_id_staff', '=', id_staff[0]), ('homere_id_unique', '=', id_unique[0])])
            # Prepare vals
            res = False
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
                'name': (nom and prenom and nom[0] and prenom[0] and ustr(nom[0]) + ', ' + ustr(prenom[0])) or (nom and ustr(nom[0])) or (prenom and ustr(prenom[0])) or False,
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
#            # If employee have a expired date, so desactivate it
#            if dateexpiration and dateexpiration[0] and dateexpiration[0] <= current_date:
#                vals.update({'active': False})
            # Add an analytic distribution
            try:
                cc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project_dummy')[1] or False
            except ValueError:
                cc_id = 0
            if cc_id:
                vals.update({'cost_center_id': cc_id,})
            if not e_ids:
                res = self.pool.get('hr.employee').create(cr, uid, vals, {'from': 'import'})
                if res:
                    created += 1
            else:
                res = self.pool.get('hr.employee').write(cr, uid, e_ids, vals, {'from': 'import'})
                if res:
                    updated += 1
        else:
            return False, created, updated
        return True, created, updated

    def button_validate(self, cr, uid, ids, context=None):
        """
        Open ZIP file and search staff.csv
        """
        if not context:
            context = {}
        # Prepare some values
        staff_file = 'staff.csv'
        res = False
        message = _("Employee import FAILED.")
        created = 0
        updated = 0
        processed = 0
        for wiz in self.browse(cr, uid, ids):
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            fileobj.seek(0)
            try:
                zipobj = zf(fileobj.name)
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Given file is not a zip file!'))
            if zipobj.namelist() and staff_file in zipobj.namelist():
                # Doublequote and escapechar avoid some problems
                reader = csv.reader(zipobj.open(staff_file), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
            else:
                raise osv.except_osv(_('Error'), _('%s not found in given zip file!') % (staff_file,))
            try:
                reader.next()
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Problem to read given file.'))
            # Unactivate all local employees
            e_ids = self.pool.get('hr.employee').search(cr, uid, [('employee_type', '=', 'local'), ('active', '=', True)])
            self.pool.get('hr.employee').write(cr, uid, e_ids, {'active': False,}, {'from': 'import'})
            res = True
            for employee_data in reader:
                processed += 1
                update, nb_created, nb_updated = self.update_employee_infos(cr, uid, employee_data)
                if not update:
                    res = False
                created += nb_created
                updated += nb_updated
            # Close Temporary File
            fileobj.close()
        if res:
            message = _("Employee import successful.")
        context.update({'message': message})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        # This is to redirect to Employee Tree View
        context.update({'from': 'employee_import'})
        
        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'updated': updated, 'total': processed, 'state': 'employee'})
        
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
