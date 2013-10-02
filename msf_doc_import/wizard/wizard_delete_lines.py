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
"""
This dictionnary is used by the document.remove.line and wizard.delete.lines
objects to get the different relation between a parent document and its lines.

The dictionnary keys are the parent document model and the values of the dict
are a tuple with information in this order :
    * model of the line for the parent document
    * field of the line that link the line to its parent
    * field of the parent that contains the lines
"""
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


#class document_remove_line(osv.osv):
#    """
#    This object is a dummy object used to have only one method to remove
#    lines from multiple objects.
#    Some other objects inherit from this object to avoid multiple overriding of
#    the button_remove_lines method.
#    """
#
#    _name = 'document.remove.line'

def brl(self, cr, uid, ids, context=None):
    '''
    Call the wizard to remove lines
    '''
    context = context or {}

    if isinstance(ids, (int, long)):
        ids = [ids]

    # If there is no line to remove.
    for obj in self.browse(cr, uid, ids, context=context):
        if not obj[DOCUMENT_DATA.get(self._name)[2]]:
            raise osv.except_osv(_('Error'), _('No line to remove'))

    # Return the wizard to display lines to remove
    return {'type': 'ir.actions.act_window',
            'res_model': 'wizard.delete.lines',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(context, active_id=ids[0], active_model=self._name)}

#document_remove_line()


#### DOCUMENT INHERITANCE ####
"""
All the following documents will inherit from document.remove.line to have an
unique button_remove_lines method to remove some or all lines on documents.

Documents which inherit from document.remove.line:
    * Product List
    * Theoretical Kit Composition
    * Purchase Order / Request for Quotation
    * Tender
    * Field Order / Internal request
    * Supplier catalogue
    * Stock Picking (IN / INT / OUT / PICK)
    * Order Cycle Replenishment Rule
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
#    _inherit = ['product.list', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
#    _inherit = ['purchase.order', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class composition_kit(osv.osv):
    _name = 'composition.kit'
    _inherit = 'composition.kit'
#    _inherit = ['composition.kit', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class tender(osv.osv):
    _name = 'tender'
    _inherit = 'tender'
#    _inherit = ['tender', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
#    _inherit = ['sale.order', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class supplier_catalogue(osv.osv):
    _name = 'supplier.catalogue'
    _inherit = 'supplier.catalogue'
#    _inherit = ['supplier.catalogue', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'
#    _inherit = ['stock.picking', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_warehouse_automatic_supply(osv.osv):
    _name = 'stock.warehouse.automatic.supply'
    _inherit = 'stock.warehouse.automatic.supply'
#    _inherit = ['stock.warehouse.automatic.supply', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_warehouse_order_cycle(osv.osv):
    _name = 'stock.warehouse.order.cycle'
    _inherit = 'stock.warehouse.order.cycle'
#    _inherit = ['stock.warehouse.order.cycle', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class threshold_value(osv.osv):
    _name = 'threshold.value'
    _inherit = 'threshold.value'
#    _inherit = ['threshold.value', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class stock_inventory(osv.osv):
    _name = 'stock.inventory'
    _inherit = 'stock.inventory'
#    _inherit = ['stock.inventory', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class initial_stock_inventory(osv.osv):
    _name = 'initial.stock.inventory'
    _inherit = 'initial.stock.inventory'
#    _inherit = ['initial.stock.inventory', 'document.remove.line']

    def button_remove_lines(self, cr, uid, ids, context=None):
        return brl(self, cr, uid, ids, context=context)


class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _inherit = 'real.average.consumption'
#    _inherit = ['real.average.consumption', 'document.remove.line']

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
purchase_order()
composition_kit()
tender()
sale_order()
supplier_catalogue()
stock_picking()
stock_warehouse_automatic_supply()
stock_warehouse_order_cycle()
threshold_value()
stock_inventory()
initial_stock_inventory()
real_average_consumption()
monthly_review_consumption()

#### END OF INHERITANCE OF DOCUMENTS ####


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
        context = context or {}

        res = super(wizard_delete_lines, self).default_get(cr, uid, fields, context=context)

        # Set the different data which are coming from the context
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
            # Parse the content of 'line_ids' field (text field) to retrieve
            # the id of lines to remove.
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

    def fields_get(self, cr, uid, fields=None, context=None):
        '''
        On this fields_get method, we build the line_ids field.
        The line_ids field is defined as a text field but, for users, this 
        field should be displayed as a many2many that allows us to select
        lines of document to remove.
        The line_ids field is changed to a many2many field according to the
        data in DOCUMENT_DATA (see top of this file).
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

