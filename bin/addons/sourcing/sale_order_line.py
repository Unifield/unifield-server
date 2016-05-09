# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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

from datetime import date
from dateutil.relativedelta import relativedelta
import threading
import time

import netsvc
from osv import osv, fields
from osv.orm import browse_record
import pooler
from tools import misc
from tools.translate import _
from collections import deque

import decimal_precision as dp
from order_types import ORDER_PRIORITY
from order_types import ORDER_CATEGORY
from sale_override import SALE_ORDER_STATE_SELECTION

_SELECTION_PO_CFT = [
    ('po', 'Purchase Order'),
    ('dpo', 'Direct Purchase Order'),
    ('cft', 'Tender'),
    ('rfq', 'Request for Quotation'),
]


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'

    _replace_exported_fields = {
        'product_id': [
            (['product_code', 'Product Code'], 10),
            (['product_name', 'Product Description'], 20),
        ],
    }

    """
    Other methods
    """
    def _check_browse_param(self, param, method):
        """
        Returns an error message if the parameter is not a
        browse_record instance

        :param param: The parameter to test
        :param method: Name of the method that call the _check_browse_param()

        :return True
        """
        if not isinstance(param, browse_record):
            raise osv.except_osv(
                _('Bad parameter'),
                _("""Exception when call the method '%s' of the object '%s' :
The parameter '%s' should be an browse_record instance !""") % (method, self._name, param)
            )

        return True

    def _get_supplier(self, cr, uid, ids, context=None):
        """
        Returns a list of sale.order.line ID to update
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of res.partner
        :param context: Context of the call
        :return: List of sale.order.line ID to update
        """
        return self.pool.get('sale.order.line').search(cr, uid, [
            ('supplier', 'in', ids),
            ('state', '=', 'draft'),
        ], context=context)

    def _check_related_sourcing_ok(self, cr, uid, supplier=False, l_type='make_to_order', context=None):
        """
        Return True if the supplier allows split PO.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param supplier: ID of the res.partner selected as supplier for the sale.order.line
        :param l_type: Procurement method selected for the sale.order.line
        :param context: Context of the call
        :return: True or False
        """
        if not supplier:
            return False

        sup_rec = self.pool.get('res.partner').\
            read(cr, uid, [supplier], ['partner_type', 'split_po'], context=context)[0]

        return l_type == 'make_to_order' and sup_rec['partner_type'] == 'esc' and sup_rec['split_po'] == 'yes'

    """
    Methods to get fields.function values
    """
    def _get_fake(self, cr, uid, idsrelated_sourcing_ok, field_name, args, context=None):
        """
        Returns False for each ID.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of field order lines to re-compute
        :param field_name: A fOield or a list of fields to be computed
        :param args: Some other arguments
        :param context: Context of the call

        :return A dictionnary with field order line id as keys and False
                 as value
        :rtype dict
        """
        res = {}
        for i in ids:
            res[i] = False

        return res

    def _get_sale_order_state(self, cr, uid, order=None, context=None):
        """
        Compute the state of the field order.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line: browse_record of the sale.order
        :param context: Context of the call

        :return The state of the sale order or False
        :rtype string
        """
        if context is None:
            context = {}

        self._check_browse_param(order, method='_get_sale_order_state')

        if order and not order.procurement_request and order.state == 'done' and order.split_type_sale_order == 'original_sale_order':
            return 'split_so'
        elif order:
            return order.state

        return False

    def _get_date(self, cr, uid, line, context=None):
        """
        Compute the estimated delivery date of the line according
        to values already on line.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line: browse_record of the sale.order.line
        :param context: Context of the call

        :return The estimated delivery date or False
        :rtype string
        """
        if context is None:
            context = {}

        self._check_browse_param(line, method='_get_date')

        res = False

        if line.cf_estimated_delivery_date and line.state in ('done', 'confirmed'):
            res = line.cf_estimated_delivery_date
        elif line.supplier:
            get_delay = self.onChangeSupplier(cr,
                                              uid,
                                              [line.id],
                                              line.supplier.id,
                                              line.type,
                                              context=context)
            res = get_delay.get('value', {}).get('estimated_delivery_date', False)

        return res

    def _get_line_values(self, cr, uid, ids, field_name, args, context=None):
        """
        Get some values from the field order line.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of field order lines to re-compute
        :param field_name: A field or a list of fields to be computed
        :param args: Some other arguments
        :param context: Context of the call

        :return A dictionnary with field order line id as keys and associated
                 computed values
        :rtype dict
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            values = {
                'priority': line.order_id.priority,
                'categ': line.order_id.categ,
                'rts': line.order_id.ready_to_ship_date,
                'procurement_request': line.order_id.procurement_request,
                'loan_type': line.order_id.order_type == 'loan',
                'estimated_delivery_date': self._get_date(cr, uid, line, context=context),
                'display_confirm_button': line.state == 'draft' and line.order_id.state == 'validated',
                'sale_order_in_progress': line.order_id.sourcing_trace_ok,
                'sale_order_state': self._get_sale_order_state(cr, uid, line.order_id, context=context),
            }
            res[line.id] = values

        return res

    def _getAvailableStock(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """
        Get the available stock for each line

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of field order lines to re-compute
        :param field_name: A field or a list of fields to be computed
        :param args: Some other arguments
        :param context: Context of the call

        :return A dictionnary with field order line id as keys and associated
                 available stock
        :rtype dict
        """
        # Objects
        product_obj = self.pool.get('product.product')

        result = {}

        for line in self.browse(cr, uid, ids, context=context):
            if line.product_id:
                real_stock = line.real_stock
                context.update({
                    'states': ['assigned', ],
                    'what': ['out', ],
                })

                if line.type == 'make_to_stock' and line.location_id:
                    context['location'] = line.location_id.id

                if 'to_date' in context:
                    del context['to_date']

                product = product_obj.get_product_available(cr, uid, [line.product_id.id], context=context)
                res = real_stock + product.get(line.product_id.id, 0.00)
            else:
                res = 0.00

            result[line.id] = res

        return result

    def _getVirtualStock(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """
        Get the virtual stock for each line

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of field order lines to re-compute
        :param field_name: A field or a list of fields to be computed
        :param args: Some other arguments
        :param context: Context of the call

        :return A dictionnary with field order line id as keys and associated
                 available stock
        :rtype dict
        """
        # Objects
        warehouse_obj = self.pool.get('stock.warehouse')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        result = {}

        # UF-1411 : Compute the virtual stock on Stock + Input locations
        wh_location_ids = []
        wids = warehouse_obj.search(cr, uid, [], context=context)
        for w in warehouse_obj.browse(cr, uid, wids, context=context):
            wh_location_ids.append(w.lot_stock_id.id)
            wh_location_ids.append(w.lot_input_id.id)

        # For each sourcing line
        for sl in self.browse(cr, uid, ids, context):
            # Get the stock location on which the stock is computed
            if sl.type == 'make_to_stock' and sl.location_id:
                location_ids = sl.location_id.id
            else:
                location_ids = wh_location_ids

            rts = sl.rts < time.strftime('%Y-%m-%d') and time.strftime('%Y-%m-%d') or sl.rts

            context.update({
                'location': location_ids,
                'to_date': '%s 23:59:59' % rts
            })

            if sl.product_id:
                product_virtual = product_obj.browse(cr, uid, sl.product_id.id, context=context)
                res = {
                    'real_stock': product_virtual.qty_available,
                    'virtual_stock': product_virtual.virtual_available,
                }
            else:
                res = {
                    'real_stock': 0.00,
                    'virtual_stock': 0.00,
                }

            result[sl.id] = res

        return result

    """
    Methods to search values for fields.function
    """
    def _src_order_state(self, cr, uid, obj, name, args, context=None):
        """
        Returns all field order lines that match with the order state domain
        given in args.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param obj: Object on which the search is
        :param field_name: Name of the field on which the search is
        :param args: The domain
        :param context: Context of the call

        :return A list of tuples that allows the system to return the list
                 of matching field order lines
        :rtype list
        """
        if context is None:
            context = {}

        if not args:
            return []

        res = []
        for arg in args:
            if arg[0] == 'sale_order_state':
                res = [('order_id.state', arg[1], arg[2])]

        return res

    def _search_need_sourcing(self, cr, uid, obj, name, args, context=None):
        """
        Returns all field order lines that need to be sourced according to the
        domain given in args.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param obj: Object on which the search is
        :param field_name: Name of the field on which the search is
        :param args: The domain
        :param context: Context of the call

        :return A list of tuples that allows the system to return the list
                 of matching field order lines
        :rtype list
        """
        if context is None:
            context = {}

        if not args:
            return []

        # Put procurement_request = True in context to get FO and IR
        context['procurement_request'] = True

        if args[0][1] != '=' or not args[0][2]:
            raise osv.except_osv(_('Error !'), _('Filter not implemented'))

        return [('state', '=', 'draft'), ('sale_order_state', '=', 'validated')]

    def _search_in_progress(self, cr, uid, obj, name, args, context=None):
        """
        Returns all field order lines that are sourcing in progress according to
        the domain given in args.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param obj: Object on which the search is
        :param field_name: Name of the field on which the search is
        :param args: The domain
        :param context: Context of the call

        :return A list of tuples that allows the system to return the list
                 of matching field order lines
        :rtype list
        """
        if context is None:
            context = {}

        if not args:
            return []

        # Put procurement_request = True in context to get FO and IR
        context['procurement_request'] = True

        if args[0][1] != '=' or not args[0][2]:
            raise osv.except_osv(_('Error !'), _('Filter not implemented'))

        return [
            ('display_confirm_button', '=', False),
            ('state', '!=', 'draft'),
            ('sale_order_in_progress', '=', False),
            '|', '&',
            ('type', '=', 'make_to_order'),
            ('procurement_id.state', '=', 'confirmed'),
            ('sale_order_state', '=', 'validated'),
        ]

    def _get_related_sourcing_ok(self, cr, uid, ids, field_name, args, context=None):
        """
        Return True or False to determine if the user could select a sourcing group on the OST for the line
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param ids: List of ID of sale.order.line to compute
        :param field_name: Name of the fields to compute
        :param args: Extra parameters
        :param context: Context of the call
        :return: True or False
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._check_related_sourcing_ok(cr, uid, line.supplier.id, line.type, context=context)

        return res

    _columns = {
        'customer': fields.related(
            'order_id',
            'partner_id',
            string='Customer',
            readonly=True,
        ),
        'po_cft': fields.selection(
            _SELECTION_PO_CFT,
            string="PO/CFT",
        ),
        'supplier': fields.many2one(
            'res.partner',
            'Supplier',
        ),
        'related_sourcing_id': fields.many2one(
            'related.sourcing',
            string='Group',
        ),
        'location_id': fields.many2one(
            'stock.location',
            string='Location',
        ),
        'priority': fields.function(
            _get_line_values,
            method=True,
            selection=ORDER_PRIORITY,
            type='selection',
            string='Priority',
            readonly=True,
            store=False,
            multi='line_info',
        ),
        'categ': fields.function(
            _get_line_values,
            method=True,
            selection=ORDER_CATEGORY,
            type='selection',
            string='Category',
            readonly=True,
            store=False,
            multi='line_info',
        ),
        'sale_order_state': fields.function(
            _get_line_values,
            fnct_search=_src_order_state,
            method=True,
            selection=SALE_ORDER_STATE_SELECTION,
            type='selection',
            string='Order State',
            readonly=True,
            store=False,
            multi='line_info',
        ),
        'rts': fields.function(
            _get_line_values,
            method=True,
            string='RTS',
            type='date',
            readonly=True,
            store=False,
            multi='line_info',
        ),
        'stock_uom_id': fields.related(
            'product_id',
            'uom_id',
            string='UoM',
            type='many2one',
            relation='product.uom',
            readonly=True,
        ),
        'cf_estimated_delivery_date': fields.date(
            string='Confirmed Estimated DD',
            readonly=True,
        ),
        'estimated_delivery_date': fields.function(
            _get_line_values,
            method=True,
            type='date',
            string='Estimated DD',
            store=False,
            readonly=True,
            multi='line_info',
        ),
        'display_confirm_button': fields.function(
            _get_line_values,
            method=True,
            type='boolean',
            string='Display Button',
            multi='line_info',
        ),
        'need_sourcing': fields.function(
            _get_fake,
            method=True,
            type='boolean',
            string='Only for filtering',
            fnct_search=_search_need_sourcing,
        ),
        'in_progress': fields.function(
            _get_fake,
            method=True,
            type='boolean',
            string='Only for filtering',
            fnct_search=_search_in_progress,
        ),
        # UTP-392: if the FO is loan type, then the procurement method is only Make to Stock allowed
        'loan_type': fields.function(
            _get_line_values,
            method=True,
            type='boolean',
            multi='line_info',
        ),
        'sale_order_in_progress': fields.function(
            _get_line_values,
            method=True,
            type='boolean',
            string='Order in progress',
            multi='line_info',
        ),
        'related_sourcing_ok': fields.function(
            _get_related_sourcing_ok,
            method=True,
            type='boolean',
            string='Related sourcing OK',
            store={
                'sale.order.line': (lambda obj, cr, uid, ids, c={}: ids, ['supplier', 'type'], 10),
                'res.partner': (_get_supplier, ['partner_type', 'split_po'], 20),
            },
        ),
        # UTP-965 : Select a source stock location for line in make to stock
        'real_stock': fields.function(
            _getVirtualStock,
            method=True,
            type='float',
            string='Real Stock',
            digits_compute=dp.get_precision('Product UoM'),
            readonly=True,
            multi='stock_qty',
        ),
        'virtual_stock': fields.function(
            _getVirtualStock, method=True,
            type='float',
            string='Virtual Stock',
            digits_compute=dp.get_precision('Product UoM'),
            readonly=True,
            multi='stock_qty',
        ),
        'available_stock': fields.function(
            _getAvailableStock,
            method=True,
            type='float',
            string='Available Stock',
            digits_compute=dp.get_precision('Product UoM'),
            readonly=True,
        ),
        # Fields used for export
        'product_code': fields.related(
            'product_id',
            'default_code',
            type='char',
            size=64,
            string='Product code',
            store=False,
        ),
        'product_name': fields.related(
            'product_id',
            'name',
            type='char',
            size=128,
            string='Product description',
            store=False,
        ),
    }

    """
    Methods to check constraints
    """
    def _check_procurement_for_service_with_recep(self, cr, uid, ids, context=None):
        """
        If the product on line is a Service with Reception product, the procurement method
        should be 'Make to Order'.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of the sale.order.line to check
        :param context: Context of the call

        :return True if no error
        :rtype boolean
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.product_id.type == 'service_recep' and obj.type != 'make_to_order':
                raise osv.except_osv(
                    _('Error'),
                    _('You must select on order procurement method for Service with Reception products.'),
                )
        return True

    _constraints = [
        (_check_procurement_for_service_with_recep, 'You must select on order procurement method for Service with Reception products.', []),
    ]

    """
    Model methods
    """
    def default_get(self, cr, uid, fields_list, context=None):
        """
        Set default values (location_id) for sale_order_line

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param fields_list: Fields to set
        :param context: Context of the call

        :return Dictionnary with fields_list as keys and default value
                 of field.
        :rtype dict
        """
        # Objects
        warehouse_obj = self.pool.get('stock.warehouse')

        res = super(sale_order_line, self).default_get(cr, uid, fields_list, context=context)

        if res is None:
            res = {}

        warehouse = warehouse_obj.search(cr, uid, [], context=context)
        if warehouse:
            res['location_id'] = warehouse_obj.browse(cr, uid, warehouse[0], context=context).lot_stock_id.id

        return res

    def create(self, cr, uid, vals=None, context=None):
        """
        Update some values according to Field order values

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param vals: A dictionary with values of the new line to create
        :param context: Context of the call

        :return The ID of the new line
        :rtype integer
        """
        # Objects
        order_obj = self.pool.get('sale.order')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        if vals is None:
            vals = {}

        product = None
        if vals.get('product_id', False):
            product = product_obj.browse(cr, uid, vals['product_id'], context=context)

        ir = False
        order_p_type = False
        if vals.get('order_id', False):
            order = order_obj.browse(cr, uid, vals['order_id'], context=context)
            ir = order.procurement_request
            order_p_type = order.partner_type
            if order.order_type == 'loan' and order.state == 'validated':
                vals.update({
                    'type': 'make_to_stock',
                    'po_cft': False,
                    'supplier': False,
                })

        if product and vals.get('type', False) == 'make_to_order' and not vals.get('supplier', False):
            vals['supplier'] = product.seller_id and product.seller_id.id or False

        if product and product.type in ('consu', 'service', 'service_recep'):
            vals['type'] = 'make_to_order'

        if product and product.type in ('service', 'service_recep'):
            if ir and vals.get('po_cft', 'dpo') == 'dpo':
                vals['po_cft'] = 'po'
            elif not ir and vals.get('po_cft', 'po') == 'po':
                vals['po_cft'] = 'dpo'

        # If type is missing, set to make_to_stock and po_cft to False
        if not vals.get('type', False):
            vals.update({
                'type': 'make_to_stock',
                'po_cft': False,
            })

        # Fill PO/CfT : by default, if MtO -> PO and PO/Cft is not specified in data, if MtS -> False
        if not vals.get('po_cft', False) and vals.get('type', False) == 'make_to_order':
            vals['po_cft'] = 'po'
        elif vals.get('type', False) == 'make_to_stock':
            vals['po_cft'] = False

        # UFTP-11: if make_to_order can not have a location
        if vals.get('type', False) == 'make_to_order':
            vals['location_id'] = False
            if vals.get('supplier') and order_p_type == 'internal':
                sup = partner_obj.read(cr, uid, vals.get('supplier'), ['partner_type'], context=context)
                if sup['partner_type'] == 'internal':
                    vals['supplier'] = False

        # UFTP-139: if make_to_stock and no location, put Stock as location
        if vals.get('type', False) == 'make_to_stock' and not vals.get('location_id', False):
            stock_loc = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
            vals['location_id'] = stock_loc

        # Create the new sale order line
        res = super(sale_order_line, self).create(cr, uid, vals, context=context)

        self._check_line_conditions(cr, uid, res, context)

        return res

    def update_supplier_on_line(self, cr, uid, line_ids, context=None):
        """
        Update the selected supplier on lines for line in make_to_order.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line_ids: List of ID of sale.order.line to update
        :param context: Context of the call

        :return True
        :rtype bool
        """
        if context is None:
            context = {}

        if isinstance(line_ids, (int, long)):
            line_ids = [line_ids]

        for line in self.browse(cr, uid, line_ids, context=context):
            if line.type == 'make_to_order' and line.product_id \
               and line.product_id.seller_id:
                self.write(cr, uid, [line.id], {
                    'supplier': line.product_id.seller_id.id,
                }, context=context)

        return True

    def _check_loan_conditions(self, cr, uid, line, context=None):
        """
        Check if the value of lines are compatible with the value
        of the order

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line: browse_record of the sale.order.line
        :param context: Context of the call

        :return The error message if any or False
        :rtype string
        """
        if context is None:
            context = {}

        self._check_browse_param(line, method='_check_loan_conditions')

        l_type = line.type == 'make_to_order'
        o_state = line.order_id and line.order_id.state != 'draft' or False
        ctx_cond = not context.get('fromOrderLine')
        o_type = line.order_id and line.order_id.order_type == 'loan' or False

        if l_type and o_state and ctx_cond and o_type:
            return _('You can\'t source a loan \'on order\'.')

        return False

    # TODO: Maybe move conditions on some methods
    def _check_line_conditions(self, cr, uid, ids, context=None):
        """
        Check if the value of lines are compatible with the other
        values.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line to check
        :param context: Context of the call

        :return The error message if any or False
        :rtype boolean
        """
        # Objects
        product_obj = self.pool.get('product.product')

        if not context:
            context = {}
        if context.get('no_check_line', False):
            return True

        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(cr, uid, ids, context=context):
            clc = self._check_loan_conditions(cr, uid, line, context=context)
            if clc:
                raise osv.except_osv(_('Warning'), clc)

            proc_request = line.order_id and line.order_id.procurement_request

            if proc_request and line.type == 'make_to_stock' and line.order_id.location_requestor_id.id == line.location_id.id:
                raise osv.except_osv(
                    _('Warning'),
                    _("You cannot choose a source location which is the destination location of the Internal Request"),
                )

            if line.type == 'make_to_order' and \
               line.po_cft not in ['cft'] and \
               not line.product_id and \
               line.order_id.procurement_request and \
               line.supplier and \
               line.supplier.partner_type not in ['internal', 'section', 'intermission']:
                raise osv.except_osv(
                    _('Warning'),
                    _("""For an Internal Request with a procurement method 'On Order' and without product,
