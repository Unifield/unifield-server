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
from openpyxl import load_workbook
from base64 import b64decode
from io import BytesIO
import threading
import pooler
import logging
import tools
from .. import ACCRUAL_LINES_COLUMNS_FOR_IMPORT


class msf_accrual_import(osv.osv_memory):
    _name = 'msf.accrual.import'

    _columns = {
        'file': fields.binary(string="File", filters='*.xls*', required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'filename_template': fields.char('Templates', size=256),
        'progression': fields.float(string="Progression", readonly=True),
        'message': fields.char(string="Message", size=256, readonly=True),
        'state': fields.selection([('draft', 'Created'), ('inprogress', 'In Progress'), ('error', 'Error'), ('ad_error', 'AD Error'), ('done', 'Done')],
                                  string="State", readonly=True, required=True),
        'error_ids': fields.one2many('msf.accrual.import.errors', 'wizard_id', "Errors", readonly=True),
        'accrual_id': fields.many2one('msf.accrual.line', 'Accrual Line', required=True, readonly=True),
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
        return super(msf_accrual_import, self).create(cr, real_uid, vals, context=context)

    def _check_col_length(self, percent_col, cc_col, dest_col, fp_col, line_num, errors, context=None):
        if context is None:
            context = {}
        return self.pool.get('account.invoice.import')._check_col_length(percent_col, cc_col, dest_col, fp_col, line_num, errors, context=context)

    def _check_percent_values(self, percent_col, line_num, errors, context= None):
        '''
        Check if the Percent Column values adds up to exactly 100
        '''
        if context is None:
            context = {}
        return self.pool.get('account.invoice.import')._check_percent_values(percent_col, line_num, errors, context=context)

    def check_header_colnames(self, colnames, context=None):
        if context is None:
            context = {}
        header_names = [_(f) for f in ACCRUAL_LINES_COLUMNS_FOR_IMPORT]
        error_message = _('The header column names should be: %s') % (', '.join(header_names))
        if len(header_names) != len(colnames):
            raise osv.except_osv(_('Warning'), error_message)
        for i, col in enumerate(colnames):
            if header_names[i] != col:
                raise osv.except_osv(_('Warning'), error_message)
        return True

    def _import(self, dbname, uid, ids, context=None):
        """
        Checks file data, and either creates the lines or displays the errors found
        """
        if context is None:
            context = {}
        cr = pooler.get_db(dbname).cursor()
        errors = []
        ad_errors = []
        accounts = {}
        ccs = {}
        dests = {}
        fps = {}
        accrual_line_expense_obj = self.pool.get('msf.accrual.line.expense')
        account_obj = self.pool.get('account.account')
        errors_obj = self.pool.get('msf.accrual.import.errors')
        ana_obj = self.pool.get('analytic.distribution')
        aac_obj = self.pool.get('account.analytic.account')

        try:
            for wiz in self.browse(cr, uid, ids, context):
                self.write(cr, uid, [wiz.id], {'message': _('Checking file…'), 'progression': 1.00}, context)
                if not wiz.file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))

                wb = load_workbook(filename=BytesIO(b64decode(wiz.file)), read_only=True)
                sheet = wb.active

                rows = tuple(sheet.rows)
                nb_rows = len(rows)

                accrual = wiz.accrual_id
                if accrual.state != 'draft':
                    raise osv.except_osv(_('Warning'), _('The import is allowed only in Draft state.'))

                # indexes of the file columns:
                cols = {
                    'description': 0,
                    'reference': 1,
                    'expense_account': 2,
                    'accrual_amount': 3,
                    'percentage': 4,
                    'cost_center': 5,
                    'destination': 6,
                    'funding_pool': 7,
                }

                header_percent = 10
                self.write(cr, uid, [wiz.id], {'message': _('Checking lines…'), 'progression': header_percent}, context)
                lines_percent = 99
                # check the lines
                for line_num, row in enumerate(rows):
                    if line_num == 0:
                        header = [x.value for x in row]
                        self.check_header_colnames(header, context=context)
                        continue
                    vals = {'line_number': line_num, 'accrual_line_id': wiz.accrual_id.id}
                    # get the data
                    description = row[cols['description']].value and tools.ustr(row[cols['description']].value)
                    reference = row[cols['reference']].value and tools.ustr(row[cols['reference']].value)
                    expense_account_code = row[cols['expense_account']].value and tools.ustr(row[cols['expense_account']].value)
                    accrual_amount = row[cols['accrual_amount']].value or 0.0
                    percentage_vals = row[cols['percentage']].value and \
                        (len(tools.ustr(row[cols['percentage']].value).split(';')) > 0 and
                         tools.ustr(row[cols['percentage']].value).split(';'))
                    cost_center_vals = row[cols['cost_center']].value and \
                        (len(tools.ustr(row[cols['cost_center']].value).split(';')) > 0 and
                         tools.ustr(row[cols['cost_center']].value).split(';'))
                    destination_vals = row[cols['destination']].value and \
                        (len(tools.ustr(row[cols['destination']].value).split(';')) > 0 and
                         tools.ustr(row[cols['destination']].value).split(';'))
                    funding_pool_vals = row[cols['funding_pool']].value and \
                        (len(tools.ustr(row[cols['funding_pool']].value).split(';')) > 0 and
                         tools.ustr(row[cols['funding_pool']].value).split(';'))
                    if not description:
                        errors.append(_("Line %s: the description (mandatory) is missing.") % (line_num,))
                    else:
                        vals['description'] = description
                    vals['reference'] = reference or ''
                    expense_account = False
                    if not expense_account_code:
                        errors.append(_("Line %s: the expense account (mandatory) is missing.") % (line_num,))
                    else:
                        if not accounts.get(expense_account_code, False):
                            account_ids = account_obj.search(cr, uid, [('code', '=', expense_account_code), ('restricted_area', '=', 'accruals')], limit=1, context=context)
                            if not account_ids:
                                errors.append(_("Line %s: the account %s doesn't exist or isn't allowed for accrual expense lines.") % (line_num, expense_account_code))
                            else:
                                expense_account = account_obj.browse(cr, uid, account_ids[0], context=context)
                                accounts[expense_account_code] = expense_account.id
                        vals['expense_account_id'] = accounts.get(expense_account_code)
                    if not accrual_amount:
                        errors.append(_("Line %s: the accrual amount booking (mandatory) is missing.") % (line_num,))
                    else:
                        vals['accrual_amount'] = accrual_amount
                    if not percentage_vals:
                        errors.append(_("Line %s: The percentages are mandatory") % line_num)
                    if not cost_center_vals:
                        errors.append(_("Line %s: Cost center codes (mandatory) are missing.") % (line_num,))
                    if not destination_vals:
                        errors.append(_("Line %s: Destination codes (mandatory) are missing.") % (line_num,))
                    if not funding_pool_vals:
                        errors.append(_("Line %s: Funding pool codes (mandatory) are missing.") % (line_num,))
                    if percentage_vals and cost_center_vals and destination_vals and funding_pool_vals:
                        if isinstance(percentage_vals, list):
                            self._check_col_length(percentage_vals, cost_center_vals, destination_vals, funding_pool_vals, line_num, errors,context=context)
                            self._check_percent_values(percentage_vals, line_num, errors, context=context)
                    cc_ids, fp_ids, dest_ids = [], [], []
                    if cost_center_vals:
                        for cc_code in cost_center_vals:
                            if not ccs.get(cc_code, False):
                                cc_id = aac_obj.search(cr, uid, [('code', '=', cc_code), ('category', '=', 'OC'), ('type', '!=', 'view')], context=context)
                                if not cc_id:
                                    errors.append(_("Line %s: the cost center %s doesn't exist.") % (line_num, cc_code))
                                else:
                                    ccs[cc_code] = cc_id[0]
                            cc_ids.append(ccs.get(cc_code))
                    if funding_pool_vals:
                        for fp_code in funding_pool_vals:
                            if not fps.get(fp_code, False):
                                fp_id = aac_obj.search(cr, uid, [('code', '=', fp_code), ('category', '=', 'FUNDING'), ('type', '!=', 'view')], context=context)
                                if not fp_id:
                                    errors.append(_("Line %s: the funding pool %s doesn't exist.") % (line_num, fp_code))
                                else:
                                    fps[fp_code] = fp_id[0]
                            fp_ids.append(fps.get(fp_code, False))
                    if destination_vals:
                        for dest_code in destination_vals:
                            if not dests.get(dest_code, False):
                                dest_id = aac_obj.search(cr, uid, [('code', '=', dest_code), ('category', '=', 'DEST'), ('type', '!=', 'view')], context=context)
                                if not dest_id:
                                    errors.append(_("Line %s: the destination %s doesn't exist.") % (line_num, dest_code))
                                else:
                                    dests[dest_code] = dest_id[0]
                            dest_ids.append(dests.get(dest_code, False))
                    if not(cc_ids and fp_ids and dest_ids and percentage_vals and accounts.get(expense_account_code, False) and accrual_amount and description and not errors):
                        continue

                    distrib_id = ana_obj.create(cr, uid, {'name': 'Line Distribution Import'}, context=context)
                    for i, percentage in enumerate(percentage_vals):
                        ad_state, ad_error = ana_obj.analytic_state_from_info(cr, uid, accounts.get(expense_account_code),
                                                                              dest_ids[i], cc_ids[i], fp_ids[i],
                                                                              posting_date=accrual.date,
                                                                              document_date=accrual.document_date,
                                                                              check_analytic_active=True,
                                                                              context=context)
                        if ad_state != 'valid':
                            ad_errors.append(_("Line %s: %s/%s/%s %s") % (line_num,
                                                                          cost_center_vals[i],
                                                                          destination_vals[i],
                                                                          funding_pool_vals[i], ad_error))

                        ad_vals = {'distribution_id': distrib_id,
                                   'percentage': percentage,
                                   'currency_id': wiz.accrual_id.currency_id.id,
                                   'destination_id': dest_ids[i],
                                   'analytic_id': cc_ids[i]}

                        self.pool.get('cost.center.distribution.line').create(cr, uid, ad_vals, context=context)

                        ad_vals.update({'analytic_id': fp_ids[i], 'cost_center_id': cc_ids[i]})
                        self.pool.get('funding.pool.distribution.line').create(cr, uid, ad_vals, context=context)

                    vals['analytic_distribution_id'] = distrib_id

                    # create the accrual expense line
                    accrual_line_expense_obj.create(cr, uid, vals, context=context)
                    # update the percent
                    if line_num == nb_rows:
                        self.write(cr, uid, [wiz.id], {'progression': lines_percent}, context)
                    elif line_num % 5 == 0:  # refresh every 5 lines
                        self.write(cr, uid, [wiz.id],
                                   {'progression': header_percent + (line_num / float(nb_rows) * (lines_percent - header_percent))},
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
            'res_model': 'msf.accrual.import',
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

    def button_refresh_accrual(self, cr, uid, ids, context=None):
        """
        Closes the wizard and refreshes the accrual view
        """
        return {'type': 'ir.actions.act_window_close'}


msf_accrual_import()


class msf_accrual_import_errors(osv.osv_memory):
    _name = 'msf.accrual.import.errors'

    _columns = {
        'name': fields.text("Description", readonly=True, required=True),
        'wizard_id': fields.many2one('msf.accrual.import', "Wizard", required=True, readonly=True),
    }


msf_accrual_import_errors()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
