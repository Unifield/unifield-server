# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import threading
import pooler
import base64
import time
import os
import tools
import datetime
import logging

from mx import DateTime
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from tools.translate import _

NB_OF_HEADER_LINES = 11
NB_LINES_COLUMNS = 9
ORDER_PRIORITY_BY_VALUE = dict((_(y), x) for x, y in ORDER_PRIORITY)
ORDER_CATEGORY_BY_VALUE = dict((_(y), x) for x, y in ORDER_CATEGORY)
LINES_COLUMNS = [
    (0, _('Line number'), 'mandatory', ('order_id', '!=', False)),
    (1, _('Product Code'), 'optionnal'),
    (2, _('Product Description'), 'optionnal'),
    (3, _('Quantity'), 'mandatory'),
    (4, _('Cost Price'), 'optionnal'),
    (5, _('UoM'), 'mandatory'),
    (6, _('Currency'), 'optionnal'),
    (7, _('Comment'), 'optionnal'),
    (8, _('Date of Stock Take'), 'optionnal'),
]


class internal_request_import(osv.osv):
    _name = 'internal.request.import'
    _rec_name = 'order_id'

    _columns = {
        'state': fields.selection([('draft', 'Draft'),
                                   ('simu_progress', 'Simulation in progress'),
                                   ('simu_done', 'Simulation done'),
                                   ('import_progress', 'Import in progress'),
                                   ('error', 'Error'),
                                   ('done', 'Done')], string='State', readonly=True),
        # File information
        'file_to_import': fields.binary(string='File to import'),
        'filename': fields.char(size=64, string='Filename'),
        'message': fields.text(string='Import message', readonly=True),
        'error_file': fields.binary(string='File with errors'),
        'error_filename': fields.char(size=64, string='Lines with errors'),
        'nb_file_lines': fields.integer(string='Total of file lines', readonly=True),
        'nb_treated_lines': fields.integer(string='Nb treated lines', readonly=True),
        'percent_completed': fields.float(string='Percent completed', readonly=True),
        'import_error_ok': fields.boolean(string='Error at import'),
        'no_prod_as_comment': fields.boolean(string='Change Product to a Comment if Product is not found'),
        'date_done': fields.datetime(string='Date of finished import', readonly=True),
        # IR Header Info
        # # Original IR info
        'order_id': fields.many2one('sale.order', string='Internal Request', readonly=True),
        'in_categ': fields.related('order_id', 'categ', type='selection', selection=ORDER_CATEGORY,
                                   string='Order Category', readonly=True),
        'in_priority': fields.related('order_id', 'priority', type='selection', selection=ORDER_PRIORITY,
                                      string='Priority', readonly=True),
        'in_requested_date': fields.related('order_id', 'delivery_requested_date', type='date', string='Requested date', readonly=True),
        'in_requestor': fields.related('order_id', 'requestor', type='char', string='Requestor', readonly=True),
        'in_loc_requestor': fields.related('order_id', 'location_requestor_id', type='many2one', relation='stock.location',
                                           string='Location Requestor', readonly=True),
        'in_origin': fields.related('order_id', 'origin', type='char', string='Origin', readonly=True),
        # # Imported IR info
        'imp_categ': fields.selection(ORDER_CATEGORY, string='Order Category', readonly=True),
        'imp_priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        'imp_requested_date': fields.date(string='Requested Date', readonly=True),
        'imp_requestor': fields.char(size=128, string='Requestor', readonly=True),
        'imp_loc_requestor': fields.many2one('stock.location', string='Location Requestor', readonly=True),
        'imp_origin': fields.char(size=64, string='Origin', readonly=True),
        'imp_line_ids': fields.one2many('internal.request.import.line', 'ir_import_id', string='Lines', readonly=True),
    }

    _defaults = {
        'state': lambda *args: 'draft',
        'nb_treated_lines': 0,
    }

    def reset_import(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'internal.request.import',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'same',
            'context': context,
        }

    def go_to_ir(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        ctx = context.copy()
        ctx.update({'procurement_request': True})
        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            order_id = wiz['order_id'][0]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': order_id,
                'context': ctx,
            }

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Display the simulation screen
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if ids and self.browse(cr, uid, ids, context=context)[0].state == 'done':
            return self.go_to_ir(cr, uid, ids, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': ids[0],
                'target': 'same',
                'context': context}

    def launch_simulate(self, cr, uid, ids, context=None):
        '''
        Launch the simulation routine in background
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for ir_imp in self.browse(cr, uid, ids, context=context):
            if not ir_imp.file_to_import:
                raise osv.except_osv(_('Error'), _('No file to import'))
            xml_file = base64.decodestring(ir_imp.file_to_import)
            excel_file = SpreadsheetXML(xmlstring=xml_file)
            if not excel_file.getWorksheets():
                raise osv.except_osv(_('Error'), _('The given file is not a valid Excel 2003 Spreadsheet file !'))

        self.write(cr, uid, ids, {'state': 'simu_progress'}, context=context)
        cr.commit()
        new_thread = threading.Thread(target=self.simulate, args=(cr.dbname, uid, ids, context))
        new_thread.start()
        new_thread.join(10.0)

        return self.go_to_simulation(cr, uid, ids, context=context)

    def get_values_from_excel(self, cr, uid, file_to_import, context=None):
        '''
        Read the Excel XML file and put data in values
        '''
        values = {}
        # Read the XML Excel file
        xml_file = base64.decodestring(file_to_import)
        fileobj = SpreadsheetXML(xmlstring=xml_file)

        # Read all lines
        rows = fileobj.getRows()

        # Get values per line
        index = 0
        for row in rows:
            index += 1
            values.setdefault(index, [])
            for cell_nb in range(len(row)):
                cell_data = row.cells and row.cells[cell_nb] and \
                    row.cells[cell_nb].data
                values[index].append(cell_data)

        return values

    def simulate(self, dbname, uid, ids, context=None):
        '''
        Import the file and fill the data in simulation screen
        '''
        cr = pooler.get_db(dbname).cursor()
        try:
            ir_imp_l_obj = self.pool.get('internal.request.import.line')
            so_obj = self.pool.get('sale.order')
            prod_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            loc_obj = self.pool.get('stock.location')

            if context is None:
                context = {}

            if isinstance(ids, (int, long)):
                ids = [ids]

            for ir_imp in self.browse(cr, uid, ids, context=context):
                nb_treated_lines = 0
                # No file => Return to the simulation screen
                if not ir_imp.file_to_import:
                    self.write(cr, uid, [ir_imp.id], {'message': _('No file to import'),
                                                      'state': 'draft'}, context=context)
                    continue

                nb_file_header_lines = NB_OF_HEADER_LINES
                nb_file_lines_columns = NB_LINES_COLUMNS
                first_line_index = nb_file_header_lines + 1

                # Variables
                lines_to_ignored = []   # Bad formatting lines
                file_format_errors = []
                values_header_errors = []
                values_line_errors = []
                blocked = False
                message = ''
                ir_order = ir_imp.order_id

                header_values = {}

                values = self.get_values_from_excel(cr, uid, ir_imp.file_to_import, context=context)

                '''
                We check for each line if the number of columns is consistent
                with the expected number of columns :
                  * For IR header information : 1 columns
                  * For the line information : 9 columns
                '''
                # Check number of columns on lines

                for x in xrange(2, nb_file_header_lines+1):
                    nb_to_check = 2
                    if nb_file_header_lines >= x > NB_OF_HEADER_LINES:
                        continue
                    if len(values.get(x, [])) != nb_to_check:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The header information must be on two columns : Column A for name of the field and column B for value.') % x
                        file_format_errors.append(error_msg)

                if len(values.get(first_line_index, [])) < nb_file_lines_columns:
                    error_msg = _('Line %s of the Excel file: This line is mandatory and must have at least %s columns. The values on this line must be the name of the field for IR lines.') \
                                % (first_line_index, nb_file_lines_columns)
                    file_format_errors.append(error_msg)

                for x in xrange(first_line_index, len(values)+1):
                    if len(values.get(x, [])) < nb_file_lines_columns:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The line information must be on at least %s columns. The line %s has %s columns') % (x, nb_file_lines_columns, x, len(values.get(x, [])))
                        file_format_errors.append(error_msg)

                nb_file_lines = len(values) - first_line_index
                self.write(cr, uid, [ir_imp.id], {'nb_file_lines': nb_file_lines}, context=context)

                if len(file_format_errors):
                    message = '''## IMPORT STOPPED ##

    Nothing has been imported because of bad file format. See below :

    ## File format errors ##\n\n'''
                    for err in file_format_errors:
                        message += '%s\n' % err

                    self.write(cr, uid, [ir_imp.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [ir_imp.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res

                '''
                Now, we know that the file has the good format, you can import data for header.
                '''
                # Line 2: Order Reference
                if ir_order:
                    if not values.get(2, [])[1] or ir_order.name != values.get(2, [])[1]:
                        blocked = True
                        values_header_errors.append(_('Line 2 of the file: IR Order Reference \'%s\' is not correct.') %
                                                    (values.get(2, [])[1],))
                elif not ir_order and values.get(2, [])[1]:  # Search for existing IR
                    ir_ids = so_obj.search(cr, uid, [('procurement_request', '=', True),
                                                     ('name', '=', values.get(2, [])[1])], limit=1, context=context)
                    if ir_ids:
                        ir_order = so_obj.browse(cr, uid, ir_ids[0], context=context)
                        for ir_line in ir_order.order_line:
                            imp_line_data = {
                                'ir_import_id': ir_imp.id,
                                'ir_line_id': ir_line.id,
                                'in_line_number': ir_line.line_number
                            }
                            ir_imp_l_obj.create(cr, uid, imp_line_data, context=context)
                    else:
                        blocked = True
                        values_header_errors.append(_('Line 2 of the file: You can not import this file with a non-existing IR Order Reference.'))

                # Line 4: Order Category
                categ = values.get(4, [])[1]
                if categ in ORDER_CATEGORY_BY_VALUE:
                    header_values['imp_categ'] = ORDER_CATEGORY_BY_VALUE[categ]
                elif not ir_order:
                    values_header_errors.append(
                        _('Line 4 of the file: Order Category \'%s\' not defined, default value will be \'Other\'')
                        % (categ or False,))
                    header_values['imp_categ'] = 'other'

                # Line 5: Priority
                priority = values.get(5, [])[1]
                if priority in ORDER_PRIORITY_BY_VALUE:
                    header_values['imp_priority'] = ORDER_PRIORITY_BY_VALUE[priority]
                elif not ir_order:
                    values_header_errors.append(
                        _('Line 5 of the file: Order Priority \'%s\' not defined, default value will be \'Normal\'')
                        % (priority or False,))
                    header_values['imp_priority'] = 'normal'

                # Line 7: Requested date
                req_date = values.get(7, [])[1]
                if req_date:
                    if type(req_date) == type(DateTime.now()):
                        req_date = req_date.strftime('%d-%m-%Y')
                        header_values['imp_requested_date'] = req_date
                    else:
                        try:
                            time.strptime(req_date, '%d-%m-%Y')
                            header_values['imp_requested_date'] = req_date
                        except:
                            blocked = True
                            values_header_errors.append(_('Line 7 of the file: The Requested Date \'%s\' must be formatted like \'DD-MM-YYYY\'')
                                                        % req_date)
                elif not ir_order:
                    blocked = True
                    values_header_errors.append(
                        _('Line 7 of the file: The Requested Date is mandatory in the first import.'))

                # Line 8: Requestor
                if values.get(8, [])[1]:
                    header_values['imp_requestor'] = values.get(8, [])[1]
                elif not ir_order:
                    blocked = True
                    values_header_errors.append(_('Line 8 of the file: The Requestor is mandatory in the first import.'))

                # Line 9: Location Requestor
                loc_req = values.get(9, [])[1]
                if loc_req:
                    ir_loc_req_domain = [
                        ('name', '=ilike', loc_req), '&',
                        ('location_category', '!=', 'transition'), '|', ('usage', '=', 'internal'), '&',
                        ('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')
                    ]
                    loc_ids = loc_obj.search(cr, uid, ir_loc_req_domain, limit=1, context=context)
                    if loc_ids:
                        header_values['imp_loc_requestor'] = loc_ids[0]
                    else:
                        blocked = True
                        values_header_errors.append(_('Line 9 of the file: The Location Requestor \'%s\' does not match possible options.')
                                                    % (loc_req,))
                elif not ir_order:
                    blocked = True
                    values_header_errors.append(_('Line 9 of the file: The Location Requestor is mandatory.'))

                # Line 10: Origin
                if not ir_order:
                    if values.get(10, [])[1]:
                        header_values['imp_origin'] = values.get(10, [])[1]
                    else:
                        blocked = True
                        values_header_errors.append(_('Line 10 of the file: The Origin is mandatory in the first import.'))

                '''
                The header values have been imported, start the importation of
                lines
                '''
                in_line_numbers = []  # existing line numbers
                imp_line_numbers = []  # imported line numbers
                if ir_order:  # get the lines numbers
                    in_line_numbers = [line.line_number for line in ir_order.order_line]

                # Loop on lines
                for x in xrange(first_line_index+1, len(values)+1):
                    line_errors = ''
                    # Check mandatory fields
                    for manda_field in LINES_COLUMNS:
                        if manda_field[2] == 'mandatory' and not values.get(x, [])[manda_field[0]]:
                            required_field = True
                            if len(manda_field) > 3 and isinstance(manda_field[3], (tuple, list, )) and \
                                    len(manda_field[3]) == 3:
                                col, op, val = manda_field[3]
                                if op == '!=':
                                    required_field = ir_imp[col] != val
                                else:
                                    required_field = ir_imp[col] == val
                            if required_field:
                                line_errors += _('The column \'%s\' mustn\'t be empty%s. ') \
                                               % (manda_field[1], manda_field[0] == 0 or '')

                    # Get values
                    line_data = {}
                    duplicate_line = False
                    product_id = False
                    product = False

                    vals = values.get(x, [])
                    # Line number
                    if in_line_numbers:
                        if vals[0]:
                            try:
                                line_n = int(vals[0])
                                line_data.update({'imp_line_number': line_n})
                                if line_n in imp_line_numbers:
                                    line_errors += _('Line Number \'%s\' has already been treated. ') % (line_n,)
                                    duplicate_line = True
                                else:
                                    imp_line_numbers.append(line_n)
                            except:
                                line_errors += _('Line Number must be an integer. ')
                        else:
                            line_errors += _('Line Number is mandatory to update a line. ')

                    # Product and Comment
                    product_code = vals[1]
                    comment = vals[7]
                    if product_code:
                        prod_ids = prod_obj.search(cr, uid, [('default_code', '=', product_code)], limit=1, context=context)
                        if prod_ids:
                            product_id = prod_ids[0]
                            prod_cols = ['standard_price', 'uom_id', 'uom_po_id']
                            product = prod_obj.read(cr, uid, product_id, prod_cols, context=context)
                            line_data.update({
                                'imp_product_id': product_id,
                                'imp_comment': comment or '',
                            })
                        else:
                            if ir_imp.no_prod_as_comment:
                                line_data.update({'imp_comment': product_code + '\n' + comment})
                            else:
                                line_data.update({'imp_comment': comment or ''})
                                line_errors += _('Product \'%s\' does not exist in this database. ') % vals[1]
                    else:
                        line_data.update({'imp_comment': comment or ''})
                        if not comment:
                            line_errors += _('Product Code is mandatory. ')

                    # Quantity
                    qty = vals[3] or 0.00
                    try:
                        qty = float(qty)
                        line_data.update({'imp_qty': qty})
                    except:
                        line_errors += _('Quantity must be a number. ')

                    # Cost Price and UoM
                    if product_id and product:
                        line_data.update({'imp_cost_price': product['standard_price']})
                        uom_ids = uom_obj.search(cr, uid, [('name', '=', vals[5])], limit=1, context=context)
                        if uom_ids and uom_ids[0] in [product['uom_id'][0], product['uom_po_id'][0]]:
                            line_data.update({'imp_uom_id': uom_ids[0]})
                        else:
                            line_errors += _('UoM \'%s\' is not consistent with the Product \'%s\'. ') \
                                           % (vals[1], vals[5])

                    line_data.update({
                        'error_msg': line_errors,
                        'ir_import_id': ir_imp.id,
                    })

                    if len(line_errors):
                        values_line_errors.append(_('Line %s of the file: %sLine not imported.') % (x, line_errors))

                    if not duplicate_line and in_line_numbers and line_data.get('imp_line_number') \
                            and line_data['imp_line_number'] in in_line_numbers:
                        l_ids = ir_imp_l_obj.search(cr, uid, [('ir_import_id', '=', ir_imp.id),
                                                              ('in_line_number', '=', line_data['imp_line_number'])],
                                                    context=context)
                        if l_ids:
                            ir_imp_l = ir_imp_l_obj.browse(cr, uid, l_ids[0], context=context)
                            if (line_data.get('imp_product_id') and ir_imp_l.in_product_id.id != line_data['imp_product_id']) \
                                    or (line_data.get('imp_qty') and ir_imp_l.in_qty != line_data['imp_qty']) \
                                    or (line_data.get('imp_uom_id') and ir_imp_l.in_uom.id != line_data['imp_uom_id']) \
                                    or (line_data.get('imp_comment') and ir_imp_l.in_comment != line_data['imp_comment']):
                                line_data.update({'line_type': 'changed'})
                        ir_imp_l_obj.write(cr, uid, l_ids, line_data, context=context)
                    else:
                        line_data.update({'line_type': 'new'})
                        ir_imp_l_obj.create(cr, uid, line_data, context=context)
                    nb_treated_lines += 1

                '''
                We generate the message which will be displayed on the simulation
                screen. This message is a merge between all errors.
                '''
                # Generate the message
                import_error_ok = False
                if len(values_header_errors):
                    import_error_ok = True
                    message += _('\n## Errors on header values ##\n\n')
                    for err in values_header_errors:
                        message += '%s\n' % err

                if len(values_line_errors):
                    import_error_ok = True
                    message += _('\n## Errors on line values ##\n\n')
                    for err in values_line_errors:
                        message += '%s\n' % err

                header_values.update({
                    'order_id': ir_order and ir_order.id,
                    'message': message,
                    'state': blocked and 'error' or 'simu_done',
                    'percent_completed': 100.0,
                    'import_error_ok': import_error_ok,
                    'nb_treated_lines': nb_treated_lines,
                })
                self.write(cr, uid, [ir_imp.id], header_values, context=context)

            cr.commit()
            cr.close(True)

        except Exception, e:
            logging.getLogger('internal.request.import').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e}, context=context)
            cr.commit()
            cr.close(True)

        return True

    def launch_import(self, cr, uid, ids, context=None):
        '''
        Launch the simulation routine in background
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        active_wiz = self.browse(cr, uid, ids, fields_to_fetch=['state', 'order_id'], context=context)[0]

        # To prevent adding multiple lines by clicking multiple times on the import button
        if active_wiz.state != 'simu_done':
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'internal.request.import',
                'res_id': active_wiz.id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
            }

        self.write(cr, uid, ids, {'state': 'import_progress', 'percent_completed': 0.00}, context=context)

        cr.commit()
        new_thread = threading.Thread(target=self.run_import, args=(cr.dbname, uid, ids, context))
        new_thread.start()
        new_thread.join(10.0)

        if new_thread.isAlive():
            return self.go_to_simulation(cr, uid, ids, context=context)
        return self.go_to_ir(cr, uid, ids, context=context)

    def run_import(self, dbname, uid, ids, context=None):
        '''
        Launch the real import
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        cr = pooler.get_db(dbname).cursor()
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')

        try:
            for wiz in self.browse(cr, uid, ids, context=context):
                self.write(cr, uid, [wiz.id], {'state': 'import_progress'}, context=context)
                if wiz.order_id:  # update IR
                    ir_vals = {
                        'delivery_requested_date': wiz.imp_requested_date,
                        'requestor': wiz.imp_requestor,
                        'location_requestor_id': wiz.imp_loc_requestor.id,
                    }
                    if wiz.imp_categ:
                        ir_vals.update({'categ': wiz.imp_categ})
                    if wiz.imp_priority:
                        ir_vals.update({'priority': wiz.imp_priority})
                    so_obj.write(cr, uid, wiz.order_id.id, ir_vals, context=context)
                    for line in wiz.imp_line_ids:
                        if not line.error_msg:
                            line_vals = {
                                'product_id': line.imp_product_id and line.imp_product_id.id or False,
                                'product_uom_qty': line.imp_qty or 0.00,
                                'comment': line.imp_comment or '',
                            }
                            if line.imp_uom_id:
                                line_vals.update({'product_uom': line.imp_uom_id.id})
                            if line.ir_line_id:  # update IR line
                                sol_obj.write(cr, uid, line.ir_line_id.id, line_vals, context=context)
                            else:  # create IR line
                                line_vals.update({
                                    'order_id': wiz.order_id.id,
                                    'cost_price': line.imp_cost_price or 0.00,
                                    'price_unit': line.imp_cost_price or 0.00,
                                })
                                sol_obj.create(cr, uid, line_vals, context=context)
                else:  # Create IR
                    ir_vals = {
                        'procurement_request': True,
                        'categ': wiz.imp_categ,
                        'priority': wiz.imp_priority,
                        'delivery_requested_date': wiz.imp_requested_date,
                        'requestor': wiz.imp_requestor,
                        'location_requestor_id': wiz.imp_loc_requestor.id,
                        'origin': wiz.imp_origin,
                        'order_line': [(0, 0, {
                            'product_id': x.imp_product_id and x.imp_product_id.id or False,
                            'product_uom_qty': x.imp_qty or 0.00,
                            'cost_price': x.imp_cost_price or 0.00,
                            'price_unit': x.imp_cost_price or 0.00,
                            'product_uom': x.imp_uom_id and x.imp_uom_id.id or False,
                            'comment': x.imp_comment or '',
                        }) for x in (y for y in wiz.imp_line_ids if not y.error_msg)],
                    }
                    new_ir_id = so_obj.create(cr, uid, ir_vals, context=context)
                    self.write(cr, uid, [wiz.id], {'order_id': new_ir_id}, context=context)

            if ids:
                self.write(cr, uid, ids, {'state': 'done', 'date_done': datetime.datetime.now(), 'percent_completed': 100.00},
                           context=context)
                res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
            else:
                res = True

            cr.commit()
            cr.close(True)
        except Exception, e:
            logging.getLogger('ir.simulation.run').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e}, context=context)
            res = True
            cr.commit()
            cr.close(True)

        return res


