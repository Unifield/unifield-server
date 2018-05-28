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
            if header_data[0][2] != picking.name:
                error_log += _(' The Packing reference in the file doesn\'t match the one from the Pre-Packing header.')
        if not header_data[3][2]:
            error_log += _(' Our Ref (origin) is mandatory.')
        else:
            if header_data[3][2] != picking.origin:
                error_log += _(' Our Ref (origin) in the file doesn\'t match the one from the Pre-Packing header.')

        if error_log:
            raise osv.except_osv(_('Error'), error_log)

        return True

    def _check_from_to_pack_integrity(self, sequences=None, context=None):
        '''
        Check if nothing is wrong with from_pack and to_pack
        '''
        if context is None:
            context = {}
        error_log = ''

        if sequences:
            # Sort the sequence according to from value
            sequences = sorted(sequences, key=lambda seq: seq[0])

            # Rule #1, the first from value must be equal to 1
            if sequences[0][0] != 1:
                error_log += _('The first From pack must be equal to 1.\n')

            # Go through the list of sequences applying the rules
            for i in range(len(sequences)):
                seq = sequences[i]
                # Rules #2-#3 applies from second element
                if i > 0:
                    # Previous sequence
                    seqb = sequences[i - 1]
                    # Rule #2: if from[i] == from[i-1] -> to[i] == to[i-1]
                    if (seq[0] == seqb[0]) and not (seq[1] == seqb[1]):
                        error_log += _('The sequence From pack - To Pack of line %s overlaps a previous one.\n') % (seq[2])
                    # Rule #3: if from[i] != from[i-1] -> from[i] == to[i-1]+1
                    if (seq[0] != seqb[0]) and not (seq[0] == seqb[1] + 1):
                        if seq[0] < seqb[1] + 1:
                            error_log += _('The sequence From pack - To Pack of line %s overlaps a previous one.\n') % (seq[2])
                        if seq[0] > seqb[1] + 1:
                            error_log += _('A gap exists with the sequence From pack - To Pack of line %s.\n') % (seq[2])
                # rule #4: to[i] >= from[i]
                if not (seq[1] >= seq[0]):
                    error_log += _('To pack must be greater than From pack on line %s.\n') % (seq[2])

        return error_log

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        # Objects
        wiz_common_import = self.pool.get('wiz.common.import')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        pack_type_obj = self.pool.get('pack.type')
        import_cell_data_obj = self.pool.get('import.cell.data')

        context = context is None and {} or context
        cr = pooler.get_db(dbname).cursor()

        # Variables
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        line_with_error = []
        error_log = ''
        move_ids = False
        # List of sequences for from_pack and to_pack
        sequences = []

        for wiz_browse in self.browse(cr, uid, ids, context):
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
                to_update = {}
                total_line_num = len([row for row in file_obj.getRows()])
                percent_completed = 0
                move_ids = move_obj.search(cr, uid, [('picking_id', '=', picking.id)], order='line_number')
                # List of data to update moves
                updated_data = []
                for i, row in enumerate(rows):
                    line_num += 1
                    # default values
                    to_update = {
                        'error_list': [],
                        'warning_list': [],
                        'to_correct_ok': False,
                        'show_msg_ok': False,
                        'from_pack': 1,
                        'to_pack': 1,
                        'weight': 0.00,
                        'width': 0.00,
                        'length': 0.00,
                        'height': 0.00,
                        'pack_type': False,
                    }

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

                        # Stock Move
                        m_value = check_line.pack_move_value_for_update(cr, uid, ids, move_obj=move_obj, row=row,
                                                                        to_write=to_update, pack_type_obj=pack_type_obj,
                                                                        import_cell_data_obj=import_cell_data_obj,
                                                                        move_id=move_ids[i], line_num=line_num,
                                                                        context=context)

                        to_update.update({'error_list': m_value['error_list'], 'from_pack': m_value['from_pack'],
                                          'to_pack': m_value['to_pack'], 'weight': m_value['weight'],
                                          'width': m_value['width'], 'length': m_value['length'],
                                          'height': m_value['height'], 'pack_type': m_value['pack_type']})

                        to_update.update({
                            'to_correct_ok': any(to_update['error_list']),
                            # the lines with to_correct_ok=True will be red
                            'show_msg_ok': any(to_update['warning_list']),
                            # the lines with show_msg_ok=True won't change color, it is just info
                            'text_error': '\n'.join(to_update['error_list'] + to_update['warning_list']),
                        })

                        sequences.append((m_value['from_pack'], m_value['to_pack'], i + 1))

                        # update move line on picking
                        if to_update['error_list']:
                            error_list += [_('Line %s:') % (line_num)] + to_update['error_list'] + ['\n']
                            lines_to_correct += 1
                            raise osv.except_osv(_('Error'), ''.join(x for x in m_value['error_list']))
                        updated_data.append(to_update)
                        complete_lines += 1
                        percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                    except IndexError:
                        line_with_error.append(
                            wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                              line_num=line_num, context=context))
                        percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                        continue
                    except osv.except_osv as osv_error:
                        osv_value = osv_error.value
                        osv_name = osv_error.name
                        message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                        line_with_error.append(
                            wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                              line_num=line_num, context=context))
                        percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                        continue
                    except AttributeError as e:
                        error_log += _('Line %s in the Excel file was added to the file of the lines with error, an error is occurred. Details : %s')\
                                     % (line_num, e)
                        line_with_error.append(
                            wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list,
                                                              line_num=line_num, context=context))
                        percent_completed = float(line_num) / float(total_line_num - 1) / 100.0
                        continue
                    finally:
                        self.write(cr, uid, ids, {'percent_completed': percent_completed})
            except Exception as e:
                error_log += _("An error is occurred. Details : %s") % e
                continue
            finally:
                error_log += ''.join(error_list)
                if error_log:
                    error_log = _("Reported errors : \n") + error_log

                # checking the number of lines
                if move_ids and line_num != len(move_ids):
                    error_log += _("There is %s lines in the file and %s lines in %s. Please import the same number of lines.\n") \
                                 % (line_num, len(move_ids), picking.name)
                    lines_to_correct += abs(len(move_ids) - line_num)

                # checking integrity of from_pack and to_pack
                from_to_pack_errors = self._check_from_to_pack_integrity(sequences, context=context)
                if from_to_pack_errors:
                    from_to_pack_errors = _("From pack - To pack sequences errors : \n") + from_to_pack_errors

                if not error_log and not from_to_pack_errors:
                    for i, move_data in enumerate(updated_data):
                        move_obj.write(cr, uid, [move_ids[i]], move_data, context=context)
                end_time = time.time()
                total_time = str(round(end_time - start_time)) + _(' second(s)')
                final_message = _('''    Importation completed in %s!
    # of lines without error : %s of %s lines
    # of lines to correct: %s
    %s
    %s

    %s
    ''') % (total_time, complete_lines, line_num, lines_to_correct, error_log, from_to_pack_errors, message)
                wizard_vals = {'message': final_message, 'state': 'done', 'percent_completed': 100}
                if line_with_error:
                    file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids,
                                                                              line_with_error=line_with_error,
                                                                              header_index=header_index)
                    wizard_vals.update(file_to_export)
                self.write(cr, uid, ids, wizard_vals, context=context)
                # we reset the state of the PPL to assigned (initial state)
                pick_obj.write(cr, uid, picking.id, {'state': 'assigned', 'import_in_progress': False},
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
                    check_header_values(cr, uid, ids, context, header_index, ppl_columns_lines_for_import, ignore_case=True)
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
            view_id = \
            self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, ids, context=context, pick=picking_id)[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'view_id': [view_id],
                'target': 'crush',
                'res_id': picking_id.id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz_obj in self.browse(cr, uid, ids, context=context):
            picking_id = wiz_obj.picking_id
            view_id = \
            self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, ids, context=context, pick=picking_id)[1]
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'view_id': [view_id],
                'target': 'crush',
                'res_id': picking_id.id,
                'context': context,
                }


wizard_import_ppl_to_create_ship()
