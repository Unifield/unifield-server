# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import pooler
from osv import osv, fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import time
import tools
from msf_doc_import import check_line
from msf_doc_import.wizard import FO_LINE_COLUMNS_FOR_IMPORT as columns_for_fo_line_import

class wizard_import_fo_line(osv.osv_memory):
    _name = 'wizard.import.fo.line'
    _description = 'Import FO Lines from Excel sheet'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)], 'error': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'fo_id': fields.many2one('sale.order', string='Field Order', required=True),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done'), ('error', 'Error')],
                                  string="State", required=True, readonly=True),
    }

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        if not context.get('yml_test', False):
            cr = pooler.get_db(dbname).cursor()
        else:
            cr = dbname

        if context is None:
            context = {}
        wiz_common_import = self.pool.get('wiz.common.import')
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        line_with_error = []
        max_value = sale_line_obj._max_value

        context_sol_create = context.copy()
        context_sol_create['no_store_function'] = ['sale.order.line']
        created_line = []
        blocker_msg = []
        for wiz_browse in self.browse(cr, uid, ids, context):
            try:
                fo_browse = wiz_browse.fo_id
                if not fo_browse.pricelist_id \
                        or not fo_browse.pricelist_id.currency_id:
                    raise osv.except_osv(_("Error!"), _("Order currency not found!"))
                fo_id = fo_browse.id

                ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
                line_ignored_num = []
                error_list = []
                error_log = ''
                message = ''
                categ_log = ''
                line_num = 0
                header_index = context['header_index']
                mandatory_col_count = 8  # ignore Status column

                file_obj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))

                """
                1st path: check currency in lines in phasis with document
                REF-94: BECAREFUL WHEN CHANGING THE ORDER OF CELLS IN THE IMPORT FILE!!!!!
                CCY COL INDEX: 6
                """
                order_currency_code = fo_browse.pricelist_id.currency_id.name
                currency_index = 6
                rows = file_obj.getRows()

                header_row = rows.next()
                header_error = False

                if len(header_row) != mandatory_col_count and len(header_row) != len(columns_for_fo_line_import):
                    header_row = False
                    header_error = True
                    error_list.append(_("\n\tNumber of columns is not equal to %s") % len(columns_for_fo_line_import))

                if header_row:
                    for i, h_name in enumerate(columns_for_fo_line_import):
                        # To be able to import without Status column
                        if h_name != 'State' or len(header_row) != mandatory_col_count:
                            tr_header_row = _(tools.ustr(header_row[i]))
                            tr_h_name = _(h_name)
                            if len(header_row) > i and tr_header_row.upper() != tr_h_name.upper():
                                header_error = True
                                error_list.append(_("\n\tPlease check spelling on column '%s'.") % tr_header_row)

                if header_error:
                    msg = _("\n\tYou can not import this file because the header of columns doesn't match with the expected headers: %s") % ','.join([_(x) for x in columns_for_fo_line_import])
                    error_list.append(msg)
                    msg = _("\n\tPlease ensure that all these columns are present and in this exact order.")
                    error_list.append(msg)
                else:
                    lines_to_correct = check_line.check_lines_currency(rows,
                                                                       currency_index, order_currency_code)
                    if lines_to_correct > 0:
                        msg = _("You can not import this file because it contains" \
                                " line(s) with currency (Column G) not of the order currency (%s)") % (
                            order_currency_code, )
                        error_list.append(msg)

                if not error_list:
                    # iterator on rows
                    rows = file_obj.getRows()
                    rows.next() # skip header
                    # ignore the first row

                    line_num = 0
                    to_write = {}
                    total_line_num = file_obj.getNbRows()
                    percent_completed = 0
                    for row in rows:
                        cr.execute("SAVEPOINT line_save")
                        line_num += 1
                        # default values
                        to_write = {
                            'error_list': [],
                            'warning_list': [],
                            'to_correct_ok': False,
                            'show_msg_ok': False,
                            'comment': '',
                            'date_planned': fo_browse.delivery_requested_date,
                            'functional_currency_id': fo_browse.pricelist_id.currency_id.id,
                            'price_unit': 1,  # in case that the product is not found and we do not have price
                            'product_qty': 1,
                            'proc_type': 'make_to_order',
                            'default_code': False,
                            'confirmed_delivery_date': False,
                        }

                        col_count = len(row)
                        template_col_count = len(header_index.items())
                        if col_count != template_col_count and col_count != mandatory_col_count:
                            message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (line_num, template_col_count,', '.join(columns_for_fo_line_import))
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            self.write(cr, uid, ids, {'percent_completed':percent_completed})
                            continue
                        try:
                            if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                                percent_completed = float(line_num)/float(total_line_num-1)*100.0
                                self.write(cr, uid, ids, {'percent_completed': percent_completed})
                                line_num-=1
                                total_line_num -= 1
                                continue

                            """
                                REF-94: BECAREFUL WHEN CHANGING THE ORDER OF CELLS IN THE IMPORT FILE!!!!!
                            """

                            # Cell 0: Product Code
                            p_value = {}
                            p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                            to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'], 'price_unit': p_value['price_unit'],
                                             'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})

                            # Cell 2: Quantity
                            qty_value = {}
                            qty_value = check_line.quantity_value(cell_nb=2, product_obj=product_obj, row=row, to_write=to_write, max_qty=max_value, context=context)
                            to_write.update({'product_uom_qty': qty_value['product_qty'], 'error_list': qty_value['error_list']})

                            # Cell 3: UOM
                            uom_value = {}
                            uom_value = check_line.compute_uom_value( cr, uid, cell_nb=3, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                            to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})

                            # Check round of qty according to UoM
                            if qty_value['product_qty'] and uom_value['uom_id']:
                                round_qty = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_value['uom_id'], qty_value['product_qty'], 'product_qty')
                                if round_qty.get('warning', {}).get('message'):
                                    to_write.update({'product_uom_qty': round_qty['value']['product_qty']})
                                    message += _("Line %s in the Excel file: %s\n") % (line_num, round_qty['warning']['message'])

                            # Cell 4: Price
                            price_value = {}
                            price_value = check_line.compute_price_value(cell_nb=4, row=row, to_write=to_write, price='Field Price', context=context)
                            to_write.update({'price_unit': price_value['price_unit'], 'error_list': price_value['error_list'],
                                             'warning_list': price_value['warning_list']})

                            # Cell 5: Date
                            date_value = {}
                            date_value = check_line.compute_date_value(cell_nb=5, row=row, to_write=to_write, context=context)
                            to_write.update({'date_planned': date_value['date_planned'], 'error_list': date_value['error_list'],
                                             'warning_list': date_value['warning_list']})

                            # Cell 6: Currency
                            curr_value = {}
                            curr_value = check_line.compute_currency_value(cr, uid, cell_nb=6, browse_sale=fo_browse,
                                                                           currency_obj=currency_obj, row=row, to_write=to_write, context=context)
                            to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})

                            # Cell 7: Comment
                            c_value = {}
                            c_value = check_line.comment_value(row=row, cell_nb=7, to_write=to_write, context=context)
                            to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
                            to_write.update({
                                'to_correct_ok': any(to_write['error_list']),  # the lines with to_correct_ok=True will be red
                                'show_msg_ok': any(to_write['warning_list']),  # the lines with show_msg_ok=True won't change color, it is just info
                                'order_id': fo_browse.id,
                                'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
                            })
                            # we check consistency on the model of on_change functions to call for updating values
                            sale_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)

                            if to_write.get('product_uom_qty', 0.00) <= 0.00:
                                error_log += _("Line %s in the Excel file was ignored. Details: %s") % (line_num, _('Product Quantity must be greater than zero.'))
                                line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                                ignore_lines += 1
                                line_ignored_num.append(line_num)
                                percent_completed = float(line_num)/float(total_line_num-1)*100.0
                                cr.execute('ROLLBACK TO SAVEPOINT line_save')
                                continue

                            # Check product restrictions
                            if p_value.get('default_code') and fo_browse.partner_id:
                                product_obj._get_restriction_error(cr, uid, [p_value['default_code']], {'partner_id': fo_browse.partner_id.id, 'obj_type': 'sale.order'}, context=dict(context, noraise=False))

                            # write order line on FO
                            if not blocker_msg:
                                created_line.append(sale_line_obj.create(cr, uid, to_write, context=context_sol_create))
                            if to_write['error_list']:
                                lines_to_correct += 1
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            complete_lines += 1

                        except IndexError, e:
                            error_log += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s") % (line_num, template_col_count, e)
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.execute('ROLLBACK TO SAVEPOINT line_save')
                            continue
                        except osv.except_osv as osv_error:
                            osv_value = osv_error.value
                            osv_name = osv_error.name
                            message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                            ignore_lines += 1
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.execute('ROLLBACK TO SAVEPOINT line_save')
                            continue
                        except check_line.ExceptionWrongQuantity as e:
                            prod = ''
                            if p_value.get('default_code'):
                                prod = self.pool.get('product.product').browse(cr, uid, p_value.get('default_code'), fields_to_fetch=['default_code'], context=context).default_code
                            blocker_msg.append(_('Line #%s of the file, product: %s') % (line_num+1, prod))
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            cr.rollback()
                            continue
                        else:
                            self.write(cr, uid, ids, {'percent_completed':percent_completed})
                            cr.execute("RELEASE SAVEPOINT line_save")

                    if not blocker_msg:
                        sale_line_obj._call_store_function(cr, uid, created_line, keys=None, result=None, bypass=False, context=context)
                        categ_log = sale_obj.onchange_categ(
                            cr, uid, [fo_id], wiz_browse.fo_id.categ, context=context).get('warning', {}).get('message', '').upper()
                        categ_log = categ_log.replace('THIS', 'THE')
                error_log += '\n'.join(error_list)
                if error_log:
                    error_log = _("Reported errors for ignored lines : \n") + error_log
                end_time = time.time()
                total_time = tools.ustr(round(end_time-start_time)) + _(' second(s)')
                if blocker_msg:
                    wizard_vals = {'state': 'error', 'percent_completed': 100, 'file': False}
                    cr.rollback()
                    final_message = _("Warning this/these lines cannot be imported due to too many digits in Qty field. Please check:\n%s") % ('\n'.join(blocker_msg), )
                else:
                    wizard_vals = {'state': 'done'}
                    cr.commit()
                    final_message = _('''
    %s
    Importation completed in %s!
# of imported lines : %s on %s lines
# of ignored lines: %s
# of lines to correct: %s
    %s

    %s
    ''') % (categ_log, total_time ,complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
                wizard_vals['message'] = final_message
                if line_with_error:
                    file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
                    wizard_vals.update(file_to_export)
                self.write(cr, uid, ids, wizard_vals, context=context)
                # we reset the state of the FO to draft (initial state)
            except Exception as e:
                self.write(cr, uid, ids, {
                    'message': _('An unknow error occurred, please contact the support team. Error message: %s') % tools.ustr(e),
                    'state': 'done',
                }, context=context)
            finally:
                sale_obj.write(cr, uid, fo_id, {'state': 'draft', 'import_in_progress': False}, context)
        cr.commit()
        cr.close(True)


    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        wiz_common_import = self.pool.get('wiz.common.import')
        sale_obj = self.pool.get('sale.order')
        for wiz_read in self.read(cr, uid, ids, ['fo_id', 'file']):
            fo_id = wiz_read['fo_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_read['file']))
                # iterator on rows
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'fo_id': fo_id, 'header_index': header_index})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_fo_line_import, origin='FO')
                if not res:
                    return self.write(cr, uid, ids, res1, context)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
            except StopIteration:
                return self.write(cr, uid, ids, {'message': _('The file has not row, nothing to import')})
            # we close the PO only during the import process so that the user can't update the PO in the same time (all fields are readonly)
            sale_obj.write(cr, uid, fo_id, {'state': 'done', 'import_in_progress': True}, context)
        if not context.get('yml_test', False):
            thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
            thread.start()
        else:
            self._import(cr, uid, ids, context)
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        sale_obj = self.pool.get('sale.order')
        for wiz_read in self.read(cr, uid, ids, ['fo_id', 'state', 'file']):
            fo_id = wiz_read['fo_id']
            fo_name = sale_obj.read(cr, uid, fo_id, ['name'])['name']
            if wiz_read['state'] not in ('done', 'error'):
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (fo_name, )})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['fo_id']):
            fo_id = wiz_obj['fo_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': fo_id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return self.cancel(cr, uid, ids, context=context)

wizard_import_fo_line()
