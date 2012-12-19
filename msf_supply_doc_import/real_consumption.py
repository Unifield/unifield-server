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