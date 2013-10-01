# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
import logging
import tools
from os import path
from tools.translate import _
import base64
# import below commented in utp-1344: becomes useless as the import is done in wizard
#from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
#import check_line
#from msf_doc_import import MAX_LINES_NB
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import FO_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_fo_line_import, IR_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_ir_line_import
from msf_doc_import.wizard import FO_LINE_COLUMNS_FOR_IMPORT as columns_for_fo_line_import
from msf_doc_import import GENERIC_MESSAGE
from msf_doc_import.wizard import IR_COLUMNS_FOR_IMPORT as columns_for_ir_line_import


class sale_order(osv.osv):
    """
    We override the class for import of Field Order and Internal Request
    """
    _inherit = 'sale.order'

    def init(self, cr):
        """
        Load data (msf_doc_import_data.xml) before self
        """
        if hasattr(super(sale_order, self), 'init'):
            super(sale_order, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        mode = mod_obj.search(cr, 1, [('name', '=', 'msf_doc_import'), ('state', '=', 'to install')]) and 'init' or 'update'
        logging.getLogger('init').info('HOOK: module msf_doc_import: loading data/msf_doc_import_data.xml')
        pathname = path.join('msf_doc_import', 'data/msf_doc_import_data.xml')
        file = tools.file_open(pathname)
        # mode to force noupdate=True when reloading this module
        tools.convert_xml_import(cr, 'msf_doc_import', file, {}, mode=mode, noupdate=True)

# The field below were replaced by the wizard_import_fo_line (utp-113)
#    _columns = {
#        'file_to_import': fields.binary(string='File to import',
#                                        help="""* You can use the template of the export for the format that you need to use.
#                                                * The file should be in XML Spreadsheet 2003 format.
#                                                * You can import up to %s lines each time,
#                                                else you have to split the lines in several files and import each one by one.
#                                                """ % MAX_LINES_NB),
#    }

    def copy(self, cr, uid, id, defaults=None, context=None):
        '''
        Remove the flag import_in_progress when duplicate a field order
        '''
        if not defaults:
            defaults = {}

        if not 'import_in_progress' in defaults:
            defaults.update({'import_in_progress': False})

        return super(sale_order, self).copy(cr, uid, id, defaults, context=context)

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.order_line  if item.to_correct_ok]):
                res[obj.id] = True
        return res

    _columns = {
        'hide_column_error_ok': fields.function(get_bool_values, method=True, type="boolean", string="Show column errors", store=False),
        'import_in_progress': fields.boolean(string='Importing'),
    }

    _defaults = {
        'import_in_progress': lambda *a: False,
    }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the Purchase order contains a line with an inactive products
        '''
        inactive_lines = self.pool.get('sale.order.line').search(cr, uid, [('product_id.active', '=', False),
                                                                           ('order_id', 'in', ids),
                                                                           ('order_id.state', 'not in', ['draft', 'cancel', 'done'])], context={'procurement_request': True})
        
        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')          
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the line containing those inactive products (see red %s of the document)') % (plural, l_plural))
            return False
        return True
    
    _constraints = [
        (_check_active_product, "You cannot validate this sale order because it contains a line with an inactive product", ['order_line', 'state'])
    ]

# This method was replaced by the one of the wizard wizard_import_fo_line (utp-113)
#    def import_internal_req(self, cr, uid, ids, context=None):
#        '''
#        Import lines from Excel file (in xml) for internal request
#        '''
#        if not context:
#            context = {}
#
#        product_obj = self.pool.get('product.product')
#        uom_obj = self.pool.get('product.uom')
#        obj_data = self.pool.get('ir.model.data')
#        currency_obj = self.pool.get('res.currency')
#        sale_obj = self.pool.get('sale.order')
#        sale_line_obj = self.pool.get('sale.order.line')
#        view_id = obj_data.get_object_reference(cr, uid, 'sale', 'view_order_form')[1]
#
#        vals = {}
#        vals['order_line'] = []
#
#        obj = self.browse(cr, uid, ids, context=context)[0]
#        if not obj.file_to_import:
#            raise osv.except_osv(_('Error'), _('Nothing to import.'))
#
#        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
#        # check that the max number of lines is not excedeed
#        if check_nb_of_lines(fileobj=fileobj):
#            raise osv.except_osv(_('Warning !'), _("""You can\'t have more than %s lines in your file.""") % MAX_LINES_NB)
#        # iterator on rows
#        rows = fileobj.getRows()
#        # ignore the first row
#        rows.next()
#        line_num = 0
#        to_write = {}
#        for row in rows:
#            # default values
#            browse_sale = sale_obj.browse(cr, uid, ids, context=context)[0]
#            to_write = {
#                'error_list': [],
#                'warning_list': [],
#                'to_correct_ok': False,
#                'show_msg_ok': False,
#                'comment': '',
#                'date_planned': obj.delivery_requested_date,
#                'functional_currency_id': browse_sale.pricelist_id.currency_id.id,
#                'price_unit': 1,  # in case that the product is not found and we do not have price
#                'product_qty': 1,
#                'nomen_manda_0':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1],
#                'nomen_manda_1':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1],
#                'nomen_manda_2':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1],
#                'nomen_manda_3':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd3')[1],
#                'proc_type': 'make_to_order',
#                'default_code': False,
#                'confirmed_delivery_date': False,
#            }
#
#            line_num += 1
#            col_count = len(row)
#            if col_count != 6:
#                raise osv.except_osv(_('Error'), _("""You should have exactly 6 columns in this order:
#Product Code, Product Description, Quantity, UoM, Currency, Comment.
#That means Not price, Neither Delivery requested date. """))
#            try:
#                if not check_empty_line(row=row, col_count=col_count):
#                    continue
#                # for each cell we check the value
#                # Cell 0: Product Code
#                p_value = {}
#                p_value = product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'], 'price_unit': p_value['price_unit'],
#                                 'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})
#
#                # Cell 2: Quantity
#                qty_value = {}
#                qty_value = quantity_value(product_obj=product_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'product_uom_qty': qty_value['product_qty'], 'error_list': qty_value['error_list']})
#
#                # Cell 3: UoM
#                uom_value = {}
#                uom_value = compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})
#
#                # Cell 4: Currency
#                curr_value = {}
#                curr_value = compute_currency_value(cr, uid, cell=4, browse_sale=browse_sale,
#                                                    currency_obj=currency_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})
#
#                # Cell 5: Comment
#                c_value = {}
#                c_value = comment_value(row=row, cell=5, to_write=to_write, context=context)
#                to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
#                to_write.update({
#                    'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
#                    'show_msg_ok': [True for x in to_write['warning_list']],  # the lines with show_msg_ok=True won't change color, it is just info
#                    'order_id': obj.id,
#                    'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
#                })
#                # we check consistency on the model of on_change functions to call for updating values
#                sale_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)
#                vals['order_line'].append((0, 0, to_write))
#            except IndexError:
#                print "The line num %s in the Excel file got element outside the defined 6 columns" % line_num
#
#        # write order line on SO
#        context['import_in_progress'] = True
#        self.write(cr, uid, ids, vals, context=context)
#        self._check_service(cr, uid, ids, vals, context=context)
#        msg_to_return = get_log_message(to_write=to_write, obj=obj)
#        if msg_to_return:
#            self.log(cr, uid, obj.id, _(msg_to_return), context={'view_id': view_id, })
#        return True

