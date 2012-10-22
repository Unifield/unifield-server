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

from datetime import datetime

from osv import osv
from osv import fields
import logging
import tools
from os import path
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

class product_list(osv.osv):
    _inherit = 'product.list'

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
        obj_data = self.pool.get('ir.model.data')
        import_to_correct = False

        vals = {}
        vals['product_ids'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()
        
        # ignore the first row
        reader.next()
        line_num = 1
        for row in reader:
            line_num += 1
            # Check length of the row
            if len(row) < 2 or len(row) > 3:
                raise osv.except_osv(_('Error'), _("""Line %s - You should have at least 2 columns (max. 3) in this order:
Product Code*, Product Description*, Comment""" % line_num))

            # default values
            product_id = False
            comment = ''
            error_list = []

            # Product code
            product_code = row.cells[0].data
            if not product_code:
                default_code = False
                error_list.append(_('Line %s - No Product Code.') % line_num)
            else:
                try:
                    product_code = product_code.strip()
                    product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code)])
                    if product_ids:
                        product_id = product_ids[0]
                except Exception:
                    error_list.append(_('Line %s - The Product Code has to be a string.') % line_num)

            # Product name
            p_name = row.cells[1].data
            if not product_id and not p_name:
                error_list.append(_('Line %s - No Product Description') % line_num)
            elif not product_id:
                try:
                    p_name = p_name.strip()
                    product_ids = product_obj.search(cr, uid, [('name', '=', p_name)])
                    if not product_ids:
                        error_list.append(_('Line %s - The Product [%s] %s was not found in the list of the products.') % (line_num, product_code or 'N/A', p_name or ''))
                    else:
                        product_id = product_ids[0]
                except Exception:
                     error_list.append(_('Line %s - The Product Description has to be a string.') % line_num)

            if not product_id:
                import_to_correct = True
                if not product_code and not p_name:
                    raise osv.except_osv(_('Error'), _('Line %s - You have to fill at least the product code or the product name !') % line_num)
                raise osv.except_osv(_('Error'), _('Line %s - The Product [%s] %s was not found in the list of products') % (line_num, product_code or 'N/A', p_name or ''))

            # Comment
            comment = len(row) == 3 and row.cells[2].data or ''

            to_write = {
                'name': product_id,
                'comment': comment,
            }
            
            vals['product_ids'].append((0, 0, to_write))
            
        # write order line on Inventory
        vals.update({'file_to_import': False})
        self.write(cr, uid, ids, vals, context=context)
        
        view_id = obj_data.get_object_reference(cr, uid, 'product_list','product_list_form_view')[1]
       
        if import_to_correct:
            msg_to_return = _("The import of lines had errors, please retry with a new file.")
        
        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})
        
    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove lines
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals = {}
        vals['product_ids'] = []
        for list in self.browse(cr, uid, ids, context=context):
            for var in list.product_ids:
                vals['product_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True
        
product_list()

