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
import threading
import pooler
from osv import osv, fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import time
from datetime import datetime
import tools
from msf_doc_import import check_line
from msf_doc_import.wizard import PPL_COLUMNS_LINES_FOR_IMPORT as ppl_columns_lines_for_import
import json


class wizard_import_ppl_to_create_ship(osv.osv_memory):
    _name = 'wizard.import.ppl.to.create.ship'
    _description = 'Import Pack Lines from Excel sheet to create a Shipment'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        '''
        Return True if a message is set on the wizard
        '''
        res = {}

        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = obj.message or False

        return res

    _columns = {
        'file': fields.binary(string='Lines to import', required=True, readonly=True,
                              states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True, translate=True),
        'picking_id': fields.many2one('stock.picking', string='Stock Picking', required=True),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'json_text': fields.text(string='JSON as text', help='Please put the data on a single line, with no line return'),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean",
                                           string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
    }

    def _check_main_header_names(self, header_data, context):
        '''
        Check the main header names
        '''
        header_names = {
            '0-0': _('Reference'), '0-3': _('Shipper'), '0-6': _('Consignee'), '1-0': _('Date'),
            '2-0': _('Requester Ref'), '3-0': _('Our Ref'), '4-0': _('FO Date'), '5-0': _('Packing Date'),
            '6-0': _('RTS Date'), '7-0': _('Transport mode')
        }
        error_log = ''
        if header_data[0][0].lower() != header_names['0-0'].lower():
            error_log += _('\nThe line 1 of the column 1 must be named "Reference" in the file.')
        if header_data[0][3].lower() != header_names['0-3'].lower():
            error_log += _('\nThe line 1 of the column 4 must be named "Shipper" in the file.')
        if header_data[0][6].lower() != header_names['0-6'].lower():
            error_log += _('\nThe line 1 of the column 7 must be named "Consignee" in the file.')
        if header_data[1][0].lower() != header_names['1-0'].lower():
            error_log += _('\nThe line 2 of the column 1 must be named "Date" in the file.')
        if header_data[2][0].lower() != header_names['2-0'].lower():
            error_log += _('\nThe line 3 of the column 1 must be named "Requester Ref" in the file.')
        if header_data[3][0].lower() != header_names['3-0'].lower():
            error_log += _('\nThe line 4 of the column 1 must be named "Our Ref" in the file.')
        if header_data[4][0].lower() != header_names['4-0'].lower():
            error_log += _('\nThe line 5 of the column 1 must be named "FO Date" in the file.')
        if header_data[5][0].lower() != header_names['5-0'].lower():
            error_log += _('\nThe line 6 of the column 1 must be named "Packing Date" in the file.')
        if header_data[6][0].lower() != header_names['6-0'].lower():
            error_log += _('\nThe line 7 of the column 1 must be named "RTS Date" in the file.')
        if header_data[7][0].lower() != header_names['7-0'].lower():
            error_log += _('\nThe line 8 of the column 1 must be named "Transport mode" in the file.')

        if error_log:
            raise osv.except_osv(_('Error'), error_log)

        return True

    def _check_main_header_data(self, header_data, picking, context):
        '''
        Check the main headers data
        '''
        error_log = ''
        if not header_data[0][2]:
            error_log += _(' The Packing reference is mandatory.')
        else:
            if header_data[0][2].lower() != picking.name.lower():
                error_log += _(' The Packing reference in the file doesn\'t match the one from the Pre-Packing header.')
        if not header_data[3][2]:
            error_log += _(' Our Ref (origin) is mandatory.')
        else:
            if header_data[3][2].lower() != picking.origin.lower():
                error_log += _(' Our Ref (origin) in the file doesn\'t match the one from the Pre-Packing header.')

        if error_log:
            raise osv.except_osv(_('Error'), error_log)

        return True

    def split_move(self, cr, uid, move_id, new_qty=0.00, context=None):
        """
        Split the line according to new parameters
        """
        if context is None:
            context = {}
        if not move_id:
            raise osv.except_osv(_('Error'), _('No line to split !'))

        move_obj = self.pool.get('stock.move')
        move = move_obj.browse(cr, uid, move_id, fields_to_fetch=['product_qty'], context=context)

        # New quantity must be greater than 0.00 and lower than the original move's qty
        if new_qty <= 0.00 or new_qty > move.product_qty or new_qty == move.product_qty:
            return False

        # Create a copy of the move with the new quantity
        context.update({'keepLineNumber': True})
        new_move_id = move_obj.copy(cr, uid, move_id, {'product_qty': new_qty}, context=context)
        context.pop('keepLineNumber')

        # Update the original move
        update_qty = move.product_qty - new_qty
        move_obj.write(cr, uid, move_id, {'product_qty': update_qty}, context=context)

        # Set the new move to available
        move_obj.action_confirm(cr, uid, [new_move_id], context=context)
        move_obj.action_assign(cr, uid, [new_move_id])
        move_obj.force_assign(cr, uid, [new_move_id])

        return new_move_id

    def get_json_data(self, cr, uid, ids, json_data, context=None):
        if context is None:
            context = {}

        line_data = []
        for line in json_data:
            line_data.append({
                'imp_line_number': line.get('line_number', False),
                'imp_product_code': line.get('product_code', False),
                'imp_product_qty': line.get('product_qty', False),
                'imp_prodlot_id': line.get('prodlot_id', False),
                'imp_expired_date': line.get('expired_date', False),
                'imp_from_pack': line.get('from_pack', False),
                'imp_to_pack': line.get('to_pack', False),
                'imp_weight': line.get('weight', False),
                'imp_pack_type': False,  # Not modifiable by SDE import
            })

        return line_data

    def get_excel_data(self, cr, uid, ids, rows, context=None):
        if context is None:
            context = {}

        line_data = []
        message = ''
        line_num = 0
        header_index = context.get('header_index', {})
        for i, row in enumerate(rows):
            line_num += 1
            col_count = len(row)
            template_col_count = len(list(header_index.items()))
            if col_count != template_col_count:
                message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") \
                           % (line_num, template_col_count, ', '.join([_(col) for col in ppl_columns_lines_for_import]))
                continue
            try:
                if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                    continue

                cell_expiry_date = self.pool.get('import.cell.data').get_expired_date(cr, uid, ids, row, 6, [], False, context=context)
                line_data.append({
                    'imp_line_number': row.cells[0] and row.cells[0].data or False,
                    'imp_product_code': row.cells[1] and row.cells[1].data or False,
                    'imp_product_qty': row.cells[4] and row.cells[4].data or False,
                    'imp_prodlot_id': row.cells[5] and row.cells[5].data or False,
                    'imp_expired_date': cell_expiry_date or (row.cells[6] and row.cells[6].data) or False,
                    'imp_from_pack': row.cells[11] and row.cells[11].data or False,
                    'imp_to_pack': row.cells[12] and row.cells[12].data or False,
                    'imp_weight': row.cells[13] and row.cells[13].data or False,
                    'imp_pack_type': row.cells[15] and row.cells[15].data or False,
                })
            except Exception as e:
                message += _('An error has occurred for the line %s in the Excel file. Details : %s') % (line_num, e)
                continue

        return line_data, message

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        # Objects
        wiz_common_import = self.pool.get('wiz.common.import')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        pack_type_obj = self.pool.get('pack.type')
        ppl_proc_obj = self.pool.get('ppl.processor')

        context = context is None and {} or context
        if context.get('sde_flow'):
            cr = dbname
        else:
            cr = pooler.get_db(dbname).cursor()

        # Variables
        context.update({'import_in_progress': True, 'import_ppl_to_create_ship': True, 'noraise': True})
        start_time = time.time()
        message = ''
        error_log = ''
        # List of sequences for from_pack and to_pack
        sequences = []
        # List of pack types per sequence
        seq_pack_types = {}

        wiz_browse = self.browse(cr, uid, ids[0], context)
        # List of data to update moves
        updated_data = []
        # Check if all the qty of each product is treated
        sum_qty = {}
        complete_lines, lines_to_correct = 0, 0
        line_num = 0
        try:
            picking = wiz_browse.picking_id

            error_list = []
            if wiz_browse.json_text:  # SDE import only
                json_data = json.loads(wiz_browse.json_text)
                line_data = self.get_json_data(cr, uid, ids, json_data.get('move_lines', []), context=context)
            else:
                file_obj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_browse.file))
                # iterator on rows
                rows = file_obj.getRows()
                # get the lines corresponding to the header data
                header_data = []
                for i, row in enumerate(rows):
                    header_data.append(wiz_common_import.get_line_values(
                        cr, uid, ids, row, cell_nb=False, error_list=False, line_num=i, context=context))
                    if i >= 7:
                        break
                self._check_main_header_data(header_data, picking, context)
                # ignore the lines headers
                current_row = next(rows)
                if not current_row.cells:
                    next(rows)
                line_data, message = self.get_excel_data(cr, uid, ids, rows, context=context)

            percent_completed = 0
            total_line_num = len(line_data)
            # List of lines treated
            treated_lines = []
            for i, line in enumerate(line_data):
                line_num += 1
                # default values
                to_update = {
                    'warning_list': [],
                    'to_correct_ok': False,
                    'show_msg_ok': False,
                    'move_id': False,
                    'line_number': line_num,
                    'quantity': 0.0,
                    'num_of_packs': 0,
                    'uom': False,
                    'pack_type': False,
                }
                line_errors = []

                try:
                    # Line Number
                    imp_line_num = False
                    if line.get('imp_line_number'):
                        if not isinstance(line['imp_line_number'], int):
                            line_errors.append(_(' The Line Number has to be an integer.'))
                        else:
                            imp_line_num = line['imp_line_number']
                    else:
                        line_errors.append(_(' The Line Number has to be defined.'))

                    # Qties
                    imp_qty = 0.0
                    if line.get('imp_product_qty'):
                        try:
                            imp_qty = float(line['imp_product_qty'])
                            to_update.update({'quantity': imp_qty})
                        except:
                            line_errors.append(_(' The Total Qty to pack has to be an integer or a float.'))
                    else:
                        line_errors.append(_(' The Total Qty to Pack has to be defined.'))

                    # Check move's data
                    if line.get('imp_product_code'):
                        if imp_line_num:
                            move_domain = [
                                ('id', 'not in', treated_lines),
                                ('picking_id', '=', wiz_browse.picking_id.id),
                                ('line_number', '=', imp_line_num),
                                ('product_id.default_code', '=', line['imp_product_code'].upper()),
                                ('state', '=', 'assigned'),
                            ]
                            if line.get('imp_prodlot_id'):
                                move_domain.append(('prodlot_id.name', '=', line['imp_prodlot_id']))
                            if line.get('imp_expired_date'):
                                try:
                                    if isinstance(line['imp_expired_date'], str):
                                        line['imp_expired_date'] = datetime.strptime(line['imp_expired_date'], '%Y-%m-%d')
                                    else:
                                        line['imp_expired_date'] = datetime(line['imp_expired_date'].year, line['imp_expired_date'].month, line['imp_expired_date'].day)
                                except Exception as e:
                                    line_errors.append(_(' The Expiry Date (%s) does not have a good date format.')
                                                       % (line['imp_expired_date'],))
                                    line['imp_expired_date'] = False
                                if line.get('imp_expired_date'):
                                    move_domain.append(('expired_date', '=', line['imp_expired_date']))

                            # Save qties by line
                            if sum_qty.get(imp_line_num):
                                sum_qty[imp_line_num] += imp_qty
                            else:
                                sum_qty[imp_line_num] = imp_qty

                            exact_move_domain = [x for x in move_domain]
                            exact_move_domain.append(('product_qty', '=', imp_qty))
                            exact_move_id = move_obj.search(cr, uid, exact_move_domain, limit=1, context=context)
                            ftf = ['line_number', 'product_id', 'product_qty', 'product_uom']
                            if exact_move_id:
                                move = move_obj.browse(cr, uid, exact_move_id[0], fields_to_fetch=ftf, context=context)
                                to_update.update({
                                    'move_id': move.id,
                                    'uom': move.product_uom or move.product_id and move.product_id.uom_id,
                                })
                                treated_lines.append(to_update['move_id'])
                            else:
                                move_ids = move_obj.search(cr, uid, move_domain, context=context)
                                for move in move_obj.browse(cr, uid, move_ids, fields_to_fetch=ftf, context=context):
                                    if imp_qty < move.product_qty:
                                        new_move_id = self.split_move(cr, uid, move.id, imp_qty, context=context)
                                        if not new_move_id:
                                            line_errors.append(_(' The Line could not be split. Please ensure that the new quantity is above 0 and less than the original line\'s quantity.'))
                                        else:
                                            to_update.update({
                                                'move_id': new_move_id,
                                                'uom': move.product_uom or move.product_id and move.product_id.uom_id,
                                            })
                                            treated_lines.append(new_move_id)
                                        break
                    else:
                        line_errors.append(_(' The Product Code has to be defined.'))

                    if not to_update.get('move_id'):
                        non = _('None')
                        line_errors.append(_(' The imported line\'s data (Line number: %s, Product: %s, Batch: %s) does not match %s\'s data.')
                                           % (imp_line_num or non, line.get('imp_product_code') or non,
                                              line.get('imp_prodlot_id') or non, wiz_browse.picking_id.name or non))

                    # from pack and to pack
                    if line.get('imp_from_pack') and line.get('imp_to_pack') and isinstance(line['imp_from_pack'], int) \
                            and isinstance(line['imp_to_pack'], int) and line['imp_from_pack'] > 0 and line['imp_to_pack'] > 0:
                        to_update.update({
                            'from_pack': line['imp_from_pack'],
                            'to_pack': line['imp_to_pack'],
                        })
                    elif line.get('imp_from_pack') and line.get('imp_to_pack') and \
                            (not isinstance(line['imp_from_pack'], int) or not isinstance(line['imp_to_pack'], int)):
                        line_errors.append(_(' From pack and To pack have to be integers.'))
                    else:
                        to_update.update({
                            'from_pack': 1,
                            'to_pack': 1,
                        })
                        line_errors.append(_(' From pack and To pack to be defined and over 0, set to 1 by default.'))

                    # Sequence check and Number of packs
                    if to_update.get('from_pack') and to_update.get('to_pack'):
                        sequences.append((to_update['from_pack'], to_update['to_pack'], i + 1))
                        to_update.update({
                            'num_of_packs': to_update['to_pack'] - to_update['from_pack'] + 1,
                        })

                    # weight per pack
                    if line.get('imp_weight') and (isinstance(line['imp_weight'], int) or isinstance(line['imp_weight'], float)) \
                            and line['imp_weight'] > 0:
                        to_update.update({
                            'weight': line['imp_weight'],
                        })
                    elif line.get('imp_weight') and not isinstance(line['imp_weight'], int) and not isinstance(line['imp_weight'], float):
                        line_errors.append(_(' Weight per pack has to be an float.'))

                    # pack type + width, length & height
                    pack_type_name = False
                    if not wiz_browse.json_text and line.get('imp_pack_type'):
                        pack_type_ids = pack_type_obj.search(cr, uid, [('name', '=', tools.ustr(line['imp_pack_type']))])
                        if pack_type_ids:
                            # Taking the last id because LOOKUP in Excel will choose the last item in a list with same names
                            pack_type = pack_type_obj.browse(cr, uid, pack_type_ids[-1])
                            pack_type_name = pack_type.name
                            to_update.update({
                                'pack_type': pack_type
                            })
                        else:
                            line_errors.append(_(' This Pack Type doesn\'t exists.'))
                    # List to display an error if two of more sequences have different pack types
                    if to_update.get('from_pack') and to_update.get('to_pack'):
                        current_seq = '%s-%s' % (to_update['from_pack'], to_update['to_pack'])
                        pack_type_data = pack_type_name or _('none')
                        if seq_pack_types.get(current_seq):
                            if pack_type_data != seq_pack_types[current_seq]:
                                line_errors.append(_(' The Parcel %s to %s contain multiple pack types (%s instead of %s). Please assign only one Pack Type per parcel.')
                                                   % (to_update['from_pack'], to_update['to_pack'], pack_type_data, seq_pack_types[current_seq]))
                        else:
                            seq_pack_types[current_seq] = pack_type_data

                    to_update.update({
                        'error_list': line_errors,
                        'to_correct_ok': any(line_errors),
                        # the lines with to_correct_ok=True will be red
                        'show_msg_ok': any(to_update['warning_list']),
                        # the lines with show_msg_ok=True won't change color, it is just info
                        'text_error': '\n'.join(line_errors + to_update['warning_list']),
                    })

                    # update move line on picking
                    if to_update['error_list']:
                        error_list += [_('Line %s:') % (line_num,)] + to_update['error_list']
                        if wiz_browse.json_text:
                            error_list += [' ']
                        else:
                            error_list += ['\n']
                        lines_to_correct += 1
                        raise osv.except_osv(_('Error'), ''.join(x for x in to_update['error_list']))
                    updated_data.append(to_update)
                    complete_lines += 1
                    percent_completed = float(line_num) / float(total_line_num) * 100.0
                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    if wiz_browse.json_text:
                        message += _("Line number %s in the JSON: %s: %s ") % (line.get('imp_line_number', line_num), osv_name, osv_value)
                    else:
                        message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                    percent_completed = float(line_num) / float(total_line_num) * 100.0
                    cr.rollback()
                    continue
                finally:
                    self.write(cr, uid, ids, {'percent_completed': percent_completed})
        except Exception as e:
            cr.rollback()
            error_log += _("An error is occurred. Details : %s") % e
        finally:
            error_log += ''.join(error_list)
            if error_log:
                if wiz_browse.json_text:
                    error_log = _("Reported errors : ") + error_log
                else:
                    error_log = _("Reported errors : \n") + error_log

            # checking integrity of from_pack and to_pack
            from_to_pack_errors = ''
            if sequences:
                from_to_pack_errors = ppl_proc_obj.check_sequences(cr, uid, sequences, False, context=context)
                if from_to_pack_errors:
                    if wiz_browse.json_text:
                        from_to_pack_errors = _("From pack - To pack sequences errors : ") + from_to_pack_errors
                    else:
                        from_to_pack_errors = _("From pack - To pack sequences errors : \n") + from_to_pack_errors

            # Check qties
            qty_errors = ''
            cr.execute('''SELECT m.line_number, p.default_code, SUM(product_qty) FROM stock_move m, product_product p
                WHERE m.product_id = p.id AND m.picking_id = %s AND m.state = 'assigned' 
                GROUP BY m.line_number, p.default_code''', (wiz_browse.picking_id.id,))
            for prod in cr.fetchall():
                if sum_qty.get(prod[0]) and sum_qty[prod[0]] != prod[2]:
                    if wiz_browse.json_text:
                        qty_errors += _('Line number %s: The imported Quantities for %s don\'t match with the PPL (%s instead of %s). ') \
                            % (prod[0], prod[1], sum_qty[prod[0]], prod[2])
                    else:
                        qty_errors += _('Line number %s: The imported Quantities for %s don\'t match with the PPL (%s instead of %s).\n') \
                            % (prod[0], prod[1], sum_qty[prod[0]], prod[2])
            if qty_errors:
                if wiz_browse.json_text:
                    qty_errors = _('Quantities errors : ') + qty_errors
                else:
                    qty_errors = _('Quantities errors : \n') + qty_errors

            if not error_log and not from_to_pack_errors and not qty_errors:
                for data in updated_data:
                    if data.get('move_id'):
                        vals = {
                            'ordered_quantity': data['quantity'],
                            'from_pack': data['from_pack'],
                            'to_pack': data['to_pack'],
                            'pack_type': data.get('pack_type') and data['pack_type'].id or False,
                            'weight': data.get('weight', 0.0),
                            'width': data.get('pack_type') and data['pack_type'].width or data.get('width', 0),
                            'length': data.get('pack_type') and data['pack_type'].length or data.get('length', 0),
                            'height': data.get('pack_type') and data['pack_type'].height or data.get('height', 0),
                        }
                        move_obj.write(cr, uid, data['move_id'], vals, context=context)
            if error_log or from_to_pack_errors or qty_errors:
                cr.rollback()

            end_time = time.time()
            total_time = str(round(end_time - start_time)) + _(' second(s)')
            final_message = _('''    Importation completed in %s!
    # of lines without error : %s of %s lines
    # of lines to correct: %s
    
    %s
    
    %s
    
    %s
    ''') % (total_time, complete_lines, line_num, lines_to_correct, error_log, qty_errors, from_to_pack_errors)
            wizard_vals = {'message': final_message, 'state': 'done', 'percent_completed': 100}
            self.write(cr, uid, ids, wizard_vals, context=context)
            # we reset the state of the PPL to assigned (initial state)
            pick_obj.write(cr, uid, wiz_browse.picking_id.id, {'state': 'assigned'}, context)

            cr.commit()
            if not context.get('sde_flow'):
                cr.close(True)

        if context.get('sde_flow'):
            return error_log, qty_errors, from_to_pack_errors
        else:
            return True

    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        wiz_common_import = self.pool.get('wiz.common.import')
        pick_obj = self.pool.get('stock.picking')
        for wiz_read in self.browse(cr, uid, ids, context=context):
            picking_id = wiz_read.picking_id.id
            if wiz_read.picking_id.state != 'assigned':
                return self.write(cr, uid, ids, {'message': _('%s must be \'Available\' to use the import') % wiz_read.picking_id.name})
            if not wiz_read.file:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_read.file))
                # iterator on rows
                reader = fileobj.getRows()
                # get the lines corresponding to the header data
                header_data = []
                for i, row in enumerate(reader):
                    header_data.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=False, line_num=i, context=context))
                    if i >= 7:
                        break
                if len([row for row in fileobj.getRows()]) < 11 and len(header_data) != 8:
                    raise osv.except_osv(_('Error'), _('Please select a file with the same model as the PPL Excel Export'))
                else:
                    self._check_main_header_names(header_data, context)
                reader_iterator = iter(reader)
                # get first lines headers
                lines_header_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, lines_header_row, error_list=[], line_num=0, context=context)
                # ignore the blank line if there's one
                if not header_index:
                    header_index = wiz_common_import.\
                        get_header_index(cr, uid, ids, next(reader_iterator), error_list=[], line_num=0, context=context)
                context.update({'picking_id': picking_id, 'header_index': header_index})
                res, res1 = wiz_common_import.\
                    check_header_values(cr, uid, ids, context, header_index, ppl_columns_lines_for_import)
                if not res:
                    return self.write(cr, uid, ids, res1, context)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})

            pick_obj.write(cr, uid, picking_id, {'state': 'import'}, context)

        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, int):
            ids = [ids]
        pick_obj = self.pool.get('stock.picking')
        for wiz_read in self.read(cr, uid, ids, ['picking_id', 'state', 'file']):
            picking_id = wiz_read['picking_id']
            int_name = pick_obj.read(cr, uid, picking_id, ['name'])['name']
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': _(
                    ' Import in progress... \n Please wait that the import is finished before editing %s.') % (
                    int_name,)})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, int):
            ids = [ids]
        for wiz_obj in self.browse(cr, uid, ids, context=context):
            picking_id = wiz_obj.picking_id
            res = self.pool.get('ir.actions.act_window').\
                open_view_from_xmlid(cr, uid, 'msf_outgoing.action_ppl', ['form', 'tree'], context=context)
            res['res_id'] = picking_id.id
            return res

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return self.cancel(cr, uid, ids, context=context)


wizard_import_ppl_to_create_ship()
