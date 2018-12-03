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

from specific_rules.specific_rules import SHORT_SHELF_LIFE_MESS

from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import base64
from tools.translate import _


NO_QTY_MODELS = [
    'monthly.review.consumption',
    'stock.warehouse.orderpoint',
    'threshold.value',
    'stock.warehouse.order.cycle',
]


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

    def check_header_values(self, cr, uid, ids, context, header_index,
                            real_columns, origin=False):
        """
        Check that the columns in the header will be taken into account.
        """
        translated_headers = [_(f) for f in real_columns]
        upper_translated_headers = translated_headers
        if origin == 'FO':
            upper_translated_headers = [_(f).upper() for f in real_columns]
        for k,v in header_index.items():
            upper_k = k
            if origin == 'FO':
                upper_k = k.upper()
            if upper_k not in upper_translated_headers:
                if origin:
                    # special case from document origin
                    if origin == 'PO' and k == 'Delivery requested date' \
                            and 'Delivery Request Date' in real_columns:
                        continue  # 'Delivery requested date' tolerated (for Rfq vs 'Delivery Requested Date' of PO_COLUMNS_HEADER_FOR_IMPORT)
                vals = {'state': 'draft',
                        'message': _('The column "%s" is not taken into account. Please correct it. The list of columns accepted is: %s'
                                     ) % (k, ', '.join(translated_headers))}
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
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        vals = {
            'parent_id': parent_id,
            'parent_model': parent_model,
            'line_model': line_model,
            'search_default_not_restricted': 1 if 'search_default_not_restricted' in context else 0,
        }
        wiz_id = self.create(cr, uid, vals, context=context)
        context['wizard_id'] = wiz_id

        if parent_model in NO_QTY_MODELS:
            view_id = data_obj.get_object_reference(cr, uid, 'msf_doc_import', 'wizard_common_import_line_form_view_no_qty')[1]
        else:
            view_id = data_obj.get_object_reference(cr, uid, 'msf_doc_import', 'wizard_common_import_line_form_view')[1]


        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def _get_current_id(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        for i in ids:
            res[i] = i

        return res

    _columns = {
        'parent_id': fields.integer(string='ID of the parent document'),
        'parent_model': fields.char(size=128, string='Model of the parent document'),
        'line_model': fields.char(size=128, string='Model of the line document'),
        'product_ids': fields.many2many('product.product', 'product_add_in_line_rel',
                                        'wiz_id', 'product_id', string='Products'),
        'search_default_not_restricted': fields.integer('Search default not restricted', invisible=True),  # UFTP-15 (for context reinject in product_ids m2m for 'add multiple lines' button)
        'current_id': fields.function(_get_current_id, method=True, type='integer', string='ID'),
    }

    _defaults = {
        'search_default_not_restricted': 0,
    }

    def add_products(self, cr, uid, ids, product_ids, context=None):
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not product_ids:
            return {}

        res = {}
        is_ssl = False
        try:
            for wl in self.browse(cr, uid, ids, context=context):
                if wl.parent_model in ('tender', 'sale.order', 'purchase.order'):
                    categ = self.pool.get(wl.parent_model).read(cr, uid, wl.parent_id, ['categ'], context=context)['categ']
                    if categ:
                        is_ssl = product_ids[0][2] and \
                            product_obj.search_exist(cr, uid, [('is_ssl', '=', True), ('id', 'in', product_ids[0][2])], context=context)

                        for product_id in product_ids[0][2]:
                            c_msg = product_obj.check_consistency(cr, uid, product_id, categ, context=context)
                            if c_msg:
                                res.setdefault('warning', {})
                                res['warning'].setdefault('title', _('Warning'))
                                res['warning']['message'] = c_msg
                                if is_ssl:
                                    res['warning']['message'] = '%s\n%s' % (res['warning']['message'], _(SHORT_SHELF_LIFE_MESS))
                            if res:
                                return res
        except IndexError:
            return {}

        if is_ssl:
            return {
                'warning': {
                    'title':  _('Warning'),
                    'message': _(SHORT_SHELF_LIFE_MESS),
                }
            }
        return res


    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill the line of attached document
        '''
        context = context is None and {} or context
        ids = isinstance(ids, (int, long)) and [ids] or ids

        fields_to_read = ['parent_id',
                          'parent_model',
                          'line_model',
                          'product_ids']

        for wiz in self.read(cr, uid, ids, fields_to_read, context=context):
            parent_id = wiz['parent_id']
            line_obj = self.pool.get(wiz['line_model'])
            product_ids = wiz['product_ids']

            context['wizard_id'] = wiz['id']

            line_obj.create_multiple_lines(cr, uid, parent_id, product_ids, context=context)

        return {'type': 'ir.actions.act_window_close'}

wizard_common_import_line()


class product_product_import_line_qty(osv.osv_memory):
    _name = 'product.product.import.line.qty'

    _columns = {
        'wizard_id': fields.many2one(
            'wizard.common.import.line',
            string='Wizard',
        ),
        'product_id': fields.many2one(
            'product.product',
            string='Product',
        ),
        'qty': fields.float(
            string='Qty',
        ),
    }

product_product_import_line_qty()


class product_product(osv.osv):
    _inherit = 'product.product'

    def write(self, cr, uid, ids, vals, context=None):
        import_product_qty = 'import_product_qty'
        if len(vals) == 1 and import_product_qty in vals:
            self._write_imp_product_qty(cr, uid, ids, field_name=import_product_qty, values=vals[import_product_qty], args=None, context=context)
            return True

        return super(product_product, self).write(cr, uid, ids, vals, context=context)

    def _get_import_product_qty(self, cr, uid, ids, field_name, args, context=None):
        if context is None:
            context = {}
        res = {}
        pplq_obj = self.pool.get('product.product.import.line.qty')

        wiz_id = context.get('wizard_id', None)
        for i in ids:
            res[i] = 0.00
            if wiz_id:
                pplq_ids = pplq_obj.search(cr, uid, [
                    ('wizard_id', '=', wiz_id),
                    ('product_id', '=', i),
                ], order='id desc', context=context)
                if pplq_ids:
                    res[i] = pplq_obj.read(cr, uid, pplq_ids[0], ['qty'])['qty']

        return res

    def _write_imp_product_qty(self, cr, uid, ids, field_name, values, args, context=None):
        """
        Create a product.product.import.line.qty for each product/wizard and put the 
        quantity.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        if field_name == 'import_product_qty' and context.get('wizard_id', None):
            for prod_id in ids:
                self.pool.get('product.product.import.line.qty').create(cr, uid, {
                    'wizard_id': context.get('wizard_id'),
                    'product_id': prod_id,
                    'qty': values,
                }, context=context)

    _columns = {
        'import_product_qty': fields.function(
            _get_import_product_qty,
            fnct_inv=_write_imp_product_qty,
            method=True,
            type='float',
            string='Qty',
            store=False,
            related_uom='uom_id',
        ),
    }

    def on_change_import_product_qty(self, cr, uid, ids, import_product_qty,
                                     context=None):
        res = {}
        if not ids:
            return res
        if import_product_qty and import_product_qty < 0:
            res['value'] = {'import_product_qty': 0.}
            res['warning'] = {
                'title': _('Warning'),
                'message': _('You can not set a negative quantity'),
            }
            return res
        if import_product_qty:
            uom = self.read(cr, uid, ids, ['uom_id'], context=context)[0]['uom_id'][0]
            return self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, import_product_qty, ['import_product_qty'], context=context)
        return {}

product_product()


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj  = self.pool.get('product.product')
        po_obj = self.pool.get('purchase.order')

        context = context is None and {} or context
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'standard_price', 'import_product_qty'], context=context):
            po_data = po_obj.read(cr, uid, parent_id, ['pricelist_id', 'partner_id', 'date_order',
                                                       'fiscal_position', 'state'], context=context)

            values = {'order_id': parent_id,
                      'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0],
                      'price_unit': p_data['standard_price'],
                      'product_qty': p_data['import_product_qty'],
                      'old_price_unit': p_data['standard_price'],}

            values.update(self.product_id_on_change(cr, uid, False,
                                                    po_data['pricelist_id'][0], # Pricelist
                                                    values['product_id'], # Product
                                                    p_data['import_product_qty'], # Product Qty - Use 1.00 to compute the price according to supplier catalogue
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
            values.update({'product_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

purchase_order_line()


class purchase_order(osv.osv):
    _inherit = 'purchase.order'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        ids = isinstance(ids, (int, long)) and [ids] or ids

        order_id = self.browse(cr, uid, ids[0], context=context)
        context.update({'partner_id': order_id.partner_id.id,
                        'quantity': 0.00,
                        'rfq_ok': order_id.rfq_ok,
                        'purchase_id': order_id.id,
                        'purchase_order': True,
                        'uom': False,
                        # UFTP-15: we active 'only not forbidden' filter as default
                        'available_for_restriction': order_id.partner_type,
                        'search_default_not_restricted': 1,
                        'add_multiple_lines': True,
                        'partner_type': order_id.partner_type,
                        'pricelist_id': order_id.pricelist_id.id,
                        'pricelist': order_id.pricelist_id.id,
                        'warehouse': order_id.warehouse_id.id,
                        'categ': order_id.categ})

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

        context = context is None and {} or context
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty', 'categ_id'], context=context):
            values = {
                'tender_id': parent_id,
                'product_id': p_data['id'],
                'product_uom': p_data['uom_id'][0],
                'categ_id': p_data['categ_id'],
            }

            values.update(self.on_product_change(cr, uid, False, p_data['id'], p_data['uom_id'][0], p_data['import_product_qty'], p_data['categ_id'], context=context).get('value', {}))

            # Set the quantity to 0.00
            values.update({'qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

tender_line()


class tender(osv.osv):
    _inherit = 'tender'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        if context is None:
            context = {}
        ids = isinstance(ids, (int, long)) and [ids] or ids

        context.update({
            'product_ids_domain': [],
            # UFTP-15: we active 'only not forbidden' filter as default
            'available_for_restriction': 'tender',
            'search_default_not_restricted': 1,
            'add_multiple_lines': True,
        })

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

        context = context is None and {} or context
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'], context=context):
            order_data = order_obj.read(cr, uid, parent_id, ['pricelist_id',
                                                             'partner_id',
                                                             'date_order',
                                                             'procurement_request',
                                                             'fiscal_position'], context=context)

            values = {'order_id': parent_id,
                      'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0]}

            if order_data['procurement_request']:
                values.update(self.requested_product_id_change(cr, uid, False,
                                                               p_data['id'],
                                                               '').get('value', {}))
            else:
                values.update(self.product_id_on_change(cr, uid, False, order_data['pricelist_id'][0],
                                                        p_data['id'],
                                                        p_data['import_product_qty'],
                                                        p_data['uom_id'][0],
                                                        p_data['uom_id'][0],
                                                        '',
                                                        order_data['partner_id'][0],
                                                        context.get('lang'),
                                                        True,
                                                        order_data['date_order'],
                                                        False,
                                                        order_data['fiscal_position'] and order_data['fiscal_position'][0] or False,
                                                        False).get('value', {}),
                              context=context)

            # Set the quantity to 0.00
            values.update({'product_uom_qty': p_data['import_product_qty'], 'product_uos_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

sale_order_line()


class sale_order(osv.osv):
    _inherit = 'sale.order'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to add multiple lines
        '''
        if context is None:
            context = {}
        ids = isinstance(ids, (int, long)) and [ids] or ids

        order = self.browse(cr, uid, ids[0], context=context)
        if order.procurement_request:
            # UFTP-15: IR context available_for_restriction = 'consumption' (3.1.3.4 case (d))
            context_update = {
                'product_ids_domain': [],
                # UFTP-15: we active 'only not forbidden' filter as default
                'available_for_restriction': 'consumption',
                'search_default_not_restricted': 1,
                'add_multiple_lines': True,
            }
        else:
            # UFTP-15: FO context available_for_restriction = 'partner type'
            context_update = {
                'product_ids_domain': [],
                # UFTP-15: we active 'only not forbidden' filter as default
                'available_for_restriction': order.partner_type,
                'search_default_not_restricted': 1,
                'add_multiple_lines': True,
                # UFTP-15: we pass infos in context like for a FO line product m2o
                'partner_id': order.partner_id.id,
                'pricelist_id': order.pricelist_id.id,
                'pricelist': order.pricelist_id.id,
                'warehouse': order.warehouse_id.id,
                'categ': order.categ,
            }
        context.update(context_update)

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

        context = context is None and {} or context
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'standard_price', 'import_product_qty'], context=context):
            values = {'item_kit_id': parent_id,
                      'item_product_id': p_data['id'],
                      'item_uom_id': p_data['uom_id'][0],}

            values.update(self.on_product_change(cr, uid, False, values['item_product_id'], context=context).get('value', {}))
            # Set the quantity to 0.00
            values.update({'item_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

composition_item()


class composition_kit(osv.osv):
    _inherit = 'composition.kit'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context

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

        context = context is None and {} or context
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'standard_price', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'catalogue_id': parent_id,
                      'unit_price': p_data['standard_price'],
                      'line_uom_id': p_data['uom_id'][0],
                      'min_qty': 1.00}

            values.update(self.product_change(cr, uid, False, p_data['id'], 1.00, 1.00).get('value', {}))

            # Set the quantity to 0.00
            values.update({'min_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

supplier_catalogue_line()


class supplier_catalogue(osv.osv):
    _inherit = 'supplier.catalogue'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context

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
        get_ref = data_obj.get_object_reference

        context = context is None and {} or context
        product_ids = isinstance(product_ids, (int, long)) and [product_ids] or product_ids

        picking = pick_obj.browse(cr, uid, parent_id, context=context)

        if picking.partner_id and picking.type == 'in':
            location_id = picking.partner_id.property_stock_supplier.id
        elif picking.ext_cu and picking.type == 'in':
            location_id = picking.ext_cu.id
        elif picking.type == 'in':
            location_id = get_ref(cr, uid, 'stock', 'stock_location_suppliers')[1]
        else:
            location_id = get_ref(cr, uid, 'stock', 'stock_location_stock')[1]

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'name', 'nomen_manda_0', 'import_product_qty'], context=context):
            # Set the location dest id
            if picking.type == 'internal':
                location_dest_id = get_ref(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
            elif picking.type == 'out' and picking.subtype == 'picking':
                location_dest_id = get_ref(cr, uid, 'msf_outgoing', 'stock_location_packing')[1]
            elif picking.type == 'out' and picking.subtype == 'standard':
                location_dest_id = get_ref(cr, uid, 'stock', 'stock_location_output')[1]
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
                      'name': p_data['name'],
                      'is_ext_cu': True if picking.ext_cu else False,
                      }

            values.update(self.onchange_product_id(cr, uid, False, p_data['id'], location_id, location_dest_id, picking.address_id and picking.address_id.id or False, picking.type, False).get('value', {}))

            values.update({'product_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True, import_in_progress=True))

        return True

stock_move()


class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        ids = isinstance(ids, (int, long)) and [ids] or ids
        data_obj = self.pool.get('ir.model.data')
        get_ref = data_obj.get_object_reference

        picking = self.browse(cr, uid, ids[0], context=context)
        if picking.type in ('in', 'out'):
            context.update({'product_ids_domain': [('type', '!=', 'service'),
                                                   ('available_for_restriction', '=', 'picking')]})
        elif picking.type == 'internal':
            cd_loc = get_ref(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
            context.update({'product_ids_domain': [('type', '!=', 'service'),
                                                   ('available_for_restriction', '=', {'location_id': cd_loc})]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'stock.picking', 'stock.move', context=context)

stock_picking()


class stock_warehouse_orderpoint_line(osv.osv):
    _inherit = 'stock.warehouse.orderpoint.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids,
                              context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')
        swo_obj = self.pool.get('stock.warehouse.orderpoint')

        # get parent default vals
        parent_vals = {
            'product_min_qty': 0.,
            'product_max_qty': 0.,
            'qty_multiple': 1.0,
        }
        if parent_id:
            parent_r = swo_obj.read(cr, uid, parent_id, parent_vals.keys(),
                                    context=context)
            if parent_r:
                for f in parent_vals.keys():
                    parent_vals[f] = parent_r[f] or 0.

        # set line vals
        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'],
                                 context=context):
            values = {
                'product_id': p_data['id'],
                'product_uom_id': p_data['uom_id'][0],
                'supply_id': parent_id,
            }
            for k in parent_vals:
                values[k] = parent_vals[k]

            values.update(self.onchange_product_id(cr, uid, False,
                                                   p_data['id'], p_data['uom_id'][0],
                                                   values.get('product_min_qty', 0.),
                                                   values.get('product_max_qty', 0.),
                                                   context=context).get('value', {}))

            domain = [
                ('product_id', '=', p_data['id']),
                ('supply_id', '=', parent_id),
            ]
            if not self.search(cr, uid, domain, context=context):
                self.create(cr, uid, values,
                            context=dict(context, noraise=True))

        return True

stock_warehouse_orderpoint_line()


class stock_warehouse_orderpoint(osv.osv):
    _inherit = 'stock.warehouse.orderpoint'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        if context is None:
            context = {}
        context.update({
            'product_ids_domain': [('type','=','product')],
            'add_multiple_line': True,
        })

        return self.pool.get('wizard.common.import.line').open_wizard(cr, uid,
                                                                      ids[0], 'stock.warehouse.orderpoint',
                                                                      'stock.warehouse.orderpoint.line', context=context)

stock_warehouse_orderpoint()


class stock_warehouse_auto_supply_line(osv.osv):
    _inherit = 'stock.warehouse.automatic.supply.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'product_uom_id': p_data['uom_id'][0],
                      'supply_id': parent_id}

            values.update(self.onchange_product_id(cr, uid, False, p_data['id'], p_data['uom_id'][0], p_data['import_product_qty'], context=context).get('value', {}))
            # Set the quantity to 0.00
            values.update({'product_qty': p_data['import_product_qty']})

            if not self.search(cr, uid, [('product_id', '=', p_data['id']), ('supply_id', '=', parent_id)], context=context):
                self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

stock_warehouse_auto_supply_line()


class stock_warehouse_auto_supply(osv.osv):
    _inherit = 'stock.warehouse.automatic.supply'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        context.update({'product_ids_domain': [('type', 'not in', ['consu', 'service', 'service_recep'])]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'stock.warehouse.automatic.supply', 'stock.warehouse.automatic.supply.line', context=context)

stock_warehouse_auto_supply()


class stock_warehouse_order_cycle_line(osv.osv):
    _inherit = 'stock.warehouse.order.cycle.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'uom_id': p_data['uom_id'][0],
                      'order_cycle_id': parent_id}

            values.update(self.product_change(cr, uid, False, p_data['id'], context=context).get('value', {}))
            # Set the quantity to 0.00
            values.update({'safety_stock': p_data['import_product_qty']})

            if not self.search(cr, uid, [('product_id', '=', p_data['id']), ('order_cycle_id', '=', parent_id)], context=context):
                self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

stock_warehouse_order_cycle_line()


class stock_warehouse_order_cycle(osv.osv):
    _inherit = 'stock.warehouse.order.cycle'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        context.update({'product_ids_domain': [('type', 'not in', ['consu', 'service', 'service_recep'])]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'stock.warehouse.order.cycle', 'stock.warehouse.order.cycle.line', context=context)

stock_warehouse_order_cycle()


class threshold_value_line(osv.osv):
    _inherit = 'threshold.value.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')

        t_data = self.pool.get('threshold.value').browse(cr, uid, parent_id, context=context)

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'product_uom_id': p_data['uom_id'],
                      'threshold_value_id': parent_id}

            values.update(self.onchange_product_id(cr,
                                                   uid,
                                                   False,
                                                   p_data['id'],
                                                   t_data.compute_method,
                                                   t_data.consumption_method,
                                                   t_data.consumption_period_from,
                                                   t_data.consumption_period_to,
                                                   t_data.frequency,
                                                   t_data.safety_month,
                                                   t_data.lead_time,
                                                   t_data.supplier_lt,).get('value', {}))
            # Set the quantity to 0.00
            values.update({'fixed_product_qty': p_data['import_product_qty'], 'fixed_threshold_value': 0.00})

            if not self.search(cr, uid, [('product_id', '=', p_data['id']), ('threshold_value_id', '=', parent_id)], context=context):
                self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

threshold_value_line()


class threshold_value(osv.osv):
    _inherit = 'threshold.value'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        context.update({'product_ids_domain': [('type', 'not in', ['consu', 'service', 'service_recep'])]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'threshold.value', 'threshold.value.line', context=context)

threshold_value()


class stock_inventory_line(osv.osv):
    _inherit = 'stock.inventory.line'
    _description = "Physical Stock Inventory Line"

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')

        location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        reason_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0],
                      'location_id': location_id,
                      'reason_type_id': reason_id,
                      'inventory_id': parent_id}

            values.update(self.on_change_product_id(cr, uid, False, location_id, p_data['id'], p_data['uom_id'][0], False).get('value', {}))

            # Set the quantity to 0.00
            values.update({'product_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

stock_inventory_line()

class stock_inventory(osv.osv):
    _inherit = 'stock.inventory'
    _description = "Physical Stock Inventory"

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context

        stock_loc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        context.update({'product_ids_domain': [('type', 'not in', ['consu', 'service', 'service_recep']),
                                               ('available_for_restriction', '=', {'location_id': stock_loc})]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'stock.inventory', 'stock.inventory.line', context=context)

stock_inventory()

class initial_stock_inventory_line(osv.osv):
    _inherit = 'initial.stock.inventory.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')

        location_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        reason_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_stock_initialization')[1]

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'perishable', 'batch_management', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'product_uom': p_data['uom_id'][0],
                      'location_id': location_id,
                      'reason_type_id': reason_id,
                      'hidden_batch_management_mandatory': p_data['batch_management'],
                      'hidden_perishable_mandatory': p_data['perishable'],
                      'inventory_id': parent_id}

            values.update(self.on_change_product_id(cr, uid, False, location_id, p_data['id'], p_data['uom_id'][0], False).get('value', {}))

            # Set the quantity to 0.00
            values.update({'product_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

initial_stock_inventory_line()

class initial_stock_inventory(osv.osv):
    _inherit = 'initial.stock.inventory'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context

        stock_loc = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
        context.update({'product_ids_domain': [('type', 'not in', ['consu', 'service', 'service_recep']),
                                               ('available_for_restriction', '=', {'location_id': stock_loc})]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'initial.stock.inventory', 'initial.stock.inventory.line', context=context)

initial_stock_inventory()


class real_average_consumption_line(osv.osv):
    _inherit = 'real.average.consumption.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        p_obj = self.pool.get('product.product')

        c_data = self.pool.get('real.average.consumption').read(cr, uid, parent_id, ['cons_location_id'], context=context)

        for p_data in p_obj.read(cr, uid, product_ids, ['uom_id', 'import_product_qty'], context=context):
            values = {'product_id': p_data['id'],
                      'uom_id': p_data['uom_id'],
                      'rac_id': parent_id}

            values.update(self.product_onchange(cr, uid, False, p_data['id'], c_data['cons_location_id'][0], p_data['uom_id'][0], False).get('value', {}))

            # Set the quantity to 0.00
            values.update({'consumed_qty': p_data['import_product_qty']})

            self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

real_average_consumption_line()

class real_average_consumption(osv.osv):
    _inherit = 'real.average.consumption'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context
        context.update({'product_ids_domain': [('available_for_restriction', '=', 'consumption')]})

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'real.average.consumption', 'real.average.consumption.line', context=context)

real_average_consumption()


class monthly_review_consumption_line(osv.osv):
    _inherit = 'monthly.review.consumption.line'

    def create_multiple_lines(self, cr, uid, parent_id, product_ids, context=None):
        '''
        Create lines according to product in list
        '''
        c_data = self.pool.get('monthly.review.consumption').read(cr, uid, parent_id, ['period_from', 'period_to'], context=context)

        for product_id in product_ids:
            values = {'name': product_id,
                      'mrc_id': parent_id,}

            values.update(self.product_onchange(cr, uid, False, product_id, parent_id, c_data['period_from'], c_data['period_to']).get('value', {}))

            # Set the quantity to 0.00
            values.update({'fmc': 0.00, 'fmc2': 0.00})

            if not self.search(cr, uid, [('name', '=', product_id), ('mrc_id', '=', parent_id)], context=context):
                self.create(cr, uid, values, context=dict(context, noraise=True))

        return True

monthly_review_consumption_line()

class monthly_review_consumption(osv.osv):
    _inherit = 'monthly.review.consumption'

    def add_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Open the wizard to open multiple lines
        '''
        context = context is None and {} or context

        return self.pool.get('wizard.common.import.line').\
            open_wizard(cr, uid, ids[0], 'monthly.review.consumption', 'monthly.review.consumption.line', context=context)

monthly_review_consumption()
