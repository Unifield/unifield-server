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

class hq_entries_import_wizard(osv.osv_memory):
    _name = 'hq.entries.import'
    _description = 'HQ Entries Import Wizard'

    _columns = {
        'file': fields.binary(string="File", filters="*.csv", required=True),
    }

    def update_hq_entries(self, cr, uid, line):
        """
        Import hq entry regarding all elements given in "line"
        """
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
        
        # Browse all given wizard
        for wiz in self.browse(cr, uid, ids):
            # Decode file string
            fileobj = NamedTemporaryFile('w+')
            fileobj.write(decodestring(wiz.file))
            # now we determine the file format
            fileobj.seek(0)
            # Read CSV file
            try:
                reader = csv.reader(fileobj, delimiter=',')
            except:
                fileobj.close()
                raise osv.except_osv(_('Error'), _('Problem to read given file.'))
            res = True
            res_amount = 0.0
            amount = 0.0
            for line in reader:
                processed += 1
                update = self.update_hq_entries(cr, uid, line)
                if update:
                    created += 1
            fileobj.close()
        
        if res:
            message = _("Payroll import successful")
        context.update({'message': message})
        
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        
        # This is to redirect to HQ Entries Tree View
        context.update({'from': 'hq_entries_import'})
        
        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'total': processed, 'state': 'hq'})
        
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