# This method was replaced by the one of the wizard wizard_import_fo_line (utp-113)
#    def import_file(self, cr, uid, ids, context=None):
#        '''
#        Import lines from Excel file (in xml)
#        '''
#        if not context:
#            context = {}
#        if isinstance(ids, (int, long)):
#            ids = [ids]
#
#        if context.get('_terp_view_name', False) == self.pool.get('ir.translation').tr_view(cr, 'Internal Requests', context):
#            return self.import_internal_req(cr, uid, ids, context=context)
#
#        product_obj = self.pool.get('product.product')
#        uom_obj = self.pool.get('product.uom')
#        obj_data = self.pool.get('ir.model.data')
#        currency_obj = self.pool.get('res.currency')
#        sale_obj = self.pool.get('sale.order')
#        sale_line_obj = self.pool.get('sale.order.line')
#        view_id = obj_data.get_object_reference(cr, uid, 'sale', 'view_order_form')[1]
#
#        vals = {}
#        vals['order_line'] = []
#
#        obj = self.browse(cr, uid, ids, context=context)[0]
#        if not obj.file_to_import:
#            raise osv.except_osv(_('Error'), _('Nothing to import.'))
#
#        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
#        # check that the max number of lines is not excedeed
#        if check_nb_of_lines(fileobj=fileobj):
#            raise osv.except_osv(_('Warning !'), _("""You can\'t have more than %s lines in your file.""") % MAX_LINES_NB)
#        # iterator on rows
#        rows = fileobj.getRows()
#        # ignore the first row
#        rows.next()
#        line_num = 0
#        to_write = {}
#        for row in rows:
#            # default values
#            browse_sale = sale_obj.browse(cr, uid, ids, context=context)[0]
#            to_write = {
#                'error_list': [],
#                'warning_list': [],
#                'to_correct_ok': False,
#                'show_msg_ok': False,
#                'comment': '',
#                'date_planned': obj.delivery_requested_date,
#                'functional_currency_id': browse_sale.pricelist_id.currency_id.id,
#                'price_unit': 1,  # in case that the product is not found and we do not have price
#                'product_qty': 1,
#                'nomen_manda_0':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1],
#                'nomen_manda_1':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1],
#                'nomen_manda_2':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1],
#                'nomen_manda_3':  obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd3')[1],
#                'proc_type': 'make_to_order',
#                'default_code': False,
#                'confirmed_delivery_date': False,
#            }
#
#            line_num += 1
#            col_count = len(row)
#            if col_count != 8:
#                raise osv.except_osv(_('Error'), _("""You should have exactly 8 columns in this order:
#Product Code*, Product Description*, Quantity*, Product UoM*, Unit Price*, Delivery Requested Date*, Currency*, Comment. """))
#            try:
#                if not check_empty_line(row=row, col_count=col_count):
#                    continue
#
#                # Cell 0: Product Code
#                p_value = {}
#                p_value = product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'], 'price_unit': p_value['price_unit'],
#                                 'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})
#
#                # Cell 2: Quantity
#                qty_value = {}
#                qty_value = quantity_value(product_obj=product_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'product_uom_qty': qty_value['product_qty'], 'error_list': qty_value['error_list']})
#
#                # Cell 3: UOM
#                uom_value = {}
#                uom_value = compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})
#
#                # Cell 4: Price
#                price_value = {}
#                price_value = compute_price_value(row=row, to_write=to_write, price='Field Price', context=context)
#                to_write.update({'price_unit': price_value['price_unit'], 'error_list': price_value['error_list'],
#                                 'warning_list': price_value['warning_list']})
#
#                # Cell 5: Date
#                date_value = {}
#                date_value = compute_date_value(row=row, to_write=to_write, context=context)
#                to_write.update({'date_planned': date_value['date_planned'], 'error_list': date_value['error_list'],
#                                 'warning_list': date_value['warning_list']})
#
#                # Cell 6: Currency
#                curr_value = {}
#                curr_value = compute_currency_value(cr, uid, cell=6, browse_sale=browse_sale,
#                                                    currency_obj=currency_obj, row=row, to_write=to_write, context=context)
#                to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})
#
#                # Cell 7: Comment
#                c_value = {}
#                c_value = comment_value(row=row, cell=7, to_write=to_write, context=context)
#                to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
#                to_write.update({
#                    'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
#                    'show_msg_ok': [True for x in to_write['warning_list']],  # the lines with show_msg_ok=True won't change color, it is just info
#                    'order_id': obj.id,
#                    'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
#                })
#                # we check consistency on the model of on_change functions to call for updating values
#                sale_line_obj.check_data_for_uom(cr, uid, ids, to_write=to_write, context=context)
#
#                vals['order_line'].append((0, 0, to_write))
#
#            except IndexError:
#                print "The line num %s in the Excel file got element outside the defined 8 columns" % line_num
#
#        # write order line on PO
#        context['import_in_progress'] = True
#        self.write(cr, uid, ids, vals, context=context)
#        msg_to_return = get_log_message(to_write=to_write, obj=obj)
#        if msg_to_return:
#            self.log(cr, uid, obj.id, _(msg_to_return), context={'view_id': view_id, })
#        return True

    def wizard_import_ir_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_ir_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.ir.line').create(cr, uid, {'file': file,
                                                                            'filename_template': 'template.xls',
                                                                            'filename': 'Lines_Not_Imported.xls',
                                                                            'message': """%s %s"""  % (GENERIC_MESSAGE, ', '.join([_(f) for f in columns_for_ir_line_import]), ),
                                                                            'fo_id': ids[0],
                                                                            'state': 'draft',}, context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.ir.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def wizard_import_fo_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_fo_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.encodestring(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.fo.line').create(cr, uid, {'file': file,
                                                                            'filename_template': 'template.xls',
                                                                            'filename': 'Lines_Not_Imported.xls',
                                                                            'message': """%s %s"""  % (GENERIC_MESSAGE, ', '.join([_(f) for f in columns_for_fo_line_import]), ),
                                                                            'fo_id': ids[0],
                                                                            'state': 'draft',}, context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.fo.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural = ''

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
                    elif not var.product_id:
                        if not var.nomen_manda_0 or not var.nomen_manda_1 or not var.nomen_manda_2:
                            line_num = var.line_number
                            if message:
                                message += ', '
                            message += str(line_num)
                            if len(message.split(',')) > 1:
                                plural = 's'
                            message += _(" Please define the nomenclature levels.")
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s: %s') % (plural, message))
        return True

