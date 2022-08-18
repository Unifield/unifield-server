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
from datetime import datetime

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
    10: 'transport_type',
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
    'qty',
    'qty_to_process',
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
        'import_file': fields.binary('PICK import file', required=True),
    }

    def normalize_data(self, cr, uid, data):
        if 'qty_to_process' in data:  # set to float
            if not data['qty_to_process']:
                data['qty_to_process'] = 0.0
            if isinstance(data['qty_to_process'], str):
                try:
                    data['qty_to_process'] = float(data['qty_to_process'])
                except:
                    raise osv.except_osv(
                        _('Error'), _('Line %s: Column "Qty to Process" must be a number') % data['item']
                    )

        if 'qty' in data:  # set to float
            if not data['qty']:
                data['qty'] = 0.0
            if isinstance(data['qty'], str):
                try:
                    data['qty'] = float(data['qty'])
                except:
                    raise osv.except_osv(
                        _('Error'), _('Line %s: Column "Qty" must be a number') % data['item']
                    )

        if 'batch' in data:  # set to str
            if not data['batch']:
                data['batch'] = ''

        if 'expiry_date' in data:
            if not data['expiry_date']:
                data['expiry_date'] = ''
            else:
                try:
                    data['expiry_date'] = datetime(data['expiry_date'].year, data['expiry_date'].month, data['expiry_date'].day)
                except:
                    raise osv.except_osv(
                        _('Error'), _('Line %s: Column "Expiry Date" must be a date') % data['item']
                    )

        return data

    def cancel(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return {'type': 'ir.actions.act_window_close'}

    def split_move(self, cr, uid, move_id, move_qty, new_qty=0.00, context=None):
        """
        Split the line according to new parameters
        """
        if not move_id:
            raise osv.except_osv(
                _('Error'),
                _('No line to split !'),
            )

        move_obj = self.pool.get('stock.move')

        # New quantity must be greater than 0.00 and lower than the original move's qty
        if new_qty <= 0.00 or new_qty > move_qty or new_qty == move_qty:
            return False

        # Create a copy of the move with the new quantity
        context.update({'keepLineNumber': True})
        new_move_id = move_obj.copy(cr, uid, move_id, {'product_qty': new_qty}, context=context)
        context.pop('keepLineNumber')

        # Update the original move
        update_qty = move_qty - new_qty
        move_obj.write(cr, uid, move_id, {'product_qty': update_qty}, context=context)

        # Set the new move to available
        move_obj.action_confirm(cr, uid, [new_move_id], context=context)
        move_obj.action_assign(cr, uid, [new_move_id])
        move_obj.force_assign(cr, uid, [new_move_id])

        return new_move_id

    def get_matching_move(self, cr, uid, ids, line_data, product_id, picking_id, treated_lines, context=None):
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')

        move_domain = [
            ('id', 'not in', treated_lines),
            ('picking_id', '=', picking_id),
            ('line_number', '=', line_data['item']),
            ('product_id', '=', product_id),
        ]
        exact_move_domain = [x for x in move_domain]
        exact_move_domain.append(('product_qty', '=', line_data['qty']))
        move_ids = move_obj.search(cr, uid, exact_move_domain, limit=1, context=context)
        if move_ids:
            exact_move = move_obj.browse(cr, uid, move_ids[0], fields_to_fetch=['product_qty', 'state'], context=context)
            if exact_move.product_qty == 0 or exact_move.state != 'assigned':
                # Prevent modification of confirmed (Not Available) or processed (qty at 0) line
                return False
            else:
                return move_ids[0]
        else:
            move_ids = move_obj.search(cr, uid, move_domain, context=context)
            for move in move_obj.browse(cr, uid, move_ids, fields_to_fetch=['product_qty', 'state'], context=context):
                if 0 < line_data['qty'] < move.product_qty and move.state == 'assigned':
                    new_move_id = self.split_move(cr, uid, move.id, move.product_qty, line_data['qty'], context=context)
                    if not new_move_id:
                        raise osv.except_osv(
                            _('Error'),
                            _('The Line #%s could not be split. Please ensure that the new quantity is above 0 and less than the original line\'s quantity.')
                            % (line_data['item'],)
                        )
                    else:
                        return new_move_id
                else:
                    # Prevent modification of confirmed (Not Available) line
                    return False

        raise osv.except_osv(
            _('Error'),
            _('The total quantity of line #%s in the import file (%s) doesn\'t match with the total qty on screen')
            % (line_data['item'], line_data['qty'])
        )

    def checks_on_batch(self, cr, uid, ids, product, line_data, context=None):
        if context is None:
            context = {}

        if product.batch_management and not line_data['batch']:
            raise osv.except_osv(
                _('Error'),
                _('Line %s: Product is batch number mandatory and no batch number is given') % line_data['item']
            )
        if not product.batch_management and product.perishable and not line_data['expiry_date']:
            raise osv.except_osv(
                _('Error'),
                _('Line %s: Product is expiry date mandatory and no expiry date is given') % line_data['item']
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

    def get_product(self, cr, uid, ids, line_data, context=None):
        if context is None:
            context = {}

        prod_obj = self.pool.get('product.product')

        product_ids = prod_obj.search(cr, uid, [('default_code', '=ilike', line_data['code'])], limit=1, context=context)
        if not product_ids:
            raise osv.except_osv(
                _('Error'),
                _('Product with code %s not found in database') % line_data['code']
            )

        return prod_obj.browse(cr, uid, product_ids[0], fields_to_fetch=['batch_management', 'perishable'], context=context)

    def import_pick_xls(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, ids[0], context=context)
        if not wiz.import_file:
            raise osv.except_osv(_('Error'), _('No file to import'))
        import_file = SpreadsheetXML(xmlstring=base64.b64decode(wiz.import_file))
        import_data_header, import_data_lines = self.get_import_data(cr, uid, ids, import_file, context=context)

        if (import_data_header['reference'] or '').lower() != wiz.picking_id.name.lower():
            raise osv.except_osv(_('Error'), _('PICK reference in the import file doesn\'t match with the current PICK'))

        moves_data = []
        qty_per_line = {}
        treated_lines = []
        for xls_line_number, line_data in sorted(import_data_lines.items()):
            try:
                line_data['item'] = int(line_data['item'])
            except:
                raise osv.except_osv(_('Error'), _('File line %s: Column "Item" must be an integer') % xls_line_number)

            if line_data['qty_to_process'] is None:
                raise osv.except_osv(_('Error'), _('Line %s: Column "Qty to Process" should contains the quantity to process and cannot be empty, please fill it with "0" instead') % line_data['item'])
            if line_data['qty_to_process'] and float(line_data['qty_to_process']) < 0:
                raise osv.except_osv(_('Error'), _('Line %s: Column "Qty to Process" should be greater than 0') % line_data['item'])

            line_data = self.normalize_data(cr, uid, line_data)
            if line_data['qty']:
                to_write = {}

                product = self.get_product(cr, uid, ids, line_data, context=context)
                move_id = self.get_matching_move(cr, uid, ids, line_data, product.id, wiz.picking_id.id, treated_lines, context=context)
                if not move_id:
                    continue
                else:
                    self.checks_on_batch(cr, uid, ids, product, line_data, context=context)
                    to_write.update({
                        'move_id': move_id,
                    })
                    if line_data['qty_to_process'] > line_data['qty']:
                        raise osv.except_osv(
                            _('Error'), _('Line %s: Column "Qty to Process" (%s) cannot be greater than "Qty" (%s)')
                            % (line_data['item'], line_data['qty_to_process'], line_data['qty'])
                        )
                    treated_lines.append(to_write['move_id'])

                move = self.pool.get('stock.move').browse(cr, uid, to_write['move_id'], context=context)

                if move.state == 'assigned':  # Save qties by line
                    if qty_per_line.get(line_data['item']):
                        qty_per_line[line_data['item']] += line_data['qty']
                    else:
                        qty_per_line[line_data['item']] = line_data['qty']

                to_write['qty_to_process'] = line_data['qty_to_process']
                if move.product_id.batch_management:
                    if line_data['batch'] and line_data['expiry_date']:
                        prodlot_ids = self.pool.get('stock.production.lot').search(cr, uid, [
                            ('product_id', '=', move.product_id.id),
                            ('name', '=', line_data['batch']),
                            ('life_date', '=', line_data['expiry_date']),
                        ], context=context)
                        if prodlot_ids:
                            to_write['prodlot_id'] = prodlot_ids[0]
                        else:
                            raise osv.except_osv(
                                _('Error'),
                                _('Line %s: The given batch number with this expiry date doesn\'t exist in database') % line_data['item']
                            )
                    else:
                        raise osv.except_osv(_('Error'),
                                             _('Line %s: Product %s must have a batch number and an expiry date')
                                             % (line_data['item'], line_data['code']))
                elif not move.product_id.batch_management and move.product_id.perishable and line_data['expiry_date']:
                    prodlot_ids = self.pool.get('stock.production.lot').search(cr, uid, [
                        ('life_date', '=', line_data['expiry_date']),
                        ('type', '=', 'internal'),
                        ('product_id', '=', move.product_id.id),
                    ], context=context)
                    if prodlot_ids:
                        to_write['prodlot_id'] = prodlot_ids[0]
                    else:
                        raise osv.except_osv(
                            _('Error'),
                            _('Line %s: The given expiry date doesn\'t exist in database') % line_data['item']
                        )

                moves_data.append(to_write)

        cr.execute("""
            SELECT m.line_number, p.default_code, SUM(product_qty) 
            FROM stock_move m, product_product p
            WHERE m.product_id = p.id AND m.picking_id = %s AND m.state = 'assigned' 
            GROUP BY m.line_number, p.default_code
        """, (wiz.picking_id.id,))
        for prod in cr.fetchall():
            if prod[2] != 0 and qty_per_line.get(prod[0]) and qty_per_line[prod[0]] != prod[2]:
                raise osv.except_osv(
                    _('Error'),
                    _('The total quantity of line #%s in the import file (%s) doesn\'t match with the total qty on screen (%s)')
                    % (prod[0], prod[2], qty_per_line.get(prod[0]))
                )

        for to_write in moves_data:
            if to_write.get('move_id'):
                move_data = {'qty_to_process': to_write.get('qty_to_process', 0)}
                if to_write.get('prodlot_id'):
                    move_data.update({'prodlot_id': to_write['prodlot_id']})
                self.pool.get('stock.move').write(cr, uid, to_write['move_id'], move_data, context=context)

        return {'type': 'ir.actions.act_window_close'}


wizard_pick_import()


