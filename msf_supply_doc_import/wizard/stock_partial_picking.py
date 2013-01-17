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
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'message': fields.text('Report of lines\' import', readonly=True),
    }

    def default_get(self, cr, uid, fields, context=None):
        if not context:
            context = {}
        values = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
        columns_header = [('Line Number', 'string'), ('Product Code','string'), ('Product Descrpition', 'string'), ('Quantity To Process', 'string'),
                          ('Product UOM', 'string'), ('Batch', 'string'), ('Expiry Date', 'string')]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        values.update({'file_to_import': base64.encodestring(default_template.get_xml()), 'filename': 'template.xls'})
        return values

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        lines_not_imported = kwargs.get('line_with_error') # list of list
        columns_header = [('Line Number', 'string'), ('Product Code','string'), ('Product Descrpition', 'string'), ('Quantity To Process', 'string'),
                          ('Product UOM', 'string'), ('Batch', 'string'), ('Expiry Date', 'string')]
        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml()), 'filename': 'Lines_Not_Imported.xls'}
        return vals
        


    def check_file_line_integrity(self, cr, uid, ids, row, product_id, product_uom_id, prodlot_name, expired_date, file_line_num, error_list, line_with_error, context=None):
        '''
        Check the integrity of the information on the Excel file line. Return False if the information is not correct
        '''
        product_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        cell_data = self.pool.get('import.cell.data')
        
        prodlot_id = False
        
        # integrity check on product
        if not product_id:
            error_list.append("Line %s of the Excel file was added to the file of the lines with errors: The product was not found in the database" % (file_line_num))
            line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
            return False, prodlot_id
        
        product = product_obj.browse(cr, uid, product_id, context)

        # integrity check on uom
        if not product_uom_id:
            error_list.append("Line %s of the Excel file was added to the file of the lines with errors: The product UOM was not found in the database" % (file_line_num))
            line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
            return False, prodlot_id

        # integrity check on batch if the product is batch mandatory (also for perishable)
        if product.perishable:
            # Error if no expiry date
            if not expired_date:
                error_list.append("Line %s of the Excel file was added to the file of the lines with errors: The Expiry Date was not found" % (file_line_num))
                line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                return False, prodlot_id

            # Search or create a batch number
            prodlot_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_name), ('product_id', '=', product_id), ('life_date', '=', expired_date)])
            if prodlot_ids:
                prodlot_id = prodlot_ids[0]
            elif not prodlot_obj.search(cr, uid, [('name', '=', prodlot_name)]):
                prodlot_id = prodlot_obj.create(cr, uid, {'name': prodlot_name, 'life_date': expired_date, 'product_id': product_id})
                error_list.append("Line %s of the Excel file: the batch %s with the expiry date %s was created for the product %s"
                    % (file_line_num, prodlot_name, expired_date, product.default_code))
            else:
                # Batch number and expiry date don't match
                error_list.append("Line %s of the Excel file: the batch %s already exists, check the product and the expiry date associated." % (file_line_num, prodlot_name))

        return True, prodlot_id

        
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

        line_cell = 0
        product_cell = 1
        qty_cell = 3
        uom_cell = 4
        lot_cell = 5
        expiry_cell = 6

        error = ''
        error_list = []
        ignore_lines, complete_lines = 0, 0
        line_with_error = []

        context.update({'import_in_progress': True})
        
        wizard_lines = False
        file_to_import = False
        for obj in self.browse(cr, uid, ids, context):
            file_to_import = obj.file_to_import
            wizard_lines = obj.product_moves_in

        # Error if no file to import
        if not file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        # Error if no line in wizard
        if not wizard_lines:
            raise osv.except_osv(_('Error'), _('No file to process.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(file_to_import))

        # iteration on rows
        rows = fileobj.getRows()
        # ignore the first row
        rows.next()

        file_line_num = 1
        
        nm_lines = {} # Dict containing data of lines not matching with wizard lines
        matching_wiz_lines = [] # List of wizard lines matching with file lines
        
        for row in rows:
            # default values
            line_data = {}
            file_line_num += 1
            # Check length of the row
            if len(row) < 8:
                raise osv.except_osv(_('Error'), _("""You should have exactly the 8 first following columns in this order for all lines:
Line Number*, Product Code*, Product Description*, Quantity, Product UOM, Batch, Expiry Date, Asset"""))

            # get values from row
            line_values = cell_data.get_line_values(cr, uid, ids, row)
            line_number = cell_data.get_move_line_number(cr, uid, ids, row, line_cell, error_list, file_line_num, context)
            product_id = cell_data.get_product_id(cr, uid, ids, row, product_cell, error_list, file_line_num, context)
            uom_id = cell_data.get_product_uom_id(cr, uid, ids, row, uom_cell, error_list, file_line_num, context)
            prodlot_name = cell_data.get_prodlot_name(cr, uid, ids, row, lot_cell, error_list, file_line_num, context)
            expired_date = cell_data.get_expired_date(cr, uid, ids, row, expiry_cell, error_list, file_line_num, context)
            product_qty = cell_data.get_product_qty(cr, uid, ids, row, qty_cell, error_list, file_line_num, context)

            integrity, prodlot_id = self.check_file_line_integrity(cr, uid, ids, row, product_id, uom_id, prodlot_name, expired_date, file_line_num, error_list, line_with_error)
            
            if not integrity:
                ignore_lines += 1
                continue

            line_found = False
            # Search if a wizard line values match with file line values
            wiz_line_ids = move_obj.search(cr, uid, [('wizard_pick_id', '=', obj.id),
                                                     ('id', 'not in', matching_wiz_lines),
                                                     ('product_id', '=', product_id),
                                                     ('line_number', '=', line_number),
                                                     ('product_uom', '=', uom_id),
                                                     ('quantity_ordered', '=', product_qty)])
            for l in move_obj.browse(cr, uid, wiz_line_ids):
                # If a line is found, pass to the next file line
                if line_found:
                    break

                # Fill the line only if the quantity to process is 0.00
                if l.quantity == 0.00:
                    line_found = True                        
                    move_obj.write(cr, uid, [l.id], {'quantity': product_qty,})
                    matching_wiz_lines.append(l.id)
                    complete_lines += 1
                    
            if not line_found:
                if line_number not in nm_lines:
                    nm_lines.update({line_number: []})
                    
                nm_lines[line_number].append({'file_line_num': file_line_num,
                                              'product_id': product_id,
                                              'uom_id': uom_id,
                                              'product_qty': product_qty,
                                              'prodlot_id': prodlot_id,
                                              'expired_date': expired_date,
                                              'line_values': line_values})
                
        for ln in nm_lines:
            wiz_line_ids = move_obj.search(cr, uid, [('wizard_pick_id', '=', obj.id),
                                                     ('id', 'not in', matching_wiz_lines),
                                                     ('line_number', '=', ln),])
            if wiz_line_ids and len(nm_lines[ln]) <= len(wiz_line_ids):
                for nml in nm_lines[ln]:
                    leave_qty = nml.get('product_qty')
                    while leave_qty > 0.00:
                        last_move = False
                        for wl in move_obj.browse(cr, uid, wiz_line_ids):
                            last_move = wl.id
                            available_qty = wl.quantity_ordered - wl.quantity
                            if available_qty > 0.00:
                                if available_qty > leave_qty:
                                    leave_qty = 0.00
                                    move_obj.write(cr, uid, [wl.id], {'quantity': wl.quantity + leave_qty})
                                else:
                                    leave_qty -= available_qty
                                    move_obj.write(cr, uid, [wl.id], {'quantity': wl.quantity + available_qty})
                        if leave_qty > 0.00:
                            last_move = move_obj.browse(cr, uid, last_move)
                            move_obj.write(cr, uid, [last_move.id], {'quantity': last_move.quantity + leave_qty})
                            leave_qty = 0.00
                    complete_lines += 1
            elif wiz_line_ids:
                last_move = False
                for nml in nm_lines[ln]:
                    leave_qty = nml.get('product_qty')
                    while leave_qty > 0.00:
                        # Split the last line
                        if not wiz_line_ids and last_move:
                            wizard_values = move_obj.split(cr, uid, last_move, context)
                            wiz_context = wizard_values.get('context')
                            self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']],
                                                                            {'quantity': leave_qty}, context=wiz_context)
                            self.pool.get(wizard_values['res_model']).split(cr, uid, [wizard_values['res_id']], context=wiz_context)
                            error_list.append(_("Line %s of the Excel file produced a split for the line %s.") % (nml.get('file_line_num'), nml.get('line_number')))
                            wiz_line_ids = move_obj.search(cr, uid, [('wizard_pick_id', '=', obj.id),
                                                                     ('id', 'not in', matching_wiz_lines),
                                                                     ('line_number', '=', ln),])
                            
                        # Continue the process
                        for wl in move_obj.browse(cr, uid, wiz_line_ids):
                            last_move = wl.id
                            available_qty = wl.quantity_ordered - wl.quantity
                            if available_qty > 0.00:
                                if available_qty > leave_qty:
                                    move_obj.write(cr, uid, [wl.id], {'quantity': wl.quantity + leave_qty})
                                    leave_qty = 0.00
                                else:
                                    leave_qty -= available_qty
                                    move_obj.write(cr, uid, [wl.id], {'quantity': wl.quantity + available_qty})
                            # Remove the wizard line from wizard to process
                            wiz_line_ids.remove(last_move)
                            matching_wiz_lines.append(last_move)
                        if leave_qty > 0.00:
                            last_move = move_obj.browse(cr, uid, last_move)
                            move_obj.write(cr, uid, [last_move.id], {'quantity': last_move.quantity + leave_qty})
                            leave_qty = 0.00
                    complete_lines += 1
                    
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
        """
        Launch a thread for importing lines.
        """
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
        Otherwise, you can continue to use Unifield.""")
        return self.log(cr, uid, ids[0], msg_to_return)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        return False

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
        return False

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
