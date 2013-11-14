# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import base64
from tools.translate import _


class wiz_common_import(osv.osv_memory):
    '''
    Special methods for the import wizards
    '''
    _name = 'wiz.common.import'

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        lines_not_imported = []
        header_index = kwargs.get('header_index')
        data = header_index.items()
        columns_header = []
        for k,v in sorted(data, key=lambda tup: tup[1]):
            columns_header.append((k, type(k)))
        for line in kwargs.get('line_with_error'):
            if len(line) < len(columns_header):
                lines_not_imported.append(line + ['' for x in range(len(columns_header)-len(line))])
            else:
                lines_not_imported.append(line)
        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml(default_filters=['decode.utf8']))}
        return vals

    def get_line_values(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        list_of_values = []
        for cell_nb in range(len(row)):
            cell_data = self.get_cell_data(cr, uid, ids, row, cell_nb, error_list, line_num, context)
            list_of_values.append(cell_data)
        return list_of_values

    def get_cell_data(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        cell_data = False
        try:
            line_content = row.cells
        except ValueError:
            line_content = row.cells
        if line_content and len(line_content)-1>=cell_nb and row.cells[cell_nb] and row.cells[cell_nb].data:
            cell_data = row.cells[cell_nb].data
        return cell_data

    def get_header_index(self, cr, uid, ids, row, error_list, line_num, context):
        """
        Return dict with {'header_name0': header_index0, 'header_name1': header_index1...}
        """
        header_dict = {}
        for cell_nb in range(len(row.cells)):
            header_dict.update({self.get_cell_data(cr, uid, ids, row, cell_nb, error_list, line_num, context): cell_nb})
        return header_dict

    def check_header_values(self, cr, uid, ids, context, header_index, real_columns):
        """
        Check that the columns in the header will be taken into account.
        """
        translated_headers = [_(f) for f in real_columns]
        for k,v in header_index.items():
            if k not in translated_headers:
                vals = {'state': 'draft',
                        'message': _('The column "%s" is not taken into account. Please remove it. The list of columns accepted is: %s'
                                     ) % (k, ','.join(translated_headers))}
                return False, vals
        return True, True

    def get_file_values(self, cr, uid, ids, rows, header_index, error_list, line_num, context=None):
        """
        Catch the file values on the form [{values of the 1st line}, {values of the 2nd line}...]
        """
        file_values = []
        for row in rows:
            line_values = {}
            for cell in enumerate(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context)):
                line_values.update({cell[0]: cell[1]})
            file_values.append(line_values)
        return file_values

wiz_common_import()


class wizard_common_import_line(osv.osv_memory):
    _name = 'wizard.common.import.line'

    def open_wizard(self, cr, uid, parent_id, parent_model, line_model, context=None):
        '''
        Open the wizard
        '''
        context = context or {}

        wiz_id = self.create(cr, uid, {'parent_id': parent_id,
                                       'parent_model': parent_model,
                                       'line_model': line_model}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    _columns = {
        'parent_id': fields.integer(string='ID of the parent document'),
        'parent_model': fields.char(size=128, string='Model of the parent document'),
        'line_model': fields.char(size=128, string='Model of the line document'),
        'product_ids': fields.many2many('product.product', 'product_add_in_line_rel',
                                        'wiz_id', 'product_id', string='Products'),
    }

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill the line of attached document
        '''
        context = context or {}
        ids = isinstance(ids, (int, long)) and [ids] or ids

        fields_to_read = ['parent_id', 
                          'parent_model',
                          'line_model',
                          'product_ids']

        for wiz in self.read(cr, uid, ids, fields_to_read, context=context):
            parent_id = wiz['parent_id']
            parent_obj = self.pool.get(wiz['parent_model'])
            line_obj = self.pool.get(wiz['line_model'])
            product_ids = wiz['product_ids']

            line_obj.create_multiple_lines(cr, uid, parent_id, product_ids, context=context)
                                        
        return {'type': 'ir.actions.act_window_close'}

wizard_common_import_line()


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj  = self.pool.get('product.product')
        po_obj = self.pool.get('purchase.order')

        context = context or {}
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'standard_price'], context=context):
            po_data = po_obj.read(cr, uid, parent_id, ['pricelist_id', 'partner_id', 'date_order',
                                                       'fiscal_position', 'state'], context=context)

            values = {'order_id': parent_id,
                      'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0],
                      'price_unit': p_data['standard_price'],
                      'old_price_unit': p_data['standard_price'],}
            
            values.update(self.product_id_on_change(cr, uid, False,
                                                    po_data['pricelist_id'][0], # Pricelist
                                                    values['product_id'], # Product
                                                    1.00, # Product Qty - Use 1.00 to compute the price according to supplier catalogue
                                                    values['product_uom'], # UoM
                                                    po_data['partner_id'][0], # Supplier
                                                    po_data['date_order'], # Date order
                                                    po_data['fiscal_position'], # Fiscal position
                                                    po_data['date_order'], # Date planned
                                                    '', # Name
                                                    values['price_unit'], # Price unit
                                                    '', # Notes
                                                    po_data['state'], # State
                                                    values['old_price_unit'], # Old price unit
                                                    False, # Nomen_manda_0
                                                    '', # Comment
                                                    context=context).get('value', {}))
            # Set the quantity to 0.00
            values.update({'product_qty': 0.00})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

purchase_order_line()


class purchase_order(osv.osv):
    _inherit = 'purchase.order'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context or {}

        return self.pool.get('wizard.common.import.line').\
                open_wizard(cr, uid, ids[0], 'purchase.order', 'purchase.order.line', context=context)


purchase_order()


class tender_line(osv.osv):
    _inherit = 'tender.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')
        tender_obj = self.pool.get('tender')

        context = context or {}
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id'], context=context):
            values = {'tender_id': parent_id,
                      'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0]}

            values.update(self.on_product_change(cr, uid, False, p_data['id'], p_data['uom_id'][0], 1.00, context=context).get('value', {}))

            # Set the quantity to 0.00
            values.update({'qty': 0.00})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

tender_line()


class tender(osv.osv):
    _inherit = 'tender'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context or {}

        return self.pool.get('wizard.common.import.line').\
                open_wizard(cr, uid, ids[0], 'tender', 'tender.line', context=context)

tender()


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')
        order_obj = self.pool.get('sale.order')

        context = context or {}
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id'], context=context):
            order_data = order_obj.read(cr, uid, parent_id, ['pricelist_id', 
                                                             'partner_id', 
                                                             'date_order',
                                                             'fiscal_position'], context=context)

            values = {'order_id': parent_id,
                      'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0]}

            values.update(self.product_id_change(cr, uid, False, order_data['pricelist_id'][0],
                                                                 p_data['id'],
                                                                 1.00,
                                                                 p_data['uom_id'][0],
                                                                 p_data['uom_id'][0],
                                                                 '',
                                                                 order_data['partner_id'][0],
                                                                 context.get('lang'),
                                                                 True,
                                                                 order_data['date_order'],
                                                                 False,
                                                                 order_data['fiscal_position'] and order_data['fiscal_position'][0] or False,
                                                                 False).get('value', {}))

            # Set the quantity to 0.00
            values.update({'product_uom_qty': 0.00, 'product_uos_qty': 0.00})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

sale_order_line()


class sale_order(osv.osv):
    _inherit = 'sale.order'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to add multiple lines
        '''
        context = context or {}

        return self.pool.get('wizard.common.import.line').\
                open_wizard(cr, uid, ids[0], 'sale.order', 'sale.order.line', context=context)

sale_order()


class composition_item(osv.osv):
    _inherit = 'composition.item'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj  = self.pool.get('product.product')
        kit_obj = self.pool.get('composition.kit')

        context = context or {}
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'standard_price'], context=context):
            values = {'item_kit_id': parent_id,
                      'item_product_id': p_data['id'],
                      'item_uom_id': p_data['uom_id'][0],}
            
            values.update(self.on_product_change(cr, uid, False, values['item_product_id'], context=context).get('value', {}))
            # Set the quantity to 0.00
            values.update({'product_qty': 0.00})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

