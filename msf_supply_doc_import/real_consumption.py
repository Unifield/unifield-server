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
import check_line
import time


class real_average_consumption(osv.osv):
    _inherit = 'real.average.consumption'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n 
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : 
                                        Product Code*, Product Description*, Product UOM, Batch Number, Expiry Date, Consumed Quantity, Remark"""),
        'text_error': fields.text('Errors when trying to import file', readonly=1),
        'to_correct_ok': fields.boolean('To correct', readonly=1),
    }

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        rac_id = ids[0]

        # erase previous error messages
        self.remove_error_message(cr, uid, ids, context)

        product_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')
        line_obj = self.pool.get('real.average.consumption.line')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'consumption_calculation', 'real_average_consumption_form_view')[1]

        ignore_lines, complete_lines, lines_with_error = 0, 0, 0
        error = ''

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))

        # iterator on rows
        rows = fileobj.getRows()
        
        # ignore the first row
        rows.next()
        line_num = 1
        to_write = {}
        for row in rows:
            # default values
            to_write = {
                'default_code': False,
                'uom_id': False,
                'consumed_qty': 0,
                'error_list': [],
                'warning_list': [],
            }
            consumed_qty = 0
            remark = ''
            batch = False
            expiry_date = False
            line_num += 1
            # Check length of the row
            if len(row) != 7:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code*, Product Description*, Product UOM, Batch Number, Expiry Date, Consumed Quantity, Remark"""))

            # Cell 0: Product Code
            p_value = {}
            p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            if p_value['default_code']:
                product_id = p_value['default_code']
                to_write.update({'product_id': product_id})
                # Cell 3: Batch Number
                prod = product_obj.browse(cr, uid, product_id)
                if prod.batch_management:
                    if prod.batch_management and not row[3]:
                        error += "Line %s in your Excel file: batch number required, please fix the line below with the product\n" % (line_num, prod.default_code)
                    if row[3]:
                        lot = prodlot_obj.search(cr, uid, [('name', '=', row[3])])
                        if not lot:
                            error += "Line %s in your Excel file: batch number %s not found.\n" % (line_num, row[3])
                        else:
                            batch = lot[0]
                if prod.perishable:
                    if not row[4]:
                        error += "Line %s in your Excel file  : expiry date required\n" % (line_num, )
                    elif row[4] and row[4].data:
                        if row[4].type in ('datetime', 'date'):
                            expiry_date = row[4].data
                        else:
                            try:
                                expiry_date = time.strftime('%d/%b/%Y', time.strptime(str(row[4]), '%d/%m/%Y'))
                            except ValueError:
                                try:
                                    expiry_date = time.strftime('%d/%b/%Y', time.strptime(str(row[4]), '%d/%b/%Y'))
                                except ValueError as e:
                                    error += "Line %s in your Excel file: expiry date %s has a wrong format (day/month/year). Details: %s' \n" % (line_num, row[4], e)
                    if not batch and product_id and expiry_date:
                        batch_list = self.pool.get('stock.production.lot').search(cr, uid, [('product_id', '=', product_id),
                                                                                            ('life_date', '=', expiry_date)])
                        if batch_list:
                            batch = batch_list[0]
            else:
                product_id = False
                error += 'Line %s in your Excel file ignored: Product Code [%s] not found ! Details: %s \n' % (line_num, row[0], p_value['error_list'])
                ignore_lines += 1
                continue

            # Cell 2: UOM
            uom_value = {}
            uom_value = check_line.compute_uom_value(cr, uid, cell_nb=2, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
            if uom_value['uom_id'] and uom_value['uom_id'] != obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]:
                uom_id = uom_value['uom_id']
            else:
                uom_id = False
                error += 'Line %s in your Excel file ignored: UoM %s not found ! Details: %s' % (line_num, row[2], uom_value['error_list'])
                ignore_lines += 1
                continue

            # Cell 5: Quantity
            if row.cells[5] and row.cells[5].data:
                try:
                    consumed_qty = float(row.cells[5].data)
                except ValueError as e:
                    error += "Line %s in your Excel file ignored: the Consumed Quantity should be a number and not %s \n. Details: %s" % (line_num, row.cells[5].data, e)
                    ignore_lines += 1
                    continue
            else:
                consumed_qty = 0

            # Cell 6: Remark
            if row.cells[6] and row.cells[6].data:
                remark = row.cells[6].data

            line_data = {'product_id': product_id,
                         'uom_id': uom_id,
                         'prodlot_id': batch,
                         'expiry_date': expiry_date,
                         'consumed_qty': consumed_qty,
                         'remark': remark,
                         'rac_id': rac_id}

            context['import_in_progress'] = True
            try:
                line_obj.create(cr, uid, line_data)
            except osv.except_osv as osv_error:
                lines_with_error += 1
                osv_value = osv_error.value
                osv_name = osv_error.name
                error += "Line %s in your Excel file: %s: %s\n" % (line_num, osv_name, osv_value)
            complete_lines += 1

        if complete_lines or ignore_lines:
            self.log(cr, uid, obj.id, _("%s line(s) imported, %s line(s) ignored and %s line(s) with error(s)" % (complete_lines, ignore_lines, lines_with_error)), context={'view_id': view_id, })
        if error:
            self.write(cr, uid, ids, {'text_error': error, 'to_correct_ok': True}, context=context)
        return True

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals = {}
        vals['line_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.line_ids
            for var in line_browse_list:
                vals['line_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
            self.remove_error_message(cr, uid, ids, context)
        return True

    def remove_error_message(self, cr,uid, ids, context=None):
        """
        Remove error of import lines
        """
        vals = {'text_error': False, 'to_correct_ok': False}
        return self.write(cr, uid, ids, vals, context=context)

real_average_consumption()