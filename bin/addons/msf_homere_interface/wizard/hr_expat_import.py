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
from mx import DateTime


class hr_expat_employee_import_wizard(osv.osv_memory):
    _name = 'hr.expat.employee.import'
    _description = 'Expat employee import'

    _columns = {
        'file': fields.binary("File", filters="*.xml", required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    def button_validate(self, cr, uid, ids, context=None, auto_import=False):
        """
        Import XLS file
        """
        def get_xml_spreadheet_cell_value(cell_index):
            return line.cells and len(line.cells) > cell_index and \
                line.cells[cell_index] and line.cells[cell_index].data \
                or False

        def manage_error(line_index, msg, name='', code='', status='', contract_end_date=''):
            if auto_import:
                rejected_data = [name, code, status]
                if handle_contract_end_date:
                    rejected_data.append(contract_end_date or '')
                rejected_lines.append((line_index, rejected_data, msg))
            else:
                raise osv.except_osv(_('Error'), _(msg))

        processed_lines = []
        rejected_lines = []
        handle_contract_end_date = False
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
            to_update_vals = []
            to_create_vals = []
            # Check that a file is given
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('No file given'))
            # Check file extension
            if wiz.filename.split('.')[-1] != 'xml':
                raise osv.except_osv(_('Warning'), _('This wizard only accept XML files.'))
            # Read file
            fileobj = SpreadsheetXML(xmlstring=decodestring(wiz.file))
            reader = fileobj.getRows()
            line_index = 2  # header taken into account
            header_analyzed = False
            for line in reader:
                if not header_analyzed:
                    # the 4th column (Contract End Date) may not exist in the file and should then be ignored
                    contract_end_date_header = get_xml_spreadheet_cell_value(3) or ''
                    if contract_end_date_header.strip():
                        handle_contract_end_date = True
                    header_analyzed = True
                    continue
                # get cells
                contract_end_date = False
                contract_end_date_str = ''
                name = get_xml_spreadheet_cell_value(0)
                if not name:
                    manage_error(line_index, 'No name defined')
                    line_index += 1
                    continue
                if handle_contract_end_date:
                    contract_end_date = get_xml_spreadheet_cell_value(3) or False
                    if contract_end_date:
                        if not isinstance(contract_end_date, DateTime.DateTimeType):
                            msg = _("The Contract End Date format is invalid on line %d") % line_index
                            manage_error(line_index, msg, name, contract_end_date="%s" % contract_end_date)
                            line_index += 1
                            continue  # inserting an invalid date format in the DB would fail
                        else:
                            contract_end_date_str = contract_end_date and contract_end_date.strftime('%Y-%m-%d') or ''
                code = get_xml_spreadheet_cell_value(1) and get_xml_spreadheet_cell_value(1).strip()
                if not code:
                    msg = _('THE EMPLOYEE DOES NOT HAVE AN ID NUMBER AT LINE %d.') % line_index
                    manage_error(line_index, msg, name, contract_end_date=contract_end_date_str)
                active_str = get_xml_spreadheet_cell_value(2)
                if not active_str:
                    msg = "Active column is missing or empty at line %d" % line_index
                    manage_error(line_index, msg, name, code, contract_end_date=contract_end_date_str)
                active_str = active_str and active_str.lower() or ''
                if active_str not in ('active', 'inactive'):
                    msg = "Active column invalid value line %d" \
                        " (should be Active/Inactive)" % line_index
                    manage_error(line_index, msg, name, code, active_str, contract_end_date=contract_end_date_str)
                active = active_str == 'active' or False

                processed += 1
                if auto_import:
                    processed_data = [name, code, active_str]
                    if handle_contract_end_date:
                        processed_data.append(contract_end_date_str)
                    processed_lines.append((line_index, processed_data))

                ids = hr_emp_obj.search(cr, uid,
                                        [('identification_id', '=', code)])
                vals = {
                    'name': name,
                    'active': active,
                }
                if handle_contract_end_date:
                    vals.update({'contract_end_date': contract_end_date})
                if ids:
                    # Store name of Expat employee to update
                    to_update_vals.append(([ids[0]], vals))
                    updated += 1
                else:
                    # Store Expat employee to create
                    vals.update(
                        {
                            'type': 'ex',
                            'identification_id': code,
                        }
                    )
                    to_create_vals.append(vals)
                    created += 1
                line_index += 1
            if not rejected_lines:
                for vals in to_update_vals:
                    hr_emp_obj.write(cr, uid, vals[0], vals[1], context=context)
                for vals in to_create_vals:
                    hr_emp_obj.create(cr, uid, vals, context=context)
            else:  # US-7624: To avoid partial import, reject all lines if there is at least one invalid employee line
                created = 0
                updated = 0
                rejected_idx = [i[0] for i in rejected_lines]  # get line number of each rejected line
                temp = [(t[0], t[1], '') for t in processed_lines if
                        t[0] not in rejected_idx]  # add an empty error column to valid lines
                rejected_lines += temp
                rejected_lines.sort(key=lambda j: j[0])  # sort on line number

            context.update({'message': ' ', 'from': 'expat_import'})

            if auto_import:
                headers = [_('Name'), _('Code'), _('Status')]
                if handle_contract_end_date:
                    headers.append(_('Contract End Date'))
                return processed_lines, rejected_lines, headers

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
