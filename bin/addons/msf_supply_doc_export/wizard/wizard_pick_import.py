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
        'picking_processor_id': fields.many2one('create.picking.processor', string="PICK processor ref"),
        'validate_processor_id': fields.many2one('validate.picking.processor', string="PICK processor ref"),
        'import_file': fields.binary('PICK import file'),
    }


    def normalize_data(self, cr, uid, data):
        if 'qty_picked' in data: # set to float
            if not data['qty_picked']:
                data['qty_picked'] = 0.0
            if isinstance(data['qty_picked'], (str,unicode)):
                data['qty_picked'] = float(data['qty_picked'])

        if 'qty_to_pick' in data: # set to float
            if not data['qty_to_pick']:
                data['qty_to_pick'] = 0.0
            if isinstance(data['qty_to_pick'], (str,unicode)):
                data['qty_to_pick'] = float(data['qty_to_pick'])

        if 'batch' in data: #  set to str
            if not data['batch']:
                data['batch'] = ''

        if 'expiry_date' in data: #  set to str
            if not data['expiry_date']:
                data['expiry_date'] = '' 

        return data


    def cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids[0], context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'create.picking.processor' if wiz.picking_processor_id else 'validate.picking.processor',
            'res_id': wiz.picking_processor_id.id or wiz.validate_processor_id.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }  


    def import_pick_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids[0], context=context)
        import_file = SpreadsheetXML(xmlstring=base64.decodestring(wiz.import_file))

        res_model = 'create.picking.processor' if wiz.picking_processor_id else 'validate.picking.processor'
        move_proc_model = 'create.picking.move.processor' if wiz.picking_processor_id else 'validate.move.processor'
        res_id = wiz.picking_processor_id.id or wiz.validate_processor_id.id

        # wizard moves :: reset wizard lines
        move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [('wizard_id', '=', res_id)], context=context)
        self.pool.get(move_proc_model).write(cr, uid, move_proc_ids, {
            'quantity': 0,
            'prodlot_id': False,
            'expiry_date': False,
        }, context=context)

        line_index = 0
        import_data_header = {}
        import_data_lines = {}
        for row in import_file.getRows():
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

        if import_data_header['reference'] != wiz.picking_id.name:
            raise osv.except_osv(_('Error'), _('PICK reference in the import file doesn\'t match with the current PICK'))

        for xls_line_number, line_data in sorted(import_data_lines.items()):
            if line_data['qty_picked'] is None:
                raise osv.except_osv(_('Error'), _('Line %s: Column "Qty Picked" should contains the quantity to process and cannot be empty, please fill it with "0" instead') % xls_line_number)
            line_data = self.normalize_data(cr, uid, line_data)
            if line_data['qty_picked'] > line_data['qty_to_pick']:
                raise osv.except_osv(
                    _('Error'), 
                    _('Line %s: Column "Qty Picked" cannot be greater than "Qty to pick"') % xls_line_number
                )

            # search line in processor wiz
            move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [
                ('wizard_id', '=', res_id),
                ('line_number', '=', line_data['item']),
                ('ordered_quantity', '=', line_data['qty_to_pick']),
                ('quantity', '=', 0),
            ], context=context)

            # search line in PICK
            move_ids = self.pool.get('stock.move').search(cr, uid, [
                ('picking_id', '=', wiz.picking_id.id),
                ('line_number', '=', line_data['item']),
                ('product_qty', '=', line_data['qty_to_pick']),
            ], context=context)

            if not move_proc_ids and not move_ids:
                raise osv.except_osv(
                    _('Error'), 
                    _('Line %s: Move with line number %s and ordered qty %s not found') % (xls_line_number, line_data['item'], line_data['qty_to_pick'])
                )

            # if stock move is not "available" then it should be ignored:
            if move_ids:
                stock_move = self.pool.get('stock.move').browse(cr, uid, move_ids[0], fields_to_fetch=['state'], context=context)
                if stock_move.state != 'assigned':
                    continue
                
            if move_proc_ids and line_data['qty_picked'] and line_data['qty_to_pick']:
                move_proc = self.pool.get(move_proc_model).browse(cr, uid, move_proc_ids[0], context=context)
                to_write = {}

                if line_data['code'] != move_proc.product_id.default_code:
                    raise osv.except_osv(
                        _('Error'), 
                        _('Line %s: Import product code doesn\'t match with the product') % xls_line_number
                    )
                if move_proc.product_id.batch_management and not line_data['batch']:
                    raise osv.except_osv(
                        _('Error'), 
                        _('Line %s: Product is batch number mandatory and no batch number is given') % xls_line_number
                    )
                if not move_proc.product_id.batch_management and move_proc.product_id.perishable and not line_data['expiry_date']:
                    raise osv.except_osv(
                        _('Error'), 
                        _('Line %s: Product is expiry date mandatory and no expiry date is given') % xls_line_number
                    )

                to_write['quantity'] = line_data['qty_picked']

                if move_proc.product_id.batch_management and line_data['batch']:
                    prodlot_ids = self.pool.get('stock.production.lot').search(cr, uid, [
                        ('product_id', '=', move_proc.product_id.id),
                        ('name', '=', line_data['batch']),
                    ], context=context)
                    if prodlot_ids:
                        to_write['prodlot_id'] = prodlot_ids[0]
                    else:
                        raise osv.except_osv(
                        _('Error'), 
                        _('Line %s: Given batch number doesn\'t exists in database') % xls_line_number
                    )
                elif not move_proc.product_id.batch_management and move_proc.product_id.perishable and line_data['expiry_date']:
                    prodlot_ids = self.pool.get('stock.production.lot').search(cr, uid, [
                        ('life_date', '=', line_data['expiry_date']),
                        ('type', '=', 'internal'),
                        ('product_id', '=', move_proc.product_id.id),
                    ], context=context)
                    if prodlot_ids:
                        to_write['prodlot_id'] = prodlot_ids[0]
                    else:
                        raise osv.except_osv(
                            _('Error'), 
                            _('Line %s: Given expiry date doesn\'t exists in database') % xls_line_number
                        )

                self.pool.get(move_proc_model).write(cr, uid, [move_proc.id], to_write, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'res_id': res_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }


wizard_pick_import()


