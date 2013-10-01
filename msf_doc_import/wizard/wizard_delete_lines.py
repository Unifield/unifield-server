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
from tools.translate import _


# DOCUMENT DATA dict : {'document.model': ('document.line.model',
#                                          'field linked to document.model on document.line.model',
#                                          'field linked to document.line.model on document.model)}
DOCUMENT_DATA = {'product.list': ('product.list.line', 'list_id', 'product_ids'),
                 'composition.kit': ('composition.item', 'item_kit_id', 'composition_item_ids'),
                 'purchase.order': ('purchase.order.line', 'order_id', 'order_line'),
                 'tender': ('tender.line', 'tender_id', 'tender_line_ids'),
                 'sale.order': ('sale.order.line', 'order_id', 'order_line'),
                 'supplier.catalogue': ('supplier.catalogue.line', 'catalogue_id', 'line_ids'),
                 'stock.picking': ('stock.mvoe', 'picking_id', 'move_lines'),
                 'stock.warehouse.automatic.supply': ('stock.warehouse.automatic.supply.line', 'supply_id', 'line_ids'),
                 'stock.warehouse.order.cycle': ('stock.warehouse.order.cycle.line', 'order_cycle_id', 'product_id'),
                 'threshold.value': ('threshold.value.line', 'threshold_value_id', 'line_ids'),
                 'stock.inventory': ('stock.inventory.line', 'inventory_id', 'inventory_line_id'),
                 'initial.stock.inventory': ('initial.stock.inventory.line', 'inventory_id', 'inventory_line_id'),
                 'real.average.consumption': ('real.average.consumption.line', 'rac_id', 'line_ids'),
                 'monthly.review.consumption': ('monthly.review.consumption.line', 'mrc_id', 'line_ids'),}


