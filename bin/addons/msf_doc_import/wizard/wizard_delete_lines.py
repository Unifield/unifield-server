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

from lxml import etree


# DOCUMENT DATA dict : {'document.model': ('document.line.model',
#                                          'field linked to document.model on document.line.model',
#                                          'field linked to document.line.model on document.model',
#                                          'field with the quantity in document.line.model',
#                                          'domain to apply on document.line.model')}
"""
This dictionnary is used by the document.remove.line and wizard.delete.lines
objects to get the different relation between a parent document and its lines.

The dictionnary keys are the parent document model and the values of the dict
are a tuple with information in this order :
    * model of the line for the parent document
    * field of the line that link the line to its parent
    * field of the parent that contains the lines
    * field with the quantity for the line
    * domain to apply on lines (e.g. : only draft stock moves on picking)
"""
DOCUMENT_DATA = {
    'product.list': ('product.list.line', 'list_id', 'product_ids', '', ''),
    'return.claim': ('claim.product.line', 'claim_id_claim_product_line', 'product_line_ids_return_claim', 'qty_claim_product_line', ''),
    'composition.kit': ('composition.item', 'item_kit_id', 'composition_item_ids', 'item_qty', ''),
    'purchase.order': ('purchase.order.line', 'order_id', 'order_line', 'product_qty', ''),
    'tender': ('tender.line', 'tender_id', 'tender_line_ids', 'qty', ''),
    'sale.order': ('sale.order.line', 'order_id', 'order_line', 'product_uom_qty', ''),
    'supplier.catalogue': ('supplier.catalogue.line', 'catalogue_id', 'line_ids', 'min_qty', ''),
    'stock.picking': ('stock.move', 'picking_id', 'move_lines', 'product_qty', '(\'state\', \'=\', \'draft\')'),
    'stock.warehouse.orderpoint': ('stock.warehouse.orderpoint.line', 'supply_id', 'line_ids', '', ''),
    'stock.warehouse.automatic.supply': ('stock.warehouse.automatic.supply.line', 'supply_id', 'line_ids', 'product_qty', ''),
    'stock.warehouse.order.cycle': ('stock.warehouse.order.cycle.line', 'order_cycle_id', 'product_ids', 'safety_stock', ''),
    'threshold.value': ('threshold.value.line', 'threshold_value_id', 'line_ids', '', ''),
    'stock.inventory': ('stock.inventory.line', 'inventory_id', 'inventory_line_id', 'product_qty', ''),
    'initial.stock.inventory': ('initial.stock.inventory.line', 'inventory_id', 'inventory_line_id', 'product_qty', ''),
    'real.average.consumption': ('real.average.consumption.line', 'rac_id', 'line_ids', 'consumed_qty', ''),
    'monthly.review.consumption': ('monthly.review.consumption.line', 'mrc_id', 'line_ids', 'fmc', ''),
}


def brl(self, cr, uid, ids, context=None):
    '''
    Call the wizard to remove lines
    '''
    context = context is None and {} or context

    if isinstance(ids, (int, long)):
        ids = [ids]

    # If there is no line to remove.
    for obj in self.browse(cr, uid, ids, context=context):
        if not obj[DOCUMENT_DATA.get(self._name)[2]]:
            raise osv.except_osv(_('Error'), _('No line to remove'))

    context.update({
        'active_id': ids[0],
        'from_delete_wizard': True,
        'active_model': self._name,
    })

    # Return the wizard to display lines to remove
    return {'type': 'ir.actions.act_window',
            'res_model': 'wizard.delete.lines',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context}

"""
All the following documents will call the same button_remove_lines method
to remove some or all lines on documents.

Documents which inherit from document.remove.line:
    * Product List
    * Theoretical Kit Composition
    * Purchase Order / Request for Quotation
    * Tender
    * Field Order / Internal request
    * Supplier catalogue
    * Stock Picking (IN / INT / OUT / PICK)
    * Order Cycle Replenishment Rule
    * Minimun Stock Rule Line
    * Automatic Supply Replenishment Rule
    * Threshold value Replenishment Rule
    * Physical Inventory
    * Initial stock inventory
    * Real consumption report
    * Monthly consumption report
"""


