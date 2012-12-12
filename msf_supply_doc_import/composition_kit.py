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
import time


class composition_kit(osv.osv):
    _inherit = 'composition.kit'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n 
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : 
                                        Module, Product Code*, Product Description*, Quantity and Product UOM"""),
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
        item_kit_id = ids[0]

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        line_obj = self.pool.get('composition.item')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'kit', 'view_composition_kit_form')[1]

        ignore_lines, complete_lines = 0, 0
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
                'item_qty': 0,
                'error_list': [],
                'warning_list': [],
            }
            item_qty = 0
            module = ''
            batch = False
            expiry_date = False
            line_num += 1
            # Check length of the row
            if len(row) != 5:
                raise osv.except_osv(_('Error'), _("""You should have exactly 5 columns in this order:
Module, Product Code*, Product Description*, Quantity and Product UOM""" % line_num))

            # Cell 0: Module
            if row.cells[0] and row.cells[0].data:
                module = row.cells[0].data

            # Cell 1: Product Code
            p_value = {}
            p_value = product_value(cr, uid, cell_nb=1, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            if p_value['default_code']:
                product_id = p_value['default_code']
            else:
                product_id = False
                error += 'Line %s in your Excel file: Product Code [%s] not found ! Details: %s \n' % (line_num, row[1], p_value['error_list'])
                ignore_lines += 1
                continue

            # Cell 3: Quantity
            if row.cells[3] and row.cells[3].data:
                try:
                    item_qty = float(row.cells[3].data)
                except ValueError as e:
                    error += "Line %s in your Excel file: the Quantity should be a number and not %s. Details: %s\n" % (line_num, row.cells[3].data, e)
                    ignore_lines += 1
                    continue
            else:
                item_qty = 0

            # Cell 4: UOM
            uom_value = {}
            uom_value = compute_uom_value(cr, uid, cell_nb=4, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
            if uom_value['uom_id'] and uom_value['uom_id'] != obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]:
                item_uom_id = uom_value['uom_id']
            else:
                item_uom_id = False
                error += 'Line %s in your Excel file: UoM %s not found ! Details: %s' % (line_num, row[4], uom_value['error_list'])
                ignore_lines += 1
                continue

            line_data = {'item_product_id': product_id,
                         'item_uom_id': item_uom_id,
                         'prodlot_id': batch,
                         'expiry_date': expiry_date,
                         'item_qty': item_qty,
                         'module': module,
                         'item_kit_id': item_kit_id}

            context['import_in_progress'] = True
            try:
                line_obj.create(cr, uid, line_data)
                complete_lines += 1
            except osv.except_osv:
                error += "Line %s in your Excel file: Warning, not enough quantity in stock\n" % (line_num, )

        if complete_lines or ignore_lines:
            self.log(cr, uid, obj.id, _("%s lines have been imported and %s lines have been ignored" % (complete_lines, ignore_lines)), context={'view_id': view_id, })
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
        vals['composition_item_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.composition_item_ids
            for var in line_browse_list:
                vals['composition_item_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
            self.remove_error_message(cr, uid, ids, context)
        return True

    def remove_error_message(self, cr,uid, ids, context=None):
        vals = {'text_error': False, 'to_correct_ok': False}
        return self.write(cr, uid, ids, vals, context=context)

composition_kit()