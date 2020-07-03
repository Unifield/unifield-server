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

from osv import osv, fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import time
from msf_doc_import import check_line
from consumption_calculation.consumption_calculation import _get_asset_mandatory

class wizard_import_rac(osv.osv_memory):
    _name = 'wizard.import.rac'
    _description = 'Import RAC from Excel sheet'

    _msg =  _("""
        IMPORTANT : The first line will be ignored by the system.

        The file should be in XML 2003 format.
        The columns should be in this order :
           Product Code ; Product Description ; UoM ; Indicative Stock ; Batch Number ; Expiry Date (DD/MM/YYYY) (ignored if batch number is set) ; Asset ; Consumed quantity ; Remark
        """)
    _columns = {
        'file': fields.binary(string='File to import', required=True),
        'message': fields.text(string='Message', readonly=True),
        'rac_id': fields.many2one('real.average.consumption', string='Real average consumption', required=True),
    }

    _defaults = {
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set rac_id with the active_id value in context
        '''
        if not context or not context.get('active_id'):
            raise osv.except_osv(_('Error !'), _('No Real average consumption found !'))
        else:
            rac_id = context.get('active_id')
            res = super(wizard_import_rac, self).default_get(cr, uid, fields, context=context)
            res['rac_id'] = rac_id
        res['message'] = _(self._msg)
        return res

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import file
        '''
        if context is None:
            context = {}
        start_time = time.time()
        product_obj = self.pool.get('product.product')
        prodlot_obj = self.pool.get('stock.production.lot')
        uom_obj = self.pool.get('product.uom')
        line_obj = self.pool.get('real.average.consumption.line')
        asset_obj = self.pool.get('product.asset')
        obj_data = self.pool.get('ir.model.data')
        product_tbd = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]

        import_rac = self.browse(cr, uid, ids[0], context)
        rac_id = import_rac.rac_id.id

        ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
        error_log = ''
        line_num = 0
        if not import_rac.file:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(import_rac.file))
        # iterator on rows
        reader = fileobj.getRows()
        reader.next()

        for row in reader:
            # Check length of the row
            col_count = len(row)
            if not check_line.check_empty_line(row=row, col_count=col_count, line_num=line_num):
                continue
            if col_count != 9:
                raise osv.except_osv(_('Error'), _("""You should have exactly 9 columns in this order:
Product Code*, Product Description*, Product UOM, Indicative Stock, Batch Number, Asset, Expiry Date, Consumed Quantity, Remark"""))
            # default values
            to_write = {
                'default_code': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1],
                'uom_id': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1],
                'consumed_qty': 0,
                'error_list': [],
                'warning_list': [],
            }
            consumed_qty = 0
            remark = ''
            error = ''
            just_info_ok = False
            batch = False
            asset = False
            expiry_date = None # date type
            batch_mandatory = False
            date_mandatory = False
            line_num += 1
            existing_line_domain = []
            context.update({'import_in_progress': True, 'noraise': True})
            try:
                # Cell 8: Quantity
                if row.cells[7] and row.cells[7].data:
                    try:
                        consumed_qty = float(row.cells[7].data)
                    except ValueError:
                        error += _("Line %s of the imported file: the Consumed Quantity should be a number and not %s \n.") % (line_num, row.cells[7].data,)

                # Cell 0: Product Code
                expiry_date = False
                p_value = {}
                p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                if p_value['default_code']:
                    product_id = p_value['default_code']
                    to_write.update({'product_id': product_id})
                    prod = product_obj.browse(cr, uid, [product_id], context)[0]
                    existing_line_domain.append(('product_id', '=', product_id))
                    # Expiry Date
                    if prod.perishable:
                        date_mandatory = True
                        if not row[4] or row[5] is None:
                            error += _("Line %s of the imported file: expiry date required\n") % (line_num, )
                        elif row[5] and row[5].data:
                            if row[5].type in ('datetime', 'date'):
                                expiry_date = row[5].data
                            elif row[5].type == 'str':
                                try:
                                    expiry_date = time.strftime('%d/%b/%Y', time.strptime(row[5].data, '%d/%m/%Y'))
                                except ValueError:
                                    try:
                                        expiry_date = time.strftime('%d/%b/%Y', time.strptime(row[5].data, '%d/%b/%Y'))
                                    except ValueError as e:
                                        error += _("""Line %s of the imported file: expiry date %s has a wrong format (day/month/year).'\n"""
                                                   ) % (line_num, row[5],)
                            if expiry_date:
                                existing_line_domain.append(('expiry_date', '=', expiry_date))
                    # Cell 4: Batch Number
                    if prod.batch_management:
                        batch_mandatory = True
                        if prod.batch_management and not row[4]:
                            error += _("Line %s of the imported file: Batch Number required.\n") % (line_num,)
                        if row[4]:
                            lot = prodlot_obj.search(cr, uid, [('name', '=', row[4]), ('product_id', '=', prod.id)], context=context)
                            if not lot and consumed_qty:
                                error += _("Line %s of the imported file: Batch Number [%s] not found.\n") % (line_num, row[4])
                            elif lot:
                                batch = lot[0]
                        if expiry_date and product_id:
                            if not batch:
                                batch_list = prodlot_obj.search(cr, uid, [('product_id', '=', product_id), ('life_date', '=', expiry_date)], context=context)
                                if batch_list:
                                    batch = batch_list[0]
                                else:
                                    error += _("Line %s of the imported file: the Expiry Date does not match with any batch number of the product.\n") % (line_num,)
                            else:
                                # if the expiry date and batch exist, the expiry date indicated here and the one on the batch should be the same
                                if not prodlot_obj.search(cr, uid, [('id', '=', batch), ('product_id', '=', product_id), ('life_date', '=', expiry_date)], context=context):
                                    batch_read = prodlot_obj.read(cr, uid, batch, ['life_date', 'name'], context)
                                    expiry_date = batch_read['life_date']
                                    error += _("""Line %s of the imported file: Expiry Date has been changed to %s which is the system BN date (was wrong in the file)"""
                                               ) % (line_num, batch_read['life_date'] and time.strftime('%d/%b/%Y', time.strptime(batch_read['life_date'], '%Y-%m-%d')))
                                    just_info_ok = True
                        if batch:
                            existing_line_domain.append(('prodlot_id', '=', batch))

                    # Cell 6 : Asset
                    if _get_asset_mandatory(prod):
                        if not row[6].data:
                            error += _("Line %s of the imported file: Asset form required.\n") % (line_num,)
                        if row[6].data:
                            asset = asset_obj.search(cr, uid, [('name', '=', row[6]), ('product_id', '=', prod.id)], context=context)
                            if not asset and consumed_qty:
                                error += _("Line %s of the imported file: Asset [%s] not found.\n") % (line_num, row[6])
                            elif asset:
                                asset = asset[0]
                else:
                    product_id = False
                    error += _('Line %s of the imported file: Product Code [%s] not found ! Details: %s \n') % (line_num, row[0], p_value['error_list'])

                # Cell 2: UOM
                uom_value = {}
                # The consistency between the product and the uom used the product_id value contained in the write dictionary.
                uom_value = check_line.compute_uom_value(cr, uid, cell_nb=2, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                if uom_value['uom_id']:
                    uom_id = uom_value['uom_id']
                else:
                    uom_id = False
                    error += _('Line %s of the imported file: UoM [%s] not found ! Details: %s') % (line_num, row[2], uom_value['error_list'])

                # Cell 3: Indicative Stock
                # IGNORE IT

                # Check rounding of qty according to UoM
                if uom_id and consumed_qty:
                    round_qty = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, consumed_qty, 'consumed_qty')
                    if round_qty.get('warning', {}).get('message'):
                        consumed_qty = round_qty['value']['consumed_qty']
                        error_log += _('Line %s of the imported file: %s') % (line_num, round_qty.get('warning', {}).get('message'))

                # Cell 8: Remark
                if row.cells[8] and row.cells[8].data:
                    remark = row.cells[8].data
                error += '\n'.join(to_write['error_list'])
                if not consumed_qty and not product_id == product_tbd:
                     # If the line doesn't have quantity we do not check it.
                    error = None
                line_data = {'batch_mandatory': batch_mandatory,
                             'date_mandatory': date_mandatory,
                             'product_id': product_id,
                             'uom_id': uom_id,
                             'prodlot_id': batch,
                             'expiry_date': expiry_date,
                             'asset_id': asset,
                             'consumed_qty': consumed_qty,
                             'remark': remark,
                             'rac_id': rac_id,
                             'text_error': error,
                             'just_info_ok': just_info_ok,}

                # Check product restrictions
                if product_id:
                    product_obj._get_restriction_error(cr, uid, [product_id], {'constraints': ['consumption']}, context=dict(context, noraise=False))

                context.update({'line_num': line_num})
                existing_line_ids = []
                if existing_line_domain:
                    existing_line_ids = line_obj.search(cr, uid, existing_line_domain, context=context)
                if existing_line_ids:
                    line_id = existing_line_ids[0]
                    line_obj.write(cr, uid, line_id, line_data, context=context)
                else:
                    line_id = line_obj.create(cr, uid, line_data, context=context)

                complete_lines += 1
                # when we enter the create, we catch the raise error into the context value of 'error_message'
                list_message = context.get('error_message')
                if list_message:
                    # if errors are found and a text_error was already existing we add it the line after
                    text_error = line_obj.read(cr, uid, line_id,['text_error'], context)['text_error'] + '\n' + '\n'.join(list_message)
                    line_obj.write(cr, uid, line_id, {'text_error': text_error}, context)
                if error or list_message:
                    if consumed_qty or product_id == product_tbd:
                        lines_to_correct += 1
                cr.commit()
            except IndexError, e:
                # the IndexError is often happening when we open Excel file into LibreOffice because the latter adds empty lines
                error_log += _("Line %s ignored: the system reference an object that doesn't exist in the Excel file. Details: %s\n") % (line_num, e)
                ignore_lines += 1
                cr.rollback()
                continue
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                error_log += _("Line %s in the Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                ignore_lines += 1
                cr.rollback()
                continue
            except Exception, e:
                error_log += _("Line %s ignored: an error appeared in the Excel file. Details: %s\n") % (line_num, e)
                ignore_lines += 1
                cr.rollback()
                continue
        if error_log: error_log = _("Reported errors for ignored lines : \n") + error_log
        end_time = time.time()
        total_time = str(round(end_time-start_time)) + _(' second(s)')
        vals = {'message': _(''' Importation completed in %s second(s)!
# of imported lines : %s
# of lines to correct: %s
# of ignored lines: %s
%s
''') % (total_time ,complete_lines, lines_to_correct, ignore_lines, error_log)}
        try:
            self.write(cr, uid, ids, vals, context=context)

            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'wizard_to_import_rac_end')[1],

            return {'type': 'ir.actions.act_window',
                    'res_model': 'wizard.import.rac',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                    'res_id': ids[0],
                    'view_id': [view_id],
                    'context': context,
                    }
        except Exception, e:
            raise osv.except_osv(_('Error !'), _('%s !') % e)

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return {'type': 'ir.actions.act_window_close'}

wizard_import_rac()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
