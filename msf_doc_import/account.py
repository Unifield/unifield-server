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
            col_names = ['Description', 'Reference', 'Document Date', 'Posting Date', 'G/L Account', 'Third party', 'Destination', 'Cost Centre', 'Booking Debit', 'Booking Credit', 'Booking Currency']
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
            money = {}
            # Check file's content
            for num, r in enumerate(rows):
                # Prepare some values
                r_debit = 0
                r_credit = 0
                r_currency = False
                r_partner = False
                r_account = False
                r_destination = False
                r_cc = False
                current_line_num = num + base_num
                # Fetch all XML row values
                line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, r)
                # Bypass this line if NO debit AND NO credit
                if not line[cols['Booking Debit']] and not line[cols['Booking Credit']]:
                    continue
                # Check that currency is active
                if not line[cols['Booking Currency']]:
                    errors.append(_('Line %s. No currency specified!') % (current_line_num,))
                    continue
                curr_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', line[cols['Booking Currency']])])
                if not curr_ids:
                    errors.append(_('Line %s. Currency not found: %s') % (current_line_num, line[cols['Booking Currency']],))
                    continue
                for c in self.pool.get('res.currency').browse(cr, uid, curr_ids):
                    if not c.active:
                        errors.append(_('Line %s. Currency is not active: %s') % (current_line_num, line[cols['Booking Currency']],))
                        continue
                r_currency = curr_ids[0]
                if not line[cols['Booking Currency']] in money:
                    money[line[cols['Booking Currency']]] = {}
                if not 'debit' in money[line[cols['Booking Currency']]]:
                    money[line[cols['Booking Currency']]]['debit'] = 0
                if not 'credit' in money[line[cols['Booking Currency']]]:
                    money[line[cols['Booking Currency']]]['credit'] = 0
                if not 'name' in money[line[cols['Booking Currency']]]:
                    money[line[cols['Booking Currency']]]['name'] = line[cols['Booking Currency']]
                # Increment global debit/credit
                if line[cols['Booking Debit']]:
                    money[line[cols['Booking Currency']]]['debit'] += line[cols['Booking Debit']]
                    r_debit = line[cols['Booking Debit']]
                if line[cols['Booking Credit']]:
                    money[line[cols['Booking Currency']]]['credit'] += line[cols['Booking Credit']]
                    r_credit = line[cols['Booking Credit']]
                # Check document/posting dates
                if not line[cols['Document Date']]:
                    errors.append(_('Line %s. No document date specified!') % (current_line_num,))
                    continue
                if not line[cols['Posting Date']]:
                    errors.append(_('Line %s. No posting date specified!') % (current_line_num,))
                    continue
                if line[cols['Document Date']] > line[cols['Posting Date']]:
                    errors.append(_("Line %s. Document date '%s' should be inferior or equal to Posting date '%s'.") % (current_line_num, line[cols['Document Date']], line[cols['Posting Date']],))
                    continue
                # Check G/L account
                if not line[cols['G/L Account']]:
                    errors.append(_('Line %s. No G/L account specified!') % (current_line_num,))
                    continue
                account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', line[cols['G/L Account']])])
                if not account_ids:
                    errors.append(_('Line %s. G/L account %s not found!') % (current_line_num, line[cols['G/L Account']],))
                    continue
                r_account = account_ids[0]
                account = self.pool.get('account.account').browse(cr, uid, r_account)
                # Check that Third party exists (if not empty)
                tp_label = 'Partner'
                if line[cols['Third party']]:
                    if account.type_for_register == 'advance':
                        tp_ids = self.pool.get('hr.employee').search(cr, uid, [('name', '=', line[cols['Third party']])])
                        tp_label = 'Employee'
                    else:
                        tp_ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', line[cols['Third party']])])
                    if not tp_ids:
                        errors.append(_('Line %s. %s not found: %s') % (current_line_num, tp_label, line[cols['Third party']],))
                        continue
                    r_partner = tp_ids[0]
                # Check analytic axis only if G/L account is an expense account
                if account.user_type_code == 'expense':
                    # Check Destination
                    if not line[cols['Destination']]:
                        errors.append(_('Line %s. No destination specified!') % (current_line_num,))
                        continue
                    destination_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'DEST'), '|', ('name', '=', line[cols['Destination']]), ('code', '=', line[cols['Destination']])])
                    if not destination_ids:
                        errors.append(_('Line %s. Destination %s not found!') % (current_line_num, line[cols['Destination']],))
                        continue
                    r_destination = destination_ids[0]
                    # Check Cost Center
                    if not line[cols['Cost Centre']]:
                        errors.append(_('Line %s. No cost center specified:') % (current_line_num,))
                        continue
                    cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), '|', ('name', '=', line[cols['Cost Centre']]), ('code', '=', line[cols['Cost Centre']])])
                    if not cc_ids:
                        errors.append(_('Line %s. Cost Center %s not found!') % (current_line_num, line[cols['Cost Centre']]))
                        continue
                    r_cc = cc_ids[0]
                # NOTE: There is no need to check G/L account, Cost Center and Destination regarding document/posting date because this check is already done at Journal Entries validation.

                # Launch journal entry write
                # FIXME
            # Check if all is ok for the file
            ## The lines should be balanced for each currency
            for c in money:
                if (money[c]['debit'] - money[c]['credit']) != 0.0:
                    raise osv.except_osv(_('Error'), _('Currency %s is not balanced: %s' ) % (money[c]['name'], (money[c]['debit'] - money[c]['credit']),))

        for e in errors:
            print e

        raise osv.except_osv('error', 'programmed error')

        # FIXME
        if errors:
            cr.rollback()
            created = 0
            # FIXME
        else:
            pass

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
