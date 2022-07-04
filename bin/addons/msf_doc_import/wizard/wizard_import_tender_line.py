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
# For the the time logger function------
import time
from msf_doc_import import check_line
from msf_doc_import.wizard import TENDER_COLUMNS_FOR_IMPORT as columns_for_tender_line_import

class wizard_import_tender_line(osv.osv_memory):
    _name = 'wizard.import.tender.line'
    _description = 'Import Tender Lines from Excel sheet'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)], 'error': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'tender_id': fields.many2one('tender', string='Tender', required=True),
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
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        cr = pooler.get_db(dbname).cursor()
        context.update({'import_in_progress': True})
        start_time = time.time()
        wiz_common_import = self.pool.get('wiz.common.import')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        tender_obj = self.pool.get('tender')
        tender_line_obj = self.pool.get('tender.line')
        line_with_error = []
        blocker_msg = []

        categ_log = ''
        max_qty = self.pool.get('purchase.order.line')._max_qty

        for wiz_browse in self.browse(cr, uid, ids, context):
            tender_browse = wiz_browse.tender_id
            tender_id = tender_browse.id

            ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
            line_ignored_num, error_list = [], []
            error_log, message = '', ''
            header_index = context['header_index']

            file_obj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_browse.file))
            # iterator on rows
            rows = file_obj.getRows()
            # ignore the first row
            next(rows)
            line_num = 0
            to_write = {}
            total_line_num = len([row for row in file_obj.getRows()])
            percent_completed = 0
            for row in rows:
                cr.execute("SAVEPOINT line_save")
                # default values
                to_write = {
                    'error_list': [],
                    'warning_list': [],
                    'to_correct_ok': False,
                    'default_code': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1],
                    'uom_id': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1],
                    'product_qty': 1,
                }
                line_num += 1
                col_count = len(row)
                template_col_count = len(list(header_index.items()))
                if col_count != template_col_count:
                    message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (line_num, template_col_count,','.join([_(f) for f in columns_for_tender_line_import]))
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

                    # for each cell we check the value
                    # Cell 0: Product Code
                    p_value = {}
                    p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'product_id': p_value['default_code'], 'error_list': p_value['error_list']})

                    # Cell 2: Quantity
                    qty_value = {}
                    qty_value = check_line.quantity_value(cell_nb=2, product_obj=product_obj, row=row, to_write=to_write, max_qty=max_qty, context=context)
                    to_write.update({'qty': qty_value['product_qty'], 'error_list': qty_value['error_list'], 'warning_list': qty_value['warning_list']})

                    # Cell 3: UoM
                    uom_value = {}
                    uom_value = check_line.compute_uom_value(cr, uid, cell_nb=3, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})

                    # Check rounding of qty according to UoM
                    if qty_value['product_qty'] and uom_value['uom_id']:
                        round_qty = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_value['uom_id'], qty_value['product_qty'], 'product_qty')
                        if round_qty.get('warning', {}).get('message'):
                            to_write.update({'qty': round_qty['value']['product_qty']})
                            message += _("Line %s in the Excel file: %s\n") % (line_num, round_qty['warning']['message'])

                    to_write.update({
                        'to_correct_ok': any(to_write['error_list']),  # the lines with to_correct_ok=True will be red
                        'text_error': '\n'.join(to_write['error_list']),
                        'tender_id': tender_id,
                    })
                    # we check consistency of uom and product values
                    tender_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)

                    # Check product restrictions
                    if p_value.get('default_code'):
                        product_obj._get_restriction_error(cr, uid, [p_value['default_code']], {'constraints': ['external', 'internal', 'esc']}, context=dict(context, noraise=False))


                    if to_write.get('qty', 0.00) <= 0.00:
                        message += _("Line %s in the Excel file: Details: %s\n") % (line_num, _('Product Qty should be greater than 0.00'))
                        ignore_lines += 1
                        line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        cr.execute("RELEASE SAVEPOINT line_save")
                        continue

                    if not blocker_msg:
                        tender_line_obj.create(cr, uid, to_write, context)
                    if to_write['error_list']:
                        lines_to_correct += 1
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    complete_lines += 1

                except IndexError as e:
                    error_log += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s") % (line_num, template_col_count, e)
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    ignore_lines += 1
                    line_ignored_num.append(line_num)
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    cr.execute("RELEASE SAVEPOINT line_save")
                    continue
                except check_line.ExceptionWrongQuantity:
                    prod = ''
                    if p_value.get('default_code'):
                        prod = self.pool.get('product.product').browse(cr, uid, p_value.get('default_code'), fields_to_fetch=['default_code'], context=context).default_code
                        blocker_msg.append(_('Line #%s of the file, product: %s') % (line_num+1, prod))
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    cr.rollback()
                    continue
                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                    ignore_lines += 1
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    cr.execute("RELEASE SAVEPOINT line_save")
                    continue
                else:
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    cr.commit()

            if not blocker_msg:
                categ_log = tender_obj.onchange_categ(
                    cr, uid, [tender_browse.id], tender_browse.categ, context=context).get('warning', {}).get('message', '').upper()
                categ_log = categ_log.replace('THIS', 'THE')

        error_log += '\n'.join(error_list)
        if error_log:
            error_log = _("Reported errors for ignored lines : \n") + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + _(' second(s)')
        if blocker_msg:
            wizard_vals = {'state': 'error', 'percent_completed': 100, 'file': False}
            cr.rollback()
            final_message = _("Warning this/these lines cannot be imported due to too many digits in Qty field. Please check:\n%s") % ('\n'.join(blocker_msg), )
        else:
            wizard_vals = {'state': 'done'}
            final_message = _('''
%s
Importation completed in %s!
# of imported lines : %s on %s lines
# of ignored lines: %s
# of lines to correct: %s
%s

%s
''') % (categ_log, total_time ,complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
#        try:
        wizard_vals['message'] = final_message
        if line_with_error:
            file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
            wizard_vals.update(file_to_export)
        self.write(cr, uid, ids, wizard_vals, context=context)
        # we reset the state of the PO to draft (initial state)
        tender_obj.write(cr, uid, tender_id, {'state': 'draft'}, context)
        cr.commit()
        cr.close(True)


    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        if isinstance(ids, int):
            ids = [ids]
        wiz_common_import = self.pool.get('wiz.common.import')
        tender_obj = self.pool.get('tender')
        for wiz_read in self.read(cr, uid, ids, ['tender_id', 'file']):
            tender_id = wiz_read['tender_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_read['file']))
                # iterator on rows
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'tender_id': tender_id, 'header_index': header_index, 'object': tender_obj})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_tender_line_import)
                if not res:
                    return self.write(cr, uid, ids, res1)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
            # we close the PO only during the import process so that the user can't update the PO in the same time (all fields are readonly)
            tender_obj.write(cr, uid, tender_id, {'state': 'done'}, context)
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, int):
            ids = [ids]
        tender_obj = self.pool.get('tender')
        for wiz_read in self.read(cr, uid, ids, ['tender_id', 'state', 'file']):
            tender_id = wiz_read['tender_id']
            po_name = tender_obj.read(cr, uid, tender_id, ['name'])['name']
            if wiz_read['state'] not in  ('done', 'error'):
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (po_name, )})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, int):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['tender_id']):
            tender_id = wiz_obj['tender_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'tender',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': tender_id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, int):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['tender_id']):
            tender_id = wiz_obj['tender_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'tender',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': tender_id,
                'context': context,
                }

wizard_import_tender_line()
