# -*- coding: utf-8 -*-
from osv import fields
from osv import osv
from tools.translate import _
from openpyxl import load_workbook
import base64
import tools
import time
from io import BytesIO


class wizard_return_from_unit_import(osv.osv_memory):
    _name = 'wizard.return.from.unit.import'
    _rec_name = 'picking_id'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Incoming shipment', required=True, readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'Import in progress'), ('error', 'Error'), ('done', 'Done')], string='State', readonly=True),
        'file_to_import': fields.binary(string='File to import', filters='*.xls*'),
        'filename': fields.char(size=64, string='Filename'),
        'message': fields.text(string='Message', readonly=True, translate=True),
    }

    def export_scratch_template_file(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids,(int,long)):
            ids = [ids]

        return {'type': 'ir.actions.report.xml', 'report_name': 'report_return_from_unit_xls', 'context': context}

    def go_to_in(self, cr, uid, ids, context=None):
        '''
        Return to the initial view.
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz in self.browse(cr, uid, ids, context=context):
            pick = wiz.picking_id
            xmild = self.pool.get('stock.picking')._hook_picking_get_view(cr, uid, ids, context=context, pick=pick)
            res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, xmild, ['form', 'tree'], context=context)
            res['res_id'] = pick.id
            return res

    def import_in(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids,(int,long)):
            ids = [ids]

        loc_obj = self.pool.get('stock.location')
        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        lot_obj = self.pool.get('stock.production.lot')

        start_time = time.time()
        wiz = self.browse(cr, uid, ids[0], context=context)
        pick = wiz.picking_id
        if not wiz.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        wb = load_workbook(filename=BytesIO(base64.decodestring(wiz.file_to_import)), read_only=True)
        sheet = wb.active

        header_message = ''
        error = False
        # From (Ext CU)
        from_loc_id = False
        if sheet['C9'].value:
            ext_cu = sheet['C9'].value
            loc_ids = loc_obj.search(cr, uid, [('name', '=ilike', ext_cu), ('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')], context=context)
            if loc_ids:
                if loc_ids[0] == pick.ext_cu.id:
                    from_loc_id = loc_ids[0]
                else:
                    header_message += _('\nThe imported Ext. C.U. must be the same as in the IN (%s).') % (pick.ext_cu.name,)
                    error = True
            else:
                header_message += _('\nThere is no Ext. C.U. with the name %s.') % (ext_cu,)
                error = True
        else:
            header_message += _('\nYou must fill "From" with an Ext. C.U. location.')
            error = True

        # To (Internal Location)
        to_loc_id = False
        if sheet['F9'].value:
            to_loc = sheet['F9'].value
            loc_ids = loc_obj.search(cr, uid, [('name', '=ilike', to_loc), ('usage', '=', 'internal'), ('location_category', '=', 'stock')], context=context)
            if loc_ids:
                to_loc_id = loc_ids[0]
            else:
                header_message += _('\nThere is no Internal Location with the name %s.') % (to_loc,)
                error = True
        else:
            header_message += _('\nYou must fill "To" with an Internal location.')
            error = True

        lines = []
        message = ''
        db_datetime_format = self.pool.get('date.tools').get_db_datetime_format(cr, uid, context=context)
        today = time.strftime(db_datetime_format)
        def_line = {'picking_id': pick.id, 'location_id': from_loc_id, 'location_dest_id': to_loc_id,
                    'reason_type_id': pick.reason_type_id.id, 'date': today, 'date_expected': today}
        lns_to_fix = 0
        for cell in sheet.iter_rows(min_row=13, min_col=1, max_col=8):
            line_err = ''
            if not cell[1].value:  # Stop looking at lines if there is no product
                break
            line = def_line.copy()

            # Product Code and BN/ED
            prod = False
            prod_name = cell[1].value
            prod_ids = prod_obj.search(cr, uid, [('default_code', '=ilike', prod_name)], context=context)
            if prod_ids:
                ftf = ['name', 'list_price', 'uom_id', 'perishable', 'batch_management']
                prod = prod_obj.browse(cr, uid, prod_ids[0], fields_to_fetch=ftf, context=context)
                line.update({'product_id': prod.id, 'name': prod.name, 'price_unit': prod.list_price})
                # BN/ED
                if prod.batch_management or prod.perishable:
                    bn_name = cell[5].value
                    ed = cell[6].value
                    if prod.batch_management and not bn_name:
                        line_err += _('The Batch Number is mandatory for %s. ') % (prod_name, )
                        error = True
                    if prod.perishable and not ed:
                        line_err += _('The Expiry Date is mandatory for %s. ') % (prod_name, )
                        error = True
                    if cell[6].data_type == 'd' and cell[6].is_date:
                        if bn_name or ed:
                            ed = ed.strftime('%Y-%m-%d')  # Fix format
                            if prod.batch_management and prod.perishable:
                                bn_ids = lot_obj.search(cr, uid, [('product_id', '=', prod.id), ('name', '=ilike', bn_name),
                                                                  ('life_date', '=', ed)], context=context)
                                if bn_ids:
                                    line.update({'prodlot_id': bn_ids[0], 'expired_date': ed})
                                else:
                                    line_err += _('No Batch Number was found with the name %s and the expiry date %s. ') % (bn_name, cell[6].value.strftime('%d/%m/%Y'))
                                    error = True
                            elif not prod.batch_management and prod.perishable:
                                bn_ids = lot_obj.search(cr, uid, [('product_id', '=', prod.id), ('life_date', '=', ed)], context=context)
                                ed_bn_id = False
                                if not bn_ids:
                                    # Create the internal batch number if not exists
                                    ed_bn_id = lot_obj.create(cr, uid, {'type': 'internal', 'product_id': prod.id,
                                        'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.serial'), 'life_date': ed,
                                    }, context=context)
                                line.update({'prodlot_id': bn_ids and bn_ids[0] or ed_bn_id, 'expired_date': ed})
                    else:
                        line_err += _('The Expiry Date must be a date. ')
                        error = True
            else:
                line_err += _('There is no active product %s. ') % (prod_name,)
                error = True

            # Quantity
            qty = cell[3].value
            if qty:
                if cell[3].data_type == 'n':
                    line.update({'product_qty': qty})
                else:
                    line_err += _('The quantity must be a number. ')
                    error = True
            else:
                line_err += _('The Quantity is mandatory for each line. ')
                error = True

            # UoM
            uom_name = cell[4].value
            if uom_name:
                uom_ids = uom_obj.search(cr, uid, [('name', '=ilike', uom_name)], context=context)
                if uom_ids:
                    uom_id = uom_ids[0]
                    # Check the uom category consistency
                    if prod and not self.pool.get('uom.tools').check_uom(cr, uid, prod.id, uom_id, context):
                        uom_id = prod.uom_id.id
                        line_err += _('The UoM imported was not in the same category than the UoM of the product. The UoM of the product was taken instead. ')
                    line.update({'product_uom': uom_id})
            else:
                line_err += _('The UoM is mandatory for each line. ')
                error = True

            # Comment
            if cell[7].value:
                line.update({'comment': tools.ustr(cell[7].value)})

            if line_err:
                lns_to_fix += 1
                message += _('\nLine %s: %s') % (cell[0].row, line_err)

            lines.append(line)

        wiz_state = 'done'
        if not error:
            for line in lines:
                self.pool.get('stock.move').create(cr, uid, line, context=context)
        else:
            wiz_state = 'error'

        end_time = time.time()
        total_time = str(round(end_time - start_time)) + _(' second(s)')
        final_message = _(''' 
Importation completed in %s!
# of imported lines : %s lines
# of lines to correct: %s

%s
%s
    ''') % (total_time, len(lines), lns_to_fix, header_message, message)
        self.write(cr, uid, wiz.id, {'state': wiz_state, 'message': final_message}, context=context)

        wb.close()  # Close manually because of readonly
        return True


wizard_return_from_unit_import()
