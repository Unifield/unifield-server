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
from msf_doc_import.wizard import COLUMNS_FOR_PRODUCT_LINE_IMPORT as columns_for_product_line_import


class wizard_import_product_line(osv.osv_memory):
    _name = 'wizard.import.product.line'
    _description = 'Import Products data from Excel sheet'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'product_mass_upd_id': fields.many2one('product.mass.update', string='Product Mass Update', required=True),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
    }

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        cr = pooler.get_db(dbname).cursor()

        if context is None:
            context = {}
        wiz_common_import = self.pool.get('wiz.common.import')
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        product_obj = self.pool.get('product.product')
        p_mass_upd_obj = self.pool.get('product.mass.update')
        line_with_error = []

        # Get the expected product creator id
        instance_level = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.level

        for wiz_browse in self.browse(cr, uid, ids, context):
            p_mass_upd_id = wiz_browse.product_mass_upd_id.id
            prod_creator_id = product_obj._get_authorized_creator(cr, uid, bool(wiz_browse.product_mass_upd_id.type_of_ed_bn), context)
            try:
                product_ids = [prod.id for prod in wiz_browse.product_mass_upd_id.product_ids]

                ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
                line_ignored_num = []
                error_list = []
                error_log = ''
                message = ''
                line_num = 0
                header_index = context['header_index']
                mandatory_col_count = 1  # ignore Status column

                file_obj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_browse.file))
                rows = file_obj.getRows()

                header_row = next(rows)
                header_error = False

                if len(header_row) != mandatory_col_count and len(header_row) != len(columns_for_product_line_import):
                    header_row = False
                    header_error = True
                    error_list.append(_("\n\tNumber of columns is not equal to %s") % len(columns_for_product_line_import))

                if header_row:
                    for i, h_name in enumerate(columns_for_product_line_import):
                        # To be able to import without Status column
                        if h_name != 'state' or len(header_row) != mandatory_col_count:
                            tr_header_row = _(tools.ustr(header_row[i]))
                            tr_h_name = _(h_name)
                            if len(header_row) > i and tr_header_row != tr_h_name:
                                header_error = True
                                if tr_header_row.upper() == tr_h_name.upper():
                                    error_list.append(_("\n\tPlease check spelling on column '%s'.") % tr_header_row)

                if header_error:
                    msg = _("\n\tYou can not import this file because the header of columns doesn't match with the expected headers: %s") % ','.join([_(x) for x in columns_for_product_line_import])
                    error_list.append(msg)
                    msg = _("\n\tPlease ensure that all these columns are present and in this exact order.")
                    error_list.append(msg)

                if not error_list:
                    # iterator on rows
                    rows = file_obj.getRows()
                    next(rows) # skip header
                    # ignore the first row

                    line_num = 0
                    total_line_num = file_obj.getNbRows()
                    percent_completed = 0
                    for row in rows:
                        line_num += 1
                        error_list_line = []

                        col_count = len(row)
                        template_col_count = len(list(header_index.items()))
                        if col_count != template_col_count and col_count != mandatory_col_count:
                            message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (line_num, template_col_count,','.join([_(x) for x in columns_for_product_line_import]))
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            self.write(cr, uid, ids, {'percent_completed': percent_completed})
                            continue
                        try:
                            if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                                percent_completed = float(line_num)/float(total_line_num-1)*100.0
                                self.write(cr, uid, ids, {'percent_completed': percent_completed})
                                line_num -= 1
                                total_line_num -= 1
                                continue

                            # Cell 0: Product
                            if row[0]:
                                prod_ids = product_obj.search(cr, uid, [('default_code', '=ilike', row[0].data),
                                                                        ('active', 'in', ['t', 'f']), ('replaced_by_product_id', '=', False)], context=context)
                                if prod_ids and prod_ids[0] not in product_ids:
                                    prod = product_obj.browse(cr, uid, prod_ids[0], fields_to_fetch=['international_status'], context=context)
                                    if prod_creator_id and prod.international_status.id in prod_creator_id:
                                        product_ids.append(prod.id)
                                    else:
                                        if instance_level == 'section':
                                            if wiz_browse.product_mass_upd_id.type_of_ed_bn:
                                                error_list_line.append(_('Product %s doesn\'t have the expected Product Creator. ')
                                                                       % (row[0].data,))
                                            else:
                                                error_list_line.append(_('Product %s doesn\'t have the expected Product Creator "ITC", "ESC" or "HQ". ')
                                                                       % (row[0].data,))
                                        elif instance_level == 'coordo':
                                            error_list_line.append(_('Product %s doesn\'t have the expected Product Creator "Local". ')
                                                                   % (row[0].data,))
                                        else:
                                            error_list_line.append(_('You must be on Coordo or HQ instance to add products to the list. '))
                                elif not prod_ids:
                                    error_list_line.append(_('Product code %s doesn\'t exist in the DB. ') % (row[0].data,))
                            else:
                                error_list_line.append(_('Product code is mandatory. '))

                            if error_list_line:
                                lines_to_correct += 1
                                line_txt = _('Line %s: ') % (line_num,)
                                error_list.append(line_txt + ' '.join(error_list_line))

                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            complete_lines += 1

                        except IndexError as e:
                            error_log += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s") % (line_num, template_col_count, e)
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.rollback()
                            continue
                        except osv.except_osv as osv_error:
                            osv_value = osv_error.value
                            osv_name = osv_error.name
                            message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                            ignore_lines += 1
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.rollback()
                            continue
                        finally:
                            self.write(cr, uid, ids, {'percent_completed': percent_completed})
                            cr.commit()

                # Update products
                if wiz_browse.product_mass_upd_id.type_of_ed_bn and len(product_ids) > 500:
                    nb_in_file = len(product_ids)
                    ignore_lines += nb_in_file - 500
                    product_ids = product_ids[0:500]
                    error_list.append(_('Import is limited to 500 products, %d lines ignored') % (nb_in_file - 500))

                p_mass_upd_obj.write(cr, uid, p_mass_upd_id, {'product_ids': [(6, 0, product_ids)]}, context=context)

                error_log += '\n'.join(error_list)
                if error_log:
                    error_log = _("Reported errors for ignored lines : \n") + error_log
                end_time = time.time()
                total_time = tools.ustr(round(end_time-start_time)) + _(' second(s)')
                final_message = _('''
    Importation completed in %s!
# of imported lines : %s on %s lines
# of ignored lines: %s
# of lines to correct: %s
    %s

    %s
    ''') % (total_time ,complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
                wizard_vals = {'message': final_message, 'state': 'done'}
                if line_with_error:
                    file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
                    wizard_vals.update(file_to_export)
                self.write(cr, uid, ids, wizard_vals, context=context)
                # we reset the state of the FO to draft (initial state)
            except Exception as e:
                self.write(cr, uid, ids, {
                    'message': _('An unknow error occurred, please contact the support team. Error message: %s') % tools.ustr(e),
                    'state': 'done',
                }, context=context)
            finally:
                p_mass_upd_obj.write(cr, uid, p_mass_upd_id, {'state': 'draft', 'import_in_progress': False}, context)
        cr.commit()
        cr.close(True)

    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        wiz_common_import = self.pool.get('wiz.common.import')
        p_mass_upd_obj = self.pool.get('product.mass.update')
        for wiz_read in self.browse(cr, uid, ids, fields_to_fetch=['product_mass_upd_id', 'file'], context=context):
            p_mass_upd = wiz_read.product_mass_upd_id
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            if p_mass_upd.state != 'draft':
                return self.write(cr, uid, ids, {'state': 'done', 'message': _("You can only import on a Draft Product Mass Update; import file is ignored")}, context=context)
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_read.file))
                # iterator on rows
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'p_mass_upd_id': p_mass_upd.id, 'header_index': header_index})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_product_line_import, origin='')
                if not res:
                    return self.write(cr, uid, ids, res1, context)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
            except StopIteration:
                return self.write(cr, uid, ids, {'message': _('The file has no row, nothing to import')})
            p_mass_upd_obj.write(cr, uid, p_mass_upd.id, {'state': 'done', 'import_in_progress': True}, context)
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
        for wiz_read in self.read(cr, uid, ids, ['fo_id', 'state', 'file']):
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing.')})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, int):
            ids=[ids]
        wiz_obj = self.browse(cr, uid, ids[0], fields_to_fetch=['product_mass_upd_id'])
        p_mass_upd_id = wiz_obj.product_mass_upd_id.id
        if wiz_obj.product_mass_upd_id.type_of_ed_bn:
            xmlid = 'product.products_bn_ed_mass_update_action'
        else:
            xmlid = 'product.previous_mass_update_action'

        act = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, xmlid, ['form', 'tree'], context=context)
        act['res_id'] = p_mass_upd_id
        return act

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return self.cancel(cr, uid, ids, context=context)


wizard_import_product_line()
