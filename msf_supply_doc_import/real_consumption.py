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

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.line_ids  if item.to_correct_ok]):
                res[obj.id] = True
        return res

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n 
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : 
                                        Product Code*, Product Description*, Product UOM, Batch Number, Expiry Date, Consumed Quantity, Remark"""),
        'hide_column_error_ok': fields.function(get_bool_values, method=True, type="boolean", string="Show column errors", store=False),
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

        product_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')
        line_obj = self.pool.get('real.average.consumption.line')
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'consumption_calculation', 'real_average_consumption_form_view')[1]

        complete_lines, lines_with_error = 0, 0
        error_log = ''

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
                'consumed_qty': 0,
                'error_list': [],
                'warning_list': [],
            }
            consumed_qty = 0
            remark = ''
            error = ''
            batch = False
            expiry_date = False
            line_num += 1
            # Check length of the row
            col_count = len(row)
            if col_count != 7:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code*, Product Description*, Product UOM, Batch Number, Expiry Date, Consumed Quantity, Remark"""))
            try:
                if not check_line.check_empty_line(row=row, col_count=col_count):
                    continue
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
                            error += "Line %s in your Excel file: batch number required\n" % (line_num, prod.default_code)
                        if row[3]:
                            lot = prodlot_obj.search(cr, uid, [('name', '=', row[3])])
                            if not lot:
                                error += "Line %s in your Excel file: batch number %s not found.\n" % (line_num, row[3])
                            else:
                                batch = lot[0]
                    if prod.perishable:
                        if not row[4] or str(row[4]) == str(None):
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
                    error += 'Line %s in your Excel file: Product Code [%s] not found ! Details: %s \n' % (line_num, row[0], p_value['error_list'])
    
                # Cell 2: UOM
                uom_value = {}
                uom_value = check_line.compute_uom_value(cr, uid, cell_nb=2, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                if uom_value['uom_id'] and uom_value['uom_id'] != obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]:
                    uom_id = uom_value['uom_id']
                else:
                    uom_id = False
                    error += 'Line %s in your Excel file: UoM %s not found ! Details: %s' % (line_num, row[2], uom_value['error_list'])
    
                # Cell 5: Quantity
                if row.cells[5] and row.cells[5].data:
                    try:
                        consumed_qty = float(row.cells[5].data)
                    except ValueError as e:
                        error += "Line %s in your Excel file: the Consumed Quantity should be a number and not %s \n. Details: %s" % (line_num, row.cells[5].data, e)
                else:
                    consumed_qty = 0
    
                # Cell 6: Remark
                if row.cells[6] and row.cells[6].data:
                    remark = row.cells[6].data
                error += '\n'.join(to_write['error_list'])
                line_data = {'product_id': product_id,
                             'uom_id': uom_id,
                             'prodlot_id': batch,
                             'expiry_date': expiry_date,
                             'consumed_qty': consumed_qty,
                             'remark': remark,
                             'rac_id': rac_id,
                             'text_error': error,
                             'to_correct_ok': [True for x in error],}  # the lines with to_correct_ok=True will be red}
    
                context['import_in_progress'] = True
                line_obj.create(cr, uid, line_data)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                error_log += "Line %s in your Excel file: %s: %s\n" % (line_num, osv_name, osv_value)
                lines_with_error += 1
            complete_lines += 1

        if complete_lines:
            self.log(cr, uid, obj.id, _("""
                                        %s line(s) imported and %s line(s) with error(s) \n 
                                        %s
                                        """ % (complete_lines, lines_with_error, error_log)), context={'view_id': view_id, })
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
        return True

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        """
        Check both the lines that need to be corrected and also that the supplier or the address is not 'To be defined'
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural= ''
        obj_data = self.pool.get('ir.model.data')
        
        for var in self.browse(cr, uid, ids, context=context):
            # we check the lines that need to be fixed
            if var.line_ids:
                for var in var.line_ids:
                    if var.to_correct_ok:
                        raise osv.except_osv(_('Warning !'), _('Some lines need to be fixed before.'))
        return True

    def _hook_for_import(self, cr, uid, ids, context=None):
        return self.check_lines_to_fix(cr, uid, ids, context)

real_average_consumption()

class real_average_consumption_line(osv.osv):
    '''
    override of real_average_consumption_line class
    '''
    _inherit = 'real.average.consumption.line'
    _description = 'Real Average Consumption Line'
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
        return super(real_average_consumption_line, self).write(cr, uid, ids, vals, context=context)

real_average_consumption_line()