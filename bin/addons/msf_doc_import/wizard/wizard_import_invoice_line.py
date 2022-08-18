# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2017 MSF, TeMPO Consulting.
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
import threading
import logging
import pooler
from osv import osv, fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from base import currency_date
from account_override import ACCOUNT_RESTRICTED_AREA
import time
from msf_doc_import.wizard import ACCOUNT_INVOICE_COLUMNS_FOR_IMPORT as columns_for_account_line_import


class wizard_import_invoice_line(osv.osv_memory):
    _name = 'wizard.import.invoice.line'
    _description = 'Import Invoice Lines from Excel sheet'

    def _get_bool_values(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file': fields.binary(
            string='File to import',
            required=True, readonly=True,
            states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'invoice_id': fields.many2one(
            'account.invoice', required=True, string="Account Invoice"),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(
            _get_bool_values, method=True,
            type='boolean', store=False, readonly=True,
            string="Error at import"),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection(
            [('draft', 'Draft'),
             ('in_progress', 'In Progress'),
             ('done', 'Done')],
            string="State", required=True, readonly=True),
    }

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        if context is None:
            context = {}
        if not context.get('yml_test', False):
            cr = pooler.get_db(dbname).cursor()
        else:
            cr = dbname
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        invoice_line_obj = self.pool.get('account.invoice.line')
        account_id = False
        r_cc = False
        line_num = 0

        try:
            msf_fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        except ValueError:
            msf_fp_id = 0

        for wiz in self.browse(cr, uid, ids, context):
            self.ignore_lines, self.complete_lines, self.lines_to_correct, self.created_lines = 0, 0, 0, 0
            self.error_list = []
            error_log, self.message = '', ''
            header_index = context['header_index']
            template_col_count = len(header_index)
            mandatory_fields = ['Description', 'Account', 'Quantity', 'Unit Price']

            file_obj = SpreadsheetXML(xmlstring=base64.b64decode(wiz.file))
            row_iterator = file_obj.getRows()

            to_write = {}
            total_line_num = file_obj.getNbRows()
            if total_line_num <=1:
                self.error_list.append(_('No data found in the spreadhseet.'))
                percent_completed = 100
                break
            # ignore the header line
            next(row_iterator)

            def add_error(error):
                self.error_list.append(error)
                self.ignore_lines += 1

            def add_message(new_message):
                self.message += new_message
                self.ignore_lines += 1

            for line_num, row in enumerate(row_iterator, start=1):
                percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                # default values
                to_write = {
                    'invoice_id': wiz.invoice_id.id,
                    'name': False,
                    'account_id': False,
                    'price_unit': 1,
                    'quantity': 1,
                    'line_number': '',
                }
                col_count = len(row)
                if col_count != template_col_count:
                    add_message(_("Line %s: You should have exactly %s columns in this order: %s \n") % (
                        line_num, template_col_count,
                        ','.join(columns_for_account_line_import[1:])))
                    continue
                try:
                    line = self.pool.get('import.cell.data').get_line_values(cr, uid, ids, row)
                    missing_required = False
                    # check the required fields are present
                    for mandatory_field in mandatory_fields:
                        cell_nb = header_index[_(mandatory_field)]
                        if not line[cell_nb]:
                            add_error(_('Line %s. %s was not set. This field is mandatory.') % (line_num, _(mandatory_field)))
                            missing_required = True

                    if missing_required:
                        continue

                    ## Cell 0: Description
                    desc_value = line[header_index[_('Description')]]

                    ## Cell 1: Account
                    account_value = line[header_index[_('Account')]]
                    account_obj = self.pool.get('account.account')
                    account_ids = account_obj.search(cr, uid, [('code', '=', account_value)])
                    if not account_ids:
                        add_error(_('Line %s. Account %s not found!') % (line_num, account_value))
                        continue
                    account_id = account_ids[0]
                    account = account_obj.browse(cr, uid, account_id)
                    # like in US-2170, account of type donation are not allowed
                    if account.type_for_register == 'donation':
                        add_error(_('Line %s. Account %s is \'Donations\' type which is forbidden.') % (line_num, account_value))
                        continue

                    domain = [('id', '=', account_id)]
                    if context.get('intermission_type', False):
                        domain.extend(ACCOUNT_RESTRICTED_AREA['intermission_lines'])
                        error_domain = _("Line %s: Some restrictions prevent account %s to be used to import this line:\n"
                                         "- the account cannot be of type 'View'\n"
                                         "- account can not be set as 'Prevent correction on account codes'\n"
                                         "- 'Account Type' should be in ('expense', 'income', 'receivables')\n"
                                         "- 'P&L / BS Category' cannot be None.") % (line_num, account_value)
                    else:
                        domain.extend(ACCOUNT_RESTRICTED_AREA['invoice_lines'])
                        error_domain = _("Line %s: Some restrictions prevent account %s to be used to import this line:\n"
                                         "- the account cannot be of type 'View' or 'Liquidity'\n"
                                         "- account can not be set as 'Prevent correction on account codes'\n"
                                         "- 'Type for specific treatment' cannot be 'Donations'\n"
                                         "- 'Internal Type' should be different from 'Regular' OR 'Account Type' should be different from 'Stock'\n"
                                         "- 'Account Type' should be different from 'Expense' OR 'P&L / BS Category' not None."
                                         ) % (line_num, account_value)
                        # US-2170, special case for Stock Transfer Vouchers
                        is_stock_transfer_voucher = context.get('journal_type') == 'sale' and context.get('type') == 'out_invoice'
                        if is_stock_transfer_voucher:
                            domain.extend([('user_type_code', 'in', ['expense', 'income', 'receivables'])])
                            error_domain += _("\n- 'Account Type' should be in ('expense', 'income', 'receivables').")

                    if not account_obj.search_exist(cr, uid, domain, context=context):
                        add_error(error_domain)
                        continue

                    ## Cell 2: Quantity
                    quantity_value = line[header_index[_('Quantity')]]

                    ## Cell 3: Unit Price
                    unit_price_value = line[header_index[_('Unit Price')]]

                    # Check analytic axis only if account is analytic-a-holic
                    analytic_obj = self.pool.get('account.analytic.account')
                    if account.is_analytic_addicted:
                        # Check Destination
                        destination = line[header_index[_('Destination')]]
                        r_destination = False  # US-3022 Destination is not mandatory
                        if destination:
                            destination_ids = analytic_obj.search(cr, uid, [('category', '=', 'DEST'),
                                                                            '|', ('name', '=', destination),
                                                                            ('code', '=', destination)])
                            if destination_ids:
                                r_destination = destination_ids[0]

                        # Check Cost Center
                        cost_center = line[header_index[_('Cost Center')]]
                        r_cc = False  # US-3022 Cost Center is not mandatory
                        if cost_center:
                            # If necessary cast the CC into a string, otherwise the below search would crash
                            if not isinstance(cost_center, str):
                                cost_center = '%s' % (cost_center)
                            cc_ids = analytic_obj.search(cr, uid, [('category', '=', 'OC'),
                                                                   '|', ('name', '=', cost_center),
                                                                   ('code', '=', cost_center)])
                            if cc_ids:
                                r_cc = cc_ids[0]
                                # Check Cost Center type
                                cc = analytic_obj.browse(cr, uid, r_cc, context)
                                if cc.type == 'view':
                                    r_cc = False

                        # Check Funding Pool
                        r_fp = msf_fp_id
                        funding_pool = line[header_index[_('Funding Pool')]]
                        if funding_pool:
                            fp_ids = analytic_obj.search(cr, uid, [('category', '=', 'FUNDING'),
                                                                   '|', ('name', '=', funding_pool),
                                                                   ('code', '=', funding_pool)])
                            if fp_ids:
                                r_fp = fp_ids[0]

                        invoice = self.pool.get('account.invoice').browse(cr,
                                                                          uid, wiz.invoice_id.id, context=context)

                        if r_destination and r_cc:
                            distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context)
                            curr_date = currency_date.get_date(self, cr, invoice.document_date, invoice.date_invoice)
                            common_vals = {
                                'distribution_id': distrib_id,
                                'currency_id': invoice.currency_id.id,
                                'percentage': 100.0,
                                'date': invoice.date_invoice,
                                'source_date': curr_date,
                                'destination_id': r_destination,
                            }
                            common_vals.update({'analytic_id': r_cc})
                            self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                            common_vals.update({'analytic_id':r_fp, 'cost_center_id': r_cc})
                            self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                            to_write.update({'analytic_distribution_id': distrib_id})

                    to_write.update(
                        {
                            'name': desc_value,
                            'account_id': account_id,
                            'price_unit': unit_price_value,
                            'quantity': quantity_value,
                            'line_number': line_num,
                        }
                    )
                    invoice_line_obj.create(cr, uid, to_write, context=context)
                    self.created_lines += 1

                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    add_message(_("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value))
                    cr.rollback()
                    continue
                except UnicodeEncodeError as e:
                    add_message(_("""Line %s in the Excel file, uncaught error: %s\n""") % (line_num, e))
                    logging.getLogger('import purchase order').error('Error %s' % e)
                    cr.rollback()
                    continue
                except Exception as e:
                    add_message(_("""Line %s in the Excel file, uncaught error: %s\n""") % (line_num, e))
                    logging.getLogger('import purchase order').error('Error %s' % e)
                    cr.rollback()
                    continue
                else:
                    self.complete_lines += 1
                finally:
                    self.write(cr, uid, wiz.id, {'percent_completed':percent_completed})
                    if not context.get('yml_test', False):
                        cr.commit()

        wizard_vals = {'state': 'done'}
        try:
            error_log += '\n'.join(self.error_list)
            if error_log:
                error_log = _("Reported errors for ignored lines : \n") + error_log
            end_time = time.time()
            total_time = str(round(end_time-start_time, 1)) + _(' second(s)')
            final_message = _('''
Importation completed in %s!
# of imported lines : %s on %s lines (%s updated and %s created)
# of ignored lines: %s
# of lines to correct: %s
%s

%s
''') % (total_time, self.complete_lines, line_num, self.complete_lines-self.created_lines,self.created_lines, self.ignore_lines, self.lines_to_correct, error_log, self.message)
            wizard_vals['message'] = final_message
        except:
            cr.rollback()
        finally:
            # we reset the state of the PO to draft (initial state)
            self.write(cr, uid, ids, wizard_vals, context=context)
            if not context.get('yml_test', False):
                cr.commit()
                cr.close(True)

    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        if isinstance(ids, int):
            ids = [ids]
        wiz_common_import = self.pool.get('wiz.common.import')
        for wiz_read in self.read(cr, uid, ids, ['invoice_id', 'file']):
            invoice_id = wiz_read['invoice_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_read['file']))
                # iterator on rows
                reader_iterator = fileobj.getRows()
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(
                    cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'invoice_id': invoice_id, 'header_index': header_index})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index,
                                                                  columns_for_account_line_import)
                if not res:
                    return self.write(cr, uid, ids, res1, context)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
        if not context.get('yml_test'):
            thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
            thread.start()
        else:
            self._import(cr, uid, ids, context)
        msg_to_return = _("You can refresh the screen if you need to follow "
                          "the upload progress by clicking on \'Update\'.")
        return self.write(
            cr, uid, ids,
            {'message': msg_to_return, 'state': 'in_progress'},
            context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, int):
            ids = [ids]
        invoice_obj = self.pool.get('account.invoice')
        for wiz_read in self.read(cr, uid, ids, ['invoice_id', 'state', 'file']):
            invoice_id = wiz_read['invoice_id']
            invoice_name = invoice_obj.read(cr, uid, invoice_id, ['name'])['name']
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (invoice_name or _('the object'), )})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, int):
            ids = [ids]
        for wiz_obj in self.read(cr, uid, ids, ['invoice_id']):
            invoice_id = wiz_obj['invoice_id']
            view_data = self.pool.get('account.invoice')._get_invoice_act_window(cr, uid, invoice_id, views_order=['form', 'tree'], context=context)
            view_data['res_id'] = invoice_id
            view_data['help'] = False  # hide the Tip message displayed on top
            return view_data

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return self.cancel(cr, uid, ids, context=context)

wizard_import_invoice_line()
