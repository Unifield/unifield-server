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
from msf_doc_import import check_line
import time

class wizard_import_fmc(osv.osv_memory):
    _name = 'wizard.import.fmc'
    _description = 'Import FMC from Excel sheet'

    _columns = {
        'file': fields.binary(string='File to import', required=True),
        'message': fields.text(string='Message', readonly=True),
        'rmc_id': fields.many2one('monthly.review.consumption', string='Monthly review consumption', required=True),
    }


    def default_get(self, cr, uid, fields, context=None):
        '''
        Set rmc_id with the active_id value in context
        '''
        if not context or not context.get('active_id'):
            raise osv.except_osv(_('Error !'), _('No Monthly review consumption found !'))

        rmc_id = context.get('active_id')
        res = super(wizard_import_fmc, self).default_get(cr, uid, fields, context=context)
        res['rmc_id'] = rmc_id
        res['message'] =  _("""
        IMPORTANT: The four first lines will be ignored by the system.
        
        The file should be in Excel xml 2003 format.
        The columns should be in this order :
          * Product Code
          * Product Description
          * UoM (not imported)
          * AMC
          * FMC
          * Safety Stock (qty) - (not imported)
          * Valid Until (DD-MMM-YYYY)
        """)
        return res

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines form file
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        import_mrc = self.browse(cr, uid, ids[0], context)
        mrc_id = import_mrc.rmc_id.id

        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('monthly.review.consumption.line')
        obj_data = self.pool.get('ir.model.data')

        ignore_lines, complete_lines, lines_to_correct = 0, 0, 0

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file))

        # iterator on rows
        rows = fileobj.getRows()

        # check import template:
        for i in range(3):
            row = rows.next()
            if any([cell.data for cell in row.cells[2:]]): # if cells #2 to end are not empty
                raise osv.except_osv(_('Error'), _('Import template not recognized, please use the same as exports'))

        header = rows.next() # skip main table header

        doc_headers = self.pool.get('wizard.export.fmc').get_headers(context=context)
        if len(header) != len(doc_headers):
            raise osv.except_osv(_('Error'), _('Import template not recognized, please use the same as exports'))

        for i, h in enumerate(doc_headers):
            if h.lower().strip() != header[i].data.lower().strip():
                raise osv.except_osv(_('Error'), _("""Column %d mismatches, expected: %s, found: %s""") % (i+1, h, header[i].data))

        line_num = 1
        to_write = {}
        errors = []
        for row in rows:
            error = ''
            # default values
            to_write = {
                'error_list': [],
                'warning_list': [],
                'default_code': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1],
                'uom_id': obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1],
            }
            fmc = 0
            valid_until = False
            line_num += 1
            # Check length of the row
            if len(row) != 7:
                raise osv.except_osv(_('Error'), _("""You should have exactly 7 columns in this order:
Product Code*, Product Description*, UoM, AMC, FMC, Safety Stock (qty), Valid Until"""))

            # Cell 0: Product Code
            p_value = {}
            p_value = check_line.product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
            if p_value['default_code']:
                product_id = p_value['default_code']
            else:
                product_id = False
                error += _('Line %s in your Excel file ignored: Product Code [%s] not found ! Details: %s \n') % (line_num, row[0], p_value['error_list'])

            # Cell 3: Quantity (FMC)
            if row.cells[4] and row.cells[4].data:
                if row.cells[3].type in ('int', 'float'):
                    fmc = row.cells[4].data
                elif isinstance(row.cells[4].data, (int, long, float)):
                    fmc = row.cells[4].data
                else:
                    error += _("Line %s in your Excel file ignored: FMC should be a number and not %s \n") % (line_num, row.cells[4].data)

            # Cell 5: Date (Valid Until)
            if row[6] and row[6].data:
                if row[6].type in ('datetime', 'date'):
                    valid_until = row[6].data
                else:
                    try:
                        valid_until = time.strftime('%Y-%m-%d', time.strptime(str(row[6]), '%d/%m/%Y'))
                    except ValueError:
                        try:
                            valid_until = time.strftime('%Y-%b-%d', time.strptime(str(row[6]), '%d/%b/%Y'))
                        except ValueError as e:
                            error += _("Line %s in your Excel file: expiry date %s has a wrong format. Details: %s' \n") % (line_num, row[6], e)

            error += '\n'.join(to_write['error_list'])
            if error:
                lines_to_correct += 1
                if error not in errors:
                    errors.append(error)
            line_data = {'name': product_id,
                         'fmc': fmc,
                         'mrc_id': mrc_id,
                         'valid_until': valid_until,
                         'text_error': error,}

            context['import_in_progress'] = True
            try:
                line_obj.create(cr, uid, line_data)
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                error += _("Line %s in your Excel file: %s: %s\n") % (line_num, osv_name, osv_value)
                ignore_lines += 1
            complete_lines += 1

        self.write(cr, uid, ids, {'message': _('''Importation completed !
                                                # of imported lines : %s
                                                # of lines to correct: %s
                                                # of ignored lines : %s
                                                
                                                Reported errors :
                                                %s
                                             ''') % (complete_lines, lines_to_correct, ignore_lines, ' '.join(errors) or _('No error !'))}, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'wizard_to_import_fmc_end')[1],

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.fmc',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                'view_id': [view_id],
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        return {'type': 'ir.actions.act_window_close'}

wizard_import_fmc()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
