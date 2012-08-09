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

from datetime import datetime

from osv import osv
from osv import fields
import logging
import tools
from os import path
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML

class sale_order(osv.osv):
    """
    We override the class for import of Field Order and Internal Request
    """
    _inherit = 'sale.order'

    def init(self, cr):
        """
        Load data (msf_supply_doc_import_data.xml) before self
        """
        if hasattr(super(sale_order, self), 'init'):
            super(sale_order, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        logging.getLogger('init').info('HOOK: module msf_supply_doc_import: loading data/msf_supply_doc_import_data.xml')
        pathname = path.join('msf_supply_doc_import', 'data/msf_supply_doc_import_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'msf_supply_doc_import', file, {}, mode='init', noupdate=False)

    _columns = {
        'file_to_import': fields.binary(string='File to import', 
                                        help='* You can use the template of the export for the format that you need to use. \
                                            \n* The file should be in XML Spreadsheet 2003 format.'
                                        ),
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
        vals['order_line'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.order_line
            for var in line_browse_list:
                vals['order_line'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True

    def import_internal_req(self, cr, uid, ids, context=None):
        '''
        Import lines from file specially for internal request
        '''
        if not context:
            context = {}
        
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        view_id = obj_data.get_object_reference(cr, uid, 'sale','view_order_form')[1]

        vals = {}
        vals['order_line'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
        
        # iterator on rows
        reader = fileobj.getRows()
        
        # ignore the first row
        reader.next()
        line_num = 0
        for row in reader:
            # default values
            error_list = []
            to_correct_ok = False
            show_msg_ok = False
            comment = ''
            browse_sale = sale_obj.browse(cr, uid, ids, context=context)[0]
            functional_currency_id = browse_sale.pricelist_id.currency_id.id
            product_qty = 1
            nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]
            nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]
            nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]
            nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1]
            proc_type = 'make_to_order'
            
            line_num += 1
            row_len = len(row)
            if row_len != 6:
                raise osv.except_osv(_('Error'), _("""You should have exactly 6 columns in this order: 
Product Code, Product Description, Quantity, UoM, Currency, Comment.
That means Not price, Neither Delivery requested date. """))
            try:
                if row.cells[0].data or row.cells[1].data or row.cells[2].data or row.cells[3].data or row.cells[4].data or row.cells[5].data:
                    # for each cell we check the value
                    product_code = row.cells[0].data
                    p_name = row.cells[1].data
                    if product_code and p_name:
                        try:
                            product_code = product_code.strip()
                            product_name = p_name.strip()
                            p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code),('name', '=', product_name)])
                            if not p_ids:
                                default_code = False
                                product_id = False
                                to_correct_ok = True
                                comment += ' Code: %s, Description: %s'%(product_code, product_name)
                                error_list.append('The Product\'s Code and Description do not match.')
                            else:
                                default_code = p_ids[0]
                                product_id = p_ids[0]
                                nomen_manda_0 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_0
                                nomen_manda_1 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_1
                                nomen_manda_2 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_2
                                nomen_manda_3 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_3
                                proc_type = product_obj.browse(cr, uid, [product_id], context=context)[0].procure_method
                        except Exception:
                             error_list.append('The Product Code and Description have to be a string.')
                             comment += ' Product Code and Description to be defined'
                             product_id = False
                             default_code = False
                             to_correct_ok = True
                    else:
                        default_code = False
                        product_id = False
                        to_correct_ok = True
                        comment += ' Code: %s, Description: %s'%(product_code or 'To be defined', p_name or 'To be defined')
                        error_list.append('The Product\'s Code and Description have to be defined both.')
                        
                    if not row.cells[2].data:
                        to_correct_ok = True
                        product_qty = 1.0
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
                            uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                            to_correct_ok = True
                            error_list.append('No product UoM was defined.')
                        else:
                            try:
                                uom_name = p_uom.strip()
                                uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
                                if not uom_ids:
                                    uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                                    to_correct_ok = True
                                    error_list.append('The UOM was not found.')
                                else:
                                    uom_id = uom_ids[0]
                            except Exception:
                                 error_list.append('The UOM Name has to be a string.')
                                 uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                                 to_correct_ok = True
                    except IndexError:
                         error_list.append('The UOM Name was not properly defined.')
                         uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                         to_correct_ok = True
                        
                    try:
                        curr = row.cells[4].data
                        if not curr:
                            show_msg_ok = True
                            error_list.append('No currency was defined.')
                        else:
                            try:
                                curr_name = curr.strip().upper()
                                currency_ids = currency_obj.search(cr, uid, [('name', '=', curr_name)])
                                if currency_ids[0] == browse_sale.pricelist_id.currency_id.id:
                                    functional_currency_id = currency_ids[0]
                                else:
                                    error_list.append("The imported currency '%s' was not consistent and has been replaced by the currency '%s' of the order, please check the price."%(currency_obj.browse(cr, uid, currency_ids, context=context)[0].name, browse_sale.pricelist_id.currency_id.name))
                                    show_msg_ok = True
                            except Exception:
                                 error_list.append('The Currency Name was not found.')
                                 show_msg_ok = True
                    except IndexError:
                         error_list.append('The Currency Name was not properly defined.')
                         show_msg_ok = True
                    
                    try:
                        if row.cells[5].data:
                            if comment:
                                comment += ', %s'%row.cells[5].data
                            else:
                                comment = row.cells[5].data
                    except Exception:
                        error_list.append("No comment was defined")
                        show_msg_ok = True
                        
                    to_write = {
                        'to_correct_ok': to_correct_ok, # the lines with to_correct_ok=True will be red
                        'show_msg_ok': show_msg_ok, # the lines with show_msg_ok=True won't change color, it is just info
                        'comment': comment,
                        'nomen_manda_0': nomen_manda_0,
                        'nomen_manda_1': nomen_manda_1,
                        'nomen_manda_2': nomen_manda_2,
                        'nomen_manda_3': nomen_manda_3,
                        'confirmed_delivery_date': False,
                        'order_id': obj.id,
                        'default_code':  default_code,
                        'product_id': product_id,
                        'product_uom': uom_id,
                        'product_uom_qty': product_qty,
                        'functional_currency_id': functional_currency_id,
                        'type': proc_type,
                        'text_error': '\n'.join(error_list), 
                    }
                    # we check consistency on the model of on_change functions to call for updating values
                    sale_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)
                    vals['order_line'].append((0, 0, to_write))
            except IndexError:
                print "The line num %s in the Excel file got element outside the defined 6 columns"% line_num
            
        # write order line on SO
        context['import_in_progress'] = True
        self.write(cr, uid, ids, vals, context=context)
        
        if [x for x in obj.order_line if x.to_correct_ok]:
            msg_to_return = "The import of lines had errors, please correct the red lines below"
        
        return self.log(cr, uid, obj.id, _(msg_to_return), context={'view_id': view_id,})
    
    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        if not context:
            context = {}
            
        if context.get('_terp_view_name', False) == 'Internal Requests':
            return self.import_internal_req(cr, uid, ids, context=context)
            
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        sale_obj = self.pool.get('sale.order')
        sale_line_obj = self.pool.get('sale.order.line')
        view_id = obj_data.get_object_reference(cr, uid, 'sale','view_order_form')[1]

        vals = {}
        vals['order_line'] = []
        msg_to_return = _("All lines successfully imported")

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
        
        # iterator on rows
        reader = fileobj.getRows()
        
        # ignore the first row
        reader.next()
        line_num = 0
        for row in reader:
            # default values
            error_list = []
            to_correct_ok = False
            show_msg_ok = False
            comment = ''
            date_planned = obj.delivery_requested_date
            browse_sale = sale_obj.browse(cr, uid, ids, context=context)[0]
            functional_currency_id = browse_sale.pricelist_id.currency_id.id
            price_unit = 1 # in case that the product is not found and we do not have price
            product_qty = 1
            nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]
            nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]
            nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]
            nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1]
            proc_type = 'make_to_order'
            
            line_num += 1
            row_len = len(row)
            if row_len != 8:
                raise osv.except_osv(_('Error'), _("""You should have exactly 8 columns in this order:
Product Code*, Product Description*, Quantity*, Product UoM*, Unit Price*, Delivery Requested Date*, Currency*, Comment. """))
            try:
                if row.cells[0].data or row.cells[1].data or row.cells[2].data or row.cells[3].data or row.cells[4].data or row.cells[5].data or row.cells[6].data or row.cells[7].data:
                    # for each cell we check the value
                    product_code = row.cells[0].data
                    p_name = row.cells[1].data
                    if product_code and p_name:
                        try:
                            product_code = product_code.strip()
                            product_name = p_name.strip()
                            p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code),('name', '=', product_name)])
                            if not p_ids:
                                default_code = False
                                product_id = False
                                to_correct_ok = True
                                comment += ' Code: %s, Description: %s'%(product_code, product_name)
                                error_list.append('The Product\'s Code and Description do not match.')
                            else:
                                default_code = p_ids[0]
                                product_id = p_ids[0]
                                nomen_manda_0 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_0
                                nomen_manda_1 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_1
                                nomen_manda_2 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_2
                                nomen_manda_3 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_3
                                proc_type = product_obj.browse(cr, uid, [product_id], context=context)[0].procure_method
                                price_unit = product_obj.browse(cr, uid, [product_id], context=context)[0].list_price
                        except Exception:
                             error_list.append('The Product Code and Description have to be a string.')
                             comment += ' Product Code and Description to be defined'
                             product_id = False
                             default_code = False
                             to_correct_ok = True
                    else:
                        default_code = False
                        product_id = False
                        to_correct_ok = True
                        comment += ' Code: %s, Description: %s'%(product_code or 'To be defined', p_name or 'To be defined')
                        error_list.append('The Product\'s Code and Description have to be defined both.')
                        
                    if not row.cells[2].data :
                        to_correct_ok = True
                        error_list.append('The Product Quantity was not set, we set it to 1 by default.')
                    else:
                        if row.cells[2].type in ['int','float']:
                            product_qty = row.cells[2].data
                        else:
                            error_list.append('The Product Quantity was not a number and it is required to be more than 0, we set it to 1 by default.')
                            to_correct_ok = True
                    
                    try:
                        p_uom = row.cells[3].data
                        if not p_uom:
                            uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                            to_correct_ok = True
                            error_list.append('No product UoM was defined.')
                        else:
                            try:
                                uom_name = p_uom.strip()
                                uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
                                if not uom_ids:
                                    uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                                    to_correct_ok = True
                                    error_list.append('The UOM was not found.')
                                else:
                                    uom_id = uom_ids[0]
                            except Exception:
                                 error_list.append('The UOM Name has to be a string.')
                                 uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                                 to_correct_ok = True
                    except IndexError:
                         error_list.append('The UOM Name was not defined properly.')
                         uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                         to_correct_ok = True
                         
                    try:
                        if not row.cells[4].data and product_id:
                            to_correct_ok = True
                            error_list.append('The Price Unit was not set, we have taken the default "Field Price" of the product.')
                        elif not row.cells[4].data and not product_id:
                            to_correct_ok = True
                            error_list.append('The Price Unit was not set and no product was found.')
                        elif row.cells[4].type not in ['int','float'] and product_id:
                             error_list.append('The Price Unit was not a number, we have taken the default "Field Price" of the product.')
                             to_correct_ok = True
                        elif row.cells[4].type not in ['int','float'] and not product_id:
                            to_correct_ok = True
                            error_list.append('The Price Unit was not a number and no product was found.')
                        else:
                            price_unit = row.cells[4].data
                    except IndexError:
                         error_list.append('The Price Unit was not defined properly.')
                         to_correct_ok = True
                    
                    try:
                        if row.cells[5].type == 'datetime':
                            date_planned = row.cells[5].data
                        else:
                            error_list.append('The date format was not in a good format so we took the one from the header.')
                            to_correct_ok = True
                    except Exception:
                        error_list.append('The date was not specified so we took the one from the header.')
                        to_correct_ok = True
                    
                    try:
                        curr = row.cells[6].data
                        if not curr:
                            show_msg_ok = True
                            error_list.append('No currency was defined.')
                        else:
                            try:
                                curr_name = curr.strip().upper()
                                currency_ids = currency_obj.search(cr, uid, [('name', '=', curr_name)])
                                if currency_ids[0] == browse_sale.pricelist_id.currency_id.id:
                                    functional_currency_id = currency_ids[0]
                                else:
                                    error_list.append("The imported currency '%s' was not consistent and has been replaced by the currency '%s' of the order, please check the price."%(currency_obj.browse(cr, uid, currency_ids, context=context)[0].name, browse_sale.pricelist_id.currency_id.name))
                                    show_msg_ok = True
                            except Exception:
                                 error_list.append('The Currency Name was not found.')
                                 show_msg_ok = True
                    except Exception:
                        error_list.append('No currency was defined.')
                        to_correct_ok = True
                    
                    try:
                        if row.cells[7].data:
                            if comment:
                                comment += ', %s'%row.cells[7].data
                            else:
                                comment = row.cells[7].data
                    except Exception:
                        error_list.append("No comment was defined")
                        show_msg_ok = True
        
                    to_write = {
                        'to_correct_ok': to_correct_ok, # the lines with to_correct_ok=True will be red
                        'show_msg_ok': show_msg_ok, # the lines with show_msg_ok=True won't change color, it is just info
                        'comment': comment,
                        'nomen_manda_0': nomen_manda_0,
                        'nomen_manda_1': nomen_manda_1,
                        'nomen_manda_2': nomen_manda_2,
                        'nomen_manda_3': nomen_manda_3,
                        'confirmed_delivery_date': False,
                        'order_id': obj.id,
                        'default_code':  default_code,
                        'product_id': product_id,
                        'product_uom': uom_id,
                        'product_uom_qty': product_qty,
                        'price_unit': price_unit,
                        'date_planned': date_planned,
                        'functional_currency_id': functional_currency_id,
                        'type': proc_type,
                        'text_error': '\n'.join(error_list), 
                    }
                    # we check consistency on the model of on_change functions to call for updating values
                    sale_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)
                    
                    vals['order_line'].append((0, 0, to_write))
            
            except IndexError:
                print "The line num %s in the Excel file got element outside the defined 8 columns"% line_num
            
        # write order line on SO
        context['import_in_progress'] = True
        self.write(cr, uid, ids, vals, context=context)
        
        if [x for x in obj.order_line if x.to_correct_ok]:
            msg_to_return = "The import of lines had errors, please correct the red lines below"
        
        return self.log(cr, uid, obj.id, _(msg_to_return), context={'view_id': view_id,})
        
    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural= ''
            
        for var in self.browse(cr, uid, ids, context=context):
            if var.order_line:
                for var in var.order_line:
                    if var.to_correct_ok:
                        line_num = var.line_number
                        if message:
                            message += ', '
                        message += str(line_num)
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s : %s')% (plural, message))
        return True
            
