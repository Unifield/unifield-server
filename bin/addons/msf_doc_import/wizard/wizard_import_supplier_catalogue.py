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

import threading
import time
import datetime
import base64

import pooler

from osv import osv
from osv import fields
from tools.translate import _
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator

from msf_doc_import.wizard import SUPPLIER_CATALOG_COLUMNS_FOR_IMPORT as columns_for_supplier_catalogue_import
from tools.misc import ustr

help_message = _("""
You can use the template of the export for the format that you need to use.
The file should be in XML Spreadsheet 2003 format.
The columns should be in this order (* indicates that the field cannot be empty):
  - Product Code*
  - Product Description
  - Supplier Code
  - UoM*
  - Min. Qty*
  - Unit Price*
  - SoQ Rounding
  - Min. Order Qty
  - Comment
""")


class wizard_import_supplier_catalogue(osv.osv_memory):
    _name = 'wizard.import.supplier.catalogue'
    _rec_name = 'catalogue_id'

    _columns = {
        'file': fields.binary(
            string='File to import',
            filters='*.xml',
            help=help_message,
        ),
        'message': fields.text(
            string='Message',
            readonly=True,
        ),
        'catalogue_id': fields.many2one(
            'supplier.catalogue',
            string='Catalogue',
            required=True,
            ondelete='cascade',
        ),
        'data': fields.binary(
            string='Lines with errors',
        ),
        'filename': fields.char(
            string='Lines with errors',
            size=256,
        ),
        'filename_template': fields.char(
            string='Templates',
            size=256,
        ),
        'import_error_ok': fields.boolean(
            string="Show column errors",
            store=False,
        ),
        'percent_completed': fields.integer(
            string='% completed',
            readonly=True,
        ),
        'state': fields.selection(
            selection=[
                ('draft', 'Draft'),
                ('in_progress', 'In Progress'),
                ('done', 'Done'),
            ],
            string="State",
            required=True,
            readonly=True,
        ),
    }

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        """
        Export lines with errors in a file.
        Warning: len(columns_header) == len(lines_not_imported)
        """
        columns_header = [('Product code*', 'string'), ('Product description', 'string'), ('Supplier Code', 'string'), ('Product UoM*', 'string'),
                          ('Min Quantity*', 'number'), ('Unit Price*', 'number'), ('SoQ Rounding', 'number'), ('Min Order Qty', 'number'),
                          ('Comment', 'string')]
        lines_not_imported = [] # list of list
        t_dt = type(datetime.datetime.now())
        for line in kwargs.get('line_with_error'):
            for f in line:
                if type(f) == t_dt:
                    new_f = f.strftime('%Y-%m-%dT%H:%M:%S.000')
                    line[line.index(f)] = (new_f, 'DateTime')
                elif isinstance(f, str) and 0 <= line.index(f) < len(columns_header) and columns_header[line.index(f)][1] != 'string':
                    try:
                        line[line.index(f)] = (float(f), 'Number')
                    except:
                        line[line.index(f)] = (f, 'String')

            if len(line) < len(columns_header):
                lines_not_imported.append(line + ['' for x in range(len(columns_header)-len(line))])
            else:
                lines_not_imported.append(line)

        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml(['decode.utf8'])),
                'filename': 'Lines_Not_Imported.xls',
                'import_error_ok': True}
        return vals

    def _import(self, cr, uid, ids, context=None):
        '''
        Import the catalogue lines
        '''
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        wiz_common_import = self.pool.get('wiz.common.import')
        obj_catalog_line = self.pool.get('supplier.catalogue.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        vals = {}
        error_list, line_with_error = [], []
        error_log = ''
        start_time = time.time()

        cr = pooler.get_db(cr).cursor()


        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.file:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))

            fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file))
            rows,reader = fileobj.getRows(), fileobj.getRows() # because we got 2 iterations
            # take all the lines of the file in a list of dict
            file_values = wiz_common_import.get_file_values(cr, uid, ids, rows, False, error_list, False, context)
            total_line_num = len([row for row in fileobj.getRows()])
            percent_completed = 0
            ignore_lines, complete_lines = 0, 0

            reader.next()
            line_num = 1
            for row in reader:
                error_list_line = []
                to_correct_ok = False
                row_len = len(row)
                if row_len != 9:
                    all_empty = True
                    for x in range(0, row_len):
                        if row.cells[x].data:
                            all_empty = False
                            break

                    if all_empty:
                        continue

                    error_list_line.append(_("You should have exactly 9 columns in this order: Product code*, Product description, Supplier Code, Product UoM*, Min Quantity*, Unit Price*, SoQ Rounding, Min Order Qty, Comment."))
                comment = []
                p_comment = False
                catalog_line_id = False
                try:
                    #Product code
                    try:
                        product_code = row.cells[0].data
                    except TypeError:
                        product_code = row.cells[0].data
                    except ValueError:
                        product_code = row.cells[0].data
                    if not product_code or row.cells[0].type != 'str':
                        default_code = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]
                        to_correct_ok = True
                        error_list_line.append(_("The product was not defined properly."))
                    else:
                        try:
                            product_code = product_code.strip()
                            code_ids = product_obj.search(cr, uid, [('default_code', '=ilike', product_code)])
                            if not code_ids:
                                default_code = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]
                                to_correct_ok = True
                                error_list_line.append(_("The product '%s' was not found.") % product_code)
                            else:
                                default_code = code_ids[0]
                        except Exception:
                            default_code = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]
                            to_correct_ok = True
                            error_list_line.append(_("The product '%s' was not found.") % product_code)

                    supplier_code = len(row.cells)>=3 and row.cells[2].data
                    #Product UoM
                    p_uom = len(row.cells)>=4 and row.cells[3].data
                    if not p_uom:
                        uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
                        to_correct_ok = True
                        error_list_line.append(_("The UoM '%s' was not found.") % p_uom)
                    else:
                        try:
                            uom_name = p_uom.strip()
                            uom_ids = uom_obj.search(cr, uid, [('name', '=ilike', uom_name)], context=context)
                            if not uom_ids:
                                uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
                                error_list_line.append(_("The UoM '%s' was not found.") % uom_name)
                                to_correct_ok = True
                            else:
                                uom_id = uom_ids[0]
                        except Exception:
                            uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
                            error_list_line.append(_("The UoM '%s' was not found.") % p_uom)
                            to_correct_ok = True
                    #[utp-129]: check consistency of uom
                    # I made the check on uom_id according to the constraint _check_uom in unifield-addons/product/product.py (l.744) so that we keep the consistency even when we create a supplierinfo directly from the product
                    if default_code != obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]:
                        if not self.pool.get('uom.tools').check_uom(cr, uid, default_code, uom_id, context):
                            browse_uom = uom_obj.browse(cr, uid, uom_id, context)
                            browse_product = product_obj.browse(cr, uid, default_code, context)
                            uom_id = browse_product.uom_id.id
                            to_correct_ok = True
                            error_list_line.append(_('The UoM "%s" was not consistent with the UoM\'s category ("%s") of the product "%s".'
                                                     ) % (browse_uom.name, browse_product.uom_id.category_id.name, browse_product.default_code))

                    #Product Min Qty
                    if not len(row.cells)>=5 or not row.cells[4].data :
                        p_min_qty = 1.0
                    else:
                        if row.cells[4].type in ['int', 'float']:
                            p_min_qty = row.cells[4].data
                        else:
                            error_list_line.append(_('Please, format the line number %s, column "Min Qty".') % (line_num,))

                    #Product Unit Price
                    if not len(row.cells)>=6 or not row.cells[5].data:
                        p_unit_price = 1.0
                        to_correct_ok = True
                        comment.append('Unit Price defined automatically as 1.00')
                    else:
                        if row.cells[5].type in ['int', 'float']:
                            p_unit_price = row.cells[5].data
                        else:
                            error_list_line.append(_('Please, format the line number %s, column "Unit Price".') % (line_num,))

                    #Product Rounding
                    if not len(row.cells)>=7 or not row.cells[6].data:
                        p_rounding = False
                    else:
                        if row.cells[6] and row.cells[6].type in ['int', 'float']:
                            p_rounding = row.cells[6].data
                        else:
                            error_list_line.append(_('Please, format the line number %s, column "SoQ rounding".') % (line_num,))

                    #Product Min Order Qty
                    if not len(row.cells)>=8 or not row.cells[7].data:
                        p_min_order_qty = 0
                    else:
                        if row.cells[7].type in ['int', 'float']:
                            p_min_order_qty = row.cells[7].data
                        else:
                            error_list_line.append(_('Please, format the line number %s, column "Min Order Qty".') % (line_num,))

                    #Product Comment
                    if len(row.cells)>=9 and row.cells[8].data:
                        comment.append(ustr(row.cells[8].data))
                    if comment:
                        p_comment = ', '.join(comment)

                    if error_list_line:
                        error_list_line.insert(0, _('Line %s of the file was exported in the file of the lines not imported:') % (line_num,))
                        data = file_values[line_num].items()
                        line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                        ignore_lines += 1
                        line_num += 1
                        error_list.append('\n -'.join(error_list_line) + '\n')
                        continue
                    line_num += 1

                    # [utp-746] update prices of an already product in catalog
                    criteria = [
                        ('catalogue_id', '=', obj.catalogue_id.id),
                        ('product_id', '=', default_code),
                    ]
                    catalog_line_id = obj_catalog_line.search(cr, uid, criteria, context=context)
                    qty_check = {}
                    soq_check = {}
                    if catalog_line_id:
                        if isinstance(catalog_line_id, (int, long)):
                            catalog_line_id = [catalog_line_id]
                        # update product in catalog only if any modification
                        # and only modified fields (for sync)
                        cl_obj = obj_catalog_line.browse(cr, uid, catalog_line_id[0], context=context)
                        if cl_obj:
                            to_write = {}
                            if cl_obj.min_qty != p_min_qty:
                                to_write['min_qty'] = p_min_qty
                            if cl_obj.line_uom_id.id != uom_id:
                                to_write['line_uom_id'] = uom_id
                            if cl_obj.unit_price != p_unit_price:
                                to_write['unit_price'] = p_unit_price
                            if cl_obj.rounding != p_rounding:
                                to_write['rounding'] = p_rounding
                            if cl_obj.min_order_qty != p_min_order_qty:
                                to_write['min_order_qty'] = p_min_order_qty
                            if cl_obj.comment != p_comment:
                                to_write['comment'] = p_comment
                            if cl_obj.product_code != supplier_code:
                                to_write['product_code'] = supplier_code
                            # Check Min. Qty rounding quantity
                            qty_check = obj_catalog_line.change_uom_qty(cr, uid, cl_obj.id,
                                                                        to_write.get('line_uom_id', cl_obj.line_uom_id.id),
                                                                        to_write.get('min_qty', cl_obj.min_qty),
                                                                        to_write.get('min_order_qty', cl_obj.min_order_qty),)
                            # Check SoQ rounding quantity
                            soq_check = obj_catalog_line.change_soq_quantity(cr, uid, cl_obj.id,
                                                                             to_write.get('rounding', cl_obj.rounding),
                                                                             to_write.get('line_uom_id', cl_obj.line_uom_id.id),)

                    else:
                        to_write = {
                            'to_correct_ok': to_correct_ok,
                            'product_id': default_code,
                            'min_qty': p_min_qty,
                            'line_uom_id': uom_id,
                            'unit_price': p_unit_price,
                            'rounding': p_rounding,
                            'min_order_qty': p_min_order_qty,
                            'comment': p_comment,
                            'product_code': supplier_code,
                        }
                        # Check Min. Qty rounding quantity
                        qty_check = obj_catalog_line.change_uom_qty(cr, uid, False,
                                                                    to_write.get('line_uom_id', False),
                                                                    to_write.get('min_qty', 0.00),
                                                                    to_write.get('min_order_qty', 0.00),)
                        # Check SoQ rounding quantity
                        soq_check = obj_catalog_line.change_soq_quantity(cr, uid, False,
                                                                         to_write.get('rounding', 0.00),
                                                                         to_write.get('line_uom_id', False),)


                    if qty_check.get('warning'):
                        error_list_line.append(qty_check['warning']['message'])
                    if qty_check.get('value'):
                        if qty_check['value'].get('min_qty'):
                            to_write['min_qty'] = qty_check['value']['min_qty']
                        if qty_check['value'].get('min_order_qty'):
                            to_write['min_order_qty'] = qty_check['value']['min_order_qty']

                    if soq_check.get('warning'):
                        error_list_line.append(soq_check['warning']['message'])
                    if soq_check.get('value', {}).get('rounding', 0.00):
                        to_write['rounding'] = soq_check['value']['rounding']

                    to_write['catalogue_id'] = obj.catalogue_id.id

                    if not catalog_line_id:
                        obj_catalog_line.create(cr, uid, to_write)
                    else:
                        obj_catalog_line.write(cr, uid, catalog_line_id, to_write)

                    percent_completed = float(line_num-1)/float(total_line_num-1)*100.0
                    complete_lines += 1
                except IndexError, e:
                    error_log += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s") % (line_num-1, '', e)
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    ignore_lines += 1
                    percent_completed = float(line_num-1)/float(total_line_num-1)*100.0
                    cr.rollback()
                    continue
                except osv.except_osv:
                    ignore_lines += 1
                    line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                    percent_completed = float(line_num-1)/float(total_line_num-1)*100.0
                    cr.rollback()
                    continue
                finally:
                    self.write(cr, uid, ids, {'percent_completed': percent_completed})
                    cr.commit()

            # in case of lines ignored, we notify the user and create a file with the lines ignored
            vals.update({'message': _('Lines ignored: %s \n ----------------------\n') % (ignore_lines,) +
                         '\n'.join(error_list), 'data': False, 'import_error_ok': False,
                         'file': False})

        error_log += '\n'.join(error_list)
        if error_log:
            error_log = _("Reported errors for ignored lines : \n") + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + _(' second(s)')
        final_message = _('''
Importation completed in %s!
# of imported lines: %s on %s lines
# of ignored lines: %s
%s
''') % (total_time, complete_lines, line_num-1, ignore_lines, error_log)
        wizard_vals = {'message': final_message, 'state': 'done', 'percent_completed': 100}
        if line_with_error:
            file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=context.get('header_index'))
            wizard_vals.update(file_to_export)
            vals['import_error_ok'] = True
        self.write(cr, uid, ids, wizard_vals, context=context)
        cr.commit()
        cr.close(True)

    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of wizard.import.supplier.catalogue records which make the import
        :param context: Context of the call
        :return : True
        """
        wiz_common_import = self.pool.get('wiz.common.import')
        catalogue_obj = self.pool.get('supplier.catalogue')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.read(cr, uid, ids, ['file', 'catalogue_id']):
            if not wiz['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz['file']))
                # iterator on rews
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'catalogue_id': wiz['catalogue_id'], 'header_index': header_index, 'object': catalogue_obj})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_supplier_catalogue_import)
                if not res:
                    return self.write(cr, uid, ids, res1)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""")
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of wizard.import.supplier.catalogue records to reload
        :param context: Context of the call
        :return : False
        """
        catalogue_obj = self.pool.get('supplier.catalogue')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            return False

        wiz = self.read(cr, uid, ids, ['catalogue_id', 'state', 'file'])
        catalogue_name = catalogue_obj.read(cr, uid, wiz[0]['catalogue_id'], ['name'])['name']
        if wiz[0]['state'] != 'done':
            self.write(cr, uid, ids, {
                'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (catalogue_name),
            }, context=context)

        return False

    def cancel(self, cr, uid, ids, context=None):
        """
        Return to the initial view.
        I don't use the special cancel because when I open the wizard with target: crush,
        and I click on cancel (the special), I come back on the home page.
        Here, I come back on the object on which I opened the wizard.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of wizard.import.supplier.catalogue records to close
        :param context: Context of the call
        :return : The action description to close the wizard and go back to the catalogue form view
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            return True

        catalogue_id = self.read(cr, uid, ids[0], ['catalogue_id'], context=context)['catalogue_id']

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'supplier.catalogue',
            'view_type': 'form',
            'view_mode': 'form, tree',
            'target': 'crush',
            'res_id': catalogue_id,
            'context': context,
        }

    def close_import(self, cr, uid, ids, context=None):
        """
        Return to the initial view
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of wizard.import.supplier.catalogue records to close
        :param context: Context of the call
        :return : The action description to close the wizard
        """
        return self.cancel(cr, uid, ids, context=context)

wizard_import_supplier_catalogue()
