# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

class catalogue_import_lines_xls(osv.osv_memory):
    _name = 'catalogue.import.lines.xls'
    _description = 'Supplier catalogue import lines'

    _columns = {
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
        'file_to_import': fields.binary(string='File to import'),
        'msg': fields.char('Message', size=512),
        'error': fields.text('Errors'),
        'hide_error': fields.boolean('Hide error'),
    }

    _defaults = {
        'hide_error': lambda *a: True,
    }

    def log_error(self, line_num, msg, error):
        error.append('Line %d: %s'%(line_num, msg))

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        cat_line_obj = self.pool.get('supplier.catalogue.line')

        error = []
        nb_line = 0

        wiz = self.browse(cr, uid, ids[0], context=context)
        if not wiz.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz.file_to_import))

        # iterator on rows
        reader = fileobj.getRows()

        # ingore the first row
        reader.next()
        line_num = 1
        for row in reader:
            line_num += 1
            row_len = len(row)
            if row_len < 4:
                self.log_error(line_num, _('Invalid line'), error)
                continue

            if not row.cells[0].data:
                self.log_error(line_num, _('No product code'), error)
                continue
            if not row.cells[1].data:
                self.log_error(line_num, _('No product UOM'), error)
                continue
            if not row.cells[2].data:
                self.log_error(line_num, _('No Min. Qty'), error)
                continue
            if row.cells[2].type not in ('float', 'int'):
                self.log_error(line_num, _('Min. Qty %s should by a number')%(row.cells[2].data, ), error)
                continue
            if not row.cells[3].data:
                self.log_error(line_num, _('No Unit Price'), error)
                continue
            if row.cells[3].type not in ('float', 'int'):
                self.log_error(line_num, _('Unit Price %s should by a number')%(row.cells[3].data, ), error)
                continue

            p_ids = product_obj.search(cr, uid, [('default_code', '=', row.cells[0].data.strip())])
            if not p_ids:
                self.log_error(line_num, _('Code %s not found')%(row.cells[0].data, ), error)
                continue

            uom_ids = uom_obj.search(cr, uid, [('name', '=', row.cells[1].data.strip())], context=context)
            if not uom_ids:
                self.log_error(line_num, _('UOM %s not found')%(row.cells[1].data, ), error)
                continue

            roundig = False
            min_order = False
            comment = False

            if row_len >= 5:
                if row.cells[4].data:
                    if row.cells[4].type not in ('float', 'int'):
                        self.log_error(line_num, _('Rounding %s should by a number')%(row.cells[4].data, ), error)
                        continue
                    rounding = row.cells[4].data
            if row_len >= 6:
                if row.cells[5].data:
                    if row.cells[5].type not in ('float', 'int'):
                        self.log_error(line_num, _('Min. Order Qty %s should by a number')%(row.cells[5].data, ), error)
                        continue
                    min_order = row.cells[5].data
            if row_len >= 7:
                comment = row.cells[6].data


            # TODO: check Product/UOM compat: should be a constraint in supplier_catalogue_line

            to_write = {
                'catalogue_id': wiz.catalogue_id.id,
                'product_id': p_ids[0],
                'line_uom_id': uom_ids[0],
                'min_qty': row.cells[2].data,
                'unit_price': row.cells[3].data,
                'rounding': roundig,
                'min_order_qty': min_order,
                'comment': comment
            }

            cat_line_obj.create(cr, uid, to_write, context=context)
            nb_line += 1

        if error:
            data = {'msg': _('File not imported, %d lines in error')%(len(error),), 'error': "\n".join(error), 'hide_error': False}
            cr.rollback()
        else:
            data = {'msg': _('%d lines successfully imported')%(nb_line,), 'error': False}

        self.write(cr, uid, [wiz.id], data)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'spreadsheet_xml_examples', 'catalogue_import_lines_xls_report_form_view')[1]

        return {
            'name': 'Import Catalogue Report',
            'type': 'ir.actions.act_window',
            'res_model': 'catalogue.import.lines.xls',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': wiz.id,
            'context': context,
            'target': 'new',
        }

    def close(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}

catalogue_import_lines_xls()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
