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
import time
import xml.etree.ElementTree as ET
from lxml import etree
from lxml.etree import XMLSyntaxError
import logging
import os
import netsvc

from mx import DateTime


# Server imports
from osv import osv
from osv import fields
from tools.translate import _
import tools

# Addons imports
from msf_order_date import TRANSPORT_TYPE
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


NB_OF_HEADER_LINES = 20
NB_LINES_COLUMNS = 20


PRODUCT_CODE_ID = {}
UOM_NAME_ID = {}
CURRENCY_NAME_ID = {}

SIMU_LINES = {}
LN_BY_EXT_REF = {}
EXT_REF_BY_LN = {}

LINES_COLUMNS = [(0, _('Line number'), 'optionnal'),
                 (1, _('External ref'), 'optionnal'),
                 (2, _('Product Code'), 'mandatory'),
                 (3, _('Product Description'), 'optionnal'),
                 (4, _('Product Qty'), 'mandatory'),
                 (5, _('Product UoM'), 'mandatory'),
                 (6, _('Price Unit'), 'mandatory'),
                 (7, _('Currency'), 'mandatory'),
                 (8, _('Origin'), 'optionnal'),
                 (11, _('Delivery Confirmed Date'), 'optionnal'),
                 (15, _('Comment'), 'optionnal'),
                 (17, _('Project Ref.'), 'optionnal'),
                 (18, _('Message ESC 1'), 'optionnal'),
                 (19, _('Message ESC 2'), 'optionnal'),
                 ]

