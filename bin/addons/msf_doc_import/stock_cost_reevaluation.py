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

class stock_cost_reevaluation(osv.osv):
    _inherit = 'stock.cost.reevaluation'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use. \n The file should be in XML Spreadsheet 2003 format. \n The columns should be in this order : Product Code*, Product Description*, Initial Average Cost, Location*, Batch, Expiry Date, Quantity'),
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
        vals['reevaluation_line_ids'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        # get company default currency
        comp_currency_name = ''
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)
        if user and user[0] and user[0].company_id:
            comp_currency_id = user[0].company_id.currency_id.id
            comp_currency_name = user[0].company_id.currency_id.name
        else:
            comp_currency_id = False
        if not comp_currency_id:
            raise osv.except_osv(_('Error'), _('Company currency is not defined'))

        product_cache = {}

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()

        # ignore the first row
        reader.next()
        line_num = 1
        for row in reader:
            line_num += 1
            # Check length of the row
            if len(row) != 4:
                raise osv.except_osv(_('Error'), _("""You should have exactly 4 columns in this order:
Product Code*, Product Description*, Product Cost*, Currency*"""))

            # default values
            product_id = False
            product_cost = 1.00
            product_code = False
            product_name = False

            # Product code
            product_code = row.cells[0].data
            if not product_code:
                product_code = False
            else:
                try:
                    product_code = product_code.strip()
                    if product_code in product_cache:
                        product_id = product_cache.get(product_code)
                    if not product_id:
                        product_ids = product_obj.search(cr, uid, ['|', ('default_code', '=', product_code.upper()), ('default_code', '=', product_code)], context=context)
                        if product_ids:
                            product_id = product_ids[0]
                            product_cache.update({product_code: product_id})
                except Exception:
                    pass

            # Product name
            product_name = row.cells[1].data
            if not product_id:
                raise osv.except_osv(_('Error'), _('The Product [%s] %s was not found in the list of the products') % (product_code or '', product_name or ''))

            # Average cost
            cost = row.cells[2].data
            if not cost:
                if product_id:
                    product_cost = product_obj.browse(cr, uid, product_id).standard_price
                else:
                    product_cost = 1.00
            else:
                if row.cells[2].type in ('int', 'float'):
                    product_cost = cost
                elif product_id:
                    product_cost = product_obj.browse(cr, uid, product_id).standard_price
                else:
                    product_cost = 1.00

            # Currency
            currency_name = row.cells[3].data
            if not currency_name or currency_name.lower() != comp_currency_name.lower():
                raise osv.except_osv(_('Error'),
                                     _("The Product [%s] %s is not in company currency. Company currency is '%s' and the product currency is '%s'.") % (
                    product_code or '', product_name or '', comp_currency_name, currency_name or '', ))

            to_write = {
                'product_id': product_id,
                'average_cost': product_cost,
                'currency_id': comp_currency_id,
            }

            vals['reevaluation_line_ids'].append((0, 0, to_write))

        # write order line on Inventory
        vals.update({'file_to_import': False})
        self.write(cr, uid, ids, vals, context=context)

        view_id = obj_data.get_object_reference(cr, uid, 'specific_rules','cost_reevaluation_form_view')[1]

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
        vals['reevaluation_line_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.reevaluation_line_ids
            for var in line_browse_list:
                vals['reevaluation_line_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True

stock_cost_reevaluation()

