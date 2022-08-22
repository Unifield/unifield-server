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
from datetime import datetime
import threading
import pooler
import logging
import tools
import re


class account_cv_import(osv.osv_memory):
    _name = 'account.cv.import'
    _inherit = 'account.invoice.import'

    _columns = {
        'error_ids': fields.one2many('account.cv.import.errors', 'wizard_id', "Errors", readonly=True),
        'commit_id': fields.many2one('account.commitment', 'Commitment Voucher', required=True, readonly=True),
    }

    def create(self, cr, uid, vals, context=None):
        """
        Creation of the wizard using the realUid to allow the process for the non-admin users
        """
        real_uid = hasattr(uid, 'realUid') and uid.realUid or uid
        return super(account_cv_import, self).create(cr, real_uid, vals, context=context)

    def _import(self, dbname, uid, ids, context=None):
        """
        Checks file data, and either updates the lines or displays the errors found
        """
        if context is None:
            context = {}
        cr = pooler.get_db(dbname).cursor()
        errors = []
        ad_errors = []
        cv_obj = self.pool.get('account.commitment')
        cv_line_obj = self.pool.get('account.commitment.line')
        currency_obj = self.pool.get('res.currency')
        partner_obj = self.pool.get('res.partner')
        account_obj = self.pool.get('account.account')
        product_obj = self.pool.get('product.product')
        import_cell_data_obj = self.pool.get('import.cell.data')
        errors_obj = self.pool.get('account.cv.import.errors')
        ana_obj = self.pool.get('analytic.distribution')
        aac_obj = self.pool.get('account.analytic.account')
        po_obj = self.pool.get('purchase.order')

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
                cv = wiz.commit_id
                if cv.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('The import is allowed only in Draft state.'))
                rows = content.getRows()
                nb_rows = len([x for x in content.getRows()])
                self.write(cr, uid, [wiz.id], {'message': _('Checking header…'), 'progression': 5.00}, context)
                # indexes of the file columns:
                cols = {
                    'cv_line': 0,
                    'line_number': 1,
                    'account': 2,
                    'initial_amount': 3,
                    'left_amount': 4,
                    'analytic_distribution': 5,
                    'cost_center': 6,
                    'destination': 7,
                    'funding_pool': 8,
                }
                # number of the first line in the file containing data (not header)
                base_num = 12
                rows.next()  # journal is ignored
                number_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    name = number_line[1]
                except IndexError as e:
                    raise osv.except_osv(_('Warning'), _('No CV number found.'))
                cv_ids = cv_obj.search(cr, uid, [('name', '=', name)], context=context)
                if not cv_ids:
                    raise osv.except_osv(_('Error'), _("CV with number: %s not found.") % (name or '',))
                commitment_date_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    commitment_date = commitment_date_line[1] or False
                except IndexError as e:
                    commitment_date = False
                if commitment_date:
                    try:
                        commitment_date = commitment_date.strftime('%Y-%m-%d')
                    except AttributeError as e:
                        raise osv.except_osv(_('Warning'), _("The commitment date has a wrong format."))
                currency_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    currency_name = currency_line[1]
                except IndexError as e:
                    raise osv.except_osv(_('Warning'), _('No currency found.'))
                currency_ids = currency_obj.search(cr, uid, [('name', '=', currency_name), ('active', '=', True)],
                                                   limit=1, context=context)
                if not currency_ids:
                    raise osv.except_osv(_('Error'), _("Currency %s not found or inactive.") % (currency_name or '',))
                rows.next()  # description is ignored
                partner_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    partner_name = partner_line[1]
                except IndexError as e:
                    raise osv.except_osv(_('Warning'), _('No supplier found.'))
                partner_ids = partner_obj.search(cr, uid, [('name', '=', partner_name), ('active', '=', True)],
                                                 context=context)
                if not partner_ids:
                    raise osv.except_osv(_('Error'), _("Supplier %s not found or inactive.") % (partner_name or '',))
                po_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    po_name = po_line[1]
                except IndexError as e:
                    raise osv.except_osv(_('Warning'), _('No source document found.'))
                po_ids = po_obj.search(cr, uid, [('name', '=', po_name)], context=context)
                if not po_ids:
                    raise osv.except_osv(_('Error'), _("Source document %s not found or inactive.") % (po_name or '',))
                rows.next()  # period is ignored
                type_line = import_cell_data_obj.get_line_values(cr, uid, ids, rows.next())
                try:
                    type_desc = type_line[1]
                except IndexError as e:
                    raise osv.except_osv(_('Warning'), _('No CV type found.'))
                cv_types = cv_obj.get_cv_type(cr, uid, context=context)
                type_list = [type_name for (type_code, type_name) in cv_types]
                if type_desc not in type_list:
                    raise osv.except_osv(_('Error'), _("CV type '%s' not found or doesn't exist.") % (type or '',))
                type_dct = dict((x, y) for x, y in cv_types)
                type = list(type_dct.keys())[list(type_dct.values()).index(type_desc)]
                cv_dom = [('id', '=', cv.id), ('name', '=', name), ('currency_id', '=', currency_ids[0]),
                          ('partner_id', '=', partner_ids[0]), ('purchase_id', '=', po_ids[0]), ('type', '=', type)]
                if not cv_obj.search_exist(cr, uid, cv_dom, context=context):
                    raise osv.except_osv(_('Warning'),
                                         _("The combination \"CV Number, Currency, Supplier, Source Document and CV Type\" of the imported file "
                                           "doesn't match with the current commitment voucher."))
                # ignore: empty line, line with titles
                for i in range(2):
                    rows.next()
                header_percent = 10  # percentage of the process reached AFTER having checked the header
                self.write(cr, uid, [wiz.id], {'message': _('Checking lines…'), 'progression': header_percent}, context)
                lines_percent = 99  # % of the process to be reached AFTER having checked and updated the lines
                # check the lines
                for num, r in enumerate(rows):
                    current_line_num = num + base_num
                    vals = {}
                    line = import_cell_data_obj.get_line_values(cr, uid, ids, r)
                    line.extend([False for i in range(len(cols) - len(line))])
                    # get the data
                    cv_line_product = line[cols['cv_line']]
                    line_number = line[cols['line_number']]
                    account_code = line[cols['account']] and tools.ustr(line[cols['account']])
                    initial_amount = line[cols['initial_amount']] or 0.0
                    left_amount = line[cols['left_amount']] or 0.0
                    analytic_distribution_type = line[cols['analytic_distribution']] and tools.ustr(line[cols['analytic_distribution']])
                    cost_center_code = line[cols['cost_center']] and tools.ustr(line[cols['cost_center']])
                    destination_code = line[cols['destination']] and tools.ustr(line[cols['destination']])
                    funding_pool_code = line[cols['funding_pool']] and tools.ustr(line[cols['funding_pool']])

                    if analytic_distribution_type and analytic_distribution_type.strip() == 'SPLIT':
                        continue  # if AD is SPLIT, skip the line and check the next one

                    if not line_number:
                        errors.append(_('Line %s: the line number is missing.') % (current_line_num,))
                        continue
                    try:
                        line_number = int(line_number)
                    except ValueError as e:
                        errors.append(_("Line %s: the line number format is incorrect.") % (current_line_num,))
                        continue
                    cv_line_dom = [('commit_id', '=', cv.id), ('line_number', '=', line_number)]
                    cv_line_ids = cv_line_obj.search(cr, uid, cv_line_dom, limit=1, context=context)
                    if not cv_line_ids:
                        errors.append(_("Line %s: the line number %s doesn't exist in the commitment voucher.") % (current_line_num, line_number))
                        continue
                    if not account_code:
                        errors.append(_("Line %s: empty account code field is not allowed.") % (current_line_num,))
                        continue
                    if not re.search(r'\A\d{5}\Z', account_code):
                        errors.append(_("Line %s: Wrong format of the account code %s: it must have exactly 5 digits.") % (current_line_num, account_code))
                        continue
                    account_ids = account_obj.search(cr, uid, [('code', '=', account_code)], limit=1, context=context)
                    if not account_ids:
                        errors.append(_("Line %s: the account %s does not exist or inactive or mistyped.") % (current_line_num, account_code))
                        continue
                    account = account_obj.browse(cr, uid, account_ids[0], context=context)
                    checking_date = commitment_date or datetime.now().strftime('%Y-%m-%d')
                    if checking_date < account.activation_date or (account.inactivation_date and checking_date >= account.inactivation_date):
                        errors.append(_("Line %s: the account %s is inactive.") % (current_line_num, account_code))
                        continue

                    vals['account_id'] = account.id
                    try:
                        initial_amount = float(initial_amount)
                    except ValueError as e:
                        errors.append(_("Line %s: the initial amount format is incorrect.") % (current_line_num,))
                        continue
                    cv_line_dom.append(('initial_amount', '=', initial_amount))
                    try:
                        left_amount = float(left_amount)
                    except ValueError as e:
                        errors.append(_("Line %s: the left amount format is incorrect.") % (current_line_num,))
                        continue
                    cv_line_dom.append(('amount', '=', left_amount))

                    if not cv_line_product:
                        errors.append(_('Line %s: the line product code is missing.') % (current_line_num,))
                        continue
                    prod_ids = product_obj.search(cr, uid, [('default_code', '=', cv_line_product)], limit=1, context=context)
                    if not prod_ids:
                        errors.append(_("Line %s: the product %s doesn't exist.") % (current_line_num, cv_line_product))
                        continue
                    cv_line_dom.append(('line_product_id', '=', prod_ids[0]))

                    cv_line_ids = cv_line_obj.search(cr, uid, cv_line_dom, limit=1, context=context)
                    if not cv_line_ids:
                        errors.append(_("Line %s: the combination product code: %s, line number: %s, initial amount: %s,"
                                        "left amount: %s  doesn't exist in the commitment voucher.")
                                      % (current_line_num, cv_line_product, line_number, initial_amount, left_amount))
                        continue

                    if analytic_distribution_type and analytic_distribution_type.strip() in ('100%', '100'):
                        if account.user_type and account.user_type.code == 'expense' and (not cost_center_code or not destination_code or not funding_pool_code):
                            errors.append(_("Line %s: An expense account is set while the analytic distribution values (mandatory) are missing.") % (current_line_num,))
                            continue
                        # If the AD is left blank, remove AD, including from header
                        if account.user_type and account.user_type.code != 'expense' and (not cost_center_code or not destination_code or not funding_pool_code):
                            if cv.analytic_distribution_id:
                                ana_obj.unlink(cr, uid, [cv.analytic_distribution_id.id], context=context)  # delete header AD if any
                            il_ad = cv_line_obj.browse(cr, uid, cv_line_ids[0], fields_to_fetch=['analytic_distribution_id'], context=context)
                            if il_ad and il_ad.analytic_distribution_id:
                                ana_obj.unlink(cr, uid, [il_ad.analytic_distribution_id.id], context=context)  # delete line level AD if any
                                vals['analytic_distribution_id'] = False
                        # If AD is filled - write on each line the AD on the import file. Remove from header.
                        if cost_center_code and destination_code and funding_pool_code:
                            ad_vals = {}
                            distrib_id = ana_obj.create(cr, uid, {'name': 'Line Distribution Import'}, context=context)
                            cc_ids = aac_obj.search(cr, uid, [('code', '=', cost_center_code),('category', '=', 'OC'), ('filter_active', '=', True)],
                                                    limit=1, context=context)
                            if not cc_ids:
                                errors.append(_("Line %s: the cost center %s doesn't exist or is inactive.") % (current_line_num, cost_center_code))
                                continue
                            fp_ids = aac_obj.search(cr, uid, [('code', '=', funding_pool_code), ('category', '=', 'FUNDING'),
                                                              ('filter_active', '=', True)], limit=1, context=context)
                            if not fp_ids:
                                errors.append(_("Line %s: the funding pool %s doesn't exist or is inactive.") % (current_line_num, funding_pool_code))
                                continue
                            dest_ids = aac_obj.search(cr, uid, [('code', '=', destination_code), ('category', '=', 'DEST'),
                                                                ('filter_active', '=', True)], limit=1, context=context)
                            if not dest_ids:
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
                            # delete header AD if any
                            if cv.analytic_distribution_id:
                                ana_obj.unlink(cr, uid, [cv.analytic_distribution_id.id], context=context)

                    # update the line
                    vals['analytic_distribution_id'] = distrib_id
                    cv_line_obj.write(cr, uid, cv_line_ids, vals, context=context)
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
            logging.getLogger('account.cv.import').warn('OSV Exception', exc_info=True)
            cr.rollback()
            self.write(cr, uid, ids, {'message': _("An error occurred: %s: %s") %
                                      (osv_error.name, osv_error.value), 'state': 'done', 'progression': 100.0})
            cr.close(True)
        except Exception as e:
            logging.getLogger('account.cv.import').warn('Exception', exc_info=True)
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
            'res_model': 'account.cv.import',
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

    def button_refresh_cv(self, cr, uid, ids, context=None):
        """
        Closes the wizard and refreshes the CV view
        """
        return {'type': 'ir.actions.act_window_close'}


account_cv_import()


class account_cv_import_errors(osv.osv_memory):
    _name = 'account.cv.import.errors'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('account.cv.import', "Wizard", required=True, readonly=True),
    }


account_cv_import_errors()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
