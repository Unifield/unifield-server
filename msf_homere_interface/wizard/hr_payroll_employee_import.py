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

class hr_payroll_employee_import(osv.osv_memory):
    _name = 'hr.payroll.employee.import'
    _description = 'Employee Import'

    _columns = {
        'file': fields.binary(string="File", filters='*.zip', required=True),
    }

    def update_employee_infos(self, cr, uid, employee_data=''):
        """
        Get employee infos and 
        """
        # Some verifications
        if not employee_data:
            return False
        # Extract information
        adresse, adressecontact, anciennete, anglais, annee_diplome, annee_diplome2, asuivre, autrecausedeces, autreidentite, autrelangue, bqbic, \
            bqcommentaire, bqiban, bqmodereglement, bqnom, bqnumerocompte, bqsortnumber, canddetachement, carteemploye, causedeces, civilite, \
            code_staff, codeterrain, commentaire, date_maj, datedebanciennete, datedeces, dateemission, dateentree, dateexpiration, datenaissance, \
            decede, delegue, diplome, diplome2, email, enfants, espagnol, fax, fichierstaff, francais, id_staff, id_unique, lieuemission, \
            lieunaissance, nation, nom, num_soc, numidentite, OPE1EMPLOYER, OPE1OCCUPATION, OPE1YEAR, OPE2EMPLOYER, OPE2OCCUPATION, OPE2YEAR, \
            OPE3EMPLOYER, OPE3OCCUPATION, OPE3YEAR, pays, PIN1, PIN2, PIN3, PIN4, PIN5, poolurgence, portable, prenom, qui, relocatedstaff, sexe, \
            statutfamilial, tel_bureau, tel_prive, typeidentite = zip(employee_data)
        print civilite, code_staff, codeterrain, commentaire, datedeces, dateexpiration, datenaissance, decede, email, id_staff, id_unique, lieuemission, nation, nom, num_soc, pays, portable, prenom, sexe, statutfamilial, tel_bureau, tel_prive
        # CODE UNIQUE = codeterrain, id_staff, id_unique
        return True

    def button_validate(self, cr, uid, ids, context={}):
        """
        Open ZIP file and search staff.csv
        """
        if not context:
            context = {}
        # Prepare some values
        staff_file = 'staff.csv'
        for wiz in self.browse(cr, uid, ids):
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            fileobj.seek(0)
            zipobj = zf(fileobj.name)
            if zipobj.namelist() and staff_file in zipobj.namelist():
                namelist =  zipobj.namelist()
                # Doublequote and escapechar avoid some problems
                reader = csv.reader(zipobj.open(staff_file), quotechar='"', delimiter=',', doublequote=False, escapechar='\\')
            reader.next()
            for employee_data in reader:
                self.update_employee_infos(cr, uid, employee_data)
            fileobj.close()
        return { 'type': 'ir.actions.act_window_close', 'context': context}

hr_payroll_employee_import()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
