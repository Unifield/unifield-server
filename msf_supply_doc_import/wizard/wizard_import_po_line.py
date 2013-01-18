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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import time
from msf_supply_doc_import import check_line
from msf_supply_doc_import.wizard import PO_LINE_COLUMNS_FOR_IMPORT as columns_for_po_line_import

class wizard_import_po_line(osv.osv_memory):
    _name = 'wizard.import.po.line'
    _description = 'Import PO Lines from Excel sheet'

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
        'file': fields.binary(string='File to import', required=True),
        'message': fields.text(string='Message', readonly=True),
        'po_id': fields.many2one('purchase.order', string='Purchase Order', required=True),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
    }
    
    _defaults = {
        'message': lambda *a : """
        IMPORTANT : The first line will be ignored by the system.
        The file should be in XML 2003 format.

The columns should be in this values:
%s
""" % (', \n'.join(columns_for_po_line_import), ),
        'state': lambda *a: 'draft',
    }

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        lines_not_imported = kwargs.get('line_with_error') # list of list
        header_index = kwargs.get('header_index')
        data = header_index.items()
        columns_header = []
        for k,v in sorted(data, key=lambda tup: tup[1]):
            columns_header.append((k, type(k)))
        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml()), 'filename': 'Lines_Not_Imported.xls'}
        return vals

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set po_id with the active_id value in context
        '''
        if not context or not context.get('active_id'):
            raise osv.except_osv(_('Error !'), _('No Purchase Order found !'))
        else:
            po_id = context.get('active_id')
            res = super(wizard_import_po_line, self).default_get(cr, uid, fields, context=context)
            res['po_id'] = po_id
        return res

    def get_line_values(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        list_of_values = []
        for cell_nb in range(len(row)):
            cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb, error_list, line_num, context)
            list_of_values.append(cell_data)
        return list_of_values

    def get_cell_data(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = False
        try:
            line_content = row.cells
        except ValueError:
            line_content = row.cells
        if line_content and row.cells[cell_nb] and row.cells[cell_nb].data:
            cell_data = row.cells[cell_nb].data
        return cell_data

    def get_header_index(self, cr, uid, ids, row, error_list, line_num, context):
        """
        Return dict with {'header_name0': header_index0, 'header_name1': header_index1...}
        """
        header_dict = {}
        for cell_nb in range(len(row.cells)):
            header_dict.update({self.get_cell_data(cr, uid, ids, row, cell_nb, error_list, line_num, context): cell_nb})
        return header_dict

    def check_header_values(self, cr, uid, ids, context, header_index):
        """
        Check that the columns in the header will be taken into account.
        """
        for k,v in header_index.items():
            if k not in columns_for_po_line_import:
                vals = {'message': 'The column "%s" is not taken into account. Please remove it. The list of columns accepted is: %s' 
                                                   % (k, ', \n'.join(columns_for_po_line_import))}
                self.write(cr, uid, ids, vals, context)
#                raise osv.except_osv(_('Error'), _('The column "%s" is not taken into account. Please remove it. The list of columns accepted is: %s' 
#                                                   % (k, ', \n'.join(columns_for_po_line_import))))

    def get_file_values(self, cr, uid, ids, rows, header_index, error_list, line_num, context=None):
        """
        Catch the file values on the form [{values of the 1st line}, {values of the 2nd line}...]
        """
        data = header_index.items()
        columns_header = []
        for k,v in sorted(data, key=lambda tup: tup[1]):
            columns_header.append(k)
        file_values = []
        for row in rows:
            line_values = {}
            for cell in enumerate(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context)):
                line_values.update({columns_header[cell[0]]: cell[1]})
            file_values.append(line_values)
        return file_values

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        cr = pooler.get_db(dbname).cursor()
        
        if context is None:
            context = {}
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')
        line_with_error = []
        vals = {'order_line': []}
        
        for wiz_browse in self.browse(cr, uid, ids, context):
            po_browse = wiz_browse.po_id
            po_id = po_browse.id
            
            ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
            line_ignored_num = []
            error_list = []
            error_log = ''
            message = ''
            line_num = 0
            
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
            # iterator on rows
            reader = fileobj.getRows()
            reader_iterator = iter(reader)
            # get first line
            first_row = next(reader_iterator)
            header_index = self.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=line_num, context=context)
            self.check_header_values(cr, uid, ids, context, header_index)

            # iterator on rows
            rows = fileobj.getRows()
            # ignore the first row
            rows.next()
            line_num = 0
            to_write = {}
            total_line_num = len([row for row in fileobj.getRows()])
            for row in rows:
                line_num += 1
                # default values
                to_write = {
                    'error_list': [],
                    'warning_list': [],
                    'to_correct_ok': False,
                    'show_msg_ok': False,
                    'comment': '',
                    'date_planned': po_browse.delivery_requested_date,
                    'functional_currency_id': po_browse.pricelist_id.currency_id.id,
                    'price_unit': 1,  # as the price unit cannot be null, it will be computed in the method "compute_price_unit" after.
                    'product_qty': 1,
                    'nomen_manda_0':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1],
                    'nomen_manda_1':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1],
                    'nomen_manda_2':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1],
                    'nomen_manda_3':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1],
                    'proc_type': 'make_to_order',
                    'default_code': False,
                    'confirmed_delivery_date': False,
                }

                col_count = len(row)
                template_col_count = len(header_index.items())
                if col_count != template_col_count:
                    message += """Line %s: You should have exactly %s columns in this order: %s \n""" % (line_num, template_col_count,','.join(columns_for_po_line_import))
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    ignore_lines += 1
                    line_ignored_num.append(line_num)
                    continue
                try:
                    if not check_line.check_empty_line(row=row, col_count=col_count):
                        continue
    
                    # Cell 0: Product Code
                    p_value = {}
                    p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'],
                                     'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})
    
                    # Cell 2: Quantity
                    qty_value = {}
                    qty_value = check_line.quantity_value(product_obj=product_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'product_qty': qty_value['product_qty'], 'error_list': qty_value['error_list'],
                                     'warning_list': qty_value['warning_list']})
    
                    # Cell 3: UOM
                    uom_value = {}
                    uom_value = check_line.compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})
    
                    # Cell 4: Price
                    price_value = {}
                    price_value = check_line.compute_price_value(row=row, to_write=to_write, price='Cost Price', context=context)
                    to_write.update({'price_unit': price_value['price_unit'], 'error_list': price_value['error_list'],
                                     'warning_list': price_value['warning_list'], 'price_unit_defined': price_value['price_unit_defined']})
    
                    # Cell 5: Delivery Request Date
                    date_value = {}
                    date_value = check_line.compute_date_value(row=row, to_write=to_write, context=context)
                    to_write.update({'date_planned': date_value['date_planned'], 'error_list': date_value['error_list']})
    
                    # Cell 6: Currency
                    curr_value = {}
                    curr_value = check_line.compute_currency_value(cr, uid, cell=6, browse_purchase=po_browse,
                                                        currency_obj=currency_obj, row=row, to_write=to_write, context=context)
                    to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})
    
                    # Cell 7: Comment
                    c_value = {}
                    c_value = check_line.comment_value(row=row, cell=7, to_write=to_write, context=context)
                    to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
                    to_write.update({
                        'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
                        'show_msg_ok': [True for x in to_write['warning_list']],  # the lines with show_msg_ok=True won't change color, it is just info
                        'order_id': po_browse.id,
                        'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
                    })
                    # we check consistency on the model of on_change functions to call for updating values
                    purchase_line_obj.check_line_consistency(cr, uid, po_browse.id, to_write=to_write, context=context)

                    # write order line on PO
                    if purchase_obj._check_service(cr, uid, po_id, vals, context=context):
                        purchase_line_obj.create(cr, uid, to_write, context=context)
                        vals['order_line'].append((0, 0, to_write))
                        if to_write['error_list']:
                            lines_to_correct += 1
                        complete_lines += 1

                    percent_completed = float(line_num)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                except IndexError, e:
                    error_log += "The line num %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined 8 columns. Details: %s" % (line_num, e)
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    ignore_lines += 1
                    line_ignored_num.append(line_num)
                    continue
                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    message += "Line %s in your Excel file: %s: %s\n" % (line_num, osv_name, osv_value)
                    ignore_lines = '1'
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    continue
                except Exception, e:
                    message += """Line %s: Uncaught error: %s""" % (line_num, e)
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    continue
                complete_lines += 1
        error_log += '\n'.join(error_list)
        if error_log:
            error_log = "Reported errors for ignored lines : \n" + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + ' second(s)'
        final_message = ''' 
