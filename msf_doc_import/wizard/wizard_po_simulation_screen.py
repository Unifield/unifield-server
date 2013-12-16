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

# Module imports
import threading
import pooler
import base64

from mx import DateTime

# Server imports
from osv import osv
from osv import fields
from tools.translate import _

# Addons imports
from msf_order_date import TRANSPORT_TYPE
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


NB_OF_HEADER_LINES = 20
NB_LINES_COLUMNS = 19


PRODUCT_NAME_ID = {}
PRODUCT_CODE_ID = {}
UOM_NAME_ID = {}
CURRENCY_NAME_ID = {}

SIMU_LINES = {}


class wizard_import_po_simulation_screen(osv.osv):
    _name = 'wizard.import.po.simulation.screen'
    _rec_name = 'order_id'

    def _get_po_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of lines in the PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = 0
            if wiz.order_id:
                res[wiz.id] = len(wiz.order_id.order_line)

        return res

    def _get_import_lines(self,cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of lines after the import
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = 0
            if wiz.state == 'done':
                res[wiz.id] = len(wiz.line_ids)

        return res


    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order',
                                    required=True,
                                    readonly=True),
        'message': fields.text(string='Import message',
                               readonly=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('in_progress', 'In Progress'),
                                   ('done', 'Done')], 
                                   string='State',
                                   readonly=True),
        # File information
        'file_to_import': fields.binary(string='File to import'),
        'filename': fields.char(size=64, string='Filename'),
        'error_file': fields.binary(string='File with errors'),
        'error_filename': fields.char(size=64, string='Lines with errors'),
        'nb_file_lines': fields.integer(string='Total of file lines',
                                        readonly=True),
        'nb_treated_lines': fields.integer(string='Nb treated lines',
                                           readonly=True),
        'percent_completed': fields.float(string='Percent completed',
                                          readonly=True),
        'import_error_ok': fields.boolean(string='Error at import'),
        # PO Header information
        'in_creation_date': fields.related('order_id', 'date_order',
                                           type='date',
                                           string='Creation date',
                                           readonly=True),
        'in_supplier_ref': fields.related('order_id', 'partner_ref',
                                          type='char',
                                          string='Supplier Reference',
                                          readonly=True),
        'in_dest_addr': fields.related('order_id', 'dest_address_id',
                                       type='many2one',
                                       relation='res.partner.address',
                                       string='Destination Address',
                                       readonly=True),
        'in_transport_mode': fields.related('order_id', 'transport_type',
                                            type='selection',
                                            selection=TRANSPORT_TYPE,
                                            string='Transport mode',
                                            readonly=True),
        'in_notes': fields.related('order_id', 'notes', type='text', 
                                   string='Header notes', readonly=True),
        'in_currency': fields.related('order_id', 'pricelist_id',
                                      type='relation',
                                      relation='product.pricelist',
                                      string='Currency',
                                      readonly=True),
        'in_ready_to_ship_date': fields.related('order_id', 'ready_to_ship_date',
                                                type='date',
                                                string='RTS Date',
                                                readonly=True),
        'in_amount_untaxed': fields.related('order_id', 'amount_untaxed',
                                            string='Untaxed Amount',
                                            readonly=True),
        'in_amount_tax': fields.related('order_id', 'amount_tax',
                                        string='Taxes',
                                        readonly=True),
        'in_amount_total': fields.related('order_id', 'amount_total',
                                          string='Total',
                                          readonly=True),
        'in_transport_cost': fields.related('order_id', 'transport_cost',
                                            string='Transport mt',
                                            readonly=True),
        'in_total_price_include_transport': fields.related('order_id', 'total_price_include_transport',
                                                           string='Total incl. transport',
                                                           readonly=True),
        'nb_po_lines': fields.function(_get_po_lines, method=True, type='integer',
                                       string='Nb PO lines', readonly=True),
        # Import fiels
        'imp_supplier_ref': fields.char(size=256, string='Supplier Ref', 
                                        readonly=True),
        'imp_transport_mode': fields.selection(selection=TRANSPORT_TYPE,
                                               string='Transport mode',
                                               readonly=True),
        'imp_ready_to_ship_date': fields.date(string='RTS Date',
                                              readonly=True),
        'imp_message_esc': fields.text(string='Message ESC Header',
                                       readonly=True),
        'imp_amount_untaxed': fields.float(digits=(16,2),
                                           string='Untaxed Amount',
                                           readonly=True),
        'imp_amount_total': fields.float(digits=(16,2),
                                         string='Total Amount',
                                         readonly=True),
        'imp_total_price_include_transport': fields.float(digits=(16,2),
                                                          string='Total incl. transport',
                                                          readonly=True),
        'amount_discrepancy': fields.float(digits=(16,2),
                                           string='Discrepancy',
                                           readonly=True),
        'imp_nb_po_lines': fields.function(_get_import_lines, methode=True,
                                           type='integer', string='Nb Import lines',
                                           readonly=True),
        'simu_line_ids': fields.one2many('wizard.import.po.simulation.screen.line',
                                         'simu_id', string='Lines', readonly=True),
    }

    '''
    Action buttons
    '''
    def return_to_po(self, cr, uid, ids, context=None):
        '''
        Go back to PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            order_id = wiz['order_id']
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'view_type': 'form',
                    'view_mode': 'form, tree',
                    'target': 'crush',
                    'res_id': order_id,
                    'context': context,
                    }

    def import_file(self, cr, uid, ids, context=None):
        '''
        Launch a thread to import the file
        '''
        po_obj = self.pool.get('purchase.order')
        po_name = False

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if not wiz.file_to_import:
                raise osv.except_osv(_('Error'), _('Nothing to import'))
            
            po_obj.write(cr, uid, wiz.order_id.id, {'state': 'done', 'import_in_progress': True}, context=context)
            po_name = wiz.order_id.name
            break

        thread = threading.Thread(target=self._simulate, args=(cr.dbname, uid, ids, context))
        thread.start()

        msg_to_return = _("""
Important, please do not update the Purchase Order %s
Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""") % po_name
        
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Display the simulation screen
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': ids[0],
                'target': 'crush',
                'context': context}


    '''
    Simulate routine
    '''
    def simulate(self, dbname, uid, ids, context=None):
        '''
        Import the file and fill the data in simulation screen
        '''
        #cr = pooler.get_db(dbname).cursor()
        cr = dbname
        wl_obj = self.pool.get('wizard.import.po.simulation.screen.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            # No file => Return to the simulation screen
            if not wiz.file_to_import:
                self.write(cr, uid, [wiz.id], {'message': _('No file to import'),
                                               'state': 'draft'}, context=context)

            for line in wiz.simu_line_ids:
                # Put data in cache
                if line.in_product_id:
                    PRODUCT_NAME_ID.setdefault(line.in_product_id.name, line.in_product_id.id)
                    PRODUCT_CODE_ID.setdefault(line.in_product_id.default_code, line.in_product_id.id)
                if line.in_uom:
                    UOM_NAME_ID.setdefault(line.in_uom.name, line.in_uom.id)
                if line.in_currency:
                    CURRENCY_NAME_ID.setdefault(line.in_currency.name, line.in_currency.id)

                l_num = line.in_line_number
                l_prod = line.in_product_id and line.in_product_id.id or False
                l_uom = line.in_uom and line.in_uom.id or False
                # By simulation screen
                SIMU_LINES.setdefault(wiz.id, {})
                SIMU_LINES[wiz.id].setdefault('line_ids', [])
                SIMU_LINES[wiz.id]['line_ids'].append(line.id)
                # By line number
                SIMU_LINES[wiz.id].setdefault(l_num, {})
                SIMU_LINES[wiz.id][l_num].setdefault('line_ids', [])
                SIMU_LINES[wiz.id][l_num]['line_ids'].append(line.id)
                # By product
                SIMU_LINES[wiz.id][l_num].setdefault(l_prod, {})
                SIMU_LINES[wiz.id][l_num][l_prod].setdefault('line_ids', [])
                SIMU_LINES[wiz.id][l_num][l_prod]['line_ids'].append(line.id)
                # By UoM
                SIMU_LINES[wiz.id][l_num][l_prod].setdefault(l_uom, {})
                SIMU_LINES[wiz.id][l_num][l_prod][l_uom].setdefault('line_ids', [])
                SIMU_LINES[wiz.id][l_num][l_prod][l_uom]['line_ids'].append(line.id)
                # By Qty
                SIMU_LINES[wiz.id][l_num][l_prod][l_uom].setdefault(line.in_qty, [])
                SIMU_LINES[wiz.id][l_num][l_prod][l_uom][line.in_qty].append(line.id)

            # Variables
            values = {}
            lines_to_ignored = []   # Bad formatting lines
            lines_with_errors = []  # Bad values lines
            file_format_errors = []
            values_header_errors = []
            values_line_errors = []
            message = ''

            header_values = {}

            # Read the XML Excel file
            xml_file = base64.decodestring(wiz.file_to_import)
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

            '''
            We check for each line if the number of columns is consistent
            with the expected number of columns :
              * For PO header information : 2 columns
              * For the line information : 17 columns
            '''
            # Check number of columns on lines

            for x in xrange(1, NB_OF_HEADER_LINES+1):
                if len(values.get(x, [])) != 2:
                    lines_to_ignored.append(x)
                    error_msg = _('Line %s of the imported file: The header \
information must be on two columns : Column A for name of the field and column\
 B for value.') % x
                    file_format_errors.append(error_msg)

            if len(values.get(NB_OF_HEADER_LINES+1, [])) != NB_LINES_COLUMNS:
                error_msg = _('Line 20 of the Excel file: This line is \
mandatory and must have 17 columns. The values on this line must be the name \
of the field for PO lines.')
                file_format_errors.append(error_msg)

            for x in xrange(NB_OF_HEADER_LINES+2, len(values)+1):
                if len(values.get(x, [])) != NB_LINES_COLUMNS:
                    lines_to_ignored.append(x)
                    error_msg = _('Line %s of the imported file: The line \
information must be on 17 columns. The line %s has %s columns') % (x, x, len(values.get(x, [])))
                    file_format_errors.append(error_msg)

            if len(file_format_errors):
                message = '''## IMPORT STOPPED ##

