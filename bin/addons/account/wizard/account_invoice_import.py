#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) TeMPO Consulting (<http://www.tempo-consulting.fr/>), MSF.
#    All Rights Reserved
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
from tempfile import NamedTemporaryFile
from base64 import decodestring
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from account.report import export_invoice
from datetime import datetime
import threading
import pooler
import logging
import tools


class account_invoice_import(osv.osv_memory):
    _name = 'account.invoice.import'

    _columns = {
        'file': fields.binary(string="File", filters='*.xml, *.xls', required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'progression': fields.float(string="Progression", readonly=True),
        'message': fields.char(string="Message", size=256, readonly=True),
        'state': fields.selection([('draft', 'Created'), ('inprogress', 'In Progress'), ('error', 'Error'), ('ad_error', 'AD Error'), ('done', 'Done')],
                                  string="State", readonly=True, required=True),
        'error_ids': fields.one2many('account.invoice.import.errors', 'wizard_id', "Errors", readonly=True),
        'invoice_id': fields.many2one('account.invoice', 'Invoice', required=True, readonly=True),
    }

    _defaults = {
        'progression': lambda *a: 0.0,
        'state': lambda *a: 'draft',
    }

    def create(self, cr, uid, vals, context=None):
        """
        Creation of the wizard using the realUid to allow the process for the non-admin users
        """
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        return super(account_invoice_import, self).create(cr, real_uid, vals, context=context)

    def _import(self, dbname, uid, ids, context=None):
        """
        Checks file data, and either updates the lines or displays the errors found
        """
        if context is None:
            context = {}
        cr = pooler.get_db(dbname).cursor()
        errors = []
        ad_errors = []
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        currency_obj = self.pool.get('res.currency')
        partner_obj = self.pool.get('res.partner')
        account_obj = self.pool.get('account.account')
        product_obj = self.pool.get('product.product')
        import_cell_data_obj = self.pool.get('import.cell.data')
        errors_obj = self.pool.get('account.invoice.import.errors')
        ana_obj = self.pool.get('analytic.distribution')
        aac_obj = self.pool.get('account.analytic.account')

        def _check_col_length(percent_col, cc_col, dest_col, fp_col, line_num, errors):
            if isinstance(percent_col, list):
                if not isinstance(cc_col,list) or len(cc_col) != len(percent_col) or \
                    not isinstance(dest_col, list) or len(dest_col) != len(percent_col) or \
                        not isinstance(fp_col, list) or len(fp_col) != len(percent_col):
                    errors.append(_('Line %s: Cost Center, Destination and Funding Pool columns should have '
                                                       'the same number of values as Percentage column') % line_num)
        def _check_percent_values(percent_col, line_num, errors):
            '''
            Check if the Percent Column values adds up to exactly 100
            '''
            if isinstance(percent_col, list):
                try:
                    percent_vals = [float(percent_val) for percent_val in percent_col]
                    if sum(percent_vals) != 100:
                        errors.append(
                            _('Line %s: The values in Percentage column should add up to exactly 100') % line_num)
                    if any(percent_val <= 0 or percent_val > 100 for percent_val in percent_vals):
                        errors.append(_('Line %s: All percentages values should be superior to 0 and inferior or equal to 100') % line_num)
                except ValueError as e:
                    errors.append(_('Line %s: All values in Percentage column should be numbers') % line_num)

        def _is_ad_diff(current_ad, cc_ids, dest_ids, fp_ids, percentages):
            ad_diff = False
            for i, percent in enumerate(percentages):
                if current_ad.funding_pool_lines[i].analytic_id.id != fp_ids[i] or \
                        current_ad.funding_pool_lines[i].cost_center_id.id != cc_ids[i] or \
                        current_ad.funding_pool_lines[i].destination_id.id != dest_ids[i] or \
                        current_ad.funding_pool_lines[i].percentage != percent:
                    ad_diff = True
            return ad_diff

        try:
            for wiz in self.browse(cr, uid, ids, context):
                self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': 1.00}, context)
                if not wiz.file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))
                fileobj = NamedTemporaryFile('w+b', delete=False)
                fileobj.write(decodestring(wiz.file))
                fileobj.close()
                content = SpreadsheetXML(xmlfile=fileobj.name, context=context)
                if not content:
                    raise osv.except_osv(_('Warning'), _('No content.'))
                invoice = wiz.invoice_id
                if invoice.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('The import is allowed only in Draft state.'))
                rows = content.getRows()
                nb_rows = len([x for x in content.getRows()])
                self.write(cr, uid, [wiz.id], {'message': _('Checking header…'), 'progression': 5.00}, context)
                # indexes of the file columns:
                cols = {
                    'line_number': 0,
                    'product': 1,
                    'account': 2,
                    'quantity': 3,
                    'unit_price': 4,
                    'description': 5,
                    'notes': 6,
                    'percentage': 7,
                    'cost_center': 8,
                    'destination': 9,
                    'funding_pool': 10,
                }
                # number of the first line in the file containing data (not header)
                base_num = 10
                rows.next()  # number is ignored
                rows.next()  # journal is ignored
                currency_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    currency_name = currency_line[1]
                except IndexError, e:
                    raise osv.except_osv(_('Warning'), _('No currency found.'))
                currency_ids = currency_obj.search(cr, uid,
                                                   [('name', '=', currency_name), ('currency_table_id', '=', False),
                                                    ('active', '=', True)], limit=1, context=context)
                if not currency_ids:
                    raise osv.except_osv(_('Error'), _("Currency %s not found or inactive.") % (currency_name or '',))
                partner_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    partner_name = partner_line[1]
                except IndexError, e:
                    raise osv.except_osv(_('Warning'), _('No partner found.'))
                partner_ids = partner_obj.search(cr, uid, [('name', '=', partner_name), ('active', '=', True)], context=context)
                if not partner_ids:
                    raise osv.except_osv(_('Error'), _("Partner %s not found or inactive.") % (partner_name or '',))
                rows.next()  # document date is ignored
                posting_date_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    posting_date = posting_date_line[1] or False
                except IndexError, e:
                    posting_date = False
                if posting_date:
                    try:
                        posting_date = posting_date.strftime('%Y-%m-%d')
                    except AttributeError, e:
                        raise osv.except_osv(_('Warning'), _("The posting date has a wrong format."))
                invoice_dom = [('id', '=', invoice.id),
                               ('currency_id', '=', currency_ids[0]),
                               ('partner_id', '=', partner_ids[0]),
                               ('date_invoice', '=', posting_date)]
                if not invoice_obj.search_exist(cr, uid, invoice_dom, context=context):
                    raise osv.except_osv(_('Warning'),
                                         _("The combination \"Currency, Partner and Posting Date\" of the imported file "
                                           "doesn't match with the current invoice."))
                # ignore: header account, empty line, line with titles
                for i in range(3):
                    rows.next()
                header_percent = 10  # percentage of the process reached AFTER having checked the header
                self.write(cr, uid, [wiz.id], {'message': _('Checking lines…'), 'progression': header_percent}, context)
                lines_percent = 99  # % of the process to be reached AFTER having checked and updated the lines
                # use the method from export_invoice to determine whether the product and quantity columns are editable
                all_fields_editable = not export_invoice.is_readonly(self, invoice)
                # check the lines
                for num, r in enumerate(rows):
                    current_line_num = num + base_num
                    vals = {}
                    line = import_cell_data_obj.get_line_values(cr, uid, ids, r)
                    line.extend([False for i in range(len(cols) - len(line))])
                    # get the data
                    line_number = line[cols['line_number']]
                    product_code = line[cols['product']] and tools.ustr(line[cols['product']])
                    account_code = line[cols['account']] and tools.ustr(line[cols['account']])
                    quantity = line[cols['quantity']] or 0.0
                    unit_price = line[cols['unit_price']] or 0.0
                    description = line[cols['description']] and tools.ustr(line[cols['description']])
                    notes = line[cols['notes']] and tools.ustr(line[cols['notes']])
                    percentage_vals = line[cols['percentage']] and \
                                      (len(tools.ustr(line[cols['percentage']]).split(';')) > 0 and
                                       tools.ustr(line[cols['percentage']]).split(';'))
                    cost_center_vals = line[cols['cost_center']] and \
                                       (len(tools.ustr(line[cols['cost_center']]).split(';')) > 0 and
                                        tools.ustr(line[cols['cost_center']]).split(';'))
                    destination_vals = line[cols['destination']] and \
                                       (len(tools.ustr(line[cols['destination']]).split(';')) > 0 and
                                        tools.ustr(line[cols['destination']]).split(';'))
                    funding_pool_vals = line[cols['funding_pool']] and \
                                        (len(tools.ustr(line[cols['funding_pool']]).split(';')) > 0 and
                                         tools.ustr(line[cols['funding_pool']]).split(';'))

                    if not line_number:
                        errors.append(_('Line %s: the line number is missing.') % (current_line_num,))
                        continue
                    try:
                        line_number = int(line_number)
                    except ValueError as e:
                        errors.append(_("Line %s: the line number format is incorrect.") % (current_line_num,))
                        continue
                    invoice_line_dom = [('invoice_id', '=', invoice.id), ('line_number', '=', line_number)]
                    invoice_line_ids = invoice_line_obj.search(cr, uid, invoice_line_dom, limit=1, context=context)
                    if not invoice_line_ids:
                        errors.append(_("Line %s: the line number %s doesn't exist in the invoice.") % (current_line_num, line_number))
                        continue
                    if not account_code:
                        errors.append(_("Line %s: the account (mandatory) is missing.") % (current_line_num,))
                        continue
                    account_ids = account_obj.search(cr, uid, [('code', '=', account_code)], limit=1, context=context)
                    if not account_ids:
                        errors.append(_("Line %s: the account %s doesn't exist.") % (current_line_num, account_code))
                        continue
                    account = account_obj.browse(cr, uid, account_ids[0], context=context)
                    checking_date = posting_date or datetime.now().strftime('%Y-%m-%d')
                    if checking_date < account.activation_date or (account.inactivation_date and checking_date >= account.inactivation_date):
                        errors.append(_("Line %s: the account %s is inactive.") % (current_line_num, account_code))
                        continue
                    # restricted_area = accounts allowed. Note: the context is different for each type and used in the related fnct_search
                    if invoice.is_intermission:
                        restricted_area = 'intermission_lines'  # for IVI / IVO
                    elif invoice.is_inkind_donation:  # for Donations
                        restricted_area = 'donation_lines'
                    else:
                        restricted_area = 'invoice_lines'  # for SI / STV / ISI
                    if not account_obj.search_exist(cr, uid, [('id', '=', account.id), ('restricted_area', '=', restricted_area)],
                                                    context=context):
                        errors.append(_("Line %s: the account %s is not allowed.") % (current_line_num, account_code))
                        continue
                    vals['account_id'] = account.id
                    try:
                        unit_price = float(unit_price)
                    except ValueError as e:
                        errors.append(_("Line %s: the unit price format is incorrect.") % (current_line_num,))
                        continue
                    vals['price_unit'] = unit_price
                    # edit the Product and Quantity only if it is allowed
                    if all_fields_editable:
                        if not product_code:
                            vals['product_id'] = False  # delete the existing value
                        else:
                            product_ids = product_obj.search(cr, uid, [('default_code', '=', product_code), ('active', '=', True)],
                                                             limit=1, context=context)
                            if not product_ids:
                                errors.append(_("Line %s: the product %s doesn't exist or is inactive.") % (current_line_num, product_code))
                                continue
                            vals['product_id'] = product_ids[0]
                        try:
                            quantity = float(quantity)
                        except ValueError as e:
                            errors.append(_("Line %s: the quantity format is incorrect.") % (current_line_num,))
                            continue
                        vals['quantity'] = quantity

                    if not description:
                        errors.append(_("Line %s: the description (mandatory) is missing.") % (current_line_num,))
                        continue
                    vals['name'] = description
                    vals['note'] = notes

                    if not percentage_vals:
                        errors.append(_("Line %s: The percentages are mandatory") % current_line_num)
                    if account.is_analytic_addicted and percentage_vals:
                        if not cost_center_vals:
                            errors.append(_("Line %s: An expense account is set while the cost center code (mandatory) is missing.") % (current_line_num,))
                        if not destination_vals:
                            errors.append(_("Line %s: An expense account is set while the destination code (mandatory) is missing.") % (current_line_num,))
                        if not funding_pool_vals:
                            errors.append(_("Line %s: An expense account is set while the funding pool code (mandatory) is missing.") % (current_line_num,))
                        if isinstance(percentage_vals, list):
                            _check_col_length(percentage_vals, cost_center_vals, destination_vals, funding_pool_vals, current_line_num, errors)
                            _check_percent_values(percentage_vals, current_line_num, errors)
                        # If AD is filled - write on each line the AD on the import file. Remove from header.

                        cc_ids, fp_ids, dest_ids = [], [], []
                        for cc_code in cost_center_vals:
                            cc_id = aac_obj.search(cr, uid,[('code', '=', cc_code),('category', '=', 'OC'),
                                                         ('type', '!=', 'view')], context=context)
                            if not cc_id:
                                errors.append(_("Line %s: the cost center %s doesn't exist.") % (current_line_num, cc_code))
                            else:
                                cc_ids.append(cc_id[0])
                        for fp_code in funding_pool_vals:
                            fp_id = aac_obj.search(cr, uid, [('code', '=', fp_code),
                                                             ('category', '=', 'FUNDING'),
                                                             ('type', '!=', 'view')], context=context)
                            if not fp_id:
                                errors.append(_("Line %s: the funding pool %s doesn't exist.") % (current_line_num, fp_code))
                            else:
                                fp_ids.append(fp_id[0])
                        for dest_code in destination_vals:
                            dest_id = aac_obj.search(cr, uid, [('code', '=', dest_code),
                                                               ('category', '=', 'DEST'),
                                                               ('type', '!=', 'view')], context=context)
                            if not dest_id:
                                errors.append(_("Line %s: the destination %s doesn't exist.") % (current_line_num, dest_code))
                            else:
                                dest_ids.append(dest_id[0])

                        current_ad =  invoice_line_obj.browse(cr, uid, invoice_line_ids[0],fields_to_fetch=['analytic_distribution_id'], context=context).analytic_distribution_id

                        # create a new AD if diff from current AD on line
                        if not current_ad or _is_ad_diff(current_ad, cc_ids=cc_ids, dest_ids=dest_ids, fp_ids=fp_ids, percentages=percentage_vals):
                            distrib_id = ana_obj.create(cr, uid, {'name': 'Line Distribution Import'}, context=context)
                            for i, percentage in enumerate(percentage_vals):
                                ad_state, ad_error = ana_obj.analytic_state_from_info(cr, uid, account.id, dest_ids[i], cc_ids[i], fp_ids[i],
                                                                                      posting_date=checking_date,
                                                                                      document_date=invoice.document_date,
                                                                                      check_analytic_active=True,
                                                                                      context=context)
                                if ad_state != 'valid':
                                    ad_errors.append(_("Line %s: %s/%s/%s %s" ) % (current_line_num,
                                                                                   cost_center_vals[i],
                                                                                   destination_vals[i],
                                                                                   funding_pool_vals[i], ad_error))

                                ad_vals = {'distribution_id': distrib_id,
                                           'percentage': percentage,
                                           'currency_id': currency_ids[0],
                                           'destination_id': dest_ids[i],
                                           'analytic_id': cc_ids[i]}

                                self.pool.get('cost.center.distribution.line').create(cr, uid, ad_vals, context=context)

                                ad_vals.update({'analytic_id': fp_ids[i], 'cost_center_id': cc_ids[i]})
                                self.pool.get('funding.pool.distribution.line').create(cr, uid, ad_vals, context=context)

                            vals['analytic_distribution_id'] = distrib_id

                            if current_ad:
                                ana_obj.unlink(cr, uid, [current_ad.id], context=context)

                    # update the line
                    invoice_line_obj.write(cr, uid, invoice_line_ids[0], vals, context=context)
                    # update the percent
                    if current_line_num == nb_rows:
                        self.write(cr, uid, [wiz.id], {'progression': lines_percent}, context)
                    elif current_line_num % 5 == 0:  # refresh every 5 lines
                        self.write(cr, uid, [wiz.id],
                                   {'progression': header_percent + (current_line_num / float(nb_rows) * (lines_percent - header_percent))},
                                   context)
            wiz_state = 'done'
            # cancel the process in case of errors
            if errors:
                cr.rollback()
                message = _('Import FAILED.')
                # delete old errors and create new ones
                error_ids = errors_obj.search(cr, uid, [], context)
                if error_ids:
                    errors_obj.unlink(cr, uid, error_ids, context)
                for e in errors:
                    errors_obj.create(cr, uid, {'wizard_id': wiz.id, 'name': e}, context)
                wiz_state = 'error'
            # if it's AD error, handle it separately to allow import invalid AD combination
            elif ad_errors:
                message = _('Import successful but with analytic distribution invalid combination.')
                # delete old errors and create new ones
                error_ids = errors_obj.search(cr, uid, [], context)
                if error_ids:
                    errors_obj.unlink(cr, uid, error_ids, context)
                for e in ad_errors:
                    errors_obj.create(cr, uid, {'wizard_id': wiz.id, 'name': e}, context)
                wiz_state = 'ad_error'
            else:
                message = _('Import successful.')
            # 100% progression
            self.write(cr, uid, ids, {'message': message, 'state': wiz_state, 'progression': 100.0}, context)
            cr.commit()
            cr.close(True)
        except osv.except_osv as osv_error:
            logging.getLogger('account.invoice.import').warn('OSV Exception', exc_info=True)
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occurred: %s: %s") %
                                      (osv_error.name, osv_error.value), 'state': 'done', 'progression': 100.0})
            cr.close(True)
        except Exception as e:
            logging.getLogger('account.invoice.import').warn('Exception', exc_info=True)
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occurred: %s") %
                                      (e and e.args and e.args[0] or ''), 'state': 'done', 'progression': 100.0})
            cr.close(True)
        return True

    def button_validate(self, cr, uid, ids, context=None):
        """
        Starts thread and returns the wizard with the state "inprogress"
        """
        if context is None:
            context = {}
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        self.write(cr, uid, ids, {'state': 'inprogress'}, context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.import',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids[0],
            'context': context,
            'target': 'new',
        }

    def button_update(self, cr, uid, ids, context=None):
        """
        Updates the view to follow the progression
        """
        return False

    def button_refresh_invoice(self, cr, uid, ids, context=None):
        """
        Closes the wizard and refreshes the invoice view
        """
        return {'type': 'ir.actions.act_window_close'}


account_invoice_import()


class account_invoice_import_errors(osv.osv_memory):
    _name = 'account.invoice.import.errors'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('account.invoice.import', "Wizard", required=True, readonly=True),
    }


account_invoice_import_errors()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
