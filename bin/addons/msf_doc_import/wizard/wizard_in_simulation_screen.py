# -*- coding: utf-8 -*-

# Module imports
import base64
from datetime import datetime
import threading
import time
import logging

from osv import fields
from osv import osv
import pooler
from tools.translate import _
import tools
import traceback

from msf_order_date import TRANSPORT_TYPE
from msf_outgoing import INTEGRITY_STATUS_SELECTION
from msf_outgoing import PACK_INTEGRITY_STATUS_SELECTION
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import xml.etree.ElementTree as ET

# Server imports
# Addons imports
NB_OF_HEADER_LINES = 7


PRODUCT_CODE_ID = {}
UOM_NAME_ID = {}
CURRENCY_NAME_ID = {}
PRODLOT_NAME_ID = {}

SIMU_LINES = {}
LN_BY_EXT_REF = {}


LINES_COLUMNS = [
    (_('Line number*'), 'line_number', '', 'int'),
    (_('Ext. Reference'), 'external_ref', '', 'string'),
    (_('Product Code*'), 'product_code', 'mandatory', 'string'),
    (_('Product Description'), 'product_name', '', 'string'),
    (_('Product Qty*'), 'product_qty', 'mandatory', 'float'),
    (_('Product UoM'), 'product_uom', 'mandatory', 'string'),
    (_('Price Unit'), 'price_unit', 'mandatory', 'float'),
    (_('Currency'), 'price_currency_id', 'mandatory', 'string'),
    (_('Batch'), 'prodlot_id', '', 'string'),
    (_('Expiry Date'), 'expired_date', '', 'date'),
    (_('ESC message 1'), 'message_esc1', '', 'string'),
    (_('ESC message 2'), 'message_esc2', '', 'string'),
]


HEADER_COLUMNS = [
    (1, _('Freight'), 'optionnal'),
    (2, _('Picking Reference'), 'optionnal'),
    (1, _('Origin'), 'mandatory'),
    (4, _('Supplier'), 'optionnal'),
    (5, _('Transport mode'), 'optionnal'),
    (6, _('Notes'), 'optionnal'),
    (7, _('Message ESC'), 'optionnal'),
]

PACK_HEADER = [
    ('', '', '', ''),
    (_('Qty of parcels*'), 'parcel_qty', '', ''),
    (_('From parcel*'), 'parcel_from', 'mandatory', 'int'),
    (_('To parcel*'), 'parcel_to', 'mandatory', 'int'),
    (_('Weight*'), 'total_weight', '', 'float'),
    (_('Volume'), 'total_volume', '', 'float'),
    (_('Height'), 'total_height', '', 'float', 10),
    (_('Length'), 'total_length', '', 'float', 10),
    (_('Width'), 'total_width', '', 'float', 10),
    (_('Packing List'), 'packing_list', '', ''),
    (_('ESC Message 1'), 'message_esc1', '', ''),
    (_('ESC Message 2'), 'message_esc2', '', ''),
]

pack_header = [x[1] for x in PACK_HEADER if x[0]]
pack_header_mandatory = [x[1] for x in PACK_HEADER if x[2] == 'mandatory']
pack_coeff = dict((x[1], x[4]) for x in PACK_HEADER if len(x) == 5)