class document_remove_line(osv.osv):
    _name = 'document.remove.line'

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Call the wizard to remove lines
        '''
        context = context or {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if not obj[DOCUMENT_DATA.get(self._name)[2]]:
                raise osv.except_osv(_('Error'), _('No line to remove'))

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.delete.lines',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': dict(context, active_id=ids[0], active_model=self._name)}

document_remove_line()


class product_list(osv.osv):
    _name = 'product.list'
    _inherit = ['product.list', 'document.remove.line']

product_list()


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'document.remove.line']

purchase_order()


class wizard_delete_lines(osv.osv_memory):
    """
    Wizard to remove lines of document
    """
    _name = 'wizard.delete.lines'

    def _get_doc_name(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the name of the initial document
        '''
        res = {}

        for wiz_data in self.read(cr, uid, ids, ['initial_doc_id', 'initial_doc_type'], context=context):
            res[wiz_data['id']] = self.pool.get(wiz_data['initial_doc_type']).name_get(cr, uid, wiz_data['initial_doc_id'], context=context)[0][1]

        return res

    _columns = {
        'initial_doc_id': fields.integer(string='ID of the initial document', required=True),
        'initial_doc_type': fields.char(size=128, string='Model of the initial document', required=True),
        'to_remove_type': fields.char(size=128, string='Model of the lines', required=True),
        'linked_field_name': fields.char(size=128, string='Field name of the link between lines and original doc', required=True),
        'initial_doc_name': fields.function(_get_doc_name, method=True, string='Initial doc. name', type='char', readonly=True),
        'line_ids': fields.text(string='Line ids'),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Check if the wizard has been overrided
        '''
        context = context or {}

#        if not 'line_ids' in self._columns:
#            raise osv.except_osv(_('Error'), _('You has to override the object wizard.delete.lines before using it.'))

        res = super(wizard_delete_lines, self).default_get(cr, uid, fields, context=context)

        if 'active_id' in context:
            res['initial_doc_id'] = context.get('active_id')

        if 'active_model' in context and context.get('active_model') in DOCUMENT_DATA:
            res['initial_doc_type'] = context.get('active_model')
            res['to_remove_type'] = DOCUMENT_DATA.get(context.get('active_model'))[0]
            res['linked_field_name'] = DOCUMENT_DATA.get(context.get('active_model'))[1]

        return res

    def remove_selected_lines(self, cr, uid, ids, context=None):
        '''
        Remove only the selected lines
        '''
        context = context or {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            line_obj = self.pool.get(wiz.to_remove_type)
            line_ids = []
            for line in wiz.line_ids:
                for l in line[2]:
                    line_ids.append(l)

            line_obj.unlink(cr, uid, line_ids, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def remove_all_lines(self, cr, uid, ids, context=None):
        '''
        Remove all lines of the initial document
        '''
        context = context or {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            line_obj = self.pool.get(wiz.to_remove_type)
            line_ids = line_obj.search(cr, uid, [(wiz.linked_field_name, '=', wiz.initial_doc_id)], context=context)
            line_obj.unlink(cr, uid, line_ids, context=context)

        return {'type': 'ir.actions.act_window_close'}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        '''
        if self._name != 'wizard.delete.lines':
            res = self.pool.get('wizard.delete.lines').fields_view_get(cr, uid, view_id, view_type, context=dict(context, object_model=self._name), toolbar=toolbar, submenu=submenu)
        else:
            res = super(wizard_delete_lines, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

        return res

    def fields_get(self, cr, uid, fields=None, context=None):
        '''
        '''
        context = context or {}

        res = super(wizard_delete_lines, self).fields_get(cr, uid, fields, context=context)

        if context.get('active_model') and DOCUMENT_DATA.get(context.get('active_model')):
            ddata = DOCUMENT_DATA.get(context.get('active_model'))
            line_obj = ddata[0]
            res.update(line_ids={'related_columns': ['wiz_id', 'line_id'], 
                                 'relation': line_obj, 
                                 'string': 'Lines to remove', 
                                 'context': {}, 
                                 'third_table': '%sto_remove' % line_obj.replace('.', '_'), 
                                 'selectable': True, 
                                 'type': 'many2many', 
                                 'domain': "[('%s', '=', initial_doc_id)]" % ddata[1]})

        return res
    
wizard_delete_lines()

'''
class wizard_delete_product_list_line(osv.osv_memory):
    _name = 'wizard.delete.product.list.line'
    _inherit = 'wizard.delete.lines'

    _columns = {
        'line_ids': fields.many2many('product.list.line', 'product_list_line_to_remove', 'wiz_id', 'line_id',
                                     string='Lines to remove', domain="[('list_id', '=', initial_doc_id)]"),
    }

    _defaults = {
        'initial_doc_type': lambda *a: 'product.list',
        'to_remove_type': lambda *a: 'product.list.line',
        'linked_field_name': lambda *a: 'list_id',
    }

wizard_delete_product_list_line()


class wizard_delete_kit_line(osv.osv_memory):
    _name = 'wizard.delete.kit.line'
    _inherit = 'wizard.delete.lines'

    _columns = {
        'line_ids': fields.many2many('composition.item', 'composition_item_to_remove', 'wiz_id', 'item_id',
                                     string='Lines to remove', domain="[('item_kit_id', '=', initial_doc_id)]"),
    }

    _defaults = {
        'initial_doc_type': lambda *a: 'composition.kit',
        'to_remove_type': lambda *a: 'composition.item',
        'linked_field_name': lambda *a: 'item_kit_id',
    }

wizard_delete_kit_line()

class wizard_delete_purchase_order_line(osv.osv_memory):
    _name = 'wizard.delete.purchase.order.line'
    _inherit = 'wizard.delete.lines'

    _columns = {
        'line_ids': fields.many2many('purchase.order.line', 'purchase_order_line_to_remove', 'wiz_id', 'line_id',
                                     string='Lines to remove', domain="[('order_id', '=', initial_doc_id)]"),
    }

    _defaults = {
        'initial_doc_type': lambda *a: 'purchase.order',
        'to_remove_type': lambda *a: 'purchase.order.line',
        'linked_field_name': lambda *a: 'order_id',
    }

wizard_delete_purchase_order_line()
'''