the supplier must be either in 'Internal', 'Inter-section' or 'Intermission type."""),
                )

            if line.product_id and \
               line.product_id.type in ('consu', 'service', 'service_recep') and \
               line.type == 'make_to_stock':
                product_type = line.product_id.type == 'consu' and _('non stockable') or _('service')
                raise osv.except_osv(
                    _('Warning'),
                    _("""You cannot choose 'from stock' as method to source a %s product !""") % product_type,
                )

            if line.product_id and \
               line.po_cft == 'rfq' and \
               line.supplier.partner_type in ['internal', 'section', 'intermission']:
                raise osv.except_osv(
                    _('Warning'),
                    _("""You can't source with 'Request for Quotation' to an internal/inter-section/intermission partner."""),
                )

            if line.product_id and \
               line.product_id.type in ('service', 'service_recep') and \
               not line.order_id.procurement_request and \
               line.po_cft == 'po':
                raise osv.except_osv(
                    _('Warning'),
                    _("""'Purchase Order' is not allowed to source a 'Service' product."""),
                )

            if not line.product_id:
                if line.po_cft == 'cft':
                    raise osv.except_osv(
                        _('Warning'),
                        _("You can't source with 'Tender' if you don't have product."),
                    )
                if line.po_cft == 'rfq':
                    raise osv.except_osv(
                        _('Warning'),
                        _("You can't source with 'Request for Quotation' if you don't have product."),
                    )
                if line.type == 'make_to_stock':
                    raise osv.except_osv(
                        _('Warning'),
                        _("You can't Source 'from stock' if you don't have product."),
                    )
                if line.supplier and line.supplier.partner_type in ('external', 'esc'):
                    raise osv.except_osv(
                        _('Warning'),
                        _("You can't Source to an '%s' partner if you don't have product.") %
                        (line.supplier.partner_type == 'external' and 'External' or 'ESC'),
                    )

            if line.state not in ('draft', 'cancel') and line.product_id and line.supplier:
                # Check product constraints (no external supply, no storage...)
                check_fnct = product_obj._get_restriction_error
                self._check_product_constraints(cr, uid, line.type, line.po_cft, line.product_id.id, line.supplier.id, check_fnct, context=context)

        return True

    def _check_product_constraints(self, cr, uid, line_type='make_to_order', po_cft='po',
                                   product_id=False, partner_id=False, check_fnct=False, *args, **kwargs):
        """
        Check if the value of lines are compatible with the other
        values.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line_type: Procurement type of the line
        :param po_cft: MTO procurement type of the line
        :param product_id: ID of the product of the line
        :param partner_id: ID of the supplier
        :param check_fnct: The method that will be called to check constraints
        :param *args: Othen non-keyward arguments
        :param **kwargs: Other keyword arguments

        :return A tuple with the error message if any and the result of the check
        :rtype tuple(string, boolean)
        """
        if not check_fnct:
            check_fnct = self.pool.get('product.product')._get_restriction_error

        vals = {}
        if line_type == 'make_to_order' and product_id and (po_cft == 'cft' or partner_id):
            if po_cft == 'cft':
                vals = {'constraints': ['external']}
            elif partner_id:
                vals = {'partner_id': partner_id}
        elif line_type == 'make_to_stock' and product_id:
            vals = {'constraints': ['storage']}

        if product_id:
            return check_fnct(cr, uid, product_id, vals, *args, **kwargs)

        return '', False

    def check_supplierinfo(self, line, partner, context=None):
        """
        Returns the supplier lead time or -1 according to supplier

        :param line: browse_record of the sale.order.line
        :param partner: browse_record of the res.partner
        :param context: Context of the call

        :return The supplier lead time if any or -1
        :rtype integer
        """
        if context is None:
            context = {}

        self._check_browse_param(line, 'check_supplierinfo')
        self._check_browse_param(partner, 'check_supplierinfo')

        if line.supplier and line.supplier.supplier_lt:
            return line.supplier.supplier_lt
        else:
            return partner.default_delay

        return -1

    def write(self, cr, uid, ids, vals, context=None):
        """
        Write new values on the sale.order.line record and
        check if the new values are compatible with the line
        and order values.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line to write
        :param vals: Dictionary with the new values
        :param context: Context of the call

        :return True if all is ok else False
        :rtype boolean
        """
        # Objects
        product_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')

        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        product = False

        if vals.get('product_id', False):
            product = product_obj.browse(cr, uid, vals['product_id'])
            if product.type in ('consu', 'service', 'service_recep'):
                vals['type'] = 'make_to_order'

        if 'state' in vals and vals['state'] == 'cancel':
            self.write(cr, uid, ids, {'cf_estimated_delivery_date': False}, context=context)

        if 'type' in vals:
            if vals['type'] == 'make_to_stock':
                vals.update({
                    'po_cft': False,
                    'supplier': False,
                })

        # Search lines to modified with loan values
        loan_sol_ids = self.search(cr, uid, [('order_id.order_type', '=', 'loan'),
                                             ('order_id.state', '=', 'validated'),
                                             ('id', 'in', ids)], context=context)

        if loan_sol_ids:
            loan_vals = vals.copy()
            loan_data = {'type': 'make_to_stock',
                         'po_cft': False,
                         'suppier': False}
            loan_vals.update(loan_data)

            if loan_sol_ids:
                # Update lines with loan
                super(sale_order_line, self).write(cr, uid, loan_sol_ids, loan_vals, context)

        # UFTP-11: if make_to_order can not have a location
        if vals.get('type', False) == 'make_to_order':
            vals['location_id'] = False

        # UFTP-139: if make_to_stock and no location, put Stock as location
        if ids and 'type' in vals and  vals.get('type', False) == 'make_to_stock' and not vals.get('location_id', False):
            # Define Stock as location_id for each line without location_id
            for line in self.read(cr, uid, ids, ['location_id'], context=context):
                line_vals = vals.copy()
                if not line['location_id'] and not vals.get('location_id', False):
                    stock_loc = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]
                    line_vals['location_id'] = stock_loc
                result = super(sale_order_line, self).write(cr, uid, [line['id']], line_vals, context)
        else:
            result = super(sale_order_line, self).write(cr, uid, ids, vals, context)

        f_to_check = ['type', 'order_id', 'po_cft', 'product_id', 'supplier', 'state', 'location_id']
        for f in f_to_check:
            if vals.get(f, False):
                self._check_line_conditions(cr, uid, ids, context=context)
                break

        return result

    def confirmLine(self, cr, uid, ids, context=None, run_scheduler=False):
        """
        Set the line as confirmed and check if all lines
        of the FO/IR are confirmed. If yes, launch the
        confirmation of the FO/IR in background.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line to check
        :param run_scheduler: If set to True, after all FO/IR are confirmed,
                              run the Auto POs creation scheduler
        :param context: Context of the call

        :return Raise an error or True
        :rtype boolean
        """
        # Objects
        order_obj = self.pool.get('sale.order')
        po_auto_obj = self.pool.get('po.automation.config')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        context['procurement_request'] = True
        no_prod = self.search(cr, uid, [
            ('id', 'in', ids),
            ('product_id', '=', False),
            ('order_id.procurement_request', '=', False)
        ], count=True, context=context)

        if no_prod:
            raise osv.except_osv(_('Warning'), _("""The product must be chosen before sourcing the line.
                Please select it within the lines of the associated Field Order (through the "Field Orders" menu).
                """))

        loan_stock = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_order'),
            ('order_id.state', '!=', 'draft'),
            ('order_id.order_type', '=', 'loan'),
        ], count=True, context=context)

        if loan_stock:
            raise osv.except_osv(_('Warning'), _("""You can't source a loan 'from stock'."""))

        mto_no_cft_no_sup = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_order'),
            ('po_cft', 'not in', ['cft']),
            ('supplier', '=', False),
        ], count=True, context=context)

        if mto_no_cft_no_sup:
            raise osv.except_osv(_('Warning'), _("The supplier must be chosen before sourcing the line"))

        mto_no_cft_no_prod = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_order'),
            ('po_cft', 'not in', ['cft']),
            ('supplier', '!=', False),
            ('product_id', '=', False),
            ('order_id.procurement_request', '=', True),
            ('supplier.partner_type', 'not in', ['internal', 'section', 'intermission']),
        ], count=True, context=context)

        if mto_no_cft_no_prod:
            raise osv.except_osv(_('Warning'), _("""For an Internal Request with a procurement method 'On Order' and without product,
                    the supplier must be either in 'Internal', 'Inter-Section' or 'Intermission' type.
                    """))

        stock_no_loc = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_stock'),
            ('location_id', '=', False),
        ], count=True, context=context)

        if stock_no_loc:
            raise osv.except_osv(
                _('Warning'),
                _('A location must be chosen before sourcing the line.'),
            )
        # US_376: If order type is loan, we accept unit price as zero
        no_price_ids = self.search(cr, uid, [
           ('id', 'in', ids),
           ('price_unit', '=', 0.00),
           ('order_id.order_type', 'not in', ['loan', 'donation_st', 'donation_exp']),
           ('order_id.procurement_request', '=', False),
        ], limit=1, context=context)

        if no_price_ids:
            raise osv.except_osv(
                _('Warning'),
                _('You cannot confirm the sourcing of a line with unit price as zero.'),
            )

        int_int_supplier = self.search(cr, uid, [
            ('id', 'in', ids),
            ('supplier.partner_type', '=', 'internal'),
            ('order_id.partner_type', '=', 'internal'),
            ('order_id.procurement_request', '=', False),
        ], count=True, context=context)
        if int_int_supplier:
            raise osv.except_osv(
                _('Warning'),
                _('You cannot confirm the sourcing of a line to an internal customer with an internal supplier.'),
            )

        if not run_scheduler:
            run_scheduler = po_auto_obj.get_po_automation(cr, uid, context=context)

        self.check_confirm_order(cr, uid, ids, run_scheduler=run_scheduler, context=context)

        return True

    def check_confirm_order(self, cr, uid, ids, run_scheduler=False, context=None):
        """
        Run the confirmation of the FO/IR if all lines are confirmed
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of sale.order.line to check
        :param run_scheduler: If set to True, after all FO/IR are confirmed,
                              run the Auto POs creation scheduler
        :praam context: Context of the call
        """
        # Objects
        order_obj = self.pool.get('sale.order')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        order_to_check = {}
        for line in self.read(cr, uid, ids, ['order_id', 'estimated_delivery_date', 'price_unit', 'product_uom_qty'], context=context):
            order_data = order_obj.read(cr, uid, line['order_id'][0], ['procurement_request', 'order_type', 'state'], context=context)
            order_proc = order_data['procurement_request']
            order_type = order_data['order_type']
            if order_data['state'] != 'validated':
                continue
            state_to_use = order_proc and 'confirmed' or 'sourced'
            self.write(cr, uid, [line['id']], {
                'state': state_to_use,
                'cf_estimated_delivery_date': line['estimated_delivery_date'],
            }, context=context)
            if line['order_id'][0] not in order_to_check:
                order_to_check.update({line['order_id'][0]: state_to_use})

            if order_type == 'regular' and not order_proc and line['price_unit'] * line['product_uom_qty'] < 0.01:
                raise osv.except_osv(
                    _('Warning'),
                    _('You cannot confirm the sourcing of a line with a subtotal of zero.'),
                )

        order_to_process = {}
        for order_id, state_to_use in order_to_check.iteritems():
            lines_not_confirmed = self.search(cr, uid, [
                ('order_id', '=', order_id),
                ('state', '!=', state_to_use),
            ], count=True, context=context)

            if lines_not_confirmed:
                pass
            else:
                order_to_process.setdefault(state_to_use, [])
                order_to_process[state_to_use].append(order_id)

        for state_to_use, val in order_to_process.iteritems():
            queue = deque(val)
            while queue:
                i = 0
                order_ids = []
                # We create 20 threads (so if there are 15 order to process,
                # we will create 15 threads (1 per order), but if there are 50
                # order to process, we will create 20 threads (1 per 2/3 orders)
                while i < (len(order_to_check)/20 or 1) and queue:
                    i +=1
                    order_id = queue.popleft()
                    order_ids.append(order_id)

                    # Create the sourcing process object
                    self.pool.get('sale.order.sourcing.progress').create(cr, uid, {
                        'order_id': order_id,
                        'start_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    }, context=context)

                self.pool.get('sale.order').write(cr, uid, order_ids, {
                    'sourcing_trace_ok': True,
                    'sourcing_trace': 'Sourcing in progress',
                }, context=context)

                for order_id in order_ids:
                    self.infolog(cr, uid, "All lines of the FO/IR id:%s have been sourced" % order_id)
                thread = threading.Thread(
                    target=self.confirmOrder,
                    args=(cr, uid, order_ids, state_to_use, run_scheduler, context)
                )
                thread.start()

        return True

    def confirmOrder(self, cr, uid, order_ids, state_to_use, run_scheduler=False,
                     context=None, new_cursor=True):
        """
        Confirm the order specified in the parameter.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param order_id: List of ID of the orders to confirm
        :param state_to_use: Determine if the order is an IR or a FO
        :param run_scheduler: If set to True, after all FO/IR are confirmed,
                              run the Auto POs creation scheduler
        :param context: Context of the call
        :param new_cursor: Use a new DB cursor or not

        :return Raise an error or True
        :rtype boolean
        """
        if not context:
            context = {}
        wiz_obj = self.pool.get('procurement.purchase.compute.all')
        wf_service = netsvc.LocalService("workflow")

        if new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()

        for order_id in order_ids:
            try:
                if state_to_use == 'confirmed':
                    wf_service.trg_validate(uid, 'sale.order', order_id, 'procurement_confirm', cr)
                else:
                    wf_service.trg_validate(uid, 'sale.order', order_id, 'order_confirm', cr)
                self.pool.get('sale.order').write(cr, uid, [order_id],
                                                  {'sourcing_trace_ok': False,
                                                   'sourcing_trace': ''}, context=context)
                prog_ids = self.pool.get('sale.order.sourcing.progress').search(cr, uid, [
                    ('order_id', '=', order_id),
                ], context=context)
                self.pool.get('sale.order.sourcing.progress').write(cr, uid, prog_ids, {
                    'end_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                }, context=context)
            except osv.except_osv, e:
                cr.rollback()
                self.pool.get('sale.order').write(cr, uid, order_id,
                                                  {'sourcing_trace_ok': True,
                                                   'sourcing_trace': e.value}, context=context)
                prog_ids = self.pool.get('sale.order.sourcing.progress').search(cr, uid, [
                    ('order_id', '=', order_id),
                ], context=context)
                self.pool.get('sale.order.sourcing.progress').write(cr, uid, prog_ids, {
                    'error': e.value,
                }, context=context)
            except Exception, e:
                cr.rollback()
                self.pool.get('sale.order').write(cr, uid, order_id,
                                                  {'sourcing_trace_ok': True,
                                                   'sourcing_trace': misc.ustr(e)}, context=context)
                prog_ids = self.pool.get('sale.order.sourcing.progress').search(cr, uid, [
                    ('order_id', '=', order_id),
                ], context=context)
                self.pool.get('sale.order.sourcing.progress').write(cr, uid, prog_ids, {
                    'error': misc.ustr(e),
                }, context=context)

        if run_scheduler:
            # Run Auto POs creation scheduler
            wiz_id = wiz_obj.create(cr, uid, {}, context=context)
            wiz_obj.procure_calculation_purchase(cr, uid, wiz_id, context=context)

        if new_cursor:
            cr.commit()
            cr.close(True)

        return True

    def unconfirmLine(self, cr, uid, ids, context=None):
        """
        Set the line as draft.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line to unconfirm
        :param context: Context of the call

        :return True if all is ok or False
        :rtype boolean
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    """
    Controller methods
    """
    def onChangeLocation(self, cr, uid, ids, location_id, product_id, rts, sale_order_id):
        """
        When the location is changed on line, re-compute the stock
        quantity values for the line.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line on which the
                     modifications will be done.
        :param location_id: ID of the current or new value for the stock location of the line
        :param product_id: ID of the current or new value for the product of the line
        :param rts: Current or new value for the Ready to ship date of the line
        :param sale_order_id: ID of the current or new value for the order of the line

        :return A dictionary with the new values
        :rtype dict
        """
        # Objects
        product_obj = self.pool.get('product.product')
        order_obj = self.pool.get('sale.order')

        res = {'value': {}}

        if not location_id or not product_id:
            return res

        if sale_order_id:
            so = order_obj.browse(cr, uid, sale_order_id)
            if so.procurement_request and so.location_requestor_id.id == location_id:
                return {
                    'value': {
                        'location_id': False,
                        'real_stock': 0.00,
                        'virtual_stock': 0.00,
                        'available_stock': 0.00,
                    },
                    'warning': {
                        'title': _('Warning'),
                        'message': _('You cannot choose a source location which is the destination location of the Internal request'),
                    },
                }

        rts = rts < time.strftime('%Y-%m-%d') and time.strftime('%Y-%m-%d') or rts
        ctx = {
            'location': location_id,
            'to_date': '%s 23:59:59' % rts,
        }

        product = product_obj.browse(cr, uid, product_id, context=ctx)
        res['value'].update({
            'real_stock': product.qty_available,
            'virtual_stock': product.virtual_available,
        })

        ctx2 = {
            'states': ('assigned',),
            'what': ('out',),
            'location': location_id,
        }
        product2 = product_obj.get_product_available(cr, uid, [product_id], context=ctx2)
        res['value']['available_stock'] = res['value']['real_stock'] + product2.get(product_id, 0.00)

        return res

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
                          uom=False, qty_uos=0, uos=False, name='', partner_id=False,
                          lang=False, update_tax=True, date_order=False, packaging=False,
                          fiscal_position=False, flag=False):
        """
        When the product is changed on the line, looking for the
        best supplier for the new product.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line on which the
                     modifications will be done.
        :param pricelist: ID of the pricelist of the FO. Used to compute the good price.
        :param product: ID of the current or new product of the line.
        :param qty: Quantity of product on the line
        :param uom: ID of the UoM on the line
        :param qty_uos: Quantity of product on the line in UoS
        :param uos: ID of the UoS on the line
        :param name: Name of the line
        :param partner_id: ID of the partner of the order
        :param lang: Lang of the partner of the ordre
        :param update_tax: Is the modification of product must change the taxes
        :param date_order: Date of the order
        :param packaging: Packaging of the product
        :param fiscal_position: Fiscal position of the partner of the order (used to compute taxes)
        :param flag: ???

        :return A dictionary with the new values
        :rtype dict
        """
        # Objects
        product_obj = self.pool.get('product.product')

        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
                                                                uom, qty_uos, uos, name, partner_id,
                                                                lang, update_tax, date_order, packaging, fiscal_position, flag)

        # Add supplier
        sellerId = False
        po_cft = False
        l_type = 'type' in result['value'] and result['value']['type']

        line = None
        if ids:
            line = self.browse(cr, uid, ids[0])

        if product and type:
            seller = product_obj.browse(cr, uid, product).seller_id
            sellerId = (seller and seller.id) or False

            if l_type == 'make_to_order':
                po_cft = 'po'
                if line and line.product_id and line.product_id.type in ('service', 'service_recep') and line.order_id and not line.order_id.procurement_request:
                    po_cft = 'dpo'

            result['value'].update({
                'supplier': sellerId,
                'po_cft': po_cft,
            })

        return result

    def onChangePoCft(self, cr, uid, line_id, po_cft, order_id=False, partner_id=False, context=None):
        """
        When the method of procurement for Make To Order lines is changed, check if the new
        values are compatible with the other values of the line and of the order.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line_id: ID of the line to check
        :param po_cft: Value of the procurement method
        :param order_id: ID of the order of the line
        :param partner_id: ID of the partner of the order
        :param context: Context of the change

        :return A dictionary with the new values
        :rtype dict
        """
        # Objects
        order_obj = self.pool.get('sale.order')
        product_obj = self.pool.get('product.product')

        warning = {}
        value = {}

        if order_id:
            order = order_obj.browse(cr, uid, order_id, context=context)
            if order.procurement_request and po_cft == 'dpo':
                warning = {
                    'title': _('DPO for IR'),
                    'message': _('You cannot choose Direct Purchase Order as method to source an Internal Request line.'),
                }
                value['po_cft'] = 'po'
            if po_cft == 'cft':
                # Tender does not allow supplier selection
                value['supplier'] = False

        if line_id and isinstance(line_id, list):
            line_id = line_id[0]

        res = {'value': value, 'warning': warning}

        line = self.browse(cr, uid, line_id, context=context)

        if line.product_id.type in ('service', 'service_recep') and not line.order_id.procurement_request and po_cft == 'po':
            res['warning'] = {
                'title': _('Warning'),
                'message': _("""'Purchase Order' is not allowed to source a 'Service' product."""),
            }
            res['value'].update({'po_cft': 'dpo'})

        partner_id = 'supplier' in value and value['supplier'] or partner_id
        if line_id and partner_id and line.product_id:
            check_fnct = product_obj._on_change_restriction_error
            res, error = self._check_product_constraints(
                cr,
                uid,
                line.type,
                value.get('po_cft', line.po_cft),
                line.product_id.id,
                partner_id,
                check_fnct,
                field_name='po_cft',
                values=res,
                vals={'partner_id': partner_id},
                context=context,
            )

            if error:
                return res

        return res

    def onChangeType(self, cr, uid, line_id, l_type, location_id=False, supplier=False, context=None):
        """
        When the method of procurement is changed, check if the new
        values are compatible with the other values of the line and of the order.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line_id: ID of the line to check
        :param l_type: Value of the procurement method
        :param location_id: ID of the stock location of the line
        :param supplier: Id of the res.partner selected as partner for the line
        :param context: Context of the change

        :return A dictionary with the new values
        :rtype dict
        """
        # Objects
        wh_obj = self.pool.get('stock.warehouse')
        product_obj = self.pool.get('product.product')

        if not context:
            context = {}

        if line_id and isinstance(line_id, list):
            line_id = line_id[0]

        value = {}
        message = {}

        if line_id:
            line = self.browse(cr, uid, line_id, context=context)
            if line.product_id.type in ('consu', 'service', 'service_recep') and l_type == 'make_to_stock':
                product_type = line.product_id.type == 'consu' and 'non stockable' or 'service'
                value['type'] = 'make_to_order'
                message.update({
                    'title': _('Warning'),
                    'message': _('You cannot choose \'from stock\' as method to source a %s product !') % product_type,
                })

        if l_type == 'make_to_stock':
            if not location_id:
                wh_ids = wh_obj.search(cr, uid, [], context=context)
                if wh_ids:
                    value['location_id'] = wh_obj.browse(cr, uid, wh_ids[0], context=context).lot_stock_id.id

            value.update({
                'po_cft': False,
                'related_sourcing_ok': False,
                'related_sourcing_id': False,
            })

            res = {'value': value, 'warning': message}
            if line_id:
                line = self.browse(cr, uid, line_id, context=context)
                check_fnct = product_obj._on_change_restriction_error
                if line.product_id:
                    res, error = self._check_product_constraints(
                        cr,
                        uid,
                        l_type,
                        line.po_cft,
                        line.product_id.id,
                        False,
                        check_fnct,
                        field_name='l_type',
                        values=res,
                        vals={'constraints': ['storage']},
                        context=context,
                    )

                    if error:
                        return res
        else:
            related_sourcing_ok = self._check_related_sourcing_ok(cr, uid, supplier, l_type, context=context)
            value['related_sourcing_ok'] = related_sourcing_ok
            if not related_sourcing_ok:
                value['related_sourcing_id'] = False

        return {'value': value, 'warning': message}

    def onChangeSupplier(self, cr, uid, line_id, supplier, l_type, context=None):
        """
        When the supplier is changed, check if the new values are compatible
        with the other values of the line and of the order.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param line_id: ID of the line to check
        :param supplier: ID of the current or new choosen supplier
        :param l_type: Mode of procurement for the line
        :param context: Context of the change

        :return A dictionary with the new values
        :rtype dict
        """
        # Objects
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if line_id and isinstance(line_id, list):
            line_id = line_id[0]

        result = {
            'value': {},
            'domain': {},
        }

        if not supplier:
            result['value'].update({
                'related_sourcing_id': False,
                'related_sourcing_ok': False,
            })
            sl = self.browse(cr, uid, line_id, context=context)
            if not sl.product_id and sl.order_id.procurement_request and sl.type == 'make_to_order':
                result['domain']['supplier'] = [('partner_type', 'in', ['internal', 'section', 'intermission'])]
            return result

        partner = partner_obj.browse(cr, uid, supplier, context)

        # Check if the partner has addresses
        if not partner.address:
            result['warning'] = {
                'title': _('Warning'),
                'message': _('The chosen partner has no address. Please define an address before continuing.'),
            }

        # If the selected partner belongs to product->suppliers, we take that delay (from supplierinfo)
        line = self.browse(cr, uid, line_id, context=context)
        delay = self.check_supplierinfo(line, partner, context=context)

        estDeliveryDate = date.today() + relativedelta(days=int(delay))

        related_sourcing_ok = self._check_related_sourcing_ok(cr, uid, supplier, l_type, context=context)
        result['value'].update({
            'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d'),
            'related_sourcing_ok': related_sourcing_ok,
        })
        if not related_sourcing_ok:
            result['value']['related_sourcing_id'] = False

        value = result['value']
        partner_id = 'supplier' in value and value['supplier'] or supplier
        if line_id and partner_id and line.product_id:
            check_fnct = product_obj._on_change_restriction_error
            result, error = self._check_product_constraints(
                cr,
                uid,
                line.type,
                value.get('po_cft', line.po_cft),
                line.product_id.id,
                partner_id,
                check_fnct,
                field_name='supplier',
                values=result,
                vals={'partner_id': partner_id},
                context=context,
            )

            if error:
                return result

        return result

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None,
        context=None, orderby=False):
        res = super(sale_order_line, self).read_group(cr, uid, domain, fields,
            groupby, offset=offset, limit=limit, context=context,
            orderby=orderby)

        if 'line_number' in fields:
            """
            UFTP-346 'order sourcing tool search view'
            (and all SO line search views with line_number field)
            replace the sum of 'line_number' by count of so lines
            """
            for g in res:
                # for each group line, compute so lines count by domain,
                # then replace sum('line_number') value by the count
                if '__domain' in g:
                    # aware to manage all group levels chain with __domain
                    line_count = self.search(cr, uid, g.get('__domain', []),
                        context={}, count=True)  # search with 'new' context
                    g['line_number'] = line_count
        return res

sale_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
