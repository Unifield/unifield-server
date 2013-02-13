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


class incoming_import_xml_line(osv.osv_memory):
    _name = 'incoming.import.xml.line'
    
    
    _columns = {
        'wizard_id': fields.many2one('stock.partial.picking', string='Wizard', required=True),
        'file_line_number': fields.integer(string='File line numbers'),
        'line_number': fields.integer(string='Line number'),
        'product_id': fields.many2one('product.product', string='Product'),
        'uom_id': fields.many2one('product.uom', string='UoM'),
        'quantity': fields.float(digits=(16,2), string='Quantity'),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch'),
        'expiry_date': fields.date(string='Expiry date'),
        'line_values': fields.text(string='Line values'),
    }
    
    
incoming_import_xml_line()


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
        'filename_template': fields.char('Template', size=256),
        'filename': fields.char('Lines with errors', size=256),
        #'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'import_error_ok': fields.boolean(string='error', readonly=True),
        'message': fields.text('Report of lines\' import', readonly=True),
        'percent_completed': fields.integer('% completed', readonly=True),
        'import_in_progress': fields.boolean(string='import in progress', readonly=True),
    }
    
    _defaults = {
        'import_error_ok': False,
    }

    def default_get(self, cr, uid, fields, context=None):
        if not context:
            context = {}
        values = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
        columns_header = [('Line Number', 'string'), ('Product Code','string'), ('Product Description', 'string'), ('Quantity To Process', 'string'),
                          ('Product UOM', 'string'), ('Batch', 'string'), ('Expiry Date', 'string')]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        values.update({'file_to_import': base64.encodestring(default_template.get_xml(default_filters=['decode.utf8'])), 'filename_template': 'template.xls'})
        return values

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        """
        Export lines with errors in a file.
        Warning: len(columns_header) == len(lines_not_imported)
        """
        columns_header = [('Line Number', 'string'), ('Product Code','string'), ('Product Description', 'string'), ('Quantity To Process', 'string'),
                          ('Product UOM', 'string'), ('Batch', 'string'), ('Expiry Date', 'string')]
        lines_not_imported = [] # list of list
        for line in kwargs.get('line_with_error'):
            if len(line) < len(columns_header):
                lines_not_imported.append(line + ['' for x in range(len(columns_header)-len(line))])
            else:
                lines_not_imported.append(line)
        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml(['decode.utf8'])),
                'filename': 'Lines_Not_Imported.xls',
                'import_error_ok': True,}
        return vals
        


    def check_file_line_integrity(self, cr, uid, ids, row, product_id, product_uom_id, prodlot_name, expired_date, file_line_num, error_list, info_list, line_with_error, context=None):
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
                if not prodlot_name:
                    error_list.append("Line %s of the Excel file was added to the file of the lines with errors: The Expiry Date was not found or it has a wrong format ('DD-MM-YYYY')" % (file_line_num))
                    line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                    return True, prodlot_id
                else:
                    prodlot_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_name), ('product_id', '=', product_id)])
                    if prodlot_ids:
                        prodlot_id = prodlot_ids[0]
                    return True, prodlot_id
            # Search or create a batch number
            prodlot_ids = prodlot_obj.search(cr, uid, [('name', '=', prodlot_name), ('product_id', '=', product_id), ('life_date', '=', expired_date)])
            if prodlot_ids:
                prodlot_id = prodlot_ids[0]
            elif not prodlot_obj.search(cr, uid, [('name', '=', prodlot_name)]) and prodlot_name and expired_date:
                prodlot_id = prodlot_obj.create(cr, uid, {'name': prodlot_name, 'life_date': expired_date, 'product_id': product_id})
                info_list.append("Line %s of the Excel file: the batch %s with the expiry date %s was created for the product %s"
                    % (file_line_num, prodlot_name, expired_date, product.default_code))
            elif not prodlot_name:
                return True, prodlot_id
            else:
                # Batch number and expiry date don't match
                error_list.append("Line %s of the Excel file: the batch %s already exists, check the product and the expiry date associated." % (file_line_num, prodlot_name))
                line_with_error.append(cell_data.get_line_values(cr, uid, ids, row))
                return True, prodlot_id

        return True, prodlot_id

        
    def _import(self, dbname, uid, ids, fileobj=None, context=None):
        """
        Read the file line of the xls file and update the values of the wizard.
        Create an other xls file if lines are ignored.
        """
        cr = pooler.get_db(dbname).cursor()
        
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_obj = self.pool.get('stock.move.memory.in')
        cell_data = self.pool.get('import.cell.data')
        import_obj = self.pool.get('incoming.import.xml.line')

        line_cell = 0
        product_cell = 1
        qty_cell = 3
        uom_cell = 4
        lot_cell = 5
        expiry_cell = 6

        error = ''
        error_list = []
        info = ''
        info_list = []
        ignore_lines, complete_lines = 0, 0
        line_with_error = []
        
        percent_completed = 0
        processed_lines = 0

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
            raise osv.except_osv(_('Error'), _('No line to process.'))

        if not fileobj:
            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(file_to_import))

        total_line_num = len([row for row in fileobj.getRows()])
        # iteration on rows
        rows = fileobj.getRows()
        # ignore the first row
        rows.next()

        file_line_num = 1
        
        line_numbers = []

        for row in rows:
            # default values
            line_data = {}
            file_line_num += 1

            # get values from row
            line_values = cell_data.get_line_values(cr, uid, ids, row)
            # Check length of the row
            if len(row) < 7:
                error_list.append(_("""Line %s of the Excel file was added to the file of the lines with errors. You should have exactly 7 columns in this order:
Line Number*, Product Code*, Product Description*, Quantity, Product UOM, Batch, Expiry Date.""") % (file_line_num, ))
                line_with_error.append(list(line_values))
                ignore_lines += 1
                continue
            line_number = cell_data.get_move_line_number(cr, uid, ids, row, line_cell, error_list, file_line_num, context)
            product_id = cell_data.get_product_id(cr, uid, ids, row, product_cell, error_list, file_line_num, context)
            uom_id = cell_data.get_product_uom_id(cr, uid, ids, row, uom_cell, error_list, file_line_num, context)
            prodlot_name = cell_data.get_prodlot_name(cr, uid, ids, row, lot_cell, error_list, file_line_num, context)
            expired_date = cell_data.get_expired_date(cr, uid, ids, row, expiry_cell, error_list, file_line_num, context)
            product_qty = cell_data.get_product_qty(cr, uid, ids, row, qty_cell, error_list, file_line_num, context)

            integrity, prodlot_id = self.check_file_line_integrity(cr, uid, ids, row, product_id, uom_id, prodlot_name, expired_date, file_line_num, error_list, info_list, line_with_error)
            
            if not integrity:
                ignore_lines += 1
                continue
                
            if line_number not in line_numbers:
                line_numbers.append(line_number)
            
            # Create an osv.memory object for each file lines
            import_obj.create(cr, uid, {'wizard_id': obj.id,
                                        'file_line_number': file_line_num,
                                        'line_number': line_number,
                                        'product_id': product_id,
                                        'uom_id': uom_id,
                                        'quantity': product_qty,
                                        'prodlot_id': prodlot_id,
                                        'expiry_date': expired_date,
                                        'line_values': line_values})
        
        for ln in line_numbers:
            move_ids = move_obj.search(cr, uid, [('wizard_pick_id', '=', obj.id),
                                                 ('line_number', '=', ln)],
                                                order='quantity_ordered desc',
                                                context=context)
            
            line_ids = import_obj.search(cr, uid, [('wizard_id', '=', obj.id),
                                                   ('line_number', '=', ln)],
                                                  order='quantity desc',
                                                  context=context)
            
            '''
            4 cases :
                1/ No move corresponding to the line number
                2/ The number of moves is equal to the number of lines
                3/ The number of moves is smallest than the number of lines
                4/ The number of moves is biggest than the number of lines
            '''
            nb_moves = len(move_ids)
            nb_lines = len(line_ids)
            # 1/ No move corresponding to the line number
            if nb_moves == 0:
                '''
                All lines raise an error because no move found
                '''
                for l in import_obj.browse(cr, uid, line_ids, context=context):
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : No matching line found with in the Incoming shipment for the line number %s.") % (l.file_line_number, l.line_number))
                    line_with_error.append(list(l.line_values))
                    ignore_lines += 1
                    
            # 2/ The number of moves is equal to the number of lines
            elif nb_moves == nb_lines:
                '''
                Each line of the stock move should match with a line of the file
                '''
                # Treat after lines with a different product/UoM
                remaining_lines = []
                already_treated = []
                for l in import_obj.browse(cr, uid, line_ids, context=context):
                    match_ids = move_obj.search(cr, uid, [('id', 'in', move_ids),
                                                          ('id', 'not in', already_treated),
                                                          ('product_id', '=', l.product_id.id),
                                                          ('product_uom', '=', l.uom_id.id)], context=context)
                    
                    # Treat after if no move matches with the line values
                    if not match_ids:
                        remaining_lines.append(l.id)
                        continue
                    
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    # We search the best move to fill
                    diff_qty = False
                    best_move = False
                    for m in move_obj.browse(cr, uid, match_ids, context=context):
                        if not best_move:
                            best_move = m.id
                            diff_qty = abs(m.quantity_ordered - l.quantity)
                        if abs(m.quantity_ordered - l.quantity) < diff_qty:
                            best_move = m.id
                            diff_qty = abs(m.quantity_ordered - l.quantity)
                            
                    move_obj.write(cr, uid, [best_move], {'quantity': l.quantity,
                                                          'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                          'expiry_date': l.expiry_date}, context=context)
                    complete_lines += 1
                    already_treated.append(best_move)
                    
                # Treat the remaining lines
                for l in import_obj.browse(cr, uid, remaining_lines, context=context):
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    ok = False
                    for m in move_obj.browse(cr, uid, move_ids, context=context):
                        # Pass to the next move if UoMs are not compatible
                        if m.id in already_treated or m.product_uom.category_id.id != l.uom_id.category_id.id:
                            continue
                        else:
                            ok = True
                            
                            if m.product_id.id != l.product_id.id:
                                # Call the change product wizard
                                wizard_values = move_obj.change_product(cr, uid, m.id, context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']], {'change_reason': 'Import changed product', 'new_product_id': l.product_id.id}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).change_product(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                info_list.append(_("Line %s of the Excel file: The product did not match with the existing product of the line, so we change the from [%s] %s to [%s] %s.") % (l.file_line_number, m.product_id.default_code, m.product_id.name, l.product_id.default_code, l.product_id.name))
                                
                            if m.product_uom.id != l.uom_id.id:
                                info_list.append(_("Line %s of the Excel file: The product UOM did not match with the existing product UoM of the line, so we change the UoM from %s to %s.") % (l.file_line_number, m.product_uom.name, l.uom_id.name))
                                
                            move_obj.write(cr, uid, [m.id], {'product_uom': l.uom_id.id,
                                                             'quantity': l.quantity,
                                                             'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                             'expiry_date': l.expiry_date}, context=context)
                            complete_lines += 1
                            already_treated.append(m.id)
                            break
                            
                    if not ok:
                        error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : A line was found in the Incoming shipment but the UoM of the Excel line (%s) is not compatible with UoM (%s) of the incoming shipment line.") % (l.file_line_number, l.uom_id.name, m.product_uom.name))
                        line_with_error.append(list(l.line_values))
                        ignore_lines += 1
                    
            # 3/ The number of moves is smallest than the number of lines
            elif nb_moves < nb_lines:
                '''
                This needs a split at least one line.
                First, treate lines matching
                Then, the remaining lines by splitting
                '''
                multi_product = []
                for m in move_obj.browse(cr, uid, move_ids, context=context):
                    multi_product.append(m.product_id.id)
                        
                # Treat after the lines which not match directly
                remaining_lines = []
                already_treated = []
                for l in import_obj.browse(cr, uid, line_ids, context=context):
                    match_ids = move_obj.search(cr, uid, [('id', 'in', move_ids),
                                                          ('id', 'not in', already_treated),
                                                          ('product_id', '=', l.product_id.id),
                                                          ('product_uom', '=', l.uom_id.id)], context=context)
                    # Treat after if no move match with the line
                    if not match_ids:
                        remaining_lines.append(l.id)
                        continue
                    
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    
                    # Search the best move to fill
                    diff_qty = False
                    best_move = False
                    for m in move_obj.browse(cr, uid, match_ids, context=context):
                        if not best_move:
                            best_move = m.id
                            diff_qty = abs(m.quantity_ordered - l.quantity)
                        if abs(m.quantity_ordered - l.quantity) < diff_qty:
                            best_move = m.id
                            diff_qty = abs(m.quantity_ordered - l.quantity)
                            
                    move_obj.write(cr, uid, [best_move], {'quantity': l.quantity,
                                                          'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                          'expiry_date': l.expiry_date}, context=context)
                    complete_lines += 1
                    already_treated.append(best_move)
                    
                for l in import_obj.browse(cr, uid, remaining_lines, context=context):
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    
                    # If the moves have more than one product and the line has another product, return an error
                    if len(multi_product) > 1 and l.product_id.id not in multi_product:
                        error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : The system cannot found a line matching with the line numbert %s, the product [%s] %s and the UoM %s.") % (l.file_line_number, l.line_number, l.product_id.default_code, l.product_id.name, l.uom_id.name))
                        line_with_error.append(list(l.line_values))
                        ignore_lines += 1
                        continue
                        
                    # Search moves which can be split
                    match_ids = move_obj.search(cr, uid, [('id', 'in', move_ids),
                                                          ('quantity_ordered', '>=', l.quantity),], order='quantity_ordered desc', context=context)
                    
                    if not match_ids:
                        match_ids = move_obj.search(cr, uid, [('id', 'in', already_treated)], order='quantity_ordered desc', context=context)
                    
                    ok = False
                    for m in move_obj.browse(cr, uid, match_ids, context=context):
                        # Split the move only if UoMs are compatible and if the quantity ordered is bigger than the line quantity
                        # or a quantity is already filled on this move
                        if (m.quantity_ordered > l.quantity or m.quantity > 0) and m.product_uom.category_id.id == l.uom_id.category_id.id:
                            ok = True
                            # Split the line
                            wizard_values = move_obj.split(cr, uid, m.id, context)
                            wiz_context = wizard_values.get('context')
                            qty_to_split = m.quantity_ordered - l.quantity < 1 and 1 or l.quantity
                            self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']],
                                                                            {'quantity': qty_to_split}, context=wiz_context)
                            try:
                                self.pool.get(wizard_values['res_model']).split(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                info_list.append(_("Line %s of the Excel file produced a split for the line %s.") % (l.file_line_number, ln))
                                new_move_ids = move_obj.search(cr, uid, [('wizard_pick_id', '=', obj.id),
                                                                        ('id', 'not in', already_treated),
                                                                        ('id', 'not in', move_ids),
                                                                        ('line_number', '=', ln)], order='id desc')
                                new_move_id = new_move_ids[0]
                                move_ids.append(new_move_id)
                                move_obj.write(cr, uid, [new_move_id], {'product_uom': l.uom_id.id,
                                                                        'quantity': l.quantity,
                                                                        'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                                        'expiry_date': l.expiry_date}, context=context)
                            except osv.except_osv as osv_error:
                                error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : %s") % (l.file_line_number, osv_error.value))
                                line_with_error.append(list(l.line_values))
                                ignore_lines += 1
                                processed_lines -= 1
                                percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                self.write(cr, uid, ids, {'percent_completed':percent_completed})
                                break
                            if m.product_id.id != l.product_id.id:
                                # Call the change product wizard
                                wizard_values = move_obj.change_product(cr, uid, new_move_id, context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']], {'change_reason': 'Import changed product', 'new_product_id': l.product_id.id}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).change_product(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                info_list.append(_("Line %s of the Excel file: The product did not match with the existing product of the line, so we change the from [%s] %s to [%s] %s.") % (l.file_line_number, m.product_id.default_code, m.product_id.name, l.product_id.default_code, l.product_id.name))
                                
                            if m.product_uom.id != l.uom_id.id:
                                info_list.append(_("Line %s of the Excel file: The product UOM did not match with the existing product UoM of the line, so we change the UoM from %s to %s.") % (l.file_line_number, m.product_uom.name, l.uom_id.name))
                                
                            complete_lines += 1
                            break
                        # Don't split the move if the quantity ordered is equal to the quantity of the line and the move quantity is not filled
                        elif m.quantity_ordered == l.quantity and m.quantity == 0.00 and m.product_uom.category_id.id == l.uom_id.category_id.id:
                            ok = True
                            move_obj.write(cr, uid, [m.id], {'product_uom': l.uom_id.id,
                                                             'quantity': l.quantity,
                                                             'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                             'expiry_date': l.expiry_date}, context=context)
                            if m.product_id.id != l.product_id.id:
                                # Call the change product wizard
                                wizard_values = move_obj.change_product(cr, uid, m.id, context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']], {'change_reason': 'Import changed product', 'new_product_id': l.product_id.id}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).change_product(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                info_list.append(_("Line %s of the Excel file: The product did not match with the existing product of the line, so we change the from [%s] %s to [%s] %s.") % (l.file_line_number, m.product_id.default_code, m.product_id.name, l.product_id.default_code, l.product_id.name))
                                
                            if m.product_uom.id != l.uom_id.id:
                                info_list.append(_("Line %s of the Excel file: The product UOM did not match with the existing product UoM of the line, so we change the UoM from %s to %s.") % (l.file_line_number, m.product_uom.name, l.uom_id.name))
                                
                            complete_lines += 1
                            break
                        
                    if not ok:
                        error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : A line was found in the Incoming shipment but the quantity of the Excel line (%s %s) exceeds the quantity of the incoming shipment line that the system is able to split.") % (l.file_line_number, l.quantity, l.uom_id.name))
                        line_with_error.append(list(l.line_values))
                        ignore_lines += 1
                        
            # 4/ The number of moves is biggest than the number of lines
            elif nb_moves > nb_lines:
                '''
                In this case, search the best move corresponding to line and update data
                '''
                # Treat after the lines which not match directly
                remaining_lines = []
                already_treated = []
                for l in import_obj.browse(cr, uid, line_ids, context=context):
                    remaining_qty = l.quantity
                    match_ids = move_obj.search(cr, uid, [('id', 'in', move_ids),
                                                          ('id', 'not in', already_treated),
                                                          ('product_id', '=', l.product_id.id),
                                                          ('product_uom', '=', l.uom_id.id)], context=context)
                    # Treat after if no move match with the line
                    if not match_ids:
                        remaining_lines.append(l.id)
                        continue
                    
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    last_move = False
                    # Fill moves while there is quantity to fill
                    while remaining_qty:
                        # In case where is no move available, add the remaining qty to the last move filled
                        if not match_ids:
                            move_obj.write(cr, uid, [last_move.id], {'quantity': best_move.quantity_ordered + remaining_qty,
                                                                     'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                                     'expiry_date': l.expiry_date}, context=context)
                            break
                        
                        # Search the best move
                        diff_qty = False
                        best_move = False
                        for m in move_obj.browse(cr, uid, match_ids, context=context):
                            if not best_move:
                                best_move = m
                                diff_qty = abs(m.quantity_ordered - l.quantity)
                            if abs(m.quantity_ordered - l.quantity) < diff_qty:
                                best_move = m
                                diff_qty = abs(m.quantity_ordered - l.quantity)
                                
                        move_obj.write(cr, uid, [best_move.id], {'quantity': min(best_move.quantity_ordered, remaining_qty),
                                                                 'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                                 'expiry_date': l.expiry_date}, context=context)
                        remaining_qty -= min(best_move.quantity_ordered, remaining_qty)
                        last_move = best_move
                        match_ids.remove(best_move.id)
                        
                    complete_lines += 1
                    already_treated.append(best_move)
                    
                for l in import_obj.browse(cr, uid, remaining_lines, context=context):
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    ok = False
                    for m in move_obj.browse(cr, uid, move_ids, context=context):
                        if m.id in already_treated or m.product_uom.category_id.id != l.uom_id.category_id.id:
                            continue
                        else:
                            ok = True
                            
                            if m.product_id.id != l.product_id.id:
                                # Call the change product wizard
                                wizard_values = move_obj.change_product(cr, uid, m.id, context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']], {'change_reason': 'Import changed product', 'new_product_id': l.product_id.id}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).change_product(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                info_list.append(_("Line %s of the Excel file: The product did not match with the existing product of the line, so we change the from [%s] %s to [%s] %s.") % (l.file_line_number, m.product_id.default_code, m.product_id.name, l.product_id.default_code, l.product_id.name))
                                
                            if m.product_uom.id != l.uom_id.id:
                                info_list.append(_("Line %s of the Excel file: The product UOM did not match with the existing product UoM of the line, so we change the UoM from %s to %s.") % (l.file_line_number, m.product_uom.name, l.uom_id.name))
                                
                            move_obj.write(cr, uid, [m.id], {'product_uom': l.uom_id.id,
                                                             'quantity': l.quantity,
                                                             'prodlot_id': l.prodlot_id and l.prodlot_id.id or False,
                                                             'expiry_date': l.expiry_date}, context=context)
                            complete_lines += 1
                            already_treated.append(m.id)
                            break
                            
                    if not ok:
                        error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : A line was found in the Incoming shipment but the UoM of the Excel line (%s) is not compatible with UoM (%s) of the incoming shipment line.") % (l.file_line_number, l.uom_id.name, m.product_uom.name))
                        line_with_error.append(list(l.line_values))
                        ignore_lines += 1
                    
        error += '\n'.join(error_list)
        info += '\n'.join(info_list)
        message = '''Importation completed !
# of imported lines : %s
# of ignored lines : %s

Reported errors :
%s

%s
%s
                '''  % (complete_lines, ignore_lines, error or 'No error !', info and 'Reported information :' or '', info or '')
        vals = {'message': message, 'percent_completed': percent_completed}
        if line_with_error:
            file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error)
            vals.update(file_to_export)
            vals.update({'import_error_ok': True})
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
            raise osv.except_osv(_('Error'), _('No line to process.'))
        
        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(file_to_import))
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
        Otherwise, you can continue to use Unifield.""")
        self.write(cr, uid, ids, {'import_in_progress': True, 'message': msg_to_return})
        
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, fileobj, context))
        thread.start()
        # the windows must be updated to display the message
        return self.pool.get('wizard').open_wizard(cr, uid, ids, type='update', context=context)

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
                <field name="import_in_progress" invisible="1" />
                <group name="import_file_lines" string="Import Lines" colspan="28" col="7">
                <field name="file_to_import" filename="filename_template" colspan="2"/>
                <button name="import_file" string="Import the file" icon="gtk-execute" colspan="1" type="object" />
                <field name="import_error_ok" invisible="1"/>
                <field name="filename" invisible="1"  />
                <button name="dummy" string="Update" icon="gtk-execute" colspan="1" type="object" />
                <newline />
                <field name="percent_completed" widget="progressbar" attrs="{'invisible': [('import_in_progress', '=', False)]}" />
                <field name="data" filename="filename" colspan="2" attrs="{'invisible':[('import_error_ok', '=', False)]}"/>
                </group>
                <field name="message" attrs="{'invisible':[('import_in_progress', '=', False)]}" colspan="4" nolabel="1"/>
                """
                # add field in arch
                arch = result['arch']
                l = arch.split('<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>')
                arch = l[0]
                arch += '<button name="uncopy_all" string="Clear all" colspan="1" type="object" icon="gtk-undo"/>' + new_field_txt + l[1]
                result['arch'] = arch
                
        return result

stock_partial_picking()