HEADER_COLUMNS = [(1, _('Order Reference'), 'mandatory'),
                  (5, _('Supplier Reference'), 'optionnal'),
                  (10, _('Ready To Ship Date'), 'optionnal'),
                  (15, _('Shipment Date'), 'optionnal'),
                  (19, _('Message ESC'), 'optionnal')
                  ]


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

    def _get_totals(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the totals after the simulation
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for wiz in self.browse(cr, uid, ids, context=context):
            imp_amount_untaxed = 0.00
            amount_discrepancy = 0.00

            cr.execute('''SELECT
                            sum(l.imp_qty * l.imp_price) AS imp_amount_untaxed,
                            sum(imp_discrepancy) AS amount_discrepancy
                          FROM
                            wizard_import_po_simulation_screen_line l
                          WHERE l.simu_id = %(simu_id)s''', {'simu_id': wiz.id})
            db_res = cr.dictfetchall()
            for r in db_res:
                imp_amount_untaxed += r['imp_amount_untaxed'] or 0.00
                amount_discrepancy += r['amount_discrepancy'] or 0.00

            res[wiz.id] = {'imp_amount_untaxed': imp_amount_untaxed,
                           #TODO: Take into account of Taxes
                           'imp_amount_total': imp_amount_untaxed,
                           'imp_total_price_include_transport': imp_amount_untaxed + wiz.in_transport_cost,
                           'amount_discrepancy': amount_discrepancy}

        return res

    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order',
                                    required=True,
                                    readonly=True),
        'message': fields.text(string='Import message',
                               readonly=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('simu_progress', 'Simulation in progress'),
                                   ('simu_done', 'Simulation done'),
                                   ('import_progress', 'Import in progress'),
                                   ('error', 'Error'),
                                   ('done', 'Done')],
                                  string='State',
                                  readonly=True),
        'with_ad': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
            ],
            string='File contains Analytic Distribution',
            required=True,
        ),
        # File information
        'file_to_import': fields.binary(string='File to import'),
        'filename': fields.char(size=64, string='Filename'),
        'filetype': fields.selection([('excel', 'Excel file'),
                                      ('xml', 'XML file')], string='Type of file',),
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
        'in_shipment_date': fields.related('order_id', 'shipment_date',
                                           type='date',
                                           string='Shipment date',
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
        'imp_shipment_date': fields.date(string='Shipment date',
                                         readonly=True),
        'imp_notes': fields.text(string='Header notes',
                                 readonly=True),  # UFTP-59
        'imp_message_esc': fields.text(string='Message ESC Header',
                                       readonly=True),
        'imp_amount_untaxed': fields.function(_get_totals, method=True,
                                              type='float', string='Untaxed Amount',
                                              readonly=True, store=False, multi='simu'),
        'imp_amount_total': fields.function(_get_totals, method=True,
                                            type='float', string='Total Amount',
                                            readonly=True, store=False, multi='simu'),
        'imp_total_price_include_transport': fields.function(_get_totals, method=True,
                                                             type='float', string='Total incl. transport',
                                                             readonly=True, store=False, multi='simu'),
        'amount_discrepancy': fields.function(_get_totals, method=True,
                                              type='float', string='Discrepancy',
                                              readonly=True, store=False, multi='simu'),
        'imp_nb_po_lines': fields.function(_get_import_lines, method=True,
                                           type='integer', string='Nb Import lines',
                                           readonly=True),
        'simu_line_ids': fields.one2many('wizard.import.po.simulation.screen.line',
                                         'simu_id', string='Lines', readonly=True),
    }

    _defaults = {
        'state': 'draft',
        'with_ad': lambda *a: 'yes',
    }

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}

        if context.get('button') in ('go_to_simulation', 'print_simulation_report', 'return_to_po'):
            return True

        try:
            return super(wizard_import_po_simulation_screen, self).write(cr, uid, ids, vals, context=context)
        except Exception, e:
            if e[0] == 'ConcurrencyException':
                return True
            else:
                raise e

    '''
    Action buttons
    '''
    def print_simulation_report(self, cr, uid, ids, context=None):
        '''
        Print the PDF report of the simulation
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        datas = {}
        datas['ids'] = ids
        report_name = 'po.simulation.screen.xls'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'context': context,
        }

    def return_to_po(self, cr, uid, ids, context=None):
        '''
        Go back to PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            order_id = wiz['order_id'][0]
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'view_type': 'form',
                    'view_mode': 'form, tree',
                    'target': 'crush',
                    'res_id': order_id,
                    'context': context,
                    }

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Display the simulation screen
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if ids and self.browse(cr, uid, ids, context=context)[0].state == 'done':
            return self.return_to_po(cr, uid, ids, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': ids[0],
                'target': 'same',
                'context': context}

    def populate(self, cr, uid, imp_id, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, imp_id, fields_to_fetch=['order_id'], context=context)
        for line in wiz.order_id.order_line:
            self.pool.get('wizard.import.po.simulation.screen.line').create(cr, uid, {
                'po_line_id': line.id,
                'in_line_number': line.line_number,
                'in_ext_ref': line.external_ref,
                'simu_id': imp_id,
            }, context=context)

        return True

    def launch_simulate(self, cr, uid, ids, context=None, thread=True):
        '''
        Launch the simulation routine in background
        '''
        global SIMU_LINES, LN_BY_EXT_REF, EXT_REF_BY_LN
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.filetype == 'excel':
                xml_file = base64.decodestring(wiz.file_to_import)
                excel_file = SpreadsheetXML(xmlstring=xml_file)
                if not excel_file.getWorksheets():
                    raise osv.except_osv(_('Error'), _('The given file is not a valid Excel 2003 Spreadsheet file !'))
            else:
                try:
                    xml_file = base64.decodestring(wiz.file_to_import)
                    dtd_path = os.path.join(tools.config['root_path'], 'tools/import_po.dtd')
                    dtd = etree.DTD(dtd_path)
                    tree = etree.fromstring(xml_file)
                except XMLSyntaxError as ex:
                    raise osv.except_osv(_('Error'), _('The given file is not a valid XML file !\nTechnical details:\n%s') % tools.ustr(ex))

                if not dtd.validate(tree):
                    # build error message:
                    error_msg = ""
                    for line_obj in dtd.error_log.filter_from_errors():
                        line = tools.ustr(line_obj)
                        err_line = line.split(':')[1]
                        err_str = line.split(':')[-1]
                        err_type = line.split(':')[5]
                        if err_type != 'DTD_UNKNOWN_ELEM':
                            continue
                        error_msg += "Line %s: The tag '%s' is not supported\n" % (err_line, err_str.split()[-1])

                    raise osv.except_osv(_('Error'), _("The given XML file is not structured as expected in the DTD:\n %s") % error_msg)

        self.write(cr, uid, ids, {'state': 'simu_progress', 'error_filename': False, 'error_file': False,
                                  'simu_line_ids': [(6, 0, [])], 'percent_completed': 0, 'import_error_ok': False},
                   context=context)
        if ids[0] in SIMU_LINES:
            del SIMU_LINES[ids[0]]
        if ids[0] in LN_BY_EXT_REF:
            del LN_BY_EXT_REF[ids[0]]
        if ids[0] in EXT_REF_BY_LN:
            del EXT_REF_BY_LN[ids[0]]

        self.populate(cr, uid, ids[0], context=context)
        cr.commit()
        if thread:
            new_thread = threading.Thread(target=self.simulate, args=(cr.dbname, uid, ids, context))
            new_thread.start()
            new_thread.join(10.0)

            return self.go_to_simulation(cr, uid, ids, context=context)

        self.simulate(cr.dbname, uid, ids, context)
        return True

    def get_values_from_xml(self, cr, uid, file_to_import, context=None):
        '''
        Read the XML file and put data in values
        '''
        values = {}
        # Read the XML file
        xml_file = base64.decodestring(file_to_import)

        root = ET.fromstring(xml_file)
        if root.tag != 'data':
            return values

        records = []
        rec_lines = []
        rec = False

        ad_field_names = [
            'analytic_distribution_id',
            'ad_destination_name',
            'ad_cost_center_name',
            'ad_percentage',
            'ad_subtotal',
        ]

        index = 0
        for record in root:
            if record.tag == 'record':
                records.append(record)

        if len(records) > 0:
            rec = records[0]

        def get_field_index(node, index):
            if not index:
                index = 0
            if node.getchildren():
                for subnode in node:
                    index = get_field_index(subnode, index)
                return index
            else:
                index += 1
                values[index] = [node.attrib['name'], node.text or '']
                return index

        for field in rec:
            ad_field = field.attrib['name'] in ad_field_names
            if field.attrib['name'] != 'order_line' and not ad_field:
                index = get_field_index(field, index)
            elif not ad_field:
                index += 1
                values[index] = ['line_number', 'external_ref',
                                 'product_code', 'product_name',
                                 'product_qty', 'product_uom',
                                 'price_unit', 'currency_id',
                                 'origin', 'stock_take_date','comment', 'date_planned',
                                 'confirmed_delivery_date',
                                 'nomen_manda_0', 'nomen_manda_1',
                                 'nomen_manda_2',
                                 'notes', 'project_ref',
                                 'message_esc1', 'message_esc2']
                for line in field:
                    rec_lines.append(line)

        for line in rec_lines:
            index += 1
            values[index] = []
            for fl in line:
                if fl.attrib['name'] in ad_field_names:
                    continue
                if not fl.getchildren():
                    values[index].append(fl.text or '')
                else:
                    for sfl in fl:
                        values[index].append(sfl.text or '')

        return values


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


    '''
    Simulate routine
    '''
    def simulate(self, dbname, uid, ids, context=None):
        '''
        Import the file and fill the data in simulation screen
        '''
        cr = pooler.get_db(dbname).cursor()
        #cr = dbname
        try:
            wl_obj = self.pool.get('wizard.import.po.simulation.screen.line')
            prod_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')


            # Declare global variables (need this explicit declaration to clear
            # them at the end of the treatment)
            global PRODUCT_CODE_ID
            global UOM_NAME_ID
            global CURRENCY_NAME_ID
            global SIMU_LINES
            global LN_BY_EXT_REF
            global EXT_REF_BY_LN

            if context is None:
                context = {}

            if isinstance(ids, (int, long)):
                ids = [ids]

            for wiz in self.browse(cr, uid, ids, context=context):
                nb_treated_lines = 0
                # No file => Return to the simulation screen
                if not wiz.file_to_import:
                    self.write(cr, uid, [wiz.id], {'message': _('No file to import'),
                                                   'state': 'draft'}, context=context)
                    continue

                nb_file_header_lines = NB_OF_HEADER_LINES
                nb_file_lines_columns = NB_LINES_COLUMNS
                first_line_index = nb_file_header_lines + 1
                if wiz.with_ad == 'yes' and wiz.filetype != 'xml':
                    nb_file_header_lines += 2
                    first_line_index += 2

                for line in wiz.simu_line_ids:
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

                    LN_BY_EXT_REF.setdefault(wiz.id, {})
                    EXT_REF_BY_LN.setdefault(wiz.id, {})
                    if line.in_ext_ref:
                        LN_BY_EXT_REF[wiz.id].setdefault(tools.ustr(line.in_ext_ref), [])
                        EXT_REF_BY_LN[wiz.id].setdefault(l_num, [])
                        LN_BY_EXT_REF[wiz.id][line.in_ext_ref].append(l_num)
                        EXT_REF_BY_LN[wiz.id][l_num].append(tools.ustr(line.in_ext_ref))

                # Variables
                lines_to_ignored = []   # Bad formatting lines
                file_format_errors = []
                values_header_errors = []
                values_line_errors = []
                message = ''
                header_values = {}

                if wiz.filetype == 'excel':
                    values = self.get_values_from_excel(cr, uid, wiz.file_to_import, context=context)
                else:
                    values = self.get_values_from_xml(cr, uid, wiz.file_to_import, context=context)

                '''
                We check for each line if the number of columns is consistent
                with the expected number of columns :
                  * For PO header information : 2 columns
                  * For the line information : 17 columns
                '''
                # Check number of columns on lines

                for x in xrange(1, nb_file_header_lines+1):
                    nb_to_check = 2
                    if x > NB_OF_HEADER_LINES and x <= nb_file_header_lines:
                        continue
                    if len(values.get(x, [])) != nb_to_check:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The header \
information must be on two columns : Column A for name of the field and column\
 B for value.') % x
                        file_format_errors.append(error_msg)

                if len(values.get(first_line_index, [])) < nb_file_lines_columns:
                    error_msg = _('Line %s of the Excel file: This line is \
mandatory and must have at least %s columns. The values on this line must be the name \
of the field for PO lines.') % (first_line_index, nb_file_lines_columns)
                    file_format_errors.append(error_msg)

                for x in xrange(first_line_index, len(values)+1):
                    if len(values.get(x, [])) < nb_file_lines_columns:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The line \