class product_list(osv.osv):
    _name = 'product.list'
    _inherit = 'product.list'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class return_claim(osv.osv):
    _name = 'return.claim'
    _inherit = 'return.claim'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def button_remove_lines(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            if order.rfq_ok and order.tender_id:
                raise osv.except_osv(
                    _('Warning'),
                    _('You cannot remove lines on a RfQ created by a tender. '
                      'Leave the lines with Unit price = 0.00 if you dont\'t have answer for them.'),
                )

        return brl(self, cr, uid, ids, context=context)


class composition_kit(osv.osv):
    _name = 'composition.kit'
    _inherit = 'composition.kit'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class tender(osv.osv):
    _name = 'tender'
    _inherit = 'tender'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class supplier_catalogue(osv.osv):
    _name = 'supplier.catalogue'
    _inherit = 'supplier.catalogue'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_warehouse_orderpoint(osv.osv):
    _name = 'stock.warehouse.orderpoint'
    _inherit = 'stock.warehouse.orderpoint'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_warehouse_automatic_supply(osv.osv):
    _name = 'stock.warehouse.automatic.supply'
    _inherit = 'stock.warehouse.automatic.supply'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_warehouse_order_cycle(osv.osv):
    _name = 'stock.warehouse.order.cycle'
    _inherit = 'stock.warehouse.order.cycle'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class threshold_value(osv.osv):
    _name = 'threshold.value'
    _inherit = 'threshold.value'

    def button_remove_lines(self, cr, uid, ids, context=None):
        ids = isinstance(ids, (int, long)) and [ids] or ids
        context = context is None and {} or context

        context.update({'compute_method': self.read(cr, uid, ids[0], ['compute_method'], context=context)['compute_method']})

        return brl(self, cr, uid, ids, context=context)


class stock_inventory(osv.osv):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class initial_stock_inventory(osv.osv):
    _name = 'initial.stock.inventory'
    _inherit = 'initial.stock.inventory'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _inherit = 'real.average.consumption'

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class monthly_review_consumption(osv.osv):
    _name = 'monthly.review.consumption'
    _inherit = 'monthly.review.consumption'
#    _inherit = ['monthly.review.consumption', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


## Object initializations ##

product_list()
return_claim()
purchase_order()
composition_kit()
tender()
sale_order()
supplier_catalogue()
stock_picking()
stock_warehouse_orderpoint()
stock_warehouse_automatic_supply()
stock_warehouse_order_cycle()
threshold_value()
stock_inventory()
initial_stock_inventory()
real_average_consumption()
monthly_review_consumption()

#### END OF INHERITANCE OF DOCUMENTS ####

"""
All the following documents will call the same fields_view_get to
display the good tree/search view if a tree/search view is defined
for the document wizard deletion.

Documents:
    * Product List lines
    * Claim product lines
    * Theoretical Kit Items
    * Purchase Order / Request for Quotation lines
    * Tender lines
    * Field Order / Internal request lines
    * Supplier catalogue lines
    * Stock Moves (IN / INT / OUT / PICK)
    * Order Cycle Replenishment Rule lines
    * Minimun Stock Rule Line
    * Automatic Supply Replenishment Rule lines
    * Threshold value Replenishment Rule lines
    * Physical Inventory lines
    * Initial stock inventory lines
    * Real consumption report lines
    * Monthly consumption report lines

"""


def delete_fields_view_get(self, cr, uid, view_id, view_type, context=None):
    '''
    Check if a view exist for the object (self) and the view type (view_type)
    '''
    if context is None:
        context = {}

    if view_id:
        return view_id

    # If we don't coming from delete lines wizard
    if not context.get('from_delete_wizard') or view_type not in ('tree', 'search'):
        return None

    data_obj = self.pool.get('ir.model.data')
    view_name = '%s_%s_delete_view' % (self._name.replace('.', '_'), view_type)
    try:
        res = None
        view = data_obj.get_object_reference(cr, uid, 'msf_doc_import', view_name)
        if view:
            res = view[1]
    except ValueError:
        res = None

    return res


def noteditable_fields_view_get(res, view_type, context=None):
    '''
    Make the list of lines not editable
    '''
    if context is None:
        context = {}

    if context.get('from_delete_wizard') and view_type == 'tree':
        root = etree.fromstring(res['arch'])
        fields = root.xpath('/tree')
        for field in fields:
            root.set('noteditable', 'True')
            if context.get('procurement_request'):
                root.set('string', 'Internal request lines')
            if context.get('rfq_ok'):
                root.set('string', 'RfQ lines')
        res['arch'] = etree.tostring(root)

    return res


class product_list_line(osv.osv):
    _inherit = 'product.list.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(product_list_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class claim_product_line(osv.osv):
    _inherit = 'claim.product.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(claim_product_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        if context.get('initial_doc_id', False) and context.get('initial_doc_type', False) == 'purchase.order':
            rfq_ok = self.pool.get('purchase.order').browse(cr, uid, context.get('initial_doc_id'), context=context).rfq_ok
            context['rfq_ok'] = rfq_ok
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(purchase_order_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class composition_item(osv.osv):
    _inherit = 'composition.item'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(composition_item, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class tender_line(osv.osv):
    _inherit = 'tender.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(tender_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        if context.get('initial_doc_id', False) and context.get('initial_doc_type', False) == 'sale.order':
            proc_request = self.pool.get('sale.order').browse(cr, uid, context.get('initial_doc_id'), context=context).procurement_request
            context['procurement_request'] = proc_request

        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(sale_order_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class supplier_catalogue_line(osv.osv):
    _inherit = 'supplier.catalogue.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(supplier_catalogue_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class stock_move(osv.osv):
    _inherit = 'stock.move'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(stock_move, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class stock_warehouse_automatic_supply_line(osv.osv):
    _inherit = 'stock.warehouse.automatic.supply.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(stock_warehouse_automatic_supply_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class stock_warehouse_order_cycle_line(osv.osv):
    _inherit = 'stock.warehouse.order.cycle.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(stock_warehouse_order_cycle_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class threshold_value_line(osv.osv):
    _inherit = 'threshold.value.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(threshold_value_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class stock_inventory_line(osv.osv):
    _inherit = 'stock.inventory.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(stock_inventory_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class initial_stock_inventory_line(osv.osv):
    _inherit = 'initial.stock.inventory.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(initial_stock_inventory_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class real_average_consumption_line(osv.osv):
    _inherit = 'real.average.consumption.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(real_average_consumption_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


class monthly_review_consumption_line(osv.osv):
    _inherit = 'monthly.review.consumption.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view_id = delete_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(monthly_review_consumption_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


product_list_line()
claim_product_line()
purchase_order_line()
composition_item()
tender_line()
sale_order_line()
supplier_catalogue_line()
stock_move()
stock_warehouse_automatic_supply_line()
stock_warehouse_order_cycle_line()
threshold_value_line()
stock_inventory_line()
initial_stock_inventory_line()
real_average_consumption_line()
monthly_review_consumption_line()

### END OF INHERITANCE ###


class wizard_delete_lines(osv.osv_memory):
    """
    Wizard to remove lines of document.

    The displaying of lines to remove is dynamically build according to
    the initial_doc_type given (see fields_get method).
    """
    _name = 'wizard.delete.lines'

    _columns = {
        'initial_doc_id': fields.integer(string='ID of the initial document', required=True),
        'initial_doc_type': fields.char(size=128, string='Model of the initial document', required=True),
        'to_remove_type': fields.char(size=128, string='Model of the lines', required=True),
        'linked_field_name': fields.char(size=128, string='Field name of the link between lines and original doc', required=True),
        'qty_field': fields.char(size=128, string='Qty field used to select only empty lines'),
        # The line_ids field is a text field, but the content of this field is
        # the result of the many2many field creation (like [(6,0,[IDS])]).
        # On the remove_selected_lines method, we parse this content to get
        # id of the lines to remove.
        'line_ids': fields.text(string='Line ids'),
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Check if the wizard has been overrided
        '''
        context = context is None and {} or context

        res = super(wizard_delete_lines, self).default_get(cr, uid, fields, context=context)

        # Set the different data which are coming from the context
        if 'active_id' in context:
            res['initial_doc_id'] = context.get('active_id')

        if 'active_model' in context and context.get('active_model') in DOCUMENT_DATA:
            res['initial_doc_type'] = context.get('active_model')
            res['to_remove_type'] = DOCUMENT_DATA.get(context.get('active_model'))[0]
            res['linked_field_name'] = DOCUMENT_DATA.get(context.get('active_model'))[1]
            res['qty_field'] = DOCUMENT_DATA.get(context.get('active_model'))[3]

#        if 'active_id' in context and 'active_model' in context and context.get('active_model') in DOCUMENT_DATA:
#            line_field = DOCUMENT_DATA.get(context.get('active_model'))[2]
#            lines = self.pool.get(res['initial_doc_type']).read(cr, uid, res['initial_doc_id'], [line_field], context=context)
#            res['line_ids'] = lines[line_field]

        return res

    def remove_selected_lines(self, cr, uid, ids, context=None):
        '''
        Remove only the selected lines
        '''
        context = context is None and {} or context
        if isinstance(ids, (int, long)):
            ids = [ids]

        # only for FO
        if context['active_model'] == 'sale.order' \
                and (not context.get('procurement_request') or not context['procurement_request']):
            lines_ids = []
            for wiz in self.browse(cr, uid, ids, context=context):
                # the id of lines to remove.
                for line in wiz.line_ids:
                    for l in line[2]:
                        lines_ids.append(l)

            context['from_del_wizard'] = False
            ids = lines_ids
            model = 'delete.sale.order.line.wizard'
            name = _('Warning!')
            wiz_obj = self.pool.get('wizard')
            if len(ids) > 0:
                # open the selected wizard
                return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)
        else:
            for wiz in self.browse(cr, uid, ids, context=context):
                line_obj = self.pool.get(wiz.to_remove_type)
                line_ids = []
                # Parse the content of 'line_ids' field (text field) to retrieve
                # the id of lines to remove.
                for line in wiz.line_ids:
                    for l in line[2]:
                        line_ids.append(l)

                context['noraise'] = True
                context.update({
                    'noraise': True,
                    'from_del_wizard': True,
                })
                if wiz.to_remove_type in ('purchase.order.line', 'tender.line', 'delete.sale.order.line.wizard'):
                    line_obj.fake_unlink(cr, uid, line_ids, context=context)
                else:
                    line_obj.unlink(cr, uid, line_ids, context=context)
            context['from_del_wizard'] = False

        return {'type': 'ir.actions.act_window_close'}

    def select_empty_lines(self, cr, uid, ids, context=None):
        '''
        Add empty lines
        '''
        return self.select_all_lines(cr, uid, ids, context=context, select_only_empty=True)

    def select_all_lines(self, cr, uid, ids, context=None, select_only_empty=False):
        '''
        Select all lines of the initial document
        '''
        context = context is None and {} or context
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if select_only_empty and not wiz.qty_field:
                raise osv.except_osv(_('Error'), _('The select empty lines is not available for this document'))

            line_obj = self.pool.get(wiz.to_remove_type)
            if select_only_empty:
                line_ids = line_obj.search(cr, uid, [(wiz.linked_field_name, '=', wiz.initial_doc_id), (wiz.qty_field, '=', 0.00)], context=context)
            else:
                line_ids = line_obj.search(cr, uid, [(wiz.linked_field_name, '=', wiz.initial_doc_id)], context=context)

            if wiz.to_remove_type in ['sale.order.line', 'purchase.order.line']:
                line_ids = line_obj.search(cr, uid, [('id', 'in', line_ids), ('state', 'not in', ['cancel', 'cancel_r'])], context=context)

            self.write(cr, uid, [wiz.id], {'line_ids': line_ids}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids and wiz.id or False,
            'context': context,
            'target': 'new',
        }

    def fields_get(self, cr, uid, fields=None, context=None):
        '''
        On this fields_get method, we build the line_ids field.
        The line_ids field is defined as a text field but, for users, this
        field should be displayed as a many2many that allows us to select
        lines of document to remove.
        The line_ids field is changed to a many2many field according to the
        data in DOCUMENT_DATA (see top of this file).
        '''
        context = context is None and {} or context

        res = super(wizard_delete_lines, self).fields_get(cr, uid, fields, context=context)

        if context.get('active_model') and DOCUMENT_DATA.get(context.get('active_model')):
            ddata = DOCUMENT_DATA.get(context.get('active_model'))
            line_obj = ddata[0]
            if not ddata[4]:
                domain = "[('%s', '=', initial_doc_id)]" % ddata[1]
            else:
                domain = "[%s, ('%s', '=', initial_doc_id)]" % (ddata[4], ddata[1])
            res.update(line_ids={'related_columns': ['wiz_id', 'line_id'],
                                 'relation': line_obj,
                                 'string': 'Lines to remove',
                                 'context': context,
                                 'third_table': '%sto_remove' % line_obj.replace('.', '_'),
                                 'selectable': True,
                                 'type': 'many2many',
                                 'domain': "%s" % domain})

        return res

wizard_delete_lines()