class wizard_import_in_simulation_screen(osv.osv):
    _name = 'wizard.import.in.simulation.screen'
    _rec_name = 'picking_id'

    def _get_related_values(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get the values related to the picking
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for simu in self.browse(cr, uid, ids, context=context):
            res[simu.id] = {'origin': simu.picking_id.origin,
                            'creation_date': simu.picking_id.date,
                            'purchase_id': simu.picking_id.purchase_id and simu.picking_id.purchase_id.id or False,
                            'backorder_id': simu.picking_id.backorder_id and simu.picking_id.backorder_id.id or False,
                            'header_notes': simu.picking_id.note,
                            'freight_number': simu.picking_id.shipment_ref,
                            'transport_type': simu.picking_id and simu.picking_id.purchase_id and simu.picking_id.purchase_id.transport_type or False}

        return res

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Incoming shipment', required=True, readonly=True),
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
        # File information
        'file_to_import': fields.binary(string='File to import'),
        'filename': fields.char(size=64, string='Filename'),
        'filetype': fields.selection([('excel', 'Excel file'),
                                      ('xml', 'XML file')], string='Type of file',
                                     required=True),
        'error_file': fields.binary(string='File with errors'),
        'error_filename': fields.char(size=64, string='Lines with errors'),
        'nb_file_lines': fields.integer(string='Total of file lines',
                                        readonly=True),
        'extra_info': fields.text('Extra Info'),
        'nb_treated_lines': fields.integer(string='Nb treated lines',
                                           readonly=True),
        'percent_completed': fields.float(string='Percent completed',
                                          readonly=True),
        'import_error_ok': fields.boolean(string='Error at import'),
        # Related fields
        'origin': fields.function(_get_related_values, method=True, string='Origin',
                                  readonly=True, type='char', size=512, multi='related'),
        'creation_date': fields.function(_get_related_values, method=True, string='Creation date',
                                         readonly=True, type='datetime', multi='related'),
        'purchase_id': fields.function(_get_related_values, method=True, string='Purchase Order',
                                       readonly=True, type='many2one', relation='purchase.order', multi='related'),
        'backorder_id': fields.function(_get_related_values, method=True, string='Back Order Of',
                                        readonly=True, type='many2one', relation='stock.picking', multi='related'),
        'header_notes': fields.function(_get_related_values, method=True, string='Header notes',
                                        readonly=True, type='text', multi='related'),
        'freight_number': fields.function(_get_related_values, method=True, string='Freight number',
                                          readonly=True, type='char', size=128, multi='related'),
        'transport_type': fields.function(_get_related_values, method=True, string='Transport mode',
                                          readonly=True, type='selection', selection=TRANSPORT_TYPE, multi='related'),
        # Import fields
        'imp_notes': fields.text(string='Notes', readonly=True),
        'message_esc': fields.text(string='Message ESC', readonly=True),
        'imp_origin': fields.char(size=128, string='Origin', readonly=True),
        'imp_freight_number': fields.char(size=128, string='Freight number', readonly=True),
        'imp_transport_type': fields.char(string='Transport mode', size=128, readonly=True),
        # Lines
        'line_ids': fields.one2many('wizard.import.in.line.simulation.screen', 'simu_id', string='Stock moves'),
        'with_pack': fields.boolean('With Pack Info'),
        'pack_found': fields.boolean('Pack Found'),
        'physical_reception_date': fields.datetime('Physical Reception Date'),

    }

    _defaults = {
        'state': 'draft',
        'filetype': 'excel',
        'with_pack': False,
        'pack_found': False,
        'physical_reception_date': False,
    }

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Remove the concurrency access warning
        '''
        if not ids:
            return True
        if context is None:
            context = {}

        buttons = ['return_to_in',
                   'go_to_simulation',
                   'print_simulation_report',
                   'launch_import',
                   'simulate']
        if context.get('button') in buttons:
            return True

        return super(wizard_import_in_simulation_screen, self).write(cr, uid, ids, vals, context=context)

    def return_to_in(self, cr, uid, ids, context=None):
        '''
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        picking_id = self.browse(cr, uid, ids[0], context=context).picking_id.id
        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'stock.action_picking_tree4', ['form', 'tree'], context=context)
        res['res_id'] = picking_id
        return res

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Reload the simulation screen
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        data =  {'type': 'ir.actions.act_window',
                 'res_model': self._name,
                 'res_id': ids[0],
                 'view_type': 'form',
                 'view_mode': 'form',
                 'target': 'same'}

        if self.read(cr, uid, ids[0], ['with_pack'])['with_pack']:
            data['name'] = _('Incoming shipment simulation screen (pick and pack mode)')

        return data

    def print_simulation_report(self, cr, uid, ids, context=None):
        '''
        Print the Excel report of the simulation
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        datas = {}
        datas['ids'] = ids
        report_name = 'in.simulation.screen.xls'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'context': context,
        }

    def launch_import(self, cr, uid, ids, context=None, with_ppl=False):
        '''
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        return self._import(cr, uid, ids, context=context, with_ppl=with_ppl)

    def launch_import_pack(self, cr, uid, ids, context=None):
        return self.launch_import(cr, uid, ids, context, with_ppl=True)

    def populate(self, cr, uid, import_id, picking_id, context=None):
        if context is None:
            context = {}

        pick_obj = self.pool.get('stock.picking')
        line_obj = self.pool.get('wizard.import.in.line.simulation.screen')

        for move in pick_obj.browse(cr, uid, picking_id, context=context).move_lines:
            if move.state not in ('draft', 'cancel', 'done'):
                line_obj.create(cr, uid, {
                    'move_id': move.id,
                    'initial_move_id': move.id,
                    'simu_id': import_id,
                    'move_product_id': move.product_id and move.product_id.id or False,
                    'move_product_qty': move.product_qty or 0.00,
                    'move_uom_id': move.product_uom and move.product_uom.id or False,
                    'move_price_unit': move.price_unit or move.product_id.standard_price,
                    'move_currency_id': move.price_currency_id and move.price_currency_id.id or False,
                    'line_number': move.line_number,
                    'external_ref': move.purchase_line_id and move.purchase_line_id.external_ref or False,
                }, context=context)

        return True

    def launch_simulate(self, cr, uid, ids, context=None):
        '''
        Launch the simulation routine in background
        '''
        global SIMU_LINES, LN_BY_EXT_REF
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if not wiz.file_to_import:
                raise osv.except_osv(
                    _('Error'),
                    _('Please select a file to import !'),
                )
            if wiz.filetype == 'excel':
                xml_file = base64.b64decode(wiz.file_to_import)
                excel_file = SpreadsheetXML(xmlstring=xml_file)
                if not excel_file.getWorksheets():
                    raise osv.except_osv(_('Error'), _('The given file is not a valid Excel 2003 Spreadsheet file !'))
            else:
                xml_file = base64.b64decode(wiz.file_to_import)
                try:
                    root = ET.fromstring(xml_file)
                except ET.ParseError:
                    raise osv.except_osv(_('Error'), _('The given file is not a valid XML file !'))
                if root.tag != 'data':
                    raise osv.except_osv(_('Error'), _('The given file is not a valid XML file !'))

            self.pool.get('wizard.import.in.line.simulation.screen').unlink(cr, uid, [line.id for line in wiz.line_ids],
                                                                            context=context)
            self.write(cr, uid, ids, {'state': 'simu_progress', 'error_filename': False, 'error_file': False,
                                      'percent_completed': 0, 'import_error_ok': False}, context=context)
            if wiz.id in SIMU_LINES:
                del SIMU_LINES[wiz.id]
            if wiz.id in LN_BY_EXT_REF:
                del LN_BY_EXT_REF[wiz.id]

            self.populate(cr, uid, wiz.id, wiz.picking_id.id, context=context)
            cr.commit()
            if context.get('do_not_import_with_thread'):
                self.simulate(cr.dbname, uid, ids, context=context)
            else:
                new_thread = threading.Thread(target=self.simulate, args=(cr.dbname, uid, ids, context))
                new_thread.start()
                new_thread.join(10.0)

            return self.go_to_simulation(cr, uid, ids, context=context)

    def get_values_from_xml(self, cr, uid, file_to_import, with_pack=False, context=None):
        '''
        Read the XML file and put data in values
        '''
        values = {}
        # Read the XML file
        xml_file = context.get('xml_is_string', False) and file_to_import or base64.b64decode(file_to_import)
        error = []

        root = ET.fromstring(xml_file)
        if root.tag != 'data':
            return values

        records = []
        rec = False

        index = 0
        for record in root:
            if record.tag == 'record':
                records.append(record)

        if len(records) > 0:
            rec = records[0]



        for node in rec.findall('field'):
            if node.attrib['name'] != 'move_lines':
                index += 1
                if len(node):
                    node = node[0]
                values[index] = [node.attrib['name'], node.text or '']
            else:
                nb_pack = 0
                nb_line = 0
                for record in node.findall('record'):
                    nb_pack = +1
                    # record is a pack info
                    index += 1
                    values[index] = pack_header
                    index += 1
                    values[index] = dict((x, False) for x in pack_header)
                    for pack_data_node in record.findall('field'):
                        if with_pack:
                            if pack_data_node.attrib['name'] not in pack_header:
                                error.append(_('Pack record node %s, wrong attribute %s') % (nb_pack, pack_data_node.attrib['name']))
                            values[index][pack_data_node.attrib['name']]= pack_data_node.text and pack_data_node.text.strip() or False
                    if with_pack:
                        for x in PACK_HEADER:
                            if x[2] == 'mandatory' and not values[index][x[1]]:
                                error.append(_('Pack record node %s, no value for mandatory attribute %s')% (nb_pack,x[1]))
                            elif x[3] == 'int' and values[index][x[1]]:
                                try:
                                    int(values[index][x[1]])
                                except:
                                    error.append(_('Pack record node %s, field %s, integer expected, found %s') % (nb_pack, x[1], values[index][x[1]]))
                            elif x[3] == 'float' and values[index][x[1]]:
                                try:
                                    float(values[index][x[1]])
                                except:
                                    error.append(_('Pack record node %s, field %s, float expected, found %s') % (nb_pack, x[1], values[index][x[1]]))

                    index += 1
                    values[index] = [x[1] for x in LINES_COLUMNS]

                    for subrecord in record.findall('record'):
                        index += 1
                        nb_line += 1
                        values[index] = dict((x[1], False) for x in LINES_COLUMNS)
                        for field_info in subrecord.findall('field'):
                            if len(field_info) == 1:
                                field_info[0].attrib['name'] = field_info.attrib['name']
                                field_info = [field_info[0]]
                            elif not len(field_info):
                                field_info = [field_info]
                            for f in field_info:
                                if f.attrib['name'] not in [x[1] for x in LINES_COLUMNS]:
                                    error.append(_('Pack record node %s, line %s, attribute %s unknown') % (nb_pack, nb_line, f.attrib['name']))

                                values[index][f.attrib['name']] = f.text or ''

                        for column in LINES_COLUMNS:
                            if column[2] == 'mandatory' and not values[index].get(column[1]):
                                error.append(_('Pack record node %s, line %s, data %s is mandatory') % (nb_pack, nb_line, column[1]))

        return values, nb_line, error

    def get_values_from_excel(self, cr, uid, file_to_import, with_pack=False, context=None):
        '''
        Read the Excel XML file and put data in values
        '''
        values = {}
        # Read the XML Excel file
        xml_file = context.get('xml_is_string', False) and file_to_import or base64.b64decode(file_to_import)
        fileobj = SpreadsheetXML(xmlstring=xml_file)

        # Read all lines
        rows = fileobj.getRows()

        error = []
        nb_pack = 0
        nb_line = 0

        process_pack_header = False
        process_pack_line = False
        process_move_line = False
        is_line = False
        # Get values per line
        index = 0
        for row in rows:
            index += 1
            values.setdefault(index, [])
            if len(row) > 2 and row[1] and row[1].data and (row[1].data == PACK_HEADER[1][0] or
                                                            (row[1].type == 'str' and row[1].data.lower() == PACK_HEADER[1][0].lower())):
                # this line is for pack header
                nb_pack += 1
                for nb, x in enumerate(PACK_HEADER):
                    if x[0] and (not row.cells[nb].data or row.cells[nb].type != 'str' or row.cells[nb].data.lower() != x[0].lower()):
                        error.append(_('Line %s, column %s, expected %s, found %s') % (index, nb+1, x[0], row.cells[nb]))
                    # replace user sting by key
                    row.cells[nb].data = x[1]
                process_pack_header = True
                process_pack_line = False
                process_move_line = False
                is_line = False
            elif process_pack_header:
                # previous line was pack header, so current line is pack data
                process_pack_header = False
                process_pack_line = True
                process_move_line = False
                for nb, x in enumerate(PACK_HEADER):
                    if x[1] in pack_header_mandatory and not row.cells[nb]:
                        error.append(_('Line %s, column %s, value %s is mandatory') % (index, nb+1, x[0]))
                    if row.cells[nb].data and x[3] == 'int':
                        try:
                            int(row.cells[nb].data)
                        except:
                            error.append(_('Line %s, column %s, integer expected, found %s') % (index, nb+1, row.cells[nb].data))
                    elif row.cells[nb].data and x[3] == 'float':
                        try:
                            float(row.cells[nb].data)
                        except:
                            error.append(_('Line %s, column %s, float expected, found %s') % (index, nb+1, row.cells[nb].data))

            elif process_pack_line:
                # previous line was pack data so current line must be move line header
                process_pack_line = False
                process_move_line = True
                for nb, x in enumerate(LINES_COLUMNS):
                    if not row.cells[nb].data or row.cells[nb].type != 'str' or x[0].lower() != row.cells[nb].data.lower():
                        error.append(_('Line %s, column %s, line header expected, found %s, expected: %s') % (index, nb+1, row.cells[nb], x[0]))
                    row.cells[nb].data = x[1]
            elif process_move_line:
                is_line = True
                # this line is a move line data
                nb_line += 1
                for nb, x in enumerate(LINES_COLUMNS):
                    if x[1] == 'line_number' and row.cells[nb].data:
                        try:
                            int(row.cells[nb].data)
                        except:
                            error.append(_('Line %s, column %s, line number expected, found %s, expected: integer value') % (index, nb+1, row.cells[nb]))
                    if x[2] == 'mandatory' and not row.cells[nb]:
                        error.append(_('Line %s, column %s, value %s is mandatory') % (index, nb+1, x[0]))

            if is_line or process_pack_line:
                values[index] = {}
            for cell_nb in range(len(row)):
                try:
                    cell_data = row.cells and row.cells[cell_nb] and \
                        row.cells[cell_nb].data
                    if is_line:
                        if cell_data and LINES_COLUMNS[cell_nb][3] == 'string':
                            cell_data = '%s' % cell_data
                        values[index][LINES_COLUMNS[cell_nb][1]] = cell_data
                    elif process_pack_line:
                        values[index][PACK_HEADER[cell_nb][1]] = cell_data
                    else:
                        values[index].append(cell_data)
                except ValueError as e:
                    raise osv.except_osv(_('Error'), _('Line %s of the imported file, \
the date has a wrong format: %s') % (index+1, str(e)))
                except IndexError:
                    raise osv.except_osv(_('Error'), _("Line %s of the imported file, extra column found (%s cols found)\n-- %s") % (index+1, len(row), tools.ustr(traceback.format_exc())))

        return values, nb_line, error

    def error_pick_already_processed(self, cr, uid, sol_id_sum, sol_id_to_wiz_line, context):
        if not sol_id_sum:
            return ''
        cr.execute('''
                select m.sale_line_id, sum(m.product_qty)
                from stock_move m, stock_picking p
                where
                    m.picking_id = p.id and
                    p.type = 'out' and
                    p.subtype = 'picking' and
                    p.state = 'draft' and
                    m.state in ('assigned', 'confirmed') and
                    m.in_out_updated = 'f' and
                    m.sale_line_id in %s
                group by
                    m.sale_line_id
            ''', (tuple(sol_id_sum.keys()),))
        extra_qty = {}
        for x in cr.fetchall():
            if sol_id_sum[x[0]] and x[1] < sol_id_sum[x[0]]:
                extra_qty[x[0]] = sol_id_sum[x[0]] -  x[1]

        already_process = {}
        if extra_qty:
            cr.execute('''
                    select m.sale_line_id, sum(m.product_qty)
                    from stock_move m, stock_picking p
                    where
                        m.picking_id = p.id and
                        p.type = 'out' and
                        (
                            p.subtype = 'standard' and p.state = 'done' or
                            p.subtype = 'picking' and m.state != 'cancel' and p.state in ('done', 'assigned')
                        ) and
                        m.in_out_updated = 'f' and
                        m.sale_line_id in %s
                    group by
                        m.sale_line_id
                ''', (tuple(extra_qty.keys()),))
            for x in cr.fetchall():
                already_process[x[0]] = x[1]

        if already_process:
            details = []
            for sol in self.pool.get('sale.order.line').browse(cr, uid, list(already_process.keys()), fields_to_fetch=['product_id'], context=context):
                details.append(_('Line number: %s, [%s] %s, qty already processed: %s, qty imported: %s') % (sol_id_to_wiz_line.get(sol.id),sol.product_id.default_code, sol.product_id.name, '{:g}'.format(round(already_process.get(sol.id, 0),2)), '{:g}'.format(round(sol_id_sum.get(sol.id,0),2))))
            return _('Warning the following product lines have already been processed in linked OUT/Pick document, so cannot be processed here. Please remove these lines or adjust quantity before trying to processs the movement\n%s') % ("\n".join(details))
        return ''

    # Simulation routing
    def simulate(self, dbname, uid, ids, context=None):
        '''
        Import the file and fill data in the simulation screen
        '''
        cr = pooler.get_db(dbname).cursor()
        # cr = dbname
        try:
            wl_obj = self.pool.get('wizard.import.in.line.simulation.screen')
            prod_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            pack_info_obj = self.pool.get('wizard.import.in.pack.simulation.screen')

            # Declare global variables (need this explicit declaration to clear
            # them at the end of the process
            global PRODUCT_CODE_ID
            global UOM_NAME_ID
            global CURRENCY_NAME_ID
            global PRODLOT_NAME_ID
            global SIMU_LINES
            global LN_BY_EXT_REF

            if context is None:
                context = {}

            if isinstance(ids, int):
                ids = [ids]

            for wiz in self.browse(cr, uid, ids, context=context):
                nb_treated_lines = 0
                prodlot_cache = {}
                # No file => Return to the simulation screen
                if not wiz.file_to_import:
                    self.write(cr, uid, [wiz.id], {'message': _('No file to import'),
                                                   'state': 'draft'}, context=context)
                    continue

                for line in wiz.line_ids:
                    # Put data in cache
                    if line.move_product_id:
                        PRODUCT_CODE_ID.setdefault(line.move_product_id.default_code, line.move_product_id.id)
                    if line.move_uom_id:
                        UOM_NAME_ID.setdefault(line.move_uom_id.name, line.move_uom_id.id)
                    if line.move_currency_id:
                        CURRENCY_NAME_ID.setdefault(line.move_currency_id.name, line.move_currency_id.id)

                    '''
                    First of all, we build a cache for simulation screen lines
                    '''
                    l_num = line.line_number
                    l_ext_ref = line.external_ref
                    l_prod = line.move_product_id and line.move_product_id.id or False
                    l_uom = line.move_uom_id and line.move_uom_id.id or False
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
                    SIMU_LINES[wiz.id][l_num][l_prod][l_uom].setdefault(line.move_product_qty, [])
                    SIMU_LINES[wiz.id][l_num][l_prod][l_uom][line.move_product_qty].append(line.id)

                    LN_BY_EXT_REF.setdefault(wiz.id, {})
                    if l_ext_ref and l_num:
                        LN_BY_EXT_REF[wiz.id].setdefault(l_ext_ref, [])
                        LN_BY_EXT_REF[wiz.id][l_ext_ref].append(l_num)

                # Variables
                values_header_errors = []
                values_line_errors = []
                file_format_errors = []
                message = ''
                header_values = {}
                file_parse_errors = []

                try:
                    if wiz.filetype == 'excel':
                        values, nb_file_lines, file_parse_errors = self.get_values_from_excel(cr, uid, wiz.file_to_import, with_pack=wiz.with_pack, context=context)
                    else:
                        values, nb_file_lines, file_parse_errors = self.get_values_from_xml(cr, uid, wiz.file_to_import, with_pack=wiz.with_pack, context=context)
                except Exception as e:
                    file_parse_errors.append(str(e))

                if context.get('auto_import_ok') and file_parse_errors:
                    raise Exception('\n'.join(file_parse_errors))

                '''
                We check for each line if the number of columns is consistent
                with the expected number of columns :
                  * For PO header information : 2 columns
                  * For the line information : 12 columns
                '''
                # Check number of columns on lines

                if not file_parse_errors:

                    self.write(cr, uid, [wiz.id], {'nb_file_lines': nb_file_lines}, context=context)

                if file_format_errors or file_parse_errors:
                    message = _('''## IMPORT STOPPED ##

Nothing has been imported because of %s. See below:

    ## File errors ##\n\n''') % (file_format_errors and _('a bad file format') or _('a file parse error'))
                    for err in file_format_errors + file_parse_errors:
                        message += '%s\n' % err

                    self.write(cr, uid, [wiz.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res

                '''
                New, we know that the file has the good format, you can import
                data for header.
                '''
                # Line 1: Freight
                freight_ref = values.get(1, ['', ''])[1]
                header_values['imp_freight_number'] = freight_ref

                # Line 3: Origin
                origin = values.get(3, ['', ''])[1]
                if origin and wiz.purchase_id.name.lower() not in origin.lower():
                    message = _("Import aborted, the Origin (%s) is not the same as in the Incoming Shipment %s (%s).") \
                        % (origin, wiz.picking_id.name, wiz.origin)
                    self.write(cr, uid, [wiz.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res
                header_values['imp_origin'] = wiz.origin

                # Line 5: Transport mode
                transport_type = values.get(5, ['', ''])[1]
                header_values['imp_transport_type'] = transport_type

                # Line 6: Notes
                imp_notes = values.get(6, ['', ''])[1]
                header_values['imp_notes'] = imp_notes

                # Line 7: Message ESC header
                esc_message = values.get(7, ['', ''])[1]
                header_values['message_esc'] = esc_message

                '''
                The header values have been imported, start the importation of
                lines
                '''
                file_lines = {}
                file_in_lines = {}
                data_per_pack = {}
                new_in_lines = []
                not_ok_file_lines = {}
                # Loop on lines

                x = NB_OF_HEADER_LINES + 1
                pack_sequences = {}
                pack_id = False
                pack_found = False
                while x < len(values) + 1:
                    not_ok = False
                    file_line_error = []

                    if 'parcel_from' in values[x]:
                        x += 1
                        if wiz.with_pack:

                            pack_info = {'wizard_id': wiz.id}
                            for key in pack_header:
                                pack_info[key] = values[x].get(key)
                                if pack_coeff.get(key):
                                    pack_info[key] = float(pack_info[key]) * pack_coeff[key]
                                if key == 'packing_list' and pack_info[key]:
                                    pack_info[key] = '%s' % pack_info[key]
                            if pack_info.get('packing_list') and len(pack_info.get('packing_list', '')) > 30:
                                values_line_errors.append(_('Packing List %s, max characters length is 30, found %s') % (pack_info.get('packing_list'), len(pack_info.get('packing_list', ''))))
                            pack_id = pack_info_obj.create(cr, uid, pack_info)
                            pack_sequences.setdefault(pack_info.get('packing_list', ''), []).append((int(pack_info.get('parcel_from')), int(pack_info.get('parcel_to')), pack_id))
                            if values[x]['parcel_from']:
                                pack_found = True
                        x += 2

                    if pack_id:
                        values[x]['pack_info_id'] = pack_id
                    # Check mandatory fields
                    line_number = values.get(x, {}).get('line_number') and int(values.get(x, {}).get('line_number', 0)) or False

                    # external ref is set at PO VI import on new line, because line number is not known by the external system
                    ext_ref = values.get(x, {}).get('external_ref', '')
                    ext_ref = ext_ref and tools.ustr(ext_ref) or False
                    for manda_field in LINES_COLUMNS:
                        if manda_field[2] == 'mandatory' and not values.get(x, {}).get(manda_field[1]):
                            not_ok = True
                            err1 = _('The column \'%s\' mustn\'t be empty%s') % (manda_field[0], manda_field[1] == 'line_number' and ' - Line not imported' or '')
                            err = _('Line %s of the file: %s') % (x, err1)
                            values_line_errors.append(err)
                            file_line_error.append(err1)

                    if line_number and ext_ref:
                        if line_number not in LN_BY_EXT_REF[wiz.id].get(ext_ref, []):
                            not_ok = True
                            err1 = _('No line found for line number \'%s\' and ext. ref. \'%s\' - Line not imported') % (line_number, ext_ref)
                            err = _('Line %s of the file: %s') % (x, err1)
                            values_line_errors.append(err)
                            file_line_error.append(err1)

                    if not line_number and ext_ref:
                        line_number = LN_BY_EXT_REF[wiz.id].get(ext_ref, [False])[0]

                    if not_ok:
                        not_ok_file_lines[x] = ' - '.join(err for err in file_line_error)

                    # Get values
                    product_id = False
                    uom_id = False
                    qty = 0.00

                    vals = values.get(x, {})
                    # Product
                    if vals.get('product_code'):
                        product_id = PRODUCT_CODE_ID.get(vals['product_code'], False)
                    if not product_id and vals.get('product_code'):
                        prod_ids = prod_obj.search(cr, uid, [('default_code', '=', vals['product_code'])], context=context)
                        if prod_ids:
                            product_id = prod_ids[0]
                            PRODUCT_CODE_ID.setdefault(vals['product_code'], product_id)

                    # UoM
                    if vals.get('product_uom'):
                        uom_id = UOM_NAME_ID.get(vals['product_uom'], False)
                        if not uom_id:
                            uom_ids = uom_obj.search(cr, uid, [('name', '=', vals['product_uom'])], context=context)
                            if uom_ids:
                                uom_id = uom_ids[0]
                                UOM_NAME_ID.setdefault(vals['product_uom'], uom_id)

                    # Qty
                    if vals.get('product_qty'):
                        try:
                            qty = float(vals['product_qty'])
                        except ValueError:
                            # do not raise here if the qty is not a float as
                            # it is checked later in import_line()
                            pass

                    # Batch and expiry date
                    # Put the batch + expiry date in a cache to create
                    # the batch that don't exist only during the import
                    # not at simulation time
                    if vals.get('prodlot_id') and vals.get('expired_date'):
                        exp_value = vals['expired_date']
                        if isinstance(vals['expired_date'], datetime):
                            exp_value = exp_value.strftime('%Y-%m-%d')
                        elif vals['expired_date'] and isinstance(vals['expired_date'], str):
                            try:
                                time.strptime(vals['expired_date'], '%Y-%m-%d')
                                exp_value = vals['expired_date']
                            except ValueError:
                                exp_value = False

                        if exp_value and not prodlot_cache.get(product_id, {}).get(tools.ustr(vals['prodlot_id'])):
                            prodlot_cache.setdefault(product_id, {})
                            prodlot_cache[product_id].setdefault(tools.ustr(vals['prodlot_id']), exp_value)

                    file_lines[x] = (line_number, product_id, uom_id, qty, ext_ref, pack_id)
                    if pack_id:
                        data_per_pack.setdefault(pack_id, []).append(file_lines[x])

                    x += 1
                '''
                Get the best matching line:
                    1/ Within lines with same line number, same product, same UoM and same qty
                    2/ Within lines with same line number, same product and same UoM
                    3/ Within lines with same line number and same product
                    4/ Within lines with same line number

                If a matching line is found in one of these cases, keep the link between the
                file line and the simulation screen line.
                '''
                if pack_found:
                    self.write(cr, uid, [wiz.id], {'pack_found': True}, context=context)
                if pack_sequences:
                    rounding_issues = []
                    uom_ids = uom_obj.search(cr, uid, [])
                    uom_data = dict((x.id, x) for x in uom_obj.browse(cr, uid, uom_ids, fields_to_fetch=['rounding'], context=context))
                    ppl_processor = self.pool.get('ppl.processor')
                    for ppl in pack_sequences:
                        ppl_processor.check_sequences(cr, uid, pack_sequences[ppl], pack_info_obj)
                        for pack_d in pack_sequences[ppl]:
                            num_of_pack = pack_d[1] -  pack_d[0] + 1
                            if num_of_pack:
                                for line in data_per_pack.get(pack_d[2], []):
                                    if line[3] and line[2] in uom_data:
                                        if not ppl_processor._check_rounding(cr, uid, uom_data.get(line[2]), num_of_pack, line[3]):
                                            rounding_issues.append('Packing List %s, Pack from parcel %s, to parcel %s' % (ppl or '-', pack_d[0], pack_d[1]))

                        pack_errors_ids = pack_info_obj.search(cr, uid, [('id', 'in', [pack[2] for pack in pack_sequences[ppl]]), ('integrity_status', '!=', 'empty')], context=context)
                        if pack_errors_ids:
                            pack_error_string = dict(PACK_INTEGRITY_STATUS_SELECTION)
                            for pack_error in pack_info_obj.browse(cr, uid, pack_errors_ids, context=context):
                                values_header_errors.append(_("Packing List %s, Pack from parcel %s, to parcel %s, integrity error %s") % (pack_error.packing_list or '-', pack_error.parcel_from, pack_error.parcel_to, _(pack_error_string.get(pack_error.integrity_status))))


                    rounding_text = ""
                    if rounding_issues:
                        rounding_text = "\n" + _("WARNING! The packing results in one or more products with decimal quantities per pack, therefore it might not be possible to do a return of packs or to ship only some of this range of packs") + "\n -"
                        rounding_text += "\n - ".join(rounding_issues)

                    self.write(cr, uid, wiz.id, {'extra_info': _('There are %(num_pl)d Supplier Packing lists in the imported IN: upon confirmation of this screen %(num_pl)d PICK and %(num_pl)d PPL will be created %(rounding_text)s') % {'num_pl': len(pack_sequences), 'rounding_text': rounding_text}}, context=context)


                to_del = []
                for x, fl in file_lines.items():
                    # Search lines with same product, same UoM and same qty
                    matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                    tmp_wl_ids = matching_lines.get(fl[1], {}).get(fl[2], {}).get(fl[3], [])
                    no_match = True
                    for l in tmp_wl_ids:
                        if l not in file_in_lines:
                            file_in_lines[l] = [(x, 'match')]
                            to_del.append(x)
                            no_match = False
                            break

                    if tmp_wl_ids and no_match:
                        file_in_lines[l].append((x, 'split'))
                        to_del.append(x)
                # Clear the dict
                for x in to_del:
                    del file_lines[x]
                to_del = []


                for x, fl in file_lines.items():
                    # Search lines with same product, same UoM
                    matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                    tmp_wl_ids = matching_lines.get(fl[1], {}).get(fl[2], {}).get('line_ids', [])
                    no_match = True
                    for l in tmp_wl_ids:
                        if l not in file_in_lines:
                            file_in_lines[l] = [(x, 'match')]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_in_lines[l].append((x, 'split'))
                        to_del.append(x)
                # Clear the dict
                for x in to_del:
                    del file_lines[x]
                to_del = []

                for x, fl in file_lines.items():
                    # Search lines with same product
                    matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                    tmp_wl_ids = matching_lines.get(fl[1], {}).get('line_ids', [])
                    no_match = True
                    for l in tmp_wl_ids:
                        if l not in file_in_lines:
                            file_in_lines[l] = [(x, 'match')]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_in_lines[l].append((x, 'split'))
                        to_del.append(x)
                # Clear the dict
                for x in to_del:
                    del file_lines[x]
                to_del = []

                for x, fl in file_lines.items():
                    # Search lines with same line number
                    matching_lines = SIMU_LINES.get(wiz.id, {}).get(fl[0], {})
                    tmp_wl_ids = matching_lines.get('line_ids', [])
                    no_match = True
                    for l in tmp_wl_ids:
                        if l not in file_in_lines:
                            file_in_lines[l] = [(x, 'match')]
                            to_del.append(x)
                            no_match = False
                            break
                    if tmp_wl_ids and no_match:
                        file_in_lines[l].append((x, 'split'))
                        to_del.append(x)
                # Clear the dict
                for x in to_del:
                    del file_lines[x]
                to_del = []

                # For file lines with no simu. screen lines with same line number,
                # create a new simu. screen line
                for x in list(file_lines.keys()):
                    new_in_lines.append(x)
                # Split the simu. screen line or/and update the values according
                # to linked file line.
                for in_line, file_lines in file_in_lines.items():
                    if in_line in SIMU_LINES[wiz.id]['line_ids']:
                        index_in_line = SIMU_LINES[wiz.id]['line_ids'].index(in_line)
                        SIMU_LINES[wiz.id]['line_ids'].pop(index_in_line)
                    for file_line in file_lines:
                        nb_treated_lines += 1
                        percent_completed = round(nb_treated_lines / float(nb_file_lines) * 100)
                        self.write(cr, uid, [wiz.id], {'nb_treated_lines': nb_treated_lines,
                                                       'percent_completed': percent_completed}, context=context)
                        vals = values.get(file_line[0], [])
                        if file_line[1] == 'match':
                            err_msg = wl_obj.import_line(cr, uid, in_line, vals, prodlot_cache, wiz.with_pack, context=context)
                            if file_line[0] in not_ok_file_lines:
                                wl_obj.write(cr, uid, [in_line], {'type_change': 'error', 'error_msg': not_ok_file_lines[file_line[0]]}, context=context)
                        elif file_line[1] == 'split':
                            new_wl_id = wl_obj.copy(cr, uid, in_line,
                                                    {'move_product_id': False,
                                                     'move_product_qty': 0.00,
                                                     'move_uom_id': False,
                                                     'move_price_unit': 0.00,
                                                     'move_currenty_id': False,
                                                     'type_change': 'split',
                                                     'imp_batch_name': '',
                                                     'imp_batch_id': False,
                                                     'imp_exp_date': False,
                                                     'error_msg': '',
                                                     'parent_line_id': in_line,
                                                     'move_id': False}, context=context)
                            err_msg = wl_obj.import_line(cr, uid, new_wl_id, vals, prodlot_cache, wiz.with_pack, context=context)
                            if file_line[0] in not_ok_file_lines:
                                wl_obj.write(cr, uid, [new_wl_id], {'type_change': 'error', 'error_msg': not_ok_file_lines[file_line[0]]}, context=context)
                        # Commit modifications
                        cr.commit()

                        if err_msg:
                            for err in err_msg:
                                if wiz.filetype == 'excel':
                                    err = _('Line %s of the Excel file: %s') % (file_line[0], err)
                                values_line_errors.append(err)

                if wiz.with_pack and not context.get('auto_import_ok'):
                    # check if an out line has been forced
                    cr.execute('''
                        select wiz_line.line_number, pol.linked_sol_id, sum(wiz_line.imp_product_qty)
                        from wizard_import_in_line_simulation_screen wiz_line
                        left join wizard_import_in_simulation_screen wiz on wiz.id = wiz_line.simu_id
                        left join stock_move move_in on move_in.picking_id = wiz.picking_id and ( move_id is not null and move_in.id = wiz_line.move_id or move_id is null and move_in.id = wiz_line.initial_move_id)
                        left join purchase_order_line pol on pol.id = move_in.purchase_line_id
                        where
                            (wiz_line.type_change in ('', 'split') or wiz_line.type_change is NULL) and
                            wiz.id = %s
                        group by wiz_line.line_number, pol.linked_sol_id
                    ''', (wiz.id,))
                    sol_id_to_wiz_line = {}
                    sol_id_sum = {}
                    for x in cr.fetchall():
                        sol_id_to_wiz_line[x[1]] = x[0]
                        sol_id_sum[x[1]] = x[2]
                    error_pick = self.error_pick_already_processed(cr, uid, sol_id_sum, sol_id_to_wiz_line, context)
                    if error_pick:
                        values_line_errors.append(error_pick)

                # Create new lines
                for in_line in new_in_lines:
                    nb_treated_lines += 1
                    percent_completed = nb_treated_lines / nb_file_lines * 100
                    self.write(cr, uid, [wiz.id], {'nb_treated_lines': nb_treated_lines,
                                                   'percent_completed': percent_completed}, context=context)
                    if in_line in SIMU_LINES[wiz.id]['line_ids']:
                        index_in_line = SIMU_LINES[wiz.id]['line_ids'].index(in_line)
                        SIMU_LINES[wiz.id]['line_ids'].pop(index_in_line)
                    vals = values.get(in_line, {})
                    new_wl_id = wl_obj.create(cr, uid, {'type_change': 'new',
                                                        'line_number': vals.get('line_number') and int(vals.get('line_number', 0)) or False,
                                                        'simu_id': wiz.id}, context=context)
                    err_msg = wl_obj.import_line(cr, uid, new_wl_id, vals, prodlot_cache, wiz.with_pack, context=context)
                    if in_line in not_ok_file_lines:
                        wl_obj.write(cr, uid, [new_wl_id], {'type_change': 'error', 'error_msg': not_ok_file_lines[in_line]}, context=context)

                    if err_msg:
                        for err in err_msg:
                            if wiz.filetype == 'excel':
                                err = _('Line %s of the Excel file: %s') % (in_line, err)
                            values_line_errors.append(err)
                    # Commit modifications
                    cr.commit()

                # Lines to ignore
                for in_line in SIMU_LINES[wiz.id]['line_ids']:
                    l_d = wl_obj.read(cr, uid, in_line, ['move_uom_id'], context=context)
                    wl_obj.write(cr, uid, in_line, {'type_change': 'ign', 'imp_uom_id': l_d['move_uom_id'] and l_d['move_uom_id'][0]}, context=context)

                '''
                We generate the message which will be displayed on the simulation
                screen. This message is a merge between all errors.
                '''

                import_error_ok = False
                can_be_imported = True
                # Generate the message
                if len(values_header_errors):
                    import_error_ok = True
                    can_be_imported = False
                    message += '\n## %s ##\n\n' % (_('Error on header values'),)
                    for err in values_header_errors:
                        message += '%s\n' % err

                if len(values_line_errors):
                    import_error_ok = True
                    message += '\n## %s ##\n\n' % (_('Error on line values'),)
                    for err in values_line_errors:
                        message += '%s\n' % err
                    if wiz.with_pack:
                        can_be_imported = False

                header_values['message'] = message
                header_values['state'] = can_be_imported and 'simu_done' or 'error'
                header_values['percent_completed'] = 100.0
                header_values['import_error_ok'] = import_error_ok
                self.write(cr, uid, [wiz.id], header_values, context=context)

                res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                cr.commit()
                cr.close(True)
                return res

            cr.commit()
            cr.close(True)

        except Exception as e:
            cr.rollback()
            logging.getLogger('in.simulation simulate').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e, 'state': 'error'}, context=context)
            cr.commit()
            cr.close(True)

        finally:
            # Clear the cache
            PRODUCT_CODE_ID = {}
            UOM_NAME_ID = {}
            CURRENCY_NAME_ID = {}
            SIMU_LINES = {}

        return {'type': 'ir.actions.act_window_close'}

    def _import_with_thread(self, cr, uid, partial_id, simu_id, context=None, with_ppl=False):
        inc_proc_obj = self.pool.get('stock.incoming.processor')
        in_proc_obj = self.pool.get('stock.move.in.processor')
        picking_obj = self.pool.get('stock.picking')
        # Create new cursor
        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()
        try:
            for wiz in inc_proc_obj.browse(new_cr, uid, partial_id, context=context):
                for line in wiz.move_ids:
                    if line.exp_check and not line.lot_check and not line.prodlot_id and line.expiry_date and line.type_check == 'in':
                        prodlot_id = self.pool.get('stock.production.lot')._get_prodlot_from_expiry_date(new_cr, uid, line.expiry_date, line.product_id.id, context=context)
                        in_proc_obj.write(new_cr, uid, [line.id], {'prodlot_id': prodlot_id}, context=context)

            new_picking = picking_obj.do_incoming_shipment(new_cr, uid, partial_id, context=context, with_ppl=with_ppl)
            if isinstance(new_picking, int):
                context['new_picking'] = new_picking
            new_cr.commit()
        except Exception as e:
            new_cr.rollback()
            logging.getLogger('stock.picking').warn('Exception do_incoming_shipment', exc_info=True)
            for wiz in inc_proc_obj.read(new_cr, uid, partial_id, ['picking_id'], context=context):
                picking_obj.update_processing_info(new_cr, uid, wiz['picking_id'][0], False, {
                    'error_msg': '%s\n\nPlease reset the incoming shipment '\
                    'processing and fix the source of the error'\
                    'before re-try the processing.' % str(e),
                }, context=context)
        finally:
            # Close the cursor
            pack_obj = self.pool.get('wizard.import.in.pack.simulation.screen')
            # security: delete pack info used by this simu and set to stock.move
            pack_ids = pack_obj.search(new_cr, uid, [('wizard_id', '=', simu_id)])
            if pack_ids:
                pack_obj.unlink(new_cr, uid, pack_ids)
            new_cr.close(True)
        return True


    def _import(self, cr, uid, ids, context=None, with_ppl=False):
        '''
        Create memeory moves and return to the standard incoming processing wizard
        '''
        line_obj = self.pool.get('wizard.import.in.line.simulation.screen')
        mem_move_obj = self.pool.get('stock.move.in.processor')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        simu_id = self.browse(cr, uid, ids[0], context=context)
        partner = simu_id.picking_id.partner_id

        context['active_id'] = simu_id.picking_id.id
        context['active_ids'] = [simu_id.picking_id.id]
        fields_as_ro = partner.partner_type == 'esc' and simu_id.picking_id.state == 'updated'
        to_write = {'picking_id': simu_id.picking_id.id, 'date': simu_id.picking_id.date, 'fields_as_ro': fields_as_ro}
        if simu_id.physical_reception_date:
            to_write['physical_reception_date'] = simu_id.physical_reception_date
        if not partner or partner.partner_type in ['external', 'esc']:
            to_write['imp_shipment_ref'] = simu_id.imp_freight_number or ''
        to_write['imp_filename'] = simu_id.filename or ''  # To put in last_imported_filename
        partial_id = self.pool.get('stock.incoming.processor').create(cr, uid, to_write, context=context)
        line_ids = line_obj.search(cr, uid, [('simu_id', '=', simu_id.id), '|', ('type_change', 'not in', ('ign', 'error', 'new')), ('type_change', '=', False)], context=context)

        mem_move_ids, move_ids = line_obj.put_in_memory_move(cr, uid, line_ids, partial_id, fields_as_ro=fields_as_ro, context=context)

        # delete extra lines
        del_lines = mem_move_obj.search(cr, uid, [('wizard_id', '=', partial_id), ('id', 'not in', mem_move_ids), ('move_id', 'in', move_ids)], context=context)
        mem_move_obj.unlink(cr, uid, del_lines, context=context)

        self.pool.get('stock.picking').write(cr, uid, [simu_id.picking_id.id], {'note': simu_id.imp_notes}, context=context)

        context['from_simu_screen'] = True

        if simu_id.with_pack or context.get('do_not_import_with_thread'):
            cr.commit()
            if context.get('do_not_import_with_thread'):
                # Auto VI IN import: do not process IN
                self._import_with_thread(cr, uid, [partial_id], simu_id.id, context=context, with_ppl=with_ppl)
            else:
                new_thread = threading.Thread(target=self._import_with_thread, args=(cr, uid, [partial_id], simu_id.id, context, with_ppl))
                new_thread.start()
                new_thread.join(20)
                if new_thread.is_alive():
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'delivery_mechanism', 'stock_picking_processing_info_form_view')[1]
                    prog_id = self.pool.get('stock.picking').update_processing_info(cr, uid, simu_id.picking_id.id, prog_id=False, values={}, context=context)
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'stock.picking.processing.info',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': prog_id,
                        'view_id': [view_id],
                        'context': context,
                        'target': 'new',
                    }

            return self.return_to_in(cr, uid, simu_id.id, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.incoming.processor',
                'res_id': partial_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'same',
                'context': context}

