# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
"""
Rules regarding the PO import for the vertical integration

Rule 0:
If the line number of the line of a file does not exist in the line of the PO:
we ignore it and write it in the file with the lines not imported.

Rule 1:
If a cell is empty:
we keep the eventually existing field value of the object (PO or PO line) and we do not erase the value of the field.

Rule 2:
If a cell is not empty and satisfy the standard checks (product exist...)
The values are taken as they are and no update mechanism is triggered afterwards (i.e. the price unit mechanism).

Rule 3:
if the number of PO lines with the same line number is equal to the number of lines with the same line number in the file,
We update all the lines with this line number.

Rule 4:
if the number of PO lines with the same line number is lower than the number of lines with the same line number in the file, and if the number of PO lines is equal to 1:
We split the only line with this line number.
Else, we search in the file if there are lines with the same product as a line of the PO:
in that case, we update the PO line.
Else (if the number of PO lines is greater than 1 and we don't find a link with the product):
We ignore the file lines with this line number because we can't know which PO lines to upate or not.

Rule 5:
if the number of PO lines with the same line number is greater than the number of lines with the same line number in the file, if the product is the same:
we update the corresponding line
Else:
we ignore the file lines with this line number because we can't know which lines to upate or not.

Rule 6:
the user can't update the PO in the same time that an import is processing. For preventing him from updating the PO, we set it to "Closed" (it implies that all fields are readonly, but temporary, just in the time of the import) and we reset it to "Validated" at the end of the import.
"""

import threading
import pooler
from osv import osv, fields
from tools.translate import _
import base64
import decimal_precision as dp
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import time
from msf_doc_import.wizard import PO_COLUMNS_FOR_INTEGRATION as columns_for_po_integration
from msf_order_date import TRANSPORT_TYPE


class purchase_line_import_xml_line(osv.osv_memory):
    """
    This class is usefull only for the import:
    - it helps using search function to find matching lines (between PO lines and file lines)
    - it helps updating or spliting the lines because we can directly use the fields in vals
    with a read.
    """
    _name = 'purchase.line.import.xml.line'


    _columns = {
        'order_id': fields.many2one('purchase.order', string='Purchase Order'),
        'line_ignored_ok': fields.boolean('Ignored?'),
        'file_line_number': fields.integer(string='File line numbers'),
        'line_number': fields.integer(string='Line number'),
        'product_id': fields.many2one('product.product', string='Product'),
        'product_uom': fields.many2one('product.uom', string='UoM'),
        'product_qty': fields.float(digits=(16,2), string='Quantity', related_uom='product_uom'),
        'price_unit': fields.float(digits=(16,2), string='Price'),
        'price_unit_defined': fields.boolean('Price Unit Defined?'),
        'confirmed_delivery_date': fields.date('Confirmed Delivery Date'),
        'origin': fields.char(size=512, string='Origin'),
        'notes': fields.text('Notes'),
        'comment': fields.text('Comment'),
        'to_correct_ok': fields.boolean('To correct?'),
        'error_list': fields.text('Error'),
        'text_error': fields.text('Text Error'),
        'show_msg_ok': fields.boolean('To show?'),
    }
    _defaults = {
        'line_ignored_ok': False,
    }

purchase_line_import_xml_line()


class purchase_import_xml_line(osv.osv_memory):
    """
    This class is usefull only for the import:
    - it helps using search function to find matching lines (between PO lines and file lines)
    - it helps updating or spliting the lines because we can directly use the fields in vals
    with a read.
    """
    _name = 'purchase.import.xml.line'


    _columns = {
        'file_line_number': fields.integer(string='File line numbers'),
        'error_list': fields.text('Error'),
        'line_ignored_ok': fields.boolean('Ignored?'),
        'delivery_confirmed_date': fields.date('Confirmed Delivery Date'),
        'partner_ref': fields.char('Supplier Reference', size=64),
        'est_transport_lead_time': fields.float(digits=(16,2), string='Est. Transport Lead Time'),
        'transport_type': fields.selection(selection=TRANSPORT_TYPE, string='Transport Mode'),
        'dest_partner_id': fields.many2one('res.partner', string='Destination partner', domain=[('partner_type', '=', 'internal')]),
        'dest_address_id':fields.many2one('res.partner.address', 'Destination Address'),
        'invoice_address_id': fields.many2one('res.partner.address', string='Invoicing address'),
        'arrival_date': fields.date(string='Arrival date in the country'),
        'incoterm_id': fields.many2one('stock.incoterms', string='Incoterm'),
        'notes': fields.text('Notes'),
        'to_correct_ok': fields.boolean('To correct?'),
    }
    _defaults = {
        'line_ignored_ok': False,
    }

purchase_import_xml_line()


