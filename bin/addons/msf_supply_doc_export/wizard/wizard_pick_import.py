#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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
from tools.translate import _
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

import base64


# /!\ to keep up to date with XLS export template:
XLS_TEMPLATE_HEADER = {
    1: 'reference',
    2: 'date',
    3: 'fo_ref',
    4: 'origin_ref',
    5: 'incoming_ref',
    6: 'category',
    7: 'packing_date',
    8: 'total_items',
    9: 'content',
    10: 'transport_mode',
    11: 'priority',
    12: 'rts_date',
}
XLS_TEMPLATE_LINE_HEADER = [
    'item',
    'code',
    'description',
    'changed_article',
    'comment',
    'src_location',
    'qty_in_stock',
    'qty_to_pick',
    'qty_picked',
    'batch',
    'expiry_date',
    'kc',
    'dg',
    'cs',
]

class wizard_pick_import(osv.osv_memory):
    _name = 'wizard.pick.import'
    _description = 'PICK import wizard'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string="PICK ref", required=True),
        'picking_processor_id': fields.many2one('create.picking.processor', string="PICK processor ref", required=True),
        'import_file': fields.binary('PICK import file'),
    }

    def import_pick_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids[0], context=context)
        import_file = SpreadsheetXML(xmlstring=base64.decodestring(wiz.import_file))
        rows = import_file.getRows()

        line_index = 0
        import_data_header = {}
        import_data_lines = {}
        for row in rows:
            line_index += 1
            if line_index <= max(XLS_TEMPLATE_HEADER.keys()):
                import_data_header[XLS_TEMPLATE_HEADER[line_index]] = row.cells[1].data
            elif line_index > max(XLS_TEMPLATE_HEADER.keys()) + 1:
                line = tuple([rc.data for rc in row.cells])
                line_data = {}
                i = 0
                for key in XLS_TEMPLATE_LINE_HEADER:
                    line_data[key] = line[i]
                    i += 1
                import_data_lines[line_index] = line_data


        for xls_line_number, line_data in import_data_lines.items():
            pass # TODO update processing wizard with import values

wizard_pick_import()


