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

class product_list(osv.osv):
    _inherit = 'product.list'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""You can use the template of the export for the format that you need to use. \n
                                        The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : Product Code*, Product Description*, Comment"""),
    }

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        obj_data = self.pool.get('ir.model.data')

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

            # Product code
            product_code = row.cells[0].data
            if product_code:
                product_code = product_code.strip()
                product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code)], context=context)
                if product_ids:
                    product_id = product_ids[0]

            # Product name
            p_name = row.cells[1].data
            if not product_id and p_name:
                p_name = p_name.strip()
                product_ids = product_obj.search(cr, uid, [('name', '=', p_name)], context=context)
                if product_ids:
                    product_id = product_ids[0]

            if not product_id:
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
       
        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})
        
product_list()

