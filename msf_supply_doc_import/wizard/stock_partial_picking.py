
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF
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

from osv import fields, osv
from tools.translate import _
# xml parser
from lxml import etree
# import xml file
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


class stock_partial_picking(osv.osv_memory):
    """
    Enables to choose the location for IN (selection of destination for incoming shipment)
    and OUT (selection of the source for delivery orders and picking ticket)
    """
    _inherit = "stock.partial.picking"

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml, *.xls',
                                        help="""* You can use the template of the export for the format that you need to use.
                                                * The file should be in XML Spreadsheet 2003 format."""),
        'file_error': fields.binary(string='Lines not imported',
                                    help="""* This file caught the lines that were not imported."""),
        'import_error_ok': fields.boolean(string='Error at import', readonly=True),
        'message': fields.text('Report of lines\' import', readonly=True),
    }

    def import_file(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        product_obj = self.pool.get('product.product')
        move_obj = self.pool.get('stock.move.memory.in')
        obj_data = self.pool.get('ir.model.data')
        cell_data = self.pool.get('import.cell.data')
        for obj in self.read(cr, uid, ids, ['product_moves_in', 'file_to_import'], context):
            file_to_import = obj['file_to_import']
            if not file_to_import:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            product_moves_in = obj['product_moves_in']
            test = move_obj.read(cr, uid, product_moves_in)
        ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(file_to_import))
        # iterator on rows
        rows = fileobj.getRows()
        # ignore the first row
        rows.next()
        import_error_ok = False
        file_line_num = 1
        error_list = []
        for row in rows:
            # default values
            purchase_line_ids = []
            error = ''
            file_line_num += 1
            # Check length of the row
            if len(row) < 8:
                raise osv.except_osv(_('Error'), _("""You should have exactly the 8 first following columns in this order for all lines:
Line Number*, Product Code*, Product Description*, Quantity, Product UOM, Batch, Expiry Date, Asset"""))
            # Cell 0: Line Number
            cell_nb = 0
            line_number = cell_data.get_move_line_number(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
            # Cell 1: Product Code
            cell_nb = 1
            product_id = cell_data.get_product_id(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
            # Cell 3: Quantity To Process
            cell_nb = 3
            product_qty = cell_data.get_product_qty(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
            # Cell 4: Product UOM
            cell_nb = 4
            product_uom_id = cell_data.get_product_uom_id(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
            # Cell 5: Batch, Prodlot
            cell_nb = 5
            prodlot_id = cell_data.get_prodlot_id(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
            # Cell 6: Expiry Date
            cell_nb = 6
            expired_date = cell_data.get_expired_date(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
            line_data = {'line_number': line_number,
                         'product_id': product_id,
                         'quantity': product_qty,
                         'product_uom': product_uom_id,
                         'prodlot_id': prodlot_id,
                         'expiry_date':expired_date,}
            # each line is identifying with the search key below (wizard_pick_id, line_number, product_id)
            existing_line_id = move_obj.search(cr, uid, [('wizard_pick_id', '=', ids[0]), ('line_number', '=', line_number), ('product_id', '=', product_id),])
            if existing_line_id:
                try:
                    move_obj.write(cr, uid, existing_line_id, line_data, context)
                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    error_list.append("Line %s in your Excel file: %s: %s\n" % (file_line_num, osv_name, osv_value))
                    ignore_lines += 1
                complete_lines += 1
            elif move_obj.search(cr, uid, [('wizard_pick_id', '=', ids[0]), ('line_number', '=', line_number)]):
                product_name = False
                if product_id:
                    product_name = product_obj.read(cr, uid, product_id, ['name'], context)['name']
                error_list.append("Line %s of the Excel file: The product %s does not match with the existing product of the line %s" % (file_line_num, product_name or 'is not found in the database or', line_number))
                import_error_ok = True
                ignore_lines += 1
        error += '\n'.join(error_list)
        message = '''Importation completed !
# of imported lines : %s
# of lines to correct: %s
# of ignored lines : %s

Reported errors :
%s
                '''  % (complete_lines, lines_to_correct, ignore_lines, error or 'No error !')
        self.write(cr, uid, ids, {'message': message,
                                  'import_error_ok': import_error_ok,}, context=context)
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.partial.picking',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add the field "file_to_import" for the wizard 'incoming shipment' with the button "import_file"
        '''
        if not context:
            context = {}
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
        picking_type = context.get('picking_type')
        if view_type == 'form':
            form = etree.fromstring(result['arch'])
            if picking_type == 'incoming_shipment':
                new_field_txt = """
                <newline/>
                <group name="import_file_lines" string="Import Lines" colspan="4" col="8">
                <field name="file_to_import"/>
                <button name="import_file" string="Import the file" icon="gtk-execute" colspan="2" type="object" />
                <field name="file_error" attrs="{'invisible':[('import_error_ok', '=', True)]}"/>
                <field name="import_error_ok" invisible="1"/>
                <newline/>
                <field name="message" attrs="{'invisible':[('import_error_ok', '=', False)]}" colspan="4" nolabel="1"/>
                </group>
                """
                # add field in arch
                arch = result['arch']
                l = arch.split('<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>')
                arch = l[0]
                arch += '<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>' + new_field_txt + l[1]
                result['arch'] = arch
                
        return result

stock_partial_picking()