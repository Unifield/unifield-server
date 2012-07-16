# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF, Smile. All Rights Reserved
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

from osv import osv
from osv import fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


class tender(osv.osv):
    _inherit = 'tender'

    _columns = {
        'file_to_import': fields.binary(string='File to import', 
                                        help='You can use the template of the export for the format that you need to use'),
    }

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals = {}
        vals['tender_line_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.tender_line_ids
            for var in line_browse_list:
                vals['tender_line_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')

        vals = {}
        vals['tender_line_ids'] = []
        text_error = ''

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
        
        # iterator on rows
        reader = fileobj.getRows()
        
        # ignore the first row
        line_num = 1
        reader.next()
        for row in reader:
            # default values
            error_list = []
            to_correct_ok = False
            default_code = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','product_tbd')[1]
            product_qty = 1
            nb_lines_error = 0
            
            line_num += 1
            row_len = len(row)
            if row_len != 6:
                raise osv.except_osv(_('Error'), _(""" Tenders should have exactly 6 columns in this order:
 Product Code*, Product Name*, Quantity*, Product UoM*, Unit Price*, Delivery Requested Date*"""))
            
            product_code = row.cells[0].data
            if not product_code:
                to_correct_ok = True
                error_list.append('No Product Name')
            else:
                try:
                    product_code = product_code.strip()
                    code_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)])
                    if not code_ids:
                        default_code = False
                        to_correct_ok = True
                        comment = 'Code: %s'%product_code
                    else:
                        default_code = code_ids[0]
                except ValueError:
                     error_list.append('The Product Code has to be a string.')
                     comment = 'Product Reference (Code) to be defined'
                     to_correct_ok = True
            
            product_qty = row.cells[2].data
            if not product_qty:
                to_correct_ok = True
                error_list.append('The Product Quantity was not set, we set it to 1 by default.')
            else:
                try:
                    float(product_qty)
                    product_qty = float(product_qty)
                except ValueError:
                     error_list.append('The Product Quantity was not a number, we set it to 1 by default.')
                     to_correct_ok = True
                     product_qty = 1.0
            
            p_uom = row.cells[3].data
            if not p_uom:
                uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                to_correct_ok = True
                error_list.append('No product UoM was defined.')
            else:
                try:
                    uom_name = str(p_uom).strip()
                    uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
                    if not uom_ids:
                        uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                        to_correct_ok = True
                        error_list.append('The UOM was not found.')
                    else:
                        uom_id = uom_ids[0]
                except ValueError:
                     error_list.append('The UoM Name has to be a string.')
                     uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                     to_correct_ok = True
                
            to_write = {
                'to_correct_ok': to_correct_ok, # the lines with to_correct_ok=True will be red
                'text_error': '\n'.join(error_list), 
                'tender_id': obj.id,
                'product_id': default_code,
                'product_uom': uom_id,
                'qty': product_qty,
            }
            
            vals['tender_line_ids'].append((0, 0, to_write))
            
        # write tender line on tender
        self.write(cr, uid, ids, vals, context=context)
        
        view_id = obj_data.get_object_reference(cr, uid, 'tender_flow','tender_form')[1]
        
        nb_lines_error = self.pool.get('tender.line').search_count(cr, uid, [('to_correct_ok', '=', True)], context=context)
        
        if nb_lines_error:
            if nb_lines_error > 1:
                plural = 's have'
            elif nb_lines_error == 1:
                plural = ' has'
            msg_to_return = _("Please correct the red lines below, %s line%s errors ")%(nb_lines_error, plural)
        else:
            msg_to_return = _("All lines successfully imported")
        
        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})
        
    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for var in self.browse(cr, uid, ids, context=context):
            if var.tender_line_ids:
                for var in var.tender_line_ids:
                    if var.to_correct_ok:
                        raise osv.except_osv(_('Warning !'), _('You still have lines to correct: check the red lines'))
                    else:
                        self.log(cr, uid, var.id, _("There isn't error in import"), context=context)
        return True
        
tender()

class tender_line(osv.osv):
    '''
    override of tender_line class
    '''
    _inherit = 'tender.line'
    _description = 'Tender Line'
    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'text_error': fields.text('Errors'),
    }

tender_line()
