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
from . import check_line


class composition_kit(osv.osv):
    _inherit = 'composition.kit'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.composition_item_ids if item.to_correct_ok]):
                res[obj.id] = True
        return res

    _columns = {
        'real_file_to_import': fields.binary(string='File to import', filters='*.xml',
                                             help="""You can use the template of the export for the format that you need to use. \n 
                                             The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : 
                                             Module*, Product Code*, Product Description*, Quantity*, Product UoM*, Asset, Batch Number and Expiry Date"""),
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n 
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : 
                                        Module*, Product Code*, Product Description*, Quantity* and Product UoM*"""),
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
        if isinstance(ids, int):
            ids = [ids]
        item_kit_id = ids[0]

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
        if obj.state != 'draft':
            raise osv.except_osv(_('Error'), _('You can only import on a Draft Theoretical Kit Composition; import file is ignored'))

        fileobj = SpreadsheetXML(xmlstring=base64.b64decode(obj.file_to_import))

        # iterator on rows
        rows = fileobj.getRows()

        # ignore the first row
        next(rows)
        line_num = 1
        to_write = {}
        for row in rows:
            # default values
            to_write = {
                'default_code': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1],
                'uom_id': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1],
                'product_qty': 1,
                'error_list': [],
                'warning_list': [],
            }
            module = ''
            line_num += 1
            # Check length of the row
            col_count = len(row)
            if col_count != 8:
                raise osv.except_osv(_('Error'), _("""You should have exactly 8 columns in this order:
Module, Product Code*, Product Description, Quantity, Product UOM, Comment, B.Num mandatory and Exp. Date mandatory"""))

            if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
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
            qty = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, uom_value['uom_id'], qty_value['product_qty'])
            to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list'], 'qty': qty})

            # Cell 5: Comment
            to_write.update({'comment': row.cells[5] and row.cells[5].data or ''})

            line_data = {'item_product_id': to_write['product_id'],
                         'item_uom_id': to_write['product_uom'],
                         'item_qty': to_write['qty'],
                         'item_module': module,
                         'item_kit_id': item_kit_id,
                         'comment': to_write['comment'],
                         'to_correct_ok': any(to_write['error_list']),  # the lines with to_correct_ok=True will be red
                         'text_error': '\n'.join(to_write['error_list'])}

            context['import_in_progress'] = True
            try:
                line_obj.create(cr, uid, line_data)
                complete_lines += 1
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                error += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)

        if complete_lines or error:
            self.log(cr, uid, obj.id, _("# lines imported: %s. %s") % (complete_lines, error or ''), context={'view_id': view_id, })
        return True

    def import_file_real(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        item_kit_id = ids[0]

        product_obj = self.pool.get('product.product')
        asset_obj = self.pool.get('product.asset')
        uom_obj = self.pool.get('product.uom')
        line_obj = self.pool.get('composition.item')
        bn_obj = self.pool.get('stock.production.lot')
        cell_data_obj = self.pool.get('import.cell.data')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'kit', 'view_composition_kit_form')[1]

        complete_lines = 0
        error = ''

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.real_file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        if obj.state != 'draft':
            raise osv.except_osv(_('Error'), _('You can only import on a Draft Kit Composition List; import file is ignored'))

        fileobj = SpreadsheetXML(xmlstring=base64.b64decode(obj.real_file_to_import))

        # iterator on rows
        rows = fileobj.getRows()

        # ignore the first row
        next(rows)
        line_num = 1
        to_write = {}
        for row in rows:
            # default values
            to_write = {
                'default_code': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1],
                'uom_id': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1],
                'product_qty': 1,
                'error_list': [],
                'warning_list': [],
            }
            module = ''
            line_num += 1
            # Check length of the row
            col_count = len(row)
            if col_count < 5 or col_count > 11:
                raise osv.except_osv(_('Error'), _("""You should have exactly 11 columns in this order:
Module*, Product Code*, Product Description*, Quantity*, Product UOM*, Comment, Asset, Batch Number, Expiry Date, B.Num mandatory and Exp. Date mandatory"""))

#            if not check_line.check_empty_line(row=row, col_count=col_count):
#                continue

            # Cell 0: Module
            cell_nb = 0
            module = cell_data_obj.get_cell_data(cr, uid,  ids, row, cell_nb)

            # Cell 1: Product Code
            p_value = check_line.product_value(cr, uid, cell_nb=1, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            to_write.update({'product_id': p_value['default_code'], 'error_list': p_value['error_list']})

            # Cell 3: Quantity
            qty_value = check_line.quantity_value(cell_nb=3, product_obj=product_obj, row=row, to_write=to_write, context=context)
            to_write.update({'qty': qty_value['product_qty'], 'error_list': qty_value['error_list'], 'warning_list': qty_value['warning_list']})

            # Cell 4: UOM
            uom_value = check_line.compute_uom_value(cr, uid, cell_nb=4, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
            qty = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, uom_value['uom_id'], qty_value['product_qty'])
            to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list'], 'qty': qty})

            # Cell 5: Comment
            to_write.update({'comment': row.cells[5] and row.cells[5].data or ''})

            # Cell 6: Asset
            if col_count > 6 and row[6]:
                asset_value = check_line.compute_asset_value(cr, uid, cell_nb=6, asset_obj=asset_obj, row=row, to_write=to_write, context=context)
                to_write.update({'asset_id': asset_value['asset_id'], 'error_list': asset_value['error_list']})

            # Cells 7 & 8: Batch and Expiry Date
            if to_write.get('product_id'):
                product = product_obj.read(cr, uid, to_write['product_id'], ['batch_management', 'perishable'], context=context)
                if product['batch_management'] or product['perishable']:
                    batch_value = check_line.compute_batch_expiry_value(
                        cr, uid, row=row, to_write=to_write, bn_obj=bn_obj, product_obj=product_obj, bn_cell_nb=7,
                        ed_cell_nb=8, date_format=self.pool.get('date.tools').get_date_format(cr, uid, context=context),
                        product_id=to_write.get('product_id'), picking_type=None)

                    # Create the internal batch number if not exists
                    if not product['batch_management'] and product['perishable'] and batch_value['expired_date'] and \
                            not batch_value['prodlot_id'] and not batch_value['error_list']:
                        batch_value['prodlot_id'] = bn_obj.create(cr, uid, {
                            'type': 'internal', 'product_id': product['id'], 'life_date': batch_value['expired_date'],
                            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial')}, context=context)

                    to_write.update({'prodlot_id': batch_value['prodlot_id'], 'expiry_date': batch_value['expired_date'], 'error_list': batch_value['error_list']})

            line_data = {'item_kit_id': item_kit_id,
                         'item_module': module,
                         'item_product_id': to_write['product_id'],
                         'item_qty': to_write['qty'],
                         'item_uom_id': to_write['product_uom'],
                         'comment': to_write['comment'],
                         'item_asset_id': 'asset_id' in to_write and to_write['asset_id'] or False,
                         'item_lot_id': to_write.get('prodlot_id', False),
                         'item_exp': to_write.get('expiry_date', False),
                         'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
                         'text_error': '\n'.join(to_write['error_list'])}

            context['import_in_progress'] = True
            try:
                line_obj.create(cr, uid, line_data)
                complete_lines += 1
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                error += _("Line %s in your Excel file: %s: %s\n") % (line_num, osv_name, osv_value)

        if complete_lines or error:
            self.log(cr, uid, obj.id, _("# lines imported: %s. %s") % (complete_lines, error or ''), context={'view_id': view_id, })
        return True

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
            if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, product_uom, context):
                warning = {'title': _('Wrong Product UOM !'),
                           'message': _("You have to select a product UOM in the same category than the UOM of the product")}
        return {'warning': warning}

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        if not context.get('import_in_progress') and not context.get('button'):
            obj_data = self.pool.get('ir.model.data')
            tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
            tbd_product = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
            message = ''
            if vals.get('item_uom_id'):
                if vals.get('item_uom_id') == tbd_uom:
                    message += _('You have to define a valid UOM, i.e. not "To be define".')
            if vals.get('item_product_id'):
                if vals.get('item_product_id') == tbd_product:
                    message += _('You have to define a valid product, i.e. not "To be define".')
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
