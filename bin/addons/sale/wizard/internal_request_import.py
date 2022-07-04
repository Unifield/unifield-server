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
from lxml import etree
import threading
import pooler
import base64
import time
import datetime
import logging
import tools

from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from tools.translate import _
from tools.misc import escape_html

NB_OF_HEADER_LINES = 11
NB_LINES_COLUMNS = 9
LINES_COLUMNS = [
    (0, _('Line number'), 'optionnal'),
    (1, _('Product Code'), 'optionnal'),
    (2, _('Product Description'), 'optionnal'),
    (3, _('Quantity'), 'mandatory'),
    (4, _('Unit Price'), 'optionnal'),
    (5, _('UoM'), 'mandatory'),
    (6, _('Currency'), 'optionnal'),
    (7, _('Comment'), 'optionnal'),
    (8, _('Date of Stock Take'), 'optionnal'),
]


class internal_request_import(osv.osv):
    _name = 'internal.request.import'
    _rec_name = 'order_id'

    def _check_header_error_lines(self, cr, uid, ids, field_names=None, arg=None, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}

        for imp in self.browse(cr, uid, ids, fields_to_fetch=['error_line_ids'], context=context):
            for line in imp.error_line_ids:
                if line.header_line:
                    res[imp.id] = True

        return res

    def _check_error_lines(self, cr, uid, ids, field_names=None, arg=None, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}

        for imp in self.browse(cr, uid, ids, fields_to_fetch=['error_line_ids'], context=context):
            nb_header = 0
            for line in imp.error_line_ids:
                if line.header_line:
                    nb_header += 1
            if len(imp.error_line_ids) > nb_header:
                res[imp.id] = True

        return res

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
        'message': fields.text(string='Import general message for html display', readonly=True),
        'nb_file_lines': fields.integer(string='Total of file lines', readonly=True),
        'nb_treated_lines': fields.integer(string='Nb treated lines', readonly=True),
        'percent_completed': fields.float(string='Percent completed', readonly=True),
        'import_error_ok': fields.boolean(string='Error at import'),
        'no_prod_as_comment': fields.boolean(string='Change Product to a Comment if Product is not found'),
        'date_done': fields.datetime(string='Date of finished import', readonly=True),
        'error_line_ids': fields.one2many('internal.request.import.error.line', 'ir_import_id', string='Error lines', readonly=True),
        'has_header_error': fields.function(_check_header_error_lines, method=True, store=False, string="Has a header error", type="boolean", readonly=True),
        'has_line_error': fields.function(_check_error_lines, method=True, store=False, string="Has a line error", type="boolean", readonly=True),
        # IR Header Info
        # # Original IR info
        'order_id': fields.many2one('sale.order', string='Internal Request', readonly=True),
        'in_ref': fields.char(string='Order Reference', size=64, readonly=True),
        'in_categ': fields.char(string='Order Category', size=64, readonly=True),
        'in_priority': fields.char(string='Priority', size=64, readonly=True),
        'in_creation_date': fields.char(string='Creation date', size=64, readonly=True),
        'in_requested_date': fields.char(string='Requested date', size=64, readonly=True),
        'in_requestor': fields.char(string='Requestor', size=64, readonly=True),
        'in_loc_requestor': fields.char(string='Location Requestor', size=64, readonly=True),
        'in_origin': fields.char(string='Origin', size=64, readonly=True),
        'in_currency': fields.char(string='Currency', size=64, readonly=True),
        # # Imported IR info
        'imp_categ': fields.selection(ORDER_CATEGORY, string='Order Category', readonly=True),
        'imp_priority': fields.selection(ORDER_PRIORITY, string='Priority', readonly=True),
        'imp_creation_date': fields.date(string='Creation Date', readonly=True),
        'imp_requested_date': fields.date(string='Requested Date', readonly=True),
        'imp_requestor': fields.char(size=128, string='Requestor', readonly=True),
        'imp_loc_requestor': fields.many2one('stock.location', string='Location Requestor', readonly=True),
        'imp_origin': fields.char(size=64, string='Origin', readonly=True),
        'imp_line_ids': fields.one2many('internal.request.import.line', 'ir_import_id', string='Lines', readonly=True),
    }

    _defaults = {
        'state': lambda *args: 'draft',
        'nb_treated_lines': 0,
        'has_header_error': False,
        'has_line_error': False,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Returns views to display errors
        """
        res = super(internal_request_import, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        if context.get('ir_import_id'):
            fields = ['state', 'message', 'error_line_ids', 'has_header_error']
            ir_import = self.browse(cr, uid, context['ir_import_id'], fields_to_fetch=fields, context=context)
            if ir_import.state in ['error', 'simu_done']:
                info_msg = '''
<html>
    <p>%s</p>
                ''' % (ir_import.message,)
                if ir_import.error_line_ids:
                    header_err_data = ''
                    line_err_data = ''
                    for line in ir_import.error_line_ids:
                        if line.header_line:
                            header_err_data += '<p>%s</p>' % (line.line_message,)
                        else:
                            if line.red:
                                line_n = _('Line %s') % (line.line_number,)
                                line_err_data += '''
    <span style="color: red">
    <p><u>%s</u></p>
    <p>%s</p>
    <p>%s</p>
    </span>
                                ''' % (line_n, escape_html(line.line_message), escape_html(line.data_summary))
                            else:
                                line_n = _('Line %s') % (line.line_number,)
                                line_err_data += '''
    <p><u>%s</u></p>
    <p>%s</p>
    <p>%s</p>
                                ''' % (line_n, escape_html(line.line_message), escape_html(line.data_summary))
                    if header_err_data:
                        info_msg += '''
    <br/>
    <p><b>%s</b></p>
    %s
                        ''' % (_('Header messages:'), header_err_data)
                    if line_err_data:
                        info_msg += '''
    <br/>
    <p><b>%s</b></p>
    %s
                        ''' % (_('Line messages:'), line_err_data)
                info_msg += '''
</html>'''

                # modify the group size
                # load the xml tree
                root = etree.fromstring(res['arch'])
                # xpath of fields to be modified
                list_xpath = ['//group[@colspan="4" and @col="2"]']
                group_field = False
                for xpath in list_xpath:
                    fields = root.xpath(xpath)
                    if not fields:
                        raise osv.except_osv(_('Warning !'), _('Element %s not found.') % xpath)
                    for field in fields:
                        group_field = field
                new_field = etree.fromstring(info_msg)
                group_field.insert(0, new_field)
                res['arch'] = etree.tostring(root, encoding='unicode')

        return res

    # Unused yet
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
        '''
        Send back to IR form view if there's an IR. To the tree view if there's not
        '''
        if context is None:
            context = {}

        ctx = context.copy()
        ctx.update({'procurement_request': True, 'ir_import_id': False})
        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            if wiz['order_id']:
                res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'procurement_request.action_procurement_request', ['form', 'tree'], context=ctx)
                res['res_id'] = wiz['order_id'][0]
                return res

            return self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'procurement_request.action_procurement_request', ['tree', 'form'], context=ctx)

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Display the simulation screen
        '''
        if isinstance(ids, int):
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
        if isinstance(ids, int):
            ids = [ids]

        for ir_imp in self.browse(cr, uid, ids, context=context):
            if not ir_imp.file_to_import:
                raise osv.except_osv(_('Error'), _('No file to import'))
            xml_file = base64.b64decode(ir_imp.file_to_import)
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
        xml_file = base64.b64decode(file_to_import)
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
        ir_obj = self.pool.get('sale.order').fields_get(cr, uid, ['priority', 'categ'], context=context)
        ORDER_PRIORITY_BY_VALUE = dict([(y, x) for x, y in ir_obj.get('priority', {}).get('selection', [])])
        ORDER_CATEGORY_BY_VALUE = dict([(y, x) for x, y in ir_obj.get('categ', {}).get('selection', [])])

        try:
            ir_imp_l_obj = self.pool.get('internal.request.import.line')
            err_line_obj = self.pool.get('internal.request.import.error.line')
            so_obj = self.pool.get('sale.order')
            prod_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            loc_obj = self.pool.get('stock.location')

            if context is None:
                context = {}

            if isinstance(ids, int):
                ids = [ids]

            max_value = self.pool.get('sale.order.line')._max_value
            start_time = time.time()
            for ir_imp in self.browse(cr, uid, ids, context=context):
                # Delete old error lines
                err_line_ids = err_line_obj.search(cr, uid, [('ir_import_id', '=', ir_imp.id)], context=context)
                err_line_obj.unlink(cr, uid, err_line_ids, context=context)

                nb_treated_lines = 0
                nb_treated_lines_by_nomen = 0
                nb_error_lines = 0
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
                l_date_format = ['%d-%m-%Y', '%d.%m.%Y']
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

                for x in range(2, nb_file_header_lines+1):
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

                for x in range(first_line_index, len(values)+1):
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

                    self.write(cr, uid, [ir_imp.id], {'message': message, 'state': 'error', 'file_to_import': False}, context)
                    res = self.go_to_simulation(cr, uid, [ir_imp.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res

                '''
                Now, we know that the file has the good format, you can import data for header.
                '''
                # Retreived data for overview export
                header_values.update({
                    'in_ref': values.get(2, [])[1],
                    'in_categ': values.get(4, [])[1],
                    'in_priority': values.get(5, [])[1],
                    'in_creation_date': values.get(6, [])[1],
                    'in_requested_date': values.get(7, [])[1],
                    'in_requestor': values.get(8, [])[1],
                    'in_loc_requestor': values.get(9, [])[1],
                    'in_origin': values.get(10, [])[1],
                    'in_currency': values.get(11, [])[1],
                })
                # Line 2: Order Reference
                if context.get('to_update_ir', False):
                    if ir_order:
                        if not values.get(2, [])[1] or ir_order.name != values.get(2, [])[1]:
                            blocked = True
                            msg_val = _('Order Reference: IR Order Reference \'%s\' is not correct.') % \
                                (values.get(2, [])[1],)
                            values_header_errors.append(msg_val)
                            err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True, 'line_message': msg_val},
                                                context=context)
                    elif not ir_order and values.get(2, [])[1]:  # Search for existing IR
                        ir_ids = so_obj.search(cr, uid, [('procurement_request', '=', True),
                                                         ('name', '=', values.get(2, [])[1])], limit=1, context=context)
                        if ir_ids:
                            ir_order = so_obj.browse(cr, uid, ir_ids[0], context=context)
                            for ir_line in ir_order.order_line:
                                imp_line_data = {
                                    'ir_import_id': ir_imp.id,
                                    'ir_line_id': ir_line.id,
                                    'ir_line_number': ir_line.line_number
                                }
                                ir_imp_l_obj.create(cr, uid, imp_line_data, context=context)
                        else:
                            blocked = True
                            msg_val = _('Order Reference: You can not import this file with a non-existing IR Order Reference.')
                            values_header_errors.append(msg_val)
                            err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True, 'line_message': msg_val},
                                                context=context)

                # Line 4: Order Category
                categ = values.get(4, [])[1] or ' '
                if categ in ORDER_CATEGORY_BY_VALUE:
                    header_values['imp_categ'] = ORDER_CATEGORY_BY_VALUE[categ]
                elif not ir_order:
                    msg_val = _('Order Category: Order Category \'%s\' not defined, default value will be \'Other\'') \
                        % (categ or False,)
                    values_header_errors.append(msg_val)
                    err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True, 'line_message': msg_val},
                                        context=context)
                    header_values['imp_categ'] = 'other'

                # Line 5: Priority
                priority = values.get(5, [])[1] or ' '
                if priority in ORDER_PRIORITY_BY_VALUE:
                    header_values['imp_priority'] = ORDER_PRIORITY_BY_VALUE[priority]
                elif not ir_order:
                    msg_val = _('Order Priority: Order Priority \'%s\' not defined, default value will be \'Normal\'')\
                        % (priority or False,)
                    values_header_errors.append(msg_val)
                    err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True, 'line_message': msg_val},
                                        context=context)
                    header_values['imp_priority'] = 'normal'

                # Line 6: Creation date
                create_date = values.get(6, [])[1]
                if isinstance(create_date, datetime.datetime):
                    create_date = create_date.strftime('%Y-%m-%d')
                    header_values['imp_creation_date'] = create_date
                else:
                    for format in l_date_format:
                        try:
                            create_date = datetime.datetime.strptime(create_date, format)
                            header_values['imp_creation_date'] = create_date.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                    if not header_values.get('imp_creation_date'):
                        msg_val = _('Creation Date: The Creation Date \'%s\' is empty or incorrect, current date will be used.') \
                            % (create_date,)
                        values_header_errors.append(msg_val)
                        err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True,
                                                      'line_message': msg_val}, context=context)
                        header_values['imp_creation_date'] = time.strftime('%Y-%m-%d')

                # Line 7: Requested date
                req_date = values.get(7, [])[1]
                if isinstance(req_date, datetime.datetime):
                    req_date = req_date.strftime('%Y-%m-%d')
                    header_values['imp_requested_date'] = req_date
                else:
                    for format in l_date_format:
                        try:
                            req_date = datetime.datetime.strptime(req_date, format)
                            header_values['imp_requested_date'] = req_date.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                    if not header_values.get('imp_requested_date'):
                        msg_val = _('Requested Date: The Requested Date \'%s\' is incorrect, you will need to correct this manually.') \
                            % req_date
                        values_header_errors.append(msg_val)
                        err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True,
                                                      'line_message': msg_val}, context=context)

                # Line 8: Requestor
                if values.get(8, [])[1]:
                    header_values['imp_requestor'] = values.get(8, [])[1]

                # Line 9: Location Requestor
                loc_req = values.get(9, [])[1]
                ir_loc_req_domain = [
                    ('name', '=ilike', loc_req), '&',
                    ('location_category', '!=', 'transition'), '|', ('usage', '=', 'internal'), '&',
                    ('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')
                ]
                loc_ids = loc_obj.search(cr, uid, ir_loc_req_domain, limit=1, context=context)
                if loc_ids:
                    header_values['imp_loc_requestor'] = loc_ids[0]
                else:
                    msg_val = _('Location Requestor: The Location Requestor \'%s\' does not match possible options, you will need to correct this manually.')\
                        % (loc_req,)
                    values_header_errors.append(msg_val)
                    err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'header_line': True, 'line_message': msg_val},
                                        context=context)

                # Line 10: Origin
                if values.get(10, [])[1]:
                    header_values['imp_origin'] = values.get(10, [])[1]

                '''
                The header values have been imported, start the importation of
                lines
                '''
                ir_line_numbers = []  # existing line numbers
                imp_line_numbers = []  # imported line numbers
                ignored = []
                if ir_order:  # get the lines numbers
                    ir_line_numbers = [line.line_number for line in ir_order.order_line]

                # Loop on lines
                for x in range(first_line_index+1, len(values)+1):
                    red = False
                    line_errors = ''
                    ignored_line = False
                    # Check mandatory fields
                    for manda_field in LINES_COLUMNS:
                        if manda_field[2] == 'mandatory' and not values.get(x, [])[manda_field[0]]:
                            required_field = True
                            if len(manda_field) > 3 and isinstance(manda_field[3], (tuple, list )) and \
                                    len(manda_field[3]) == 3:
                                col, op, val = manda_field[3]
                                if op == '!=':
                                    required_field = ir_imp[col] != val
                                else:
                                    required_field = ir_imp[col] == val
                            if required_field:
                                red = True
                                line_errors += _('The column \'%s\' mustn\'t be empty%s. ') \
                                    % (manda_field[1], manda_field[0] == 0 or '')

                    # Get values
                    vals = values.get(x, [])
                    line_data = {
                        'in_line_number': vals[0],
                        'in_product': vals[1],
                        'in_product_desc': vals[2],
                        'in_qty': vals[3],
                        'in_cost_price': vals[4],
                        'in_uom': vals[5],
                        'in_comment': vals[7],
                        'in_stock_take_date': vals[8],
                    }

                    duplicate_line = False
                    product_id = False
                    product = False
                    line_recap = ''
                    for val in vals:
                        line_recap += tools.ustr(val or '') + '/'
                    # Line number
                    if ir_order and vals[0]:
                        if vals[0] in ir_line_numbers:
                            try:
                                line_n = int(vals[0])
                                line_data.update({'imp_line_number': line_n})
                                if line_n in imp_line_numbers:
                                    red = True
                                    line_errors += _('Line Number \'%s\' has already been treated. ') % (line_n,)
                                    duplicate_line = True
                                else:
                                    imp_line_numbers.append(line_n)
                            except:
                                red = True
                                line_errors += _('Line Number must be an integer. ')
                        else:
                            red = True
                            line_errors += _('Line Number must be empty to add a new line to an existing IR. ')

                    # Product and Comment
                    product_code = vals[1]
                    comment = vals[7]
                    if product_code:
                        product_code = tools.ustr(product_code)
                        prod_ids = prod_obj.search(cr, uid, [('default_code', '=', product_code)], limit=1, context=context)
                        if prod_ids:
                            product_id = prod_ids[0]
                            prod_cols = ['standard_price', 'uom_id', 'uom_po_id']
                            p_error, p_msg = prod_obj._test_restriction_error(cr, uid, [product_id],
                                                                              vals={'constraints': 'consumption'},
                                                                              context=context)
                            if p_error:  # Check constraints on products
                                red = True
                                line_errors += p_msg + '. '
                            else:
                                product = prod_obj.read(cr, uid, product_id, prod_cols, context=context)
                                line_data.update({
                                    'imp_product_id': product_id,
                                    'imp_comment': comment or '',
                                })
                        else:
                            if ir_imp.no_prod_as_comment:
                                nb_treated_lines_by_nomen += 1
                                desc = vals[2] and '/' + tools.ustr(vals[2]) or ''
                                if comment:
                                    line_data.update({'imp_comment': product_code + desc + '/' + tools.ustr(comment)})
                                else:
                                    line_data.update({'imp_comment': product_code + desc})
                                line_errors += _('Product \'%s\' not recognized, line by nomenclature created. ') % vals[1]
                            else:
                                red = True
                                line_data.update({'imp_comment': comment or ''})
                                line_errors += _('Product \'%s\' does not exist in this database. ') % vals[1]
                    else:
                        line_data.update({'imp_comment': comment or ''})
                        if not comment:
                            red = True
                            line_errors += _('Product Code is mandatory. ')

                    # Quantity
                    qty = vals[3] or 0.00
                    try:
                        qty = float(qty)
                        if qty > 0:
                            if qty < max_value:
                                line_data.update({'imp_qty': qty})
                            else:
                                red = True
                                line_errors += _('Quantity can not have more than 10 digits. ')
                        else:
                            red = True
                            line_errors += _('Quantity \'%s\' must be above 0. ') % (qty,)
                    except:
                        red = True
                        line_errors += _('Quantity must be a number. ')

                    # Cost Price and UoM
                    uom_ids = uom_obj.search(cr, uid, [('name', '=', vals[5])], limit=1, context=context)
                    if product_id and product:
                        cost_price = vals[4]
                        try:
                            cost_price = float(cost_price)
                            if cost_price > 0:
                                line_data.update({'imp_cost_price': cost_price})
                            else:
                                line_data.update({'imp_cost_price': product['standard_price']})
                                line_errors += _('Price \'%s\' must be above 0, default cost price has been used. ') \
                                    % (cost_price,)
                        except:
                            line_data.update({'imp_cost_price': product['standard_price']})
                            line_errors += _('Price \'%s\' is not a correct value, default cost price has been used. ') \
                                % (cost_price,)
                        if uom_ids and uom_ids[0] in [product['uom_id'][0], product['uom_po_id'][0]]:
                            line_data.update({'imp_uom_id': uom_ids[0]})
                        else:
                            red = True
                            line_errors += _('UoM \'%s\' is not consistent with the Product \'%s\'. ') \
                                % (vals[5], vals[1])
                    else:
                        cost_price = vals[4] or 0.00
                        try:
                            cost_price = float(cost_price)
                            if cost_price > 0:
                                line_data.update({'imp_cost_price': cost_price})
                            else:
                                red = True
                                line_errors += _('Price \'%s\' must be above 0. ') % (cost_price,)
                        except:
                            red = True
                            line_errors += _('Unit Price must be a number. ')
                        if uom_ids:
                            line_data.update({'imp_uom_id': uom_ids[0]})
                        else:
                            red = True
                            line_errors += _('UoM \'%s\' does not exist in this database. ') % (vals[5],)

                    # Check the total amount
                    if qty and cost_price and len(str(int(qty * cost_price))) > 25:
                        red = True
                        line_errors += _('The Total amount is more than 28 digits. Please check that the Qty and Unit price are correct, the current values are not allowed. ')

                    # Date of Stock Take
                    if vals[8]:
                        dost = vals[8]
                        if isinstance(dost, datetime.datetime):
                            dost = dost.strftime('%Y-%m-%d')
                            line_data.update({'imp_stock_take_date': dost})
                        else:
                            for format in l_date_format:
                                try:
                                    dost = datetime.datetime.strptime(dost, format)
                                    line_data.update({'imp_stock_take_date': dost.strftime('%Y-%m-%d')})
                                    break
                                except:
                                    continue
                            if not line_data.get('imp_stock_take_date'):
                                line_errors += _('Date of Stock Take \'%s\' is not a correct value, line has been imported without Date of Stock Take. ') \
                                    % vals[8]
                        if line_data.get('imp_stock_take_date') and line_data['imp_stock_take_date'] > ir_order.date_order:
                            red = True
                            line_errors += _('The Date of Stock Take is not consistent! It should not be later than %s\'s creation date. ') \
                                % (ir_order.name)

                    line_data.update({
                        'error_msg': line_errors,
                        'ir_import_id': ir_imp.id,
                    })

                    ir_imp_l_ids_to_write = []  # Fetch the ids of lines to modify if any
                    if not duplicate_line and ir_line_numbers and line_data.get('imp_line_number') \
                            and line_data['imp_line_number'] in ir_line_numbers:
                        l_ids = ir_imp_l_obj.search(cr, uid, [('ir_import_id', '=', ir_imp.id),
                                                              ('ir_line_number', '=', line_data['imp_line_number'])],
                                                    context=context)
                        for ir_imp_l in ir_imp_l_obj.browse(cr, uid, l_ids, fields_to_fetch=['ir_line_id'], context=context):
                            if ir_imp_l.ir_line_id.state != 'draft':
                                ignored_line = True
                                ignored.append(str(line_data['imp_line_number']))
                            else:
                                ir_imp_l_ids_to_write.append(ir_imp_l.id)

                    if len(line_errors) and not ignored_line:  # Add the errors if the line is not cancelled
                        if red:
                            line_errors = _('%sLine not imported.') % (line_errors,)
                            line_data.update({'red': red})
                            nb_error_lines += 1
                        values_line_errors.append(line_errors)
                        err_line_obj.create(cr, uid, {'ir_import_id': ir_imp.id, 'red': red, 'line_message': line_errors,
                                                      'line_number': x - first_line_index, 'data_summary': line_recap},
                                            context=context)

                    if not duplicate_line and ir_line_numbers and line_data.get('imp_line_number') \
                            and line_data['imp_line_number'] in ir_line_numbers:
                        if ir_imp_l_ids_to_write and not ignored_line:  # No modification on ignored lines
                            ir_imp_l_obj.write(cr, uid, ir_imp_l_ids_to_write, line_data, context=context)
                    else:
                        ir_imp_l_obj.create(cr, uid, line_data, context=context)

                    nb_treated_lines += 1

                import_error_ok = False
                if len(values_header_errors) or len(values_line_errors):
                    import_error_ok = True

                nb_imp_lines = nb_treated_lines - nb_error_lines
                if blocked:
                    nb_imp_lines = 0
                    nb_error_lines = nb_treated_lines
                    nb_treated_lines_by_nomen = 0
                else:
                    nb_imp_lines -= len(ignored)

                message = _('''
<p>Importation completed in %s second(s)!</p>
<p># of lines in the file : %s</p>
<p># of lines imported : %s</p>
<p># of lines not imported : %s</p>
<p># of lines imported as line by nomenclature : %s</p>
                ''') % (str(round(time.time() - start_time, 1)), nb_treated_lines, nb_imp_lines,
                        nb_error_lines, nb_treated_lines_by_nomen)
                if ignored:
                    message += _('''
<p>Non-Draft lines ignored: Number %s</p>
                    ''') % (', '.join(ignored),)

                header_values.update({
                    'order_id': ir_order and ir_order.id,
                    'message': message,
                    'state': blocked and 'error' or 'simu_done',
                    'percent_completed': 100.0,
                    'import_error_ok': import_error_ok,
                    'nb_treated_lines': nb_treated_lines,
                    'file_to_import': False,
                })
                self.write(cr, uid, [ir_imp.id], header_values, context=context)

            cr.commit()
            cr.close(True)

        except Exception as e:
            logging.getLogger('internal.request.import').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e, 'file_to_import': False}, context=context)
            cr.commit()
            cr.close(True)

        return True

    def launch_import(self, cr, uid, ids, context=None):
        '''
        Launch the simulation routine in background
        '''
        if isinstance(ids, int):
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

        if new_thread.is_alive():
            return self.go_to_simulation(cr, uid, ids, context=context)
        return self.go_to_ir(cr, uid, ids, context=context)

    def run_import(self, dbname, uid, ids, context=None):
        '''
        Launch the real import
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        cr = pooler.get_db(dbname).cursor()
        so_obj = self.pool.get('sale.order')
        sol_obj = self.pool.get('sale.order.line')

        try:
            for wiz in self.browse(cr, uid, ids, context=context):
                self.write(cr, uid, [wiz.id], {'state': 'import_progress'}, context=context)
                if wiz.order_id:  # update IR
                    ir_vals = {
                        'requestor': wiz.imp_requestor
                    }
                    if wiz.imp_creation_date:
                        ir_vals.update({'date_order': wiz.imp_creation_date})
                    if wiz.imp_requested_date:
                        ir_vals.update({'delivery_requested_date': wiz.imp_requested_date})
                    else:
                        ir_vals.update({'delivery_requested_date': False})
                    if wiz.imp_loc_requestor:
                        ir_vals.update({'location_requestor_id': wiz.imp_loc_requestor.id})
                    if wiz.imp_categ:
                        ir_vals.update({'categ': wiz.imp_categ})
                    if wiz.imp_priority:
                        ir_vals.update({'priority': wiz.imp_priority})
                    so_obj.write(cr, uid, wiz.order_id.id, ir_vals, context=context)
                    for line in wiz.imp_line_ids:
                        if not line.red and line.imp_qty > 0:
                            line_vals = {
                                'product_id': line.imp_product_id and line.imp_product_id.id or False,
                                'product_uom_qty': line.imp_qty or 0.00,
                                'comment': line.imp_comment or '',
                                'procurement_request': True,
                                'stock_take_date': line.imp_stock_take_date or False,
                                'cost_price': line.imp_cost_price or 0.00,
                                'price_unit': line.imp_cost_price or 0.00,
                            }
                            if line.imp_uom_id:
                                line_vals.update({'product_uom': line.imp_uom_id.id})
                            if line.ir_line_id:  # update IR line
                                if line.ir_line_id.state == 'draft':
                                    sol_obj.write(cr, uid, line.ir_line_id.id, line_vals, context=context)
                            else:  # create IR line
                                line_vals.update({
                                    'order_id': wiz.order_id.id,
                                })
                                sol_obj.create(cr, uid, line_vals, context=context)
                else:  # Create IR
                    ir_vals = {
                        'procurement_request': True,
                        'categ': wiz.imp_categ,
                        'priority': wiz.imp_priority,
                        'date_order': wiz.imp_creation_date,
                        'delivery_requested_date': wiz.imp_requested_date or False,
                        'requestor': wiz.imp_requestor,
                        'location_requestor_id': wiz.imp_loc_requestor and wiz.imp_loc_requestor.id or False,
                        'origin': wiz.imp_origin,
                        'order_line': [(0, 0, {
                            'product_id': x.imp_product_id and x.imp_product_id.id or False,
                            'product_uom_qty': x.imp_qty or 0.00,
                            'cost_price': x.imp_cost_price or 0.00,
                            'price_unit': x.imp_cost_price or 0.00,
                            'product_uom': x.imp_uom_id and x.imp_uom_id.id or False,
                            'procurement_request': True,
                            'comment': x.imp_comment or '',
                            'stock_take_date': x.imp_stock_take_date or False,
                        }) for x in (y for y in wiz.imp_line_ids if not y.red)],
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
        except Exception as e:
            logging.getLogger('ir.simulation.run').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e}, context=context)
            res = True
            cr.commit()
            cr.close(True)

        return res

    def export_ir_import_overview(self, cr, uid, ids, context=None):
        '''
        Call the Excel report of IR Import Overview
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        data = {'ids': ids}
        dt_now = datetime.datetime.now()
        ir_imp_order = False
        if ids:
            ir_imp_order = self.browse(cr, uid, ids[0], fields_to_fetch=['order_id'], context=context).order_id
        if ir_imp_order:
            filename = "%s_%s_%d_%02d_%02d" % (ir_imp_order.name.replace('/', '_'), _('Import_Overview'),
                                               dt_now.year, dt_now.month, dt_now.day)
        else:
            filename = "%s_%d_%02d_%02d" % (_('IR_Import_Overview'), dt_now.year, dt_now.month, dt_now.day)
        data['target_filename'] = filename

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'internal_request_import_overview_export',
            'datas': data,
            'context': context,
        }


internal_request_import()


class internal_request_import_line(osv.osv):
    _name = 'internal.request.import.line'
    _rec_name = 'ir_line_number'

    _columns = {
        'ir_line_id': fields.many2one('sale.order.line', string='Line', readonly=True),
        'ir_import_id': fields.many2one('internal.request.import', string='Simulation screen', readonly=True, ondelete='cascade'),
        'ir_line_number': fields.integer(string='Line Number'),
        'red': fields.boolean(string='Is the line error blocking ?'),
        # # File IR line info
        'in_line_number': fields.char(string='Line Number', size=32, readonly=True),
        'in_product': fields.char(string='Product', size=64, readonly=True),
        'in_product_desc': fields.char(string='Product Description', size=128, readonly=True),
        'in_qty': fields.char(string='Quantity', size=64, readonly=True),
        'in_cost_price': fields.char(string='Unit Price', size=64, readonly=True),
        'in_uom': fields.char(string='UoM', size=64, readonly=True),
        'in_comment': fields.char(string='Comment', size=256, readonly=True),
        'in_stock_take_date': fields.char(string='Date of Stock Take', size=64, readonly=True),
        # # Imported IR line info
        'imp_line_number': fields.integer(string='Line Number'),
        'imp_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'imp_qty': fields.float(digits=(16, 2), string='Quantity', readonly=True),
        'imp_cost_price': fields.float(digits=(16, 2), string='Unit Price', readonly=True),
        'imp_uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_comment': fields.char(size=256, string='Comment', readonly=True),
        'imp_stock_take_date': fields.date(string='Date of Stock Take', readonly=True),
        'error_msg': fields.text(string='Error message', readonly=True),
    }

    defaults = {
        'ir_line_number': 0,
    }

    def get_error_msg(self, cr, uid, ids, context=None):
        '''
        Display the error message
        '''
        if isinstance(ids, int):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.error_msg:
                raise osv.except_osv(_('Warning'), line.error_msg)

        return True


internal_request_import_line()


class internal_request_import_error_line(osv.osv):
    _name = 'internal.request.import.error.line'
    _rec_name = 'line_number'

    _columns = {
        'ir_import_id': fields.many2one('internal.request.import', string='IR Import reference', readonly=True),
        'line_number': fields.integer(string='Line number', readonly=True),
        'line_message': fields.char(string='Error message', size=1024, required=True, readonly=True),
        'data_summary': fields.char(string='Line\'s data summary', size=256, readonly=True),
        'header_line': fields.boolean(string='Is line header', readonly=True),
        'red': fields.boolean(string='Line has to be red', readonly=True),
    }

    defaults = {
        'line_number': False,
        'header_line': False,
        'red': False,
    }


internal_request_import_error_line()
