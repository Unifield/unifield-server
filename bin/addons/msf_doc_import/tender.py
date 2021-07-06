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
from msf_doc_import import GENERIC_MESSAGE
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import TENDER_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_tender_line_import
from msf_doc_import.wizard import TENDER_COLUMNS_FOR_IMPORT as columns_for_tender_line_import


class tender(osv.osv):
    _inherit = 'tender'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, int):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.tender_line_ids  if item.to_correct_ok]):
                res[obj.id] = True
        return res

    _columns = {
        'hide_column_error_ok': fields.function(get_bool_values, method=True, type="boolean", string="Show column errors", store=False),
    }


    def wizard_import_tender_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        context.update({'active_id': ids[0]})
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_tender_line_import]
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.tender.line').create(cr, uid, {'file': file,
                                                                                'filename_template': 'template.xls',
                                                                                'message': """%s %s"""  % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in columns_for_tender_line_import]), ),
                                                                                'filename': 'Lines_Not_Imported.xls',
                                                                                'tender_id': ids[0],
                                                                                'state': 'draft',}, context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.tender.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
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

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.to_correct_ok:
                res[line.id].update({'inactive_error': line.text_error})
            if line.tender_id and line.tender_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {'inactive_product': True,
                                'inactive_error': _('The product in line is inactive !')}

        return res

    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'text_error': fields.text('Errors'),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Error', store=False, multi='inactive'),
    }

    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if a tender line has an inactive products
        '''
        inactive_lines = self.search(cr, uid, [('product_id.active', '=', False), ('id', 'in', ids), ('state', '!=', 'done'),
                                               ('line_state', 'not in', ['cancel', 'cancel_r', 'done'])], context=context)

        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            raise osv.except_osv(_('Error'),
                                 _('%s been inactivated. If you want to generate RfQ from this document you have to remove/correct the line containing those inactive products (see red %s of the document)') % (plural, l_plural))
        return True

    _constraints = [
        (_check_active_product, "You cannot validate this tender because it contains a line with an inactive product", ['id', 'state'])
    ]

    def check_data_for_uom(self, cr, uid, ids, *args, **kwargs):
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
            product_obj = self.pool.get('product.product')
            uom_obj = self.pool.get('product.uom')
            product = product_obj.browse(cr, uid, product_id, context=context)
            uom = uom_obj.browse(cr, uid, uom_id, context=context)
            if product.uom_id.category_id.id != uom.category_id.id:
                # this is inspired by onchange_uom in specific_rules>specific_rules.py
                text_error += _("""The product UOM must be in the same category than the UOM of the product.
The category of the UoM of the product is '%s' whereas the category of the UoM you have chosen is '%s'.
                """) % (product.uom_id.category_id.name, uom.category_id.name)
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

    def onchange_uom(self, cr, uid, ids, product_id, product_uom, product_qty=0.00, context=None):
        '''
        Check if the UoM is convertible to product standard UoM
        '''
        if product_uom and product_id:
            if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, product_uom, context):
                return {'warning': {'title': _('Wrong Product UOM !'),
                                    'message': _("You have to select a product UOM in the same category than the purchase UOM of the product")}}
        return self.onchange_uom_qty(cr, uid, ids, product_uom, product_qty)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        if not context.get('import_in_progress') and not context.get('button'):
            obj_data = self.pool.get('ir.model.data')
            tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
            tbd_product = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
            message = ''
            if vals.get('product_uom'):
                if vals.get('product_uom') == tbd_uom:
                    message += _('You have to define a valid UOM, i.e. not "To be define".')
            if vals.get('product_id'):
                if vals.get('product_id') == tbd_product:
                    message += _('You have to define a valid product, i.e. not "To be define".')
            if vals.get('product_uom') and vals.get('product_id'):
                product_id = vals.get('product_id')
                product_uom = vals.get('product_uom')
                res = self.onchange_uom(cr, uid, ids, product_id, product_uom, vals.get('product_qty', 0.00), context)
                if res and res['warning']:
                    message += res['warning']['message']
            if message:
                raise osv.except_osv(_('Warning !'), _(message))
            else:
                vals['to_correct_ok'] = False
                vals['text_error'] = False
        return super(tender_line, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        message = ''
        if not context.get('import_in_progress'):
            if vals.get('product_uom') and vals.get('product_id'):
                product_id = vals.get('product_id')
                product_uom = vals.get('product_uom')
                res = self.onchange_uom(cr, uid, False, product_id, product_uom, context=context)
                if res and res['warning']:
                    message += res['warning']['message']
            if message:
                raise osv.except_osv(_('Warning !'), _(message))
        return super(tender_line, self).create(cr, uid, vals, context=context)

tender_line()