composition_item()


class composition_kit(osv.osv):
    _inherit = 'composition.kit'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context or {}

        return self.pool.get('wizard.common.import.line').\
                open_wizard(cr, uid, ids[0], 'composition.kit', 'composition.item', context=context)

composition_kit()


class supplier_catalogue_line(osv.osv):
    _inherit = 'supplier.catalogue.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')
        cat_obj = self.pool.get('supplier.catalogue')

        context = context or {}
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'standard_price'], context=context):
            values = {'product_id': p_data['id'],
                      'catalogue_id': parent_id,
                      'unit_price': p_data['standard_price'],
                      'line_uom_id': p_data['uom_id'][0],
                      'min_qty': 1.00}

            values.update(self.product_change(cr, uid, False, p_data['id'], 1.00, 1.00).get('value', {}))

            # Set the quantity to 0.00
            values.update({'min_qty': 0.00})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

supplier_catalogue_line()


class supplier_catalogue(osv.osv):
    _inherit = 'supplier.catalogue'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context or {}

        return self.pool.get('wizard.common.import.line').\
                open_wizard(cr, uid, ids[0], 'supplier.catalogue', 'supplier.catalogue.line', context=context)

supplier_catalogue()


class stock_move(osv.osv):
    _inherit = 'stock.move'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')
        pick_obj = self.pool.get('stock.picking')
        data_obj = self.pool.get('ir.model.data')

        context = context or {}
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        picking = pick_obj.browse(cr, uid, parent_id, context=context)

        nomen_manda_log = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'nomen_log')[1]
        nomen_manda_med = data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'nomen_med')[1]

        if picking.partner_id:
            location_id = picking.partner_id.property_stock_supplier.id
        elif picking.type == 'in':
            location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')[1]
        else:
            location_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'name', 'nomen_manda_0'], context=context):
            # Set the location dest id
            if picking.type == 'internal':
                location_dest_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
            else:
                location_dest_id = False

            values = {'picking_id': parent_id,
                      'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0],
                      'date': picking.date,
                      'date_expected': picking.min_date,
                      'reason_type_id': picking.reason_type_id.id,
                      'location_id': location_id,
                      'location_dest_id': location_dest_id,
                      'name': p_data['name'],}

            values.update(self.onchange_product_id(cr, uid, False, p_data['id'], location_id, location_dest_id, picking.address_id and picking.address_id.id or False, picking.type, False).get('value', {}))

            values.update({'product_qty': 0.00})

            print values
            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

stock_move()


class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context or {}

        return self.pool.get('wizard.common.import.line').\
                open_wizard(cr, uid, ids[0], 'stock.picking', 'stock.move', context=context)

stock_picking()

