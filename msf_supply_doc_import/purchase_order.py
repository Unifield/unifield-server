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

class purchase_order(osv.osv):
    _inherit = 'purchase.order'

    def init(self, cr):
        """
        Load data (product_data.xml) before self
        """
        if hasattr(super(purchase_order, self), 'init'):
            super(purchase_order, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        logging.getLogger('init').info('HOOK: module product: loading product_data.xml')
        pathname = path.join('product', 'product_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'product', file, {}, mode='init', noupdate=False)

    _columns = {
        'file_to_import': fields.binary(string='File to import', 
                                        help='You can use the template of the export for the format that you need to use'),
    }

    def hook_rfq_sent_check_lines(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the rfq_sent method from tender_flow>tender_flow.py
        - check lines after import
        '''
        res = super(purchase_order, self).hook_rfq_sent_check_lines(cr, uid, ids, context)
        
        if self.check_lines_to_fix(cr, uid, ids, context):
            res = False
        return res

    def _get_import_error(self, cr, uid, ids, fields, arg, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for var in self.browse(cr, uid, ids, context=context):
            res[var.id] = False
            if var.order_line:
                for var in var.order_line:
                    if var.to_correct_ok:
                        res[var.id] = True
        return res

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml', help='* You can use the template of the export for the format that you need to use. \
                                                                                        \n* The file should be in XML Spreadsheet 2003 format.'),
        'import_error_ok':fields.function(_get_import_error,  method=True, type="boolean", string="Error in Import", store=True),
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

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')
        purchase_obj = self.pool.get('purchase.order')
        purchase_line_obj = self.pool.get('purchase.order.line')

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
        line_num = 1
        for row in reader:
            # default values
            error_list = []
            to_correct_ok = False
            comment = False
            date_planned = obj.delivery_requested_date
            browse_purchase = purchase_obj.browse(cr, uid, ids, context=context)[0]
            functional_currency_id = browse_purchase.pricelist_id.currency_id.id
            price_unit = 0 # as the price unit cannot be null, it will be computed in the method "compute_price_unit" after.
            product_qty = 1.0
            nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]
            nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]
            nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]
            nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1]
            
            line_num += 1
            row_len = len(row)
            if row_len != 8:
                raise osv.except_osv(_('Error'), _("""You should have exactly 8 columns in this order:
Product Code*, Product Description*, Quantity*, Product UoM*, Unit Price*, Delivery Requested Date*, Currency*, Comment"""))
            
            product_code = row.cells[0].data
            if not product_code :
                default_code = False
                to_correct_ok = True
                error_list.append('No Product Code.')
                comment = 'Product Code to be defined'
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
                except Exception:
                     error_list.append('The Product Code has to be a string.')
                     comment = 'Product Code to be defined'
                     default_code = False
                     to_correct_ok = True
            
            p_id = row.cells[1].data
            if not p_id:
                product_id = False
                to_correct_ok = True
                error_list.append('No Product Description')
                comment = 'Product Description to be defined'
            else:
                try:
                    p_name = p_id.strip()
                    p_ids = product_obj.search(cr, uid, [('name', '=', p_name)])
                    if not p_ids:
                        product_id = False
                        to_correct_ok = True
                        comment = 'Description: %s' %p_name
                        error_list.append('The Product was not found in the list of the products.')
                    else:
                        product_id = p_ids[0]
                        nomen_manda_0 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_0
                        nomen_manda_1 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_1
                        nomen_manda_2 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_2
                        nomen_manda_3 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_3
                except Exception:
                     error_list.append('The Product Description has to be a string.')
                     comment = 'Product Description to be defined'
                     product_id = False
                     to_correct_ok = True
                
            if not row.cells[2].data :
                product_qty = 1.0
                to_correct_ok = True
                error_list.append('The Product Quantity was not set and it is required to be more than 0, we set it to 1 by default.')
            else:
                if row.cells[4].type in ['int', 'float']:
                    product_qty = row.cells[2].data
                else:
                     error_list.append('The Product Quantity was not a number and it is required to be more than 0, we set it to 1 by default.')
                     to_correct_ok = True
                     product_qty = 1.0
            
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
                     error_list.append('The UOM name has to be a string.')
                     uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                     to_correct_ok = True
                
            if not row.cells[4].data:
                to_correct_ok = True
                error_list.append('The Price Unit was not set, we set it to 0 by default but ou cannot have a price unit with 0 quantity.')
            else:
                if row.cells[4].type in ['int', 'float']:
                    price_unit = row.cells[4].data
                else:
                     error_list.append('The Price Unit was not a number, we set it to 0 by default.')
                     to_correct_ok = True
            
            if row.cells[5].data:
                if row.cells[5].type == 'datetime':
                    date_planned = row.cells[5].data
                else:
                    error_list.append('The date format was not good so we took the date from the parent.')
                    to_correct_ok = True
            else:
                error_list.append('The date was not specified or so we took the one from the parent.')
                to_correct_ok = True
            
            curr = row.cells[6].data
            if not curr:
                to_correct_ok = True
                error_list.append('No currency was defined.')
            else:
                try:
                    curr_name = curr.strip()
                    currency_ids = currency_obj.search(cr, uid, [('name', '=', curr_name)])
                    if currency_ids[0] == browse_purchase.pricelist_id.currency_id.id:
                        functional_currency_id = currency_ids[0]
                    else:
                        error_list.append('The imported currency was not consistent and has been replaced by the currency of the order, please check the price.')
                        to_correct_ok = True
                except Exception:
                     error_list.append('The Currency Name has to be a string.')
                     to_correct_ok = True
                
            proc_type = 'make_to_stock'
            for product in product_obj.read(cr, uid, ids, ['type'], context=context):
                if product['type'] == 'service_recep':
                    proc_type = 'make_to_order'

            to_write = {
                'to_correct_ok': to_correct_ok, # the lines with to_correct_ok=True will be red
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
                'product_qty': product_qty,
                'price_unit': price_unit,
                'date_planned': date_planned,
                'functional_currency_id': functional_currency_id,
                'type': proc_type,
                'text_error': '\n'.join(error_list), 
            }
            # we check consistency on the model of on_change functions to call for updating values
            purchase_line_obj.check_line_consistency(cr, uid, ids, to_write=to_write, context=context)
            
            vals['order_line'].append((0, 0, to_write))
            
        # write order line on PO
        self.write(cr, uid, ids, vals, context=context)
        
        view_id = obj_data.get_object_reference(cr, uid, 'purchase','purchase_order_form')[1]
        
        for line in obj.order_line:
            if line.to_correct_ok:
                msg_to_return = _("The import of lines had errors, please correct the red lines below")
        
        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})
        
        
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
        
purchase_order()

class purchase_order_line(osv.osv):
    '''
    override of purchase_order_line class
    '''
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'
    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'text_error': fields.text('Errors when trying to import file'),
    }

    def check_line_consistency(self, cr, uid, ids, *args, **kwargs):
        """
        After having taken the value in the to_write variable we are going to check them.
        This function routes the value to check in dedicated methods (one for checking UoM, an other for Price Unit...).
        """
        context = kwargs['context']
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        error_list = []
        to_write = kwargs['to_write']
        pol_obj = self.pool.get('purchase.order.line')
        browse_pol = pol_obj.browse(cr, uid, ids, context=context)
        for pol in browse_pol:
            # on_change functions to call for updating values
            pricelist_id = pol.order_id.pricelist_id.id or False
            partner_id = pol.order_id.partner_id.id or False
            date_order = pol.order_id.date_order or False
            fiscal_position = pol.order_id.fiscal_position or False
            state =  pol.order_id.state or False
            order_id = pol.order_id.id or False
            product_id = to_write['product_id']
            product_qty = to_write['product_qty']
            uom_id = to_write['product_uom']
            if product_id and product_qty:
                self.compute_price_unit(cr, uid, ids,to_write= to_write,product_qty=product_qty, product_id=product_id, uom_id=uom_id, 
                                        state=state,order_id=order_id,pricelist_id=pricelist_id, date_order=date_order,context=context)
            if uom_id:
                self.check_data_for_uom(cr, uid, ids, to_write= to_write, context=context)
        
    def compute_price_unit(self, cr, uid, ids, *args, **kwargs):
        """
        This method was strongly influenced by the on_change method "product_id_on_change"
        in purchase_override>purchase.py
        """
        context = kwargs['context']
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        to_write = kwargs['to_write']
        text_error = to_write['text_error']
        to_correct_ok = to_write['to_correct_ok']
        product = kwargs['product_id']
        uom = kwargs['uom_id']
        qty = kwargs['product_qty']
        state = kwargs['state']
        order_id = kwargs['order_id']
        pricelist = kwargs['pricelist_id']
        date_order = kwargs['date_order']
        suppinfo_obj = self.pool.get('product.supplierinfo')
        partner_price = self.pool.get('pricelist.partnerinfo')
        all_qty = qty
        if product and not uom or uom == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]:
            uom = self.pool.get('product.product').browse(cr, uid, product).uom_po_id.id
        
        if order_id and state == 'draft' and product:
            domain = [('product_id', '=', product), 
                      ('product_uom', '=', uom), 
                      ('order_id', '=', order_id)]
            other_lines = self.search(cr, uid, domain)
            for l in self.browse(cr, uid, other_lines):
                all_qty += l.product_qty 
        
        func_curr_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        if pricelist:
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist).currency_id.id
        else:
            currency_id = func_curr_id
        
        # Update the old price value
        to_write.update({'product_qty': qty})
        if product and not to_write.get('price_unit', False) and all_qty != 0.00:
            # Display a warning message if the quantity is under the minimal qty of the supplier
            currency_id = self.pool.get('product.pricelist').browse(cr, uid, pricelist).currency_id.id
            tmpl_id = self.pool.get('product.product').read(cr, uid, product, ['product_tmpl_id'])['product_tmpl_id'][0]
            info_prices = []
            sequence_ids = suppinfo_obj.search(cr, uid, [('name', '=', partner_id),
                                                     ('product_id', '=', tmpl_id)], 
                                                     order='sequence asc', context=context)
            domain = [('uom_id', '=', uom),
                      ('currency_id', '=', currency_id),
                      '|', ('valid_from', '<=', date_order),
                      ('valid_from', '=', False),
                      '|', ('valid_till', '>=', date_order),
                      ('valid_till', '=', False)]
        
            if sequence_ids:
                min_seq = suppinfo_obj.browse(cr, uid, sequence_ids[0], context=context).sequence
                domain.append(('suppinfo_id.sequence', '=', min_seq))
                domain.append(('suppinfo_id', 'in', sequence_ids))
        
                info_prices = partner_price.search(cr, uid, domain, order='min_quantity asc, id desc', limit=1, context=context)
                
            if info_prices:
                info_price = partner_price.browse(cr, uid, info_prices[0], context=context)
                to_write.update({'old_price_unit': info_price.price, 'price_unit': info_price.price})
                text_error += '\n The product unit price has been set ' \
                              'for a minimal quantity of %s (the min quantity of the price list), '\
                              'it might change at the supplier confirmation.' % info_price.min_quantity
                to_write.update({'text_error': text_error,
                                 'to_correct_ok': True})
            else:
                old_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, to_write['price_unit'])
                to_write.update({'old_price_unit': old_price})
        else:
            old_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, to_write.get('price_unit'))
            to_write.update({'old_price_unit': old_price})
                
        # Set the unit price with cost price if the product has no staged pricelist
        if product and qty != 0.00: 
            to_write.update({'comment': False, 'nomen_manda_0': False, 'nomen_manda_1': False,
                             'nomen_manda_2': False, 'nomen_manda_3': False, 'nomen_sub_0': False, 
                             'nomen_sub_1': False, 'nomen_sub_2': False, 'nomen_sub_3': False, 
                             'nomen_sub_4': False, 'nomen_sub_5': False})
            st_price = self.pool.get('product.product').browse(cr, uid, product).standard_price
            st_price = self.pool.get('res.currency').compute(cr, uid, func_curr_id, currency_id, st_price)
        
            if to_write.get('price_unit', False) == False and (state and state == 'draft') or not state :
                to_write.update({'price_unit': st_price, 
                                 'old_price_unit': st_price})
            elif state and state != 'draft' and old_price_unit:
                to_write.update({'price_unit': old_price_unit, 
                                 'old_price_unit': old_price_unit})
                
            if to_write['price_unit'] == 0.00:
                to_write.update({'price_unit': st_price, 
                                 'old_price_unit': st_price})
                
        elif qty == 0.00:
            text_error += "\n You cannot have a 0 quantity, we set the price unit to 0.0." 
            to_write.update({'price_unit': 0.00, 
                             'old_price_unit': 0.00,
                             'to_correct_ok': True,
                             'text_error': text_error,
                             })
        elif not product and not comment and not nomen_manda_0:
            text_error += "\n You cannot save a line without quantity, nor comment, nor product"
            to_write.update({'price_unit': 0.00, 
                             'text_error': text_error,
                             'to_correct_ok': True,
                             'product_qty': 0.00, 
                             'product_uom': False, 
                             'old_price_unit': 0.00})
        
        return to_write

        
    def check_data_for_uom(self, cr, uid, ids, *args, **kwargs):
        context = kwargs['context']
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        # we take the values that we are going to write in PO line in "to_write"
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
        if not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]:
            # this is inspired by the on_change in purchase>purchase.py : product_uom_change
            text_error += "\n The UoM was not defined so we set the price unit to 0.0."
            return to_write.update({'text_error': text_error,
                                    'to_correct_ok': True,
                                    'price_unit':0.0,})

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
        message = ''
        
        if vals.get('product_uom'):
            if vals.get('product_uom') == tbd_uom:
                message += 'You have to define a valid UOM, i.e. not "To be define".'
        if vals.get('nomen_manda_0'):
            if vals.get('nomen_manda_0') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]:
                message += 'You have to define a valid Main Type (in tab "Nomenclature Selection"), i.e. not "To be define".'
        if vals.get('nomen_manda_1'):
            if vals.get('nomen_manda_1') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]:
                message += 'You have to define a valid Group (in tab "Nomenclature Selection"), i.e. not "To be define".'
        if vals.get('nomen_manda_2'):
            if vals.get('nomen_manda_2') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]:
                message += 'You have to define a valid Family (in tab "Nomenclature Selection"), i.e. not "To be define".'
        # the 3rd level is not mandatory
        if message:
            raise osv.except_osv(_('Warning !'), _(message))
        else:
            vals['to_correct_ok'] = False
            vals['text_error'] = False
        
        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

purchase_order_line()