wizard_import_in_simulation_screen()

class wizard_import_in_pack_simulation_screen(osv.osv):
    _name = 'wizard.import.in.pack.simulation.screen'
    _rec_name = 'parcel_from'

    def _get_real_total(self, cr, uid, ids, f, a, context=None):
        res = {}
        for pack in self.browse(cr, uid, ids, context=context):
            res[pack.id] = {'real_total_volume': False, 'real_total_weight': False}

            if pack.parcel_to and pack.parcel_from:
                nb_pack = pack.parcel_to - pack.parcel_from + 1
                if pack.total_weight:
                    res[pack.id]['real_total_weight'] = int(round(nb_pack * pack.total_weight, 0))
                if pack.total_height and pack.total_length and pack.total_width:
                    res[pack.id]['real_total_volume'] = int(round(pack.total_height * pack.total_length * pack.total_width * nb_pack / 1000, 0))
        return res

    _columns = {
        'wizard_id': fields.many2one('wizard.import.in.simulation.screen', 'Simu Wizard'),
        'parcel_from': fields.integer_null('Parcel From'),
        'parcel_to': fields.integer_null('Parcel To'),
        'parcel_qty': fields.integer_null('Parcel Qty'),
        # on IN VI import file the fields are named total_xxx but the figures are p.p
        'total_weight': fields.float_null('Weight', digits=(16,2)),
        'total_volume': fields.float_null('Volume', digits=(16,2)),
        'total_height': fields.float_null('Height', digits=(16,2)),
        'total_length': fields.float_null('Length', digits=(16,2)),
        'total_width': fields.float_null('Width', digits=(16,2)),
        'packing_list': fields.char('Supplier Packing List', size=30),
        'ppl_name': fields.char('Supplier Packing List', size=128),
        'integrity_status': fields.selection(string='Integrity Status', selection=PACK_INTEGRITY_STATUS_SELECTION, readonly=True),
        'real_total_volume': fields.function(_get_real_total, method=True, type='integer_null', string='Total volume for all packs', multi='real_total'),
        'real_total_weight': fields.function(_get_real_total, method=True, type='integer_null', string='Total weight for all packs', multi='real_total'),
    }

    _defaults = {
        'integrity_status': 'empty',
    }

