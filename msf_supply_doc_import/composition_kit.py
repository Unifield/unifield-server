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


class composition_kit(osv.osv):
    _inherit = 'composition.kit'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.composition_item_ids if item.to_correct_ok]):
                res[obj.id] = True
        return res

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n 
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : 
                                        Module, Product Code*, Product Description, Quantity and Product UOM"""),
        'text_error': fields.text('Errors when trying to import file', readonly=1),
        'to_correct_ok': fields.boolean('To correct', readonly=1),
        'hide_column_error_ok': fields.function(get_bool_values, method=True, type="boolean", string="Show column errors", store=False),
    }

    def mark_as_completed(self, cr, uid, ids, context=None):
        """
        Check that there isn't error
        """
        res = super(composition_kit, self).mark_as_completed(cr, uid, ids, context=context)
        for obj in self.browse(cr, uid, ids, context=context):
            if any([item for item in obj.composition_item_ids if item.to_correct_ok]):
                raise osv.except_osv(_('Warning !'), _('Please fix the line with errors (red lines)'))
        return res

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        item_kit_id = ids[0]

        # erase previous error messages
        self.remove_error_message(cr, uid, ids, context)

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        line_obj = self.pool.get('composition.item')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'kit', 'view_composition_kit_form')[1]

        complete_lines = 0
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
                'default_code': obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'product_tbd')[1],
                'uom_id': obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1],
                'product_qty': 1,
                'error_list': [],
                'warning_list': [],
            }
            module = ''
            line_num += 1
            # Check length of the row
            col_count = len(row)
            if col_count != 5:
                raise osv.except_osv(_('Error'), _("""You should have exactly 5 columns in this order:
Module, Product Code*, Product Description, Quantity and Product UOM"""))

            if not check_line.check_empty_line(row=row, col_count=col_count):
                continue

            # Cell 0: Module
            if row.cells[0] and row.cells[0].data:
                module = row.cells[0].data

            # Cell 1: Product Code
            p_value = {}
            p_value = check_line.product_value(cr, uid, cell_nb=1, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            to_write.update({'product_id': p_value['default_code'], 'error_list': p_value['error_list']})

            # Cell 3: Quantity
            qty_value = {}
            qty_value = check_line.quantity_value(cell_nb=3, product_obj=product_obj, row=row, to_write=to_write, context=context)
            to_write.update({'qty': qty_value['product_qty'], 'error_list': qty_value['error_list'], 'warning_list': qty_value['warning_list']})

            # Cell 4: UOM
            uom_value = {}
            uom_value = check_line.compute_uom_value(cr, uid, cell_nb=4, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
            to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})

            line_data = {'item_product_id': to_write['default_code'],
                         'item_uom_id': to_write['product_uom'],
                         'item_qty': to_write['qty'],
                         'item_module': module,
                         'item_kit_id': item_kit_id,
                         'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
                         'text_error': '\n'.join(to_write['error_list'])}

            context['import_in_progress'] = True
            try:
                line_obj.create(cr, uid, line_data)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                error += "Line %s in your Excel file: %s: %s\n" % (line_num, osv_name, osv_value)
            complete_lines += 1

        if complete_lines:
            if complete_lines == 1:
                self.log(cr, uid, obj.id, _("%s line has been imported" % (complete_lines)), context={'view_id': view_id, })
            else:
                self.log(cr, uid, obj.id, _("%s lines have been imported" % (complete_lines)), context={'view_id': view_id, })
        if error:
            self.write(cr, uid, ids, {'text_error': error, 'to_correct_ok': True}, context=context)
        return True

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove all lines
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
        """
        Remove error of import lines
        """
        vals = {'text_error': False, 'to_correct_ok': False}
        return self.write(cr, uid, ids, vals, context=context)

composition_kit()


class composition_item(osv.osv):
    '''
    override of composition_item class
    '''
    _inherit = 'composition.item'
    _description = 'Composition Item Line'
    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'text_error': fields.text('Errors', readonly=True),
    }

    def onchange_uom(self, cr, uid, ids, product_id, product_uom, context=None):
        '''
        Check if the UoM is convertible to product standard UoM
        '''
        warning = {}
        if product_uom and product_id:
            product_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            product = product_obj.browse(cr, uid, product_id, context=context)
            uom = uom_obj.browse(cr, uid, product_uom, context=context)
            if product.uom_id.category_id.id != uom.category_id.id:
                warning = {'title': 'Wrong Product UOM !',
                           'message': "You have to select a product UOM in the same category than the purchase UOM of the product"}
        return {'warning': warning}

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        if not context.get('import_in_progress') and not context.get('button'):
            obj_data = self.pool.get('ir.model.data')
            tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]
            tbd_product = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'product_tbd')[1]
            message = ''
            if vals.get('item_uom_id'):
                if vals.get('item_uom_id') == tbd_uom:
                    message += 'You have to define a valid UOM, i.e. not "To be define".'
            if vals.get('item_product_id'):
                if vals.get('item_product_id') == tbd_product:
                    message += 'You have to define a valid product, i.e. not "To be define".'
            if vals.get('item_uom_id') and vals.get('item_product_id'):
                product_id = vals.get('item_product_id')
                product_uom = vals.get('item_uom_id')
                res = self.onchange_uom(cr, uid, ids, product_id, product_uom, context)
                if res and res['warning']:
                    message += res['warning']['message']
            if message:
                raise osv.except_osv(_('Warning !'), _(message))
            else:
                vals['to_correct_ok'] = False
                vals['text_error'] = False
        return super(composition_item, self).write(cr, uid, ids, vals, context=context)

composition_item()