sale_order()

class sale_order_line(osv.osv):
    '''
    override of sale_order_line class
    '''
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line'
    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'show_msg_ok': fields.boolean('Info on importation of lines'),
        'text_error': fields.text('Errors when trying to import file'),
    }

    def check_data_for_uom(self, cr, uid, ids, *args, **kwargs):
        """
        We check consistency between product and uom
        """
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

    def save_and_close(self, cr, uid, ids, context=None):
        '''
        Save and close the configuration window for internal request
        '''
        vals = {}
        self.write(cr, uid, ids, vals, context=context)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')[1]
        return {'type': 'ir.actions.act_window_close',
                'res_model': 'sale.order',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': [view_id],
                }

    def open_order_line_to_correct(self, cr, uid, ids, context=None):
        '''
        Open Order Line in form view for internal request
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        view_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'view_order_line_to_correct_form')[1]
        view_to_return = {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order.line',
            'type': 'ir.actions.act_window',
            'res_id': ids[0],
            'target': 'new',
            'context': context,
            'view_id': [view_id],
        }
        return view_to_return

    def onchange_uom(self, cr, uid, ids, product_id, uom_id, context=None):
        '''
        Check if the UoM is convertible to product standard UoM
        '''
        res = {}
        if uom_id and product_id:
            product_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
        
            product = product_obj.browse(cr, uid, product_id, context=context)
            uom = uom_obj.browse(cr, uid, uom_id, context=context)
        
            if product.uom_id.category_id.id != uom.category_id.id:
                warning = {
                    'title': 'Wrong Product UOM !',
                    'message':
                        "You have to select a product UOM in the same category than the purchase UOM of the product"
                    }
                res.update({'warning': warning})
                domain = {'product_uom':[('category_id','=',product.uom_id.category_id.id)]}
                res['domain'] = domain
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
        message = ''
        
        if not context.get('import_in_progress') or not context.get('button') and context.get('button') == 'save_and_close':
            if vals.get('product_uom') or vals.get('nomen_manda_0') or vals.get('nomen_manda_1') or vals.get('nomen_manda_2'):
                if vals.get('product_uom') and vals.get('product_uom') == tbd_uom:
                    message += 'You have to define a valid UOM, i.e. not "To be define".'
                if vals.get('nomen_manda_0') and vals.get('nomen_manda_0') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]:
                    message += 'You have to define a valid Main Type (in tab "Nomenclature Selection"), i.e. not "To be define".'
                if vals.get('nomen_manda_1') and vals.get('nomen_manda_1') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]:
                    message += 'You have to define a valid Group (in tab "Nomenclature Selection"), i.e. not "To be define".'
                if vals.get('nomen_manda_2') and vals.get('nomen_manda_2') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]:
                    message += 'You have to define a valid Family (in tab "Nomenclature Selection"), i.e. not "To be define".'
                if vals.get('product_uom') and vals.get('product_id') :
                    product_id = vals.get('product_id')
                    uom_id = vals.get('product_uom')
                    res = self.onchange_uom(cr, uid, ids, product_id, uom_id, context)
                    if res and res['warning']:
                        message += res['warning']['message']
                if message:
                    raise osv.except_osv(_('Warning !'), _(message))
                else:
                    vals['show_msg_ok'] = False
                    vals['to_correct_ok'] = False
                    vals['text_error'] = False
        
        return super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

sale_order_line()

