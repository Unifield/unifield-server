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


    def normalize_data(self, cr, uid, data, xls_line_number):
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

        if data['qty_picked'] > data['qty_to_pick']:
            raise osv.except_osv(
                _('Error'),
                _('Line %s: Column "Qty Picked" cannot be greater than "Qty to pick"') % xls_line_number
            )

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


    def get_matching_move(self, cr, uid, ids, wizard_id, move_proc_model, xls_line_number, line_data, product_id, location_id, picking_id, context=None):
        if context is None:
            context = {}

        original_line = False # if new line is created (split), then it contains the original line

        # same line_number, product, source location, qty
        move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [
            ('wizard_id', '=', wizard_id),
            ('line_number', '=', line_data['item']),
            ('product_id', '=', product_id),
            ('location_id', '=', location_id),
            ('ordered_quantity', '=', line_data['qty_to_pick']),
            ('quantity', '=', 0),
        ], context=context)

        # same line_number, product, source location, greater qty
        if not move_proc_ids:
            move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [
                ('wizard_id', '=', wizard_id),
                ('line_number', '=', line_data['item']),
                ('product_id', '=', product_id),
                ('location_id', '=', location_id),
                ('ordered_quantity', '>', line_data['qty_to_pick']),
                ('quantity', '=', 0),
            ], context=context)

        # same line_number, product, source location
        if not move_proc_ids:
            move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [
                ('wizard_id', '=', wizard_id),
                ('line_number', '=', line_data['item']),
                ('product_id', '=', product_id),
                ('location_id', '=', location_id),
                ('quantity', '=', 0),
            ], context=context)

        if not move_proc_ids: # then create new line
            move_not_available_ids = self.pool.get('stock.move').search(cr, uid, [
                ('picking_id', '=', picking_id),
                ('line_number', '=', line_data['item']),
                ('product_id', '=', product_id),
                ('product_qty', '=', line_data['qty_to_pick']),
                ('state', '!=', 'assigned'),
            ], context=context)
            if move_not_available_ids:
                return False

            move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [
                ('wizard_id', '=', wizard_id),
                ('line_number', '=', line_data['item']),
                ('product_id', '=', product_id),
                ('location_id', '=', location_id),
            ], context=context)
            if move_proc_ids:
                new_move_id = self.pool.get(move_proc_model).copy(cr, uid, move_proc_ids[0], {}, context=context)
                original_line = move_proc_ids[0]
                move_proc_ids = [new_move_id]

                self.pool.get(move_proc_model).write(cr, uid, [new_move_id], {'ordered_quantity': line_data['qty_to_pick']}, context=context)
                original_qty = self.pool.get(move_proc_model).browse(cr, uid, original_line).ordered_quantity
                self.pool.get(move_proc_model).write(cr, uid, [original_line], {'ordered_quantity': original_qty - line_data['qty_to_pick']}, context=context)
            else:
                raise osv.except_osv(
                    _('Error'),
                    _('Line %s: Matching move not found') % xls_line_number
                )

        return move_proc_ids[0]


    def checks_on_batch(self, cr, uid, ids, move_proc, line_data, xls_line_number, context=None):
        if context is None:
            context = {}

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


    def get_import_data(self, cr, uid, ids, import_file, context=None):
        if context is None:
            context = {}

        import_data_header = {}
        import_data_lines = {}
        line_index = 0
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

        return (import_data_header, import_data_lines)


    def reset_wizard_lines(self, cr, uid, ids, wizard_id, move_proc_model, context=None):
        if context is None:
            context = {}
        move_proc_ids = self.pool.get(move_proc_model).search(cr, uid, [('wizard_id', '=', wizard_id)], context=context)
        self.pool.get(move_proc_model).write(cr, uid, move_proc_ids, {
            'quantity': 0,
            'prodlot_id': False,
            'expiry_date': False,
        }, context=context)


    def get_product_id(self, cr, uid, ids, line_data, context=None):
        if context is None:
            context = {}

        product_ids = self.pool.get('product.product').search(cr, uid, [('default_code', '=', line_data['code'])], context=context)
        if not product_ids:
            raise osv.except_osv(
                _('Error'),
                _('Product with code %s not found in database') % line_data['code']
            )
        return product_ids[0]


    def get_location_id(self, cr, uid, ids, line_data, context=None):
        if context is None:
            context = {}

        location_ids = self.pool.get('stock.location').search(cr, uid, [('name', '=', line_data['src_location'])], context=context)
        if not location_ids:
            raise osv.except_osv(
                _('Error'),
                _('Stock location %s not found in database') % line_data['src_location']
            )
        return location_ids[0]


    def check_matching_qty_per_line_number(self, cr, uid, ids, import_data_lines, wiz, context=None):
        if context is None:
            context = {}
        ln_with_cancelled = []
        stock_move_data = {}
        for stock_move in wiz.picking_id.move_lines:
            if stock_move.state in ('cancel', 'done'):
                ln_with_cancelled.append(stock_move.line_number)
                continue
            if stock_move_data.get(stock_move.line_number):
                stock_move_data[stock_move.line_number] += stock_move.product_qty
            else:
                stock_move_data[stock_move.line_number] = stock_move.product_qty

        import_data = {}
        for xls_line_number, line_data in sorted(import_data_lines.items()):
            line_data = self.normalize_data(cr, uid, line_data, xls_line_number)

            if line_data['item'] in ln_with_cancelled: # ignore cancelled/done lines
                product_id = self.get_product_id(cr, uid, ids, line_data, context=context)
                closed_move_ids = self.pool.get('stock.move').search(cr, uid, [
                    ('picking_id', '=', wiz.picking_id.id),
                    ('line_number', '=', line_data['item']),
                    ('product_id', '=', product_id),
                    ('product_qty', '=', line_data['qty_to_pick']),
                    ('state', 'in', ['cancel', 'done']),
                ], context=context)
                if closed_move_ids:
                    continue

            if import_data.get(line_data['item']):
                import_data[line_data['item']] += line_data['qty_to_pick']
            else:
                import_data[line_data['item']] = line_data['qty_to_pick']

        for ln in import_data.keys():
            if ln in stock_move_data and import_data[ln] != stock_move_data[ln]:
                raise osv.except_osv(
                    _('Error'),
                    _('The total quantity of line #%s in the import file doesn\'t match with the total qty on screen') % ln
                )


    def import_pick_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids[0], context=context)
        import_file = SpreadsheetXML(xmlstring=base64.decodestring(wiz.import_file))
        res_model = 'create.picking.processor' if wiz.picking_processor_id else 'validate.picking.processor'
        move_proc_model = 'create.picking.move.processor' if wiz.picking_processor_id else 'validate.move.processor'
        res_id = wiz.picking_processor_id.id or wiz.validate_processor_id.id
        import_data_header, import_data_lines = self.get_import_data(cr, uid, ids, import_file, context=context)

        self.reset_wizard_lines(cr, uid, ids, res_id, move_proc_model, context=context)

        if import_data_header['reference'] != wiz.picking_id.name:
            raise osv.except_osv(_('Error'), _('PICK reference in the import file doesn\'t match with the current PICK'))

        self.check_matching_qty_per_line_number(cr, uid, ids, import_data_lines, wiz, context=context)

        for xls_line_number, line_data in sorted(import_data_lines.items()):
            if line_data['qty_picked'] is None:
                raise osv.except_osv(_('Error'), _('Line %s: Column "Qty Picked" should contains the quantity to process and cannot be empty, please fill it with "0" instead') % xls_line_number)

            line_data = self.normalize_data(cr, uid, line_data, xls_line_number)

            if line_data['qty_picked'] and line_data['qty_to_pick']:
                product_id = self.get_product_id(cr, uid, ids, line_data, context=context)
                location_id = self.get_location_id(cr, uid, ids, line_data, context=context)
                move_proc_id = self.get_matching_move(cr, uid, ids, res_id, move_proc_model, xls_line_number, line_data, product_id, location_id, wiz.picking_id.id, context=context)
                if not move_proc_id:
                    continue

                move_proc = self.pool.get(move_proc_model).browse(cr, uid, move_proc_id, context=context)
                to_write = {}

                self.checks_on_batch(cr, uid, ids, move_proc, line_data, xls_line_number, context=context)

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