sale_order()


class sale_order_line(osv.osv):
    '''
    override of sale_order_line class
    '''
    _inherit = 'sale.order.line'
    _description = 'Sale Order Line'
    
    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if not line.procurement_request and line.comment:
                res[line.id].update({'inactive_error': line.comment})
            if line.order_id and line.order_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {'inactive_product': True,
                                'inactive_error': _('The product in line is inactive !')}
                
        return res
    
    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'show_msg_ok': fields.boolean('Info on importation of lines'),
        'text_error': fields.text('Errors when trying to import file'),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
    }
    
    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
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
        text_error = to_write['text_error']
        product_id = to_write['product_id']
        uom_id = to_write['product_uom']
        if uom_id and product_id:
            if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, uom_id, context):
                text_error += _("""\n You have to select a product UOM in the same category than the UOM of the product.""")
                return to_write.update({'text_error': text_error,
                                        'to_correct_ok': True})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1] and product_id:
            # we take the default uom of the product
            product_uom = product.uom_id.id
            return to_write.update({'product_uom': product_uom})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]:
            # this is inspired by the on_change in purchase>purchase.py: product_uom_change
            text_error += _("\n The UoM was not defined so we set the price unit to 0.0.")
            return to_write.update({'text_error': text_error,
                                    'to_correct_ok': True,
                                    'price_unit': 0.0, })

    def onchange_uom(self, cr, uid, ids, product_id, uom_id, product_qty=0.00, context=None):
        '''
        Check if the UoM is convertible to product standard UoM
        '''
        res = {'domain':{}, 'warning':{}}
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        uom = False
        
        if product_id:
            product = product_obj.browse(cr, uid, product_id, context=context)
            
            domain = {'product_uom': [('category_id', '=', product.uom_id.category_id.id)]}
            res['domain'] = domain
            if uom_id:
                if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, uom_id, context):
                    warning = {'title': _('Wrong Product UOM !'),
                               'message': _("You have to select a product UOM in the same category than the purchase UOM of the product")}
                    res['warning'] = warning

                unit_price = self.pool.get('product.uom')._compute_price(cr, uid, product.uom_id.id, product.list_price, uom_id)
                res.setdefault('value', {}).update({'price_unit': unit_price,
                                                    'cost_price': unit_price})

        # Round-up the quantity
        if uom_id and product_qty:
            res = uom_obj._change_round_up_qty(cr, uid, uom_id, product_qty, ['product_uos_qty', 'product_uom_qty'], result=res)

        return res

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        message = ''

        if not context.get('import_in_progress') or not context.get('button') and context.get('button') == 'save_and_close':

            if vals.get('product_uom') or vals.get('nomen_manda_0') or vals.get('nomen_manda_1') or vals.get('nomen_manda_2'):
                if vals.get('product_uom') and vals.get('product_uom') == tbd_uom:
                    message += _('You have to define a valid UOM, i.e. not "To be defined".')
                if vals.get('nomen_manda_0') and vals.get('nomen_manda_0') == obj_data.get_object_reference(cr, uid,
                                                                                                            'msf_doc_import', 'nomen_tbd0')[1]:
                    message += _('You have to define a valid Main Type (in tab "Nomenclature Selection"), i.e. not "To be defined".')
                if vals.get('nomen_manda_1') and vals.get('nomen_manda_1') == obj_data.get_object_reference(cr, uid,
                                                                                                            'msf_doc_import', 'nomen_tbd1')[1]:
                    message += _('You have to define a valid Group (in tab "Nomenclature Selection"), i.e. not "To be defined".')
                if vals.get('nomen_manda_2') and vals.get('nomen_manda_2') == obj_data.get_object_reference(cr, uid,
                                                                                                            'msf_doc_import', 'nomen_tbd2')[1]:
                    message += _('You have to define a valid Family (in tab "Nomenclature Selection"), i.e. not "To be defined".')

                if vals.get('product_uom') and vals.get('product_id'):
                    product_id = vals.get('product_id')
                    uom_id = vals.get('product_uom')
                    res = self.onchange_uom(cr, uid, ids, product_id, uom_id, context=context)
                    if res and res.get('warning', False):
                        message += res['warning']['message']

                if message and not context.get('procurement_request', False):
                    raise osv.except_osv(_('Warning !'), _(message))

                else:
                    vals['show_msg_ok'] = False
                    vals['to_correct_ok'] = False
                    vals['text_error'] = False

        return super(sale_order_line, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        message = ''
        if not context.get('import_in_progress'):
            if vals.get('product_uom') and vals.get('product_id'):
                product_id = vals.get('product_id')
                product_uom = vals.get('product_uom')
                res = self.onchange_uom(cr, uid, False, product_id, product_uom, context=context)
                if res and res.get('warning', False):
                    message += res['warning']['message']
            if message:
                raise osv.except_osv(_('Warning !'), _(message))
        return super(sale_order_line, self).create(cr, uid, vals, context=context)

sale_order_line()
