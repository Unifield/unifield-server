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
from osv import osv, fields, orm
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import time

from msf_doc_import import check_line
from msf_doc_import.wizard import STOCK_WAREHOUSE_ORDERPOINT_LINE_COLUMNS_FOR_IMPORT as columns_for_stock_warehouse_orderpoint


class wizard_import_stock_warehouse_orderpoint_line(osv.osv_memory):
    _name = 'wizard.import.stock.warehouse.orderpoint.line'
    _description = 'Import Minimum stock rules lines from Excel sheet'

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
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'rule_id': fields.many2one('stock.warehouse.orderpoint', string='Rule', required=True),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
    }

    def check_line_quantity_value_wrapper(self, **kwargs):
        """use of a custom product qty field name instead of 'product_qty'"""
        field_name = kwargs.get('field_name', False)
        if field_name:
            if 'to_write' in kwargs:
                kwargs['to_write']['product_qty'] = kwargs['to_write'][field_name]
        res = check_line.quantity_value(**kwargs)
        if field_name:
            res[field_name] = res['product_qty']
            del res['product_qty']
            if 'to_write' in kwargs:
                del kwargs['to_write']['product_qty']
        return res

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context.get('yml_test', False):
            cr = pooler.get_db(dbname).cursor()
        else:
            cr = dbname

        context.update({'import_in_progress': True})
        start_time = time.time()
        wiz_common_import = self.pool.get('wiz.common.import')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        rule_obj = self.pool.get('stock.warehouse.orderpoint')
        rule_line_obj = self.pool.get('stock.warehouse.orderpoint.line')
        line_with_error = []
        vals = {'rule_line_ids': []}

        cell_index = {'product_code': 0,
                      'product_desc': 1,
                      'uom_id': 2,
                      'product_min_qty': 3,
                      'product_max_qty': 4,
                      'qty_multiple': 5,
        }

        for wiz_browse in self.browse(cr, uid, ids, context):
            rule_browse = wiz_browse.rule_id
            rule_id = rule_browse.id

            ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
            line_ignored_num, error_list = [], []
            error_log, message = '', ''
            header_index = context['header_index']

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
                    'to_correct_ok': False,
                    'default_code': False,
                    'product_min_qty': 1.,
                    'product_max_qty': 1.,
                    'qty_multiple': 1,
                    'supply_id': rule_id,
                }
                line_num += 1
                col_count = len(row)
                template_col_count = len(header_index.items())
                if col_count != template_col_count:
                    message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (line_num, template_col_count,','.join([_(f) for f in columns_for_stock_warehouse_orderpoint]))
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
                    # for each cell we check the value
                    # Cell 0: Product Code
                    p_value = {}
                    p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'product_id': p_value['default_code'], 'error_list': p_value['error_list']})

                    if not to_write.get('product_id'):
                        raise osv.except_osv(_('Error'), '\n'.join(x for x in p_value['error_list']))

                     # Cell 2: UoM
                    uom_value = {}
                    uom_value = check_line.compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, cell_nb=cell_index['uom_id'], context=context)
                    to_write.update({'product_uom_id': uom_value['uom_id'], 'error_list': uom_value['error_list']})

                    if not to_write.get('product_uom_id') or to_write.get('product_uom_id') == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]:
                        raise osv.except_osv(_('Error'), '\n'.join(x for x in p_value['error_list']))

                    # Check if the UoM is compatible with the product
                    if to_write.get('product_id') and to_write.get('product_uom_id'):
                        uom_categ = uom_obj.browse(cr, uid, to_write.get('product_uom_id'), context=context).category_id.id
                        prod_uom_categ = product_obj.browse(cr, uid, to_write.get('product_id'), context=context).uom_id.category_id.id
                        if uom_categ != prod_uom_categ:
                            message += _("Line %s in the Excel file: Details: %s\n") % (line_num, _('The UoM is not compatible with the product.'))
                            ignore_lines += 1
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            cr.rollback()
                            continue

                    # Cell 3,4: Min Quantity, Max Quantity
                    qty_fields = ['product_min_qty', 'product_max_qty', ]
                    min_qty = False
                    for qty_field in qty_fields:
                        qty_value = {}
                        qty_value = self.check_line_quantity_value_wrapper(
                            field_name=qty_field, product_obj=product_obj,
                            row=row, to_write=to_write,
                            cell_nb=cell_index[qty_field], context=context)
                        to_write[qty_field] = qty_value[qty_field]
                        to_write.update({'error_list': qty_value['error_list'], 'warning_list': qty_value['warning_list']})

                        if not to_write.get(qty_field) or to_write.get(qty_field) == 0.00:
                            error_log += _("Line %s in the Excel file : The product qty has been set to 1.00 because the quantity in Excel file was 0.00") % line_num
                            to_write[qty_field] = 1.00

                        # Check rounding of qty according to UoM
                        if qty_value[qty_field] and uom_value['uom_id']:
                            round_qty = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_value['uom_id'], qty_value[qty_field], qty_field)
                            if round_qty.get('warning', {}).get('message'):
                                to_write[qty_field] = round_qty['value'][qty_field]
                                message += _("Line %s in the Excel file: %s\n") % (line_num, round_qty['warning']['message'])
                        if to_write.get(qty_field, 0.00) <= 0.00:
                            message += _("Line %s in the Excel file: Details: %s\n") % (line_num, _('Product Qty should be greater than 0.00'))
                            ignore_lines += 1
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            cr.rollback()
                            continue
                        if qty_field == 'product_min_qty':
                            min_qty = qty_value.get('product_min_qty', False)
                        if qty_field == 'product_max_qty' and min_qty:
                            max_qty = qty_value.get('product_max_qty', False)
                            if max_qty and max_qty > 0. and min_qty > max_qty:
                                error_log += _("Line %s in the Excel file : The product min qty has been set to 1.00 because it was greater than the max qty") % line_num
                                to_write['product_min_qty'] = 1.00

                    # Cell 5: Quantity Multiple
                    qty_multiple_value = {}
                    qty_multiple_value = check_line.number_value(
                        product_obj=product_obj, row=row, to_write=to_write,
                        cell_nb=cell_index['qty_multiple'],
                        field_name='qty_multiple', field_desc='Qty Multiple',
                        default=1, context=context)
                    to_write.update({'qty_multiple': qty_multiple_value['qty_multiple'], 'error_list': qty_multiple_value['error_list'], 'warning_list': qty_multiple_value['warning_list']})
                    if not to_write.get('qty_multiple') or to_write.get('qty_multiple') == 0:
                        error_log += _("Line %s in the Excel file : The product qty multiple has been set to 1 because the value in Excel file was 0.00") % line_num
                        to_write['qty_multiple'] = 1

                    rule_line_obj.create(cr, uid, to_write, context)
                    if 'error_list' in to_write and to_write['error_list']:
                        lines_to_correct += 1
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    complete_lines += 1
                except IndexError, e:
                    error_log += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s") % (line_num, template_col_count, e)
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
                except orm.except_orm as orm_error:
                    orm_value = orm_error.value
                    orm_name = orm_error.name
                    message += _("Line %s in the Excel file: %s: %s\n") % (line_num, orm_name, orm_value)
                    ignore_lines += 1
                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    cr.rollback()
                    continue
                finally:
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    if not context.get('yml_test', False):
                        cr.commit()

        error_log += '\n'.join(error_list)
        if error_log:
            error_log = _("Reported errors for ignored lines : \n") + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + _(' second(s)')
        final_message = _('''
Importation completed in %s!
# of imported lines : %s on %s lines
# of ignored lines: %s
# of lines to correct: %s
%s

%s
''') % (total_time ,complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
#        try:
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
        if isinstance(ids, (int, long)):
            ids = [ids]
        wiz_common_import = self.pool.get('wiz.common.import')
        rule_obj = self.pool.get('stock.warehouse.orderpoint')

        for wiz_read in self.read(cr, uid, ids, ['rule_id', 'file']):
            rule_id = wiz_read['rule_id']
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
                context.update({'rule_id': rule_id, 'header_index': header_index, 'object': rule_obj})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_stock_warehouse_orderpoint)
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
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        rule_obj = self.pool.get('stock.warehouse.orderpoint')
        for wiz_read in self.read(cr, uid, ids, ['rule_id', 'state', 'file']):
            rule_id = wiz_read['rule_id']
            po_name = rule_obj.read(cr, uid, rule_id, ['name'])['name']
            if wiz_read['state'] != 'done':
                msg = _(' Import in progress... \n Please wait that the import is finished before editing %s.')
                self.write(cr, uid, ids, {'message': msg % (po_name, )})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['rule_id']):
            rule_id = wiz_obj['rule_id']
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.warehouse.orderpoint',
            'view_type': 'form',
            'view_mode': 'form, tree',
            'target': 'crush',
            'res_id': rule_id,
            'context': context,
        }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['rule_id']):
            rule_id = wiz_obj['rule_id']
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.warehouse.orderpoint',
            'view_type': 'form',
            'view_mode': 'form, tree',
            'target': 'crush',
            'res_id': rule_id,
            'context': context,
        }

wizard_import_stock_warehouse_orderpoint_line()