information must be on at least %s columns. The line %s has %s columns') % (x, nb_file_lines_columns, x, len(values.get(x, [])))
                        file_format_errors.append(error_msg)

                nb_file_lines = len(values) - first_line_index
                self.write(cr, uid, [wiz.id], {'nb_file_lines': nb_file_lines}, context=context)

                if len(file_format_errors):
                    message = '''## IMPORT STOPPED ##

    Nothing has been imported because of bad file format. See below :

    ## File format errors ##\n\n'''
                    for err in file_format_errors:
                        message += '%s\n' % err

                    self.write(cr, uid, [wiz.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res

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
                    self.write(cr, uid, [wiz.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res


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

                # Line 7: Stock take date
                # Nothing to do

                # Line 8: Delivery Requested Date
                # Nothing to do

                # Line 9: Transport mode
                transport_mode = values.get(9, [])[1]
                if transport_mode:
                    transport_select = self.fields_get(cr, uid, ['imp_transport_mode'], context=context)
                    for x in transport_select['imp_transport_mode']['selection']:
                        if x[1] == transport_mode:
                            header_values['imp_transport_mode'] = x[0]
                            break
                    else:
                        possible_mode = ', '.join(x[1] for x in transport_select['imp_transport_mode']['selection'] if x[1])
                        err_msg = _('Line 9 of the file: The transport mode \'%s\' is not \
a valid transport mode. Valid transport modes: %s') % (transport_mode, possible_mode)
                        values_header_errors.append(err_msg)


                # Line 10: RTS Date
                rts_date = values.get(10, [])[1]
                if rts_date:
                    if type(rts_date) == type(DateTime.now()):
                        rts_date = rts_date.strftime('%Y-%m-%d')
                        header_values['imp_ready_to_ship_date'] = rts_date
                    else:
                        try:
                            time.strptime(rts_date, '%Y-%m-%d')
                            header_values['imp_ready_to_ship_date'] = rts_date
                        except:
                            err_msg = _('Line 10 of the file: The date \'%s\' is not \
    a valid date. A date must be formatted like \'YYYY-MM-DD\'') % rts_date
                            values_header_errors.append(err_msg)

                # Line 11: Delivery address name
                # Nothing to do

                # Line 12: Delivery address
                # Nothing to do

                # Line 13: Customer address name
                # Nothing to do

                # Line 14: Customer address
                # Nothing to do

                # Line 15: Shipment date
                shipment_date = values.get(15, [])[1]
                if shipment_date:
                    if type(shipment_date) == type(DateTime.now()):
                        shipment_date = shipment_date.strftime('%Y-%m-%d')
                        header_values['imp_shipment_date'] = shipment_date
                    else:
                        try:
                            time.strptime(shipment_date, '%Y-%m-%d')
                            header_values['imp_shipment_date'] = shipment_date
                        except:
                            err_msg = _('Line 15 of the file: The date \'%s\' is not \
    a valid date. A date must be formatted like \'YYYY-MM-DD\'') % shipment_date
                            values_header_errors.append(err_msg)

                # Line 16: Notes
                # UFTP-59
                if wiz.filetype != 'excel':
                    header_values['imp_notes'] = values.get(16, [])[1]

                # Line 17: Origin
                # Nothing to do

                # Line 18: Project Ref.
                # Nothing to do

                # Line 19: Message ESC Header
                if values.get(19, False):
                    header_values['imp_message_esc'] = values.get(19)[1]

                # Line 20: Sourcing group
                # Nothing to do

                '''
                The header values have been imported, start the importation of
                lines
                '''
                file_lines = {}
                file_po_lines = {}
                new_po_lines = []
                not_ok_file_lines = {}
                # Loop on lines
                for x in xrange(first_line_index+1, len(values)+1):

                    # Check mandatory fields
                    not_ok = False
                    file_line_error = []
                    line_number = values.get(x, [''])[0] and int(values.get(x, [''])[0]) or False
                    for manda_field in LINES_COLUMNS:
                        if manda_field[2] == 'mandatory' and not values.get(x, [])[manda_field[0]]:
                            not_ok = True
                            err1 = _('The column \'%s\' mustn\'t be empty%s') % (manda_field[1], manda_field[0] == 0 and ' - Line not imported' or '')
                            err = _('Line %s of the PO: %s') % (line_number, err1)
                            values_line_errors.append(err)
                            file_line_error.append(err1)

                    ext_ref = values.get(x, ['', ''])[1] and tools.ustr(values.get(x, ['', ''])[1])

                    if context.get('auto_import_confirm_pol'):
                        delivery_confirmed_date = values.get(x, [None]*12)[11]
                        if delivery_confirmed_date:
                            if line_number:
                                context['line_number_to_confirm'] = context.get('line_number_to_confirm', []) + [line_number]
                            elif ext_ref:
                                context['ext_ref_to_confirm'] = context.get('ext_ref_to_confirm', []) + [ext_ref]

                    if not line_number and not ext_ref:
                        not_ok = True
                        err1 = _('The line must have either the line number or the external ref. set')
                        err = _('Line %s of the file: %s') % (x, err1)
                        values_line_errors.append(err)
                        file_line_error.append(err1)

                    if line_number and ext_ref and (ext_ref not in LN_BY_EXT_REF[wiz.id].keys() or line_number not in LN_BY_EXT_REF[wiz.id][ext_ref]):
                        not_ok = True
                        err1 = _('The line cannot have both Line no. and Ext. Ref')
                        err = _('Line %s of the PO: %s') % (line_number, err1)
                        values_line_errors.append(err)
                        file_line_error.append(err1)

                    if not line_number and ext_ref and ext_ref in LN_BY_EXT_REF[wiz.id].keys():
                        line_number = LN_BY_EXT_REF[wiz.id][ext_ref][0]

                    if not ext_ref and line_number and line_number in EXT_REF_BY_LN[wiz.id].keys():
                        ext_ref = EXT_REF_BY_LN[wiz.id][line_number][0]

                    if not_ok:
                        not_ok_file_lines[x] = ' - '.join(err for err in file_line_error)

#                    if not line_number and not ext_ref:
#                        continue

                    # Get values
                    product_id = False
                    uom_id = False
                    qty = 0.00

                    vals = values.get(x, [])
                    # Product
                    if vals[2]:
                        product_id = PRODUCT_CODE_ID.get(vals[2], False)
                    if not product_id and vals[2]:
                        prod_ids = prod_obj.search(cr, uid, [('default_code', '=', vals[2])], context=context)
                        if prod_ids:
                            product_id = prod_ids[0]
                            PRODUCT_CODE_ID.setdefault(vals[2], product_id)
                    # UoM
                    if vals[5]:
                        uom_id = UOM_NAME_ID.get(vals[5], False)
                        if not uom_id:
                            uom_ids = uom_obj.search(cr, uid, [('name', '=', vals[5])], context=context)
                            if uom_ids:
                                uom_id = uom_ids[0]
                                UOM_NAME_ID.setdefault(vals[5], uom_id)
                    # Qty
                    if vals[4]:
                        qty = float(vals[4])

                    file_lines[x] = (line_number, product_id, uom_id, qty, ext_ref)

                '''
                Get the best matching line :
                    1/ Within lines with same line number, same product, same UoM and same qty
                    2/ Within lines with same line number, same product and same UoM
                    3/ Within lines with same line number and same product
                    4/ Within lines with same line number

                If a matching line is found in one of these cases, keep the link between the
                file line and the simulation screen line.
                '''
                to_del = []
                for x, fl in sorted(file_lines.iteritems()):
                    # Search lines with same product, same UoM and same qty
                    matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                    tmp_wl_ids = matching_lines.get(fl[1], {}).get(fl[2], {}).get(fl[3], [])
                    no_match = True
                    for l in tmp_wl_ids:
                        if l not in file_po_lines:
                            file_po_lines[l] = [(x, 'match', fl[0])]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_po_lines[l].append((x, 'split', fl[0]))
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
                            file_po_lines[l] = [(x, 'match', fl[0])]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_po_lines[l].append((x, 'split', fl[0]))
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
                            file_po_lines[l] = [(x, 'match', fl[0])]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_po_lines[l].append((x, 'split', fl[0]))
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
                            file_po_lines[l] = [(x, 'match', fl[0])]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_po_lines[l].append((x, 'split', fl[0]))
                        to_del.append(x)
                # Clear the dict
                for x in to_del:
                    del file_lines[x]
                to_del = []

                # For file lines with no simu. screen lines with same line number,
                # create a new simu. screen line
                for x in file_lines.keys():
                    new_po_lines.append(x)

                # Split the simu. screen line or/and update the values according
                # to linked file line.
                for po_line, file_lines in file_po_lines.iteritems():
                    if po_line in SIMU_LINES[wiz.id]['line_ids']:
                        index_po_line = SIMU_LINES[wiz.id]['line_ids'].index(po_line)
                        SIMU_LINES[wiz.id]['line_ids'].pop(index_po_line)
                    for file_line in file_lines:
                        nb_treated_lines += 1
                        percent_completed = int(float(nb_treated_lines) / float(nb_file_lines) * 100)
                        self.write(cr, uid, [wiz.id], {'nb_treated_lines': nb_treated_lines,
                                                       'percent_completed': percent_completed}, context=context)
                        vals = values.get(file_line[0], [])
                        if file_line[1] == 'match':
                            err_msg = wl_obj.import_line(cr, uid, po_line, vals, context=context)
                            if file_line[0] in not_ok_file_lines:
                                wl_obj.write(cr, uid, [po_line], {'type_change': 'error', 'error_msg': not_ok_file_lines[file_line[0]]}, context=context)
                        elif file_line[1] == 'split':
                            new_wl_id = wl_obj.copy(cr, uid, po_line,
                                                    {'type_change': 'split',
                                                     'chg_text': _('Split\nQTY'),
                                                     'parent_line_id': po_line,
                                                     'imp_dcd': False,
                                                     'po_line_id': False}, context=context)
                            err_msg = wl_obj.import_line(cr, uid, new_wl_id, vals, context=context)
                            if file_line[0] in not_ok_file_lines:
                                wl_obj.write(cr, uid, [new_wl_id], {'type_change': 'error', 'error_msg': not_ok_file_lines[file_line[0]]}, context=context)
                        # Commit modifications
                        cr.commit()

                    if err_msg:
                        for err in err_msg:
                            err = 'Line %s of the PO: %s' % (file_line[2], err)
                            values_line_errors.append(err)


                # Create new lines
                for po_line in new_po_lines:
                    nb_treated_lines += 1
                    percent_completed = int(float(nb_treated_lines) / float(nb_file_lines) * 100)
                    self.write(cr, uid, [wiz.id], {'nb_treated_lines': nb_treated_lines,
                                                   'percent_completed': percent_completed}, context=context)
                    if po_line in SIMU_LINES[wiz.id]['line_ids']:
                        index_po_line = SIMU_LINES[wiz.id]['line_ids'].index(po_line)
                        SIMU_LINES[wiz.id]['line_ids'].pop(index_po_line)
                    vals = values.get(po_line, [])
                    new_wl_id = wl_obj.create(cr, uid, {'type_change': 'new',
                                                        'in_line_number': values.get(po_line, [])[0] and int(values.get(po_line, [])[0]) or False,
                                                        'in_ext_ref': values.get(po_line, [])[1] or False,
                                                        'simu_id': wiz.id}, context=context)
                    err_msg = wl_obj.import_line(cr, uid, new_wl_id, vals, context=context)
                    if po_line in not_ok_file_lines:
                        wl_obj.write(cr, uid, [new_wl_id], {'type_change': 'error', 'error_msg': not_ok_file_lines[po_line]}, context=context)

                    line_n = vals[0] or False
                    if err_msg:
                        for err in err_msg:
                            if line_n:
                                err = 'Line %s of the PO: %s' % (line_n, err)
                            else:
                                err = 'Line %s of the file: %s' % (po_line, err)
                            values_line_errors.append(err)
                    # Commit modifications
                    cr.commit()

                # Lines to delete
                for po_line in SIMU_LINES[wiz.id]['line_ids']:
                    line_data = wl_obj.read(cr, uid, [po_line], ['type_change', 'in_uom'], context=context)[0]
                    if line_data['type_change'] != 'del':
                        wl_obj.write(cr, uid, po_line, {'type_change': 'ignore', 'imp_uom': line_data['in_uom']}, context=context)

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
                })
                self.write(cr, uid, [wiz.id], header_values, context=context)

            cr.commit()
            cr.close(True)

            # Clear the cache
            PRODUCT_CODE_ID = {}
            UOM_NAME_ID = {}
            CURRENCY_NAME_ID = {}
            SIMU_LINES = {}
        except Exception, e:
            logging.getLogger('po.simulation simulate').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e}, context=context)
            cr.commit()
            cr.close(True)

        return True

    def launch_import(self, cr, uid, ids, context=None, thread=True):
        '''
        Launch the simulation routine in background
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        active_wiz = self.browse(cr, uid, ids, fields_to_fetch=['state', 'order_id'], context=context)[0]

        # To prevent adding multiple lines by clicking multiple times on the import button
        if active_wiz.state != 'simu_done':
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'res_id': active_wiz.order_id.id,
                    'view_type': 'form',
                    'view_mode': 'form, tree',
                    'target': 'crush',
                    'context': context}

        self.write(cr, uid, ids, {'state': 'import_progress', 'percent_completed': 0.00}, context=context)
        for wiz in self.browse(cr, uid, ids, context=context):
            filename = wiz.filename.split('\\')[-1]
            self.pool.get('purchase.order.simu.import.file').create(cr, uid, {'order_id': wiz.order_id.id,
                                                                              'filename': filename,}, context=context)
        cr.commit()
        if thread:
            new_thread = threading.Thread(target=self.run_import, args=(cr.dbname, uid, ids, context))
            new_thread.start()
            new_thread.join(10.0)

            if new_thread.isAlive():
                return self.go_to_simulation(cr, uid, ids, context=context)
            else:
                return {'type': 'ir.actions.act_window',
                        'res_model': 'purchase.order',
                        'res_id': active_wiz.order_id.id,
                        'view_type': 'form',
                        'view_mode': 'form, tree',
                        'target': 'crush',
                        'context': context}
        else:
            self.run_import(cr.dbname, uid, ids, context)
            return True

    def run_import(self, dbname, uid, ids, context=None):
        '''
        Launch the real import
        '''
        line_obj = self.pool.get('wizard.import.po.simulation.screen.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        cr = pooler.get_db(dbname).cursor()

        try:
            for wiz in self.browse(cr, uid, ids, context=context):
                w_vals = {'state': 'import_progress',}
                self.write(cr, uid, [wiz.id], w_vals, context=context)

                """
                UFTP-59: import PO header
                20/Mar/14 2:51 PM was asked to import only:
                1)Supplier Ref, 2) RTS date, 3) Shipment date
                just uncomment the 3 other fields if asked later
                """
                po_vals = {
                    'partner_ref': wiz.imp_supplier_ref or wiz.in_supplier_ref,
                    'ready_to_ship_date': wiz.imp_ready_to_ship_date or wiz.in_ready_to_ship_date,
                    'shipment_date': wiz.imp_shipment_date or wiz.in_shipment_date,
                }
                self.pool.get('purchase.order').write(cr, uid, [wiz.order_id.id], po_vals, context=context)

                lines = [x.id for x in wiz.simu_line_ids]
                line_obj.update_po_line(cr, uid, lines, context=context)

            if ids:
                self.write(cr, uid, ids, {'state': 'done', 'percent_completed': 100.00}, context=context)
                res =self.go_to_simulation(cr, uid, [wiz.id], context=context)
            else:
                res = True

            cr.commit()
            cr.close(True)
        except Exception, e:
            logging.getLogger('po.simulation.run').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e}, context=context)
            res = True
            cr.commit()
            cr.close(True)

        return res

wizard_import_po_simulation_screen()


class wizard_import_po_simulation_screen_line(osv.osv):
    _name = 'wizard.import.po.simulation.screen.line'
    _order = 'is_new_line, in_line_number, in_ext_ref, in_product_id, id'
    _rec_name = 'in_line_number'

    def _get_line_info(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get values for each lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        delete_line_ids = self.search(cr, uid, [
            ('imp_comment', '=', '[DELETE]')
        ], context=context)
        delete_line_numbers = set()
        for x in self.read(cr, uid, delete_line_ids, ['in_line_number'], context=context):
            if x['in_line_number']:
                delete_line_numbers.add(x['in_line_number'])

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            chg = ''
            if line.type_change in ('warning', 'del', 'ignore'):
                chg = dict(self._columns['type_change'].selection).get(line.type_change) or ''
            elif line.chg_text:
                chg = line.chg_text
            elif line.type_change:
                chg = dict(self._columns['type_change'].selection).get(line.type_change) or ''
            res[line.id] = {'in_product_id': False,
                            'in_nomen': False,
                            'in_comment': False,
                            'in_qty': 0.00,
                            'in_uom': False,
                            'in_drd': False,
                            'in_dcd': False,
                            'in_price': 0.00,
                            'in_currency': False,
                            'in_ext_ref': False,
                            'imp_discrepancy': 0.00,
                            'change_ok': False,
                            'chg_text': chg
                            }

            if line.po_line_id:
                l = line.po_line_id
                res[line.id]['in_product_id'] = l.product_id and l.product_id.id or False
                res[line.id]['in_nomen'] = l.nomenclature_description
                res[line.id]['in_comment'] = l.comment
                res[line.id]['in_qty'] = l.product_qty
                res[line.id]['in_uom'] = l.product_uom and l.product_uom.id or False
                res[line.id]['in_drd'] = l.date_planned
                res[line.id]['in_dcd'] = l.confirmed_delivery_date
                res[line.id]['in_price'] = l.price_unit
                res[line.id]['in_currency'] = l.currency_id and l.currency_id.id or False
                res[line.id]['in_ext_ref'] = l.external_ref or False
                if line.type_change != '':
                    if line.imp_qty and line.imp_price:
                        disc = (line.imp_qty*line.imp_price)-(line.in_qty*line.in_price)
                        res[line.id]['imp_discrepancy'] = disc

                    prod_change = False
                    if res[line.id]['in_product_id'] and not line.imp_product_id or \
                            not res[line.id]['in_product_id'] and line.imp_product_id or \
                            res[line.id]['in_product_id'] != line.imp_product_id.id:
                        prod_change = True
                        if not line.chg_text and line.imp_product_id or (not line.imp_product_id and line.in_comment):
                            res[line.id]['chg_text'] += _('\nPROD')
                    qty_change = not(res[line.id]['in_qty'] == line.imp_qty)
                    if not line.chg_text and (line.imp_product_id or (not line.imp_product_id and line.in_comment)) \
                            and qty_change:
                        res[line.id]['chg_text'] += _('\nQTY')
                    price_change = not(res[line.id]['in_price'] == line.imp_price)
                    if not line.chg_text and (line.imp_product_id or (not line.imp_product_id and line.in_comment)) \
                            and price_change:
                        res[line.id]['chg_text'] += _('\nPRICE')
                    drd_change = not(res[line.id]['in_drd'] == line.imp_drd)
                    dcd_change = not(res[line.id]['in_dcd'] == line.imp_dcd)
                    to_delete = line.imp_comment == '[DELETE]'
                    if to_delete:
                        delete_line_numbers.add(line.in_line_number)

                    if line.simu_id.state != 'draft' and (prod_change or qty_change or price_change or drd_change or dcd_change or to_delete):
                        res[line.id]['change_ok'] = True
                elif line.type_change == 'del':
                    res[line.id]['imp_discrepancy'] = -(line.in_qty*line.in_price)
            else:
                res[line.id]['imp_discrepancy'] = line.imp_qty*line.imp_price
                if line.imp_uom:
                    res[line.id]['in_uom'] = line.imp_uom.id

            if line.type_change in ('warning', 'del', 'ignore'):
                res[line.id]['chg_text'] = dict(self._columns['type_change'].selection).get(line.type_change) or ''

        return res

    def _get_str_line_number(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the str of the line according to the line number or nothing
        if the line number is 0
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {}
            if line.in_line_number and line.in_line_number > 0:
                res[line.id]['str_in_line_number'] = line.in_line_number
                res[line.id]['is_new_line'] = 0
            else:
                res[line.id]['str_in_line_number'] = ''
                res[line.id]['is_new_line'] = 1

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
                                    type='char', size=1024, string='Nomenclature',
                                    readonly=True, store=True),
        'in_comment': fields.function(_get_line_info, method=True, multi='line',
                                      type='char', size=1024, string='Comment',
                                      readonly=True, store=True),
        'in_qty': fields.function(_get_line_info, method=True, multi='line',
                                  type='float', string='Qty',
                                  readonly=True, store=True, related_uom='in_uom'),
        'in_uom': fields.function(_get_line_info, method=True, multi='line',
                                  type='many2one', relation='product.uom', string='UoM',
                                  readonly=True, store=True),
        'in_drd': fields.function(_get_line_info, method=True, multi='line',
                                  type='date', string='Delivery Requested Date',
                                  readonly=True, store=True),
        'in_dcd': fields.function(_get_line_info, method=True, multi='line',
                                  type='date', string='Delivery Confirmed Date',
                                  readonly=True, store=True),
        'in_price': fields.function(_get_line_info, method=True, multi='line',
                                    type='float', string='Price Unit',
                                    readonly=True, store=True),
        'in_currency': fields.function(_get_line_info, method=True, multi='line',
                                       type='many2one', relation='res.currency', string='Currency',
                                       readonly=True, store=True),
        'in_line_number': fields.integer(string='Line', readonly=True),
        'str_in_line_number': fields.function(_get_str_line_number, method=True, string='Line',
                                              type='char', size=24, readonly=True, multi='new_line',
                                              store={'wizard.import.po.simulation.screen.line': (lambda self, cr, uid, ids, c={}: ids, ['in_line_number'], 20),}),
        'is_new_line': fields.function(_get_str_line_number, method=True, string='Is new line ?',
                                       type='boolean', readonly=True, multi='new_line',
                                       store={'wizard.import.po.simulation.screen.line': (lambda self, cr, uid, ids, c={}: ids, ['in_line_number'], 20),}),
        'in_ext_ref': fields.char(size=256, string='External Ref.', readonly=True),
        'type_change': fields.selection([('', ''), ('error', 'Error'), ('new', 'New'),
                                         ('split', 'Split'), ('del', 'Del'),
                                         ('ignore', 'Ignore'), ('warning', 'Warning')],
                                        string='Change type', readonly=True),
        'imp_product_id': fields.many2one('product.product', string='Product',
                                          readonly=True),
        'imp_qty': fields.float(digits=(16,2), string='Qty', readonly=True, related_uom='imp_uom'),
        'imp_uom': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_price': fields.float(digits=(16,2), string='Price Unit', readonly=True),
        'imp_discrepancy': fields.function(_get_line_info, method=True, multi='line',
                                           type='float', string='Discrepancy',
                                           store={'wizard.import.po.simulation.screen.line': (lambda self, cr, uid, ids, c={}: ids, ['imp_qty', 'imp_price', 'in_qty', 'in_price', 'type_change', 'po_line_id'], 20),}),
        'imp_currency': fields.many2one('res.currency', string='Currency', readonly=True),
        'imp_stock_take_date': fields.date(string='Stock Take Date', readonly=True),
        'imp_drd': fields.date(string='Delivery Requested Date', readonly=True),
        'imp_dcd': fields.date(string='Delivery Confirmed Date', readonly=True),
        'esc_conf': fields.boolean(string='ESC Confirmed', readonly=True),
        'imp_esc1': fields.char(size=256, string='Message ESC1', readonly=True),
        'imp_esc2': fields.char(size=256, string='Message ESC2', readonly=True),
        'imp_comment': fields.text(string='Comment', readonly=True),
        'imp_external_ref': fields.char(size=256, string='External Ref.', readonly=True),
        'imp_project_ref': fields.char(size=256, string='Project Ref.', readonly=True),
        'imp_origin': fields.char(size=256, string='Origin Ref.', readonly=True),
        'change_ok': fields.function(_get_line_info, method=True, multi='line',
                                     type='boolean', string='Change', store=False),
        'error_msg': fields.text(string='Error message', readonly=True),
        'parent_line_id': fields.many2one('wizard.import.po.simulation.screen.line',
                                          string='Parent line id',
                                          help='Use to split the good PO line',
                                          readonly=True),
        'chg_text': fields.function(_get_line_info, method=True, multi='line', type='char', size=216, string='CHG',
                                    readonly=True, store=True),
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

    def import_line(self, cr, uid, ids, values, context=None):
        '''
        Write the line with the values
        '''
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        sale_obj = self.pool.get('sale.order')

        if isinstance(ids, (int, long)):
            ids = [ids]

        errors = []

        for line in self.browse(cr, uid, ids, context=context):
            write_vals = {}

            # Comment
            write_vals['imp_comment'] = values[15] and values[15].strip()

            if line.po_line_id.state in ('confirmed', 'done') or ( line.po_line_id.state in  ('cancel', 'cancel_r') and write_vals['imp_comment'] != '[DELETE]'):
                write_vals['type_change'] = 'error'
                errors.append(_('PO line has been confirmed or cancelled and consequently is not editable'))


            # External Ref.
            write_vals['imp_external_ref'] = values[1]
            pol_ids = None
            if line.in_line_number:
                pol_ids = self.pool.get('purchase.order.line').search(cr, uid, [('order_id', '=', line.simu_id.order_id.id), ('line_number', '=', line.in_line_number)], context=context)
                if not pol_ids and not (write_vals['imp_comment'] and write_vals['imp_comment'] == '[DELETE]'):
                    errors.append(_('Line no is not consistent with validated PO.'))
                    write_vals['in_line_number'] = False
                    write_vals['type_change'] = 'warning'

            if (write_vals['imp_comment'] and write_vals['imp_comment'] == '[DELETE]'):
                if not pol_ids:
                    write_vals['type_change'] = 'warning'
                    if line.in_line_number:
                        errors.append(_('The import file is inconsistent. Line no. %s is not existing or was previously deleted') % line.in_line_number)
                    else:
                        errors.append(_('The import file is inconsistent. The matching line is not existing or was previously deleted'))
                else:
                    if line.po_line_id.state in ('validated', 'validated_n'):
                        write_vals['type_change'] = 'del'
                        if line.in_line_number:
                            to_delete = self.search(cr, uid, [
                                ('simu_id', '=', line.simu_id.id),
                                ('in_line_number', '=', line.in_line_number),
                            ], context=context)
                            self.write(cr, uid, to_delete, {'type_change': 'del'}, context=context)
                    else:
                        write_vals['type_change'] = 'ignore'

            if not line.in_line_number and not write_vals.get('imp_external_ref'):
                errors.append(_('The line should have a Line no. or an Ext Ref.'))
                write_vals['in_line_number'] = False
                write_vals['imp_external_ref'] = False
                write_vals['type_change'] = 'error'

            # Product
            if (values[2] and values[2] == line.in_product_id.default_code):
                write_vals['imp_product_id'] = line.in_product_id and line.in_product_id.id or False
            else:
                prod_id = False
                if values[2]:
                    prod_id = PRODUCT_CODE_ID.get(values[2])

                if not prod_id and values[2]:
                    prod_ids = prod_obj.search(cr, uid, [('default_code', '=', values[2])], context=context)
                    if not prod_ids:
                        write_vals['type_change'] = 'error'
                        errors.append(_('Product %s not found in database') % values[2])
                    else:
                        write_vals['imp_product_id'] = prod_ids[0]
                else:
                    write_vals['imp_product_id'] = prod_id
                    if not prod_id:
                        write_vals['type_change'] = 'error'

            # Qty
            err_msg = _('Incorrect float value for field \'Product Qty\'')
            try:
                qty = float(values[4])
                write_vals['imp_qty'] = qty
            except Exception:
                errors.append(err_msg)
                write_vals['type_change'] = 'error'
                write_vals['imp_qty'] = 0.00

            # UoM
            uom_value = values[5]
            if tools.ustr(uom_value) == line.in_uom.name:
                write_vals['imp_uom'] = line.in_uom.id
            else:
                uom_id = UOM_NAME_ID.get(tools.ustr(uom_value))
                if not uom_id:
                    uom_ids = uom_obj.search(cr, uid, [('name', '=', tools.ustr(uom_value))], context=context)
                    if uom_ids:
                        write_vals['imp_uom'] = uom_ids[0]
                    else:
                        errors.append(_('UoM not found in database.'))
                        write_vals['imp_uom'] = False
                        write_vals['type_change'] = 'error'
                else:
                    write_vals['imp_uom'] = uom_id

            if write_vals.get('imp_uom') and write_vals.get('imp_product_id') and \
                    (write_vals['imp_uom'] != line.in_uom.id or write_vals['imp_product_id'] != line.in_product_id.id):
                # Check if the UoM is compatible with the Product
                new_uom_categ = uom_obj.browse(cr, uid, write_vals['imp_uom'], context=context).category_id.id
                prod_uom_categ = prod_obj.browse(cr, uid, write_vals['imp_product_id'], context=context).uom_id.category_id.id
                if new_uom_categ != prod_uom_categ:
                    errors.append(_('The new UoM is not compatible with the product UoM.'))
                    write_vals['type_change'] = 'error'

            # Unit price
            err_msg = _('Incorrect float value for field \'Price Unit\'')
            try:
                unit_price = float(values[6])
                write_vals['imp_price'] = unit_price
            except Exception:
                errors.append(err_msg)
                write_vals['type_change'] = 'error'
                write_vals['imp_price'] = 0.00

            # Check unit price * quantity
            err_msg = _('The price subtotal must be greater than or equal to 0.01')
            if line.simu_id and line.simu_id.order_id and line.simu_id.order_id.order_type == 'regular' and write_vals['imp_price'] and write_vals['imp_qty']:
                if write_vals['imp_price'] * write_vals['imp_qty'] < 0.01:
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'

            # Currency
            currency_value = values[7]
            if tools.ustr(currency_value) == line.in_currency.name:
                write_vals['imp_currency'] = line.in_currency.id
            elif line.in_currency.name:
                err_msg = _('The currency on the file is not the same as the currency of the PO line - You must have the same currency on both side - Currency of the initial line kept.')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # Origin
            write_vals['imp_origin'] = values[8]
            if line.simu_id.order_id.po_from_fo and not values[8]:
                err_msg = _('The Origin is mandatory for a PO coming from a FO')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'
            elif line.simu_id.order_id.po_from_fo:
                fo_ids = self.pool.get('sale.order').search(cr, uid,
                                                            [('name', '=', values[8]),
                                                             ('procurement_request', '=', False)], context=context)
                ir_ids = self.pool.get('sale.order').search(cr, uid,
                                                            [('name', '=', values[8]),
                                                             ('procurement_request', '=', True)], context=context)
                if not fo_ids and not ir_ids:
                    err_msg = _('The FO reference in \'Origin\' is not consistent with this PO')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'

            # Stock Take Date
            stock_take_date = values[9]
            if stock_take_date and type(stock_take_date) == type(DateTime.now()):
                write_vals['imp_stock_take_date'] = stock_take_date.strftime('%Y-%m-%d')
            elif stock_take_date and isinstance(stock_take_date, str):
                try:
                    time.strptime(stock_take_date, '%Y-%m-%d')
                    write_vals['imp_stock_take_date'] = stock_take_date
                except ValueError:
                    err_msg = _('Incorrect date value for field \'Stock Take Date\'')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
            elif stock_take_date:
                err_msg = _('Incorrect date value for field \'Stock Take Date\'')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # Delivery Requested Date
            drd_value = values[10]
            if drd_value and type(drd_value) == type(DateTime.now()):
                write_vals['imp_drd'] = drd_value.strftime('%Y-%m-%d')
            elif drd_value and isinstance(drd_value, str):
                try:
                    time.strptime(drd_value, '%Y-%m-%d')
                    write_vals['imp_drd'] = drd_value
                except ValueError:
                    err_msg = _('Incorrect date value for field \'Delivery Requested Date\'')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
            elif drd_value:
                err_msg = _('Incorrect date value for field \'Delivery Requested Date\'')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # Delivery Confirmed Date
            dcd_value = values[11]
            if dcd_value and type(dcd_value) == type(DateTime.now()):
                write_vals['imp_dcd'] = dcd_value.strftime('%Y-%m-%d')
            elif dcd_value and isinstance(dcd_value, str):
                try:
                    time.strptime(dcd_value, '%Y-%m-%d')
                    write_vals['imp_dcd'] = dcd_value
                except ValueError:
                    err_msg = _('Incorrect date value for field \'Delivery Confirmed Date\'')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
            elif dcd_value:
                err_msg = _('Incorrect date value for field \'Delivery Confirmed Date\'')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # ESC Confirmed
            if write_vals.get('imp_dcd') and line.simu_id.order_id.partner_type == 'esc':
                write_vals['esc_conf'] = True

            # Project Ref.
            proj_ref = values[17]
            if proj_ref:
                so_ids = sale_obj.search(cr, uid, [('name', 'ilike', proj_ref), ('procurement_request', 'in', ['t', 'f'])],
                                         limit=1, context=context)
                if so_ids:
                    so_state = sale_obj.browse(cr, uid, so_ids[0], fields_to_fetch=['state'], context=context).state
                    if so_state in ('draft', 'draft_p', 'validated', 'validated_p', 'sourced', 'sourced_p'):
                        write_vals['imp_project_ref'] = values[17]
                    else:
                        err_msg = _('\'Project Ref\' Document can\'t be Confirmed, Closed or Cancelled')
                        errors.append(err_msg)
                        write_vals['type_change'] = 'error'
                else:
                    err_msg = _('The Reference in \'Project Ref\' was not found')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'

            # Message ESC1
            write_vals['imp_esc1'] = values[18]
            # Message ESC2
            write_vals['imp_esc2'] = values[19]

            if line.error_msg:
                write_vals['type_change'] = 'error'

            if write_vals.get('type_change') in ['error', 'warning']:
                err_msg = line.error_msg or ''
                for err in errors:
                    if err_msg:
                        err_msg += ' - '
                    err_msg += err
                write_vals['error_msg'] = err_msg

            self.write(cr, uid, [line.id], write_vals, context=context)

        return errors

    def update_po_line(self, cr, uid, ids, context=None):
        '''
        Update the corresponding PO lines with the imported values
        according to the change type
        '''
        line_obj = self.pool.get('purchase.order.line')
        split_obj = self.pool.get('split.purchase.order.line.wizard')
        simu_obj = self.pool.get('wizard.import.po.simulation.screen')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        nb_lines = float(len(ids))
        line_treated = 0.00
        percent_completed = 0.00
        for line in self.browse(cr, uid, ids, context=context):
            context['purchase_id'] = line.simu_id.order_id.id
            line_treated += 1
            percent_completed = int(float(line_treated) / float(nb_lines) * 100)
            if line.po_line_id and line.type_change != 'ignore' and not line.change_ok and not line.imp_external_ref and not line.imp_project_ref and not line.imp_origin:
                continue
            if line.type_change in ('ignore', 'error'):
                if line.type_change == 'error':
                    job_comment = context.get('job_comment', [])
                    job_comment.append({
                        'res_model': 'purchase.order',
                        'res_id': line.simu_id.order_id.id,
                        'msg': _('%s: error on line %s %s') % (line.simu_id.order_id.name, line.in_line_number or line.imp_external_ref, line.error_msg),
                    })
                    context['job_comment'] = job_comment
                continue

            if line.type_change == 'del' and line.po_line_id:
                wf_service.trg_validate(uid, 'purchase.order.line', line.po_line_id.id, 'cancel', cr)
            elif line.type_change == 'split' and line.parent_line_id:
                # Call the split line wizard
                po_line_id = False
                if line.parent_line_id and line.parent_line_id.po_line_id:
                    po_line_id = line.parent_line_id.po_line_id.id

                    new_product_split = False
                    if line.in_qty == 0 and \
                            not line.in_product_id and line.imp_product_id and \
                            line.imp_product_id.id != line.in_product_id.id:

                        # UF-2337: we could enter a case where the import file
                        # slit with a new product (like if we manually split
                        # then after change product of the splited line)
                        new_product_split = True
                    else:
                        # REF-97: Fixed the wrong quantity for the original line
                        # which got split
                        context['from_simu_screen'] = True
                        split_id = split_obj.create(cr, uid, {
                            'purchase_line_id': po_line_id,
                            'original_qty': line.parent_line_id.in_qty,
                            'new_line_qty': line.imp_qty
                        }, context=context)

                        new_po_line_id = split_obj.split_line(cr, uid, split_id,
                                                              context=context)
                        context['from_simu_screen'] = False
                    if not new_product_split and not new_po_line_id:
                        continue  # split line has failed or case not to be done

                    line_vals = {'product_uom': line.imp_uom.id,
                                 'product_id': line.imp_product_id.id,
                                 'price_unit': line.imp_price,
                                 'is_line_split': True,
                                 }
                    if line.imp_drd:
                        line_vals['date_planned'] = line.imp_drd
                    if line.imp_project_ref:
                        line_vals['project_ref'] = line.imp_project_ref
                    if line.imp_origin:
                        line_vals['origin'] = line.imp_origin
                    if line.imp_external_ref:
                        line_vals['external_ref'] = line.imp_external_ref
                    if line.imp_stock_take_date:
                        line_vals['stock_take_date'] = line.imp_stock_take_date,

                    # UF-2537 after split reinject import qty computed in
                    # simu for import consistency versus simu
                    # (or set qty of a new product split line)
                    line_vals['product_qty'] = line.imp_qty

                    if new_product_split:
                        line_vals.update({
                            'order_id': line.simu_id.order_id.id,
                            'line_number': line.in_line_number,
                            'confirmed_delivery_date': line.imp_dcd or False,
                            'esc_confirmed': True if line.imp_dcd else False,
                            'original_line_id': line.parent_line_id.po_line_id.id,
                        })
                        if line.parent_line_id.po_line_id.analytic_distribution_id:
                            line_vals.update({
                                'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid, line.parent_line_id.po_line_id.analytic_distribution_id.id, {}, context=context),
                            })
                        if line.parent_line_id.po_line_id.stock_take_date:
                            line_vals['stock_take_date'] = line.parent_line_id.po_line_id.stock_take_date
                        split_line_id = line_obj.create(cr, uid, line_vals, context=context)
                        wf_service.trg_validate(uid, 'purchase.order.line', split_line_id, 'validated', cr)
                        if line.parent_line_id.po_line_id.linked_sol_id:
                            line_obj.update_fo_lines(cr, uid, line.parent_line_id.po_line_id.id, context=context)
                    else:
                        if line.imp_dcd:
                            line_vals['confirmed_delivery_date'] = line.imp_dcd
                            line_vals['esc_confirmed'] = line.esc_conf
                        line_obj.write(cr, uid, [new_po_line_id], line_vals,
                                       context=context)

                    # UF-2537 after split reinject ORIGINAL line import qty
                    # computed in simu for import consistency versus simu
                    # note: if total qty of splited lines is > to original qty
                    # the original line qty was truncated in term of qty
                    # (never be greater than line.parent_line_id.in_qty)
                    line_vals = {
                        'product_qty': line.parent_line_id.imp_qty,
                    }
                    line_obj.write(cr, uid, [line.parent_line_id.po_line_id.id],
                                   line_vals, context=context)

                    job_comment = context.get('job_comment', [])
                    job_comment.append({
                        'res_model': 'purchase.order',
                        'res_id': line.simu_id.order_id.id,
                        'msg': _('%s: Line #%s has been split.') % (line.simu_id.order_id.name, line.parent_line_id.po_line_id.line_number),
                    })
                    context['job_comment'] = job_comment
            elif line.type_change == 'new':
                line_vals = {'order_id': line.simu_id.order_id.id,
                             'product_id': line.imp_product_id.id,
                             'product_uom': line.imp_uom.id,
                             'price_unit': line.imp_price,
                             'product_qty': line.imp_qty,
                             'date_planned': line.imp_drd or line.simu_id.order_id.delivery_requested_date,
                             'set_as_validated_n': True,
                             'display_sync_ref': True,
                             'created_by_vi_import': True,
                             }
                if line.imp_stock_take_date:
                    line_vals['stock_take_date'] = line.imp_stock_take_date,
                if line.imp_dcd:
                    line_vals['confirmed_delivery_date'] = line.imp_dcd
                if line.imp_project_ref:
                    line_vals['project_ref'] = line.imp_project_ref
                if line.imp_origin:
                    line_vals['origin'] = line.imp_origin
                if line.imp_external_ref:
                    line_vals['external_ref'] = line.imp_external_ref
                if line.esc_conf:
                    line_vals['esc_confirmed'] = line.esc_conf
                new_line_id = line_obj.create(cr, uid, line_vals, context=context)
                new_line_numb = line_obj.read(cr, uid, new_line_id, ['line_number'], context=context)['line_number']
                job_comment = context.get('job_comment', [])
                job_comment.append({
                    'res_model': 'purchase.order',
                    'res_id': line.simu_id.order_id.id,
                    'msg': _('%s: New line #%s created.') % (line.simu_id.order_id.name, new_line_numb),
                })
                context['job_comment'] = job_comment
            elif line.po_line_id:
                line_vals = {'product_id': line.imp_product_id.id,
                             'product_uom': line.imp_uom.id,
                             'price_unit': line.imp_price,
                             'product_qty': line.imp_qty,
                             }
                if line.imp_drd:
                    line_vals['date_planned'] = line.imp_drd
                if line.imp_dcd:
                    line_vals['confirmed_delivery_date'] = line.imp_dcd
                if line.imp_project_ref:
                    line_vals['project_ref'] = line.imp_project_ref
                if line.imp_origin:
                    line_vals['origin'] = line.imp_origin
                if line.imp_external_ref:
                    line_vals['external_ref'] = line.imp_external_ref
                if line.esc_conf:
                    line_vals['esc_confirmed'] = line.esc_conf
                if context.get('auto_import_ok') and line.simu_id.order_id.stock_take_date:
                    line_vals['stock_take_date'] = line.simu_id.order_id.stock_take_date

                line_obj.write(cr, uid, [line.po_line_id.id], line_vals, context=context)
            simu_obj.write(cr, uid, [line.simu_id.id], {'percent_completed': percent_completed}, context=context)
            # Commit modifications
            cr.commit()

        if ids:
            return simu_obj.go_to_simulation(cr, uid, line.simu_id.id, context=context)

        return True


wizard_import_po_simulation_screen_line()
