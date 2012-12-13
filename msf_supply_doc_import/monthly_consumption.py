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
from check_line import *


class monthly_review_consumption(osv.osv):
    _inherit = 'monthly.review.consumption'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml', 
                                        help="""You can use the template of the export for the format that you need to use. \n 
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order :
                                        Product Code*, Product Description*, AMC, FMC, Valid Until"""),
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
        mrc_id = ids[0]

        # erase previous error messages
        self.remove_error_message(cr, uid, ids, context)

        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('monthly.review.consumption.line')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'consumption_calculation', 'monthly_review_consumption_form_view')[1]

        vals = {}
        vals['line_ids'] = []
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
                'error_list': [],
                'default_code': False,
            }
            fmc = 0
            valid_until = False
            line_num += 1
            # Check length of the row
            if len(row) != 5:
                raise osv.except_osv(_('Error'), _("""You should have exactly 5 columns in this order:
Product Code*, Product Description*, AMC, FMC, Valid Until"""))

            # Cell 0: Product Code
            p_value = {}
            p_value = product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            if p_value['default_code']:
                product_id = p_value['default_code']
            else:
                product_id = False
                error += 'Line %s in your Excel file: Product Code [%s] not found ! Details: %s \n' % (line_num, row[0], p_value['error_list'])
                ignore_lines += 1
                continue

            # Cell 3: Quantity (FMC)
            if row.cells[3] and row.cells[3].data:
                if row.cells[3].type in ('int', 'float'):
                    fmc = row.cells[3].data
                elif isinstance(row.cells[3].data, (int, long, float)):
                    fmc = row.cells[3].data
                else:
                    error += "Line %s in your Excel file: FMC should be a number and not %s \n" % (line_num, row.cells[3].data)
                    ignore_lines += 1
                    continue

            # Cell 4: Date (Valid Until)
            if row[4] and row[4].data:
                if row[4].type in ('datetime', 'date'):
                    valid_until = row[4].data
                else:
                    try:
                        valid_until = time.strftime('%Y-%m-%d', time.strptime(str(row[4]), '%d/%m/%Y'))
                    except ValueError:
                        try:
                            valid_until = time.strftime('%Y-%b-%d', time.strptime(str(row[4]), '%d/%b/%Y'))
                        except ValueError as e:
                            error += "Line %s in your Excel file: expiry date %s has a wrong format. Details: %s' \n" % (line_num, row[4], e)

            line_data = {'name': product_id,
                         'fmc': fmc,
                         'mrc_id': mrc_id,
                         'valid_until': valid_until,}

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
            self.log(cr, uid, obj.id, _("%s lines have been imported, %s lines have been ignored and %s line(s) with error(s)" % (complete_lines, ignore_lines, lines_with_error)), context={'view_id': view_id, })
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

monthly_review_consumption()
