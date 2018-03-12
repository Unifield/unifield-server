# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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

import base64
from os import path

from osv import fields
from osv import osv
from tools.translate import _

from msf_doc_import import GENERIC_MESSAGE
from msf_doc_import.wizard import INT_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_internal_import
from msf_doc_import.wizard import INT_LINE_COLUMNS_FOR_IMPORT as columns_for_internal_import
from msf_doc_import.wizard import IN_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_incoming_import
from msf_doc_import.wizard import IN_LINE_COLUMNS_FOR_IMPORT as columns_for_incoming_import
from msf_doc_import.wizard import OUT_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_delivery_import
from msf_doc_import.wizard import OUT_LINE_COLUMNS_FOR_IMPORT as columns_for_delivery_import
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import xml.etree.ElementTree as ET


class stock_picking(osv.osv):
    """
    We override the class for import of Internal moves
    """
    _inherit = 'stock.picking'

    _columns = {
        'filetype': fields.selection([('excel', 'Excel file'),
                                      ('xml', 'XML file')], string='Type of file',),
        'last_imported_filename': fields.char(size=128, string='Filename'),
    }

    def get_import_filetype(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}

        if '.' not in file_path:
            raise osv.except_osv(_('Error'), _('Wrong extension for given import file')  )

        if file_path.endswith('.xml'):
            return 'xml'      
        elif file_path.endswith('.xls'):
            return 'excel'
        else:
            raise osv.except_osv(_('Error'), _('Import file extension should end with .xml or .xls'))


    def get_available_incoming_from_po_name(self, cr, uid, po_name, context=None):
        if context is None:
            context = {}

        po_id = self.pool.get('purchase.order').search(cr, uid, [('name', '=', po_name)], context=context)
        if not po_id:
            raise osv.except_osv(_('Error'), _('PO with name %s not found') % po_name)
        in_id = self.pool.get('stock.picking').search(cr, uid, [
            ('purchase_id', '=', po_id[0]),
            ('type', '=', 'in'),
            ('state', 'in', ['assigned', 'shipped', 'updated']),
        ], context=context)
        if not in_id:
            raise osv.except_osv(_('Error'), _('No available IN found for the given PO %s' % po_name))
        return in_id[0]


    def get_incoming_id_from_file(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}

        filetype = self.get_import_filetype(cr, uid, file_path, context)
        xmlstring = open(file_path).read()

        incoming_id = False
        if filetype == 'excel':
            file_obj = SpreadsheetXML(xmlstring=xmlstring)
            po_name = False
            for index, row in enumerate(file_obj.getRows()):
                if row.cells[0].data == 'Origin':
                    po_name = row.cells[1].data or ''
                    if isinstance(po_name, (str,unicode)):
                        po_name = po_name.strip()
                    if not po_name:
                        raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
                    break
            else:
                raise osv.except_osv(_('Error'), _('Header field "Origin" not found in the given XLS file'))
            incoming_id = self.get_available_incoming_from_po_name(cr, uid, po_name, context=context)

        elif filetype == 'xml':
            root = ET.fromstring(xmlstring)
            orig = root.findall('.//field[@name="origin"]')
            if orig:
                po_name = orig[0].text or ''
                po_name = po_name.strip()
                if not po_name:
                    raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
            else:
                raise osv.except_osv(_('Error'), _('No field with name "Origin" was found in the XML file'))
            incoming_id = self.get_available_incoming_from_po_name(cr, uid, po_name, context=context)

        return incoming_id


    def get_file_content(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}
        res = ''
        with open(file_path) as fich:
            res = fich.read()
        return res


    def auto_import_incoming_shipment(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}
        filetype = self.get_import_filetype(cr, uid, file_path, context=context)
        file_content = self.get_file_content(cr, uid, file_path, context=context)
        LINE_START = 11

        # get ID of the IN:
        in_id = self.get_incoming_id_from_file(cr, uid, file_path, context)

        # create stock.incoming.processor and its stock.move.in.processor:
        in_processor = self.pool.get('stock.incoming.processor').create(cr, uid, {'picking_id': in_id}, context=context)
        self.pool.get('stock.incoming.processor').create_lines(cr, uid, in_processor, context=context) # import all lines and set qty to zero

        # get imported moves and its qty:
        context.update({'xml_is_string': True})
        if filetype == 'excel':
            values, nb_file_lines, file_parse_errors = self.pool.get('wizard.import.in.simulation.screen').get_values_from_excel(cr, uid, file_content, context=context)
        else:
            values, nb_file_lines, file_parse_errors = self.pool.get('wizard.import.in.simulation.screen').get_values_from_xml(cr, uid, file_content, context=context)

        # for each move imported, update qty in the stock.incoming.processor:
        for index in range(LINE_START, LINE_START+nb_file_lines):
            row = values[index]
            move_id = self.pool.get('stock.move').search(cr, uid, [
                ('picking_id', '=', in_id),
                ('line_number', '=', row.get('line_number')),
            ], context=context)
            if move_id:
                move = self.pool.get('stock.move').browse(cr, uid, move_id[0], context=context)
                move_proc_ids = self.pool.get('stock.move.in.processor').search(cr, uid, [
                    ('wizard_id', '=', in_processor),
                    ('move_id', '=', move.id),
                    ('quantity', '=', 0.00),
                ], context=context)
                if move_proc_ids:
                    self.pool.get('stock.move.in.processor').write(cr, uid, move_proc_ids, {
                        'quantity': row.get('product_qty', 0.00),
                    }, context=context)
            else:
                raise osv.except_osv(_('Error'), _('No matching stock move found for line %s') % index)

        # run method do_incoming_shipment:
        new_picking = self.do_incoming_shipment(cr, uid, in_processor, context)

        return True


    def export_template_file(self, cr, uid, ids, context=None):
        '''
        Export the template file in Excel or Pure XML format
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick = self.browse(cr, uid, ids[0], context=context)
        if not pick.filetype:
            raise osv.except_osv(_('Error'), _('You must select a file type before print the template'))

        report_name = pick.filetype == 'excel' and 'incoming.shipment.xls' or 'incoming.shipment.xml'

        datas = {'ids': ids}

        return {'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': datas,
                'context': context,
        }

    def wizard_import_pick_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        # Objects
        wiz_obj = self.pool.get('wizard.import.pick.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({'active_id': ids[0]})

        picking = self.browse(cr, uid, ids[0], context=context)
        if picking.type == 'in':
            header_cols = columns_header_for_incoming_import
            cols = columns_for_incoming_import
        elif picking.type == 'out' and picking.subtype == 'standard':
            header_cols = columns_header_for_delivery_import
            cols = columns_for_delivery_import
        else:
            header_cols = columns_header_for_internal_import
            cols = columns_for_incoming_import

        columns_header = [(_(f[0]), f[1]) for f in header_cols]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': file,
                                             'filename_template': 'template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'picking_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.pick.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        message = ''
        plural = ''

        for var in self.browse(cr, uid, ids, context=context):
            if var.move_lines:
                for var in var.move_lines:
                    if var.to_correct_ok:
                        line_num = var.line_number
                        if message:
                            message += ', '
                        message += str(line_num)
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s: %s') % (plural, message))
        return True


stock_picking()


class stock_move(osv.osv):
    _inherit = 'stock.move'

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        vals.update({
            'to_correct_ok': False,
            'text_error': False,
        })
        return super(stock_move, self).write(cr, uid, ids, vals, context=context)


stock_move()