class wizard_import_po(osv.osv_memory):
    """
    This class helps importing the PO for the vertical integration.
    """
    _name = 'wizard.import.po'
    _description = 'Import PO from Excel sheet'

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
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'po_id': fields.many2one('purchase.order', string='Purchase Order', required=True),
        'data': fields.binary('Lines with errors'),
        'filename_template': fields.char('Templates', size=256),
        'filename': fields.char('Lines with errors', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
        'line_ids': fields.one2many('wizard.simu.import.po.line', 'import_id', string='Purchase Order Lines'),
    }

    _defaults = {
        'message': lambda *a : _("""
        IMPORTANT : The first line will be ignored by the system because it only contains the header values.
        The file should be in XML 2003 format.

The Purchase Order will be updated with the first data line only (the one after the header values).

The columns should be in this values:
%s
""") % (', \n'.join(columns_for_po_integration), ),
        'state': lambda *a: 'draft',
    }

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        lines_not_imported = []
        header_index = kwargs.get('header_index')
        data = header_index.items()
        columns_header = []
        for k,v in sorted(data, key=lambda tup: tup[1]):
            columns_header.append((k, type(k)))
        for line in kwargs.get('line_with_error'):
            if len(line) < len(columns_header):
                lines_not_imported.append(line + ['' for x in range(len(columns_header)-len(line))])
            else:
                lines_not_imported.append(line)
        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml(default_filters=['decode.utf8'])), 'filename': 'Lines_Not_Imported.xls'}
        return vals

    def get_line_values(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        list_of_values = []
        for cell_nb in range(len(row)):
            cell_data = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
            list_of_values.append(cell_data)
        return list_of_values

    def get_header_index(self, cr, uid, ids, row, error_list, line_num, context):
        """
        Return dict with {'header_name0': header_index0, 'header_name1': header_index1...}
        """
        header_dict = {}
        for cell_nb in range(len(row.cells)):
            header_dict.update({row.cells and row.cells[cell_nb] and row.cells[cell_nb].data: cell_nb})
        return header_dict

    def check_header_values(self, cr, uid, ids, context, header_index):
        """
        Check that the columns in the header will be taken into account.
        """
        for k,v in header_index.items():
            if k not in columns_for_po_integration:
                if k == 'Delivery requested date':
                    continue  # 'Delivery requested date' tolerated (for Rfq vs 'Delivery Requested Date' of PO_COLUMNS_HEADER_FOR_IMPORT)
                vals = {'message': _('The column "%s" is not taken into account. Please remove it. The list of columns accepted is: \n %s')
                        % (k, ', \n'.join(columns_for_po_integration))}
                return self.write(cr, uid, ids, vals, context), False
        list_of_required_values = ['Line', 'Product Code']
        for required_value in list_of_required_values:
            if required_value not in header_index.keys():
                vals = {'message': _('The following columns are required for the import (case sensitive): %s.\n Please add the missing one.'
                                     ) % (', '.join(list_of_required_values))}
                return self.write(cr, uid, ids, vals, context), False
        return True, True

    def get_po_header_row_values(self, cr, uid, ids, row, po_browse, header_index, context=None):
        """
        Get the PO values for the first line
        """
        partner_obj = self.pool.get('res.partner')
        partner_address_obj = self.pool.get('res.partner.address')
        incoterm_obj = self.pool.get('stock.incoterms')
        to_write_po = {'error_list': [],}
        # Delivery Confirmed Date (PO)*
        cell_nb = header_index.get('Delivery Confirmed Date (PO)', False)
        delivery_confirmed_date = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if delivery_confirmed_date:
            if row.cells[cell_nb].type in ('date', 'datetime'):
                delivery_confirmed_date = delivery_confirmed_date.strftime('%Y-%m-%d')
                if delivery_confirmed_date != '1899-12-30':
                    to_write_po.update({'delivery_confirmed_date': delivery_confirmed_date})
                else:
                    #http://stackoverflow.com/questions/3963617/why-is-1899-12-30-the-zero-date-in-access-sql-server-instead-of-12-31
                    to_write_po['error_list'].append(_('"Delivery Confirmed Date (PO)" has a wrong format and was reset to "30-12-1899" which is the default Excel date.'))
                    to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})
            else:
                to_write_po['error_list'].append(_('"Delivery Confirmed Date (PO)" %s has a wrong format. Please format the cell in Excel as date.') % (delivery_confirmed_date, ))

        # Supplier Reference
        cell_nb = header_index.get('Supplier Reference', False)
        partner_ref = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if partner_ref:
            to_write_po.update({'partner_ref': partner_ref})

        # Est. Transport Lead Time
        cell_nb = header_index.get('Est. Transport Lead Time', False)
        cell_data = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if cell_data:
            try:
                est_transport_lead_time = float(cell_data)
                to_write_po.update({'est_transport_lead_time': est_transport_lead_time})
            except ValueError, e:
                to_write_po['error_list'].append(_('The Est. Transport Lead Time %s has a wrong value. Details: %s.') % (cell_data, e))
                to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})

        # Transport Mode
        cell_nb = header_index.get('Transport Mode', False)
        transport_type = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if transport_type:
            transport_type_value = [y for (x,y) in TRANSPORT_TYPE]
            transport_type_key = [x for (x,y) in TRANSPORT_TYPE]
            transport_type_reverse = [(y, x) for (x,y) in TRANSPORT_TYPE]
            transport_type_dict_val = dict(transport_type_reverse)
            if transport_type in transport_type_value:
                to_write_po.update({'transport_type': transport_type_dict_val[transport_type]})
            if transport_type in transport_type_key:
                to_write_po.update({'transport_type': transport_type})
            elif transport_type not in transport_type_value and transport_type not in transport_type_key:
                # we set all the error in to_write
                to_write_po['error_list'].append(_('The Transport Mode Value should be in %s.') % transport_type_value)
                to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})

        # Destination Partner and Destination Address go together
        cell_nb = header_index.get('Destination Partner', False)
        dest_partner_name = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if dest_partner_name:
            dest_partner_ids = partner_obj.search(cr, uid, [('name', '=', dest_partner_name)], context=context)
            if dest_partner_ids:
                dest_partner_id = dest_partner_ids[0]
                dest_address_id = self.pool.get('res.partner').address_get(cr, uid, dest_partner_id, ['delivery'])['delivery']
                to_write_po.update({'dest_partner_id': dest_partner_id, 'dest_address_id': dest_address_id})
            else:
                to_write_po['error_list'].append(_('The Destination Partner %s does not exist in the Database.') % dest_partner_name)
                to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})

        # Invoicing Address
        cell_nb = header_index.get('Invoicing Address', False)
        invoice_address_name = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if invoice_address_name:
            invoice_address_ids = partner_address_obj.search(cr, uid, [('name', '=', invoice_address_name)], context=context)
            if invoice_address_ids:
                invoice_address_id = invoice_address_ids[0]
                to_write_po.update({'invoice_address_id': invoice_address_id})
            else:
                to_write_po['error_list'].append(_('The Invoicing Address %s does not exist in the Database.') % invoice_address_name)
                to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})

        # Arrival Date in the country
        cell_nb = header_index.get('Arrival Date in the country', False)
        arrival_date = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if arrival_date:
            if row.cells[cell_nb].type in ('date', 'datetime'):
                arrival_date = arrival_date.strftime('%Y-%m-%d')
                if arrival_date != '1899-12-30':
                    to_write_po.update({'arrival_date': arrival_date})
                else:
                    #http://stackoverflow.com/questions/3963617/why-is-1899-12-30-the-zero-date-in-access-sql-server-instead-of-12-31
                    to_write_po['error_list'].append(_('"Arrival Date in the country" has a wrong format and was reset to "30-12-1899" which is the default Excel date.'))
                    to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})
            else:
                to_write_po['error_list'].append(_('"Arrival Date in the country" %s has a wrong format. Please format the cell in Excel as date.') % (arrival_date,))

        # Incoterm
        cell_nb = header_index.get('Incoterm', False)
        incoterm_name = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if incoterm_name:
            incoterm_ids = incoterm_obj.search(cr, uid, [('name', '=', incoterm_name)], context=context)
            if incoterm_ids:
                incoterm_id = incoterm_ids[0]
                to_write_po.update({'incoterm_id': incoterm_id})
            else:
                to_write_po['error_list'].append(_('The Incoterm %s does not exist in the Database.') % incoterm_name)
                to_write_po.update({'error_list': to_write_po['error_list'], 'to_correct_ok': True})

        # Notes (PO)
        cell_nb = header_index.get('Notes (PO)', False)
        notes_po = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        to_write_po.update({'notes': notes_po})

        return to_write_po

    def get_po_row_values(self, cr, uid, ids, row, po_browse, header_index, context=None):
        """
        Get PO lines values
        """
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        purchase_obj = self.pool.get('purchase.order')
        to_write = {
            'error_list': [],
            'to_correct_ok': False,
            'show_msg_ok': False,
            'comment': '',
            'confirmed_delivery_date': False,
            'text_error': '',
            'price_unit_defined': False,
        }

        # Order Reference*
        cell_nb = header_index.get('Order Reference', False)
        order_name = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if order_name:
            order_ids = purchase_obj.search(cr, uid, [('name', '=', order_name)], context=context)
            if not order_ids:
                to_write['error_list'].append(_('The Purchase Order %s was not found in the DataBase.') % order_name)
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
            elif order_ids[0] != po_browse.id:
                to_write['error_list'].append(_('The Purchase Order %s does not correspond to the current one (%s).') % (order_name, po_browse.name))
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
            elif order_ids[0] == po_browse.id:
                to_write.update({'order_id': order_ids[0]})
        # if the order_id was not fulfilled! we deduce it from the wizard (thanks to po_browse)
        else:
            to_write.update({'order_id': po_browse.id})
        # Line
        cell_nb = header_index['Line']
        cell_data = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if cell_data:
            try:
                line_number = int(cell_data)
                to_write.update({'line_number': line_number})
            except ValueError, e:
                to_write['error_list'].append(_('The Line %s has a wrong value. Details: %s.') % (cell_data, e))
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
        else:
            to_write.update({'line_number': False})

        # Origin
        cell_nb = header_index.get('Origin', False)
        origin = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if origin:
            to_write.update({'origin': origin})

        # Notes
        cell_nb = header_index.get('Notes')
        notes = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if notes:
            to_write.update({'notes': notes})

        # Quantity
        cell_nb = header_index.get('Quantity', False)
        cell_data = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if cell_data:
            try:
                product_qty = float(cell_data)
                to_write.update({'product_qty': product_qty})
            except ValueError, e:
                to_write['error_list'].append(_('The Quantity %s has a wrong format. Details: %s.') % (cell_data, e))
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})

        # Product Code
        cell_nb = header_index.get('Product Code', False)
        product_code = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if product_code:
            p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)], context=context)
            if not p_ids:
                to_write['error_list'].append(_("The Product\'s Code %s is not found in the database.") % product_code)
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
            else:
                default_code = p_ids[0]
                to_write.update({'product_id': default_code})
        else:
            to_write.update({'product_id': False})

        # UOM
        cell_nb = header_index.get('UoM', False)
        cell_data = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if cell_data:
            product_uom = uom_obj.search(cr, uid, [('name', '=', cell_data)], context=context)
            if product_uom:
                to_write.update({'product_uom': product_uom[0]})
            else:
                to_write['error_list'].append(_('The UOM %s was not found in the DataBase.') % cell_data)
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})

        # Price
        cell_nb = header_index.get('Price', False)
        cell_data = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if cell_data:
            try:
                price_unit = float(cell_data)
                to_write.update({'price_unit': price_unit, 'price_unit_defined': True})
            except ValueError, e:
                to_write['error_list'].append(_('The Price %s has a wrong format. Details: %s.') % (cell_data, e))
                to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})

        # Delivery Confirmed Date
        cell_nb = header_index.get('Delivery Confirmed Date', False)
        confirmed_delivery_date = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if confirmed_delivery_date:
            if row.cells[cell_nb].type in ('date', 'datetime'):
                confirmed_delivery_date = confirmed_delivery_date.strftime('%Y-%m-%d')
                if confirmed_delivery_date != '1899-12-30':
                    to_write.update({'confirmed_delivery_date': confirmed_delivery_date})
                else:
                    #http://stackoverflow.com/questions/3963617/why-is-1899-12-30-the-zero-date-in-access-sql-server-instead-of-12-31
                    to_write['error_list'].append(_('"The Delivery Confirmed Date" has a wrong format and was reset to "30-12-1899" which is the default Excel date.'))
                    to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
            else:
                to_write['error_list'].append(_('"The Delivery Confirmed Date" %s has a wrong format. Please format the cell in Excel as date.') % (confirmed_delivery_date,))

        #  Comment
        cell_nb = header_index.get('Comment', False)
        comment = cell_nb and row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if comment:
            to_write.update({'comment': comment})
        return to_write

    def get_file_values(self, cr, uid, ids, rows, header_index, error_list, line_num, context=None):
        """
        Catch the file values on the form [{values of the 1st line}, {values of the 2nd line}...]
        """
        file_values = []
        for row in rows:
            line_values = {}
            for cell in enumerate(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context)):
                line_values.update({cell[0]: cell[1]})
            file_values.append(line_values)
        return file_values

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        cr = pooler.get_db(dbname).cursor()

        if context is None:
            context = {}
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        import_po_obj = self.pool.get('purchase.import.xml.line')
        import_obj = self.pool.get('purchase.line.import.xml.line')
        context.update({'import_in_progress': True, 'po_integration': True})
        cell_data = self.pool.get('import.cell.data')
        start_time = time.time()
        wiz_browse = self.browse(cr, uid, ids, context)[0]
        po_browse = wiz_browse.po_id
        po_id = po_browse.id
        header_index = context['header_index']

        processed_lines, ignore_lines, complete_lines = 0, 0, 0
        line_with_error, error_list, notif_list = [], [], []
        error_log, notif_log = '', ''

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
        rows = fileobj.getRows()
        # take all the lines of the file in a list of dict
        file_values = self.get_file_values(cr, uid, ids, rows, header_index, error_list=[], line_num=False, context=context)


        rows = fileobj.getRows()
        rows.next()
        file_line_number = 0 # we begin at 0 for referencing the first line of the file_values with this index
        total_line_num = len([row for row in fileobj.getRows()])
        first_row = True
        percent_completed = 0
        wrong_format = False
        for row in rows:
            file_line_number += 1
            if len(row) < len(header_index.keys()):
                import_po_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True}, context=context)
                error_log += _('Line %s in the Excel file was added to the file of the lines with errors because it got elements that do not fit the template. Then, none of the lines are updated. \n Please make sure that all the lines are within the template. \n'
                               ) % (file_line_number+1,)
                line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=False, line_num=False, context=context))
                ignore_lines += 1
                processed_lines += 1
                percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                self.write(cr, uid, ids, {'percent_completed':percent_completed}, context=context)
                wrong_format = True
                continue
            try:
                # take values of po (first line only)
                if first_row:
                    to_write_po = self.get_po_header_row_values(cr, uid, ids, row, po_browse, header_index, context)
                    if to_write_po.get('error_list', False):
                        import_po_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True}, context=context)
                        error_log += _('Line %s in the Excel file was added to the file of the lines with errors: %s \n') % (file_line_number+1, ' '.join(to_write_po.get('error_list', False)))
                        line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=to_write_po.get('error_list', False), line_num=False, context=context))
                    else:
                        to_write_po.update({'file_line_number': file_line_number})
                        po_import_id = import_po_obj.create(cr, uid, to_write_po, context)
                        vals_po = import_po_obj.read(cr, uid, po_import_id) # we take the whole dict of values because we don't specify the list of values
                        # We take only the not Null Value
                        filtered_vals = {}
                        for k, v in vals_po.iteritems():
                            if v:
                                filtered_vals.update({k: v})
                        po_obj.write(cr, uid, po_id, filtered_vals, context)
                        notif_list.append(_("Line %s of the Excel file updated the PO %s.") % (file_line_number+1, po_browse.name))
                    first_row = False
                # get values from row
                line_values = cell_data.get_line_values(cr, uid, ids, row)
                # ignore empty line
                if not line_values:
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    continue
                empty_list = [line for line in line_values if line==False]
                if empty_list and len(empty_list)==len(line_values):
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    continue
                # take values of po line
                to_write = self.get_po_row_values(cr, uid, ids, row, po_browse, header_index, context)
                # if not line_number nor product_id, we ignore the line
                if not to_write.get('line_number', False) or not to_write.get('product_id', False):
                    import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False}, context)
                    error_log += _('Import blocked by the Line %s in the Excel file that was added to the file of the lines with errors because it needs to have at least the "Line number" and the "Product" as identifier. \n Please make sure that all the lines got at least a "Product" and a "Line Number".\n'
                                   ) % (file_line_number+1,)
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=False, line_num=False, context=context))
                    ignore_lines += 1
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    wrong_format = True
                    continue
                # we check consistency on the model of on_change functions to call for updating values
                to_write_check = pol_obj.check_line_consistency(cr, uid, False, to_write=to_write, context=context)
                if to_write.get('error_list', False) or to_write_check.get('text_error', '').strip():
                    import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False}, context)
                    error_log += _('Line %s in the Excel file was added to the file of the lines with errors: %s \n') % (file_line_number+1, ' '.join(to_write.get('error_list', False)) or to_write_check.get('text_error', False))
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=to_write.get('error_list', False), line_num=False, context=context))
                    ignore_lines += 1
                    processed_lines += 1
                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                else:
                    line_number = to_write['line_number']
                    # We ignore the lines with a line number that does not correspond to any line number of the PO line
                    if not pol_obj.search(cr, uid, [('order_id', '=', po_id), ('line_number', '=', line_number)], context=context):
                        import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False}, context)
                        error_log += _('Line %s in the Excel file was added to the file of the lines with errors: the line number %s does not exist for %s \n') % (file_line_number+1, line_number, po_browse.name)
                        line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=to_write.get('error_list', False), line_num=False, context=context))
                        ignore_lines += 1
                        processed_lines += 1
                        percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                    else:
                        to_write.update({'file_line_number': file_line_number})
                        import_obj.create(cr, uid, to_write, context)
            except osv.except_osv as osv_error:
                import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False}, context)
                osv_value = osv_error.value
                osv_name = osv_error.name
                error_log += _("Line %s in the Excel file was added to the file of the lines with errors: %s: %s\n") % (file_line_number+1, osv_name, osv_value)
                line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=file_line_number, context=context))
                ignore_lines += 1
                processed_lines += 1
                percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
            finally:
                self.write(cr, uid, ids, {'percent_completed':percent_completed})
        # we check that all the lines are taken into a table (borders around)
        if not wrong_format:
            # start importing lines
            sql_line_number = """
            select distinct line_number
            from purchase_order_line
            where order_id = %s
            """
            cr.execute(sql_line_number, (po_id,))
            list_line_number = cr.fetchall()
            for line_number in list_line_number:
                line_number = line_number[0]
                same_file_line_nb = import_obj.search(cr, uid, [('line_ignored_ok', '=', False), ('line_number', '=', line_number), ('order_id', '=', po_id)], context=context)
                same_pol_line_nb = pol_obj.search(cr, uid, [('line_number', '=', line_number), ('order_id', '=', po_id)], context=context)
                count_same_file_line_nb = len(same_file_line_nb)
                count_same_pol_line_nb = len(same_pol_line_nb)
                # we deal with 3 cases
                if same_file_line_nb:
                    # 1st CASE
                    if count_same_file_line_nb == count_same_pol_line_nb:
                        # 'We update all the lines.'
                        for pol_line, file_line in zip(pol_obj.browse(cr, uid, same_pol_line_nb, context), import_obj.read(cr, uid, same_file_line_nb)):# with the read we take the whole dict of values because we don't specify the list of values
                            vals = file_line
                            file_line_number = vals.get('file_line_number', False)
                            # We take only the not Null Value
                            filtered_vals = {}
                            for k, v in vals.iteritems():
                                if v:
                                    filtered_vals.update({k: v})
                            pol_obj.write(cr, uid, pol_line.id, filtered_vals)
                            notif_list.append(_("Line %s of the Excel file updated the PO line %s with the product %s.")
                                              % (file_line_number+1, pol_line.line_number, pol_line.product_id.default_code))
                            complete_lines += 1
                            processed_lines += 1
                            percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                            self.write(cr, uid, ids, {'percent_completed':percent_completed})
                    # 2nd CASE
                    elif count_same_file_line_nb < count_same_pol_line_nb:
                        # if the product is the same: we update the corresponding line
                        file_line_proceed = []
                        for pol_line in pol_obj.browse(cr, uid, same_pol_line_nb, context):
                            # is a product similar between the file line and obj line?
                            overlapping_lines = import_obj.search(cr, uid, [('id', 'in', same_file_line_nb), ('product_id', '=', pol_line.product_id.id)], context=context)
                            if overlapping_lines and len(overlapping_lines) == 1 and overlapping_lines[0] not in file_line_proceed:
                                import_values = import_obj.read(cr, uid, overlapping_lines)[0] # we take the whole dict of values because we don't specify the list of values
                                file_line_number = import_values.get('file_line_number', False)
                                # We take only the not Null Value
                                filtered_vals = {}
                                for k, v in import_values.iteritems():
                                    if v:
                                        filtered_vals.update({k: v})
                                pol_obj.write(cr, uid, pol_line.id, filtered_vals, context)
                                notif_list.append(_("Line %s of the Excel file updated the line %s with the product %s in common.")
                                                  % (file_line_number+1, pol_line.line_number, pol_line.product_id.default_code))
                                file_line_proceed.append(overlapping_lines[0])
                                complete_lines += 1
                                processed_lines += 1
                                percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                self.write(cr, uid, ids, {'percent_completed':percent_completed}, context)
                        #we ignore the file lines with this line number because we can't know which lines to update or not.
                        for line in import_obj.read(cr, uid, same_file_line_nb):
                            if not line.get('line_ignored_ok', False) and line.get('id', False) not in file_line_proceed:
                                error_log += _("""Line %s in the Excel file was added to the file of the lines with errors: for the %s several POs with the line number %s, we can't find any to update with the product %s\n""") % (
                                    line['file_line_number']+1,
                                    count_same_pol_line_nb, line_number,
                                    file_values[line.get('file_line_number', False)] and file_values[line.get('file_line_number', False)][header_index['Product Code']])
                                data = file_values[line['file_line_number']].items()
                                line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                                ignore_lines += 1
                                processed_lines += 1
                                percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                self.write(cr, uid, ids, {'percent_completed':percent_completed}, context)
                    # 3rd CASE
                    elif count_same_file_line_nb > count_same_pol_line_nb:
                        if count_same_pol_line_nb == 1:
                            #"We split the only line with this line number"
                            product_qty = 0.0
                            file_line_read = import_obj.read(cr, uid, same_file_line_nb) # we take the whole dict of values because we don't specify the list of values
                            i = 0
                            read_pol_product_id = pol_obj.read(cr, uid, same_pol_line_nb, ['product_id'])[0]['product_id'][0]
                            for indice, file_line in enumerate(file_line_read):
                                product_qty += file_line.get('product_qty', False)
                                if file_line.get('product_id', False) == read_pol_product_id:
                                    i = indice
                            # we take the values that correspond to the last indice of the line that has a product in common with the po line to split, else we take the first
                            import_values = file_line_read[i]
                            del same_file_line_nb[i]
                            lines = [str(import_values.get('file_line_number', False)+1)]
                            import_values.update({'product_qty': product_qty})
                            # We take only the not Null Value
                            filtered_vals = {}
                            for k, v in import_values.iteritems():
                                if v:
                                    filtered_vals.update({k: v})
                            pol_obj.write(cr, uid, same_pol_line_nb, filtered_vals, context)
                            complete_lines += 1
                            processed_lines += 1
                            percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                            self.write(cr, uid, ids, {'percent_completed':percent_completed}, context)
                            for file_line in import_obj.browse(cr, uid, same_file_line_nb):
                                wizard_values = pol_obj.open_split_wizard(cr, uid, same_pol_line_nb, context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']],
                                                                                {'new_line_qty': file_line.product_qty}, context=wiz_context)
                                try:
                                    self.pool.get(wizard_values['res_model']).split_line(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                    lines.append(str(file_line.file_line_number+1))
                                    po_line_ids = pol_obj.search(cr, uid, [('product_qty', '=', file_line.product_qty),
                                                                           ('line_number', '=', line_number),
                                                                           ('order_id', '=', po_id)], context=context)
                                    new_po_line = po_line_ids[-1]
                                    pol_obj.write(cr, uid, [new_po_line], {'product_qty': file_line.product_qty,
                                                                           'product_uom': file_line.product_uom.id,
                                                                           'product_id': file_line.product_id.id,
                                                                           'price_unit': file_line.price_unit,
                                                                           'confirmed_delivery_date': file_line.confirmed_delivery_date}, context)
                                    complete_lines += 1
                                    processed_lines += 1
                                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                    self.write(cr, uid, ids, {'percent_completed':percent_completed}, context)
                                except osv.except_osv as osv_error:
                                    error_list.append(_("Line %s of the Excel file was added to the file of the lines with errors : %s") % (file_line.file_line_number+1, osv_error.value))
                                    data = file_values[file_line.file_line_number].items()
                                    line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                                    ignore_lines += 1
                                    processed_lines += 1
                                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                    self.write(cr, uid, ids, {'percent_completed':percent_completed}, context=context)
                                    break
                            lines = ','.join(lines)
                            notif_list.append(_("Lines %s of the Excel file produced a split for the line %s.") % (lines, line_number))
                        elif count_same_pol_line_nb > 1:
                            # if the product is the same: we update the corresponding line
                            file_line_proceed = []
                            for pol_line in pol_obj.browse(cr, uid, same_pol_line_nb, context):
                                # is a product similar between the file line and obj line?
                                overlapping_lines = import_obj.search(cr, uid, [('id', 'in', same_file_line_nb), ('product_id', '=', pol_line.product_id.id)], context=context)
                                if overlapping_lines and len(overlapping_lines) == 1 and overlapping_lines[0] not in file_line_proceed:
                                    import_values = import_obj.read(cr, uid, overlapping_lines)[0] # we take the whole dict of values because we don't specify the list of values
                                    file_line_number = import_values.get('file_line_number', False)
                                    # We take only the not Null Value
                                    filtered_vals = {}
                                    for k, v in import_values.iteritems():
                                        if v:
                                            filtered_vals.update({k: v})
                                    pol_obj.write(cr, uid, pol_line.id, filtered_vals, context=context)
                                    notif_list.append(_("Line %s of the Excel file updated the line %s with the product %s in common.")
                                                      % (file_line_number+1, pol_line.line_number, pol_line.product_id.default_code))
                                    file_line_proceed.append(overlapping_lines[0])
                                    complete_lines += 1
                                    processed_lines += 1
                                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                    self.write(cr, uid, ids, {'percent_completed':percent_completed}, context=context)
                            # we ignore the file lines that doesn't correspond to any PO line for this product and this line_number
                            for line in import_obj.read(cr, uid, same_file_line_nb):
                                if not line['line_ignored_ok'] and line['id'] not in file_line_proceed:
                                    error_log += _("""Line %s in the Excel file was added to the file of the lines with errors: for the %s several POs with the line number %s, we can't find any to update with the product %s\n""") % (
                                        line['file_line_number']+1,
                                        count_same_pol_line_nb, line_number,
                                        file_values[line['file_line_number']][header_index['Product Code']])
                                    data = file_values[line.get('file_line_number', False)].items()
                                    line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                                    ignore_lines += 1
                                    processed_lines += 1
                                    percent_completed = float(processed_lines)/float(total_line_num-1)*100.0
                                    self.write(cr, uid, ids, {'percent_completed':percent_completed}, context=context)
                    # we commit after each iteration to avoid lock on ir.sequence
                    cr.commit()
        # None of the lines are updated but we write that the import is completed to 100% to notify the user that it is finished
        elif wrong_format:
            ignore_lines = total_line_num-1
            self.write(cr, uid, ids, {'percent_completed':100.0}, context=context)
        error_log += '\n'.join(error_list)
        notif_log += '\n'.join(notif_list)
        if error_log:
            error_log = _(" ---------------------------------\n Errors report : \n") + error_log
        if notif_log:
            notif_log = _("--------------------------------- \n Modifications report: \n") + notif_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + ' second(s)'
        message = ''' Importation completed in %s!
# of imported lines : %s
# of ignored lines: %s
%s

%s
    ''' % (total_time ,complete_lines, ignore_lines, error_log, notif_log)
        wizard_vals = {'message': message, 'state': 'done'}
        if line_with_error:
            file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
            wizard_vals.update(file_to_export)
        self.write(cr, uid, ids, wizard_vals, context=context)
        #we delete all the lines of the temporary obj
        import_obj_ids = import_obj.search(cr, uid, [], context=context)
        import_obj.unlink(cr, uid, import_obj_ids, context=context)
        import_po_obj_ids = import_po_obj.search(cr, uid, [], context=context)
        import_po_obj.unlink(cr, uid, import_po_obj_ids, context=context)
        # we reset the PO to its original state ('confirmed')
        po_obj.write(cr, uid, po_id, {'state': 'confirmed', 'import_in_progress': False}, context)
        cr.commit()
        cr.close(True)

    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        po_obj = self.pool.get('purchase.order')
        for wiz_read in self.read(cr, uid, ids, ['po_id', 'file']):
            po_id = wiz_read['po_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")}, context=context)
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_read['file']))
                # iterator on rows
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = self.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'po_id': po_id, 'header_index': header_index})
                (res, res1) = self.check_header_values(cr, uid, ids, context, header_index)
                if not res1:
                    return False
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message}, context=context)
            # we close the PO only during the import process so that the user can't update the PO in the same time (all fields are readonly)
            po_obj.write(cr, uid, po_id, {'state': 'done', 'import_in_progress': True}, context)
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""
        Please note that %s is temporary closed during the import to avoid conflict accesses (you can see the loading on the PO note tab check box). At the end of the load, POXX will be back in the right state. You can refresh the screen if you need to follow the upload progress
