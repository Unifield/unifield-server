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

from osv import osv
from osv import fields
from os import path
from tools.translate import _

from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import INT_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_int_line_import
from msf_doc_import.wizard import INT_LINE_COLUMNS_FOR_IMPORT as columns_for_int_line_import
from msf_doc_import import GENERIC_MESSAGE

import base64


class stock_picking(osv.osv):
    """
    We override the class for import of Internal moves
    """
    _inherit = 'stock.picking'

    _columns = {
        'filetype': fields.selection([('excel', 'Excel file'),
                                      ('xml', 'XML file')], string='Type of file',),
    }

    def export_template_file(self, cr, uid, ids, context=None):
        '''
        Export the template file in Excel or Pure XML format
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        pick = self.browse(cr, uid, ids[0], context=context)
        if not pick.filetype:
            raise osv.except_osv(_('Error'), _('You must select a file type before print the template'))

        report_name = pick.filetype == 'excel' and 'report.incoming.shipment.xls' or 'report.incoming.shipment.xml'

        datas = {'ids': ids}

        return {'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': datas,
                'context': context,
        }

    def wizard_import_int_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_int_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.int.line').create(cr, uid, {'file': file,
                                                                             'filename_template': 'template.xls',
                                                                             'filename': 'Lines_Not_Imported.xls',
                                                                             'message': """%s %s""" % (GENERIC_MESSAGE, ', '.join([_(f) for f in columns_for_int_line_import]), ),
                                                                             'int_id': ids[0],
                                                                             'state': 'draft',}, context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.int.line',
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
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        tbd_product = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
        message = ''
        
        if not context.get('import_in_progress') or not context.get('button') and context.get('button') == 'save_and_close':
            if vals.get('product_uom') == tbd_uom:
                message += _('You have to define a valid UoM, i.e. not "To be defined".')
            if vals.get('product_id') == tbd_product:
                message += _('You have to define a valid product, i.e. not "To be defined".')

        return super(stock_move, self).write(cr, uid, ids, vals, context=context)


stock_move()
