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
from msf_doc_import import check_line
from msf_doc_import.wizard import INT_LINE_COLUMNS_FOR_IMPORT as columns_for_internal_line_import

class wizard_import_pick_line(osv.osv_memory):
    _name = 'wizard.import.pick.line'
    _description = 'Import Pick Lines from Excel sheet'

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
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True, translate=True),
        'picking_id': fields.many2one('stock.picking', string='Stock Picking', required=True),
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
        # Objects
        wiz_common_import = self.pool.get('wiz.common.import')
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        pick_obj = self.pool.get('stock.picking')
        move_obj = self.pool.get('stock.move')
        kit_obj = self.pool.get('composition.kit')
        asset_obj = self.pool.get('product.asset')
        bn_obj = self.pool.get('stock.production.lot')
        loc_obj = self.pool.get('stock.location')

        context = context is None and {} or context

        # Don't create a new cursor if we are in unit test
        if not context.get('yml_test', False):
            cr = pooler.get_db(dbname).cursor()
        else:
            cr = dbname

        # Variables
        context.update({'import_in_progress': True, 'noraise': True})
        start_time = time.time()
        date_format = self.pool.get('date.tools').get_date_format(cr, uid, context=context)
        line_with_error = []

        for wiz_browse in self.browse(cr, uid, ids, context):
            picking, categ_log = False, ''
            try:
                picking = wiz_browse.picking_id

                partner_loc = picking.partner_id and picking.partner_id.property_stock_supplier.id or False

                ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
                line_ignored_num = []
                error_list = []
                error_log = ''
                message = ''
                line_num = 0
                header_index = context['header_index']

                file_obj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_browse.file))
                # iterator on rows
                rows = file_obj.getRows()
                # ignore the first row
                next(rows)
                line_num = 0
                to_write = {}
                total_line_num = len([row for row in file_obj.getRows()])
                percent_completed = 0
                for row in rows:
                    line_num += 1
                    # default values
                    to_write = {
                        'error_list': [],
                        'warning_list': [],
                        'to_correct_ok': False,
                        'show_msg_ok': False,
                        'comment': '',
                        'price_unit': 1,  # in case that the product is not found and we do not have price
                        'product_qty': 1,
                        'default_code': False,
                        'prodlot_id': False,
                        'expiry_date': False,
                        'asset_id': False,
                        'kit_creation_id_stock_move': False,
                    }

                    col_count = len(row)
                    template_col_count = len(list(header_index.items()))
                    if col_count != template_col_count:
                        message += _("""Line %s in the Excel file: You should have exactly %s columns in this order: %s \n""") % (line_num, template_col_count,','.join(columns_for_internal_line_import))
                        line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        ignore_lines += 1
                        line_ignored_num.append(line_num)
                        percent_completed = float(line_num)/float(total_line_num-1)*100.0
                        self.write(cr, uid, ids, {'percent_completed':percent_completed})
                        continue
                    try:
                        if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            self.write(cr, uid, ids, {'percent_completed': percent_completed})
                            line_num-=1
                            total_line_num -= 1
                            continue

                        # Cell 0: Product Code
                        p_value = {}
                        p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                        to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'], 'price_unit': p_value['price_unit'],
                                         'comment': p_value['comment'], 'error_list': p_value['error_list']})

                        # Name
                        if p_value['default_code']:
                            product = product_obj.browse(cr, uid, to_write['product_id'])
                            name = '[%s] %s' % (product.default_code, product.name)
                            to_write.update({'name': name})
                        else:
                            raise osv.except_osv(_('Error'), '\n'.join(x for x in p_value['error_list']))

                        # Cell 8 : Source location
                        src_value = {}
                        src_value = check_line.compute_location_value(cr, uid, to_write=to_write, loc_obj=loc_obj, pick_type=picking.type,
                                                                      pick_ext_cu=picking.ext_cu, product_id=to_write['product_id'],
                                                                      check_type='src', row=row, cell_nb=8, context=context)
                        if picking.type == 'in' and partner_loc and partner_loc != src_value['location_id']:
                            raise osv.except_osv(_('Error'), _('The source location is not compatible with the partner'))

                        to_write.update({'location_id': src_value['location_id'],
                                         'error_list': src_value['error_list']})
                        if not src_value['location_id']:
                            raise osv.except_osv(_('Error'), '\n'.join(x for x in p_value['error_list']))

                        # Cell 9 : Destination location
                        dest_value = {}
                        dest_value = check_line.compute_location_value(cr, uid, to_write=to_write, loc_obj=loc_obj, pick_type=picking.type,
                                                                       product_id=to_write['product_id'], check_type='dest',
                                                                       row=row, cell_nb=9, context=context)
                        to_write.update({'location_dest_id': dest_value['location_id'], 'error_list': dest_value['error_list'],})
                        if not dest_value['location_id']:
                            raise osv.except_osv(_('Error'), '\n'.join(x for x in p_value['error_list']))

                        # Cell 2: Quantity
                        qty_value = {}
                        qty_value = check_line.quantity_value(product_obj=product_obj, row=row, to_write=to_write, context=context)
                        to_write.update({'product_qty': qty_value['product_qty'], 'error_list': qty_value['error_list']})

                        # Cell 3: UOM
                        uom_value = {}
                        uom_value = check_line.compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                        to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})

                        # Check if the UoM is compatible with the product
                        if to_write.get('product_id') and to_write.get('product_uom'):
                            uom_categ = uom_obj.browse(cr, uid, to_write.get('product_uom'), context=context).category_id.id
                            prod_uom_categ = product_obj.browse(cr, uid, to_write.get('product_id'), context=context).uom_id.category_id.id
                            if uom_categ != prod_uom_categ:
                                message += _("Line %s in the Excel file: Details: %s\n") % (line_num, _('The UoM is not compatible with the product.'))
                                ignore_lines += 1
                                line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                                cr.rollback()
                                continue

                        new_qty = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_value.get('uom_id', False), qty_value.get('product_qty', False), 'qty').get('value', {}).get('qty', qty_value.get('product_qty'))
                        if new_qty != qty_value.get('product_qty'):
                            qty_value.update({'product_qty': new_qty})
                            to_write.update({'product_qty': new_qty})
                            error_log += _("Line %s in the Excel file : The product qty. has been rounded with the rounding value of the UoM.") % line_num

                        # Cell 4: Kit
                        if product.type == 'product' and product.subtype == 'kit':
                            kit_value = {}
                            kit_value = check_line.compute_kit_value(cr, uid, row=row, to_write=to_write, kit_obj=kit_obj,
                                                                     cell_nb=4, context=context)
                            to_write.update({'composition_list_id': kit_value['kit_id'], 'error_list': kit_value['error_list'],})

                        # Cell 5: Asset
                        if product.type == 'product' and product.subtype == 'asset':
                            asset_value = {}
                            asset_value = check_line.compute_asset_value(cr, uid, row=row, to_write=to_write, asset_obj=asset_obj,
                                                                         cell_nb=5, context=context)
                            to_write.update({'asset_id': asset_value['asset_id'], 'error_list': asset_value['error_list']})

                        if product.batch_management or product.perishable:
                            # Cell 6: Batch Number and Cell 7 : Expiry date
                            batch_value = {}
                            batch_value = check_line.compute_batch_expiry_value(cr, uid, row=row, to_write=to_write, bn_obj=bn_obj,
                                                                                product_obj=product_obj,
                                                                                bn_cell_nb=6, ed_cell_nb=7,
                                                                                date_format=date_format,
                                                                                product_id=to_write.get('product_id'),
                                                                                picking_type=picking.type)

                            # Create the internal batch number if not exists
                            if not product.batch_management and product.perishable and batch_value['expired_date'] and not batch_value['prodlot_id'] and not batch_value['error_list']:
                                batch_value['prodlot_id'] = bn_obj.create(cr, uid, {
                                    'type': 'internal',
                                    'product_id': product.id,
                                    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'),
                                    'life_date': batch_value['expired_date'],
                                }, context=context)

                            to_write.update({'prodlot_id': batch_value['prodlot_id'],
                                             'expired_date': batch_value['expired_date'],
                                             'error_list': batch_value['error_list']})


                        to_write.update({
                            'to_correct_ok': any(to_write['error_list']),  # the lines with to_correct_ok=True will be red
                            'show_msg_ok': any(to_write['warning_list']),  # the lines with show_msg_ok=True won't change color, it is just info
                            'picking_id': picking.id,
                            'reason_type_id': picking.reason_type_id.id,
                            'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
                        })
                        # we check consistency on the model of on_change functions to call for updating values
                        #move_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)

                        if to_write.get('product_qty', 0.00) <= 0.00:
                            error_log += _("Line %s in the Excel file was ignored. Details: %s") % (line_num, _('Product Quantity must be greater than zero.'))
                            line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                            ignore_lines += 1
                            line_ignored_num.append(line_num)
                            percent_completed = float(line_num)/float(total_line_num-1)*100.0
                            cr.rollback()
                            continue

                        # write move line on picking
                        #vals['move_lines'].append((0, 0, to_write))
                        move_obj.create(cr, uid, to_write, context=context)
                        if to_write['error_list']:
                            lines_to_correct += 1
                        #move_obj.action_confirm(cr, uid, [move_id], context=context)
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
                    except AttributeError as e:
                        error_log += _('Line %s in the Excel file was added to the file of the lines with error, an error is occurred. Details : %s') % (line_num, e)
                        line_with_error.append(wiz_common_import.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context))
                        ignore_lines += 1
                        line_ignored_num.append(line_num)
                        percent_completed = float(line_num)/float(total_line_num-1)/100.0
                        cr.rollback()
                        continue
                    finally:
                        self.write(cr, uid, ids, {'percent_completed':percent_completed})
                        if not context.get('yml_test', False):
                            cr.commit()
            except Exception as e:
                error_log += _("An error is occurred. Details : %s") % e
                cr.rollback()
                continue
            finally:
                error_log += '\n'.join(error_list)
                if error_log:
                    error_log = _("Reported errors for ignored lines : \n") + error_log
                elif picking and not picking.from_wkf and not picking.claim:
                    # Check category if document is form scratch
                    categ_log = pick_obj.on_change_order_category(cr, uid, [picking.id], picking.order_category,
                                                                  context=context).get('warning', {}).get('message', '').upper()
                    categ_log = categ_log.replace('THIS', 'THE')
                end_time = time.time()
                total_time = str(round(end_time-start_time)) + _(' second(s)')
                final_message = _(''' 
    %s
    Importation completed in %s!
    # of imported lines : %s on %s lines
    # of ignored lines: %s
    # of lines to correct: %s
    %s

    %s
    ''') % (categ_log, total_time, complete_lines, line_num, ignore_lines, lines_to_correct, error_log, message)
                wizard_vals = {'message': final_message, 'state': 'done'}
                if line_with_error:
                    file_to_export = wiz_common_import.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
                    wizard_vals.update(file_to_export)
                self.write(cr, uid, ids, wizard_vals, context=context)
                # we reset the state of the FO to draft (initial state)
                pick_obj.write(cr, uid, picking.id, {'state': picking.state_before_import, 'import_in_progress': False}, context)
        if not context.get('yml_test', False):
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
            picking = wiz_read.picking_id
            if not wiz_read.file:
                return self.write(cr, uid, ids, {'message': _("Nothing to import")})
            if picking.state not in ['draft', 'confirmed', 'assigned']:
                doc_name = _('Pick')
                if picking.type == 'in':
                    doc_name = _('IN')
                elif picking.type == 'internal':
                    doc_name = _('INT')
                elif picking.type == 'out' and picking.subtype == 'standard':
                    doc_name = _('OUT')
                return self.write(cr, uid, ids, {'state': 'done', 'message': _("You can only import on a Draft, Not Available or Available %s; import file is ignored") % (doc_name,)}, context=context)
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.b64decode(wiz_read.file))
                # iterator on rows
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = wiz_common_import.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'picking_id': picking.id, 'header_index': header_index})
                res, res1 = wiz_common_import.check_header_values(cr, uid, ids, context, header_index, columns_for_internal_line_import)
                if not res:
                    return self.write(cr, uid, ids, res1, context)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
            # we close the PO only during the import process so that the user can't update the PO in the same time (all fields are readonly)
            pick_obj.write(cr, uid, picking.id, {'state': 'import', 'import_in_progress': True, 'state_before_import': wiz_read.picking_id.state}, context)
            cr.commit()
        if not context.get('yml_test', False):
            thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
            thread.start()
        else:
            self._import(cr, uid, ids, context)
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
                self.write(cr, uid, ids, {'message': _(' Import in progress... \n Please wait that the import is finished before editing %s.') % (int_name, )})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the object on which I opened the wizard.
        '''
        if isinstance(ids, int):
            ids=[ids]
        for wiz_obj in self.browse(cr, uid, ids, context=context):
            picking_id = wiz_obj.picking_id
            xmild = self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, ids, context=context, pick=picking_id)
            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, xmild, ['form', 'tree'], context=context)
            res['res_id'] = picking_id.id
            return res


    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, int):
            ids=[ids]
        for wiz_obj in self.browse(cr, uid, ids, context=context):
            picking_id = wiz_obj.picking_id
            xmlid = self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, ids, context=context, pick=picking_id)
            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, xmlid, ['form', 'tree'], context=context)
            res['res_id'] = picking_id.id
            return res

wizard_import_pick_line()
