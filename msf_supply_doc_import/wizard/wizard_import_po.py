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

from osv import osv, fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import time
from msf_supply_doc_import import check_line

class wizard_import_po(osv.osv_memory):
    _name = 'wizard.import.po'
    _description = 'Import PO from Excel sheet'
    
    _columns = {
        'file': fields.binary(string='File to import', required=True),
        'message': fields.text(string='Message', readonly=True),
        'po_id': fields.many2one('purchase.order', string='Purchase Order', required=True),
    }
    
    _defaults = {
        'message': lambda *a : """
        IMPORTANT : The first line will be ignored by the system.
        
        The file should be in XML 2003 format.
        The columns should be in this order :
           Line, Product Code, Product Description, Quantity, UoM, Price, Delivery Requested Date, Currency, Comment
        """
    }
    
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
            
        return res

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

    def check_header_values(self, header_index):
        """
        Check that the columns in the header will be taken into account.
        """
        columns_imported = ['Order Reference', 'Line', 'Product Code', 'Quantity', 'UoM', 'Price', 'Delivery requested date', 'Currency', 'Comment', 'Supplier Reference',
                            'Delivery Confirmed Date', 'Est. Transport Lead Time', 'Transport Mode', 'Arrival Date in the country', 'Incoterm']
        for k,v in header_index.items():
            if k not in columns_imported:
                raise osv.except_osv(_('Error'), _('The column %s is not taken into account. Please remove it.' % k))

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import file
        '''
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
        
        for wiz_browse in self.browse(cr, uid, ids, context):
            if not wiz_browse.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            po_browse = wiz_browse.po_id
            po_id = po_browse.id
            po_line_browse = po_browse.order_line
            list_line_nb = [line.line_number for line in po_line_browse]
            
            ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
            error_list = []
            error_log = ''
            line_num = 0
            
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
            # iterator on rows
            reader = fileobj.getRows()
            reader_iterator = iter(reader)
            # get first line
            first_row = next(reader_iterator)
            header_index = self.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=line_num, context=context)
            self.check_header_values(header_index)

            for line in po_line_browse:
                line_num += 1
                rows = fileobj.getRows()
                rows.next()
                file_line_num = 1
                first_same_line_nb = True
                for row in rows:
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
                    line_data = {}
                    file_line_num += 1
                    # Cell 0: Line Number
                    # Line
                    cell_nb = header_index['Line']
                    line_number = int(self.get_cell_data(cr, uid, ids, row, cell_nb, to_write['error_list'], line_num, context))
                    to_write.update({'line_number': line_number})
                    if line_number in list_line_nb:
                        if line_number == line.line_number:
                            try:
                                # Quantity => we need it for the split
                                qty_value = {}
                                cell_nb = header_index['Quantity']
                                qty_value = check_line.quantity_value(product_obj=product_obj, cell_nb=cell_nb, row=row, to_write=to_write, context=context)
                                to_write.update({'product_qty': qty_value['product_qty'], 'error_list': qty_value['error_list'],
                                                 'warning_list': qty_value['warning_list']})
                                if not first_same_line_nb:
                                    # if the line imported is not the first to update the line_number, we split it
                                    wizard_values = purchase_line_obj.open_split_wizard(cr, uid, line.id, context)
                                    wiz_context = wizard_values.get('context')
                                    self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']],
                                                                                    {'new_line_qty': qty_value['product_qty']}, context=wiz_context)
                                    self.pool.get(wizard_values['res_model']).split_line(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                    error_list.append("Line %s of the Excel file produced a split for the line %s." % (file_line_num, line_number))
                                    # the line that will be updated changed, we take the last created
                                    new_line_id = purchase_line_obj.search(cr, uid, [('line_number', '=', line_number), ('order_id', '=', po_id)])[-1]
                                    line = purchase_line_obj.browse(cr, uid, new_line_id)
                            
                                # Product Code
                                p_value = {}
                                cell_nb = header_index['Product Code']
                                p_value = check_line.product_value(cr, uid, cell_nb=cell_nb, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                                to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'],
                                                 'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})
                
                                # UOM
                                uom_value = {}
                                cell_nb = header_index['UoM']
                                uom_value = check_line.compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, cell_nb=cell_nb, row=row, to_write=to_write, context=context)
                                to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})
                
                                # Price
                                price_value = {}
                                cell_nb = header_index['Price']
                                price_value = check_line.compute_price_value(row=row, to_write=to_write, cell_nb=cell_nb, price='Cost Price', context=context)
                                to_write.update({'price_unit': price_value['price_unit'], 'error_list': price_value['error_list'],
                                                 'warning_list': price_value['warning_list'], 'price_unit_defined': price_value['price_unit_defined']})
                
                                #  Delivery Request Date
                                date_value = {}
                                cell_nb = header_index['Delivery requested date']
                                date_value = check_line.compute_date_value(cell_nb=cell_nb, row=row, to_write=to_write, context=context)
                                to_write.update({'date_planned': date_value['date_planned'], 'error_list': date_value['error_list']})
                
                                #  Currency
                                curr_value = {}
                                cell_nb = header_index['Currency']
                                curr_value = check_line.compute_currency_value(cr, uid, cell_nb=cell_nb, browse_purchase=po_browse,
                                                                    currency_obj=currency_obj, row=row, to_write=to_write, context=context)
                                to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})
                
                                #  Comment
                                c_value = {}
                                cell_nb = header_index['Comment']
                                c_value = check_line.comment_value(row=row, cell_nb=cell_nb, to_write=to_write, context=context)
                                to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
                                to_write.update({
                                    'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
                                    'show_msg_ok': [True for x in to_write['warning_list']],  # the lines with show_msg_ok=True won't change color, it is just info
                                    'order_id': po_id,
                                    'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
                                })
                                # we check consistency on the model of on_change functions to call for updating values
                                purchase_line_obj.check_line_consistency(cr, uid, po_id, to_write=to_write, context=context)
        
                                purchase_line_obj.write(cr, uid, line.id, to_write, context)
                                first_same_line_nb = False
                                complete_lines += 1
                
                            except IndexError, e:
                                error_log += "The line num %s in the Excel file got element outside the defined 8 columns. Details: %s" % (line_num, e)
                                ignore_lines += 1
                                continue
#                except Exception, e:
#                    error_log += "Line %s ignored: an error appeared in the Excel file. Details: %s\n" % (line_num, e)
#                    ignore_lines += 1
#                    continue
        if error_log:
            error_log = "Reported errors for ignored lines : \n" + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + ' second(s)'
        wizard_vals = {'message': ''' Importation completed in %s!
# of imported lines : %s
# of ignored lines: %s
%s
''' % (total_time ,complete_lines or 'No error !', ignore_lines, error_log)}
#        try:
        self.write(cr, uid, ids, wizard_vals, context=context)
        view_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'wizard_to_import_po_end')[1],
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.po',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                'view_id': [view_id],
                }
#        except Exception, e:
#            raise osv.except_osv(_('Error !'), _('%s !') % e)
        
    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return {'type': 'ir.actions.act_window_close'}
    
wizard_import_po()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