Nothing has been imported because of bad file format. See below :

## File format errors ##\n\n'''
                for err in file_format_errors:
                    message += '%s\n' % err

                self.write(cr, uid, [wiz.id], {'message': message}, context)
                return self.go_to_simulation(cr, uid, [wiz.id], context=context)

            '''
            Now, we know that the file has the good format, you can import
            data for header.
            '''
            # Line 1: Order reference
            order_ref = values.get(1, [])[1]
            if order_ref != wiz.order_id.name:
                message = '''## IMPORT STOPPED ##

LINE 1 OF THE IMPORTED FILE: THE ORDER REFERENCE \
IN THE FILE IS NOT THE SAME AS THE ORDER REFERENCE OF THE SIMULATION SCREEN.\

YOU SHOULD IMPORT A FILE THAT HAS THE SAME ORDER REFERENCE THAN THE SIMULATION\
SCREEN !'''
                self.write(cr, uid, [wiz.id], {'message': message}, context)
                return self.go_to_simulation(cr, uid, [wiz.id], context=context)

            # Line 2: Order Type
            # Nothing to do

            # Line 3: Order Category
            # Nothing to do

            # Line 4: Creation Date
            # Nothing to do

            # Line 5: Supplier Reference
            supplier_ref = values.get(5, [])[1]
            if supplier_ref:
                header_values['imp_supplier_ref'] = supplier_ref

            # Line 6: Details
            # Nothing to do

            # Line 7: Delivery Requested Date
            # Nothing to do

            # Line 8: Transport mode
            transport_mode = values.get(8, [])[1]
            transport_select = self.fields_get(cr, uid, ['imp_transport_mode'], context=context)
            for x in transport_select['imp_transport_mode']['selection']:
                if x[1] == transport_mode:
                    transport_mode = x[0]
                    break
            header_values['imp_transport_mode'] = transport_mode


            # Line 9: RTS Date
            rts_date = values.get(9, [])[1]
            if rts_date:
                rts_date = time.strptime(rts_date)
                err_msg = _('Line 9 of the Excel file: The date \'%s\' is not \
a valid date. A date must be formatted like \'YYYY-MM-DD\'') % rts_date

            # Line 10: Address name
            # Nothing to do

            # Line 11: Address street
            # Nothing to do

            # Line 12: Address street 2
            # Nothing to do

            # Line 13: Zip
            # Nothing to do

            # Line 14: City
            # Nothing to do

            # Line 15: Country
            # Nothing to do
            
            # Line 16: Shipment date
            # Nothing to do

            # Line 17: Notes
            # Nothing to do

            # Line 18: Origin
            # Nothing to do

            # Line 19: Project Ref.
            # Nothing to do

            # Line 20: Message ESC Header
            header_values['imp_message_esc'] = values.get(19, [])[1]


            '''
            The header values have been imported, start the importation of
            lines
            '''
            lines_by_number = {}
            file_lines = {}
            file_po_lines = {}
            new_po_lines = []
            # Loop on lines
            for x in xrange(NB_OF_HEADER_LINES+2, len(values)+1):
                line_number = int(values.get(x, [])[0])

                # Get the better matching line
                product_id = False
                uom_id = False
                qty = 0.00

                vals = values.get(x, [])

                # Product
                if vals[2]:
                    product_id = PRODUCT_CODE_ID.get(vals[2], False)
                if not product_id and vals[3]:
                    product_id = PRODUCT_NAME_ID.get(vals[3], False)

                # UoM
                if vals[5]:
                    uom_id = UOM_NAME_ID.get(vals[5], False)

                # Qty
                if vals[4]:
                    qty = vals[4]

                file_lines[x] = (line_number, product_id, uom_id, qty)

            to_del = []
            for x, fl in file_lines.iteritems():
                # Search lines with same product, same UoM and same qty
                matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                tmp_wl_ids = matching_lines.get(fl[1], {}).get(fl[2], {}).get(fl[3], [])
                no_match = True
                for l in tmp_wl_ids:
                    if l not in file_po_lines:
                        file_po_lines[l] = [(x, 'match')]
                        to_del.append(x)
                        no_match = False
                        break
                if tmp_wl_ids and no_match:
                    file_po_lines[l].append((x, 'split'))
                    to_del.append(x)
            # Clear the dict
            for x in to_del:
                del file_lines[x]
            to_del = []


            for x, fl in file_lines.iteritems():
                # Search lines with same product, same UoM
                matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                tmp_wl_ids = matching_lines.get(fl[1], {}).get(fl[2], {}).get('line_ids', [])
                no_match = True
                for l in tmp_wl_ids:
                    if l not in file_po_lines:
                        file_po_lines[l] = [(x, 'match')]
                        to_del.append(x)
                        no_match = False
                        break
                if tmp_wl_ids and no_match:
                    file_po_lines[l].append((x, 'split'))
                    to_del.append(x)
            # Clear the dict
            for x in to_del:
                del file_lines[x]
            to_del = []

            for x, fl in file_lines.iteritems():
                # Search lines with same product
                matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                tmp_wl_ids = matching_lines.get(fl[1], {}).get('line_ids', [])
                no_match = True
                for l in tmp_wl_ids:
                    if l not in file_po_lines:
                        file_po_lines[l] = [(x, 'match')]
                        to_del.append(x)
                        no_match = False
                        break
                if tmp_wl_ids and no_match:
                    file_po_lines[l].append((x, 'split'))
                    to_del.append(x)
            # Clear the dict
            for x in to_del:
                del file_lines[x]
            to_del = []

            for x, fl in file_lines.iteritems():
                # Search lines with same line number
                matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                tmp_wl_ids = matching_lines.get('line_ids', [])
                no_match = True
                for l in tmp_wl_ids:
                    if l not in file_po_lines:
                        file_po_lines[l] = [(x, 'match')]
                        to_del.append(x)
                        no_match = False
                        break
                if tmp_wl_ids and no_match:
                    file_po_lines[l].append((x, 'split'))
                    to_del.append(x)
            # Clear the dict
            for x in to_del:
                del file_lines[x]
            to_del = []

            for x in file_lines.keys():
                new_po_lines.append(x)

            for po_line, file_lines in file_po_lines.iteritems():
                if po_line in SIMU_LINES[wiz.id]['line_ids']:
                    index_po_line = SIMU_LINES[wiz.id]['line_ids'].index(po_line)
                    SIMU_LINES[wiz.id]['line_ids'].pop(index_po_line)
                for file_line in file_lines:
                    vals = values.get(file_line[0], [])
                    if file_line[1] == 'match':
                        err_msg = wl_obj.import_line(cr, uid, po_line, vals, context=context)
                    elif file_line[1] == 'split':
                        new_wl_id = wl_obj.copy(cr, uid, po_line,
                                                         {'type_change': 'split',
                                                          'parent_line_id': po_line,
                                                          'po_line_id': False}, context=context)
                        err_msg = wl_obj.import_line(cr, uid, new_wl_id, vals, context=context)

                if err_msg:
                    for err in err_msg:
                        err = 'Line %s of the Excel file: %s' % (file_line[0], err)
                        values_line_errors.append(err)


            # Create new lines
            for po_line in new_po_lines:
                if po_line in SIMU_LINES[wiz.id]['line_ids']:
                    index_po_line = SIMU_LINES[wiz.id]['line_ids'].index(po_line)
                    SIMU_LINES[wiz.id]['line_ids'].pop(index_po_line)
                vals = values.get(po_line, [])
                new_wl_id = wl_obj.create(cr, uid, {'type_change': 'new',
                                                    'in_line_number': int(values.get(po_line, [])[0]),
                                                    'simu_id': wiz.id}, context=context)
                err_msg = wl_obj.import_line(cr, uid, new_wl_id, vals, context=context)

                if err_msg:
                    for err in err_msg:
                        err = 'Line %s of the Excel file: %s' % (file_line[0], err)
                        values_line_errors.append(err)

            # Lines to delete
            for po_line in SIMU_LINES[wiz.id]['line_ids']:
                wl_obj.write(cr, uid, po_line, {'type_change': 'del'}, context=context)

            '''
            We generate the message which will be displayed on the simulation
            screen. This message is a merge between all errors.
            '''
            # Generate the message
            if len(values_header_errors):
                message += '\n## Error on header values ##\n\n'
                for err in values_header_errors:
                    message += '%s\n' % err
            
            if len(values_line_errors):
                message += '\n## Error on line values ##\n\n'
                for err in values_line_errors:
                    message += '%s\n' % err

            header_values['message'] = message
            self.write(cr, uid, [wiz.id], header_values, context=context)

            return self.go_to_simulation(cr, uid, [wiz.id], context=context)
            

