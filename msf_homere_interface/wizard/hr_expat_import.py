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

class hr_expat_employee_import_wizard(osv.osv_memory):
    _name = 'hr.expat.employee.import'
    _description = 'Expat employee import'

    _columns = {
        'file': fields.binary("File", filters="*.xml", required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Import XLS file
        """
        hr_emp_obj = self.pool.get('hr.employee')
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
                name = line.cells and line.cells[0] and line.cells[0].data or False
                if not name:
                    continue
                code = line.cells and line.cells[1] and line.cells[1].data or False
                if not code:
                    msg = "At least one employee in the import file does not" \
                        " have an ID number; make sure all employees in the" \
                        " file have an ID number and run the import again."
                    raise osv.except_osv(_('Error'), _(msg))
                processed += 1

                ids = hr_emp_obj.search(cr, uid,
                    [('identification_id', '=', code)])
                if ids:
                    # Update name of Expat employee
                    hr_emp_obj.write(cr, uid, [ids[0]], {'name': name})
                    updated += 1
                else:
                    # Create Expat employee
                    hr_emp_obj.create(cr, uid, {'name': line.cells[0].data, 'active': True, 'type': 'ex', 'identification_id': code})
                    created += 1
            
            context.update({'message': ' '})
            res_id = self.pool.get('hr.payroll.import.confirmation').create(cr,uid, {'created': created, 'updated': updated, 'total': processed, 'state': 'employee'}, context=context)
            
            # BKLG-7: immediatly go to regular employee tree view
            action = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid,
                'hr', 'open_view_employee_list_my', context=context)
            action['target'] = 'same'
            return action

hr_expat_employee_import_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
