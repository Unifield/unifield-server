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
import tools
from msf_doc_import import check_line
from msf_doc_import.wizard import PPL_COLUMNS_LINES_FOR_IMPORT as ppl_columns_lines_for_import


class wizard_import_ppl_to_create_ship(osv.osv_memory):
    _name = 'wizard.import.ppl.to.create.ship'
    _description = 'Import Pack Lines from Excel sheet to create a Shipment'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        '''
        Return True if a message is set on the wizard
        '''
        res = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = obj.message or False

        return res

    _columns = {
        'file': fields.binary(string='Lines to import', required=True, readonly=True,
                              states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True, translate=True),
        'picking_id': fields.many2one('stock.picking', string='Stock Picking', required=True),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
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
        if not move_id:
            raise osv.except_osv(
                _('Error'),
                _('No line to split !'),
            )

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
        import_cell_data_obj = self.pool.get('import.cell.data')

        context = context is None and {} or context
        cr = pooler.get_db(dbname).cursor()

        # Variables
        context.update({'import_in_progress': True, 'import_ppl_to_create_ship': True, 'noraise': True})
        start_time = time.time()
        line_with_error = []
        error_log = ''
        # List of sequences for from_pack and to_pack
        sequences = []

        wiz_browse = self.browse(cr, uid, ids[0], context)
        # List of data to update moves
        updated_data = []
        # Check if all the qty of each product is treated
        sum_qty = {}
        try:
            picking = wiz_browse.picking_id

            complete_lines, lines_to_correct = 0, 0
            error_list = []
            error_log = ''
            message = ''
            line_num = 0
            header_index = context['header_index']

            file_obj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
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
            current_row = rows.next()
            if not current_row.cells:
                rows.next()
            line_num = 0
            total_line_num = len([row for row in file_obj.getRows()])
            percent_completed = 0
            # List of lines treated
            treated_lines = []
            for i, row in enumerate(rows):
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

                col_count = len(row)
                template_col_count = len(header_index.items())
                if col_count != template_col_count:
                    message += _(
                        """Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (
                        line_num, template_col_count, ','.join(ppl_columns_lines_for_import))
                    line_with_error.append(
                        wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                          line_num=line_num, context=context))
                    percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                    self.write(cr, uid, ids, {'percent_completed': percent_completed})
                    continue
                try:
                    if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                        percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                        self.write(cr, uid, ids, {'percent_completed': percent_completed})
                        line_num -= 1
                        total_line_num -= 1
                        continue

                    # Line Number
                    imp_line_num = False
                    if row.cells[0].data:
                        if row.cells[0].type != 'int':
                            line_errors.append(_(' The Line Number has to be an integer.'))
                        else:
                            imp_line_num = row.cells[0].data
                    else:
                        line_errors.append(_(' The Line Number has to be defined.'))

                    # Qties
                    imp_qty = 0.0
                    if row.cells[4].data:
                        try:
                            imp_qty = float(row.cells[4].data)
                            to_update.update({'quantity': imp_qty})
                        except:
                            line_errors.append(_(' The Total Qty to pack has to be an integer or a float.'))
                    else:
                        line_errors.append(_(' The Total Qty to Pack has to be defined.'))

                    # Check move's data
                    if row.cells[1].data:
                        if imp_line_num:
                            move_domain = [
                                ('id', 'not in', treated_lines),
                                ('picking_id', '=', wiz_browse.picking_id.id),
                                ('line_number', '=', imp_line_num),
                                ('product_id.default_code', '=', row.cells[1].data.upper()),
                                ('state', '=', 'assigned'),
                            ]
                            if row.cells[5].data:
                                move_domain.append(('prodlot_id.name', '=', row.cells[5].data))
                            if row.cells[6].data:
                                cell_expiry_date = import_cell_data_obj.\
                                    get_expired_date(cr, uid, ids, row, 6, line_errors, line_num, context=context)
                                if not cell_expiry_date:
                                    line_errors.append(_(' The Expiry Date (%s) does not have a good date format.')
                                                       % (row.cells[6].data,))
                                else:
                                    move_domain.append(('expired_date', '=', cell_expiry_date))

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
                                           % (imp_line_num or non, row.cells[1].data or non, row.cells[5].data or non,
                                              wiz_browse.picking_id.name or non))

                    # from pack and to pack
                    if row.cells[11].data and row.cells[12].data and row.cells[11].type == row.cells[
                        12].type == 'int' \
                            and row.cells[11].data > 0 and row.cells[12].data > 0:
                        to_update.update({
                            'from_pack': row.cells[11].data,
                            'to_pack': row.cells[12].data,
                        })
                    elif row.cells[11].data and row.cells[12].data and (
                            row.cells[11].type != 'int' or row.cells[12].type != 'int'):
                        line_errors.append(_(' From pack and To pack have to be integers.'))
                    else:
                        to_update.update({
                            'from_pack': 1,
                            'to_pack': 1,
                        })
                        line_errors.append(
                            _(' From pack and To pack to be defined and over 0, set to 1 by default.'))

                    # Sequence check and Number of packs
                    if to_update.get('from_pack') and to_update.get('to_pack'):
                        sequences.append((to_update['from_pack'], to_update['to_pack'], i + 1))
                        to_update.update({
                            'num_of_packs': to_update['to_pack'] - to_update['from_pack'] + 1,
                        })

                    # weight per pack
                    if row.cells[13].data and row.cells[13].type in ('int', 'float') and row.cells[13].data > 0:
                        to_update.update({
                            'weight': row.cells[13].data,
                        })
                    elif row.cells[13].data and row.cells[13].type not in ('int', 'float'):
                        line_errors.append(_(' Weight per pack has to be an float.'))

                    # pack type + width, length & height
                    if row.cells[15].data:
                        pack_type_ids = pack_type_obj.search(cr, uid, [('name', '=', tools.ustr(row.cells[15].data))])
                        if pack_type_ids:
                            pack_type = pack_type_obj.browse(cr, uid, pack_type_ids[0])
                            to_update.update({
                                'pack_type': pack_type
                            })
                        else:
                            line_errors.append(_(' This Pack Type doesn\'t exists.'))

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
                        error_list += [_('Line %s:') % (line_num)] + to_update['error_list'] + ['\n']
                        lines_to_correct += 1
                        raise osv.except_osv(_('Error'), ''.join(x for x in to_update['error_list']))
                    updated_data.append(to_update)
                    complete_lines += 1
                    percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                except IndexError:
                    line_with_error.append(
                        wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                          line_num=line_num, context=context))
                    percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                    cr.rollback()
                    continue
                except osv.except_osv as osv_error:
                    osv_value = osv_error.value
                    osv_name = osv_error.name
                    message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                    line_with_error.append(
                        wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                          line_num=line_num, context=context))
                    percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                    cr.rollback()
                    continue
                except AttributeError as e:
                    error_log += _('Line %s in the Excel file was added to the file of the lines with error, an error is occurred. Details : %s')\
                        % (line_num, e)
                    line_with_error.append(
                        wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                          line_num=line_num, context=context))
                    percent_completed = float(line_num) / float(total_line_num - 1) / 100.0
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
                error_log = _("Reported errors : \n") + error_log

            # checking integrity of from_pack and to_pack
            from_to_pack_errors = False
            if sequences:
                from_to_pack_errors = ppl_proc_obj.check_sequences(cr, uid, sequences, False, context=context)
                if from_to_pack_errors:
                    from_to_pack_errors = _("From pack - To pack sequences errors : \n") + from_to_pack_errors

            # Check qties
            qty_errors = ''
            cr.execute('''SELECT m.line_number, p.default_code, SUM(product_qty) FROM stock_move m, product_product p
                WHERE m.product_id = p.id AND m.picking_id = %s AND m.state = 'assigned' 
                GROUP BY m.line_number, p.default_code''', (wiz_browse.picking_id.id,))
            for prod in cr.fetchall():
                if sum_qty.get(prod[0]) and sum_qty[prod[0]] != prod[2]:
                    qty_errors += _('Line number %s: The imported Quantities for %s don\'t match with the PPL (%s instead of %s).\n') \
                        % (prod[0], prod[1], sum_qty[prod[0]], prod[2])
            if qty_errors:
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
            if line_with_error:
                file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids,
                                                                          line_with_error=line_with_error,
                                                                          header_index=header_index)
                wizard_vals.update(file_to_export)
            self.write(cr, uid, ids, wizard_vals, context=context)
            # we reset the state of the PPL to assigned (initial state)
            pick_obj.write(cr, uid, wiz_browse.picking_id.id, {'state': 'assigned', 'import_in_progress': False},
                           context)

            cr.commit()
            cr.close(True)

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
                fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_read.file))
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

            pick_obj.write(cr, uid, picking_id, {'state': 'import', 'import_in_progress': True}, context)

        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
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
        if isinstance(ids, (int, long)):
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