Importation completed in %s!
# of imported lines : %s on %s lines
# of ignored lines: %s
# of lines to correct: %s
%s

%s
''' % (total_time ,complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
#        try:
        wizard_vals = {'message': final_message, 'state': 'done'}
        if line_with_error:
            file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
            wizard_vals.update(file_to_export)
        self.write(cr, uid, ids, wizard_vals, context=context)
        msg_to_return = check_line.get_log_message(to_write=to_write, obj=po_browse)
        if msg_to_return:
            purchase_obj.log(cr, uid, po_id, _(msg_to_return), 
                             context={'view_id': obj_data.get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1]})
        # we reactivate the PO
        purchase_obj.write(cr, uid, po_id, {'active': True}, context)
        cr.commit()
        cr.close()


    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        purchase_obj = self.pool.get('purchase.order')
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        for wiz_obj in self.read(cr, uid, ids, ['po_id', 'file']):
            po_id = wiz_obj['po_id']
            if not wiz_obj['file']:
                raise osv.except_osv(_('Error'), _("""Nothing to import"""))
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_obj['file']))
            # we inactive the PO when it is in import_in_progress because we don't want the user to edit it in the same time
            purchase_obj.write(cr, uid, po_id, {'active': False}, context)
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        purchase_obj = self.pool.get('purchase.order')
        for wiz_obj in self.read(cr, uid, ids, ['po_id']):
            po_id = wiz_obj['po_id']
            po_name = purchase_obj.read(cr, uid, po_id, ['name'])['name']
        for wiz_read in self.read(cr, uid, ids, ['state']):
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': ' Import in progress... \n Please wait that the import is finished before editing %s.' % po_name})
        return False

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id']):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }

wizard_import_po_line()
