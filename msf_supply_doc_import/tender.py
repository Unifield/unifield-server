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
                                        help='* You can use the template of the export for the format that you need to use. \
                                            \n* The file should be in XML Spreadsheet 2003 format.'),
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
        tender_line_obj = self.pool.get('tender.line')
        view_id = obj_data.get_object_reference(cr, uid, 'tender_flow','tender_form')[1]

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
            uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
            product_qty = 1
            nb_lines_error = 0
            
            line_num += 1
            row_len = len(row)
            if row_len != 6:
                raise osv.except_osv(_('Error'), _(""" Tenders should have exactly 6 columns in this order:
Product Code*, Product Description*, Quantity*, Product UoM*, Unit Price*, Delivery Requested Date*"""))
            # we check that cells are not empty
            if [x for x in enumerate(row.cells)] :
                product_code = row.cells[0].data
                if not product_code:
                    to_correct_ok = True
                    error_list.append('No Product Description')
                else:
                    try:
                        product_code = product_code.strip()
                        code_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)])
                        if not code_ids:
                            to_correct_ok = True
                        else:
                            default_code = code_ids[0]
                    except Exception:
                         error_list.append('The Product Code has to be a string.')
                         to_correct_ok = True
                
                if not row.cells[2].data :
                    product_qty = 1.0
                    to_correct_ok = True
                    error_list.append('The Product Quantity was not set, we set it to 1 by default.')
                else:
                    if row.cells[2].type in ['int', 'float']:
                        product_qty = row.cells[2].data
                    else:
                        error_list.append('The Product Quantity was not a number and it is required to be more than 0, we set it to 1 by default.')
                        to_correct_ok = True
                        product_qty = 1.0
                
                try:
                    p_uom = row.cells[3].data
                    if not p_uom:
                        to_correct_ok = True
                        error_list.append('No product UoM was defined.')
                    else:
                        try:
                            uom_name = p_uom.strip()
                            uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
                            if not uom_ids:
                                to_correct_ok = True
                                error_list.append('The UOM was not found.')
                            else:
                                uom_id = uom_ids[0]
                        except Exception:
                             error_list.append('The UoM Name has to be a string.')
                             to_correct_ok = True
                except IndexError:
                     error_list.append('The UOM Name was not properly defined.')
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
                # we check consistency of uom and product values
                tender_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)
                vals['tender_line_ids'].append((0, 0, to_write))
            
        # write tender line on tender
        context['import_in_progress'] = True
        self.write(cr, uid, ids, vals, context=context)
        
        nb_lines_error = self.pool.get('tender.line').search_count(cr, uid, [('to_correct_ok', '=', True), ('tender_id', '=', ids[0])], context=context)
        
        if nb_lines_error:
            if nb_lines_error > 1:
                plural = 's have'
            elif nb_lines_error == 1:
                plural = ' has'
            msg_to_return = _("Please correct the red lines below, %s line%s errors ")%(nb_lines_error, plural)
        else:
            msg_to_return = _("All lines successfully imported")
        
        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id})
        
    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
            
        for var in self.browse(cr, uid, ids, context=context):
            if var.tender_line_ids:
                for var in var.tender_line_ids:
                    if var.to_correct_ok:
                        raise osv.except_osv(_('Warning !'), _('You still have lines to correct: check the red lines'))
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

    def check_data_for_uom(self, cr, uid, ids, *args, **kwargs):
        context = kwargs['context']
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        # we take the values that we are going to write in SO line in "to_write"
        to_write = kwargs['to_write']
        to_correct_ok = to_write['to_correct_ok']
        text_error = to_write['text_error']
        product_id = to_write['product_id']
        uom_id = to_write['product_uom']
        if uom_id and product_id:
            product_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            product = product_obj.browse(cr, uid, product_id, context=context)
            uom = uom_obj.browse(cr, uid, uom_id, context=context)
            if product.uom_id.category_id.id != uom.category_id.id:
                # this is inspired by onchange_uom in specific_rules>specific_rules.py
                text_error += "\n You have to select a product UOM in the same category than the UOM of the product. The category of the UoM of the product is '%s' whereas the category of the UoM you have chosen is '%s'."%(product.uom_id.category_id.name,uom.category_id.name)
                return to_write.update({'text_error': text_error,
                                        'to_correct_ok': True})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1] and product_id:
            # we take the default uom of the product
            product_uom = product.uom_id.id
            return to_write.update({'product_uom': product_uom})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]:
            # this is inspired by the on_change in purchase>purchase.py : product_uom_change
            text_error += "\n The UoM was not defined so we set the price unit to 0.0."
            return to_write.update({'text_error': text_error,
                                    'to_correct_ok': True,
                                    'price_unit':0.0,})

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context.get('import_in_progress') and not context.get('button'):
            uom_obj = self.pool.get('product.uom')
            obj_data = self.pool.get('ir.model.data')
            tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
            tbd_product = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','product_tbd')[1]
            message = ''
            
            if vals.get('product_uom'):
                if vals.get('product_uom') == tbd_uom:
                    message += 'You have to define a valid UOM, i.e. not "To be define".'
            if vals.get('product_id'):
                if vals.get('product_id') == tbd_product:
                    message += 'You have to define a valid product, i.e. not "To be define".'
            if message:
                raise osv.except_osv(_('Warning !'), _(message))
            else:
                vals['to_correct_ok'] = False
                vals['text_error'] = False
        
        return super(tender_line, self).write(cr, uid, ids, vals, context=context)

tender_line()