wizard_import_po_simulation_screen()


class wizard_import_po_simulation_screen_line(osv.osv):
    _name = 'wizard.import.po.simulation.screen.line'
    _order = 'in_line_number, in_product_id, id'
    _rec_name = 'in_line_number'

    def _get_line_info(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get values for each lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'in_product_id': False,
                            'in_nomen': False,
                            'in_comment': False,
                            'in_qty': 0.00,
                            'in_uom': False,
                            'in_drd': False,
                            'in_price': 0.00,
                            'in_currency': False,
                            'imp_discrepancy': 0.00,
                            'change_ok': False}

            if line.po_line_id:
                l = line.po_line_id
                res[line.id]['in_product_id'] = l.product_id and l.product_id.id or False
                res[line.id]['in_nomen'] = l.nomenclature_description
                res[line.id]['in_qty'] = l.product_qty
                res[line.id]['in_uom'] = l.product_uom and l.product_uom.id or False
                res[line.id]['in_drd'] = l.date_planned
                res[line.id]['in_price'] = l.price_unit
                res[line.id]['in_currency'] = l.currency_id and l.currency_id.id or False
                if line.imp_qty and line.imp_price:
                    disc = (line.imp_qty*line.imp_price)-(line.in_qty*line.in_price)
                    res[line.id]['imp_discrepancy'] = disc

                prod_change = False
                if res[line.id]['in_product_id'] and not line.imp_product_id or \
                   not res[line.id]['in_product_id'] and line.imp_product_id or \
                   res[line.id]['in_product_id'] != line.imp_product_id.id:
                    prod_change = True
                qty_change = not(res[line.id]['in_qty'] == line.imp_qty)
                price_change = not(res[line.id]['in_price'] == line.imp_price)
                drd_change = not(res[line.id]['in_drd'] == line.imp_drd)

                if prod_change or qty_change or price_change or drd_change:
                    res[line.id]['change_ok'] = True
            elif line.type_change == 'del':
                res[line.id]['imp_discrepancy'] = -(line.in_qty*line.in_price)
            else:
                res[line.id]['imp_discrepancy'] = line.imp_qty*line.imp_price

        return res

    _columns = {
        'po_line_id': fields.many2one('purchase.order.line', string='Line',
                                      readonly=True),
        'simu_id': fields.many2one('wizard.import.po.simulation.screen',
                                   string='Simulation screen',
                                   readonly=True, ondelete='cascade'),
        'in_product_id': fields.function(_get_line_info, method=True, multi='line',
                                         type='many2one', relation='product.product',
                                         string='Product', readonly=True, store=True),
        'in_nomen': fields.function(_get_line_info, method=True, multi='line',
                                    type='char', size=256, string='Nomenclature',
                                    readonly=True, store=True),
        'in_comment': fields.function(_get_line_info, method=True, multi='line',
                                      type='char', size=256, string='Comment',
                                      readonly=True, store=True),
        'in_qty': fields.function(_get_line_info, method=True, multi='line',
                                  type='float', string='Qty',
                                  readonly=True, store=True),
        'in_uom': fields.function(_get_line_info, method=True, multi='line',
                                  type='many2one', relation='product.uom', string='UoM',
                                  readonly=True, store=True),
        'in_drd': fields.function(_get_line_info, method=True, multi='line',
                                  type='date', string='Delivery Requested Date',
                                  readonly=True, store=True),
        'in_price': fields.function(_get_line_info, method=True, multi='line',
                                    type='float', string='Price Unit',
                                    readonly=True, store=True),
        'in_currency': fields.function(_get_line_info, method=True, multi='line',
                                       type='many2one', relation='res.currency', string='Currency',
                                       readonly=True, store=True),
        'in_line_number': fields.integer(string='Line', readonly=True),
        'type_change': fields.selection([('', ''), ('error', 'Error'), ('new', 'New'),
                                         ('split', 'Split'), ('del', 'Del'),], 
                                         string='CHG', readonly=True),
        'imp_product_id': fields.many2one('product.product', string='Product',
                                          readonly=True),
        'imp_qty': fields.float(digits=(16,2), string='Qty', readonly=True),
        'imp_uom': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_price': fields.float(digits=(16,2), string='Price Unit', readonly=True),
        'imp_discrepancy': fields.function(_get_line_info, method=True, multi='line',
                                           type='float', string='Discrepancy', store=False),
        'imp_currency': fields.many2one('res.currency', string='Currency', readonly=True),
        'imp_drd': fields.date(string='Delivery Requested Date', readonly=True),
        'imp_esc1': fields.char(size=256, string='Message ESC1', readonly=True),
        'imp_esc2': fields.char(size=256, string='Message ESC2', readonly=True),
        'change_ok': fields.function(_get_line_info, method=True, multi='line',
                                     type='boolean', string='Change', store=False),
        'parent_line_id': fields.many2one('wizard.import.po.simulation.screen.line',
                                          string='Parent line id',
                                          help='Use to split the good PO line',
                                          readonly=True),
    }

    def import_line(self, cr, uid, ids, values, context=None):
        '''
        Write the line with the values
        '''
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        if isinstance(ids, (int, long)):
            ids = [ids]

        errors = []

        for line in self.browse(cr, uid, ids, context=context):
            write_vals = {}
            # Product
            if (values[2] and values[2] == line.in_product_id.default_code) or\
               (values[3] and values[3] == line.in_product_id.name):
                write_vals['imp_product_id'] = line.in_product_id and line.in_product_id.id or False
            else:
                prod_id = False
                if values[2]:
                    prod_id = PRODUCT_CODE_ID.get(values[2])
                if not prod_id and values[3]:
                    prod_id = PRODUCT_NAME_ID.get(values[3])

                if not prod_id:
                    prod_ids = prod_obj.search(cr, uid, ['|', ('default_code', '=', values[2]),
                                                              ('name', '=', values[3])], context=context)
                    if not prod_ids:
                        errors.append(_('Product not found in database − Product of the initial line kept.'))
                        write_vals['imp_product_id'] = line.in_product_id and line.in_product_id.id or False
                    else:
                        write_vals['imp_product_id'] = prod_ids[0]
                else:
                    write_vals['imp_product_id'] = prod_id

            # Qty
            err_msg = _('Incorrect float value for field \'Product Qty\' - Quantity of the initial line kept.')
            try:
                qty = float(values[4])
                if qty != line.in_qty:
                    write_vals['imp_qty'] = qty
            except Exception:
                errors.append(err_msg)
            finally:
                write_vals['imp_qty'] = write_vals.get('imp_qty', line.in_qty)

            # UoM
            uom_value = values[5]
            if str(uom_value) == line.in_uom.name:
                write_vals['imp_uom'] = line.in_uom.id
            else:
                uom_id = UOM_NAME_ID.get(str(uom_value))
                if not uom_id:
                    uom_ids = uom_obj.search(cr, uid, [('name', '=', str(uom_value))], context=context)
                    if uom_ids:
                        write_vals['imp_uom'] = uom_ids[0]
                    else:
                        errors.apppend(_('UoM not found in database - UoM of the initial line kept.'))
                        write_vals['imp_uom'] = line.in_uom.id
                else:
                    write_vals['imp_uom'] = uom_id

            # Unit price
            err_msg = _('Incorrect float value for field \'Price Unit\' - Price Unit of the initial line kept.')
            try:
                unit_price = float(values[6])
                if unit_price != line.in_price:
                    write_vals['imp_price'] = unit_price
            except Exception:
                errors.append(err_msg)
            finally:
                write_vals['imp_price'] = write_vals.get('imp_price', line.in_price)

            # Currency
            currency_value = values[7]
            print currency_value
            if str(currency_value) == line.in_currency.name:
                write_vals['imp_currency'] = line.in_currency.id
            else:
                err_msg = _('The currency on the Excel file is not the same as the currency of the PO line - You must have the same currency on both side - Currency of the initial line kept.')
                errors.append(err_msg)

            # Delivery Requested Date
            drd_value = values[9]
            if drd_value and type(drd_value) == type(DateTime.now()):
                write_vals['imp_drd'] = drd_value.strftime('%Y-%m-%d')
            elif drd_value:
                err_msg = _('Incorrect date value for field \'Delivery Requested Date\' - Delivery Requested Date of the initial line kept.')

            # Message ESC1
            write_vals['imp_esc1'] = values[17]
            # Message ESC2
            write_vals['imp_esc2'] = values[18]

            self.write(cr, uid, [line.id], write_vals, context=context)
    
        return errors

wizard_import_po_simulation_screen_line()
