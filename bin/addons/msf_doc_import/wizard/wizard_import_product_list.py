# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

import threading
import pooler
import tools

import time
from msf_doc_import import check_line
from msf_doc_import.wizard import PRODUCT_LIST_COLUMNS_FOR_IMPORT as columns_for_product_list_import


class wizard_import_product_list(osv.osv_memory):
    _name = 'wizard.import.product.list'
    _rec_name = 'list_id'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for id in ids:
            res[id] = False
        return res

        """
        # product_ids does not exist
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.product_ids if item.to_correct_ok]):
                res[obj.id] = True
        """

    _columns = {
        'file': fields.binary(string='File to import', filters='*.xml',
                              help="""You can use the template of the export for the format that you need to use.\n
                              The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order :
                              Product Code*, Product Description*, Comment"""),
        'message': fields.text(string='Message', readonly=True),
        'list_id': fields.many2one('product.list', string='List', required=True, ondelete='cascade'),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, type="boolean", string="Show column errors", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
    }

    def _import(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        context = context is None and {} or context
        ids = isinstance(ids, (int, long)) and [ids] or ids

        if not context.get('yml_test', False):
            cr = pooler.get_db(cr).cursor()

        context.update({'import_in_progress': True})
        start_time = time.time()

        list_id = ids[0]
        obj = self.browse(cr, uid, list_id, context=context)
        if not obj.file:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        product_obj = self.pool.get('product.product')
        list_line_obj = self.pool.get('product.list.line')
        obj_data = self.pool.get('ir.model.data')
        wiz_common_import = self.pool.get('wiz.common.import')

        line_with_error = []

        for wiz_browse in self.browse(cr, uid, ids, context):
            list_browse = wiz_browse.list_id
            list_id = list_browse.id

            ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
            line_ignored_num, error_list = [], []
            error_log, message = '', ''
            header_index = context['header_index']

            imp_product_ids = []

            file_obj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
            # iterator on rows
            rows = file_obj.getRows()
            # ignore the first row
            rows.next()
            line_num = 0
            to_write = {}
            total_line_num = len([row for row in file_obj.getRows()])
            percent_completed = 0
            for row in rows:
                # default values
                to_write = {
                    'error_list': [],
                    'warning_list': [],
                    'default_code': False,
                }
                line_num += 1
                col_count = len(row)
                template_col_count = len(header_index.items())
                if col_count != template_col_count:
                    message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (line_num, template_col_count,','.join([_(f) for f in columns_for_product_list_import]))
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    ignore_lines += 1
                    line_ignored_num.append(line_num)
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed': percent_completed})
                    continue
                try:
                    if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                        percent_completed = float(line_num)/float(total_line_num-1)*100.0
                        self.write(cr, uid, ids, {'percent_completed': percent_completed})
                        line_num -= 1
                        total_line_num -= 1
                        continue

                    # for each cell we check te value
                    # Cell 0: Product Code
                    p_value = {}
                    p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'product_id': p_value['default_code'], 'error_list': p_value['error_list']})

                    if list_browse.type == 'sublist' and list_browse.parent_id:
                        pll_ids = list_line_obj.search(cr, uid, [
                            ('list_id', '=', list_browse.parent_id.id),
                            ('name', '=', to_write.get('product_id')),
                        ], context=context)
                        if not pll_ids:
                            to_write.setdefault('error_list', []).append(_('Product not allowed.'))
                            error_log += _('Line %s in the Excel file was added to the file of the lines with errors. Details: Product not in the parent list %s.') % (line_num, list_browse.parent_id.name)
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.rollback()
                            continue

                    # Cell 1: Product Description
                    if not to_write.get('product_id'):
                        product_ids = product_obj.search(cr, uid, [('name', '=', tools.ustr(row[1]))], context=context)
                        if product_ids:
                            to_write.update({'product_id': product_ids[0]})
                        else:
                            to_write.setdefault('error_list', []).append(_('Product description doesn\'t exist in the DB.'))
                            error_log += _("Line %s in the Excel file was added to the file of the lines with errors. Details: No product found.") % line_num
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.rollback()
                            continue

                    if to_write.get('product_id'):
                        exist_line_ids = list_line_obj.search(cr, uid, [
                            ('list_id', '=', list_browse.id),
                            ('name', '=', to_write.get('product_id'))
                        ], limit=1, context=context)
                        in_list = to_write['product_id'] in imp_product_ids
                        imp_product_ids.append(to_write['product_id'])
                        if exist_line_ids or in_list:
                            prod_brw = product_obj.browse(cr, uid, to_write['product_id'], context=context)
                            to_write.setdefault('error_list', []).append(
                                _('Product [%s] %s is already in the product list. Line not imported \n') % (
                                    prod_brw.default_code,
                                    prod_brw.name,
                                )
                            )
                            error_log += _("Line %s in the Excel file was added to the file of the lines with errors."
                                           "Details: Product already in the product list \n") % line_num
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False,
                                                                                     error_list=error_list,
                                                                                     line_num=line_num,
                                                                                     context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.00
                            cr.rollback()
                            continue

                    # Cell 2: Comment
                    to_write.update({'comment': row[2]})

                    line_data = {'name': to_write.get('product_id'),
                                 'list_id': list_id,
                                 'comment': to_write.get('comment'),}

                    list_line_obj.create(cr, uid, line_data, context=context)

                    if to_write.get('error_list'):
                        lines_to_correct += 1

                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    complete_lines += 1

                except IndexError, e:
                    error_log += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s") % (line_num, template_col_count, e)
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    ignore_lines += 1
                    line_ignored_num.append(line_num)
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    cr.rollback()
                    continue
                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                    ignore_lines += 1
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    cr.rollback()
                    continue
                finally:
                    self.write(cr, uid, ids, {'percent_completed': percent_completed})
                    if not context.get('yml_test', False):
                        cr.commit()

        error_log += '\n'.join(error_list)
        end_time = time.time()
        total_time = tools.ustr(round(end_time-start_time)) + _(' second(s)')
        final_message = _('''
Importation completed in %s!
# of imported lines: %s on %s lines
# of ignored lines: %s
# of lines to correct: %s
%s

%s
''') % (total_time, complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
        wizard_vals = {'message': final_message, 'state': 'done'}
        if line_with_error:
            file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
            wizard_vals.update(file_to_export)
        self.write(cr, uid, ids, wizard_vals, context=context)
        if not context.get('yml_test', False):
            cr.commit()
            cr.close(True)


    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        ids = isinstance(ids, (int, long)) and [ids] or ids
        context = context is None and {} or context

        wiz_common_import = self.pool.get('wiz.common.import')
        list_obj = self.pool.get('product.list')
        for wiz_read in self.read(cr, uid, ids, ['list_id', 'file']):
            list_id = wiz_read['list_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_read['file']))
                # iterator on rews
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'list_id': list_id, 'header_index': header_index, 'object': list_obj})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_product_list_import)
                if not res:
                    return self.write(cr, uid, ids, res1)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
        if not context.get('yml_test', False):
            thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
            thread.start()
        else:
            self._import(cr, uid, ids, context)
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done. Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        ids = isinstance(ids, (int, long)) and [ids] or ids
        context = context is None and {} or context
        list_obj = self.pool.get('product.list')
        for wiz_read in self.read(cr, uid, ids, ['list_id', 'state', 'file']):
            list_id = wiz_read['list_id'] if isinstance(wiz_read['list_id'], (int, long)) else wiz_read['list_id'][0]
            list_name = list_obj.read(cr, uid, list_id, ['name'])['name']
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (list_name)})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special), I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        ids = isinstance(ids, (int, long)) and [ids] or ids
        for wiz_obj in self.read(cr, uid, ids, ['list_id']):
            list_id =  wiz_obj['list_id'] if isinstance(wiz_obj['list_id'], (int, long)) else wiz_obj['list_id'][0]

        return {'type': 'ir.actions.act_window',
                'res_model': 'product.list',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': list_id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return self.cancel(cr, uid, ids, context=context)

wizard_import_product_list()