internal_request_import()


class internal_request_import_line(osv.osv):
    _name = 'internal.request.import.line'
    _rec_name = 'in_line_number'

    def _get_line_info(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'ir_line_id': False,
                'in_line_number': False,
                'in_product_id': False,
                'in_qty': 0.00,
                'in_cost_price': 0.00,
                'in_uom': False,
                'in_comment': False,
            }
            if line.ir_line_id:
                l = line.ir_line_id
                res[line.id].update({
                    'ir_line_id': l.id,
                    'in_line_number': l.line_number or False,
                    'in_product_id': l.product_id and l.product_id.id or False,
                    'in_qty': l.product_uom_qty,
                    'in_cost_price': l.price_unit,
                    'in_uom': l.product_uom and l.product_uom.id,
                    'in_comment': l.comment,
                })

        return res

    _columns = {
        'ir_line_id': fields.many2one('sale.order.line', string='Line', readonly=True),
        'ir_import_id': fields.many2one('internal.request.import', string='Simulation screen', readonly=True, ondelete='cascade'),
        'line_type': fields.char(size=64, string='Type of Line', readonly=True),
        # # Original IR line info
        'in_line_number': fields.function(_get_line_info, method=True, multi='line', type='integer',
                                          string='Line Number', readonly=True, store=True),
        'in_product_id': fields.function(_get_line_info, method=True, multi='line', type='many2one',
                                         relation='product.product', string='Product', readonly=True, store=True),
        'in_qty': fields.function(_get_line_info, method=True, multi='line', type='float',
                                  string='Quantity', readonly=True, store=True),
        'in_cost_price': fields.function(_get_line_info, method=True, multi='line', type='float',
                                         string='Cost Price', readonly=True, store=True),
        'in_uom': fields.function(_get_line_info, method=True, multi='line', type='many2one',
                                  relation='product.uom', string='UoM', readonly=True, store=True),
        'in_comment': fields.function(_get_line_info, method=True, multi='line', type='char',
                                      size=256, string='Comment', readonly=True, store=True),
        # # Imported IR line info
        'imp_line_number': fields.integer(string='Line Number'),
        'imp_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'imp_qty': fields.float(digits=(16, 2), string='Quantity', readonly=True),
        'imp_cost_price': fields.float(digits=(16, 2), string='Cost Price', readonly=True),
        'imp_uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_comment': fields.char(size=256, string='Comment', readonly=True),
        'error_msg': fields.text(string='Error message', readonly=True),
    }

    defaults = {
        'line_type': False,
        'imp_line_number': 0,
    }

    def get_error_msg(self, cr, uid, ids, context=None):
        '''
        Display the error message
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.error_msg:
                raise osv.except_osv(_('Warning'), line.error_msg)

        return True


internal_request_import_line()