""") % self.pool.get('purchase.order').read(cr, uid, po_id, ['name'])['name']
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        purchase_obj = self.pool.get('purchase.order')
        for wiz_read in self.read(cr, uid, ids, ['po_id', 'state', 'file']):
            po_id = wiz_read['po_id']
            po_name = purchase_obj.read(cr, uid, po_id, ['name'], context=context)['name']
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % po_name}, context=context)
        return False

    def open_po(self, cr, uid, ids, context=None):
        '''
        Open the PO in a new window, just to check it after an import
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id'], context=context):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'new',
                'res_id': po_id,
                'context': context,
                }


    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the PO on which I opened the wizard.
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id'], context=context):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id'], context=context):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }

wizard_import_po()


class wizard_simu_import_po_line(osv.osv_memory):
    _name = 'wizard.simu.import.po.line'

    def _get_discrepancy(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the discrepancy for all lines
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = (line.import_qty * line.import_unit_price) - (line.initial_qty * line.initial_unit_price)

        return res

    _columns = {
        'line_id': fields.many2one('purchase.order.line', string='Purchase Order Line', required=True, readonly=True),
        'import_id': fields.many2one('wizard.import.po', string='Simulation'),
        'initial_product_code': fields.char(size=32, string='Product Code'),
        'initial_product_name': fields.char(size=256, string='Product Description'),
        'initial_nomenclature': fields.char(size=256, string='Nomenclature'),
        'initial_comment': fields.char(size=256, string='Comment'),
        'initial_qty': fields.float(digits=(16,2), string='Qty', related_uom='initial_uom_id'),
        'initial_uom_id': fields.many2one('product.uom', string='UoM'),
        'initial_req_date': fields.date(string='Delivery Requested Date'),
        'initial_unit_price': fields.float(digits_compute=dp.get_precision('Sale Price Computation'), string='Unit Price'),
        'initial_origin': fields.char(size=256, string='Origin'),
        'initial_currency': fields.many2one('res.currency', string='Currency'),
        'line_number': fields.integer(string='Line'),
        'change_type': fields.selection([('split', 'Split'),
                                         ('error', 'Error'),
                                         ('del', 'Del'),
                                         ('new', 'New')], string='CHG'),
        'import_product_code': fields.char(size=32, string='Product Code'),
        'import_product_name': fields.char(size=256, string='Product Description'),
        'import_qty': fields.float(digits=(16,2), string='Qty', related_uom='import_uom_id'),
        'import_uom_id': fields.many2one('product.uom', string='UoM'),
        'import_unit_price': fields.float(digits_compute=dp.get_precision('Sale Price Computation'), string='Unit Price'),
        'discrepancy': fields.function(_get_discrepancy, method=True, string='Discrepancy', type='float',
                                       digits_compute=dp.get_precision('Sale Price Computation'), store=False),
        'currency_id': fields.many2one('res.currency', string='Currency'),
        'delivery_confirmed_date': fields.date(string='Delivery Confirmed Date'),
        'message_esc1': fields.char(size=256, string='Message ESC1'),
        'message_esc2': fields.char(size=256, string='Message ESC2'),
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Set the initial values at creation
        '''
        res = super(wizard_simu_import_po_line, self).create(cr, uid, vals, context=context)
        self.set_initial_data(cr, uid, [res], context=context)
        return res

    def set_initial_data(self, cr, uid, ids, context=None):
        '''
        Set the initial data with the values of the Purchase Order Line
        '''
        if not context:
            context = {}

        for simu_line in self.browse(cr, uid, ids, context=context):
            line = simu_line.line_id
            self.write(cr, uid, [simu_line.id], {'line_id': line.id,
                                                 'initial_product_code': line.product_id and line.product_id.default_code,
                                                 'initial_product_name': line.product_id and line.product_id.name,
                                                 'initial_nomenclature': line.nomenclature_description,
                                                 'initial_comment': line.comment,
                                                 'initial_qty': line.product_qty,
                                                 'initial_uom_id': line.product_uom.id,
                                                 'initial_req_date': line.date_planned,
                                                 'initial_unit_price': line.price_unit,
                                                 'initial_origin': line.origin,
                                                 'initial_currency': line.currency_id.id,
                                                 'line_number': line.line_number,}, context=context)

        return True

wizard_simu_import_po_line()


class wizard_export_po(osv.osv_memory):
    _name = 'wizard.export.po'
    _description = 'Export PO for integration'

    _columns = {
        'po_id': fields.many2one('purchase.order', string='PO'),
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }

    def close_window(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        res_id = self.browse(cr, uid, ids[0], context=context).po_id.id

        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'res_id': res_id}

wizard_export_po()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
