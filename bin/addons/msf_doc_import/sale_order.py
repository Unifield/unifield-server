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
from tools.translate import _
import base64
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
        if isinstance(ids, int):
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

    def wizard_import_ir_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_ir_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.ir.line').create(cr, uid, {'file': file,
                                                                            'filename_template': 'template.xls',
                                                                            'filename': 'Lines_Not_Imported.xls',
                                                                            'message': """%s %s"""  % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in columns_for_ir_line_import]), ),
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
        if isinstance(ids, int):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_fo_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.fo.line').create(cr, uid, {'file': file,
                                                                            'filename_template': 'template.xls',
                                                                            'filename': 'Lines_Not_Imported.xls',
                                                                            'message': """%s %s"""  % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in columns_for_fo_line_import]), ),
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
        if isinstance(ids, int):
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

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the Sale order line has an inactive product
        '''
        if not ids:
            return True
        cr.execute('''select count(sol.id) from
            sale_order_line sol, product_product p
            where
                sol.product_id = p.id and
                sol.state not in ('draft', 'cancel', 'cancel_r', 'done') and
                p.active = 'f' and
                sol.id in %s
        ''', (tuple(ids),))
        inactive_lines = cr.fetchone()[0]
        if inactive_lines:
            plural = inactive_lines == 1 and _('A product has') or _('Some products have')
            l_plural = inactive_lines == 1 and _('line') or _('lines')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this line you have to remove/correct the line containing the inactive product (see red %s of the document)') % (plural, l_plural))
        return True

    _constraints = [
        (_check_active_product, "You cannot validate this sale order line because it has an inactive product", ['id', 'state'])
    ]

    def check_data_for_uom(self, cr, uid, ids, *args, **kwargs):
        """
        We check consistency between product and uom
        """
        context = kwargs['context']
        if context is None:
            context = {}
        if isinstance(ids, int):
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
        elif (not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]) and product_id:
            # we take the default uom of the product
            product = self.pool.get('product.product').browse(cr, uid, product_id)
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

    def onchange_ir_qty(self, cr, uid, ids, product_id, uom_id, product_qty=0.00, price_unit=0.00, context=None):
        if context is None:
            context = {}

        sol = {}
        if ids:
            sol = self.read(cr, uid, ids[0], ['product_uom_qty', 'product_uos_qty'], context=context)

        res = self.onchange_uom(cr, uid, ids, product_id, uom_id, product_qty, context=context)

        p_unit = res.get('value') and res['value'].get('price_unit', price_unit) or price_unit
        self.check_digits(cr, uid, res, sol, product_qty, p_unit, context=context)

        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, int):
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

        if vals.get('state') in ('done', 'cancel'):
            context['bypass_product_constraints'] = True
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
