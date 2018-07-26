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

from lxml import etree
from lxml.etree import XMLSyntaxError
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from sale import SALE_ORDER_STATE_SELECTION
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from tools.translate import _

NB_OF_HEADER_LINES = 11
NB_LINES_COLUMNS = 9
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

    def _get_fake_state(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for ir_import in self.read(cr, uid, ids, ['state', 'in_state', 'imp_state']):
            res[ir_import['id']] = {
                'wiz_fake_state': ir_import['state'],
                'in_fake_state': ir_import['in_state'],
                'imp_fake_state': ir_import['imp_state'],
            }
        return res

    _columns = {
        'wiz_fake_state': fields.function(_get_fake_state, type='char', method=True, multi='line', string='State',
                                          help='for internal use only'),
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
        # IR Header Info
        # # Original IR info
        'order_id': fields.many2one('sale.order', string='Internal Request', readonly=True),
        'in_order_name': fields.related('order_id', 'name', type='char', string='Order Reference', readonly=True),
        'in_state': fields.related('order_id', 'state', type='selection', selection=SALE_ORDER_STATE_SELECTION,
                                   string='State', readonly=True),
        'in_fake_state': fields.function(_get_fake_state, type='char', method=True, multi='line', string='State',
                                         help='for internal use only'),
        'in_categ': fields.related('order_id', 'categ', type='selection', selection=ORDER_CATEGORY,
                                   string='Order Category', readonly=True),
        'in_priority': fields.related('order_id', 'priority', type='selection', selection=ORDER_PRIORITY,
                                   string='Priority', readonly=True),
        'in_creation_date': fields.related('order_id', 'date_order', type='date', string='Creation date', readonly=True),
        'in_requested_date': fields.related('order_id', 'delivery_requested_date', type='date', string='Requested date', readonly=True),
        'in_requestor': fields.related('order_id', 'requestor', type='char', string='Requestor', readonly=True),
        'location_requestor_id': fields.many2one('stock.location', string='Stock Location'),
        'in_loc_requestor': fields.related('location_requestor_id', 'name', type='char', size=64,
                                           string='Location Requestor', store=False, readonly=True),
        'in_origin': fields.related('order_id', 'origin', type='char', string='Origin', readonly=True),
        'functional_currency_id': fields.many2one('stock.location', string='Stock Location'),
        'in_functional_currency': fields.related('functional_currency_id', 'name', type='char', size=64,
                                                 string='Functional Currency', store=False, readonly=True),
        # # Imported IR info
        'imp_order_name': fields.char(size=64, string='Order Refererence', readonly=True),
        'imp_state': fields.selection(selection=SALE_ORDER_STATE_SELECTION, string='State', readonly=True),
        'imp_fake_state': fields.function(_get_fake_state, type='char', method=True, multi='line',
                                          string='State', help='for internal use only'),
        'imp_categ': fields.selection(ORDER_CATEGORY, string='Order Category', readonly=True),
        'imp_priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        'imp_creation_date': fields.datetime(string='Creation Date', readonly=True),
        'imp_requested_date': fields.datetime(string='Requested Date', readonly=True),
        'imp_requestor': fields.char(size=128, string='Requestor', readonly=True),
        'imp_loc_requestor': fields.char(size=64, string='Location Requestor', readonly=True),
        'imp_origin': fields.char(size=64, string='Origin', readonly=True),
        'imp_functional_currency': fields.char(size=64, string='Functional Currency', readonly=True),
        'imp_line_ids': fields.one2many('internal.request.line.import', 'ir_import_id', string='Lines', readonly=True),
    }

    _defaults = {
        'state': lambda *args: 'draft',
        # 'wiz_fake_state': 'draft',
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

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Display the simulation screen
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        # if ids and self.browse(cr, uid, ids, context=context)[0].state == 'done':
        #     return

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
            ir_imp_l_obj = self.pool.get('internal.request.line.import')
            prod_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            loc_obj = self.pool.get('stock.location')

            # Declare global variables (need this explicit declaration to clear them at the end of the treatment)
            global PRODUCT_CODE_ID
            global UOM_NAME_ID
            global CURRENCY_NAME_ID
            global SIMU_LINES

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

                for line in ir_imp.imp_line_ids:
                    # Put data in cache
                    if line.in_product_id:
                        PRODUCT_CODE_ID.setdefault(line.in_product_id.default_code, line.in_product_id.id)
                    if line.in_uom:
                        UOM_NAME_ID.setdefault(line.in_uom.name, line.in_uom.id)
                    if line.in_currency:
                        CURRENCY_NAME_ID.setdefault(line.in_currency.name, line.in_currency.id)

                    '''
                    First of all, we build a cache for simulation screen lines
                    '''
                    l_num = line.in_line_number
                    l_prod = line.in_product_id and line.in_product_id.id or False
                    l_uom = line.in_uom and line.in_uom.id or False
                    # By simulation screen
                    SIMU_LINES.setdefault(ir_imp.id, {})
                    SIMU_LINES[ir_imp.id].setdefault('line_ids', [])
                    SIMU_LINES[ir_imp.id]['line_ids'].append(line.id)
                    # By line number
                    SIMU_LINES[ir_imp.id].setdefault(l_num, {})
                    SIMU_LINES[ir_imp.id][l_num].setdefault('line_ids', [])
                    SIMU_LINES[ir_imp.id][l_num]['line_ids'].append(line.id)
                    # By product
                    SIMU_LINES[ir_imp.id][l_num].setdefault(l_prod, {})
                    SIMU_LINES[ir_imp.id][l_num][l_prod].setdefault('line_ids', [])
                    SIMU_LINES[ir_imp.id][l_num][l_prod]['line_ids'].append(line.id)
                    # By UoM
                    SIMU_LINES[ir_imp.id][l_num][l_prod].setdefault(l_uom, {})
                    SIMU_LINES[ir_imp.id][l_num][l_prod][l_uom].setdefault('line_ids', [])
                    SIMU_LINES[ir_imp.id][l_num][l_prod][l_uom]['line_ids'].append(line.id)
                    # By Qty
                    SIMU_LINES[ir_imp.id][l_num][l_prod][l_uom].setdefault(line.in_qty, [])
                    SIMU_LINES[ir_imp.id][l_num][l_prod][l_uom][line.in_qty].append(line.id)

                # Variables
                lines_to_ignored = []   # Bad formatting lines
                file_format_errors = []
                values_header_errors = []
                values_line_errors = []
                message = ''

                header_values = {}
                lines_values = []

                values = self.get_values_from_excel(cr, uid, ir_imp.file_to_import, context=context)

                '''
                We check for each line if the number of columns is consistent
                with the expected number of columns :
                  * For PO header information : 1 columns
                  * For the line information : 9 columns
                '''
                # Check number of columns on lines

                for x in xrange(2, nb_file_header_lines+1):
                    nb_to_check = 2
                    if nb_file_header_lines >= x > NB_OF_HEADER_LINES:
                        continue
                    if len(values.get(x, [])) != nb_to_check:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The header information must be on two columns : \
                        Column A for name of the field and column B for value.') % x
                        file_format_errors.append(error_msg)

                if len(values.get(first_line_index, [])) < nb_file_lines_columns:
                    error_msg = _('Line %s of the Excel file: This line is mandatory and must have at least %s columns. \
                    The values on this line must be the name of the field for IR lines.') \
                                % (first_line_index, nb_file_lines_columns)
                    file_format_errors.append(error_msg)

                for x in xrange(first_line_index, len(values)+1):
                    if len(values.get(x, [])) < nb_file_lines_columns:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The line information must be on at least %s columns. \
                        The line %s has %s columns') % (x, nb_file_lines_columns, x, len(values.get(x, [])))
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
                Now, we know that the file has the good format, you can import
                data for header.
                '''
                # Line 1: Order reference
                order_ref = values.get(1, [])[1]
                if order_ref != ir_imp.order_id.name:
                    message = '''## IMPORT STOPPED ##

    LINE 1 OF THE IMPORTED FILE: THE ORDER REFERENCE \
    IN THE FILE IS NOT THE SAME AS THE ORDER REFERENCE OF THE SIMULATION SCREEN.\

    YOU SHOULD IMPORT A FILE THAT HAS THE SAME ORDER REFERENCE THAN THE SIMULATION\
    SCREEN !'''
                    self.write(cr, uid, [ir_imp.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [ir_imp.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res

                # Line 2: Order Reference
                # TODO: update
                if values.get(2, [])[1]:
                    values_header_errors.append(_('Line 2 of the file: You can not import this file with an IR Order Reference.\
                    The Order Reference is system-generated at creation of object.'))

                # Line 3: State
                # Nothing to do

                # Line 4: Order Category
                # TODO: update
                if values.get(4, [])[1] in ORDER_CATEGORY:
                    header_values['imp_categ'] = values.get(4, [])[1]
                else:
                    values_header_errors.append(
                        _('Line 4 of the file: Order Category \'%s\' not defined, default value will be Other')
                        % (values.get(4, [])[1],))
                    header_values['imp_categ'] = 'other'

                # Line 5: Priority
                # TODO: update
                if values.get(5, [])[1] in ORDER_PRIORITY:
                    header_values['imp_categ'] = values.get(5, [])[1]
                else:
                    values_header_errors.append(
                        _('Line 5 of the file: Order Priority \'%s\' not defined, default value will be Normal')
                        % (values.get(5, [])[1],))
                    header_values['imp_categ'] = 'normal'

                # Line 6: Creation Date
                # Nothing to do

                # Line 7: Requested date
                req_date = values.get(7, [])[1]
                if req_date:
                    if isinstance(req_date, datetime.datetime):
                        req_date = req_date.strftime('%d-%m-%Y')
                        header_values['imp_requested_date'] = req_date
                    else:
                        try:
                            time.strptime(req_date, '%d-%m-%Y')
                            header_values['imp_requested_date'] = req_date
                        except:
                            values_header_errors.append(_('Line 7 of the file: The Requested Date \'%s\' must be \
                                                          formatted like \'DD-MM-YYYY\'') % req_date)
                else:
                    values_header_errors.append(_('Line 7 of the file: The Requested Date is mandatory.'))

                # Line 8: Requestor
                # TODO: update
                if values.get(8, [])[1]:
                    header_values['imp_requestor'] = values.get(8, [])[1]

                # Line 9: Location Requestor
                # TODO: update
                loc_req = values.get(9, [])[1]
                if loc_req:
                    ir_loc_req_domain = [
                        ('name', '=ilike', loc_req), '&',
                        ('location_category', '!=', 'transition'), '|', ('usage', '=', 'internal'), '&',
                        ('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')
                    ]
                    loc_ids = loc_obj.search(cr, uid, ir_loc_req_domain, context=context)
                    if loc_ids:
                        header_values['imp_loc_requestor'] = loc_req
                    else:
                        values_header_errors.append(_('Line 9 of the file: The Location Requestor \'%s\' does not match possible options.')
                                                    % (loc_req,))
                else:
                    values_header_errors.append(_('Line 9 of the file: The Location Requestor is mandatory.'))

                # Line 10: Origin
                # TODO: update
                if values.get(10, [])[1]:
                    header_values['imp_origin'] = values.get(10, [])[1]

                # Line 11: Location Requestor
                # Nothing to do

                '''
                The header values have been imported, start the importation of
                lines
                '''
                not_ok_file_lines = {}
                # Loop on lines
                for x in xrange(first_line_index+1, len(values)+1):
                    # Check mandatory fields
                    not_ok = False
                    file_line_error = []
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
                                not_ok = True
                                err1 = _('The column \'%s\' mustn\'t be empty%s') % (manda_field[1], manda_field[0] == 0 and ' - Line not imported' or '')
                                err = _('Line %s of the file: %s') % (x, err1)
                                values_line_errors.append(err)
                                file_line_error.append(err1)

                    if not_ok:
                        not_ok_file_lines[x] = ' - '.join(err for err in file_line_error)

                    # Get values
                    line_data = {}
                    line_errors = ''
                    product_id = False
                    product = False

                    vals = values.get(x, [])
                    # Product and Comment
                    product_code = vals[1]
                    comment = vals[7]
                    if product_code:
                        prod_ids = prod_obj.search(cr, uid, [('default_code', '=', product_code)], limit=1, context=context)
                        if prod_ids:
                            product_id = prod_ids[0]
                            prod_cols = ['name', 'standard_price', 'uom_id', 'uom_po_id']
                            product = prod_obj.read(cr, uid, product_id, prod_cols, context=context)
                            line_data.update({
                                'imp_product_id': product_id,
                                'imp_product_desc': product['name'],
                                'imp_comment': comment or '',
                            })
                        else:
                            if ir_imp.no_prod_as_comment:
                                line_data.update({'imp_comment': product_code + '\n' + comment})
                            else:
                                line_data.update({'imp_comment': comment or ''})
                                line_errors += _('Product \'%s\' does not exist in this database. It has not been imported.\n') % vals[1]
                    else:
                        line_data.update({'imp_comment': comment or ''})
                        if not comment:
                            line_errors += _('Product Code is mandatory.\n')

                    # Quantity
                    qty = vals[3] or 0.00
                    line_data.update({'imp_qty': qty})

                    # Cost Price and UoM
                    if product_id and product:
                        line_data.update({'imp_cost_price': product['standard_price']})
                        uom_ids = uom_obj.search(cr, uid, [('name', '=', vals[5])], limit=1, context=context)
                        if uom_ids and uom_ids[0] in [product['uom_id'][0], product['uom_po_id'][0]]:
                            line_data.update({'imp_uom_id': uom_ids[0]})
                        else:
                            line_errors += _('Product \'%s\' has not been imported as UoM \'%s\' is not consistent.') \
                                           % (vals[1], vals[5])

                    # Currency
                    # Nothing to do

                    # Date of Stock Take
                    # Nothing to do

                    line_data.update({'error_msg': line_errors})
                    lines_values.append(line_data)

                '''
                We generate the message which will be displayed on the simulation
                screen. This message is a merge between all errors.
                '''
                # Generate the message
                import_error_ok = False
                if len(values_header_errors):
                    import_error_ok = True
                    message += '\n## Error on header values ##\n\n'
                    for err in values_header_errors:
                        message += '%s\n' % err

                if len(values_line_errors):
                    import_error_ok = True
                    message += '\n## Error on line values ##\n\n'
                    for err in values_line_errors:
                        message += '%s\n' % err

                header_values.update({
                    'message': message,
                    'state': 'simu_done',
                    'percent_completed': 100.0,
                    'import_error_ok': import_error_ok,
                    'imp_line_ids': [(0, 0, {
                        'imp_line_number': i + 1,
                        'imp_product_id': line['imp_product_id'] or False,
                        'imp_product_desc': line['imp_product_desc'] or False,
                        'imp_qty': line['imp_qty'] or 0.00,
                        'imp_cost_price': line['imp_cost_price'] or 0.00,
                        'imp_uom_id': line['imp_uom_id'] or False,
                        'imp_comment': line['imp_comment'] or '',
                        'error_msg': line['error_msg'] or False,
                    }) for i, line in enumerate(lines_values)],
                })
                self.write(cr, uid, [ir_imp.id], header_values, context=context)

            cr.commit()
            cr.close(True)

            # Clear the cache
            PRODUCT_CODE_ID = {}
            UOM_NAME_ID = {}
            CURRENCY_NAME_ID = {}
            SIMU_LINES = {}
        except Exception, e:
            logging.getLogger('internal.request.import').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e}, context=context)
            cr.commit()
            cr.close(True)

        return True


internal_request_import()


class internal_request_line_import(osv.osv):
    _name = 'internal.request.line.import'

    def _get_line_info(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'in_line_number': False,
                'in_product_id': False,
                'in_product_desc': False,
                'in_qty': 0.00,
                'in_cost_price': 0.00,
                'in_uom': False,
                'in_currency': False,
                'in_comment': False,
                'in_dost': False,
            }
            if line.ir_line_id:
                l = line.ir_line_id
                res[line.id].update({
                    'in_line_number': l.line_number or False,
                    'in_product_id': l.product_id and l.product_id.id or False,
                    'in_product_desc': l.product_id and l.product_id.name or False,
                    'in_qty': l.product_uom_qty,
                    'in_cost_price': l.price_unit,
                    'in_uom': l.product_uom and l.product_uom.id,
                    'in_currency': l.order_id.functional_currency and l.order_id.functional_currency.id,
                    'in_comment': l.comment,
                    'in_dost': l.date_of_stock_take,
                })

        return res

    _columns = {
        'ir_line_id': fields.many2one('sale.order.line', string='Line', readonly=True),
        'ir_import_id': fields.many2one('internal.request.import', string='Simulation screen', readonly=True, ondelete='cascade'),
        # # Original IR line info
        'in_line_number': fields.function(_get_line_info, method=True, multi='line', type='integer',
                                          string='Line Number', readonly=True, store=True),
        'in_product_id': fields.function(_get_line_info, method=True, multi='line', type='many2one',
                                         relation='product.product', string='Product', readonly=True, store=True),
        'in_product_desc': fields.function(_get_line_info, method=True, multi='line', type='char',
                                           size=256, string='Description', readonly=True, store=True),
        'in_qty': fields.function(_get_line_info, method=True, multi='line', type='float',
                                  string='Quantity', readonly=True, store=True),
        'in_cost_price': fields.function(_get_line_info, method=True, multi='line', type='float',
                                         string='Cost Price', readonly=True, store=True),
        'in_uom': fields.function(_get_line_info, method=True, multi='line', type='many2one',
                                  relation='product.uom', string='UoM', readonly=True, store=True),
        'in_currency': fields.function(_get_line_info, method=True, multi='line', type='many2one',
                                       relation='res.currency', string='Currency', readonly=True, store=True),
        'in_comment': fields.function(_get_line_info, method=True, multi='line', type='char',
                                      size=256, string='Comment', readonly=True, store=True),
        'in_dost': fields.function(_get_line_info, method=True, multi='line', type='date',
                                   string='Date of Stock Take', readonly=True, store=True),
        # # Imported IR line info
        'imp_line_number': fields.integer(string='Line Number'),
        'imp_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'imp_product_desc': fields.char(size=256, string='Description', readonly=True),
        'imp_qty': fields.float(digits=(16, 2), string='Quantity', readonly=True),
        'imp_cost_price': fields.float(digits=(16, 2), string='Cost Price', readonly=True),
        'imp_uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_currency_id': fields.many2one('res.currency', string='Currency', readonly=True),
        'imp_comment': fields.char(size=256, string='Comment', readonly=True),
        'imp_dost': fields.date(string='Date of Stock Take', readonly=True),
        'error_msg': fields.text(string='Error message', readonly=True),
    }

    defaults = {
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


internal_request_line_import()
