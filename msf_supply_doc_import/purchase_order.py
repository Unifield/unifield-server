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
from mx.DateTime import *
from os import path
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from check_line import *
from msf_supply_doc_import import MAX_LINES_NB
from msf_supply_doc_import.wizard import PO_COLUMNS_FOR_INTEGRATION as columns_for_po_integration, PO_COLUMNS_HEADER_FOR_INTEGRATION, NEW_COLUMNS_HEADER
from msf_supply_doc_import import check_line


class purchase_order(osv.osv):
    _inherit = 'purchase.order'

    def init(self, cr):
        """
        Load data (product_data.xml) before self
        """
        if hasattr(super(purchase_order, self), 'init'):
            super(purchase_order, self).init(cr)

        logging.getLogger('init').info('HOOK: module product: loading product_data.xml')
        pathname = path.join('product', 'product_data.xml')
        file = tools.file_open(pathname)
        tools.convert_xml_import(cr, 'product', file, {}, mode='init', noupdate=False)

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
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""* You can use the template of the export for the format that you need to use.
                                                * The file should be in XML Spreadsheet 2003 format.
                                                * You can import up to %s lines each time,
                                                else you have to split the lines in several files and import each one by one.
                                                """ % MAX_LINES_NB),
        'import_error_ok': fields.function(_get_import_error, method=True, type="boolean", string="Error in Import", store=True),
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

    def wizard_import_file(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        context.update({'active_id': ids[0]})
        columns_header = NEW_COLUMNS_HEADER
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        export_id = self.pool.get('wizard.import.po').create(cr, uid, {'file': base64.encodestring(default_template.get_xml(default_filters=['decode.utf8'])),
                                                                        'filename_template': 'template.xls',
                                                                        'filename': 'Lines_Not_Imported.xls',
                                                                        'po_id': ids[0]}, context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.po',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def export_po_integration(self, cr, uid, ids, context=None):
        '''
        Creates an XML file and launches the wizard to save it
        '''
        if context is None:
            context = {}
        po = self.browse(cr, uid, ids[0], context=context)
        header_columns = NEW_COLUMNS_HEADER
        #header_columns = [(column, 'string') for column in columns_for_po_integration]
        header_index = {}
        [header_index.update({value: index})for (index, value) in enumerate(columns_for_po_integration)]
        list_of_lines = []
        for line in po.order_line:
            new_list = []
            new_list.insert(header_index['Line*'], line.line_number)
            new_list.insert(header_index['Product Code*'], line.product_id.default_code and check_line.get_xml(line.product_id.default_code))
            new_list.insert(header_index['Product Description'], line.product_id.name and check_line.get_xml(line.product_id.name))
            new_list.insert(header_index['Quantity*'], line.product_qty)
            new_list.insert(header_index['UoM*'], line.product_uom.name and check_line.get_xml(line.product_uom.name))
            new_list.insert(header_index['Price*'], line.price_unit)
            new_list.insert(header_index['Delivery Request Date'], line.date_planned and strptime(line.date_planned,'%Y-%m-%d').strftime('%Y-%m-%d') or '')
            new_list.insert(header_index['Delivery Confirmed Date*'], line.confirmed_delivery_date and strptime(line.confirmed_delivery_date,'%Y-%m-%d').strftime('%Y-%m-%d') or '')
            #new_list.insert(header_index['Order Reference*'], po.name)
            #new_list.insert(header_index['Delivery Confirmed Date (PO)*'], po.delivery_confirmed_date and strptime(po.delivery_confirmed_date,'%Y-%m-%d').strftime('%Y-%m-%d') or '')
            new_list.insert(header_index['Origin'], line.origin and check_line.get_xml(line.origin))
            new_list.insert(header_index['Comment'], line.comment and check_line.get_xml(line.comment))
            new_list.insert(header_index['Notes'], line.notes and check_line.get_xml(line.notes))
            new_list.insert(header_index['Supplier Reference'], po.partner_ref or '')
            #new_list.insert(header_index['Destination Partner'], po.dest_partner_id and po.dest_partner_id.name or '')
            #new_list.insert(header_index['Destination Address'], po.dest_address_id and po.dest_address_id.name or po.dest_address_id.city or '')
            #new_list.insert(header_index['Invoicing Address'], po.invoice_address_id and po.invoice_address_id.name or '')
            #new_list.insert(header_index['Est. Transport Lead Time'], po.est_transport_lead_time or '')
            #new_list.insert(header_index['Transport Mode'], po.transport_type or '')
            #new_list.insert(header_index['Arrival Date in the country'], po.arrival_date and strptime(po.arrival_date,'%Y-%m-%d').strftime('%Y-%m-%d') or '')
            new_list.insert(header_index['Incoterm'], po.incoterm_id and po.incoterm_id.name and check_line.get_xml(po.incoterm_id.name) or '')
            #new_list.insert(header_index['Notes (PO)'], po.notes)
            list_of_lines.append(new_list)
        if any([f_line for f_line in list_of_lines if len(f_line) != len(header_columns)]):
            raise osv.except_osv(_('Error'), _("""The number of columns in the header should be equal to the number of columns you want to export, please check
            that what you have in the NEW_COLUMNS_HEADER (global variable defined in the __init__.py of the wizard) is the same as what you have in the lines of the list list_of_lines."""))
        instanciate_class = SpreadsheetCreator('PO', header_columns, list_of_lines)
        file = base64.encodestring(instanciate_class.get_xml(default_filters=['decode.utf8']))
        
        export_id = self.pool.get('wizard.export.po').create(cr, uid, {'po_id': ids[0], 
                                                                        'file': file, 
                                                                        'filename': 'po_%s.xls' % (po.name.replace(' ', '_')), 
                                                                        'message': 'The PO has been exported. Please click on Save As button to download the file'})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.export.po',
                'res_id': export_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                }

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
        view_id = obj_data.get_object_reference(cr, uid, 'purchase', 'purchase_order_form')[1]
        vals = {}
        vals['order_line'] = []

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
        # check that the max number of lines is not excedeed
        if check_nb_of_lines(fileobj=fileobj):
            raise osv.except_osv(_('Warning !'), _("""You can\'t have more than %s lines in your file.""") % MAX_LINES_NB)
        # iterator on rows
        rows = fileobj.getRows()
        # ignore the first row
        rows.next()
        line_num = 0
        to_write = {}
        for row in rows:
            browse_purchase = purchase_obj.browse(cr, uid, ids, context=context)[0]
            # default values
            to_write = {
                'error_list': [],
                'warning_list': [],
                'to_correct_ok': False,
                'show_msg_ok': False,
                'comment': '',
                'date_planned': obj.delivery_requested_date,
                'functional_currency_id': browse_purchase.pricelist_id.currency_id.id,
                'price_unit': 1,  # as the price unit cannot be null, it will be computed in the method "compute_price_unit" after.
                'product_qty': 1,
                'nomen_manda_0':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd0')[1],
                'nomen_manda_1':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd1')[1],
                'nomen_manda_2':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd2')[1],
                'nomen_manda_3':  obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'nomen_tbd3')[1],
                'proc_type': 'make_to_order',
                'default_code': False,
                'confirmed_delivery_date': False,
            }

            line_num += 1
            col_count = len(row)
            if col_count != 8:
                raise osv.except_osv(_('Warning !'), _("""You should have exactly 8 columns in this order:
Product Code*, Product Description*, Quantity*, Product UoM*, Unit Price*, Delivery Requested Date*, Currency*, Comment. """))
            try:
                if not check_empty_line(row=row, col_count=col_count):
                    continue

                # Cell 0: Product Code
                p_value = {}
                p_value = product_value(cr, uid, obj_data=obj_data, product_obj=product_obj, row=row, to_write=to_write, context=context)
                to_write.update({'default_code': p_value['default_code'], 'product_id': p_value['default_code'],
                                 'comment': p_value['comment'], 'error_list': p_value['error_list'], 'type': p_value['proc_type']})

                # Cell 2: Quantity
                qty_value = {}
                qty_value = quantity_value(product_obj=product_obj, row=row, to_write=to_write, context=context)
                to_write.update({'product_qty': qty_value['product_qty'], 'error_list': qty_value['error_list'],
                                 'warning_list': qty_value['warning_list']})

                # Cell 3: UOM
                uom_value = {}
                uom_value = compute_uom_value(cr, uid, obj_data=obj_data, product_obj=product_obj, uom_obj=uom_obj, row=row, to_write=to_write, context=context)
                to_write.update({'product_uom': uom_value['uom_id'], 'error_list': uom_value['error_list']})

                # Cell 4: Price
                price_value = {}
                price_value = compute_price_value(row=row, to_write=to_write, price='Cost Price', context=context)
                to_write.update({'price_unit': price_value['price_unit'], 'error_list': price_value['error_list'],
                                 'warning_list': price_value['warning_list'], 'price_unit_defined': price_value['price_unit_defined']})

                # Cell 5: Delivery Request Date
                date_value = {}
                date_value = compute_date_value(row=row, to_write=to_write, context=context)
                to_write.update({'date_planned': date_value['date_planned'], 'error_list': date_value['error_list']})

                # Cell 6: Currency
                curr_value = {}
                curr_value = compute_currency_value(cr, uid, cell=6, browse_purchase=browse_purchase,
                                                    currency_obj=currency_obj, row=row, to_write=to_write, context=context)
                to_write.update({'functional_currency_id': curr_value['functional_currency_id'], 'warning_list': curr_value['warning_list']})

                # Cell 7: Comment
                c_value = {}
                c_value = comment_value(row=row, cell=7, to_write=to_write, context=context)
                to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
                to_write.update({
                    'to_correct_ok': [True for x in to_write['error_list']],  # the lines with to_correct_ok=True will be red
                    'show_msg_ok': [True for x in to_write['warning_list']],  # the lines with show_msg_ok=True won't change color, it is just info
                    'order_id': obj.id,
                    'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
                })
                # we check consistency on the model of on_change functions to call for updating values
                purchase_line_obj.check_line_consistency(cr, uid, ids, to_write=to_write, context=context)

                vals['order_line'].append((0, 0, to_write))

            except IndexError:
                print "The line num %s in the Excel file got element outside the defined 8 columns" % line_num

        # write order line on PO
        context['import_in_progress'] = True
        self.write(cr, uid, ids, vals, context=context)
        self._check_service(cr, uid, ids, vals, context=context)
        msg_to_return = get_log_message(to_write=to_write, obj=obj)
        if msg_to_return:
            self.log(cr, uid, obj.id, _(msg_to_return), context={'view_id': view_id})
        return True

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        """
        Check both the lines that need to be corrected and also that the supplier or the address is not 'To be defined'
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural= ''
        obj_data = self.pool.get('ir.model.data')
        
        for var in self.browse(cr, uid, ids, context=context):
            # we check the supplier and the address
            if var.partner_id.id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','supplier_tbd')[1] \
            or var.partner_address_id.id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','address_tbd')[1]:
                raise osv.except_osv(_('Warning !'), _("\n You can't have a supplier or an address 'To Be Defined', please select a consistent supplier."))
            # we check the lines that need to be fixed
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
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s: %s') % (plural, message))
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
        'show_msg_ok': fields.boolean('Info on importation of lines'),
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
        obj_data = self.pool.get('ir.model.data')
        to_write = kwargs['to_write']
        order_id = to_write.get('order_id', False)
        if order_id:
            text_error = to_write.get('text_error', '')
            price_unit_defined = to_write.get('price_unit_defined', False)
            po_obj = self.pool.get('purchase.order')
            po = po_obj.browse(cr, uid, order_id, context=context)
            # on_change functions to call for updating values
            pricelist = po.pricelist_id.id or False
            partner_id = po.partner_id.id or False
            date_order = po.date_order or False
            fiscal_position = po.fiscal_position or False
            state = po.state or False
            product = to_write.get('product_id', False)
            if product:
                qty = to_write.get('product_qty')
                price_unit = to_write.get('price_unit')
                uom = to_write.get('product_uom')
                if product and qty and not price_unit_defined:
                    try:
                        res = self.product_id_on_change(cr, uid, False, pricelist, product, qty, uom,
                                                        partner_id, date_order, fiscal_position, date_planned=False,
                                                        name=False, price_unit=price_unit, notes=False, state=state, old_price_unit=False,
                                                        nomen_manda_0=False, comment=False, context=context)
                        if not context.get('po_integration'):
                            price_unit = res.get('value', {}).get('price_unit', False)
                            text_error += 'We use the price mechanism to compute the Price Unit.'
                        uom = res.get('value', {}).get('product_uom', False)
                        warning_msg = res.get('warning', {}).get('message', '')
                        text_error += '\n %s' % warning_msg
                    except osv.except_osv as osv_error:
                        if not context.get('po_integration'):
                            osv_value = osv_error.value
                            osv_name = osv_error.name
                            text_error += '%s. %s\n' % (osv_value, osv_name)
                    to_write.update({'price_unit': price_unit, 'product_uom': uom, 'text_error': text_error})
                if uom:
                    self.check_data_for_uom(cr, uid, False, to_write=to_write, context=context)
                else:
                    if not context.get('po_integration'):
                        uom = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]
                        text_error += '\n It wasn\'t possible to update the UoM with the product\'s one because the former wasn\'t either defined.'
                        to_write.update({'product_uom': uom, 'text_error': text_error})
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
                text_error += """\n You have to select a product UOM in the same category than the UOM of the product.
The category of the UoM of the product is '%s' whereas the category of the UoM you have chosen is '%s'.
                """ % (product.uom_id.category_id.name, uom.category_id.name)
                return to_write.update({'text_error': text_error,
                                        'to_correct_ok': True})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1] and product_id:
            # we take the default uom of the product
            product_uom = product.uom_id.id
            return to_write.update({'product_uom': product_uom})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]:
            # this is inspired by the on_change in purchase>purchase.py: product_uom_change
            text_error += "\n The UoM was not defined so we set the price unit to 0.0."
            return to_write.update({'text_error': text_error,
                                    'to_correct_ok': True,
                                    'price_unit': 0.0, })

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import', 'uom_tbd')[1]
        message = ''
        if not context.get('import_in_progress') and not context.get('button'):
            if vals.get('product_uom') or vals.get('nomen_manda_0') or vals.get('nomen_manda_1') or vals.get('nomen_manda_2'):
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
                    vals['show_msg_ok'] = False
                    vals['to_correct_ok'] = False
                    vals['text_error'] = False

        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

purchase_order_line()