wizard_import_in_pack_simulation_screen()


class wizard_import_in_line_simulation_screen(osv.osv):
    _name = 'wizard.import.in.line.simulation.screen'
    _rec_name = 'line_number'
    _order = 'line_number_ok, line_number, id'

    def _get_values(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute values according to values in line
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            price_unit = 0.00
            if line.move_id.purchase_line_id:
                price_unit = line.move_id.purchase_line_id.price_unit
            elif line.move_product_id:
                price_unit = line.move_product_id.standard_price

            if line.move_id.picking_id and line.move_id.picking_id.purchase_id \
               and line.move_id.picking_id.purchase_id.pricelist_id \
               and line.move_id.picking_id.purchase_id.pricelist_id.currency_id:
                curr_id = line.move_id.picking_id.purchase_id.pricelist_id.currency_id.id
            elif line.move_id and line.move_id.price_currency_id:
                curr_id = line.move_id.price_currency_id.id
            elif line.parent_line_id and line.parent_line_id.move_currency_id:
                curr_id = line.parent_line_id.move_currency_id.id
            else:
                curr_id = False


            product = line.imp_product_id or line.move_product_id
            res[line.id] = {
                'lot_check': product.batch_management,
                'exp_check': product.perishable,
                'kc_check': product.is_kc and 'X',
                'dg_check': product.dg_txt,
                'np_check': product.cs_txt,
                'move_price_unit': price_unit,
                'move_currency_id': curr_id,
            }

        return res


    def _get_l_num(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute the line number
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'line_number_ok': not line.line_number or line.line_number == 0,
                            'str_line_number': line.line_number and line.line_number != 0 and line.line_number or ''}

        return res


    def _get_imported_values(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute some field with imported values
        '''
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'imp_cost': 0.00,
                            'discrepancy': 0.00}
            if line.simu_id.state != 'draft':
                res[line.id]['imp_cost'] = line.imp_product_qty * line.imp_price_unit
                res[line.id]['discrepancy'] = res[line.id]['imp_cost'] - (line.move_product_qty * line.move_price_unit)

        return res

    _columns = {
        'simu_id': fields.many2one('wizard.import.in.simulation.screen', string='Simu ID', required=True, ondelete='cascade'),
        # Values from move line
        'move_id': fields.many2one('stock.move', string='Move', readonly=True),
        'initial_move_id': fields.many2one('stock.move', string='Initial Move', readonly=True),
        'move_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'move_product_qty': fields.float(digits=(16, 2), string='Ordered Qty', readonly=True, related_uom='move_uom_id'),
        'move_uom_id': fields.many2one('product.uom', string='Ordered UoM', readonly=True),
        'move_price_unit': fields.function(_get_values, method=True, type='float', string='Price Unit',
                                           digits=(16, 2), store=True, readonly=True, multi='computed'),
        'move_currency_id': fields.function(_get_values, method=True, type='many2one', relation='res.currency',
                                            string='Curr.', store=True, readonly=True, multi='computed'),
        # Values for the simu line
        'line_number': fields.integer(string='Line'),
        'line_number_ok': fields.function(_get_l_num, method=True, type='boolean',
                                          string='Line number ok', readonly=True, multi='line_num',
                                          store={'wizard.import.in.line.simulation.screen': (lambda self, cr, uid, ids, c={}: ids, ['line_number'], 20)}),
        'str_line_number': fields.function(_get_l_num, method=True, type='char', size=32,
                                           string='Line', readonly=True, multi='line_num',
                                           store={'wizard.import.in.line.simulation.screen': (lambda self, cr, uid, ids, c={}: ids, ['line_number'], 20)}),
        'external_ref': fields.char(size=256, string='External Ref.', readonly=True),
        'type_change': fields.selection([('', ''),
                                         ('split', 'Split'),
                                         ('error', 'Error'),
                                         ('ign', 'Ign.'),
                                         ('new', 'New')], string='CHG', readonly=True),
        'error_msg': fields.text(string='Error message', readonly=True),
        'parent_line_id': fields.many2one('wizard.import.in.line.simulation.screen', string='Parent line', readonly=True),
        'parent_move_id': fields.many2one('stock.move', string='Parent Move', readonly=True),
        # Values after import
        'imp_product_id': fields.many2one('product.product', string='Product', readonly=True),
        'imp_asset_id': fields.many2one('product.asset', string='Asset', readonly=True),
        'imp_product_qty': fields.float(digits=(16, 2), string='Qty to Process', readonly=True, related_uom='imp_uom_id'),
        'imp_uom_id': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_price_unit': fields.float(digits=(16, 2), string='Price Unit', readonly=True),
        'imp_cost': fields.function(_get_imported_values, method=True, type='float', multi='imported',
                                    digits=(16, 2), string='Cost', readonly=True, store=False),
        'discrepancy': fields.function(_get_imported_values, method=True, type='float', multi='imported',
                                       digits=(16, 2), string='Discre.', readonly=True, store=False),
        'imp_currency_id': fields.many2one('res.currency', string='Curr.', readonly=True),
        'imp_batch_id': fields.many2one('stock.production.lot', string='Batch Number', readonly=True),
        'imp_batch_name': fields.char(size=128, string='Batch Number', readonly=True),
        'imp_exp_date': fields.date(string='Expiry date', readonly=True),
        'imp_packing_list': fields.char(size=256, string='Packing list', readonly=True),
        'imp_external_ref': fields.char(size=256, string='External ref.', readonly=True),
        'message_esc1': fields.char(size=256, string='Message ESC 1', readonly=True),
        'message_esc2': fields.char(size=256, string='Message ESC 2', readonly=True),
        # Computed fields
        'lot_check': fields.function(
            _get_values,
            method=True,
            type='boolean',
            string='B.Num',
            readonly=True,
            store=False,
            multi='computed',
        ),
        'exp_check': fields.function(
            _get_values,
            method=True,
            type='boolean',
            string='Exp',
            readonly=True,
            store=False,
            multi='computed',
        ),
        'kc_check': fields.function(
            _get_values,
            method=True,
            type='char',
            size=8,
            string='CC',
            readonly=True,
            store=False,
            multi='computed',
        ),
        'dg_check': fields.function(
            _get_values,
            method=True,
            type='char',
            size=8,
            string='DG',
            readonly=True,
            store=False,
            multi='computed',
        ),
        'np_check': fields.function(
            _get_values,
            method=True,
            type='char',
            size=8,
            string='CS',
            readonly=True,
            store=False,
            multi='computed',
        ),
        'integrity_status': fields.selection(
            selection=INTEGRITY_STATUS_SELECTION,
            string=' ',
            readonly=True,
        ),
        'pack_info_id': fields.many2one('wizard.import.in.pack.simulation.screen', 'Pack Info'),
    }

    _defaults = {
        'integrity_status': 'empty',
    }

    def check_exp_date(self, cr, uid, exp_value, context=None):
        if context is None:
            context = {}

        res = False
        if exp_value and isinstance(exp_value, datetime):
            if not datetime.strptime(exp_value.strftime('%Y-%m-%d'), '%Y-%m-%d') < datetime(1900, 0o1, 0o1, 0, 0, 0):
                res = exp_value.strftime('%Y-%m-%d')
        elif exp_value and isinstance(exp_value, str):
            try:
                time.strptime(exp_value, '%Y-%m-%d')
                if not datetime.strptime(exp_value, '%Y-%m-%d') < datetime(1900, 0o1, 0o1, 0, 0, 0):
                    res = exp_value
            except ValueError:
                res = False

        return res

    def import_line(self, cr, uid, ids, values, prodlot_cache=None, with_pack=None, context=None):
        '''
        Write the line with the values
        '''
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        prodlot_obj = self.pool.get('stock.production.lot')

        if isinstance(ids, int):
            ids = [ids]

        if context is None:
            context = {}

        if prodlot_cache is None:
            prodlot_cache = {}

        errors = []
        warnings = []

        ext_ref = values.get('external_ref')
        for line in self.browse(cr, uid, ids, context=context):
            write_vals = {}

            if ext_ref:
                write_vals['imp_external_ref'] = ext_ref

            # Product
            prod_id = False
            loc_id = line.move_id and line.move_id.location_id.id or line.parent_line_id and \
                line.parent_line_id.move_id.location_id.id or False
            dest_loc_id = line.move_id and line.move_id.location_dest_id.id or line.parent_line_id and line.parent_line_id.move_id.location_dest_id or False
            if values.get('product_code') == line.move_product_id.default_code:
                if line.move_product_id:
                    p_error, p_msg = prod_obj._test_restriction_error(cr, uid, [line.move_product_id.id],
                                                                      vals={'location_id': loc_id, 'location_dest_id': dest_loc_id, 'obj_type': 'in', 'partner_type': line.simu_id.picking_id.partner_id.partner_type},
                                                                      context=context)
                    if p_error:  # Check constraints on products
                        write_vals['type_change'] = 'error'
                        errors.append(p_msg)
                    else:
                        prod_id = line.move_product_id.id
                        write_vals['imp_product_id'] = prod_id
            else:
                prod_id = False
                if values.get('product_code'):
                    values['product_code'] = values['product_code'].upper()
                    prod_id = PRODUCT_CODE_ID.get(values['product_code'])

                if not prod_id and values['product_code']:
                    stripped_product_code = values['product_code'].strip()
                    prod_ids = prod_obj.search(cr, uid, [('default_code', '=ilike', stripped_product_code)], context=context)
                    if not prod_ids:
                        # if we didn't manage to link our product code with existing product in DB, we cannot continue checks
                        # because it needs the product id:
                        errors.append(_('Product not found in database'))
                        write_vals.update({
                            'error_msg': errors[-1],
                            'type_change': 'error',
                        })
                        self.write(cr, uid, [line.id], write_vals, context=context)
                        continue
                    else:
                        p_error, p_msg = prod_obj._test_restriction_error(cr, uid, [prod_id], vals={'location_id': loc_id, 'location_dest_id': dest_loc_id, 'obj_type': 'in', 'partner_type': line.simu_id.picking_id.partner_id.partner_type},
                                                                          context=context)
                        if p_error:  # Check constraints on products
                            write_vals['type_change'] = 'error'
                            errors.append(p_msg)
                        else:
                            write_vals['imp_product_id'] = prod_ids[0]
                else:
                    p_error, p_msg = prod_obj._test_restriction_error(cr, uid, [prod_id], vals={'location_id': loc_id, 'location_dest_id': dest_loc_id, 'obj_type': 'in', 'partner_type': line.simu_id.picking_id.partner_id.partner_type},
                                                                      context=context)
                    if p_error:  # Check constraints on products
                        write_vals['type_change'] = 'error'
                        errors.append(p_msg)
                    else:
                        write_vals['imp_product_id'] = prod_id

            product = False
            if write_vals.get('imp_product_id'):
                product = prod_obj.browse(cr, uid, write_vals.get('imp_product_id'), context=context)


            # Product Qty
            err_msg = _('Incorrect float value for field \'Product Qty\'')
            try:
                qty = float(values.get('product_qty'))
                if qty < 0:
                    err_msg = _('Product Qty should be greater than 0.00')
                    raise ValueError(err_msg)
                write_vals['imp_product_qty'] = qty
            except Exception:
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # UoM
            uom_value = values.get('product_uom')
            if uom_value and line.move_uom_id and tools.ustr(uom_value.lower()) == line.move_uom_id.name.lower():
                write_vals['imp_uom_id'] = line.move_uom_id.id
            else:
                uom_id = UOM_NAME_ID.get(tools.ustr(uom_value))
                if not uom_id:
                    uom_ids = uom_obj.search(cr, uid, [('name', '=ilike', tools.ustr(uom_value))], context=context)
                    if uom_ids:
                        write_vals['imp_uom_id'] = uom_ids[0]
                    else:
                        errors.append(_('UoM not found in database'))
                else:
                    write_vals['imp_uom_id'] = uom_id

            # Check UoM consistency
            if write_vals.get('imp_uom_id') and product:
                prod_uom_c_id = product.uom_id.category_id.id
                uom_c_id = uom_obj.browse(cr, uid, write_vals['imp_uom_id']).category_id.id
                if prod_uom_c_id != uom_c_id:
                    errors.append(_("Given UoM is not compatible with the product UoM"))

            if write_vals.get('imp_uom_id') and not line.move_uom_id:
                write_vals['move_uom_id'] = write_vals['imp_uom_id']

            # Unit price
            err_msg = _('Incorrect float value for field \'Price Unit\'')
            try:
                unit_price = float(values.get('price_unit'))
                if unit_price < 0:
                    err_msg = _('Unit Price should be greater than 0.00')
                    raise ValueError(err_msg)
                write_vals['imp_price_unit'] = unit_price
            except Exception:
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # Currency
            currency_value = values.get('price_currency_id')
            line_currency = False
            if line.move_currency_id:
                line_currency = line.move_currency_id
            elif line.parent_line_id and line.parent_line_id.move_currency_id:
                line_currency = line.parent_line_id.move_currency_id

            if line_currency:
                write_vals['imp_currency_id'] = line_currency.id
                if tools.ustr(currency_value.upper()) != line_currency.name.upper():
                    err_msg = _('The currency on the Excel file is not the same as the currency of the IN line - You must have the same currency on both side - Currency of the initial line kept.')
                    errors.append(err_msg)

            # Batch number :: data initialisation
            batch_value = values.get('prodlot_id')
            exp_value = values.get('expired_date') or False
            lot_check = line.lot_check
            exp_check = line.exp_check
            if product:
                lot_check = product.batch_management
                exp_check = product.perishable
            if exp_value:
                exp_value = self.check_exp_date(cr, uid, exp_value, context=context)
                if not exp_value:
                    errors.append(_('Incorrect date value for field \'Expired date\''))

            if lot_check: # product is BN mandatory
                if batch_value and exp_value:
                    write_vals.update({
                        'imp_batch_name': tools.ustr(batch_value),
                        'imp_exp_date': exp_value,
                    })
                if batch_value and not exp_value:
                    if not exp_value:
                        batch_ids = prodlot_obj.search(cr, uid, [('name', '=', batch_value), ('product_id', '=', product.id)], order='id desc', context=context)
                        if batch_ids:
                            exp_value = prodlot_obj.browse(cr, uid, batch_ids[0]).life_date
                            write_vals.update({
                                'imp_batch_name': tools.ustr(batch_value),
                                'imp_exp_date': exp_value,
                            })
            elif exp_check: # product is only ED mandatory
                if batch_value:
                    warnings.append(_('A batch number is defined on the imported file but the product doesn\'t require batch number - Batch ignored'))
                write_vals.update({
                    'imp_batch_id': False,
                    'imp_batch_name': False,
                    'imp_exp_date': exp_value,
                })
            else: # product is not BN or ED mandatory
                if batch_value:
                    warnings.append(_('A batch number is defined on the imported file but the product doesn\'t require batch number - Batch ignored'))
                if exp_value:
                    warnings.append(_('An expired date is defined on the imported file but the product doesn\'t require expired date - Expired date ignored'))
                write_vals.update({
                    'imp_batch_id': False,
                    'imp_batch_name': False,
                    'imp_exp_date': False,
                })

            # Check stock in Cross Docking and if flow comes from a FO
            sol = line.move_id and line.move_id.purchase_line_id and line.move_id.purchase_line_id.linked_sol_id or False
            if sol and not sol.procurement_request and with_pack and write_vals.get('imp_product_qty'):
                cd_ctx = context.copy()
                cd_ctx['location'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_cross_docking',
                                                                                         'stock_location_cross_docking')[1],
                new_bn = False
                if lot_check or exp_check:
                    bn_domain = [('product_id', '=', prod_id)]
                    if write_vals.get('imp_batch_name', False):
                        bn_domain.append(('name', '=', write_vals['imp_batch_name']))
                    if write_vals.get('imp_exp_date', False):
                        bn_domain.append(('life_date', '=', write_vals['imp_exp_date']))
                    bn_ids = self.pool.get('stock.production.lot').search(cr, uid, bn_domain, context=context)
                    if bn_ids:
                        cd_ctx['prodlot_id'] = bn_ids and bn_ids[0]
                    else:
                        new_bn = True

                if not new_bn and prod_obj.browse(cr, uid, prod_id, fields_to_fetch=['qty_allocable'],
                                                  context=cd_ctx).qty_allocable < 0:
                    err_msg = _('There is not enough stock in Cross Docking which can be allocated to process the product %s with a quantity of %s. Please check if there is some other (forced) availability of this product.') \
                        % (product.default_code, write_vals['imp_product_qty'])
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'

            # Message ESC 1
            write_vals['message_esc1'] = values.get('message_esc1')
            # Message ESC 2
            write_vals['message_esc2'] = values.get('message_esc2')

            write_vals['integrity_status'] = self.check_integrity_status(cr, uid, write_vals, warnings=warnings, context=context)
            if write_vals['integrity_status'] != 'empty' or len(errors) > 0:
                write_vals['type_change'] = 'error'
                if write_vals['integrity_status'] != 'empty' and write_vals.get('imp_product_qty'):
                    errors.append(_('IN-line %s Wrong BN/ED attributes') % (line.line_number,))

            if line.type_change == 'new':
                write_vals['type_change'] = 'error'
                if write_vals.get('imp_external_ref'):
                    errors.append(_('No original IN lines with external ref \'%s\' found.') % write_vals['imp_external_ref'])
                else:
                    errors.append(_('IN Line %s does not correspond to original IN') % (line.line_number or '',))

            error_msg = line.error_msg or ''
            for err in errors:
                if error_msg:
                    error_msg += ' - '
                error_msg += err

            for warn in warnings:
                if error_msg:
                    error_msg += ' - '
                error_msg += warn

            write_vals['error_msg'] = error_msg
            job_comment = context.get('job_comment', [])
            for msg in warnings:
                job_comment.append({
                    'res_model': 'stock.picking',
                    'res_id': line.simu_id.picking_id.id,
                    'msg': _('%s Line %s: %s') % (line.simu_id.picking_id.name, line.line_number, msg)
                })
            context['job_comment'] = job_comment

            if values.get('pack_info_id'):
                write_vals['pack_info_id'] = values['pack_info_id']
                pack_info_data = self.pool.get('wizard.import.in.pack.simulation.screen').read(cr, uid,  values['pack_info_id'], ['parcel_from', 'parcel_to', 'packing_list'])
                if not pack_info_data['packing_list']:
                    pack_info_data['packing_list'] = ''
                write_vals['imp_packing_list'] = '%(packing_list)s %(parcel_from)d-%(parcel_to)d' % pack_info_data

            self.write(cr, uid, [line.id], write_vals, context=context)

        return errors

    def get_error_msg(self, cr, uid, ids, context=None):
        '''
        Display the error message
        '''
        if isinstance(ids, int):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.error_msg:
                raise osv.except_osv(_('Warning'), line.error_msg)
            if line.integrity_status != 'empty':
                sel = self.fields_get(cr, uid, ['integrity_status'])
                integrity_message = dict(sel['integrity_status']['selection']).get(getattr(line, 'integrity_status'), getattr(line, 'integrity_status'))
                raise osv.except_osv(_('Warning'), integrity_message)

        return True

    def check_integrity_status(self, cr, uid, vals, warnings=None, context=None):
        '''
        Return the integrity_status of the line
        '''
        if context is None:
            context = {}

        product_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        product = vals.get('imp_product_id') and product_obj.browse(cr, uid, vals['imp_product_id'], context=context) or False
        prodlot_id = vals.get('imp_batch_id') and prodlot_obj.browse(cr, uid, vals['imp_batch_id'], context=context) or False
        exp_date = vals.get('imp_exp_date')
        prodlot_name = vals.get('imp_batch_name')

        if not product:
            return 'empty'

        if not (product.perishable or product.batch_management):
            if exp_date or prodlot_id:
                return 'no_lot_needed'

        if product.batch_management:
            if not prodlot_id and not prodlot_name and not context.get('simulation_bypass_missing_lot', False):
                return 'missing_lot'
            elif not prodlot_id and not prodlot_name and context.get('simulation_bypass_missing_lot', False) and warnings is not None:
                warnings.append(_('Batch Number is Missing'))

            if prodlot_id and prodlot_id.type != 'standard':
                return 'wrong_lot_type_need_standard'

        if product.perishable:
            if not exp_date and not context.get('simulation_bypass_missing_lot', False):
                return 'missing_date'
            elif not exp_date and context.get('simulation_bypass_missing_lot', False) and warnings is not None:
                warnings.append(_('Expiry Date is Missing'))

            if not product.batch_management and prodlot_id and prodlot_id.type != 'internal':
                return 'wrong_lot_type_need_internal'

        return 'empty'

    def _get_lot_in_cache(self, cr, uid, lot_cache, product_id, name, exp_date, context=None):
        '''
        Get the lot from the cache or from the DB
        '''
        lot_obj = self.pool.get('stock.production.lot')

        if context is None:
            context = {}

        lot_cache.setdefault(product_id, {})
        lot_cache[product_id].setdefault(name, False)

        if lot_cache[product_id][name] and lot_cache[product_id][name][1] == exp_date:
            batch_id = lot_cache[product_id][name][0]
        else:
            lot_ids = lot_obj.search(cr, uid, [
                ('product_id', '=', product_id),
                ('name', '=', name),
                ('life_date', '=', exp_date),
            ], context=context)

            if lot_ids:
                batch_id = lot_ids[0]
            else:
                batch_id = lot_obj.create(cr, uid, {
                    'product_id': product_id,
                    'name': name,
                    'life_date': exp_date,
                }, context=context)

            lot_cache[product_id][name] = (batch_id, exp_date)

        return batch_id

    def put_in_memory_move(self, cr, uid, ids, partial_id, fields_as_ro=False, context=None):
        '''
        Create a stock.move.in.processor for each lines
        '''
        move_obj = self.pool.get('stock.move.in.processor')

        if isinstance(ids, int):
            ids = [ids]

        move_ids = []
        mem_move_ids = []
        lot_cache = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.type_change in ('ign', 'error', 'new'):
                continue

            move = False
            if line.type_change == 'split':
                move = line.parent_line_id.move_id
            else:
                move = line.move_id

            batch_id = line.imp_batch_id and line.imp_batch_id.id or False
            if not batch_id and line.imp_batch_name and line.imp_exp_date:
                batch_id = self._get_lot_in_cache(
                    cr,
                    uid,
                    lot_cache,
                    line.imp_product_id.id,
                    line.imp_batch_name,
                    line.imp_exp_date,
                    context=context,
                )

            vals = {'change_reason': '%s - %s' % (line.message_esc1, line.message_esc2),
                    'cost': line.imp_price_unit,
                    'currency': line.imp_currency_id.id,
                    'expiry_date': line.imp_exp_date,
                    'line_number': line.line_number,
                    'move_id': move.id,
                    'initial_move_id': move.id,
                    'split_move_ok': line.type_change == 'split',
                    'prodlot_id': batch_id,
                    'product_id': line.imp_product_id.id,
                    'uom_id': line.imp_uom_id.id,
                    'ordered_quantity': move.product_qty,
                    'quantity': line.imp_product_qty,
                    'wizard_id': partial_id,
                    'pack_info_id': line.pack_info_id and line.pack_info_id.id or False,
                    'cost_as_ro': fields_as_ro,
                    }

            mem_move_ids.append(move_obj.create(cr, uid, vals, context=context))
            if move:
                move_ids.append(move.id)

        return mem_move_ids, move_ids


wizard_import_in_line_simulation_screen()
