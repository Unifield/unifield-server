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


class real_average_consumption(osv.osv):
    _inherit = 'real.average.consumption'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : Product Code*, Product Description*, Comment'),
    }

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'consumption_calculation', 'real_average_consumption_form_view')[1]

        vals = {}
        vals['line_ids'] = []

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
            browse_obj = self.browse(cr, uid, ids, context=context)[0]
            to_write = {
                'error_list': [],
                'warning_list': [],
                'to_correct_ok': False,
                'show_msg_ok': False,
                'default_code': False,
                'consumed_qty': 0,
            }
            line_num += 1
            # Check length of the row
            if len(row) != 7:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order::
Product Code*, Product Description*, Product UOM, Batch Number, Expiry Date, Consumed Quantity, Remark""" % line_num))

            # Cell 0: Product Code
            p_value = {}
            p_value = product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            to_write.update({'product_id': p_value['default_code'], 'error_list': p_value['error_list']})

            # Cell 2: UOM
            uom_value = {}
            uom_value = compute_uom_value(cr, uid, cell_nb=2, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
            to_write.update({'uom_id': uom_value['uom_id'], 'error_list': uom_value['error_list']})

            # Cell 3: Batch (Prodlot_id)
#            batch = {}
#            batch = batch_value(product_obj=product_obj, row=row, to_write=to_write, context=context)
#            to_write.update({'prodlot_id': qty_value['prodlot_id'], 'error_list': qty_value['error_list']})

            # Cell 5: Quantity
            qty_value = {}
            qty_value = quantity_value(real_consumption=True, cell_nb=5, product_obj=product_obj, row=row, to_write=to_write, context=context)
            to_write.update({'consumed_qty': qty_value['product_qty'], 'error_list': qty_value['error_list']})

            vals['line_ids'].append((0, 0, to_write))
        # write Real Average Consumption Line
        context['import_in_progress'] = True
        self.write(cr, uid, ids, vals, context=context)
        msg_to_return = get_log_message(real_consumption=True, to_write=to_write, obj=obj)
        if msg_to_return:
            self.log(cr, uid, obj.id, _(msg_to_return), context={'view_id': view_id, })
        return True

real_average_consumption()


class real_average_consumption_line(osv.osv):
    _inherit = 'real.average.consumption.line'

    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'show_msg_ok': fields.boolean('Info on importation of lines'),
        'text_error': fields.text('Errors when trying to import file'),
    }

real_average_consumption_line()