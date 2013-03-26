#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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
from time import strftime
from tempfile import NamedTemporaryFile
from base64 import decodestring
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from csv import DictReader

class msf_doc_import_accounting(osv.osv_memory):
    _name = 'msf.doc.import.accounting'

    _columns = {
        'date': fields.date(string="Migration date", required=True),
        'file': fields.binary(string="File", filters='*.xml, *.xls', required=True),
        'filename': fields.char(string="Imported filename", size=256),
    }

    _defaults = {
        'date': lambda *a: strftime('%Y-%m-%d'),
    }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Do treatment before validation:
        - check data from wizard
        - check that file exists and that data are inside
        - check integrity of data in files
        """
        # Some checks
        if not context:
            context = {}
        # Prepare some values
        created = 0
        processed = 0
        errors = []

        # Check wizard data
        for wiz in self.browse(cr, uid, ids):
            # Check that a file was given
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            fileobj = NamedTemporaryFile('w+b', delete=False)
            fileobj.write(decodestring(wiz.file))
            fileobj.close()
            content = SpreadsheetXML(xmlfile=fileobj.name)
            if not content:
                raise osv.except_osv(_('Warning'), _('No content.'))
            rows = content.getRows()
            # Use the first row to find which column to use
            cols = {}
            col_names = ['Description', 'Reference', 'Document Date', 'Posting Date', 'Third Party', 'Destination', 'Cost Centre', 'Booking Debit', 'Booking Credit', 'Booking Currency']
            for num, r in enumerate(rows):
                header = [x and x.data for x in r.iter_cells()]
                for el in col_names:
                    if el in header:
                        cols[el] = header.index(el)
                break
            # Number of line to bypass in line's count
            base_num = 2
            for el in col_names:
                if not el in cols:
                    raise osv.except_osv(_('Error'), _("'%s' column not found in file.") % (el,))
            # All lines
            debit = 0
            credit = 0
            for num, r in enumerate(rows):
                line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, r)
#                string = '%s - ' % (base_num + num)
#                printline = False
                # Bypass this line if NO debit AND NO credit
                if not line[cols['Booking Debit']] and not line[cols['Booking Credit']]:
                    continue
                if line[cols['Booking Debit']]:
                    debit += line[cols['Booking Debit']]
                if line[cols['Booking Credit']]:
                    credit += line[cols['Booking Credit']]
                if not line[cols['Third Party']]
                if line[cols]
#                for el in col_names:
#                    if line[cols[el]]:
#                        string += str(line[cols[el]])
#                        printline = True
#                if printline:
#                    print string

            # Check if all is ok for the file
            ## The lines should be balanced
            if (debit - credit) != 0.0:
                raise osv.except_osv(_('Error'), _('Not balanced: %s' ) % ((debit - credit),))
            print debit - credit
            # Check file's content
            # Launch journal entries write

        raise osv.except_osv('error', 'programmed error')

        # Display result
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_homere_interface', 'payroll_import_confirmation')
        view_id = view_id and view_id[1] or False
        context.update({'from': 'msf_doc_import_accounting'})
        res_id = self.pool.get('hr.payroll.import.confirmation').create(cr, uid, {'filename': filename, 'created': created, 'total': processed, 'state': 'migration', 'errors': "\n".join(errors), 'nberrors': len(errors)})
        
        return {
            'name': 'Accounting Import Confirmation',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.import.confirmation',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

msf_doc_import_accounting()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
