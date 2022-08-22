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
                    'analytic_distribution': 7,
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
                    distrib_id = False
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
                    analytic_distribution_type = line[cols['analytic_distribution']] and tools.ustr(line[cols['analytic_distribution']])
                    cost_center_code = line[cols['cost_center']] and tools.ustr(line[cols['cost_center']])
                    destination_code = line[cols['destination']] and tools.ustr(line[cols['destination']])
                    funding_pool_code = line[cols['funding_pool']] and tools.ustr(line[cols['funding_pool']])

                    if not line_number:
                        errors.append(_('Line %s: the line number is missing.') % (current_line_num,))
                        continue
                    try:
                        line_number = int(line_number)
                    except ValueError, e:
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
                    except ValueError, e:
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
                        except ValueError, e:
                            errors.append(_("Line %s: the quantity format is incorrect.") % (current_line_num,))
                            continue
                        vals['quantity'] = quantity

                    if not description:
                        errors.append(_("Line %s: the description (mandatory) is missing.") % (current_line_num,))
                        continue
                    vals['name'] = description
                    vals['note'] = notes
                    if analytic_distribution_type and analytic_distribution_type.strip() in ('100%', '100'):
                        if account.user_type and account.user_type.code == 'expense' and (not cost_center_code or not destination_code or not funding_pool_code):
                            errors.append(_("Line %s: An expense account is set while the analytic distribution values (mandatory) are missing.") % (current_line_num,))
                            continue
                        # If the AD is left blank, remove AD, including from header
                        if account.user_type and account.user_type.code != 'expense' and (not cost_center_code or not destination_code or not funding_pool_code):
                            if invoice.analytic_distribution_id:
                                ana_obj.unlink(cr, uid, [invoice.analytic_distribution_id.id], context=context)  # delete header AD if any
                                # invoice.analytic_distribution_id = False
                            il_ad = invoice_line_obj.browse(cr, uid, invoice_line_ids[0],fields_to_fetch=['analytic_distribution_id'], context=context)
                            if il_ad and il_ad.analytic_distribution_id:
                                ana_obj.unlink(cr, uid, [il_ad.analytic_distribution_id.id], context=context)  # delete line level AD if any
                                vals['analytic_distribution_id'] = False
                        # If AD is filled - write on each line the AD on the import file. Remove from header.
                        if cost_center_code and destination_code and funding_pool_code:
                            ad_vals = {}
                            distrib_id = ana_obj.create(cr, uid, {'name': 'Line Distribution Import'}, context=context)
                            cc_ids = aac_obj.search(cr, uid,[('code', '=', cost_center_code),('category', '=', 'OC')],
                                                             limit=1, context=context)
                            if cc_ids:
                                cc = aac_obj.browse(cr, uid, cc_ids[0], context=context)
                            if not cc_ids or cc.date_start >= checking_date or (cc.date and cc.date < checking_date):
                                errors.append(_("Line %s: the cost center %s doesn't exist or is inactive.") % (current_line_num, cost_center_code))
                                continue
                            fp_ids = aac_obj.search(cr, uid, [('code', '=', funding_pool_code), ('category', '=', 'FUNDING')], limit=1, context=context)
                            if fp_ids:
                                fp = aac_obj.browse(cr, uid, fp_ids[0], context=context)
                            if not fp_ids or fp.date_start >= checking_date or (fp.date and fp.date < checking_date):
                                errors.append(_("Line %s: the funding pool %s doesn't exist or is inactive.") % (current_line_num, funding_pool_code))
                                continue
                            dest_ids = aac_obj.search(cr, uid, [('code', '=', destination_code), ('category', '=', 'DEST')], limit=1, context=context)
                            if dest_ids:
                                dest = aac_obj.browse(cr, uid, dest_ids[0], context=context)
                            if not dest_ids or dest.date_start >= checking_date or (dest.date and dest.date < checking_date):
                                errors.append(_("Line %s: the destination %s doesn't exist or is inactive.") % (current_line_num, destination_code))
                                continue
                            # check destination and cc compatibility
                            if not ana_obj.check_dest_cc_compatibility(cr, uid, dest_ids[0], cc_ids[0], context=context):
                                ad_errors.append(_("Line %s: the combination %s/%s is not valid.") % (current_line_num, destination_code, cost_center_code))
                            # check funding pool and analytic account compatibility
                            if not ana_obj.check_fp_acc_dest_compatibility(cr, uid, fp_ids[0], account.id, dest_ids[0], context=context):
                                ad_errors.append(_("Line %s: the combination %s/%s is not valid.") % (current_line_num, funding_pool_code, account_code))
                            # check funding pool and cc compatibility
                            if not ana_obj.check_fp_cc_compatibility(cr, uid, fp_ids[0], cc_ids[0], context=context):
                                ad_errors.append(_("Line %s: the combination %s/%s is not valid.") % (current_line_num, funding_pool_code, cost_center_code))

                            ad_vals.update({'distribution_id': distrib_id, 'percentage': 100.0, 'currency_id': currency_ids[0],
                                            'destination_id': dest_ids[0], 'cost_center_id': cc_ids[0],
                                            'funding_pool_id': fp_ids[0]})
                            # Create funding pool lines
                            ad_vals.update({'analytic_id': fp_ids[0]})
                            self.pool.get('funding.pool.distribution.line').create(cr, uid, ad_vals)
                            # Then cost center lines
                            ad_vals.update({'analytic_id': ad_vals.get('cost_center_id'), })
                            self.pool.get('cost.center.distribution.line').create(cr, uid, ad_vals)
                            vals['analytic_distribution_id'] = distrib_id
                            # delete header AD if any
                            if invoice.analytic_distribution_id:
                                ana_obj.unlink(cr, uid, [invoice.analytic_distribution_id.id], context=context)

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
