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
        if not data:
            return False
        # Prepare some values
        vals = {}
        accounting_code,description,second_description,third,expense,receipt,project,financing_line,financing_contract,date,currency,project,analytic_line = zip(data)
        print date[0], accounting_code[0], description[0], second_description[0], expense[0], receipt[0], currency[0]
        return True

    def button_validate(self, cr, uid, ids, context={}):
        """
        Open ZIP file, take the CSV file into and parse it to import payroll entries
        """
        # Do verifications
        if not context:
            context = {}
        
        # FIXME: VERIFY THAT NO PAYROLL DRAFT LINE EXISTS.
        
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
                    for line in reader:
                        update = self.update_payroll_entries(cr, uid, line)
                        if not update:
                            res = False
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
