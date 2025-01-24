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

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import threading
import time
import logging

import netsvc
from osv import osv, fields
from osv.orm import browse_record
import pooler
from tools import misc
from tools.translate import _
from tools.safe_eval import safe_eval
from tools import DEFAULT_SERVER_DATE_FORMAT
from collections import deque

import decimal_precision as dp
from order_types import ORDER_PRIORITY
from order_types import ORDER_CATEGORY
from sale import SALE_ORDER_STATE_SELECTION

_SELECTION_PO_CFT = [
    ('po', 'Purchase Order'),
    ('dpo', 'Direct Purchase Order'),
    ('cft', 'Tender'),
    ('rfq', 'Request for Quotation'),
    ('pli', 'Purchase List'),
]


def check_is_service_nomen(obj, cr, uid, nomen=False):
    """
    Return True if the nomenclature seleced on the line is a service nomenclature
    @param cr: Cursor to the database
    @param uid: ID of the res.users that calls this method
    @param nomen: ID of the nomenclature to check
    @return: True or False
    """
    nomen_obj = obj.pool.get('product.nomenclature')

    if not nomen:
        return False

    nomen_srv = nomen_obj.search(cr, uid, [
        ('name', '=', 'SRV'),
        ('type', '=', 'mandatory'),
        ('level', '=', 0),
    ], limit=1)
    if not nomen_srv:
        return False

    return nomen_srv[0] == nomen


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'

    _replace_exported_fields = {
        'product_id': [
            (['product_code', 'Product Code'], 10),
            (['product_name', 'Product Description'], 20),
        ],
    }


    def _where_calc(self, cr, uid, domain, active_test=True, context=None):
        '''
            overwrite to speed up OST search on fields categ, priority, order state
        '''

        new_dom = []

        fields_filter = {
            'categ': {'db_field': 'categ'},
            'priority': {'db_field': 'priority'},
            'sale_order_state': {'db_field': 'state'},
        }
        has_filter = False

        operator = ['=', '!=']

        for x in domain:
            if x[0]  in fields_filter:
                if x[1] not in operator:
                    raise osv.except_osv(_('Warning'), _('Operator %s not allowed on %s') % (x[1], x[0]))
                fields_filter[x[0]].update({'operator': x[1], 'filter': x[2]})
                has_filter = True
            else:
                # US-7407: OST custom filter: change done (db value) vs Closed (user value)
                if x[0] == 'state' and x[2] and isinstance(x[2], str) and x[2].lower() == 'closed':
                    x = ('state', x[1], 'done')
                new_dom.append(x)
        ret = super(sale_order_line, self)._where_calc(cr, uid, new_dom, active_test=active_test, context=context)
        if has_filter:
            ret.tables.append('"sale_order"')
            ret.joins['"sale_order_line"'] = [('"sale_order"', 'order_id', 'id', 'LEFT JOIN')]
            for field in fields_filter:
                if fields_filter[field].get('operator'):
                    ret.where_clause.append(' "sale_order"."' + fields_filter[field]['db_field'] + '" ' + fields_filter[field]['operator'] + ' %s ')
                    ret.where_clause_params.append(fields_filter[field]['filter'])

        return ret

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
    def _get_fake(self, cr, uid, ids, field_name, args, context=None):
        """
        Returns False for each ID.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of ID of field order lines to re-compute
        :param field_name: A field or a list of fields to be computed
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

        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            values = {
                'priority': line.order_id.priority,
                'categ': line.order_id.categ,
                'rts': line.order_id.ready_to_ship_date,
                'procurement_request': line.order_id.procurement_request,
                'loan_type': line.order_id.order_type in ['loan', 'loan_return'],
                'estimated_delivery_date': self._get_date(cr, uid, line, context=context),
                'display_confirm_button': line.state == 'validated',
                'sale_order_in_progress': line.order_id.sourcing_trace_ok,
                'sale_order_state': self._get_sale_order_state(cr, uid, line.order_id, context=context),
                'supplier_type': line.supplier and line.supplier.partner_type or False,
                'supplier_split_po': line.supplier and line.supplier.split_po or False,
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

        if isinstance(ids, int):
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

        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._check_related_sourcing_ok(cr, uid, line.supplier.id, line.type, context=context)

        return res

    _columns = {
        'customer': fields.related('order_id', 'partner_id', string='Customer', readonly=True),
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
        'supplier_type': fields.function(
            _get_line_values,
            method=True,
            string='Supplier Type',
            type='char',
            readonly=True,
            store=False,
            multi='line_info',
        ),
        'supplier_split_po': fields.function(
            _get_line_values,
            method=True,
            string='Supplier can Split POs',
            type='char',
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
            string='Calculated DD',
            store=False,
            readonly=True,
            multi='line_info',
        ),
        'sourcing_date': fields.date(
            string='Date of Sourcing',
            readonly=True,
        ),
        'display_confirm_button': fields.function(
            _get_line_values,
            method=True,
            type='boolean',
            string='Display Button',
            multi='line_info',
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
            related_uom='product_uom',
        ),
        'virtual_stock': fields.function(
            _getVirtualStock, method=True,
            type='float',
            string='Virtual Stock',
            digits_compute=dp.get_precision('Product UoM'),
            readonly=True,
            related_uom='product_uom',
            multi='stock_qty',
        ),
        'available_stock': fields.function(
            _getAvailableStock,
            method=True,
            type='float',
            string='Available Stock',
            digits_compute=dp.get_precision('Product UoM'),
            related_uom='product_uom',
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
            write_relate=False,
        ),
        'product_name': fields.related(
            'product_id',
            'name',
            type='char',
            size=128,
            string='Product description',
            store=False,
            write_relate=False,
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

        if isinstance(ids, int):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if (obj.product_id.type == 'service_recep' or (not obj.product_id and check_is_service_nomen(cr, uid, obj.nomen_manda_0.id))) \
               and obj.type != 'make_to_order':
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
    def default_get(self, cr, uid, fields_list, context=None, from_web=False):
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

        res = super(sale_order_line, self).default_get(cr, uid, fields_list, context=context, from_web=from_web)

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
            order = order_obj.read(cr, uid, vals['order_id'],
                                   ['procurement_request', 'partner_type', 'state',
                                    'order_type'],
                                   context=context)
            ir = order['procurement_request']
            order_p_type = order['partner_type']
            if order['order_type'] in ('loan', 'loan_return', 'donation_exp', 'donation_st') and order['state'] == 'validated':
                vals.update({
                    'type': 'make_to_stock',
                    'po_cft': False,
                    'supplier': False,
                })
                if order['order_type'] in ['loan', 'loan_return']:
                    vals['related_sourcing_id'] = False

        if product:
            if vals.get('type', False) == 'make_to_order' and not vals.get('supplier', False):
                vals['supplier'] = product.seller_id and (product.seller_id.supplier or product.seller_id.manufacturer or
                                                          product.seller_id.transporter) and product.seller_id.id or False
            if product.type in ('consu', 'service', 'service_recep'):
                vals['type'] = 'make_to_order'

            if product.type in ('service', 'service_recep'):
                if ir and vals.get('po_cft', 'dpo') == 'dpo':
                    vals['po_cft'] = 'po'
                elif not ir and vals.get('po_cft', 'po') == 'po':
                    vals['po_cft'] = 'dpo'
            elif product.state.code == 'forbidden':
                vals['type'] = 'make_to_stock'

        if not product:
            vals.update({
                'type': 'make_to_order',
                'po_cft': 'po',
            })
            if not ir and vals.get('nomen_manda_0') and check_is_service_nomen(self, cr, uid, vals.get('nomen_manda_0')):
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

        if 'supplier' in vals and not vals.get('supplier'):
            vals['related_sourcing_id'] = False

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

        if isinstance(line_ids, int):
            line_ids = [line_ids]

        for line in self.browse(cr, uid, line_ids, context=context):
            if line.type == 'make_to_order' and line.product_id and line.product_id.seller_id and \
                    (line.product_id.seller_id.supplier or line.product_id.seller_id.manufacturer
                     or line.product_id.seller_id.transporter):
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
        o_state = line.state not in ('draft', 'confirmed', 'done')
        ctx_cond = not context.get('fromOrderLine')
        o_type = line.order_id and line.order_id.order_type in ['loan', 'loan_return', 'donation_st', 'donation_exp'] or False

        if l_type and o_state and ctx_cond and o_type:
            return _('You can\'t source a %s \'on order\'.') % (line.order_id.order_type in ['loan', 'loan_return'] and _('loan') or _('donation'))

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

        if isinstance(ids, int):
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

            if line.product_id and line.po_cft == 'pli' and line.supplier.partner_type != 'external':
                raise osv.except_osv(
                    _('Warning'),
                    _("""You can't source with 'Purchase List' to a non-external partner."""),
                )

            if line.order_id.state == 'validated' and line.order_id.order_type in (
                    'donation_st', 'donation_exp') and line.type != 'make_to_stock':
                raise osv.except_osv(
                    _('Warning'),
                    _("""You can only source a Donation line from stock.""")
                )

            cond1 = not line.order_id.procurement_request and line.po_cft in ['po', 'pli']
            cond2 = line.product_id and line.product_id.type == 'service_recep'
            cond3 = not line.product_id and check_is_service_nomen(self, cr, uid, line.nomen_manda_0.id)
            if cond1 and (cond2 or cond3):
                raise osv.except_osv(
                    _('Warning'),
                    _("""'Purchase Order' and 'Purchase List' are not allowed to source a 'Service' product."""),
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

            if line.state not in ('draft', 'cancel') and line.product_id and line.supplier and not context.get('bypass_product_constraints'):
                sourcing_not_donation = context.get('multiple_sourcing', False) and \
                                        line.order_id.order_type not in ['donation_prog', 'donation_exp', 'donation_st'] or False
                # Check product constraints (no external supply, no storage...)
                check_fnct = product_obj._get_restriction_error
                self._check_product_constraints(cr, uid, line.type, line.po_cft, line.product_id.id, line.supplier.id,
                                                sourcing_not_donation, check_fnct, context=context)

        return True

    def _check_product_constraints(self, cr, uid, line_type='make_to_order', po_cft='po', product_id=False,
                                   partner_id=False, sourcing_not_donation=False, check_fnct=False, *args, **kwargs):
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

        vals = {'obj_type': 'sale.order', 'sourcing_not_donation': sourcing_not_donation}
        if line_type == 'make_to_order' and product_id and (po_cft == 'cft' or partner_id):
            if po_cft == 'cft':
                vals['constraints'] = ['external']
        elif line_type == 'make_to_stock' and product_id:
            vals['constraints'] = ['storage']

        if partner_id:
            vals['partner_id'] = partner_id

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
        if not ids:
            return True
        # Objects
        product_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')

        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        product = False

        srv_product = False
        if vals.get('product_id', False):
            product = product_obj.browse(cr, uid, vals['product_id'])
            if product.type in ('consu', 'service', 'service_recep'):
                srv_product = True
        elif not context.get('procurement_request', False) and vals.get('nomen_manda_0') and \
                check_is_service_nomen(self, cr, uid, vals.get('nomen_manda_0')):
            srv_product = True

        if srv_product:
            vals.update({
                'type': 'make_to_order',
                'po_cft': 'dpo',
            })

        if 'state' in vals and vals['state'] == 'cancel':
            context.update({'noraise': True})
            self.write(cr, uid, ids, {'cf_estimated_delivery_date': False}, context=context)

        if 'type' in vals:
            if vals['type'] == 'make_to_stock':
                vals.update({
                    'po_cft': False,
                    'supplier': False,
                    'related_sourcing_id': False,
                })

        # Search lines to modified with loan or donation values
        loan_sol_ids = self.search(cr, uid, [('order_id.order_type', 'in', ['loan', 'loan_return', 'donation_st', 'donation_exp']),
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

        if vals.get('type') == 'make_to_stock':
            vals['related_sourcing_id'] = False
        elif vals.get('supplier'):
            related_sourcing_ok = self._check_related_sourcing_ok(cr, uid, vals.get('supplier'), vals.get('type'), context=context)
            if not related_sourcing_ok:
                vals['related_sourcing_id'] = False

        if ('supplier' in vals and not vals.get('supplier')) or ('po_cft' in vals and vals.get('po_cft') in ('cft', 'rfq')):
            vals['related_sourcing_id'] = False

        # Remove supplier if the selected PO/CFT is Tender
        if vals.get('po_cft') == 'cft':
            vals['supplier'] = False

        # UFTP-139: if make_to_stock and no location, put Stock as location
        if ids and 'type' in vals and vals.get('type', False) == 'make_to_stock' and not vals.get('location_id', False):
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
                ids_to_check = self.search(cr, uid, [('id', 'in', ids), ('state', 'in', ['draft', 'validated'])], context=context)
                if ids_to_check:
                    self._check_line_conditions(cr, uid, ids_to_check, context=context)
                break

        return result

    def confirmLine(self, cr, uid, ids, context=None):
        """
        Set the line as confirmed and check if all lines
        of the FO/IR are confirmed. If yes, launch the
        confirmation of the FO/IR in background.

        :param cr: Cursor to the database
        :param uid: ID of the user that runs the method
        :param ids: List of IDs of sale.order.line to check
        :param context: Context of the call

        :return Raise an error or True
        :rtype boolean
        """
        # Objects
        data_obj = self.pool.get('ir.model.data')
        product_obj = self.pool.get('product.product')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        context['procurement_request'] = True
        no_prod = self.search(cr, uid, [
            ('id', 'in', ids),
            ('product_id', '=', False),
            ('order_id.procurement_request', '=', False),
            ('supplier.partner_type', 'not in', ['esc', 'external']),
        ], count=True, context=context)

        if no_prod:
            raise osv.except_osv(_('Warning'), _("""The product must be chosen before sourcing the line.
                Please select it within the lines of the associated Field Order (through the "Field Orders" menu).
                """))

        temp_status = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_5')[1]
        temp_products = product_obj.search(cr, uid, [('international_status', '=', temp_status)], context=context)
        if temp_products:
            # checking for temporary products :
            line_ids = self.search(cr, uid, [('id', 'in', ids), ('product_id', 'in', temp_products),], context=context)
            err_msg = []
            for l in self.browse(cr, uid, line_ids, context=context):
                err_msg.append(_('Line %s of the order %s') % (l.line_number, l.order_id.name))

            if err_msg:
                raise osv.except_osv(_('Warning'), _("You can not source lines with Temporary products. Details: \n %s") % '\n'.join(msg for msg in err_msg))

        loan_stock = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_order'),
            ('order_id.state', '!=', 'draft'),
            ('order_id.order_type', 'in', ['loan', 'loan_return']),
        ], count=True, context=context)

        if loan_stock:
            raise osv.except_osv(_('Warning'), _("""You can't source a loan 'on order'."""))

        donation_stock = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_order'),
            ('order_id.state', '!=', 'draft'),
            ('order_id.order_type', 'in', ['donation_st', 'donation_exp']),
        ], count=True, context=context)

        if donation_stock:
            raise osv.except_osv(_('Warning'), _("""You can't source a donation 'on order'."""))

        mto_no_cft_no_sup = self.search(cr, uid, [
            ('id', 'in', ids),
            ('type', '=', 'make_to_order'),
            ('po_cft', 'not in', ['cft']),
            ('supplier', '=', False),
        ], count=True, context=context)

        if mto_no_cft_no_sup:
            raise osv.except_osv(_('Warning'), _("The supplier must be chosen before sourcing the line"))

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
            ('order_id.order_type', 'not in', ['loan', 'loan_return', 'donation_st', 'donation_exp']),
            ('order_id.procurement_request', '=', False),
        ], limit=1, context=context)

        if no_price_ids:
            raise osv.except_osv(
                _('Warning'),
                _('You cannot confirm the sourcing of a line with unit price as zero.'),
            )

        if ids:
            cr.execute('''
                select
                    count(*)
                from
                    sale_order_line sol, sale_order so, res_partner p, res_partner supplier
                where
                    sol.order_id = so.id and
                    p.id = so.partner_id and
                    supplier.id = sol.supplier and
                    p.partner_type in ('section', 'internal', 'intermission') and
                    supplier.partner_type in ('section', 'internal', 'intermission') and
                    coalesce(sol.original_instance, p.name) != p.name and
                    sol.id in %s
                ''',  (tuple(ids), ))

            if cr.fetchone()[0]:
                raise osv.except_osv(
                    _('Warning'),
                    _('You cannot re-sync a line more than 2 times')
                )

        self.source_line(cr, uid, ids, context=context)

        return True


    def get_existing_po(self, cr, uid, ids, context=None):
        """
        Do we have to create new PO/DPO or use an existing one ?
        If an existing one can be used, then returns his ID, otherwise returns False
        @return ID (int) of document to use or False
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res_id = False
        for sourcing_line in self.browse(cr, uid, ids, context=context):
            # common domain:
            domain = [
                ('partner_id', '=', sourcing_line.supplier.id),
                ('state', 'in', ['draft']),
                ('related_sourcing_id', '=', sourcing_line.related_sourcing_id.id or False), # Column "Group"
                ('delivery_requested_date', '=', sourcing_line.date_planned),
                ('rfq_ok', '=', False),
            ]
            if sourcing_line.po_cft in ('po', 'cft'):
                domain.append(('order_type', '=', 'regular'))
            elif sourcing_line.po_cft == 'rfq':
                domain.append(('order_type', '=', 'regular'))
                domain.append(('rfq_ok', '=', True))
            elif sourcing_line.po_cft == 'dpo':
                domain.append(('order_type', '=', 'direct'))
                domain.append(('dest_address_id', '=', sourcing_line.order_id.partner_shipping_id.id))
            elif sourcing_line.po_cft == 'pli':
                domain.append(('order_type', '=', 'purchase_list'))

            # supplier's order creation mode:
            if sourcing_line.supplier.po_by_project in ('project', 'category_project') or (sourcing_line.po_cft == 'dpo' and sourcing_line.supplier.po_by_project == 'all'):
                domain.append(('customer_id', '=', sourcing_line.order_id.partner_id.id))
            if sourcing_line.supplier.po_by_project == 'isolated': # Isolated requirements => One PO for one IR/FO:
                domain.append(('unique_fo_id', '=', sourcing_line.order_id.id))
            if sourcing_line.supplier.po_by_project in ('category_project', 'category'): # Category requirements => Search a PO with the same category than the IR/FO category
                domain.append(('categ', '=', sourcing_line.order_id.categ))

            res_id = self.pool.get('purchase.order').search(cr, uid, domain, context=context)

        if res_id and isinstance(res_id, list):
            res_id = res_id[0]

        return res_id or False


    def get_existing_rfq(self, cr, uid, ids, context=None):
        """
        Do we have to create new RfQ or use an existing one ?
        If an existing one can be used, then returns his ID, otherwise returns False
        @return ID (int) of document to use or False
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res_id = False
        for sourcing_line in self.browse(cr, uid, ids, context=context):
            # common domain:
            domain = [
                ('partner_id', '=', sourcing_line.supplier.id),
                ('rfq_state', 'in', ['draft']),
                ('delivery_requested_date', '=', sourcing_line.date_planned),
                ('rfq_ok', '=', True),
                ('order_type', '=', 'regular'),
            ]
            res_id = self.pool.get('purchase.order').search(cr, uid, domain, context=context)

        if res_id and isinstance(res_id, list):
            res_id = res_id[0]

        return res_id or False


    def get_existing_po_loan_for_goods_return(self, cr, uid, ids, context=None):
        """
        Do we have to create new PO or use an existing one ?
        If an existing one can be used, then returns his ID, otherwise returns False
        @return ID (int) of document to use or False
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res_id = False
        for sourcing_line in self.browse(cr, uid, ids, context=context):
            # common domain:
            domain = [
                ('partner_id', '=', sourcing_line.partner_id.id),
                ('state', 'in', ['draft']),
                ('delivery_requested_date', '=', self.compute_delivery_requested_date(cr, uid, sourcing_line.id, context=context)),
                ('order_type', 'in', ['loan', 'loan_return']),
                ('is_a_counterpart', '=', True),
                ('unique_fo_id', '=', sourcing_line.order_id.id),
            ]
            res_id = self.pool.get('purchase.order').search(cr, uid, domain, context=context)

        if res_id and isinstance(res_id, list):
            res_id = res_id[0]

        return res_id or False


    def create_po_from_sourcing_line(self, cr, uid, ids, context=None):
        '''
        Create an new PO/DPO from sourcing line
        @return id of the newly created PO/DPO
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for sourcing_line in self.browse(cr, uid, ids, context=context):
            # commom fields:
            po_values = {
                'origin': sourcing_line.order_id.name,
                'partner_id': sourcing_line.supplier.id,
                'partner_address_id': self.pool.get('res.partner').address_get(cr, uid, [sourcing_line.supplier.id], ['default'])['default'],
                'customer_id': sourcing_line.order_id.partner_id.id,
                'location_id': self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True)], context=context)[0],
                'cross_docking_ok': False if (sourcing_line.order_id.procurement_request and sourcing_line.order_id.location_requestor_id.usage != 'customer') else True,
                'pricelist_id': sourcing_line.supplier.property_product_pricelist_purchase.id,
                'fiscal_position': sourcing_line.supplier.property_account_position and sourcing_line.supplier.property_account_position.id or False,
                'warehouse_id': sourcing_line.order_id.warehouse_id.id,
                'categ': sourcing_line.categ,
                'priority': sourcing_line.order_id.priority,
                'details': sourcing_line.order_id.details,
                'delivery_requested_date': sourcing_line.date_planned,
                'related_sourcing_id': sourcing_line.related_sourcing_id.id or False,
                'unique_fo_id': sourcing_line.order_id.id if sourcing_line.supplier.po_by_project == 'isolated' else False,
            }
            if sourcing_line.po_cft == 'po':  # Purchase Order
                po_values.update({
                    'order_type': 'regular',
                })
            elif sourcing_line.po_cft == 'dpo':  # Direct Purchase Order
                po_values.update({
                    'order_type': 'direct',
                    'dest_partner_id': sourcing_line.order_id.partner_id.id,
                    'dest_address_id': sourcing_line.order_id.partner_shipping_id.id,
                })
                #if sourcing_line.order_id.partner_id.partner_type in ('esc', 'external'):
                #    po_values['po_version'] = 2 # TODO NEEDED ?
            elif sourcing_line.po_cft == 'pli':  # Purchase List
                po_values.update({'order_type': 'purchase_list'})

        return self.pool.get('purchase.order').create(cr, uid, po_values, context=context)


    def compute_delivery_requested_date(self, cr, uid, ids, context=None):
        '''
        compute delivery requested date for PO thanks to the date planned and the loan duration
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        sol = self.browse(cr, uid, ids[0], context=context)
        delivery_requested_date = datetime.strptime(sol.date_planned, DEFAULT_SERVER_DATE_FORMAT)
        delivery_requested_date = delivery_requested_date + relativedelta(months=sol.order_id.loan_duration or 0)
        delivery_requested_date = delivery_requested_date.strftime(DEFAULT_SERVER_DATE_FORMAT)

        return delivery_requested_date


    def create_po_loan_for_goods_return(self, cr, uid, ids, context=None):
        '''
        Create PO to return loaned goods at expiry date
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        for sourcing_line in self.browse(cr, uid, ids, context=context):
            po_values = {
                'order_type': 'loan_return',
                'origin': sourcing_line.order_id.name,
                'partner_id': sourcing_line.order_partner_id.id,
                'partner_address_id': self.pool.get('res.partner').address_get(cr, uid, [sourcing_line.order_partner_id.id], ['default'])['default'],
                'pricelist_id': sourcing_line.order_partner_id.property_product_pricelist_purchase.id,
                'location_id': self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True)], context=context)[0],
                'warehouse_id': sourcing_line.order_id.warehouse_id.id,
                'categ': sourcing_line.categ,
                'priority': sourcing_line.order_id.priority,
                'details': sourcing_line.order_id.details,
                'delivery_requested_date': self.compute_delivery_requested_date(cr, uid, sourcing_line.id, context=context),
                'related_sourcing_id': sourcing_line.related_sourcing_id.id or False,
                'unique_fo_id': sourcing_line.order_id.id,
                'is_a_counterpart': True,
                'loan_duration': sourcing_line.order_id.loan_duration,
            }

        return self.pool.get('purchase.order').create(cr, uid, po_values, context=context)


    def get_existing_tender(self, cr, uid, ids, context=None):
        '''
        Search for an existing tender to use for the given sale.order.line
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            return False

        sol = self.browse(cr, uid, ids[0], context=context)

        tender_to_use = self.pool.get('tender').search(cr, uid, [
            ('sale_order_id', '=', sol.order_id.id),
            ('state', '=', 'draft'),
        ], context=context)

        return tender_to_use[0] if tender_to_use else False


    def create_tender_from_sourcing_line(self, cr, uid, ids, context=None):
        '''
        create a tender with given sourcing line (=sale.order.line)
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            return False

        proc_location_id = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'procurement')], context=context)
        proc_location_id = proc_location_id[0] if proc_location_id else False

        new_tender_id = False
        sol = self.browse(cr, uid, ids[0], context=context)

        new_tender_id = self.pool.get('tender').create(cr, uid, {
            'sale_order_id': sol.order_id.id,
            'location_id': proc_location_id,
            'categ': sol.order_id.categ,
            'priority': sol.order_id.priority,
            'warehouse_id': sol.order_id.shop_id.warehouse_id.id,
            'requested_date': sol.date_planned,
        }, context=context)

        return new_tender_id


    def create_rfq_from_sourcing_line(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            return False

        new_rfq_id = False
        sol = self.browse(cr, uid, ids[0], context=context)

        rfq_values = {
            'origin': sol.order_id.name,
            'rfq_ok': True,
            'partner_id': sol.supplier.id,
            'partner_address_id': self.pool.get('res.partner').address_get(cr, uid, [sol.supplier.id], ['default'])['default'],
            'location_id': self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True)], context=context)[0],
            'pricelist_id': sol.supplier.property_product_pricelist_purchase.id,
            # 'company_id': tender.company_id.id,
            'fiscal_position': sol.supplier.property_account_position and sol.supplier.property_account_position.id or False,
            'warehouse_id': sol.order_id.warehouse_id.id,
            'categ': sol.categ,
            'priority': sol.order_id.priority,
            'details': sol.order_id.details,
            'delivery_requested_date': sol.date_planned,
            # 'rfq_delivery_address': tender.delivery_address and tender.delivery_address.id or False,
            'from_procurement': True,
        }
        context.update({'rfq_ok': True})
        new_rfq_id = self.pool.get('purchase.order').create(cr, uid, rfq_values, context=context)

        return new_rfq_id


    def check_location_integrity(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        med_loc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_medical')[1]
        log_loc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_logistic')[1]
        stock_loc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1]

        for sourcing_line in self.browse(cr, uid, ids, context=context):
            if not sourcing_line.order_id.procurement_request:
                continue
            if sourcing_line.order_id.location_requestor_id.id in (med_loc_id, log_loc_id) and sourcing_line.location_id.id == stock_loc_id:
                raise osv.except_osv(
                    _('Error'),
                    _('You cannot source with location \'Stock\' if the destination location of the Internal request is LOG or MED')
                )
            elif sourcing_line.order_id.location_requestor_id.id == sourcing_line.location_id.id:
                raise osv.except_osv(
                    _('Error'),
                    _('You cannot choose a source location which is the destination location of the Internal request')
                )

        return True


    def source_line(self, cr, uid, ids, context=None):
        """
        Source a sale.order.line
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        pricelist_obj = self.pool.get('product.pricelist')
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')

        company_currency_id = self.pool.get('res.users').get_company_currency_id(cr, uid)

        for sourcing_line in self.browse(cr, uid, ids, context=context):
            if sourcing_line.procurement_request:  # Check constraints on lines
                check_vals = {'constraints': 'consumption'}
            else:
                check_vals = {'obj_type': 'sale.order', 'partner_id': sourcing_line.order_id.partner_id.id}
            if sourcing_line.product_id.id:
                self.pool.get('product.product')._get_restriction_error(cr, uid, [sourcing_line.product_id.id], vals=check_vals,
                                                                        context=context)
            if sourcing_line.supplier and sourcing_line.supplier_type == 'esc' and \
                    sourcing_line.supplier_split_po == 'yes' and not sourcing_line.related_sourcing_id:
                raise osv.except_osv(_('Error'), _('For this Supplier you have to select a Sourcing Group'))
            if sourcing_line.state in ['validated', 'validated_p']:
                if sourcing_line.type == 'make_to_stock':
                    self.check_location_integrity(cr, uid, [sourcing_line.id], context=context)
                    so_line_data = {'confirmed_delivery_date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)}
                    if sourcing_line.order_id.order_type == 'loan' and not sourcing_line.order_id.is_a_counterpart:
                        # In case of loan, create the PO for later goods return:
                        po_loan = self.get_existing_po_loan_for_goods_return(cr, uid, sourcing_line.id, context=context)
                        if not po_loan:
                            po_loan = self.create_po_loan_for_goods_return(cr, uid, sourcing_line.id, context=context)
                            po = po_obj.browse(cr, uid, po_loan, context=context)
                            po_obj.log(cr, uid, po_loan, _('The Purchase Order %s for supplier %s has been created.') % (po.name, po.partner_id.name))
                            po_obj.infolog(cr, uid, 'The Purchase order %s for supplier %s has been created.' % (po.name, po.partner_id.name))

                        # attach PO line:
                        pol_values = {
                            'order_id': po_loan,
                            'product_id': sourcing_line.product_id.id,
                            'product_uom': sourcing_line.product_id.uom_id.id,
                            'product_qty': sourcing_line.product_uom_qty,
                            'price_unit': sourcing_line.price_unit if sourcing_line.price_unit > 0 else sourcing_line.product_id.standard_price,
                            'partner_id': sourcing_line.order_partner_id.id,
                            'loan_line_id': sourcing_line.id,
                        }
                        cp_po_line_id = pol_obj.create(cr, uid, pol_values, context=context)
                        so_line_data['counterpart_po_line_id'] = cp_po_line_id
                    # sourcing line: set delivery confirmed date to today:
                    self.write(cr, uid, [sourcing_line.id], so_line_data, context=context)

                    # update SO line with good state:
                    wf_service.trg_validate(uid, 'sale.order.line', sourcing_line.id, 'sourced', cr)
                    wf_service.trg_validate(uid, 'sale.order.line', sourcing_line.id, 'confirmed', cr) # confirmation create pick/out or INT

                elif sourcing_line.type == 'make_to_order':
                    if sourcing_line.po_cft in ('po', 'dpo', 'pli'):
                        po_to_use = self.get_existing_po(cr, uid, sourcing_line.id, context=context)
                        if not po_to_use:  # then create new PO:
                            po_to_use = self.create_po_from_sourcing_line(cr, uid, sourcing_line.id, context=context)
                            # log new PO:
                            po = po_obj.browse(cr, uid, po_to_use, fields_to_fetch=['pricelist_id', 'partner_id', 'name'],  context=context)
                            po_obj.log(cr, uid, po_to_use, _('The Purchase Order %s for supplier %s has been created.') % (po.name, po.partner_id.name))
                            po_obj.infolog(cr, uid, 'The Purchase order %s for supplier %s has been created.' % (po.name, po.partner_id.name))
                        else:
                            po = po_obj.browse(cr, uid, po_to_use, fields_to_fetch=['pricelist_id', 'partner_id'], context=context)
                            po_obj.update_details_po(cr, uid, po_to_use, sourcing_line.order_id.id, context=context)

                        target_currency_id = po.pricelist_id.currency_id.id
                        # No AD on sourcing line if it comes from IR:
                        anal_dist = False
                        if not sourcing_line.order_id.procurement_request:
                            distib_to_copy = False
                            if sourcing_line.analytic_distribution_id:
                                distib_to_copy = sourcing_line.analytic_distribution_id.id
                            elif sourcing_line.order_id.analytic_distribution_id:
                                distib_to_copy = sourcing_line.order_id.analytic_distribution_id.id
                            else:
                                raise osv.except_osv(
                                    _('Warning'),
                                    _('AD missing on line %s, FO %s') % (sourcing_line.line_number, sourcing_line.order_id.name),
                                )

                            anal_dist = self.pool.get('analytic.distribution').copy(cr, uid, distib_to_copy, {'partner_type': po.partner_id.partner_type}, context=context)

                        # set unit price
                        price = 0.0
                        if sourcing_line.product_id and sourcing_line.supplier.property_product_pricelist_purchase:
                            price_dict = pricelist_obj.price_get(cr, uid, [sourcing_line.supplier.property_product_pricelist_purchase.id],
                                                                 sourcing_line.product_id.id, sourcing_line.product_uom_qty,
                                                                 sourcing_line.supplier.id, {'uom': sourcing_line.product_uom.id})
                            if price_dict[sourcing_line.supplier.property_product_pricelist_purchase.id]:
                                price = price_dict[sourcing_line.supplier.property_product_pricelist_purchase.id]

                        if not price:
                            if not sourcing_line.product_id and sourcing_line.comment:  # Product by nomenclature
                                price = sourcing_line.price_unit or 0.0
                            else:
                                price = sourcing_line.product_id and sourcing_line.product_id.standard_price or 0.0
                            if price and company_currency_id != target_currency_id:
                                price = self.pool.get('res.currency').compute(cr, uid, company_currency_id, target_currency_id, price, round=False, context=context)

                        pol_values = {
                            'order_id': po_to_use,
                            'product_id': sourcing_line.product_id.id or False,
                            'product_uom': sourcing_line.product_id and sourcing_line.product_id.uom_id.id or sourcing_line.product_uom.id,
                            'product_qty': sourcing_line.product_uom_qty,
                            'price_unit': price,
                            'partner_id': sourcing_line.supplier.id,
                            'origin': sourcing_line.order_id.name,
                            'sale_order_line_id': sourcing_line.id,
                            'linked_sol_id': sourcing_line.id,
                            'analytic_distribution_id': anal_dist,
                            'link_so_id': sourcing_line.order_id.id,
                            'nomen_manda_0': sourcing_line.nomen_manda_0.id or False,
                            'nomen_manda_1': sourcing_line.nomen_manda_1.id or False,
                            'nomen_manda_2': sourcing_line.nomen_manda_2.id or False,
                            'nomen_manda_3': sourcing_line.nomen_manda_3.id or False,
                            'date_planned': sourcing_line.date_planned,
                            'stock_take_date': sourcing_line.stock_take_date or False,
                            'original_product': sourcing_line.original_product and sourcing_line.original_product.id or False,
                            'original_qty': sourcing_line.original_qty,
                            'original_uom': sourcing_line.original_uom.id
                        }
                        if not sourcing_line.product_id:
                            pol_values['name'] = sourcing_line.comment
                        pol_obj.create(cr, uid, pol_values, context=context)
                        po_obj.write(cr, uid, po_to_use, {'dest_partner_ids': [(4, sourcing_line.order_id.partner_id.id, 0)]}, context=context)
                        po_obj.update_source_document(cr, uid, po_to_use, sourcing_line.order_id.id, context=context)

                    elif sourcing_line.po_cft == 'rfq':
                        rfq_to_use = self.get_existing_rfq(cr, uid, sourcing_line.id, context=context)
                        if not rfq_to_use:
                            rfq_to_use = self.create_rfq_from_sourcing_line(cr, uid, sourcing_line.id, context=context)
                            # log new RfQ:
                            rfq = po_obj.browse(cr, uid, rfq_to_use, context=context)
                            po_obj.log(cr, uid, rfq_to_use, _('The Request for Quotation %s for supplier %s has been created.')
                                       % (rfq.name, rfq.partner_id.name), action_xmlid='purchase.purchase_rfq')
                            po_obj.infolog(cr, uid, _('The Request for Quotation %s for supplier %s has been created.') % (rfq.name, rfq.partner_id.name))
                        else:
                            rfq = po_obj.browse(cr, uid, rfq_to_use, fields_to_fetch=['pricelist_id'], context=context)
                            po_obj.update_details_po(cr, uid, rfq_to_use, sourcing_line.order_id.id, context=context)

                        target_currency_id = rfq.pricelist_id.currency_id.id

                        anal_dist = False
                        if not sourcing_line.order_id.procurement_request:
                            distrib = False
                            if sourcing_line.analytic_distribution_id:
                                distrib = sourcing_line.analytic_distribution_id.id
                            elif sourcing_line.order_id.analytic_distribution_id:
                                distrib = sourcing_line.order_id.analytic_distribution_id.id
                            else:
                                raise osv.except_osv(
                                    _('Warning'),
                                    _('AD missing on line %s, FO %s') % (sourcing_line.line_number, sourcing_line.order_id.name),
                                )

                            anal_dist = self.pool.get('analytic.distribution').copy(cr, uid, distrib, {}, context=context)
                        # attach new RfQ line:
                        price_unit = sourcing_line.price_unit if sourcing_line.price_unit > 0 else sourcing_line.product_id.standard_price
                        if sourcing_line.price_unit > 0:
                            src_currency = sourcing_line.currency_id.id
                        else:
                            src_currency = company_currency_id

                        if price_unit and src_currency != target_currency_id:
                            price_unit = self.pool.get('res.currency').compute(cr, uid, src_currency, target_currency_id, price_unit, round=False, context=context)

                        rfq_line_values = {
                            'order_id': rfq_to_use,
                            'product_id': sourcing_line.product_id.id,
                            'product_uom': sourcing_line.product_id.uom_id.id,
                            'product_qty': sourcing_line.product_uom_qty,
                            'price_unit': price_unit,
                            'partner_id': sourcing_line.supplier.id,
                            'origin': sourcing_line.order_id.name,
                            'sale_order_line_id': sourcing_line.id,
                            'linked_sol_id': sourcing_line.id,
                            'analytic_distribution_id': anal_dist,
                            'link_so_id': sourcing_line.order_id.id,
                            'original_product': sourcing_line.original_product and sourcing_line.original_product.id or False,
                            'original_qty': sourcing_line.original_qty,
                            'original_uom': sourcing_line.original_uom.id,
                        }
                        pol_obj.create(cr, uid, rfq_line_values, context=context)
                        po_obj.update_source_document(cr, uid, rfq_to_use, sourcing_line.order_id.id, context=context)

                    elif sourcing_line.po_cft == 'cft':
                        tender_to_use = self.get_existing_tender(cr, uid, sourcing_line.id, context=context)
                        if not tender_to_use:
                            tender_to_use = self.create_tender_from_sourcing_line(cr, uid, sourcing_line.id, context=context)
                            # log new tender:
                            tender = self.pool.get('tender').browse(cr, uid, tender_to_use, context=context)
                            self.pool.get('tender').log(cr, uid, tender_to_use, _('The Tender %s has been created.') % (tender.name,))
                            self.pool.get('tender').infolog(cr, uid, 'The Tender %s has been created.' % (tender.name,))
                        # attach tender line:
                        proc_location_id = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'procurement')], context=context)
                        proc_location_id = proc_location_id[0] if proc_location_id else False
                        tender_values = {
                            'product_id': sourcing_line.product_id.id,
                            'comment': sourcing_line.comment,
                            'qty': sourcing_line.product_uom_qty,
                            'product_uom': sourcing_line.product_id.uom_id.id,
                            'tender_id': tender_to_use,
                            'sale_order_line_id': sourcing_line.id,
                            'location_id': proc_location_id,
                            'original_product': sourcing_line.original_product and sourcing_line.original_product.id or False,
                            'original_qty': sourcing_line.original_qty,
                            'original_uom': sourcing_line.original_uom.id,
                        }
                        self.pool.get('tender.line').create(cr, uid, tender_values, context=context)
                    else:
                        raise osv.except_osv(_('Error'), _('Line %s of order %s, please select a PO/CFT in the Order Sourcing Tool') % (sourcing_line.line_number, sourcing_line.order_id.name))

                    wf_service.trg_validate(uid, 'sale.order.line', sourcing_line.id, 'sourced', cr)

        return True


    def check_confirm_order(self, cr, uid, ids, run_scheduler=False, context=None, update_lines=True):
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

        if isinstance(ids, int):
            ids = [ids]

        order_to_check = {}
        for line in self.read(cr, uid, ids, ['order_id', 'estimated_delivery_date', 'price_unit', 'product_uom_qty'], context=context):
            order_data = order_obj.read(cr, uid, line['order_id'][0], ['procurement_request', 'order_type', 'state'], context=context)
            order_proc = order_data['procurement_request']
            order_type = order_data['order_type']
            if order_data['state'] != 'validated':
                continue
            state_to_use = order_proc and 'confirmed' or 'sourced'
            if update_lines:
                self.write(cr, uid, [line['id']], {
                    'state': state_to_use,
                    'cf_estimated_delivery_date': line['estimated_delivery_date'],
                }, context=context)
            if line['order_id'][0] not in order_to_check:
                order_to_check.update({line['order_id'][0]: state_to_use})

            if order_type in ['regular', 'donation_prog'] and not order_proc and line['price_unit'] * line['product_uom_qty'] < 0.00001:
                raise osv.except_osv(
                    _('Warning'),
                    _('You cannot confirm the sourcing of a line with a subtotal of zero.'),
                )

        order_to_process = {}
        for order_id, state_to_use in order_to_check.items():
            lines_not_confirmed = self.search(cr, uid, [
                ('order_id', '=', order_id),
                ('state', '!=', state_to_use),
            ], count=True, context=context)

            if lines_not_confirmed:
                pass
            else:
                order_to_process.setdefault(state_to_use, [])
                order_to_process[state_to_use].append(order_id)

        for state_to_use, val in order_to_process.items():
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

                    order = self.pool.get('sale.order').read(cr, uid, order_id, ['name'], context=context)
                    self.infolog(cr, uid, "All lines of the FO/IR id:%s (%s) have been sourced" % (
                        order['id'],
                        order['name'],
                    ))

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
            except osv.except_osv as e:
                logging.getLogger('so confirmation').warn('Osv Exception', exc_info=True)
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
            except Exception as e:
                logging.getLogger('so confirmation').warn('Exception', exc_info=True)
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

        if isinstance(ids, int):
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

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0, uom=False, qty_uos=0, uos=False, name='',
                          partner_id=False, lang=False, update_tax=True, date_order=False, packaging=False,
                          fiscal_position=False, flag=False, context=None):
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
        if context is None:
            context = {}

        # Objects
        product_obj = self.pool.get('product.product')

        result = super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom, qty_uos,
                                                                uos, name, partner_id, lang, update_tax, date_order,
                                                                packaging, fiscal_position, flag, context=context)

        # Add supplier
        sellerId = False
        po_cft = False
        l_type = 'type' in result['value'] and result['value']['type']

        line = None
        if ids:
            line = self.browse(cr, uid, ids[0])

        if product and type:
            if l_type == 'make_to_order':
                seller = product_obj.browse(cr, uid, product).seller_id
                sellerId = (seller and (seller.supplier or seller.manufacturer or seller.transporter) and seller.id) or False

                po_cft = 'po'
                if line and \
                    ((line.product_id and line.product_id.type == 'service_recep') or \
                     (not line.product_id and check_is_service_nomen(self, cr, uid, line.nomen_manda_0.id))) and \
                        line.order_id and not line.order_id.procurement_request:
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
                value.update({
                    'supplier': False,
                    'related_sourcing_id': False,
                })
            if po_cft == 'rfq':
                value['related_sourcing_id'] = False

        if line_id and isinstance(line_id, list):
            line_id = line_id[0]

        res = {'value': value, 'warning': warning}

        line = self.browse(cr, uid, line_id, context=context)

        cond1 = line.product_id.type == 'service_recep'
        cond2 = not line.product_id and check_is_service_nomen(self, cr, uid, line.nomen_manda_0.id)
        cond3 = not line.order_id.procurement_request and po_cft in ['po', 'pli']

        if (cond1 or cond2) and cond3:
            res['warning'] = {
                'title': _('Warning'),
                'message': _("""'Purchase Order' and 'Purchase List' are not allowed to source a 'Service' product."""),
            }
            res['value'].update({'po_cft': 'dpo'})

        partner_id = 'supplier' in value and value['supplier'] or partner_id

        if partner_id:
            p_type = self.pool.get('res.partner').read(cr, uid, partner_id, ['partner_type'], context=context)['partner_type']
            if po_cft == 'pli' and p_type != 'external':
                res['warning'] = {
                    'title': _('Warning'),
                    'message': _("""'Purchase List' is not allowed with a non-external partner."""),
                }
                res['value'].update({'po_cft': 'po'})

        if line_id and partner_id and line.product_id:
            check_fnct = product_obj._on_change_restriction_error
            res, error = self._check_product_constraints(
                cr,
                uid,
                line.type,
                value.get('po_cft', line.po_cft),
                line.product_id.id,
                partner_id,
                False,
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
            if l_type == 'make_to_order' and line.product_id and line.product_id.seller_id and \
                    (line.product_id.seller_id.supplier or line.product_id.seller_id.manufacturer
                     or line.product_id.seller_id.transporter):
                value['supplier'] = line.product_id.seller_id.id
        if l_type == 'make_to_stock':
            if not location_id:
                wh_ids = wh_obj.search(cr, uid, [], context=context)
                if wh_ids:
                    value['location_id'] = wh_obj.browse(cr, uid, wh_ids[0], context=context).lot_stock_id.id

            value.update({
                'po_cft': False,
                'related_sourcing_ok': False,
                'related_sourcing_id': False,
                'supplier': False,
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
                        False,
                        check_fnct,
                        field_name='l_type',
                        values=res,
                        vals={'constraints': ['storage'], 'obj_type': 'sale.order', 'partner_id': line.order_id.partner_id.id},
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
                'supplier_type': False,
                'supplier_split_po': False,
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

        # Look if the partner is the same res_partner as Local Market
        data_obj = self.pool.get('ir.model.data')
        is_loc_mar = data_obj.search_exists(cr, uid, [('module', '=', 'order_types'), ('model', '=', 'res.partner'),
                                                      ('name', '=', 'res_partner_local_market'), ('res_id', '=', partner.id)], context=context)
        if is_loc_mar:
            result['value'].update({'po_cft': 'pli'})

        # If the selected partner belongs to product->suppliers, we take that delay (from supplierinfo)
        line = self.browse(cr, uid, line_id, context=context)
        delay = self.check_supplierinfo(line, partner, context=context)

        estDeliveryDate = date.today() + relativedelta(days=int(delay))

        related_sourcing_ok = self._check_related_sourcing_ok(cr, uid, supplier, l_type, context=context)
        result['value'].update({
            'estimated_delivery_date': estDeliveryDate.strftime('%Y-%m-%d'),
            'related_sourcing_ok': related_sourcing_ok,
            'supplier_type': partner and partner.partner_type or False,
            'supplier_split_po': partner and partner.split_po or False,
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
                False,
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
                   context=None, orderby=False, count=False):
        res = super(sale_order_line, self).read_group(cr, uid, domain, fields,
                                                      groupby, offset=offset, limit=limit, context=context,
                                                      orderby=orderby, count=count)

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

    def view_docs_with_product(self, cr, uid, ids, menu_action, context=None):
        '''
        Get info from the given menu action to return the right view with the right data
        '''
        if context is None:
            context = {}

        res = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, menu_action, ['tree', 'form'], new_tab=True, context=context)

        res_context = res.get('context', False) and safe_eval(res['context']) or {}
        for col in res_context:  # Remove the default filters
            if 'search_default_' in col:
                res_context[col] = False

        sol_product_id = False
        if context.get('active_id', False):
            sol_product_id = self.read(cr, uid, context['active_id'], ['product_id'], context=context)['product_id'][0]
        res_context['search_default_product_id'] = sol_product_id
        res['context'] = res_context

        return res


sale_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
