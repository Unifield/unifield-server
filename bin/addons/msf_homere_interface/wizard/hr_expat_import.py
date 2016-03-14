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
        def get_xml_spreadheet_cell_value(cell_index):
            return line.cells and len(line.cells) > cell_index and \
                line.cells[cell_index] and line.cells[cell_index].data \
                or False

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
            line_index = 2  # header taken into account
            for line in reader:
                # get cells
                name = get_xml_spreadheet_cell_value(0)
                if not name:
                    continue
                code = get_xml_spreadheet_cell_value(1)
                if not code:
                    msg = "At least one employee in the import file does not" \
                        " have an ID number; make sure all employees in the" \
                        " file have an ID number and run the import again."
                    raise osv.except_osv(_('Error'), _(msg))
                active_str = get_xml_spreadheet_cell_value(2)
                if not active_str:
                    msg = "Active column is missing or empty at line %d"
                    raise osv.except_osv(_('Error'), _(msg) % (line_index, ))
                active_str = active_str.lower()
                if active_str not in ('active', 'inactive'):
                    msg = "Active column invalid value line %d" \
                        " (should be Active/Inactive)"
                    raise osv.except_osv(_('Error'), _(msg) % (line_index, ))
                active = active_str == 'active' or False

                processed += 1

                ids = hr_emp_obj.search(cr, uid,
                    [('identification_id', '=', code)])
                if ids:
                    # Update name of Expat employee
                    hr_emp_obj.write(cr, uid, [ids[0]], {
                        'name': name, 
                        'active': active,
                    })
                    updated += 1
                else:
                    # Create Expat employee
                    hr_emp_obj.create(cr, uid, {
                        'name': name,
                        'active': active,
                        'type': 'ex',
                        'identification_id': code,
                    })
                    created += 1
                line_index += 1

            context.update({'message': ' ', 'from': 'expat_import'})

            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
            view_id = view_id and view_id[1] or False

            # This is to redirect to Employee Tree View
            context.update({'from': 'expat_employee_import'})
            res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'updated': updated, 'total': processed, 'state': 'employee'}, context=context)
            return {
                'name': 'Expat Employee Import Confirmation',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.payroll.import.confirmation',
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': [view_id],
                'res_id': res_id,
                'target': 'new',
                'context': context,
            }

hr_expat_employee_import_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
