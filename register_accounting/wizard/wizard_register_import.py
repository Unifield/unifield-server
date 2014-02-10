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
from ..register_tools import open_register_view
from lxml import etree

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
        'progression': lambda *a: 0.0,
        'state': lambda *a: 'draft',
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change table's headers name (to be well translated)
        """
        if not context:
            context = {}
        view = super(wizard_register_import, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='form':
            form = etree.fromstring(view['arch'])
            for el in [('document_date', 'Document Date'), ('posting_date', 'Posting Date'), ('description', 'Description'), ('reference', 'Reference'), ('account', 'Account'), ('third_party', 'Third Party'), ('amount_in', 'Amount In'), ('amount_out', 'Amount Out'), ('destination', 'Destination'), ('cost_center', 'Cost Centre'), ('funding_pool', 'Funding Pool'), ('proprietary_instance', "Proprietary instance's code"), ('journal', "Journal's code"), ('currency', "Currency's code")]:
                fields = form.xpath('/form//th[@class="' + el[0] + '"]')
                for field in fields:
                    field.text = _(el[1])
            fields = form.xpath
            view['arch'] = etree.tostring(form)
        return view

    def create(self, cr, uid, vals, context=None):
        """
        Add register regarding context @creation
        """
        if not context:
            return False
        res = super(wizard_register_import, self).create(cr, uid, vals, context=context)
        if context.get('active_ids', False):
            ids = res
            if isinstance(ids, (int, long)):
                ids = [ids]
            self.write(cr, uid, ids, {'register_id': context.get('active_ids')[0]}, context=context)
        return res

    def create_entries(self, cr, uid, ids, remaining_percent=50.0, context=None):
        """
        Create register lines with/without analytic distribution.
        If all neeeded info for analytic distribution are present: attempt to create analytic distribution.
        If this one is invalid, delete it!
        """
        # Checks
        if not context:
            context = {}
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
                raise osv.except_osv(_('Error'), _('No lines.'))
            # Browse result
            b_entries = self.pool.get('wizard.register.import.lines').browse(cr, uid, entries)
            current_percent = 100.0 - remaining_percent
            entries_number = len(b_entries)
            # Create a register line for each entry
            for nb, l in enumerate(b_entries):
                # Prepare values
                vals = {
                    'name':                l.description,
                    'reference':           l.ref,
                    'document_date':       l.document_date,
                    'date':                l.date,
                    'account_id':          l.account_id.id,
                    'amount':              (l.debit or 0.0) - (l.credit or 0.0),
                    'partner_id':          l.partner_id and l.partner_id.id or False,
                    'employee_id':         l.employee_id and l.employee_id.id or False,
                    'transfer_journal_id': l.transfer_journal_id and l.transfer_journal_id.id or False,
                    'statement_id':        w.register_id.id,
                }
                absl_id = self.pool.get('account.bank.statement.line').create(cr, uid, vals, context)
                # Analytic distribution
                distrib_id = False
                # Create analytic distribution
                if l.account_id.is_analytic_addicted and l.destination_id and l.cost_center_id and l.funding_pool_id:
                    distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context)
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': w.register_id.currency.id,
                        'percentage': 100.0,
                        'date': l.date,
                        'source_date': l.date,
                        'destination_id': l.destination_id.id,
                    }
                    common_vals.update({'analytic_id': l.cost_center_id.id,})
                    cc_res = self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': l.funding_pool_id and l.funding_pool_id.id or msf_fp_id, 'cost_center_id': l.cost_center_id.id,})
                    fp_res = self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    # Check analytic distribution
                    self.pool.get('account.bank.statement.line').write(cr, uid, [absl_id], {'analytic_distribution_id': distrib_id,})
                    absl_data = self.pool.get('account.bank.statement.line').read(cr, uid, [absl_id], ['analytic_distribution_state'], context)
                    delete_distribution = True
                    if absl_data and absl_data[0]:
                        if absl_data[0].get('analytic_distribution_state', False) == 'valid':
                            delete_distribution = False
                    if delete_distribution:
                        self.pool.get('account.bank.statement.line').write(cr, uid, [absl_id], {'analytic_distribution_id': False}, context)
                        self.pool.get('analytic.distribution').unlink(cr, uid, [distrib_id], context)
                # Update wizard with current progression
                progression = current_percent + (nb + 1.0) / entries_number * remaining_percent
                self.write(cr, uid, [w.id], {'progression': progression})
        return True

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

        try:
            # Update wizard
            self.write(cr, uid, ids, {'message': _('Cleaning up old imports…'), 'progression': 1.00}, context)
            # Clean up old temporary imported lines
            old_lines_ids = self.pool.get('wizard.register.import.lines').search(cr, uid, [])
            self.pool.get('wizard.register.import.lines').unlink(cr, uid, old_lines_ids)

            # Check wizard data
            for wiz in self.browse(cr, uid, ids, context):
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': 2.00}, context)
                # Check that a file was given
                if not wiz.file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Copying file…'), 'progression': 3.00}, context)
                fileobj = NamedTemporaryFile('w+b', delete=False)
                fileobj.write(decodestring(wiz.file))
                fileobj.close()
                content = SpreadsheetXML(xmlfile=fileobj.name)
                if not content:
                    raise osv.except_osv(_('Warning'), _('No content.'))
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Processing line…'), 'progression': 4.00}, context)
                rows = content.getRows()
                nb_rows = len([x for x in content.getRows()])
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Reading headers…'), 'progression': 5.00}, context)
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
                base_num = 5 # because of Python that begins to 0.
                # Attempt to read 3 first lines
                first_line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, rows.next())
                try:
                    instance_code = first_line[1]
                except IndexError, e:
                    raise osv.except_osv(_('Warning'), _('Proprietary Instance not found.'))
                second_line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, rows.next())
                try:
                    journal_code = second_line[1]
                except IndexError, e:
                    raise osv.except_osv(_('Warning'),  _('No journal code found.'))
                third_line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, rows.next())
                try:
                    currency_code = third_line[1]
                except IndexError, e:
                    raise osv.except_osv(_('Warning'), _('No currency code found.'))
                # Check first info: proprietary instance
                instance_ids = self.pool.get('msf.instance').search(cr, uid, [('code', '=', instance_code)])
                if not instance_ids or len(instance_ids) > 1:
                    raise osv.except_osv(_('Warning'), _('Instance %s not found.') % (instance_code or '',))
                if isinstance(instance_ids, (int, long)):
                    instance_ids = [instance_ids]
                # Check second info: journal's code
                journal_ids = self.pool.get('account.journal').search(cr, uid, [('code', '=', journal_code)])
                if not journal_ids or len(journal_ids) > 1:
                    raise osv.except_osv(_('Warning'), _('Journal %s not found.') % (journal_code or '',))
                if isinstance(journal_ids, (int, long)):
                    journal_ids = [journal_ids]
                # Check third info: currency's code
                currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', currency_code)])
                if not currency_ids or len(currency_ids) > 1:
                    raise osv.except_osv(_('Warning'), _('Currency %s not found.') % (currency_code or '',))
                # Check that currency is active
                if isinstance(currency_ids, (int, long)):
                    currency_ids = [currency_ids]
                cur = self.pool.get('res.currency').browse(cr, uid, currency_ids, context)
                if not cur or not cur[0] or not cur[0].active:
                    raise osv.except_osv(_('Error'), _('Currency %s is not active!') % (cur.name))
                # Check that currency is the same as register's one
                if wiz.register_id.currency.id not in currency_ids:
                    raise osv.except_osv('', _("the import's currency is %s whereas the register's currency is %s") % (cur[0].name, wiz.register_id.currency.name))
                # Search registers that correspond to this instance, journal's code and currency and check that our register is in the list
                register_ids = self.pool.get('account.bank.statement').search(cr, uid, [('instance_id', 'in', instance_ids), ('journal_id', 'in', journal_ids), ('currency', 'in', currency_ids)])
                if not register_ids or wiz.register_id.id not in register_ids:
                    raise osv.except_osv(_('Error'), _("The given register does not correspond to register's information from the file. Instance code: %s. Journal's code: %s. Currency code: %s.") % (wiz.register_id.instance_id.code, wiz.register_id.journal_id.code, wiz.register_id.currency.name))
                # Don't read the fourth line
                rows.next()
                # Update wizard
                self.write(cr, uid, [wiz.id], {'message': _('Reading lines…'), 'progression': 6.00}, context)
                # Remaining percent
                # 100 - 6 (94) is the remaining for:
                # - checking lines
                # - writing them
                # - validate the wizard and finish it
                # So we have 2% for miscellaneous transactions, 92% remaining with 46% checking lines and 46% to write them.
                remaining = (100.0 - 6.0 - 2.0) / 2.0
                # Check file's content
                for num, r in enumerate(rows):
                    # Update wizard
                    percent = (float(num+1) / float(nb_rows+1)) * 100.0
                    progression = ((float(num+1) * remaining) / float(nb_rows)) + 6
                    self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': progression}, context)
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
                        bd = 0.0
                    try:
                        bc = line[cols['amount_out']]
                    except IndexError, e:
                        bc = 0.0
                    if (not bd and not bc) or (bd == 0.0 and bc == 0.0):
                        continue
                    if bd and bc and (bc != 0.0 or bd != 0.0):
                        errors.append(_('Line %s: Double amount, IN and OUT. Use only one!') % (current_line_num,))
                        continue
                    processed += 1
                    # Get amount
                    r_debit = bd
                    r_credit = bc
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
                    if r[cols['document_date']].type != 'datetime':
                        errors.append(_('Line %s: Document date wrong excel format. Use a date one.') % (current_line_num,))
                        continue
                    r_document_date = line[cols['document_date']].strftime('%Y-%m-%d')
                    if r[cols['posting_date']].type != 'datetime':
                        errors.append(_('Line %s: Posting date wrong excel format. Use a date one.') % (current_line_num))
                        continue
                    r_date = line[cols['posting_date']].strftime('%Y-%m-%d')
                    r_description = line[cols['description']]
                    # Check document/posting dates
                    if line[cols['document_date']] > line[cols['posting_date']]:
                        errors.append(_("Line %s. Document date '%s' should be inferior or equal to Posting date '%s'.") % (current_line_num, line[cols['document_date']], line[cols['posting_date']],))
                        continue
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
                    account_code = str(line[cols['account']]).split(' ') and str(line[cols['account']]).split(' ')[0] or str(line[cols['account']])
                    account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', account_code)])
                    if not account_ids:
                        errors.append(_('Line %s. G/L account %s not found!') % (current_line_num, account_code,))
                        continue
                    r_account = account_ids[0]
                    account = self.pool.get('account.account').browse(cr, uid, r_account, context)
                    # Check that Third party exists (if not empty)
                    tp_label = _('Partner')
                    partner_type = 'partner'
                    if line[cols['third_party']]:
                        if account.type_for_register == 'advance':
                            tp_ids = self.pool.get('hr.employee').search(cr, uid, [('name', '=', line[cols['third_party']])])
                            tp_label = _('Employee')
                            partner_type = 'employee'
                        elif account.type_for_register in ['transfer', 'transfer_same']:
                            tp_ids = self.pool.get('account.bank.statement').search(cr, uid, [('name', '=', line[cols['third_party']])])
                            tp_label = _('Journal')
                            partner_type = 'journal'
                        else:
                            tp_ids = self.pool.get('res.partner').search(cr, uid, [('name', '=', line[cols['third_party']])])
                            partner_type = 'partner'
                        if not tp_ids:
                            # Search now if employee exists
                            tp_ids = self.pool.get('hr.employee').search(cr, uid, [('name', '=', line[cols['third_party']])])
                            tp_label = _('Employee')
                            partner_type = 'employee'
                            # If really not, raise an error for this line
                            if not tp_ids:
                                errors.append(_('Line %s. %s not found: %s') % (current_line_num, tp_label, line[cols['third_party']],))
                                continue
                        r_partner = tp_ids[0]
                    # Check analytic axis only if G/L account is an analytic-a-holic account
                    if account.is_analytic_addicted:
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
                    elif account.type_for_register in ['transfer', 'transfer_same']:
                        vals.update({'transfer_journal_id': r_partner})
                    else:
                        if partner_type == 'partner':
                            vals.update({'partner_id': r_partner,})
                        elif partner_type == 'employee':
                            vals.update({'employee_id': r_partner,})
                    line_res = self.pool.get('wizard.register.import.lines').create(cr, uid, vals, context)
                    if not line_res:
                        errors.append(_('Line %s. A problem occured for line registration. Please contact an Administrator.') % (current_line_num,))
                        continue
                    created += 1

            # Update wizard
            self.write(cr, uid, ids, {'message': _('Check complete. Reading potential errors or write needed changes.'), 'progression': 53.0}, context)

            wiz_state = 'done'
            # If errors, cancel probable modifications
            if errors:
                cr.rollback()
                created = 0
                message = _('Import FAILED.')
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
                self.write(cr, uid, ids, {'message': _('Writing changes…'), 'progression': 54.0}, context)
                # Create all journal entries
                self.create_entries(cr, uid, ids, 46.0, context)
                message = _('Import successful.')

            # Update wizard
            self.write(cr, uid, ids, {'message': message, 'state': wiz_state, 'progression': 100.0}, context)

            # Close cursor
            cr.commit()
            cr.close()
        except osv.except_osv as osv_error:
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occured %s: %s") % (osv_error.name, osv_error.value), 'state': 'done', 'progression': 100.0})
            cr.close()
        except Exception as e:
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occured: %s") % (e and e.args and e.args[0] or ''), 'state': 'done', 'progression': 100.0})
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
        
        # Write changes
        self.write(cr, uid, ids, {'state': 'inprogress'}, context)
        # Return a dict to avoid problem of panel bar to the right
        return {
         'type': 'ir.actions.act_window',
         'res_model': 'wizard.register.import',
         'view_type': 'form',
         'view_mode': 'form',
         'res_id': ids[0],
         'context': context,
         'target': 'new',
        }

    def button_update(self, cr, uid, ids, context=None):
        """
        Update view to see progress bar
        """
        return False

    def button_return(self, cr, uid, ids, context=None):
        """
        Return to the register
        """
        if not context:
            context = {}
        res = {'type': 'ir.actions.act_window_close'}
        wiz = self.browse(cr, uid, ids, context)
        if wiz and wiz[0].register_id:
            res = open_register_view(self, cr, uid, wiz[0].register_id.id, context)
        return res

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
        'transfer_journal_id': fields.many2one('account.bank.statement', 'Transfer Journal', required=False, readonly=True,)
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
