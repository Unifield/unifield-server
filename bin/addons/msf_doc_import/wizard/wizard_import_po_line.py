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
import logging
import pooler
from osv import osv, fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import time
from msf_doc_import import check_line
from msf_doc_import.wizard import PO_LINE_COLUMNS_FOR_IMPORT as columns_for_po_line_import
from msf_doc_import.wizard import RFQ_LINE_COLUMNS_FOR_IMPORT as columns_for_rfq_line_import
import itertools


class wizard_import_po_line(osv.osv_memory):
    _name = 'wizard.import.po.line'
    _description = 'Import PO Lines from Excel sheet'

    def _get_bool_values(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file': fields.binary(
            string='File to import',
            required=True, readonly=True,
            states={'draft': [('readonly', False)], 'error': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'po_id': fields.many2one(
            'purchase.order', required=True, string="Purchase Order"),
        'data': fields.binary('Lines with errors'),
        'filename': fields.char('Lines with errors', size=256),
        'filename_template': fields.char('Templates', size=256),
        'import_error_ok': fields.function(
            _get_bool_values, method=True,
            type='boolean', store=False, readonly=True,
            string="Error at import"),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection(
            [('draft', 'Draft'),
             ('in_progress', 'In Progress'),
             ('error', 'Error'),
             ('done', 'Done')],
            string="State", required=True, readonly=True),
    }

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        if context is None:
            context = {}
        cr = pooler.get_db(dbname).cursor()
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        wiz_common_import = self.pool.get('wiz.common.import')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')
        categ_log = False
        line_with_error = []
        max_qty = purchase_line_obj._max_qty
        blocker_msg = []
        for wiz in self.browse(cr, uid, ids, context):
            if not wiz.po_id.pricelist_id \
                    or not wiz.po_id.pricelist_id.currency_id:
                raise osv.except_osv(_("Error!"), _("Order currency not found!"))

            ignore_lines, complete_lines, lines_to_correct, created_lines = 0, 0, 0, 0
            line_ignored_num, error_list = [], []
            error_log, message = '', ''
            header_index = context['header_index']
            template_col_count = len(header_index)
            is_rfq = wiz.po_id.rfq_ok
            mandatory_col_count = 9 if is_rfq else 7

            file_obj = SpreadsheetXML(xmlstring=base64.b64decode(wiz.file))

            """
            1st path: check currency in lines in phasis with document
            REF-94: BECAREFUL WHEN CHANGING THE ORDER OF CELLS IN THE IMPORT FILE!!!!!
            CCY COL INDEX: 6 (PO) or 8 (RfQ)
            """
            order_currency_code = wiz.po_id.pricelist_id.currency_id.name
            currency_index = 8 if is_rfq else 6
            row_iterator = file_obj.getRows()

            # don't use the original
            row_iterator, row_iterator_line_check = itertools.tee(row_iterator)

            next(row_iterator_line_check)  # skip header line
            try:
                lines_to_correct = check_line.check_lines_currency(row_iterator_line_check, currency_index, order_currency_code)
            except Exception as e:
                message = _("""An error occurs during the check of the currency: %s""") % e
                categ_log = ''
                line_num = 0
                error_list.append(message)
                logging.getLogger('import purchase order').error('Error %s' % e)

            if lines_to_correct > 0:
                categ_log = ''
                line_num = 0
                msg = _("You can not import this file because it contains line(s) with currency not of the order currency (%s)") % (
                    order_currency_code, )
                error_list.append(msg)

            if not error_list:
                line_number_set = set()
                to_write = {}
                total_line_num = file_obj.getNbRows()
                # ignore the header line
                next(row_iterator)
                for line_num, row in enumerate(row_iterator, start=1):
                    cr.execute("SAVEPOINT line_save")
                    percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                    # default values
                    to_write = {
                        'error_list': [],
                        'warning_list': [],
                        'to_correct_ok': False,
                        'show_msg_ok': False,
                        'comment': '',
                        'date_planned': wiz.po_id.delivery_requested_date,
                        'functional_currency_id': wiz.po_id.pricelist_id.currency_id.id,
                        'price_unit': 1,  # as the price unit cannot be null, it will be computed in the method "compute_price_unit" after.
                        'product_qty': 1,
                        #'nomen_manda_0':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1],
                        #'nomen_manda_1':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1],
                        #'nomen_manda_2':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1],
                        #'nomen_manda_3':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd3')[1],
                        'proc_type': 'make_to_order',
                        'default_code': False,
                        'confirmed_delivery_date': False,
                        'line_number': '',
                        'set_as_validated_n': True if wiz.po_id.state not in ('draft', 'draft_p') else False,
                    }

                    col_count = len(row)
                    if col_count != template_col_count and col_count != mandatory_col_count:
                        message += _("Line %s: You should have exactly %s columns in this order: %s \n") % (
                            line_num, template_col_count,
                            ','.join(is_rfq and columns_for_rfq_line_import or columns_for_po_line_import[1:]))
                        line_with_error.append(
                            wiz_common_import.get_line_values(
                                cr, uid, ids, row, cell_nb=False,
                                error_list=error_list, line_num=line_num, context=context))
                        ignore_lines += 1
                        line_ignored_num.append(line_num)
                        self.write(cr, uid, ids, {'percent_completed': percent_completed})
                        continue
                    try:
                        if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                            percent_completed = float(line_num) / float(total_line_num - 1) * 100.0
                            self.write(cr, uid, ids, {'percent_completed': percent_completed})
                            line_num -= 1
                            total_line_num -= 1
                            continue

                        # Cell 0 : Line Number (RfQ)
                        if is_rfq:
                            ln_value = check_line.line_number_value(
                                row=row, cell_nb=header_index[_('line number')], to_write=to_write, context=context)
                            to_write.update(
                                line_number=ln_value['line_number'],
                                error_list=ln_value['error_list'])

                        # Cell 1: Product Code
                        p_value = check_line.product_value(
                            cr, uid, obj_data=obj_data, cell_nb=header_index[_('product code')],
                            product_obj=product_obj, row=row, to_write=to_write, context=context)
                        to_write.update(
                            default_code=p_value['default_code'],
                            product_id=p_value['default_code'],
                            comment=p_value['comment'],
                            error_list=p_value['error_list'])
                        if not p_value['product_code']:
                            raise osv.except_osv(_('Error'), _("Product code not found in the import file"))

                        # Cell 2: Quantity
                        qty_value = check_line.quantity_value(
                            product_obj=product_obj, cell_nb=header_index[_('quantity')],
                            row=row, to_write=to_write, max_qty=max_qty, context=context)
                        to_write.update(
                            product_qty=qty_value['product_qty'],
                            error_list=qty_value['error_list'],
                            warning_list=qty_value['warning_list'])

                        # Cell 3: UOM
                        uom_value = check_line.compute_uom_value(
                            cr, uid, obj_data=obj_data, cell_nb=header_index[_('uom')], product_obj=product_obj,
                            uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                        to_write.update(
                            product_uom=uom_value['uom_id'],
                            error_list=uom_value['error_list'])

                        # Check round of qty according to UoM
                        if qty_value['product_qty'] and uom_value['uom_id']:
                            round_qty = uom_obj._change_round_up_qty(
                                cr, uid, uom_value['uom_id'], qty_value['product_qty'], 'product_qty')
                            if round_qty.get('warning', {}).get('message'):
                                to_write.update(product_qty=round_qty['value']['product_qty'])
                                warn_list = to_write['warning_list']
                                warn_list.append(round_qty['warning']['message'])
                            #message += _("Line %s in the Excel file: %s\n") % (line_num, round_qty['warning']['message'])

                        # Cell 4: Price
                        price_value = check_line.compute_price_value(
                            row=row, to_write=to_write, cell_nb=header_index[_('price')], price='Cost Price',
                            is_rfq=is_rfq, context=context)
                        to_write.update(
                            price_unit=price_value['price_unit'],
                            error_list=price_value['error_list'],
                            warning_list=price_value['warning_list'],
                            price_unit_defined=price_value['price_unit_defined'])

                        # Cell 5: Requested Delivery Date
                        # for Rfq 'Requested Delivery Date' tolerated (5th column)
                        cell_nb = header_index[_('requested delivery date')] if _('requested delivery date') in header_index else 6
                        date_value = check_line.compute_date_value(
                            cell_nb=cell_nb, row=row, to_write=to_write, context=context)
                        to_write.update(
                            date_planned=date_value['date_planned'],
                            error_list=date_value['error_list'])

                        # Cell 7: Confirmed Delivery Date
                        if is_rfq:
                            cell_nb = header_index[_('confirmed delivery date')] if _('confirmed delivery date') in header_index else 7
                            cdd_value = check_line.compute_confirmed_delivery_date_value(
                                cell_nb=cell_nb, row=row, to_write=to_write, context=context)
                            to_write.update(
                                confirmed_delivery_date=cdd_value['confirmed_delivery_date'],
                                error_list=cdd_value['error_list'])

                        # Cell 6: Currency
                        curr_value = check_line.compute_currency_value(
                            cr, uid, cell_nb=header_index[_('currency')], browse_purchase=wiz.po_id,
                            currency_obj=currency_obj, row=row, to_write=to_write, context=context)
                        to_write.update(
                            functional_currency_id=curr_value['functional_currency_id'],
                            warning_list=curr_value['warning_list'])

                        # Cell 7: Comment
                        c_value = check_line.comment_value(
                            row=row, cell_nb=header_index[_('comment')], to_write=to_write, context=context)
                        to_write.update(
                            comment=c_value['comment'],
                            warning_list=c_value['warning_list'])

                        to_write.update(
                            to_correct_ok=any(to_write['error_list']),  # the lines with to_correct_ok=True will be red
                            show_msg_ok=any(to_write['warning_list']),  # the lines with show_msg_ok=True won't change color, it is just info
                            order_id=wiz.po_id.id,
                            text_error='\n'.join(to_write['error_list'] + to_write['warning_list']))

                        # we check consistency on the model of on_change functions to call for updating values
                        purchase_line_obj.check_line_consistency(
                            cr, uid, wiz.po_id.id, to_write=to_write, context=context)

                        if to_write.get('product_qty', 0.00) <= 0.00:
                            message += _("Line %s in the Excel file: Details: %s\n") % (
                                line_num, _('Product Qty should be greater than 0.00'))
                            ignore_lines += 1
                            line_with_error.append(
                                wiz_common_import.get_line_values(
                                    cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            cr.execute('ROLLBACK TO SAVEPOINT line_save')
                            continue

                        # write the warning list on the import result log textarea
                        for warn in to_write['warning_list']:
                            message += "Line %s WARNING : %s\n" % (line_num, warn)

                        if is_rfq:
                            rfq_line_ids = purchase_line_obj.search(cr, uid, [('order_id', '=', wiz.po_id.id), ('line_number', '=', to_write['line_number'])])
                            to_write['rfq_ok'] = True

                            # CASE 1: the line is not registered in the system, so CREATE it :
                            if not rfq_line_ids:
                                created_lines += 1
                                if wiz.po_id.tender_id:
                                    msg =  _('Warning! You are adding new lines which did not exist in the original tender!')
                                    if msg not in message:
                                        message += msg
                                to_write.update({
                                    'line_number': False,
                                    'red_color': True,
                                })
                                purchase_line_obj.create(cr, uid, to_write, context=context)

                            # CASE 2: the line is already in the system, so UPDATE it :
                            for po_line in purchase_line_obj.browse(cr, uid, rfq_line_ids, context=context):
                                # some checks :
                                if to_write['line_number'] in line_number_set:
                                    raise osv.except_osv(_('Error'), _("the same line number appears several times"))
                                else:
                                    line_number_set.add(to_write['line_number'])
                                if p_value['product_code'] != po_line.product_id.default_code:
                                    raise osv.except_osv(_('Error'), _("Product code from system and from import must be the same."))
                                if not price_value['price_unit_defined']:
                                    raise osv.except_osv(_('Error'), _("Price must be defined in the RfQ import file."))

                                # in case of update we do not want to update qty and uom values :
                                if 'product_qty' in to_write:
                                    to_write.pop('product_qty')
                                if 'product_uom' in to_write:
                                    to_write.pop('product_uom')

                                # update POL :
                                purchase_line_obj.write(cr, uid, rfq_line_ids, to_write, context=context)

                        else: # its not RfQ
                            purchase_line_obj.create(cr, uid, to_write, context=context)


                        if to_write['error_list']:
                            lines_to_correct += 1
                        complete_lines += 1

                    except IndexError as e:
                        message += _("Line %s in the Excel file was added to the file of the lines with errors, it got elements outside the defined %s columns. Details: %s"
                                     ) % (line_num, template_col_count, e)
                        line_with_error.append(
                            wiz_common_import.get_line_values(
                                cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        ignore_lines += 1
                        line_ignored_num.append(line_num)
                        cr.execute('ROLLBACK TO SAVEPOINT line_save')
                        continue
                    except osv.except_osv as osv_error:
                        osv_value = osv_error.value
                        osv_name = osv_error.name
                        message += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                        ignore_lines += 1
                        line_with_error.append(
                            wiz_common_import.get_line_values(
                                cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        cr.execute('ROLLBACK TO SAVEPOINT line_save')
                        continue
                    except check_line.ExceptionWrongQuantity:
                        prod = ''
                        if p_value.get('default_code'):
                            prod = self.pool.get('product.product').browse(cr, uid, p_value.get('default_code'), fields_to_fetch=['default_code'], context=context).default_code
                        blocker_msg.append(_('Line #%s of the file, product: %s') % (line_num+1, prod))
                        line_with_error.append(
                            wiz_common_import.get_line_values(
                                cr, uid, ids, row, cell_nb=False,
                                error_list=error_list, line_num=line_num, context=context))
                        cr.rollback()
                        continue
                    except UnicodeEncodeError as e:
                        message += _("""Line %s in the Excel file, uncaught error: %s\n""") % (line_num, e)
                        line_with_error.append(
                            wiz_common_import.get_line_values(
                                cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        logging.getLogger('import purchase order').error('Error %s' % e)
                        cr.execute('ROLLBACK TO SAVEPOINT line_save')
                        continue
                    except Exception as e:
                        message += _("""Line %s in the Excel file, uncaught error: %s\n""") % (line_num, e)
                        line_with_error.append(
                            wiz_common_import.get_line_values(
                                cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        logging.getLogger('import purchase order').error('Error %s' % e)
                        cr.execute('ROLLBACK TO SAVEPOINT line_save')
                        continue
                    else:
                        self.write(cr, uid, ids, {'percent_completed':percent_completed})
                        cr.execute("RELEASE SAVEPOINT line_save")

                if not blocker_msg:
                    categ_log = purchase_obj.onchange_categ(
                        cr, uid, [wiz.po_id.id], wiz.po_id.categ, wiz.po_id.warehouse_id.id, wiz.po_id.cross_docking_ok,
                        wiz.po_id.location_id.id, context=context).get('warning', {}).get('message', '').upper()
                    categ_log = categ_log.replace('THIS', 'THE')

        wizard_vals = {'percent_completed': 100}
        try:
            error_log += '\n'.join(error_list)
            if error_log:
                error_log = _("Reported errors for ignored lines : \n") + error_log
            end_time = time.time()
            total_time = str(round(end_time-start_time)) + _(' second(s)')
            if blocker_msg:
                wizard_vals['state'] = 'error'
                wizard_vals['file'] = False
                cr.rollback()
                final_message = _("Warning this/these lines cannot be imported due to too many digits in Qty field. Please check:\n%s") % ('\n'.join(blocker_msg), )
            else:
                wizard_vals['state'] = 'done'
                cr.commit()
                final_message = _('''
%s
Importation completed in %s!
# of imported lines : %s on %s lines (%s updated and %s created)
# of ignored lines: %s
# of lines to correct: %s
%s

%s
''') % (categ_log, total_time, complete_lines, line_num, complete_lines-created_lines,created_lines, ignore_lines, lines_to_correct, error_log, message)
            wizard_vals['message'] = final_message
            if line_with_error:
                file_to_export = wiz_common_import.export_file_with_error(
                    cr, uid, ids, line_with_error=line_with_error, header_index=header_index, context=context)
                wizard_vals.update(file_to_export)
        except Exception:
            cr.rollback()
        finally:
            # we reset the state of the PO to draft (initial state)
            self.write(cr, uid, ids, wizard_vals, context=context)
            cr.commit()
            cr.close(True)


    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        if isinstance(ids, int):
            ids = [ids]
        wiz_common_import = self.pool.get('wiz.common.import')
        purchase_obj = self.pool.get('purchase.order')
        for wiz_read in self.read(cr, uid, ids, ['po_id', 'file']):
            po_id = wiz_read['po_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_read['file']))
                # iterator on rows
                reader_iterator = fileobj.getRows()
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(
                    cr, uid, ids, first_row, error_list=[], line_num=0, origin='PO', context=context)
                context.update({'po_id': po_id, 'header_index': header_index})
                rfq = purchase_obj.read(cr, uid, po_id, ['state', 'rfq_ok'], context=context)
                is_rfq = rfq['rfq_ok']
                res, res1 = wiz_common_import.check_header_values(
                    cr, uid, ids, context, header_index, is_rfq and columns_for_rfq_line_import
                    or columns_for_po_line_import[1:], origin='PO')
                if not res:
                    return self.write(cr, uid, ids, res1, context)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("Please note that %s is temporary not editable during the import to "
                          "avoid conflict accesses (you can see the loading on the PO note "
                          "tab check box). At the end of the load, POXX will be back in the "
                          "right state. You can refresh the screen if you need to follow "
                          "the upload progress") % (purchase_obj.browse(cr, uid, po_id).name)
        return self.write(
            cr, uid, ids,
            {'message': msg_to_return, 'state': 'in_progress'},
            context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, int):
            ids = [ids]
        purchase_obj = self.pool.get('purchase.order')
        for wiz_read in self.read(cr, uid, ids, ['po_id', 'state', 'file']):
            po_id = wiz_read['po_id']
            po_name = purchase_obj.read(cr, uid, po_id, ['name'])['name']
            if wiz_read['state'] not in  ('done', 'error'):
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (po_name, )})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, int):
            ids = [ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id']):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, int):
            ids = [ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id']):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }

wizard_import_po_line()
