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

import threading
import pooler
from osv import fields, osv
from tools.translate import _
# xml parser
from lxml import etree
# import xml file
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator

class stock_partial_picking(osv.osv_memory):
    """
    Enables to choose the location for IN (selection of destination for incoming shipment)
    and OUT (selection of the source for delivery orders and picking ticket)
    """
    _inherit = "stock.partial.picking"

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml, *.xls',
                                        help="""* You can use the template of the export for the format that you need to use.
                                                * The file should be in XML Spreadsheet 2003 format."""),
        'data': fields.binary('Lines not imported'),
        'filename': fields.char('Lines not imported', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'message': fields.text('Report of lines\' import', readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if not context:
            context = {}
        values = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
        columns_header = [('Line Number', 'string'), ('Product Code','string'), ('Product Descrpition', 'string'), ('Quantity To Process', 'string'),
                          ('Product UOM', 'string'), ('Batch', 'string'), ('Expiry Date', 'string')]
        toto = SpreadsheetCreator('Template of import', columns_header, [])
        values.update({'file_to_import': base64.encodestring(toto.get_xml()), 'filename': 'template.xls'})
        return values

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        lines_not_imported = kwargs.get('line_with_error') # list of list
        columns_header = [('Line Number', 'string'), ('Product Code','string'), ('Product Descrpition', 'string'), ('Quantity To Process', 'string'),
                          ('Product UOM', 'string'), ('Batch', 'string'), ('Expiry Date', 'string')]
        toto = SpreadsheetCreator('Lines Not imported', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(toto.get_xml()), 'filename': 'Lines_Not_Imported.xls'}
        return vals
        

    def _import(self, dbname, uid, ids, context=None):
        """
        Read the file line of the xls file and update the values of the wizard.
        Create an other xls file if lines are ignored.
        """
        cr = pooler.get_db(dbname).cursor()
        
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        product_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        move_obj = self.pool.get('stock.move.memory.in')
        cell_data = self.pool.get('import.cell.data')
        list_line_values = []
        for obj in self.read(cr, uid, ids, ['product_moves_in', 'file_to_import'], context):
            file_to_import = obj['file_to_import']
            if not file_to_import:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))
            product_moves_in = obj['product_moves_in']
            list_line_values = move_obj.read(cr, uid, product_moves_in)
        ignore_lines, complete_lines = 0, 0
        error_list = []
        line_with_error = []
        list_line_nb = [line['line_number'] for line in list_line_values]
        error = ''
        context.update({'import_in_progress': True})
        for line in list_line_values:
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(file_to_import))
            # iterator on rows
            rows = fileobj.getRows()
            # ignore the first row
            rows.next()
            file_line_num = 1
            first_same_line_nb = True
            for row in rows:
                # default values
                line_data = {}
                file_line_num += 1
                # Check length of the row
                if len(row) < 8:
                    raise osv.except_osv(_('Error'), _("""You should have exactly the 8 first following columns in this order for all lines:
    Line Number*, Product Code*, Product Description*, Quantity, Product UOM, Batch, Expiry Date, Asset"""))
                # Cell 0: Line Number
                cell_nb = 0
                line_number = cell_data.get_move_line_number(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
                if line_number in list_line_nb:
                    if line_number == line['line_number']:
                        # Cell 3: Quantity To Process => we need it for the split
                        cell_nb = 3
                        product_qty = cell_data.get_product_qty(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
                        try:
                            if not first_same_line_nb:
                                # if the line imported is not the first to update the line_number, we split it
                                wizard_values = move_obj.split(cr, uid, line['id'], context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']],
                                                                                {'quantity': product_qty}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).split(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                error_list.append("Line %s in your Excel file produced a split for the line %s and the quantity were reset." % (file_line_num, line_number))
                                # the line that will be updated changed, we take the last created
                                new_line_id = move_obj.search(cr, uid, [('line_number', '=', line_number), ('wizard_pick_id', '=', ids[0])])[-1]
                                line = move_obj.read(cr, uid, new_line_id)

                            # Cell 3: Quantity To Process
                            if product_qty != line['quantity']:
                                error_list.append("Line %s of the Excel file: The quantity changed from %s to %s" % (file_line_num, line['quantity'], product_qty))
                                line_data.update({'quantity': product_qty})

                            # Cell 1: Product Code
                            cell_nb = 1
                            product_id = cell_data.get_product_id(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
                            if not product_id:
                                error_list.append("Line %s of the Excel file: The product was not found in the database" % (file_line_num))
                                line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                                ignore_lines += 1
                                continue
                            elif product_id and product_id != line['product_id']:
                                error_list.append("Line %s of the Excel file: The product did not match with the existing product of the line %s so we change the product from %s to %s."
                                                  % (file_line_num, line_number, product_obj.read(cr, uid, line['product_id'], ['default_code'])['default_code'], product_obj.read(cr, uid, product_id, ['default_code'])['default_code']))
                                # we change the product through the existing wizard
                                wizard_values = move_obj.change_product(cr, uid, line['id'], context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']], {'change_reason': 'Import changed product', 'new_product_id': product_id}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).change_product(cr, uid, [wizard_values['res_id']], context=wiz_context)
                            # Cell 4: Product UOM
                            cell_nb = 4
                            product_uom_id = cell_data.get_product_uom_id(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
                            if not product_uom_id:
                                error_list.append("Line %s of the Excel file: The product UOM was not found in the database" % (file_line_num))
                                line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                                ignore_lines += 1
                                continue
                            if product_uom_id and product_uom_id != line['product_uom']:
                                error_list.append("Line %s of the Excel file: The product UOM did not match with the existing product of the line %s so we change the product UOM." % (file_line_num, line_number))
                                line_data.update({'product_uom': product_uom_id})
                            # Is the product batch mandatory?
                            if product_obj.read(cr, uid, product_id, ['perishable'], context)['perishable']:
                                # Cell 5: Batch, Prodlot
                                cell_nb = 5
                                prodlot_name = cell_data.get_prodlot_name(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
                                # Cell 6: Expiry Date
                                cell_nb = 6
                                expired_date = cell_data.get_expired_date(cr, uid, ids, row, cell_nb, error_list, file_line_num, context)
                                if not expired_date:
                                    error_list.append("Line %s of the Excel file was added to the file of the lines not imported: The Expiry Date was not found" % (file_line_num))
                                    line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                                    ignore_lines += 1
                                    continue
                                prodlot_id = prodlot_obj.search(cr, uid, [('name', '=', prodlot_name), ('product_id', '=', product_id), ('life_date', '=', expired_date)])[0]
                                if not prodlot_id:
                                    prodlot_id = prodlot_obj.create(cr, uid, {'name': prodlot_name, 'life_date': expired_date, 'product_id': product_id})
                                    error_list.append("Line %s of the Excel file: the batch %s with the expiry date %s was created for the product %s"
                                                      % (file_line_num, prodlot_name, expired_date, product_obj.read(cr, uid, product_id, ['default_code'])['default_code']))
                                line_data.update({'prodlot_id': prodlot_id})
                            first_same_line_nb = False
                            move_obj.write(cr, uid, [line['id']], line_data, context)
                        except osv.except_osv as osv_error:
                            osv_value = osv_error.value
                            osv_name = osv_error.name
                            error_list.append("Line %s in your Excel file was added to the file of the lines not imported: %s: %s\n" % (file_line_num, osv_name, osv_value))
                            line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                            ignore_lines += 1
                        except Exception, e:
                            error_list.append("Line %s in your Excel file was added to the file of the lines not imported: %s\n" % (file_line_num, e))
                            line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                            ignore_lines += 1
                        complete_lines += 1
                else:
                    # lines ignored if they don't have the same line number as the line of the wizard
                    error_list.append("Line %s of the Excel file does not correspond to any line number." % (file_line_num))
                    line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                    ignore_lines += 1
        error += '\n'.join(error_list)
        message = '''Importation completed !
# of imported lines : %s
# of ignored lines : %s

Reported errors :
%s
                '''  % (complete_lines, ignore_lines, error or 'No error !')
        vals = {'message': message}
        if line_with_error:
            file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error)
            vals.update(file_to_export)
        self.write(cr, uid, ids, vals, context=context)
        self.check_lines(cr, uid, ids, context)
        cr.commit()
        cr.close()
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.partial.picking',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                }

    def import_file(self, cr, uid, ids, context=None):
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
        Otherwise, you can continue to use Unifield.""")
        self.log(cr, uid, ids[0], msg_to_return)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        return

    def check_lines(self, cr, uid, ids, context=None):
        """
        If some line have product that is not batch mandatory, we can remove the batch.
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move.memory.in')
        for spp in self.browse(cr, uid, ids,context):
            for line in spp.product_moves_in:
                if not line.product_id.perishable:
                    move_obj.write(cr, uid, [line.id], {'prodlot_id': False, 'expiry_date': False}, context)
        return

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        add the field "file_to_import" for the wizard 'incoming shipment' with the button "import_file"
        '''
        if not context:
            context = {}
        result = super(stock_partial_picking, self).fields_view_get(cr, uid, view_id=view_id, view_type='form', context=context, toolbar=toolbar, submenu=submenu)
        picking_type = context.get('picking_type')
        if view_type == 'form':
            if picking_type == 'incoming_shipment':
                new_field_txt = """
                <newline/>
                <group name="import_file_lines" string="Import Lines" colspan="28" col="7">
                <field name="file_to_import" colspan="2"/>
                <button name="import_file" string="Import the file" icon="gtk-execute" colspan="1" type="object" />
                <field name="import_error_ok" invisible="1"/>
                <field name="filename" invisible="1"  />
                <field name="data" filename="filename" readonly="2" colspan="2" attrs="{'invisible':[('import_error_ok', '=', False)]}"/>
                <button name="dummy" string="Update" icon="gtk-execute" colspan="1" type="object" />
                </group>
                <field name="message" attrs="{'invisible':[('import_error_ok', '=', False)]}" colspan="4" nolabel="1"/>
                """
                # add field in arch
                arch = result['arch']
                l = arch.split('<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>')
                arch = l[0]
                arch += '<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>' + new_field_txt + l[1]
                result['arch'] = arch
                
        return result

stock_partial_picking()