#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rigts Reserved
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
import threading
import pooler

class wizard_register_import(osv.osv_memory):
    _name = 'wizard.register.import'

    _columns = {
        'file': fields.binary(string="File", filters='*.xml, *.xls', required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'progression': fields.float(string="Progression", readonly=True),
        'message': fields.char(string="Message", size=256, readonly=True),
        'state': fields.selection([('draft', 'Created'), ('inprogress', 'In Progress'), ('error', 'Error'), ('done', 'Done')], string="State", readonly=True, required=True),
        'error_ids': fields.one2many('wizard.register.import.errors', 'wizard_id', "Errors", readonly=True),
        'register_id': fields.many2one('account.bank.statement', 'Register', required=True, readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'progression': lambda *a: 0.0,
        'state': lambda *a: 'draft',
    }

    def create_entries(self, cr, uid, ids, context=None):
        """
        Create register lines
        """
        # Checks
        if not context:
            context = {}
        # Prepare some values
        res = True
        # Fetch default funding pool: MSF Private Fund
        try: 
            msf_fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_fp_id = 0
        # Browse all wizards
        for w in self.browse(cr, uid, ids):
            # Search lines
            entries = self.pool.get('wizard.register.import.lines').search(cr, uid, [('wizard_id', '=', w.id)])
            if not entries:
                # Update wizard
                self.write(cr, uid, [w.id], {'message': _('No lines.'), 'progression': 100.0})
                return res
            # Browse result
            b_entries = self.pool.get('wizard.register.import.lines').browse(cr, uid, entries)
            current_percent = 20.0
            remaining_percent = 80.0
            entries_number = len(b_entries)
            # Create a register line for each entry
            for nb, l in enumerate(b_entries):
                # Do changes
                # FIXME: do changes!!!
                # Analytic distribution
                distrib_id = False
                # Create analytic distribution
                if l.account_id.user_type_code == 'expense':
                    distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context)
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': c_id,
                        'percentage': 100.0,
                        'date': l.date,
                        'source_date': l.date,
                        'destination_id': l.destination_id.id,
                    }
                    common_vals.update({'analytic_id': l.cost_center_id.id,})
                    cc_res = self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': msf_fp_id, 'cost_center_id': l.cost_center_id.id,})
                    fp_res = self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                # Update wizard
                progression = 20.0 + (entries_number / 80 * nb)
                self.write(cr, uid, [w.id], {'progression': progression})
        return res


    def _import(self, dbname, uid, ids, context=None):
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
        cr = pooler.get_db(dbname).cursor()
        created = 0
        processed = 0
        errors = []

        # Update wizard
        self.write(cr, uid, ids, {'message': _('Cleaning up old imports…'), 'progression': 1.00})
        # Clean up old temporary imported lines
        old_lines_ids = self.pool.get('wizard.register.import.lines').search(cr, uid, [])
        self.pool.get('wizard.register.import.lines').unlink(cr, uid, old_lines_ids)

        # Check wizard data
        for wiz in self.browse(cr, uid, ids):
            # Check that currency is active
            if not wiz.register_id.currency.active:
                raise osv.except_osv(_('Error'), _('Currency %s is not active !') % (wiz.register_id.currency.name))
            # Update wizard
            self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': 2.00})

            # Check that a file was given
            if not wiz.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            # Update wizard
            self.write(cr, uid, [wiz.id], {'message': _('Copying file…'), 'progression': 3.00})
            fileobj = NamedTemporaryFile('w+b', delete=False)
            fileobj.write(decodestring(wiz.file))
            fileobj.close()
            content = SpreadsheetXML(xmlfile=fileobj.name)
            if not content:
                raise osv.except_osv(_('Warning'), _('No content.'))
            # Update wizard
            self.write(cr, uid, [wiz.id], {'message': _('Processing line number…'), 'progression': 4.00})
            rows = content.getRows()
            nb_rows = len([x for x in content.getRows()])
            # Update wizard
            self.write(cr, uid, [wiz.id], {'message': _('Reading headers…'), 'progression': 5.00})
            # cols variable describe each column and its expected number
            cols = {
                'document_date': 0,
                'posting_date':  1,
                'description':   2,
                'reference':     3,
                'account':       4,
                'third_party':   5,
                'amount_in':     6,
                'amount_out':    7,
                'destination':   8,
                'cost_center':   9,
                'funding_pool': 10,
            }
            # Number of line to bypass in line's count
            base_num = 2 # because of Python that begins to 0.
            # Don't read the first line
            rows.next()
            # Update wizard
            self.write(cr, uid, [wiz.id], {'message': _('Reading lines…'), 'progression': 6.00})
            # Check file's content
            for num, r in enumerate(rows):
                # Update wizard
                percent = (float(num+1) / float(nb_rows+1)) * 100.0
                progression = ((float(num+1) * 94) / float(nb_rows)) + 6
                self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': progression})
                # Prepare some values
                r_debit = 0
                r_credit = 0
                r_currency = wiz.register_id.currency.id
                r_partner = False
                r_account = False
                r_destination = False
                r_cc = False
                r_fp = False
                r_document_date = False
                r_date = False
                r_period = False
                current_line_num = num + base_num
                # Fetch all XML row values
                line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, r)
                # Bypass this line if NO debit AND NO credit
                try:
                    bd = line[cols['amount_in']]
                except IndexError, e:
                    continue
                try:
                    bc = line[cols['amount_out']]
                except IndexError, e:
                    continue
                if not line[cols['amount_in']] and not line[cols['amount_out']]:
                    continue
                processed += 1
                # Get amount
                r_debit = line[cols['amount_in']]
                r_credit = line[cols['amount_out']]
                # Mandatory columns
                if not line[cols['document_date']]:
                    errors.append(_('Line %s: Document date is missing.') % (current_line_num,))
                    continue
                if not line[cols['posting_date']]:
                    errors.append(_('Line %s: Posting date is missing.') % (current_line_num,))
                    continue
                if not line[cols['description']]:
                    errors.append(_('Line %s: Description is missing.') % (current_line_num,))
                    continue
                if not line[cols['account']]:
                    errors.append(_('Line %s: Account is missing.') % (current_line_num,))
                    continue
                r_document_date = line[cols['document_date']]
                r_date = line[cols['posting_date']]
                r_description = line[cols['description']]
                # Check document/posting dates
                if line[cols['document_date']] > line[cols['posting_date']]:
                    errors.append(_("Line %s. Document date '%s' should be inferior or equal to Posting date '%s'.") % (current_line_num, line[cols['document_date']], line[cols['posting_date']],))
                    continue
                # Fetch document date and posting date
                r_document_date = line[cols['document_date']].strftime('%Y-%m-%d')
                r_date = line[cols['posting_date']].strftime('%Y-%m-%d')
                # Check that a period exist and is open
                period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, r_date, context)
                if not period_ids:
                    errors.append(_('Line %s. No period found for given date: %s') % (current_line_num, r_date))
                    continue
                r_period = period_ids[0]
                # Check that period correspond to those from register
                if r_period != wiz.register_id.period_id.id:
                    errors.append(_('Line %s: Posting date \'%s\' is not in the same period as given register.') % (current_line_num, r_date))
                    continue
                # Check G/L account
                account_code = line[cols['account']].split(' ') and line[cols['account']].split(' ')[0] or line[cols['account']]
                account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', account_code)])
                if not account_ids:
                    errors.append(_('Line %s. G/L account %s not found!') % (current_line_num, account_code,))
                    continue
                r_account = account_ids[0]
                account = self.pool.get('account.account').browse(cr, uid, r_account)
                # Check that Third party exists (if not empty)
                tp_label = 'Partner'
                if line[cols['third_party']]:
                    if account.type_for_register == 'advance':
                        tp_ids = self.pool.get('hr.employee').search(cr, uid, [('name', '=', line[cols['third_party']])])
                        tp_label = 'Employee'
                    else:
                        tp_ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', line[cols['third_party']])])
                    if not tp_ids:
                        errors.append(_('Line %s. %s not found: %s') % (current_line_num, tp_label, line[cols['third_party']],))
                        continue
                    r_partner = tp_ids[0]
                # Check analytic axis only if G/L account is an expense account
                if account.user_type_code == 'expense':
                    # Check Destination
                    try:
                        if line[cols['destination']]:
                            destination_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'DEST'), '|', ('name', '=', line[cols['destination']]), ('code', '=', line[cols['destination']])])
                            if destination_ids:
                                r_destination = destination_ids[0]
                    except IndexError, e:
                        pass
                    # Check Cost Center
                    try:
                        if line[cols['cost_center']]:
                            cc_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'OC'), '|', ('name', '=', line[cols['cost_center']]), ('code', '=', line[cols['cost_center']])])
                            if cc_ids:
                                r_cc = cc_ids[0]
                    except IndexError, e:
                        pass
                    # Check funding pool
                    try:
                        if line[cols['funding_pool']]:
                            fp_ids = self.pool.get('account.analytic.account').search(cr, uid, [('category', '=', 'FUNDING'), '|', ('name', '=', line[cols['funding_pool']]), ('code', '=', line[cols['funding_pool']])])
                            if fp_ids:
                                r_fp = fp_ids[0]
                    except IndexError, e:
                        pass
                    # NOTE: There is no need to check G/L account, Cost Center and Destination regarding document/posting date because this check is already done at Journal Entries validation.

                # Registering data regarding these "keys":
                # - G/L Account
                # - Third Party
                # - Destination
                # - Cost Centre
                # - Booking Currency
                vals = {
                    'description': r_description or '',
                    'ref': line[cols['reference']] or '',
                    'account_id': r_account or False,
                    'debit': r_debit or 0.0,
                    'credit': r_credit or 0.0,
                    'cost_center_id': r_cc or False,
                    'destination_id': r_destination or False,
                    'funding_pool_id': r_fp or False,
                    'document_date': r_document_date or False,
                    'date': r_date or False,
                    'currency_id': r_currency or False,
                    'wizard_id': wiz.id,
                    'period_id': r_period or False,
                }
                if account.type_for_register == 'advance':
                    vals.update({'employee_id': r_partner,})
                else:
                    vals.update({'partner_id': r_partner,})
                line_res = self.pool.get('wizard.register.import.lines').create(cr, uid, vals, context)
                if not line_res:
                    errors.append(_('Line %s. A problem occured for line registration. Please contact an Administrator.') % (current_line_num,))
                    continue
                created += 1

        # Update wizard
        self.write(cr, uid, ids, {'message': _('Check complete. Reading potential errors or write needed changes.'), 'progression': 100.0})

        wiz_state = 'done'
        # If errors, cancel probable modifications
        if errors:
            #cr.rollback()
            created = 0
            message = 'Import FAILED.'
            # Delete old errors
            error_ids = self.pool.get('wizard.register.import.errors').search(cr, uid, [], context)
            if error_ids:
                self.pool.get('wizard.register.import.errors').unlink(cr, uid, error_ids ,context)
            # create errors lines
            for e in errors:
                self.pool.get('wizard.register.import.errors').create(cr, uid, {'wizard_id': wiz.id, 'name': e}, context)
            wiz_state = 'error'
        else:
            # Update wizard
            self.write(cr, uid, ids, {'message': _('Writing changes…'), 'progression': 0.0})
            # Create all journal entries
            self.create_entries(cr, uid, ids, context)
            message = 'Import successful.'

        # Update wizard
        self.write(cr, uid, ids, {'message': message, 'state': wiz_state, 'progression': 100.0})

        # Close cursor
        cr.commit()
        cr.close()
        return True

    def button_validate(self, cr, uid, ids, context=None):
        """
        Launch a thread (to check file and write changes) and return to this wizard.
        """
        if not context:
            context = {}
        # Launch a thread
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        
        return self.write(cr, uid, ids, {'state': 'inprogress'}, context)

    def button_update(self, cr, uid, ids, context=None):
        """
        Update view
        """
        return False

