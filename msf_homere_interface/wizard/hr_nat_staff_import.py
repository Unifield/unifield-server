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
from tools.translate import _

from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from base64 import decodestring

class hr_nat_staff_import_wizard(osv.osv_memory):
    _name = 'hr.nat.staff.import'
    _description = 'Nat. staff employee import'

    _columns = {
        'file': fields.binary("File", filters="*.xml", required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Import XLS file
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz in self.browse(cr, uid, ids):
            # Prepare some values
            created = 0
            updated = 0
            processed = 0
            # Check that a file is given
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('No file given'))
            # Check file extension
            if wiz.filename.split('.')[-1] != 'xml':
                raise osv.except_osv(_('Warning'), _('This wizard only accept XML files.'))
            # Read file
            fileobj = SpreadsheetXML(xmlstring=decodestring(wiz.file))
            reader = fileobj.getRows()
            reader.next()
            for line in reader:
                processed += 1
                name = line.cells and line.cells[0] and line.cells[0].data or False
                if not name:
                    continue
                code = line.cells and line.cells[1] and line.cells[1].data or False
                # Create Expat employee
                self.pool.get('hr.employee').create(cr, uid, {'name': line.cells[0].data, 'active': True, 'type': 'local', 'identification_id': code})
                created += 1
            
            context.update({'message': ' '})
            
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
            view_id = view_id and view_id[1] or False
            
            # This is to redirect to Employee Tree View
            context.update({'from': 'expat_employee_import'})
            
            res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'updated': updated, 'total': processed, 'state': 'employee'})
            
            return {
                'name': 'National staff employee import confirmation',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.payroll.import.confirmation',
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': [view_id],
                'res_id': res_id,
                'target': 'new',
                'context': context,
            }

hr_nat_staff_import_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
