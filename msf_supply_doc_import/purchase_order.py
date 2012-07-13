# -*- coding: utf-8 -*-

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
        'file_to_import': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use'),
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
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        currency_obj = self.pool.get('res.currency')

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
            functional_currency_id = False
            price_unit = 1
            product_qty = 1
            
            line_num += 1
            row_len = len(row)
            if row_len > 8:
                raise osv.except_osv(_('Error'), _("""You have written element outside the columns, please check your Excel file. 
Purchase Order should have 8 columns:
Product Code*, Product Name*, Qty*, Product UoM*, Unit Price*, Delivery Requested Date*, Currency*, Comment"""))
            
            product_code = row.cells[0].data
            if not product_code :
                default_code = False
                to_correct_ok = True
                error_list.append('No Product Reference (Code).')
                comment = 'Product Reference (Code) to be defined'
            else:
                code_ids = product_obj.search(cr, uid, [('default_code', 'like', product_code)])
                if not code_ids:
                    default_code = False
                    to_correct_ok = True
                    comment = 'Code: %s' %product_code
                else:
                    default_code = code_ids[0]
            
            p_id = row.cells[1].data
            if not p_id:
                product_id = False
                to_correct_ok = True
                error_list.append('No Product Name')
                comment = 'Product Name to be defined'
                nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]
                nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]
                nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]
                nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1]
            else:
                p_ids = product_obj.search(cr, uid, [('name', '=', str(p_id).strip())])
                if not p_ids:
                    product_id = False
                    to_correct_ok = True
                    comment = 'Description: %s' %str(p_id)
                    error_list.append('The Product was not found in the list of the products.')
                    nomen_manda_0 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1]
                    nomen_manda_1 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1]
                    nomen_manda_2 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1]
                    nomen_manda_3 =  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1]
                else:
                    product_id = p_ids[0]
                    nomen_manda_0 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_0
                    nomen_manda_1 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_1
                    nomen_manda_2 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_2
                    nomen_manda_3 = product_obj.browse(cr, uid, [product_id], context=context)[0].nomen_manda_3
                
            product_qty = row.cells[2].data
            if not product_qty :
                to_correct_ok = True
                error_list.append('The Product Quantity was not set, we set it to 1 by default.')
            else:
                try:
                    float(product_qty)
                    product_qty = float(product_qty)
                except ValueError:
                     error_list.append('The Product Quantity was not a number, we set it to 1 by default.')
                     to_correct_ok = True
            
            p_uom = row.cells[3].data
            if not p_uom:
                uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                to_correct_ok = True
                error_list.append('No product UoM was defined.')
            else:
                uom_ids = uom_obj.search(cr, uid, [('name', '=', str(p_uom).strip())], context=context)
                if not uom_ids:
                    uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                    to_correct_ok = True
                    error_list.append('The UOM was not found.')
                else:
                    uom_id = uom_ids[0]
                
            price_unit = row.cells[4].data
            if not price_unit:
                to_correct_ok = True
                error_list.append('The Price Unit was not set, we set it to 1 by default.')
            else:
                try:
                    float(price_unit)
                    price_unit = float(price_unit)
                except ValueError:
                     error_list.append('The Price Unit was not a number, we set it to 1 by default.')
                     to_correct_ok = True
            
            check_date = row.cells[5].data
            if check_date:
                try:
                    datetime.strptime(str(check_date), '%d/%b/%Y')
                    date_planned = check_date
                except ValueError:
                    error_list.append('The date format should be "DD-MM-YYYY", we took the one from the parent.')
                    to_correct_ok = True
            else:
                error_list.append('The date was not specified so we took the one from the parent.')
            
            curr = row.cells[6].data
            if not curr:
                to_correct_ok = True
                error_list.append('No currency was defined.')
            else:
                currency_ids = currency_obj.search(cr, uid, [('name', '=', str(curr).strip())])
                if currency_ids:
                    functional_currency_id = curr
                else:
                    error_list.append('The currency was not found or the format of the currency was not good.')
                
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
        else:
            self.log(cr, uid, var.id, _("There isn't error in import"), context=context)
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
#        if vals.get('nomen_manda_3'):
#            if vals.get('nomen_manda_3') == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1]:
#                message += 'You have to define a valid Root (in tab "Nomenclature Selection"), i.e. not "To be define".'
        if message:
            raise osv.except_osv(_('Warning !'), _(message))
        else:
            vals['to_correct_ok'] = False
            vals['text_error'] = False
        
        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

purchase_order_line()