wizard_register_import()

class wizard_register_import_lines(osv.osv):
    _name = 'wizard.register.import.lines'

    _columns = {
        'description': fields.text("Description", required=False, readonly=True),
        'ref': fields.text("Reference", required=False, readonly=True),
        'document_date': fields.date("Document date", required=True, readonly=True),
        'date': fields.date("Posting date", required=True, readonly=True),
        'account_id': fields.many2one('account.account', "G/L Account", required=True, readonly=True),
        'destination_id': fields.many2one('account.analytic.account', "Destination", required=False, readonly=True),
        'cost_center_id': fields.many2one('account.analytic.account', "Cost Center", required=False, readonly=True),
        'funding_pool_id': fields.many2one('account.analytic.account', "Funding Pool", required=False, readonly=True),
        'debit': fields.float("Debit", required=False, readonly=True),
        'credit': fields.float("Credit", required=False, readonly=True),
        'currency_id': fields.many2one('res.currency', "Currency", required=True, readonly=True),
        'partner_id': fields.many2one('res.partner', "Partner", required=False, readonly=True),
        'employee_id': fields.many2one('hr.employee', "Employee", required=False, readonly=True),
        'period_id': fields.many2one('account.period', "Period", required=True, readonly=True),
        'wizard_id': fields.integer("Wizard", required=True, readonly=True),
    }

    _defaults = {
        'description': lambda *a: '',
        'ref': lambda *a: '',
        'document_date': lambda *a: strftime('%Y-%m-%d'),
        'date': lambda *a: strftime('%Y-%m-%d'),
        'debit': lambda *a: 0.0,
        'credit': lambda *a: 0.0,
    }

wizard_register_import_lines()

class wizard_register_import_errors(osv.osv_memory):
    _name = 'wizard.register.import.errors'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('wizard.register.import', "Wizard", required=True, readonly=True),
    }

wizard_register_import_errors()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
