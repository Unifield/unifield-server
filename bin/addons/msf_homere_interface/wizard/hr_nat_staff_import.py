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
from tools.misc import ustr
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from base64 import decodestring

class hr_nat_staff_import_wizard(osv.osv_memory):
    _name = 'hr.nat.staff.import'
    _description = 'Nat. staff employee import'

    _columns = {
        'file': fields.binary("File", filters="*.xml", required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    def update_or_create_employee(self, cr, uid, vals=None, context=None):
        """
        Update employee if exists. Otherwise create it.
        Also check values regarding National Staff employees:
         - name: mandatory field
         - identification_id: mandatory field for identification_id
         - job: search job if exists, else create it.
         - destination: search destination code or name
         - cost center: like destination
         - funding pool: like destination
         - free1: like destination
         - free2: like destination
        Return changed vals and another value: employee_id.
        If employee_id is False, it's an employee creation. Else, it's an employee update.
        """
        # Prepare some values
        employee_id = False
        # Some checks
        if not context:
            context = {}
        if not vals:
            return {}, employee_id
        # Check mandatory fields
        if not vals.get('name', False):
            raise osv.except_osv(_('Error'), _('Name is a mandatory field!'))
        if not vals.get('identification_id', False):
            raise osv.except_osv(_('Error'), _('Code is a mandatory field!'))
        # Search employee and check double identification_id
        employee_ids = self.pool.get('hr.employee').search(cr, uid, [('employee_type', '=', 'local'), ('identification_id', '=', vals.get('identification_id'))])
        if employee_ids and len(employee_ids) > 1:
            employees = ','.join([x.get('name', False) and "%s%s" % (x.get('name'), x.get('identification_id', '')) for x in self.pool.get('hr.employee').read(cr, uid, employee_ids, ['name', 'identification_id'])])
            raise osv.except_osv(_('Warning'), _('Employee code already used by: %s') % (employees or '',))
        elif employee_ids:
            e_data = self.pool.get('hr.employee').read(cr, uid, employee_ids, ['name', 'identification_id'])
            if e_data[0].get('name', False) == vals.get('name'):
                employee_id = employee_ids[0]
            else:
                raise osv.except_osv(_('Warning'), _('Employee code already used by: %s %s') % (e_data[0].get('name') or '', e_data[0].get('identification_id') or '',))
        # Update other fields
        vals.update({'employee_type': 'local', 'active': True,})
        return vals, employee_id

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
            errors = []
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
            start = 1
            column_list = ['name', 'identification_id'] #, 'job', 'dest', 'cc', 'fp', 'f1', 'f2']
            for num, line in enumerate(reader):
                processed += 1
                # Fetch values
                vals = {}
                if line.cells:
                    for i, el in enumerate(column_list):
                        if len(line.cells) > i:
                            vals[el] = ustr(line.cells[i])
                        else:
                            vals[el] = False
                # Check values
                employee_id = False
                try:
                    vals, employee_id = self.update_or_create_employee(cr, uid, vals, context)
                except osv.except_osv, e:
                    errors.append('Line %s, %s' % (start+num, e.value))
                    continue
                # Do creation/update
                context.update({'from': 'import'})
                if employee_id:
                    self.pool.get('hr.employee').write(cr, uid, [employee_id], vals, context)
                    updated += 1
                else:
                    self.pool.get('hr.employee').create(cr, uid, vals, context)
                    created += 1
            for error in errors:
                self.pool.get('hr.payroll.employee.import.errors').create(cr, uid, {'wizard_id': wiz.id, 'msg': error})
            if errors:
                context.update({'employee_import_wizard_ids': wiz.id})

            context.update({'message': ' '})

            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
            view_id = view_id and view_id[1] or False

            # This is to redirect to Employee Tree View
            context.update({'from': 'nat_staff_import'})

            res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'created': created, 'updated': updated, 'total': processed, 'state': 'employee', 'filename': wiz.filename or False,}, context=context)

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
