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
from msf_supply_doc_import.wizard import PO_COLUMNS_FOR_INTEGRATION as columns_for_po_integration, PO_COLUMNS_HEADER_FOR_INTEGRATION

class wizard_import_po(osv.osv_memory):
    _name = 'wizard.import.po'
    _description = 'Import PO from Excel sheet'

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
        'filename_template': fields.char('Templates', size=256),
        'filename': fields.char('Lines with errors', size=256),
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
""" % (', \n'.join(columns_for_po_integration), ),
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
            res = super(wizard_import_po, self).default_get(cr, uid, fields, context=context)
            res['po_id'] = po_id
        #columns_header = [(column, type(column)) for column in columns_for_po_integration]
        columns_header = PO_COLUMNS_HEADER_FOR_INTEGRATION
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        res.update({'file': base64.encodestring(default_template.get_xml()), 'filename': 'template.xls'})
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
        except ValueError, e:
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
            if k not in columns_for_po_integration:
                vals = {'message': 'The column "%s" is not taken into account. Please remove it. The list of columns accepted is: \n %s' 
                                                   % (k, ', \n'.join(columns_for_po_integration))}
                return self.write(cr, uid, ids, vals, context), False
        return True, True

    def get_po_row_values(self, cr, uid, ids, row, po_browse, header_index, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')
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
        # Line
        cell_nb = header_index['Line*']
        line_number = int(self.get_cell_data(cr, uid, ids, row, cell_nb, to_write['error_list'], line_num=False, context=context))
        to_write.update({'line_number': line_number})

        # Quantity
        qty_value = {}
        cell_nb = header_index['Quantity*']
        qty_value = check_line.quantity_value(product_obj=product_obj, cell_nb=cell_nb, row=row, to_write=to_write, context=context)
        to_write.update({'product_qty': qty_value['product_qty'], 'error_list': qty_value['error_list'],
                         'warning_list': qty_value['warning_list']})
    
        # Product Code
        p_value = {}
        cell_nb = header_index['Product Code*']
        p_value = check_line.product_value(cr, uid, cell_nb=cell_nb, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
        to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'],
                         'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})

        # UOM
        uom_value = {}
        cell_nb = header_index['UoM*']
        uom_value = check_line.compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, cell_nb=cell_nb, row=row, to_write=to_write, context=context)
        to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})

        # Price
        price_value = {}
        cell_nb = header_index['Price*']
        price_value = check_line.compute_price_value(row=row, to_write=to_write, cell_nb=cell_nb, price='Cost Price', context=context)
        to_write.update({'price_unit': price_value['price_unit'], 'error_list': price_value['error_list'],
                         'warning_list': price_value['warning_list'], 'price_unit_defined': price_value['price_unit_defined']})

        #  Currency
        curr_value = {}
        cell_nb = header_index['Currency*']
        curr_value = check_line.compute_currency_value(cr, uid, cell_nb=cell_nb, browse_purchase=po_browse,
                                            currency_obj=currency_obj, row=row, to_write=to_write, context=context)
        to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})

        # Delivery Confirmed Date
        cell_nb = header_index['Delivery Confirmed Date*']
        delivery_confirmed_date = self.get_cell_data(cr, uid, ids, row, cell_nb, error_list=to_write['error_list'], line_num=False, context=context)
        to_write.update({'delivery_confirmed_date': delivery_confirmed_date})

        #  Comment
        c_value = {}
        cell_nb = header_index['Comment']
        c_value = check_line.comment_value(row=row, cell_nb=cell_nb, to_write=to_write, context=context)
        to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
        to_write.update({
            'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
            'show_msg_ok': [True for x in to_write['warning_list']],  # the lines with show_msg_ok=True won't change color, it is just info
            'order_id': po_browse.id,
            'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
        })
        # we check consistency on the model of on_change functions to call for updating values
        purchase_line_obj.check_line_consistency(cr, uid, po_browse.id, to_write=to_write, context=context)

        return to_write


    def import_file(self, cr, uid, ids, context=None):
        '''
        Import file
        '''
        #cr = pooler.get_db(dbname).cursor()
        
        if context is None:
            context = {}
        pol_obj = self.pool.get('purchase.order.line')
        context.update({'import_in_progress': True})
        start_time = time.time()
        line_with_error = []
        
        for wiz_browse in self.browse(cr, uid, ids, context):
            if not wiz_browse.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            po_browse = wiz_browse.po_id
            po_id = po_browse.id
            po_line_browse = po_browse.order_line
            
            ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
            nm_lines = {} # Dict containing data of lines not matching with po lines
            matching_po_lines = [] # List of po lines matching with file lines
            line_ignored_num = []
            error_list = []
            error_log = ''
            
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
            # iterator on rows
            reader = fileobj.getRows()
            reader_iterator = iter(reader)
            # get first line
            first_row = next(reader_iterator)
            header_index = self.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=False, context=context)
            (res1, res2) = self.check_header_values(cr, uid, ids, context, header_index)
            if not res2:
                return False
            
            rows = fileobj.getRows()
            rows.next()
            file_line_num = 0
            for row in rows:
                file_line_num += 1
                try:
                    to_write = self.get_po_row_values(cr, uid, ids, row, po_browse, header_index, context)
                except IndexError, e:
                    if line_num not in line_ignored_num:
                        error_log += "The line num %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s" % (line_num, len(header_index.items()), e)
                        line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb, error_list, line_num=False, context=context))
                        ignore_lines += 1
                        line_ignored_num.append(line_num)

                if to_write['error_list']:
                    error_log += 'The line num %s in the Excel file was added to the file of the lines with errors: %s' % (file_line_num, ' '.join(to_write['error_list']))
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=to_write['error_list'], line_num=False, context=context))
                    ignore_lines += 1
                else:
                    product_id = to_write['product_id']
                    line_number = to_write['line_number']
                    product_uom = to_write['product_uom']
                    price_unit = to_write['price_unit']
                    product_qty = to_write['product_qty']
                    line_found = False
                    # Search if the file line matches with a po line
                    po_line_ids = pol_obj.search(cr, uid, [('order_id', '=', po_id),
                                                            ('id', 'not in', matching_po_lines),
                                                            ('product_id', '=', product_id),
                                                            ('line_number', '=', line_number),
                                                            ('product_uom', '=', product_uom),
                                                            ('price_unit', '=', price_unit),
                                                            ('product_qty', '=', product_qty)])
                    for l in pol_obj.browse(cr, uid, po_line_ids):
                        # If a line is found, pass to the next file line
                        if line_found:
                            break
                        line_found = True
                        matching_po_lines.append(l.id)
                        complete_lines += 1

                    if not line_found:
                        if line_number not in nm_lines:
                            nm_lines.update({line_number: []})
                            
                        # If the file line does not match with a wizard line
                        # add it to a list of lines to process after (sort in dict with the line_number)
                        nm_lines[line_number].append({'file_line_num': file_line_num,
                                                      'product_id': product_id,
                                                      'product_uom': product_uom,
                                                      'product_qty': product_qty})

                    # Process all lines not matching
                    
                    # First, search if a po line exists for the same line number, the same qty, the same price unit
                    # but with a different product or a different UoM
                    for ln in nm_lines:
                        index = 0
                        for nml in nm_lines[ln]:
                            # Search if a line exist with the same product/line_number/price_unit/quantity (only UoM is changed)
                            uom_change_ids = pol_obj.search(cr, uid, [('order_id', '=', po_id),
                                                                      ('id', 'not in', matching_po_lines),
                                                                      ('product_id', '=',  nml.get('product_id')),
                                                                      ('line_number', '=', ln),
                                                                      ('price_unit', '=', price_unit),
                                                                      ('product_qty', '=',nml.get('product_qty'))])
                            if uom_change_ids:
                                # The UoM has changed
                                po_line_id = uom_change_ids[0]
                                pol_obj.write(cr, uid, [po_line_id], {'product_uom': nml.get('uom_id'),
                                                                      'quantity': nml.get('product_qty')})
                                error_list.append("Line %s of the Excel file: The product UOM did not match with the existing product of the line %s so we change the product UOM." % (nml.get('file_line_num'), ln))
                                matching_wiz_lines.append(po_line_id)
                                complete_lines += 1
                                del nm_lines[ln][index]
                                continue
                                
                            # Search if a line exist with the same UoM/line_number/quantity (only product is changed)
                            prod_change_ids = pol_obj.search(cr, uid, [('order_id', '=', po_id),
                                                                      ('id', 'not in', matching_po_lines),
                                                                      ('product_uom', '=',  nml.get('product_uom')),
                                                                      ('line_number', '=', ln),
                                                                      ('price_unit', '=', price_unit),
                                                                      ('product_qty', '=',nml.get('product_qty'))])
                            if prod_change_ids:
                                # The product has changed
                                po_line_id = prod_change_ids[0]
                                pol_obj.write(cr, uid, [po_line_id], {'product_id': nml.get('product_id'),
                                                                        'quantity': nml.get('product_qty')})
                                pol_product_id = pol_obj.browse(cr, uid, po_line_id)
                                error_list.append("Line %s of the Excel file: The product did not match with the existing product of the line %s so we change the product from %s to %s." % 
                                                  (nml.get('file_line_num'), ln, pol_product_id.product_id.default_code, product_obj.browse(cr, uid, nml.get('product_id')).default_code))
                                matching_wiz_lines.append(po_line_id)
                                complete_lines += 1
                                del nm_lines[ln][index]
                                continue
                            # Increase the index
                            index += 1


#            else:
#                # lines ignored if they don't have the same line number as the line of the wizard
#                if line_num not in line_ignored_num:
#                    error_list.append("Line %s of the Excel file was added to the file of the lines with errors. It does not correspond to any line number." % (file_line_num))
#                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb, error_list, line_num, context))
#                    ignore_lines += 1
#                    line_ignored_num.append(line_num)

#                except Exception, e:
#                    error_log += "Line %s ignored: an error appeared in the Excel file. Details: %s\n" % (line_num, e)
#                    ignore_lines += 1
#                    continue
        error_log += '\n'.join(error_list)
        if error_log:
            error_log = "Reported errors for ignored lines : \n" + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + ' second(s)'
        message = ''' Importation completed in %s!
# of imported lines : %s
# of ignored lines: %s
%s
''' % (total_time ,complete_lines, ignore_lines, error_log)
#        try:
        wizard_vals = {'message': message, 'state': 'done'}
        if line_with_error:
            file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
            wizard_vals.update(file_to_export)
        self.write(cr, uid, ids, wizard_vals, context=context)
#        cr.commit()
#        cr.close()
#        except Exception, e:
#            raise osv.except_osv(_('Error !'), _('%s !') % e)

#    def import_file(self, cr, uid, ids, context=None):
#        """
#        Launch a thread for importing lines.
#        """
#        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
#        thread.start()
#        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
#        Otherwise, you can continue to use Unifield.""")
#        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
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
    
wizard_import_po()


class wizard_export_po(osv.osv_memory):
    _name = 'wizard.export.po'
    _description = 'Export PO for integration'
    
    _columns = {
        'po_id': fields.many2one('purchase.order', string='PO'),
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }
    
    def close_window(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        res_id = self.browse(cr, uid, ids[0], context=context).po_id.id
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'res_id': res_id}   
        
wizard_export_po()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
